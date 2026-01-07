{
    'name': 'Oriens - External forms Interface',
    'version': '0.1',
    'summary': 'Plugin for the Mondeo Odoo - External forms integration.',
    'author': 'Federico Candiago - Oriens Consulting',
    'category': 'Sale',
    'depends': ['base', 'sale', 'stock', 'helpdesk'],
    'data': [
        'views/crm_views.xml',
        'views/helpdesk_views.xml'
    ],
    'license': 'OPL-1',
    'installable': True,
    'application': False,
    'auto_install': False,
}
