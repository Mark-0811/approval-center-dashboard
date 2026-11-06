{
    'name': 'Approval Center Dashboard',
    'summary': 'Configurable approval inbox for Odoo',
    'version': '20.0.1.0.0',
    'category': 'Productivity/Approvals',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'web'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/rules.xml',
        'views/dashboard_views.xml',
        'views/config_views.xml',
        'views/menu_views.xml',
        'data/cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'approval_center_dashboard/static/src/dashboard/dashboard.js',
            'approval_center_dashboard/static/src/dashboard/dashboard.xml',
            'approval_center_dashboard/static/src/dashboard/dashboard.scss',
        ],
    },
    'application': True,
    'installable': True,
}
