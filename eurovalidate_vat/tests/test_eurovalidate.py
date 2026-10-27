# Copyright 2026 EuroValidate (https://eurovalidate.com)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Odoo tests: run with ``odoo-bin -d <db> --test-enable -i eurovalidate_vat --stop-after-init``.

``requests.get`` is mocked; no network access is needed.
"""

from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

PATCH_TARGET = "odoo.addons.eurovalidate_vat.models.eurovalidate_client.requests.get"


def _resp(status_code, payload):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    return resp


VALID = {
    "vat_number": "NL820646660B01",
    "country_code": "NL",
    "status": "valid",
    "company_name": "ABN AMRO BANK N.V.",
    "company_address": "GUSTAV MAHLERLAAN 00010\n1082PP AMSTERDAM",
    "request_id": "req_test_1",
    "meta": {"confidence": "high", "source": "vies_live", "cached": False, "last_verified": "2026-10-27T10:00:00Z"},
}
INVALID = dict(VALID, status="invalid", company_name=None, company_address=None)
UNAVAILABLE = dict(VALID, status="unavailable", company_name=None, company_address=None,
                   meta={"confidence": "unknown", "source": "vies_live", "upstream_status": "unavailable"})
QUOTA = {"type": "about:blank", "title": "Monthly quota exceeded", "status": 429, "detail": "Monthly quota exceeded (100)."}


@tagged("post_install", "-at_install")
class TestEuroValidate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.icp = cls.env["ir.config_parameter"].sudo()
        cls.icp.set_param("eurovalidate.api_key", "ev_test_key")
        cls.icp.set_param("eurovalidate.autofill", "True")
        cls.icp.set_param("eurovalidate.block_invalid", "False")
        cls.icp.set_param("eurovalidate.quota_warned_at", "")
        from ..models import res_partner as rp
        rp._QUOTA_WARNED_AT.clear()
        cls.Partner = cls.env["res.partner"]

    def test_valid_fills_fields_and_evidence(self):
        with patch(PATCH_TARGET, return_value=_resp(200, VALID)) as get:
            partner = self.Partner.create({"name": "", "vat": "NL820646660B01", "is_company": True})
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.kwargs["headers"]["X-API-Key"], "ev_test_key")
        self.assertEqual(partner.ev_status, "valid")
        self.assertEqual(partner.ev_confidence, "high")
        self.assertEqual(partner.name, "ABN AMRO BANK N.V.")
        self.assertEqual(partner.street, "GUSTAV MAHLERLAAN 00010")
        self.assertEqual(partner.zip, "1082PP")
        self.assertEqual(partner.city, "AMSTERDAM")
        self.assertEqual(partner.country_id.code, "NL")
        self.assertEqual(partner.ev_request_id, "req_test_1")
        self.assertEqual(partner.ev_source, "vies_live")
        self.assertTrue(partner.ev_last_verified)

    def test_autofill_never_overwrites_existing_name(self):
        with patch(PATCH_TARGET, return_value=_resp(200, VALID)):
            partner = self.Partner.create({"name": "My Own Name", "vat": "NL820646660B01", "city": "Utrecht"})
        self.assertEqual(partner.name, "My Own Name")
        self.assertEqual(partner.city, "Utrecht")
        self.assertEqual(partner.ev_company_name, "ABN AMRO BANK N.V.")

    def test_invalid_blocks_when_configured(self):
        self.icp.set_param("eurovalidate.block_invalid", "True")
        # Format-valid (passes base_vat's own elfproef) but unregistered → our block
        with patch(PATCH_TARGET, return_value=_resp(200, INVALID)):
            with self.assertRaises(ValidationError):
                self.Partner.create({"name": "Bad Co", "vat": "NL123456782B01"})
        self.icp.set_param("eurovalidate.block_invalid", "False")
        with patch(PATCH_TARGET, return_value=_resp(200, INVALID)):
            partner = self.Partner.create({"name": "Bad Co", "vat": "NL123456782B01"})
        self.assertEqual(partner.ev_status, "invalid")

    def test_quota_raises_once_then_silent(self):
        with patch(PATCH_TARGET, return_value=_resp(429, QUOTA)):
            with self.assertRaises(UserError):
                self.Partner.create({"name": "A", "vat": "NL820646660B01"})
            # second call within 10 minutes: no error, record saved as unavailable
            partner = self.Partner.create({"name": "B", "vat": "NL820646660B01"})
        self.assertEqual(partner.ev_status, "unavailable")

    def test_unavailable_never_breaks_save(self):
        self.icp.set_param("eurovalidate.block_invalid", "True")
        with patch(PATCH_TARGET, return_value=_resp(200, UNAVAILABLE)):
            partner = self.Partner.create({"name": "Pending Co", "vat": "CZ25596641"})
        self.assertEqual(partner.ev_status, "unavailable")
        self.assertEqual(partner.name, "Pending Co")
        self.icp.set_param("eurovalidate.block_invalid", "False")

    def test_network_failure_is_unavailable(self):
        import requests

        with patch(PATCH_TARGET, side_effect=requests.exceptions.ConnectTimeout("boom")):
            partner = self.Partner.create({"name": "Offline Co", "vat": "DE811569869"})
        self.assertEqual(partner.ev_status, "unavailable")

    def test_write_revalidates_only_when_vat_changes(self):
        with patch(PATCH_TARGET, return_value=_resp(200, VALID)) as get:
            partner = self.Partner.create({"name": "X", "vat": "NL820646660B01"})
            partner.write({"phone": "+31 20 000 0000"})
            self.assertEqual(get.call_count, 1)
            partner.write({"vat": "NL820646660B01"})
            self.assertEqual(get.call_count, 2)

    def test_onchange_warning_for_invalid(self):
        with patch(PATCH_TARGET, return_value=_resp(200, INVALID)):
            partner = self.Partner.new({"name": "Draft", "vat": "NL000000000B00"})
            res = partner._onchange_vat_eurovalidate()
        self.assertIn("INVALID", res["warning"]["message"])
        self.assertEqual(partner.ev_status, "invalid")

    def test_no_key_is_silent(self):
        self.icp.set_param("eurovalidate.api_key", "")
        with patch(PATCH_TARGET) as get:
            partner = self.Partner.create({"name": "No Key Co", "vat": "NL820646660B01"})
        self.assertEqual(get.call_count, 0)
        self.assertEqual(partner.ev_status, "unknown")
        self.icp.set_param("eurovalidate.api_key", "ev_test_key")
