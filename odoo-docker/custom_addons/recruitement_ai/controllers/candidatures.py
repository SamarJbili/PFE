from odoo import http
from odoo.http import request
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
import base64
import logging

_logger = logging.getLogger(__name__)

class CandidateDashboardController(http.Controller):

    @http.route('/candidat/candidatures', type='http', auth='user', website=True)
    def candidatures(self):
        # Récupérer le candidat connecté
        candidate = request.env.user.partner_id
        # Filtrer les candidatures du candidat
        applications = request.env['hr.applicant'].search([('partner_id', '=', candidate.id)])
        return request.render('recruitement_ai.candidate_dashboard', {
            'applications': applications,
        })
    from odoo import http
    from odoo.http import request
    from odoo.exceptions import AccessError
    import base64

    class RecruitmentController(http.Controller):

        @http.route('/my/applications/edit/<int:app_id>', type='http', auth='user', website=True, csrf=False)
        def edit_application(self, app_id, **post):
            application = request.env['hr.applicant'].sudo().browse(app_id)

            if application.partner_id != request.env.user.partner_id:
                raise AccessError("Accès non autorisé.")

            if request.httprequest.method == 'POST':
                # Données de base
                vals = {
                    'partner_name': post.get('partner_name'),
                    'email_from': post.get('email_from'),
                    'partner_phone': post.get('partner_phone'),
                }

                # Traitement du fichier CV
                cv_file = request.httprequest.files.get('cv_file')
                if cv_file and cv_file.filename:
                    file_data = cv_file.read()
                    if file_data:
                        vals.update({
                            'cv_file': base64.b64encode(file_data),
                            'cv_filename': cv_file.filename,
                        })

                # Mise à jour de la candidature
                application.sudo().write(vals)

                return request.redirect('/candidat/candidatures')

            # Si GET, retourne la page de modification

            return request.render('recruitement_ai.edit_application_form', {
                'application': application,
            })


    @http.route('/my/applications/delete/<int:app_id>', type='http', auth='user', website=True)
    def delete_application(self, app_id, **post):
        application = request.env['hr.applicant'].sudo().browse(app_id)
        if application.partner_id != request.env.user.partner_id:
            raise AccessError("Accès non autorisé.")
        application.unlink()
        return request.redirect('/candidat/candidatures')