# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models

class StockPickingBatch(models.Model):

    _inherit = 'stock.picking.batch'
    product_ids = fields.Many2many(
        'product.product',
        compute='_compute_product_ids',
        search='_search_product_ids',
        store=False,
        readonly=True
    )

    def _compute_product_ids(self):
        for batch in self:
            products = batch.picking_ids.mapped('move_line_ids.product_id')
            batch.product_ids = products

    def _search_product_ids(self, operator, value):

        products = self.env['product.product'].search(
            ['|',('default_code', operator, value),('name', operator, value)]
        )
        if not products: return [('id', '=', False)]

        batches = self.env['stock.picking.batch'].search(
            [('picking_ids.move_line_ids.product_id', 'in', products.ids)]
        )
        return [('id', 'in', batches.ids)]
