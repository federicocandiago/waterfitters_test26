# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import _, models, fields, api

class WfShippingmethod(models.Model):
    _name = "wf.shippingmethod"

    name = fields.Char(required=True)
    method = fields.Char(required=True)
    incoterm = fields.Char(required=True)
