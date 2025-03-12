from odoo import http
from odoo.http import request

class JobWebsite(http.Controller):

    @http.route(['/jobs/<int:job_id>'], type='http', auth="public", website=True)
    def job_details(self, job_id, **kw):
        job = request.env['hr.job'].sudo().browse(job_id)
        return request.render('recruitement_ai.job_template', {
            'job': job
        })
