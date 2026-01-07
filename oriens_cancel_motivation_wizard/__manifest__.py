{
    'name': 'Oriens - Cancel Motivation Wizard',
    'version': '0.1',
    'summary': 'Wizard for the cancellation motivation',
    'author': 'Federico Candiago - Oriens Consulting',
    'depends': ['sale'],
    'license': 'OPL-1',
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_cancel_wizard_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
