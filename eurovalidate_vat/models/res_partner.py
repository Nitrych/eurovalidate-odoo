# Copyright 2026 EuroValidate (https://eurovalidate.com)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Partner VAT validation through EuroValidate.

Decision table (what the module does with an answer):

======================  ======================================================
answer                  effect on the partner
======================  ======================================================
valid                   ev_status=valid; name/street/zip/city/country filled
                        when empty (autofill on); evidence fields stored
invalid, confidence     ev_status=invalid; non-blocking warning on the form;
high / medium           ValidationError on save when "block invalid" is on
invalid, confidence     treated as pending: ev_status=invalid but never blocks
low / unknown           (the register itself was not reachable)
unavailable             ev_status=unavailable; record saved; warning
                        "pending — re-validate later"
unverified              ev_status=unverified (format/checksum only, CL/TR/IL/
                        MX/CA/PH); informational, never blocks
error / bad input       ev_status=error; warning; never blocks
429 quota               one UserError with the upgrade hint, then silent for
                        10 minutes; the save goes through with ev_status
                        unavailable
401 bad key / 403       warning pointing to Settings; never blocks
network failure         ev_status=unavailable; INFO log with the VAT masked
======================  ======================================================
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from . import eurovalidate_client as client
from .res_config_settings import (
    PARAM_API_KEY,
    PARAM_AUTOFILL,
    PARAM_BASE_URL,
    PARAM_BLOCK_INVALID,
)

_logger = logging.getLogger(__name__)

QUOTA_WARNING_SILENCE = timedelta(minutes=10)
# dbname -> datetime of the last quota UserError shown in this process
_QUOTA_WARNED_AT: dict = {}
STATUS_SELECTION = [
    ("valid", "Valid"),
    ("invalid", "Invalid"),
    ("unavailable", "Unavailable (register down)"),
    ("unverified", "Format only (no register)"),
    ("error", "Error"),
    ("unknown", "Not checked"),
]
CONFIDENCE_SELECTION = [
    ("high", "High"),
    ("medium", "Medium"),
    ("low", "Low"),
    ("unknown", "Unknown"),
]


