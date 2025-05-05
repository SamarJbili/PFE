from odoo import models, fields

class CVData(models.Model):
    _name = 'cv.data'
    _description = 'Données extraites des CV'

    job_id = fields.Many2one('hr.job', string='Poste concerné')
    candidate_name = fields.Char(string="Nom")
    email = fields.Char()
    phone = fields.Char()
    education = fields.Char()
    experience_years = fields.Integer()
    location = fields.Char()
    skills = fields.Text()
    languages = fields.Text()
    score = fields.Float(string="Score d'évaluation")
