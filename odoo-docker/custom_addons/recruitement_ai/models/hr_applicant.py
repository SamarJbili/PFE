from odoo import models, fields

class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    score = fields.Float("Score")

    partner_id = fields.Many2one(
        'res.partner',
        string='Candidat',
        required=True,
        default=lambda self: self.env.user.partner_id
    )

    languages = fields.Many2many('res.language.custom', string="Langues parlées")

# Champ pour stocker le CV sous forme binaire
    cv_file = fields.Binary(string='Curriculum Vitae', help="Le fichier CV du candidat")

    # Nom du fichier CV
    cv_filename = fields.Char(string="Nom du fichier CV", help="Nom du fichier CV téléchargé")

    # Pièces jointes associées à la candidature (optionnel)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'hr_applicant_attachment_rel',
        'applicant_id',
        'attachment_id',
        string="Pièces jointes"
    )

    def update_cv_file(self, file_data, filename):
        """Met à jour le fichier CV et son nom."""
        self.cv_file = file_data
        self.cv_filename = filename