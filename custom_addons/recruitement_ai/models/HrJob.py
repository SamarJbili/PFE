from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class HrCV(models.Model):
    _inherit = 'hr.applicant'

    def get_cvs_by_job(self, job_id):
        """Récupère tous les CVs pour un poste spécifique"""
        _logger.info(f"Recherche des CVs pour le poste {job_id}")

        applicants = self.search([('job_id', '=', job_id)])
        _logger.info(f"Candidatures trouvées: {len(applicants)}")

        cvs = []

        for applicant in applicants:
            attachments = self.env['ir.attachment'].search([
                ('res_model', '=', 'hr.applicant'),
                ('res_id', '=', applicant.id)
            ])

            _logger.info(f"Candidat: {applicant.partner_name}, pièces jointes: {len(attachments)}")

            # Filtrer uniquement les pièces jointes qui ressemblent à des CVs
            cv_attachments = []
            for attachment in attachments:
                is_cv = False

                # Vérifier par nom
                if any(keyword in attachment.name.lower() for keyword in
                       ['cv', 'resume', 'curriculum', 'lettre', 'letter']):
                    is_cv = True

                # Vérifier par type MIME
                if not is_cv and attachment.mimetype:
                    is_cv = any(
                        mime_type in attachment.mimetype for mime_type in ['pdf', 'word', 'docx', 'application'])

                if is_cv:
                    cv_attachments.append({
                        'name': attachment.name,
                        'mimetype': attachment.mimetype,
                        'datas': attachment.datas,  # Contenu binaire encodé en base64
                        'applicant_name': applicant.partner_name
                    })

            _logger.info(f"CVs trouvés pour {applicant.partner_name}: {len(cv_attachments)}")
            cvs.extend(cv_attachments)

        _logger.info(f"Total CVs trouvés: {len(cvs)}")
        return cvs