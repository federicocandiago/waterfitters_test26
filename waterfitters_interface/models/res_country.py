# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import models, fields

class ResCountry(models.Model):
    _inherit = "res.country"

    in_eu = fields.Boolean(
        string="In European Union?",
        compute="_compute_in_eu",
        store=True
    )

    def _compute_in_eu(self):
        eu_codes = [
            "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU",
            "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"
        ]

        for country in self: country.in_eu = country.code in eu_codes
