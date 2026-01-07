# -*- coding: utf-8 -*-

from odoo import api, fields, models

class HelpdeskTicket(models.Model):
    _inherit = 'crm.lead'

    contact_method = fields.Selection([
        ('mail', 'E-mail'),
        ('phone', 'Telefono'),
        ('both', 'Entrambi'),
    ], string = 'Metodo di contatto preferito')

    contact_cause = fields.Selection([
        ('11', '01_Interessato ad una partnership'), 
        ('12', '02_Maggiori informazioni di prodotto'), 
        ('13', '03_Assistenza ed aiuto'), 
        ('14', '04_Apertura di un reclamo'), 
        ('15', '05_Maggiori informazioni sulla gestione dei dati forniti'), 
        ('16', '06_Richiesta affidamento operativo'), 
        ('17', '07_Suggerimenti per migliorare'), 
        ('18', '08_Richiesta ed informazioni per prodotto non disponibile'), 
        ('19', '09_ Altra tipologia di richiesta'), 
    ], string = 'Motivo del contatto')

    order_string = fields.Char(string = "Ordine Waterfitters di riferimento")
