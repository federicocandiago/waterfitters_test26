# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Mondeo Accounting",
    "author": "Digiduu",
    "website": "http://www.digiduu.it",
    "license": "LGPL-3",
    "category": "Acccounting",
    "version": "16.0.2.0.1",
    "depends": ["account_asset", 'base_setup'],
    "data": [
        'security/ir.model.access.csv',
        "views/account_asset_views.xml",
        'views/assets_report_views.xml',
        'views/assets_report_wizard_views.xml',
    ],
}
