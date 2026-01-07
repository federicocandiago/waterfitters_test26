from odoo import fields, models

class SaleOrderCancelWizard(models.TransientModel):
    _name = 'sale.order.cancel.wizard'
    _description = 'Wizard per annullamento Sale Order'

    wizard_motivazione = fields.Char(string='Motivazione')

    def action_confirm(self):
        sale_order = self.env['sale.order'].browse(self.env.context.get('active_id'))
        if sale_order:
            sale_order.action_cancel() 
            sale_order.write({'client_order_ref': self.wizard_motivazione})