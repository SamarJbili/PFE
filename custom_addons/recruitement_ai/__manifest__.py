{
    'name': 'AI Talent Selector',
    'version': '1.0',
    'description': 'This module enhances the recruitment module with AI-based CV management and preselection',
    'summary': 'AI-powered recruitment enhancement for Odoo',
    'author': 'Samar',
    'website': 'https://erptogo.net',
    'license': 'LGPL-3',
    'category': 'Human Resources',
    'depends': ['base',
        'hr_recruitment'
    ],
    'data': [
        'views/poste_view.xml',
        'views/HrJob.xml',
        'views/job_template.xml',
        'views/tableau.xml',
        'views/tableau_template.xml',
        'security/ir.model.access.csv'


    ],
'controllers': [
    'controllers/Tableauxdebord_Controllers.py',
],
'assets': {
        'web.assets_backend': [
            'recruitement_ai/static/src/js/kanban_controller.js',
            'recruitement_ai/static/src/xml/kanban_controller.xml'
        ],
    },
    'auto_install': False,
    'application': True,
    'sequence': 1  # Corrected: integer, not string
}
