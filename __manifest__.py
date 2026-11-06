# -*- coding: utf-8 -*-

{
    'name': 'Dex Approval Center',
    'summary': 'Central workspace for existing approval functions',
    'description': '''
Central approval dashboard

Organizes approval functions from installed Odoo modules in one dashboard while
leaving each source module responsible for its own approval and rejection logic.
''',
    'version': '13.0.3.0.0',
    'author': 'John Raymark Llavanes',
    'license': 'LGPL-3',
    'category': 'Operations',
    'depends': [
        'base',
        'dex_mail',
        'mail',
        'web',
    ],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/rules.xml',
        'views/assets.xml',
        'data/sequence.xml',
        'views/category_views.xml',
        'views/approval_type_views.xml',
        'views/approval_item_views.xml',
        'views/dashboard_views.xml',
        'data/dashboard_actions.xml',
        'views/menu_views.xml',
        'data/cron.xml',
    ],
    'qweb': [
        'static/src/xml/approval_center_dashboard.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'application': True,
    'installable': True,
}
