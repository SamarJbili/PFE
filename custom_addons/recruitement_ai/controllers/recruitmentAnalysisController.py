# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import base64
import tempfile
import os
import logging
import csv
from werkzeug.utils import secure_filename

# Import the AI recruitment functions
from ..utils import ai_recruitment

_logger = logging.getLogger(__name__)

class RecruitmentAnalysisController(http.Controller):
    @http.route('/recruitment/analyze_cvs', type='json', auth='public', csrf=False)
    def analyze_cvs(self, job_id):
        # Vérifier les permissions
        if not request.env.user.has_group('hr_recruitment.group_hr_recruitment_user'):
            return {'error': 'Permission refusée'}

        job = request.env['hr.job'].browse(int(job_id))
        if not job.exists():
            return {'error': 'Offre d\'emploi non trouvée'}

        applications = request.env['hr.applicant'].search([
            ('job_id', '=', job.id)
        ])

        if not applications:
            return {'success': False, 'message': 'Aucune candidature trouvée pour cette offre d\'emploi'}

        results = []
        all_cv_data = []

        for application in applications:
            attachments = request.env['ir.attachment'].search([
                ('res_model', '=', 'hr.applicant'),
                ('res_id', '=', application.id)
            ])

            for attachment in attachments:
                if not any(keyword in attachment.name.lower() for keyword in ['cv', 'resume', 'curriculum']):
                    continue

                try:
                    # Sauvegarder la pièce jointe dans un fichier temporaire
                    file_data = base64.b64decode(attachment.datas)
                    temp_dir = tempfile.mkdtemp()
                    file_path = os.path.join(temp_dir, secure_filename(attachment.name))

                    with open(file_path, 'wb') as f:
                        f.write(file_data)

                    # Déterminer le type de fichier
                    file_type = None
                    if attachment.mimetype and 'pdf' in attachment.mimetype:
                        file_type = 'pdf'
                    elif attachment.mimetype and ('word' in attachment.mimetype or 'docx' in attachment.mimetype):
                        file_type = 'docx'

                    if not file_type:
                        continue

                    # Traiter le CV avec le module AI
                    cv_info = ai_recruitment.process_cv(file_path, file_type)

                    # Convertir les données extraites en dictionnaire
                    cv_data = {
                        'Nom': cv_info['Nom'].values[0] if not cv_info['Nom'].empty else application.partner_name or 'Inconnu',
                        'Expérience': cv_info['Expérience'].values[0] if not cv_info['Expérience'].empty else '',
                        'Compétences': cv_info['Compétences'].values[0] if not cv_info['Compétences'].empty else '',
                        'Formation': cv_info['Formation'].values[0] if not cv_info['Formation'].empty else '',
                    }
                    all_cv_data.append(cv_data)

                    # Nettoyage des fichiers temporaires
                    os.remove(file_path)
                    os.rmdir(temp_dir)

                except Exception as e:
                    _logger.error(f"Échec du traitement du CV {attachment.name}: {str(e)}")

        # Générer un fichier CSV si des données sont présentes
        if all_cv_data:
            csv_file_path = f"/tmp/cv_analysis_{job_id}.csv"
            try:
                with open(csv_file_path, mode='w', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=['Nom', 'Expérience', 'Compétences', 'Formation'])
                    writer.writeheader()
                    writer.writerows(all_cv_data)

                return {'success': True, 'csv_url': f"/recruitment/download_csv/{job_id}"}

            except Exception as e:
                _logger.error(f"Erreur lors de la création du fichier CSV: {str(e)}")
                return {'success': False, 'message': 'Erreur lors de la création du fichier CSV'}

        return {'success': False, 'message': 'Aucun CV analysé'}

    @http.route('/recruitment/download_csv/<int:job_id>', type='http', auth='user')
    def download_csv(self, job_id):
        file_path = f"/tmp/cv_analysis_{job_id}.csv"
        if os.path.exists(file_path):
            try:
                with open(file_path, 'rb') as file:
                    return request.make_response(file.read(), [
                        ('Content-Type', 'text/csv'),
                        ('Content-Disposition', f'attachment; filename="cv_analysis_{job_id}.csv"')
                    ])
            except Exception as e:
                _logger.error(f"Erreur lors du téléchargement du fichier CSV: {str(e)}")
                return request.not_found()
        return request.not_found()