class ResPartner(models.Model):
    _inherit = "res.partner"

    ev_status = fields.Selection(
        STATUS_SELECTION, string="EuroValidate status", default="unknown", copy=False, readonly=True
    )
    ev_confidence = fields.Selection(
        CONFIDENCE_SELECTION, string="Confidence", default="unknown", copy=False, readonly=True
    )
    ev_company_name = fields.Char(string="Registered name", copy=False, readonly=True)
    ev_company_address = fields.Text(string="Registered address", copy=False, readonly=True)
    ev_request_id = fields.Char(
        string="Request id", copy=False, readonly=True, help="Evidence of the validation for audits."
    )
    ev_last_verified = fields.Datetime(string="Last verified", copy=False, readonly=True)
    ev_source = fields.Char(
        string="Source", copy=False, readonly=True, help="vies_live, vies_cached, hmrc, brreg, …"
    )

    # ── configuration helpers ────────────────────────────────────────────
    @api.model
    def _ev_params(self):
        icp = self.env["ir.config_parameter"].sudo()
        return {
            "api_key": (icp.get_param(PARAM_API_KEY) or "").strip(),
            "autofill": icp.get_param(PARAM_AUTOFILL, "True") not in ("False", "0", ""),
            "block_invalid": icp.get_param(PARAM_BLOCK_INVALID, "False") in ("True", "1"),
            "base_url": icp.get_param(PARAM_BASE_URL) or client.DEFAULT_BASE_URL,
        }

    @api.model
    def _ev_quota_warning_due(self):
        """True once per QUOTA_WARNING_SILENCE window, per database and process.

        The stamp lives in process memory, not in ir.config_parameter: the
        UserError we are about to raise rolls the whole request back, so a
        database stamp would be undone with it and the user would see the
        error on every save. With several Odoo workers each warns once —
        acceptable for a 10-minute silence window."""
        now = fields.Datetime.now()
        last = _QUOTA_WARNED_AT.get(self.env.cr.dbname)
        if last and now - last < QUOTA_WARNING_SILENCE:
            return False
        _QUOTA_WARNED_AT[self.env.cr.dbname] = now
        return True

    # ── core ─────────────────────────────────────────────────────────────
    def _ev_lookup(self, vat):
        params = self._ev_params()
        if not params["api_key"]:
            return dict(
                client.parse_response(401, {}),
                detail=_(
                    "No EuroValidate API key configured. Add one under "
                    "Settings > General Settings > EuroValidate."
                ),
            )
        return client.lookup_vat(vat, params["api_key"], params["base_url"])

    def _ev_apply(self, result, autofill):
        """Translate an answer into partner values. Returns the dict to write."""
        self.ensure_one()
        status = result["status"] if result["status"] in dict(STATUS_SELECTION) else "unknown"
        confidence = (
            result["confidence"] if result["confidence"] in dict(CONFIDENCE_SELECTION) else "unknown"
        )
        vals = {
            "ev_status": status,
            "ev_confidence": confidence,
            "ev_company_name": result.get("company_name"),
            "ev_company_address": result.get("company_address"),
            "ev_request_id": result.get("request_id"),
            "ev_source": result.get("source"),
        }
        if result["outcome"] == "ok":
            vals["ev_last_verified"] = fields.Datetime.now()
        if result["outcome"] == "ok" and result["status"] == "valid" and autofill:
            vals.update(self._ev_autofill_vals(result))
        return vals

    def _ev_autofill_vals(self, result):
        """Fill only empty fields from the registered name/address."""
        self.ensure_one()
        vals = {}
        if result.get("company_name") and not (self.name or "").strip():
            vals["name"] = result["company_name"]
        address = result.get("company_address") or ""
        if address and not (self.street or "").strip():
            lines = [ln.strip() for ln in address.replace("\r", "").split("\n") if ln.strip()]
            if lines:
                vals["street"] = lines[0]
            if len(lines) > 2:
                vals["street2"] = lines[1]
            if len(lines) > 1 and not (self.city or "").strip():
                last = lines[-1]
                zip_part, _sep, city_part = last.partition(" ")
                if any(ch.isdigit() for ch in zip_part) and city_part and not (self.zip or "").strip():
                    vals["zip"] = zip_part
                    vals["city"] = city_part.strip()
                else:
                    vals["city"] = last
        if not self.country_id:
            cc = client.normalise_vat(self.vat)[:2]
            if cc == "EL":
                cc = "GR"
            country = self.env["res.country"].search([("code", "=", cc)], limit=1)
            if country:
                vals["country_id"] = country.id
        return vals

    def _ev_warning(self, result):
        """Non-blocking form warning for anything that is not a clean 'valid'."""
        if result["outcome"] == "ok":
            if result["status"] == "valid":
                return None
            if result["status"] == "invalid":
                return _(
                    "EuroValidate: the register reports this VAT number as INVALID (confidence %s)."
                ) % result["confidence"]
            if result["status"] == "unavailable":
                return _(
                    "EuroValidate: the national VAT register is currently unavailable — "
                    "the number is pending, re-validate later."
                )
            if result["status"] == "unverified":
                return _(
                    "EuroValidate: format check only for this country; "
                    "no official register can be queried."
                )
            return _("EuroValidate: %s") % (result.get("detail") or _("could not validate this number."))
        if result["outcome"] == "quota":
            return _("EuroValidate: monthly quota reached — upgrade at %s") % client.UPGRADE_URL
        return _("EuroValidate: %s") % (result.get("detail") or result["outcome"])

    def ev_validate(self, raise_on_quota=True):
        """Validate ``vat`` on each record and store the answer. Returns {partner.id: result}."""
        results = {}
        params = self._ev_params()
        for partner in self:
            if not client.is_plausible(partner.vat):
                continue
            result = self._ev_lookup(partner.vat)
            results[partner.id] = result
            vals = partner._ev_apply(result, params["autofill"])
            partner.with_context(ev_skip_validation=True).write(vals)
            if result["outcome"] == "quota" and raise_on_quota and self._ev_quota_warning_due():
                raise UserError(
                    _(
                        "EuroValidate: your monthly validation quota is used up. "
                        "Upgrade your plan at %s — validations resume immediately."
                    )
                    % client.UPGRADE_URL
                )
            if result["outcome"] == "bad_key":
                _logger.warning("eurovalidate: API key rejected or missing")
        return results

    def action_ev_validate(self):
        """Form button."""
        results = self.ev_validate(raise_on_quota=True)
        warnings = [self.browse(pid)._ev_warning(r) for pid, r in results.items()]
        warnings = [w for w in warnings if w]
        if warnings:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"type": "warning", "sticky": False, "message": "\n".join(warnings)},
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "sticky": False,
                "message": _("VAT number valid — registered name and address stored."),
            },
        }

    # ── onchange / create / write ────────────────────────────────────────
    @api.onchange("vat")
    def _onchange_vat_eurovalidate(self):
        if not client.is_plausible(self.vat) or self.env.context.get("ev_skip_validation"):
            return None
        params = self._ev_params()
        if not params["api_key"]:
            return None  # module installed, key not set yet: stay silent on the form
        result = self._ev_lookup(self.vat)
        vals = self._ev_apply(result, params["autofill"])
        for key, value in vals.items():
            setattr(self, key, value)
        warning = self._ev_warning(result)
        if warning:
            return {"warning": {"title": _("EuroValidate"), "message": warning}}
        return None

    def _ev_check_block(self, results):
        if not self._ev_params()["block_invalid"]:
            return
        for partner in self:
            result = results.get(partner.id)
            if (
                result
                and result["outcome"] == "ok"
                and result["status"] == "invalid"
                and result["confidence"] in ("high", "medium")
            ):
                raise ValidationError(
                    _(
                        "The VAT number of %s is invalid according to the official register. "
                        "Correct it or disable 'Block invalid' in Settings > EuroValidate."
                    )
                    % (partner.display_name or partner.vat)
                )

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        if self.env.context.get("ev_skip_validation") or not self._ev_params()["api_key"]:
            return partners
        to_check = partners.filtered(
            lambda p: client.is_plausible(p.vat) and p.ev_status in (False, "unknown")
        )
        if to_check:
            results = to_check.ev_validate(raise_on_quota=True)
            to_check._ev_check_block(results)
        return partners

    def write(self, vals):
        res = super().write(vals)
        if (
            "vat" in vals
            and not self.env.context.get("ev_skip_validation")
            and self._ev_params()["api_key"]
        ):
            to_check = self.filtered(lambda p: client.is_plausible(p.vat))
            if to_check:
                results = to_check.ev_validate(raise_on_quota=True)
                to_check._ev_check_block(results)
        return res

    # ── cron ─────────────────────────────────────────────────────────────
    @api.model
    def _ev_cron_revalidate(self, batch=200, max_age_days=30):
        """Weekly: re-check partners whose last verification is older than ``max_age_days``."""
        if not self._ev_params()["api_key"]:
            return
        cutoff = fields.Datetime.now() - timedelta(days=max_age_days)
        partners = self.search(
            [
                "&",
                ("vat", "!=", False),
                "|",
                ("ev_last_verified", "=", False),
                ("ev_last_verified", "<", cutoff),
            ],
            limit=batch,
            order="ev_last_verified asc",
        )
        for partner in partners:
            result = partner.ev_validate(raise_on_quota=False).get(partner.id)
            if result and result["outcome"] == "quota":
                _logger.info("eurovalidate cron: quota reached, stopping")
                break
            self.env.cr.commit()  # keep progress if a later call hangs
