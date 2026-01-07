# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import _, models, fields, api

class WfPaymentterm(models.Model):
    _name = "wf.paymentterm"

    name = fields.Char(required=True)
    code = fields.Char()
    waterfitters_id = fields.Integer('Waterfitters ID')
