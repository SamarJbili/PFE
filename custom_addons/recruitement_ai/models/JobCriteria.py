from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class JobCriteria(models.Model):
    _inherit = 'hr.job'


    experience_years = fields.Integer(string="Années d'expérience", required=True)

    education = fields.Selection([
        ('bac_plus_3', 'Bac +3'),
        ('master', 'Master'),
        ('doctorat', 'Doctorat'),
        ('autre', 'Autre')
    ], string="Niveau de formation requis", required=True)

    @api.model
    def _get_default_domain(self):
        # Logique de génération de domaine par défaut
        return [
            ('active', '=', True),  # Filtrer uniquement les offres actives
            # Ajoutez d'autres conditions si nécessaire
        ]

    def _search_domain(self, domain=None):
        """
        Méthode pour générer un domaine de recherche sécurisé
        :param domain: Domaine de recherche optionnel
        :return: Liste de domaines
        """
        try:
            # Utiliser le domaine par défaut si aucun n'est fourni
            if domain is None:
                domain = self._get_default_domain()

            # Ajouter des vérifications de sécurité supplémentaires si nécessaire
            return domain
        except Exception as e:
            # Gestion des erreurs
            self.env.cr.rollback()  # Annuler toute transaction en cours
            return [('id', '=', 0)]


    def get_job_criteria(self):
        """Récupère les critères du poste, soit depuis une table externe (job.criteria), soit depuis le modèle hr.job lui-même."""
        criteria = None
        try:
            # Vérifier si une table "job.criteria" existe avant de l'utiliser
            if 'job.criteria' in self.env:
                criteria = self.env['job.criteria'].search([('job_id', '=', self.id)], limit=1)

            if criteria:
                return {
                    'experience_years': criteria.experience_years,
                    'education': criteria.education or '',
                }
        except Exception as e:
            _logger.error(f"Erreur lors de la récupération des critères du poste : {e}")

        # Si aucun critère trouvé, on retourne les valeurs de hr.job
        return {
            'experience_years': self.experience_years,
            'education': self.education or '',  # Éviter les valeurs None ou False
        }
