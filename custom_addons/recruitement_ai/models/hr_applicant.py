from odoo import models, fields

class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    score = fields.Integer(string="Score", help="Score du candidat basé sur l'analyse AI")
