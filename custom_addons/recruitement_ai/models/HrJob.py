from odoo import models, fields

class HRJob(models.Model):
    _inherit = 'hr.job'

    description_poste = fields.Text(string="Description du poste")

    competences = fields.Selection([
        ('python', 'Développement Python'),
        ('gestion_projet', 'Gestion de projet'),
        ('communication', 'Communication'),
        # Ajoutez d'autres compétences ici
    ], string="Compétence", required=True)

    experience_min = fields.Integer(string="Années d'expérience minimale", required=True)

    experiences_particulieres = fields.Text(string="Expériences particulières")

    niveau_formation = fields.Selection([
        ('bac_plus_3', 'Bac +3'),
        ('master', 'Master'),
        ('doctorat', 'Doctorat'),
        ('autre', 'Autre')
    ], string="Niveau de formation", required=True)

    diplomes_specifiques = fields.Text(string="Diplômes spécifiques")  # Correction ici !
