# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import _, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    waterfitters_client_id = fields.Char(
        'Waterfitters Client ID',
        config_parameter='waterfitters_client_id'
    )
    waterfitters_client_secret = fields.Char(
        config_parameter='waterfitters_client_secret'
    )
    waterfitters_endpoints_url = fields.Char(
        config_parameter='waterfitters_endpoints_url'
    )
    waterfitters_customers_batch_limit = fields.Integer(
        config_parameter='waterfitters_customers_batch_limit',
        help=_('If the number is set to zero, all records will be sent in one cycle whatever the dimension of the sync.')
    )
