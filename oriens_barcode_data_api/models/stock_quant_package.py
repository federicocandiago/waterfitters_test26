import json
from collections import defaultdict
from datetime import date
from markupsafe import Markup

from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import UserError
from odoo.tools.sql import column_exists, create_column

import logging
_logger = logging.getLogger(__name__)

class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    def _oriens_return_weight(self, product_name = False, product_uom_qty = 0.0):
        self.ensure_one()
        weight = 0.0

        self.weight = weight
        if self.quant_ids:
            for quant in self.quant_ids:
                weight += quant.quantity * quant.product_id.weight
                _logger.info(f"Quant ID {quant.id}: quantity {quant.quantity}, product weight: {quant.product_id.weight}")
                
        elif product_name and product_uom_qty:
            try:
                int_qty = int(product_uom_qty)
                product_id = self.env['product.product'].with_context(lang='it_IT').sudo().search([('name', '=', product_name)], order='id desc', limit = 1)
                if product_id and int_qty: weight = product_id.weight * int_qty
            except: 
                _logger(f'Exception in calculating the total weight. product id: {product_id.id}, product uom qty: {product_uom_qty}')

        return weight
