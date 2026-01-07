# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models
from datetime import date, timedelta

class StockPickingBatch(models.Model):

    _inherit = 'stock.picking.batch'
    kanban_color = fields.Char(
        compute='_compute_kanban_color',
        store=False,
        readonly=True
    )

    def _compute_kanban_color(self):

        today = fields.Date.context_today(self)
        for batch in self:
            kanban_color = ''
            scheduled_date = fields.Date.to_date(batch.scheduled_date)  + timedelta(days=1) 

            # Card color: red for the past, yellow for today, green for the future
            if scheduled_date:
                if scheduled_date < today: kanban_color = 'bg_warning'
                elif scheduled_date == today: kanban_color = 'bg_info'
            batch.kanban_color = kanban_color
