# -*- coding: utf-8 -*-

from odoo import api, fields, models

class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    contact_method = fields.Selection([
        ('mail', 'E-mail'),
        ('phone', 'Telefono'),
        ('both', 'Entrambi'),
    ], string = 'Metodo di contatto preferito')

    order_string = fields.Char(string = "Ordine Waterfitters di riferimento")
