from odoo import models

class HrCV(models.Model):
    _inherit = 'hr.applicant'

    def get_cvs_by_job(self, job_id):
        applicants = self.search([('job_id', '=', job_id)])
        cvs = []
        for applicant in applicants:
            attachments = self.env['ir.attachment'].search([
                ('res_model', '=', 'hr.applicant'),
                ('res_id', '=', applicant.id)
            ])
            for attachment in attachments:
                cvs.append({
                    'name': attachment.name,
                    'mimetype': attachment.mimetype,
                    'datas': attachment.datas,  # Contenu binaire encodé en base64
                    'applicant_name': applicant.partner_name
                })
        return cvs
