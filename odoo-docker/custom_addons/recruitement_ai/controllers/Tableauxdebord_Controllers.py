from odoo import http
from odoo.http import request

class RecruitmentController(http.Controller):

    @http.route('/odoo/recruitment/tableau', type='http', auth='public', website='true')
    def tableau_dashboard(self, **kw):



        # Récupérer les données pour le tableau de bord
        candidates = request.env['recruitment.candidate'].search([])
        avg_score = sum(candidates.mapped('score')) / len(candidates) if candidates else 0

        # Correction du nom du module dans le render
        return request.render('recruitement_ai.tableau', {  # Assurez-vous que le nom du module est correct
            'candidates': candidates,
            'avg_score': avg_score,
            'total_candidates': len(candidates)
        })