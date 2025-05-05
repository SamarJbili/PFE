from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrCompetence(models.Model):
    _name = 'hr.competence'
    _description = 'Compétence'

    name = fields.Char(string="Nom", required=True, translate=True)
    is_required = fields.Boolean(string="Obligatoire", default=False)
    job_id = fields.Many2one('hr.job', string="Poste")
    importance_level = fields.Selection([
        ('1', '★'),
        ('2', '★★'),
        ('3', '★★★'),
        ('4', '★★★★'),
        ('5', '★★★★★'),
    ], string="Niveau d'importance")


# 2. Modèle pour les langues personnalisées
class ResLanguageCustom(models.Model):
    _name = 'res.language.custom'
    _description = 'Langue personnalisée'

    name = fields.Char(string="Langue", required=True, translate=True)
    job_id = fields.Many2one('hr.job', string="Poste")
    is_required = fields.Boolean(string="Obligatoire", default=False)
    importance_level = fields.Selection([
        ('1', '★'),
        ('2', '★★'),
        ('3', '★★★'),
        ('4', '★★★★'),
        ('5', '★★★★★'),
    ], string="Niveau d'importance")


# 4. Extension du modèle Job
class JobCriteria(models.Model):
    _inherit = 'hr.job'

    date_debut_poste = fields.Datetime(
        string='Date de début de poste',
        required=True,
        default = fields.Datetime.now
    )
    date_fin_poste = fields.Datetime(
        string='Date de fin de poste',
        required=True,
        default=fields.Datetime.now
    )
    is_published = fields.Boolean(
        string="Publié",
        default=True
    )

    @api.constrains('date_debut_poste', 'date_fin_poste')
    def _check_dates(self):
        for record in self:
            if not record.date_debut_poste:
                raise ValidationError("La date de début de poste est obligatoire.")
            if not record.date_fin_poste:
                raise ValidationError("La date de fin de poste est obligatoire.")
            if record.date_fin_poste < record.date_debut_poste:
                raise ValidationError("La date de fin de poste doit être après la date de début de poste.")

    @api.model
    def create(self, vals):
        record = super(JobCriteria, self).create(vals)
        record._check_date_fin_today()
        return record

    def write(self, vals):
        res = super(JobCriteria, self).write(vals)
        self._check_date_fin_today()
        return res

    def _check_date_fin_today(self):
        today = fields.Date.today()
        for record in self:
            if record.date_fin_poste and record.date_fin_poste.date() <= today:
                # Si la date de fin est passée, on désactive la publication
                if record.is_published:
                    record.is_published = False
            elif record.date_fin_poste and record.date_fin_poste.date() > today:
                # Si la nouvelle date de fin est dans le futur, on réactive la publication
                if not record.is_published:
                    record.is_published = True

    experience_years = fields.Integer(string="Années d'expérience")
    education = fields.Selection([
        ('bac_plus_3', 'Bac +3'),
        ('master', 'Master'),
        ('ingenierie', 'Ingénierie'),
        ('doctorat', 'Doctorat')
    ], string="Niveau de formation requis")
    location = fields.Char(string="Lieu")
    skills = fields.Text(string="Compétences (texte libre)")
    # Relations
    language_ids = fields.Many2many('res.language.custom', string="Languages")
    competences = fields.Many2many('hr.competence', string="Compétences attendues")

    # Importance Levels for each field
    experience_years_importance = fields.Selection([
        ('1', '★'),
        ('2', '★★'),
        ('3', '★★★'),
        ('4', '★★★★'),
        ('5', '★★★★★'),
    ], string="Importance des années d'expérience")

    education_importance = fields.Selection([
        ('1', '★'),
        ('2', '★★'),
        ('3', '★★★'),
        ('4', '★★★★'),
        ('5', '★★★★★'),
    ], string="Importance du niveau de formation")

    location_importance = fields.Selection([
        ('1', '★'),
        ('2', '★★'),
        ('3', '★★★'),
        ('4', '★★★★'),
        ('5', '★★★★★'),
    ], string="Importance du lieu")

    skills_importance = fields.Selection([
        ('1', '★'),
        ('2', '★★'),
        ('3', '★★★'),
        ('4', '★★★★'),
        ('5', '★★★★★'),
    ], string="Importance des compétences")

    languages_importance = fields.Selection([
        ('1', '★'),
        ('2', '★★'),
        ('3', '★★★'),
        ('4', '★★★★'),
        ('5', '★★★★★'),
    ], string="Importance des langues")

    competences_importance = fields.Selection([
        ('1', '★'),
        ('2', '★★'),
        ('3', '★★★'),
        ('4', '★★★★'),
        ('5', '★★★★★'),
    ], string="Importance des compétences attendues")

    # Nouveaux champs booléens pour les checkboxes
    is_experience_years_required = fields.Boolean(string="Obligatoire Années d'expérience")
    is_education_required = fields.Boolean(string="Obligatoire Niveau de formation requis")
    is_location_required = fields.Boolean(string="Obligatoire Lieu")
    is_skills_required = fields.Boolean(string="Obligatoire Compétences")

    @api.constrains('experience_years', 'education', 'location', 'skills',
                    'is_experience_years_required', 'is_education_required',
                    'is_location_required', 'is_skills_required')
    def _check_required_fields(self):
        for record in self:
            if record.is_experience_years_required and not record.experience_years:
                raise ValidationError("Le champ 'Années d'expérience' est obligatoire.")
            if record.is_education_required and not record.education:
                raise ValidationError("Le champ 'Niveau de formation requis' est obligatoire.")
            if record.is_location_required and not record.location:
                raise ValidationError("Le champ 'Lieu' est obligatoire.")
            if record.is_skills_required and not record.skills:
                raise ValidationError("Le champ 'Compétences' est obligatoire.")

    @api.constrains('language_ids')
    def _check_required_languages(self):
        for record in self:
            required_languages = record.language_ids.filtered(lambda l: l.is_required)
            if not required_languages.ids:
                return  # Pas de langues obligatoires spécifiées pour ce poste

            missing = [lang.name for lang in required_languages if lang not in record.language_ids]
            if missing:
                raise ValidationError(
                    f"Les langues suivantes sont obligatoires : {', '.join(missing)}."
                )

    @api.constrains('competences')
    def _check_required_competences(self):
        for record in self:
            required_competences = record.competences.filtered(lambda c: c.is_required)
            if not required_competences.ids:
                return  # Pas de compétences obligatoires spécifiées pour ce poste

            missing = [comp.name for comp in required_competences if comp not in record.competences]
            if missing:
                raise ValidationError(
                    f"Les compétences suivantes sont obligatoires : {', '.join(missing)}."
                )

    def get_job_criteria(self):
        """Récupère les critères du poste avec leurs niveaux d'importance"""
        try:
            return {
                'experience_years': self.experience_years or 0,
                'is_experience_years_required': self.is_experience_years_required,
                'experience_years_importance': self.experience_years_importance or '3',

                'education': self.education or '',
                'is_education_required': self.is_education_required,
                'education_importance': self.education_importance or '3',

                'location': self.location or '',
                'is_location_required': self.is_location_required,
                'location_importance': self.location_importance or '3',

                'skills': self.skills or '',
                'is_skills_required': self.is_skills_required,
                'skills_importance': self.skills_importance or '3',

                'competences': [{'name': comp.name, 'is_required': comp.is_required,
                                 'importance_level': comp.importance_level or '3'}
                                for comp in self.competences],
                'competences_importance': self.competences_importance or '3',

                'language_ids': [{'name': lang.name, 'is_required': lang.is_required,
                                  'importance_level': lang.importance_level or '3'}
                                 for lang in self.language_ids],
                'languages_importance': self.languages_importance or '3',
            }
        except Exception as e:
            _logger.error(f"Erreur lors de la récupération des critères du poste : {e}")
            return {
                'experience_years': 0,
                'education': '',
                'competences': [],
                'language_ids': [],
                'location': '',
            }

    def get_importance_percentage(self):
        """
        Calcule le pourcentage d'importance basé sur le niveau d'étoiles.
        Returns:
            float: Pourcentage d'importance (0-100)
        """
        stars = int(self.importance_level) if self.importance_level else 0
        return (stars / 5) * 100
