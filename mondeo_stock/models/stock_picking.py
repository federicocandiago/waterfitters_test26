# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models
from datetime import date, timedelta
from collections import Counter

class StockPicking(models.Model):

    _inherit = 'stock.picking'

    def _get_stock_barcode_data(self):
        data = super()._get_stock_barcode_data()

        if data and 'records' in data and 'stock.move.line' in data['records']:
            records = data['records']['stock.move.line']
            product_counts = Counter([rec['product_id'] for rec in records])

            for rec in data['records']['stock.move.line']:
                if product_counts[rec['product_id']] > 1:
                    rec['display_name'] = f"{rec['display_name']} (x{product_counts[rec['product_id']]})"

        return data