# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import _, api, models, fields

import datetime
import logging

_logger = logging.getLogger(__name__)

class SaleOrderLine(models.Model):
    _name = 'sale.order.line'
    _inherit = ["sale.order.line", "waterfitters.shared"]

    wf_order_line_item_id = fields.Integer()
    wf_order_line_to_be_synched = fields.Boolean(
        compute='_check_wf_qty_sync_needed',
        store=True
    )

    @api.depends('qty_delivered')
    def _check_wf_qty_sync_needed(self):
        for line in self:
            order_id = line.order_id

            # Only set to be synched if they have a wf_order_line_item_id != 0
            if line.wf_order_line_item_id and order_id.state not in ['cancel', 'draft'] and line.qty_delivered:
                line.wf_order_line_to_be_synched = True

    def sync_waterfitters_shipping_state(self):
        token = self._wf_get_token()
        if not token:
            _logger.error(_('Unable to obtain a token - Cannot proceed'))
            return None

        # Exclude lines without wf_order_line_item_id
        for line in self.filtered(lambda l: l.wf_order_line_item_id):

            status_id = 'shipped'
            if line.qty_delivered == 0:  status_id = 'not_shipped'
            elif line.qty_delivered < line.product_uom_qty: status_id = 'partially_shipped'

            wf_line_id = str(line.wf_order_line_item_id)

            # Get the furthest DDT date for the given line, otherwise now.
            moves = self.env['stock.move'].search([('sale_line_id', '=', line.id)])
            pickings = moves.mapped('picking_id')
            picking_batches = pickings.mapped('batch_id')
            confirmed_dates = picking_batches.mapped('x_studio_data_partenza_spedizione')

            valid_dates = [d for d in confirmed_dates if d]
            max_date = max(valid_dates) if valid_dates else datetime.datetime.now()
            ship_by = max_date.strftime('%Y-%m-%d')

            payload = {
                "data": {
                    "type": "orderlineitems",
                    "id": wf_line_id,
                    "attributes": {"shipped_qty": line.qty_delivered, 'shipBy': ship_by},
                    "relationships": {
                        "shipping_status": {"data": {"type": "wforderlineitemsshippingstatuses", "id": status_id}}
                    }
                }
            }

            # payload['data']['attributes']['shipBy'] = datetime.datetime.now().strftime('%Y-%m-%d')

            item_json = self._wf_payload_request(f'orderlineitems/{wf_line_id}', payload, token, 'PATCH')

            if item_json.get('code'):
                _logger.info(_(f"Line {line.id} processed: {item_json['code']}"))
                line.wf_order_line_to_be_synched = False
            else:
                _logger.error(_(f'Unable to update the delivered quantity for line {line.id} - Passing to next..'))
                pass
