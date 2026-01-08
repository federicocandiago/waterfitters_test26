# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Mondeo - Waterfitters Interface",
    "author": "Digiduu",
    "website": "http://www.digiduu.it",
    'version': '1.0.1.0.0',
    'category': 'Sale',
    'depends': ['base', 'base_setup', 'sale', 'stock'],
    "license": "LGPL-3",
    "data": [
        "data/industry_group.xml",
        "data/wf_paymentterm.xml",
        "data/wf_shippingmethod.xml",
        "data/ir_cron.xml",
        "data/ir_sequence.xml",
        "security/ir.model.access.csv",
        "views/industry_group_views.xml",
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
        "views/wf_paymentterm_views.xml",
        "views/wf_shippingmethod_views.xml",
    ]
}
