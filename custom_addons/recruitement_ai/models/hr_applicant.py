from odoo import models, fields

class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    score = fields.Float(string="Score")
