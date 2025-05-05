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
        'hr_recruitment',
                'website',
                'website_hr_recruitment'

    ],
    'data': [
        'views/score.xml',
        'views/candidate_dashboard.xml',
        'views/candidate_edit.xml',
        'security/hr_applicant_candidate_rules.xml',
        'views/hr_applicant_views.xml',
        'security/ir.model.access.csv',
        'views/onglecritere.xml'

    ],
'controllers': [
    'controllers/Tableauxdebord_Controllers.py',
    'controllers/RecruitmentAnalysisController.py',

],
'assets': {
        'web.assets_backend': [
            'recruitement_ai/static/src/js/kanban_controller.js',
            'recruitement_ai/static/src/xml/kanban_controller.xml'
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'sequence': 1  # Corrected: integer, not string
}

