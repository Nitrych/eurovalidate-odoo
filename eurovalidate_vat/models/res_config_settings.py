# Copyright 2026 EuroValidate (https://eurovalidate.com)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from odoo import fields, models

from .eurovalidate_client import DEFAULT_BASE_URL

PARAM_API_KEY = "eurovalidate.api_key"
PARAM_AUTOFILL = "eurovalidate.autofill"
PARAM_BLOCK_INVALID = "eurovalidate.block_invalid"
PARAM_BASE_URL = "eurovalidate.base_url"
PARAM_QUOTA_WARNED_AT = "eurovalidate.quota_warned_at"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # The key is stored in ir.config_parameter: readable by any user with
    # "Administration / Settings" rights. Use a dedicated key for Odoo and
    # rotate it from the EuroValidate dashboard if needed.
    eurovalidate_api_key = fields.Char(
        string="EuroValidate API key",
        config_parameter=PARAM_API_KEY,
        help="Free key (100 validations/month, no card) at https://eurovalidate.com",
    )
    eurovalidate_autofill = fields.Boolean(
        string="Fill in name and address from the register",
        config_parameter=PARAM_AUTOFILL,
        default=True,
        help="Only empty fields are filled; existing values are never overwritten.",
    )
    eurovalidate_block_invalid = fields.Boolean(
        string="Block saving partners whose VAT number is invalid",
        config_parameter=PARAM_BLOCK_INVALID,
        default=False,
        help="Raises an error on save when the register says the number is invalid "
        "(high/medium confidence). Outages never block a save.",
    )
    eurovalidate_base_url = fields.Char(
        string="EuroValidate base URL",
        config_parameter=PARAM_BASE_URL,
        default=DEFAULT_BASE_URL,
    )
