# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _prepare_move_for_asset_depreciation(self, vals):
        if vals['asset_id'].normalize_dates_to_jan_first:
            vals['depreciation_beginning_date'] = vals['depreciation_beginning_date'].replace(day=1, month=1)
        return super()._prepare_move_for_asset_depreciation(vals)
