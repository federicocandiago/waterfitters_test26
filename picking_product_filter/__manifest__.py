# Copyright 2025-TODAY Digiduu S.r.L. (www.digiduu.it)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name" : "ORIENS - Product Filter Picking",
    "version": "16.0.1.0.0",
    "category" : "Picking",
    "author": "Digiduu",
    "website": "http://www.digiduu.it",
    "depends" : ['stock', 'stock_picking_batch'],
    "data": [
        'views/stock_picking_batch_search_view.xml',
        'views/stock_picking_search_view.xml'
    ],
    "license": "LGPL-3",
    "auto_install": False,
    "installable": True,
}
