
from odoo import models, fields

class RecruitmentCandidate(models.Model):
    _name = 'recruitment.candidate'
    _description = 'Candidat de recrutement'

    name = fields.Char(string="Nom du Candidat", required=True)
    score = fields.Float(string="Score", required=True)