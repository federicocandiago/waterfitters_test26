# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import _, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    iubenda_mondeo_web_apikey = fields.Char(
        string="Mondeo website api key",
        config_parameter='iubenda_mondeo_web_apikey'
    )

    iubenda_wf_portal_apikey = fields.Char(
        string="Waterfitters Portal api key",
        config_parameter='iubenda_wf_portal_apikey'
    )
