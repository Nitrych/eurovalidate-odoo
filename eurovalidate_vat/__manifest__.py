# Copyright 2026 EuroValidate (https://eurovalidate.com)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
{
    "name": "EuroValidate VAT",
    "summary": "VAT validation with name/address autofill that keeps working when VIES is down",
    "description": """
Validate EU and UK VAT numbers on partners through the EuroValidate API and
pre-fill the registered company name and address.

Unlike the built-in ``base_vat`` check, this module:

* fills in name, street, zip, city and country from the official register;
* keeps answering during VIES outages (24 h cache, last known answer with a
  confidence flag) instead of silently falling back to a checksum;
* stores the validation evidence (request id, source, timestamp) on the partner;
* covers EU + UK (paid plans), Norway, Switzerland and Australia.

A free API key (100 validations/month, no card) is enough to try it:
https://eurovalidate.com/v1/auth/signup?utm_source=odoo&utm_medium=module&utm_campaign=manifest
""",
    "version": "17.0.1.0.0",
    "category": "Accounting",
    "license": "LGPL-3",
    "author": "EuroValidate",
    "support": "support@eurovalidate.com",
    "website": "https://eurovalidate.com/odoo-vat-validation",
    "depends": ["base", "base_vat", "base_setup"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
        "data/ir_cron.xml",
    ],
    "images": ["static/description/banner.gif", "static/description/banner.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
