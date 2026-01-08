from odoo import fields, models, api
from odoo.exceptions import UserError
import datetime
import logging

_logger = logging.getLogger(__name__)

class StockPickingBatch(models.Model):    
    _inherit = 'stock.picking.batch'

    total_picking_time = fields.Float(string = "Tempo di Picking totale")
    current_picking_start = fields.Datetime(string = "Inizio ultimo picking")
    is_in_progress = fields.Char(string = "In corso?", required=False, store=True, readonly=True)

    def oriens_stop_picking(self):
        self.ensure_one()
        
        if not self.current_picking_start: _logger.warning(f'Attezione: attività non in corso per il l\'operazione {self.display_name} ({self.id})')
        else: 
            current_picking_end = datetime.datetime.now()
            current_picking_difference = current_picking_end - self.current_picking_start
            self['total_picking_time'] = self.total_picking_time + float(current_picking_difference.seconds) / 60
            self['current_picking_start'] = False
            self['is_in_progress'] = ''

    def oriens_start_picking(self):
        self.ensure_one()
        
        if self.current_picking_start: _logger.warning(f'Attezione: attività già in corso per il l\'operazione {self.display_name} ({self.id})')
        else: 
            self['current_picking_start'] = datetime.datetime.now()
            self['is_in_progress'] = 'Preso in carico'
