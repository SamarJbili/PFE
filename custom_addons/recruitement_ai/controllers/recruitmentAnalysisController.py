# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import base64
import tempfile
import os
import logging
import csv
from werkzeug.utils import secure_filename
import pandas as pd
# Import the AI recruitment functions
from ..utils import ai_recruitment

_logger = logging.getLogger(__name__)


class RecruitmentAnalysisController(http.Controller):
    @http.route('/recruitment/analyze_cvs', type='json', auth='public', csrf=False)
    def analyze_cvs(self, job_id):
        # Vérifier les permissions
        if not request.env.user.has_group('hr_recruitment.group_hr_recruitment_user'):
            return {'success': False, 'message': 'Permission refusée'}

        job = request.env['hr.job'].browse(int(job_id))
        if not job.exists():
            return {'success': False, 'message': 'Offre d\'emploi non trouvée'}

        applications = request.env['hr.applicant'].search([
            ('job_id', '=', job.id)
        ])

        if not applications:
            return {'success': False, 'message': 'Aucune candidature trouvée pour cette offre d\'emploi'}

        results = []
        all_cv_data = []
        cv_count = 0

        for application in applications:
            attachments = request.env['ir.attachment'].search([
                ('res_model', '=', 'hr.applicant'),
                ('res_id', '=', application.id)
            ])

            _logger.info(f"Application: {application.partner_name}, Attachments: {len(attachments)}")

            for attachment in attachments:
                _logger.info(f"Attachment: {attachment.name}, Mimetype: {attachment.mimetype}")

                # Vérifier si c'est un CV (élargir les critères)
                is_cv = any(keyword in attachment.name.lower() for keyword in
                            ['cv', 'resume', 'curriculum', 'lettre', 'letter', 'profil'])

                # Vérifier également par type MIME
                if not is_cv and attachment.mimetype:
                    is_cv = any(
                        mime_type in attachment.mimetype for mime_type in ['pdf', 'word', 'docx', 'application'])

                if not is_cv:
                    _logger.info(f"Skipping attachment: {attachment.name} - not identified as CV")
                    continue

                cv_count += 1
                _logger.info(f"Processing CV: {attachment.name}")

                try:
                    # Sauvegarder la pièce jointe dans un fichier temporaire
                    file_data = base64.b64decode(attachment.datas)
                    temp_dir = tempfile.mkdtemp()
                    file_path = os.path.join(temp_dir, secure_filename(attachment.name))

                    with open(file_path, 'wb') as f:
                        f.write(file_data)

                    # Déterminer le type de fichier (plus inclusif)
                    file_type = None
                    if attachment.mimetype and (
                            'pdf' in attachment.mimetype or attachment.name.lower().endswith('.pdf')):
                        file_type = 'pdf'
                    elif attachment.mimetype and ('word' in attachment.mimetype or 'docx' in attachment.mimetype or
                                                  attachment.name.lower().endswith(
                                                      '.doc') or attachment.name.lower().endswith('.docx')):
                        file_type = 'docx'
                    else:
                        # Si on ne peut pas déterminer par MIME, essayer par extension
                        if attachment.name.lower().endswith('.pdf'):
                            file_type = 'pdf'
                        elif attachment.name.lower().endswith('.docx') or attachment.name.lower().endswith('.doc'):
                            file_type = 'docx'

                    if not file_type:
                        _logger.warning(f"Type de fichier non supporté: {attachment.mimetype}, nom: {attachment.name}")
                        os.remove(file_path)
                        os.rmdir(temp_dir)
                        continue

                    # Traiter le CV avec le module AI
                    _logger.info(f"Calling process_cv with {file_path}, type: {file_type}")
                    cv_df = ai_recruitment.process_cv(file_path, file_type)
                    _logger.info(f"CV DataFrame returned: {cv_df}")

                    # Créer le dictionnaire de données CV à partir du DataFrame
                    if not cv_df.empty:
                        cv_data = {
                            'Nom': application.partner_name or 'Inconnu',
                            'Expérience': '',
                            'Compétences': '',
                            'Formation': '',
                        }

                        # Récupérer les données de la première ligne du DataFrame
                        row = cv_df.iloc[0]

                        if 'Nom' in cv_df.columns and not pd.isna(row['Nom']) and row['Nom']:
                            cv_data['Nom'] = row['Nom']

                        if 'Expérience' in cv_df.columns and not pd.isna(row['Expérience']) and row['Expérience']:
                            cv_data['Expérience'] = row['Expérience']

                        if 'Compétences' in cv_df.columns and not pd.isna(row['Compétences']) and row['Compétences']:
                            cv_data['Compétences'] = row['Compétences']

                        if 'Formation' in cv_df.columns and not pd.isna(row['Formation']) and row['Formation']:
                            cv_data['Formation'] = row['Formation']

                        _logger.info(f"CV data extracted: {cv_data}")
                        all_cv_data.append(cv_data)
                    else:
                        _logger.warning("CV DataFrame is empty")

                    # Nettoyage des fichiers temporaires
                    os.remove(file_path)
                    os.rmdir(temp_dir)

                except Exception as e:
                    _logger.error(f"Échec du traitement du CV {attachment.name}: {str(e)}")
                    import traceback
                    _logger.error(traceback.format_exc())
                    # Essayer de nettoyer même en cas d'erreur
                    try:
                        if 'file_path' in locals() and os.path.exists(file_path):
                            os.remove(file_path)
                        if 'temp_dir' in locals() and os.path.exists(temp_dir):
                            os.rmdir(temp_dir)
                    except Exception as cleanup_e:
                        _logger.error(f"Erreur de nettoyage des fichiers temporaires: {str(cleanup_e)}")

        # Générer un fichier CSV si des données sont présentes
        if all_cv_data:
            csv_file_path = f"/tmp/cv_analysis_{job_id}.csv"
            try:
                with open(csv_file_path, mode='w', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=['Nom', 'Expérience', 'Compétences', 'Formation'])
                    writer.writeheader()
                    writer.writerows(all_cv_data)

                return {'success': True, 'csv_url': f"/recruitment/download_csv/{job_id}", 'cv_count': cv_count}

            except Exception as e:
                _logger.error(f"Erreur lors de la création du fichier CSV: {str(e)}")
                return {'success': False, 'message': 'Erreur lors de la création du fichier CSV'}

        return {'success': False,
                'message': f'Aucun CV analysé. Total candidatures: {len(applications)}, Pièces jointes trouvées: {cv_count}'}

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