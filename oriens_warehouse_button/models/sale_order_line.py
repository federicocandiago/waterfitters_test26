from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_warehouse_available = fields.Boolean(compute='_compute_is_warehouse_available', store=True)

    @api.depends('product_id')
    def _compute_is_warehouse_available(self):
        for line in self:
            if not line.product_id:
                line.is_warehouse_available = False
            else:
                warehouse_count = self.env['x_warehouse'].search_count([
                    ('x_studio_many2one_field_laEV5', '=', line.product_id.id), 
                    ('x_studio_spedibile_01', '>=', line.product_uom_qty)
                ])
                line.is_warehouse_available = bool(warehouse_count)

    # dynamic_warehouse_button = fields.Html(compute='_compute_dynamic_button', sanitize=False)

    # @api.depends('product_id')
    # def _compute_dynamic_button(self):
    #     for line in self:
    #         button_html = ""
    #         if line.product_id:
    #             warehouse_product = self.env['x_warehouse'].search(
    #                 [('x_studio_many2one_field_laEV5', '=', line.product_id.id)],
    #                 limit=1
    #             )
    #             if warehouse_product:
    #                 wh_available = warehouse_product.x_studio_spedibile_01 >= line.product_uom_qty
    #                 btn_class = 'btn btn-primary' if wh_available else 'btn btn-danger'
    #                 btn_string = 'Wh' if wh_available else 'Wh (non disponibile)'

    #                 button_html = f"""
    #                     <button
    #                         type="action"
    #                         action="913"
    #                         class="{btn_class}"
    #                     ">
    #                         <i class="fa fa-cubes"></i> {btn_string}
    #                     </button>
    #                 """

    #         line.dynamic_warehouse_button = button_html

    # def warehouse_button_action(self):
    #     sale_order_line = self
    #     if not sale_order_line or not sale_order_line.product_id:
    #         raise UserError('Attenzione: non è stato possibile rilevare il prodotto a sistema.')

    #     action = {
    #         'type': 'ir.actions.act_window',
    #         'name': f'Warehouse: {sale_order_line.product_id.display_name}',
    #         'view_mode': 'tree,form',
    #         'res_model': 'x_warehouse',
    #         'domain': [('x_studio_many2one_field_laEV5', '=', sale_order_line.product_id.id)],
    #         'target': 'new',
    #     }
    #     return action