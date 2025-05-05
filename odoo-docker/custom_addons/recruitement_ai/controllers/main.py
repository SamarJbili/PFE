from odoo import http
from odoo.http import request
from odoo.addons.website_hr_recruitment.controllers.main import WebsiteHrRecruitment

class WebsiteHrRecruitmentExtended(WebsiteHrRecruitment):

    @http.route(['/jobs/apply/<model("hr.job"):job>'], type='http', auth="public", website=True)
    def jobs_apply(self, job, **kwargs):
        if not request.session.uid:
            # L'utilisateur n'est pas connecté, redirection vers la page de connexion
            return request.redirect('/web/login?redirect=/jobs/apply/%s' % job.id)

        # Si l'utilisateur est connecté, utiliser la méthode originale
        return super().jobs_apply(job, **kwargs)
