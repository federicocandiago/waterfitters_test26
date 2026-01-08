# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models

class StockPicking(models.Model):

    _inherit = 'stock.picking'

    vendor_codes = fields.Char(
        compute='_compute_vendor_codes',
        search='_search_vendor_codes',
        store=True,
        readonly=True
    )

    # TODO: Odoo Studio field - to be edited for migration
    vendor_code_relation = 'product_id.product_tmpl_id.seller_ids.x_studio_related_field_uCGBh'

    def _compute_vendor_codes(self):
        all_sellers = self.mapped('move_ids.product_id.product_tmpl_id.seller_ids')
        seller_vals = {s.id: s.x_studio_related_field_uCGBh for s in all_sellers}

        picking_seller_map = {
            picking.id: picking.move_ids.mapped('product_id.product_tmpl_id.seller_ids').ids
            for picking in self
        }

        for picking in self:
            codes = [seller_vals[s_id] for s_id in picking_seller_map[picking.id] if seller_vals[s_id]]
            picking.vendor_codes = ', '.join(codes)

    def _search_vendor_codes(self, operator, value):
        return [(f'move_ids.{self.vendor_code_relation}', operator, value)]
