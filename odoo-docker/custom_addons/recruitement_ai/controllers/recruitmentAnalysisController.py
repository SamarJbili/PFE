# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import base64
import tempfile
import os
import logging
import csv
from werkzeug.utils import secure_filename
from unidecode import unidecode
from fuzzywuzzy import process
import pandas as pd

# Importer les fonctions AI et évaluation
from ..utils import ai_recruitment
from ..utils.ai_recruitment import evaluate_cv
_logger = logging.getLogger(__name__)

class RecruitmentAnalysisController(http.Controller):
    @http.route('/recruitment/analyze_cvs', type='json', auth='public', csrf=False)
    def analyze_cvs(self, job_id):
        if not request.env.user.has_group('hr_recruitment.group_hr_recruitment_user'):
            return {'success': False, 'message': 'Permission refusée'}

        job = request.env['hr.job'].browse(int(job_id))
        if not job.exists():
            return {'success': False, 'message': 'Offre d\'emploi non trouvée'}

        applications = request.env['hr.applicant'].search([
            ('job_id', '=', job_id)
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

                is_cv = any(keyword in attachment.name.lower() for keyword in ['cv', 'resume', 'curriculum', 'lettre', 'letter', 'profil'])
                if not is_cv and attachment.mimetype:
                    is_cv = any(mime_type in attachment.mimetype for mime_type in ['pdf', 'word', 'docx', 'application'])

                if not is_cv:
                    _logger.info(f"Skipping attachment: {attachment.name} - not identified as CV")
                    continue

                cv_count += 1
                _logger.info(f"Processing CV: {attachment.name}")

                try:
                    file_data = base64.b64decode(attachment.datas)
                    temp_dir = tempfile.mkdtemp()
                    file_path = os.path.join(temp_dir, secure_filename(attachment.name))

                    with open(file_path, 'wb') as f:
                        f.write(file_data)

                    file_type = None
                    if attachment.mimetype and ('pdf' in attachment.mimetype or attachment.name.lower().endswith('.pdf')):
                        file_type = 'pdf'
                    elif attachment.mimetype and ('word' in attachment.mimetype or 'docx' in attachment.mimetype or attachment.name.lower().endswith('.docx')):
                        file_type = 'docx'

                    if not file_type:
                        _logger.warning(f"Unsupported file type: {attachment.mimetype}, name: {attachment.name}")
                        os.remove(file_path)
                        os.rmdir(temp_dir)
                        continue

                    _logger.info(f"Calling process_cv with {file_path}, type: {file_type}")
                    cv_df = ai_recruitment.process_cv(file_path, file_type)
                    _logger.info(f"CV DataFrame returned: {cv_df}")

                    if not cv_df.empty:
                        cv_data = {
                            "Nom": "",
                            "phone": "",
                            "email": "",
                            "education": "",
                            "experience_years": "",
                            "location": "",
                            "skills": [],
                            "languages": [],

                        }

                        row = cv_df.iloc[0]

                        if 'Nom' in cv_df.columns and not pd.isna(row['Nom']) and row['Nom']:
                            cv_data['Nom'] = row['Nom']

                        if 'phone' in cv_df.columns and not pd.isna(row['phone']) and row['phone']:
                            cv_data['phone'] = row['phone']

                        if 'email' in cv_df.columns and not pd.isna(row['email']) and row['email']:
                            cv_data['email'] = row['email']

                        if 'education' in cv_df.columns and not pd.isna(row['education']):
                            cv_data['education'] = row['education']

                        if 'experience_years' in cv_df.columns:
                            experience_value = row.get('experience_years')
                            if pd.notna(experience_value) and experience_value:
                                cv_data['experience_years'] = experience_value

                        if 'location' in cv_df.columns and not pd.isna(row['location']) and row['location']:
                            cv_data['location'] = row['location']

                        if 'skills' in cv_df.columns and isinstance(row['skills'], list) and any(row['skills']):
                            cv_data['skills'] = row['skills']

                        if 'languages' in cv_df.columns and isinstance(row['languages'], list) and any(row['languages']):
                            cv_data['languages'] = row['languages']


                        _logger.info(f"CV data extracted: {cv_data}")
                        all_cv_data.append(cv_data)
                    else:
                        _logger.warning("CV DataFrame is empty")

                    os.remove(file_path)
                    os.rmdir(temp_dir)

                except Exception as e:
                    _logger.error(f"Failed to process CV {attachment.name}: {str(e)}")
                    import traceback
                    _logger.error(traceback.format_exc())
                    try:
                        if 'file_path' in locals() and os.path.exists(file_path):
                            os.remove(file_path)
                        if 'temp_dir' in locals() and os.path.exists(temp_dir):
                            os.rmdir(temp_dir)
                    except Exception as cleanup_e:
                        _logger.error(f"Temporary file cleanup failed: {str(cleanup_e)}")

        if all_cv_data:
            csv_file_path = f"/tmp/cv_analysis_{job_id}.csv"
            sorted_cv_data = sorted(all_cv_data, key=lambda x: float(x['Nom']) if x['Nom'].isdigit() else 0, reverse=True)

            try:
                with open(csv_file_path, mode='w', newline='', encoding='utf-8') as file:
                    all_fields = set()
                    for cv_data in sorted_cv_data:
                        all_fields.update(cv_data.keys())

                    fieldnames = [
                        "Nom", "phone", "email", "education", "experience_years", "location", "skills", "languages"
                    ]

                    for field in all_fields:
                        if field not in fieldnames:
                            fieldnames.append(field)

                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(sorted_cv_data)

                return {'success': True, 'csv_url': f"/recruitment/download_csv/{job_id}", 'cv_count': cv_count}

            except Exception as e:
                _logger.error(f"Error creating CSV file: {str(e)}")
                return {'success': False, 'message': 'Error creating CSV file'}

        return {'success': False, 'message': f'No CVs processed. Total applications: {len(applications)}, Attachments found: {cv_count}'}

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
                _logger.error(f"Error downloading CSV file: {str(e)}")
                return request.not_found()
        return request.not_found()

    def load_csv(self, job_id):
        file_path = f"/tmp/cv_analysis_{job_id}.csv"
        _logger.info(f"Loading CSV file from: {file_path}")
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path)
                _logger.info(f"CSV file loaded successfully, number of rows: {len(df)}")
                return df
            except Exception as e:
                _logger.error(f"Error loading CSV file: {str(e)}")
        else:
            _logger.warning(f"CSV file not found at {file_path}")
        return None

    @http.route('/recruitment/evaluate_cvs/<int:job_id>', type='json', auth='user')
    def evaluate_cvs(self, job_id):
        _logger.info(f"Evaluating CVs for job ID: {job_id}")

        # Load CSV for the job
        df = self.load_csv(job_id)
        if df is None:
            return {'success': False, 'message': 'No CSV file found'}

        # Log the columns of the CSV to verify the structure
        _logger.info(f"CSV Columns: {df.columns}")

        # Retrieve job criteria
        criteria = request.env['hr.job'].browse(job_id).get_job_criteria()
        if not criteria:
            return {'success': False, 'message': 'No criteria defined for this job'}

        results = []

        # Process each candidate's CV
        for _, row in df.iterrows():
            candidate = row.to_dict()

            # Log candidate's information
            _logger.info(f"Processing candidate: {candidate.get('Nom', 'Unknown')}")

            # Check if 'Nom' is present in the candidate data
            if 'Nom' not in candidate:
                _logger.error(f"Missing 'Nom' in candidate: {candidate}")
                continue  # Skip this iteration if 'Nom' is missing

            # Evaluate the CV for the candidate
            candidate_evaluation = evaluate_cv(candidate, criteria)
            candidate['score'] = candidate_evaluation.get('total_score', 0)  # Default score to 0 if not found
            results.append(candidate)

        # Sort candidates by their scores
        results_sorted = sorted(results, key=lambda x: x.get('score', 0), reverse=True)

        # Log sorted results
        _logger.info("Sorted results by score:")
        for result in results_sorted:
            _logger.info(f"{result.get('Nom', 'No name')} : {result['score']}")

        # Mettre à jour les scores dans Odoo pour les candidats existants
        applicants = request.env['hr.applicant'].search([])  # Récupérer tous les candidats

        for result in results_sorted:
            nom_candidat = result.get('Nom')

            # Vérification du nom
            if not isinstance(nom_candidat, str) or not nom_candidat.strip():
                _logger.warning(f"Nom invalide trouvé : {nom_candidat}, candidat ignoré.")
                continue

            _logger.info(f"Recherche du candidat avec le nom : {nom_candidat}")

            # Normalisation du nom candidat
            nom_candidat_normalized = unidecode(nom_candidat.strip().lower())

            # Construire une liste des noms normalisés des candidats Odoo
            applicant_names = {applicant.id: unidecode(applicant.partner_name.strip().lower()) for applicant in
                               applicants if applicant.partner_name}

            # Trouver le candidat le plus proche en utilisant fuzzy matching
            if applicant_names:
                best_match = process.extractOne(nom_candidat_normalized, applicant_names.values(),
                                                score_cutoff=70)  # Seuil de 70% de similarité
                if best_match:
                    matched_id = list(applicant_names.keys())[list(applicant_names.values()).index(best_match[0])]
                    applicant = request.env['hr.applicant'].browse(matched_id)

                    if applicant:
                        applicant.write({'score': result['score']})
                        _logger.info(f"Score mis à jour pour {applicant.partner_name} : {result['score']}")
                        continue

            _logger.warning(f"Aucun candidat trouvé pour {nom_candidat}")

        return {
            'success': True,
            'message': 'CVs evaluated successfully',
            'evaluated_candidates': results_sorted,
            'results': results_sorted  # Add this line to maintain compatibility
        }

    @http.route('/recruitment/update_applicants_stage', type='json', auth='user')
    def update_applicants_stage(self, applicants=None, **kwargs):
        """
        Met à jour la phase des candidats
        """
        if not applicants or not isinstance(applicants, list):
            return {'success': False, 'message': 'Données des candidats manquantes ou invalides'}

        try:
            updated_count = 0
            for applicant_data in applicants:
                if 'id' in applicant_data and 'stage_id' in applicant_data:
                    applicant = request.env['hr.applicant'].browse(int(applicant_data['id']))
                    if applicant.exists():
                        # Si stage_id est un nom de phase, chercher l'ID correspondant
                        stage_id = applicant_data['stage_id']
                        if isinstance(stage_id, str):
                            stage = request.env['hr.recruitment.stage'].search([('name', '=', stage_id)], limit=1)
                            if stage:
                                stage_id = stage.id
                            else:
                                continue

                        # Mise à jour de la phase
                        applicant.write({'stage_id': stage_id})
                        updated_count += 1

            return {
                'success': True,
                'message': f'{updated_count} candidats mis à jour',
                'updated_count': updated_count
            }

        except Exception as e:
            return {'success': False, 'message': str(e)}

    # Add this method to your RecruitmentAnalysisController class in paste.txt

    @http.route('/recruitment/get_stage_by_name', type='json', auth='user')
    def get_stage_by_name(self, name=None):
        """
        Récupère l'ID d'une phase de recrutement par son nom
        """
        if not name:
            return {'success': False, 'message': 'Nom de phase non spécifié'}

        try:
            stage = request.env['hr.recruitment.stage'].search([('name', '=', name)], limit=1)
            if stage:
                return {
                    'success': True,
                    'stage_id': stage.id,
                    'name': stage.name
                }
            else:
                return {
                    'success': False,
                    'message': f'Aucune phase trouvée avec le nom: {name}'
                }
        except Exception as e:
            _logger.error(f"Erreur lors de la recherche de la phase: {str(e)}")
            return {'success': False, 'message': str(e)}

    @http.route('/recruitment/get_applicant_by_name', type='json', auth='user')
    def get_applicant_by_name(self, name):
        """
        Recherche un candidat par son nom dans Odoo, en utilisant une correspondance floue.
        :param name: Le nom du candidat à rechercher.
        :return: Un dictionnaire contenant les informations du candidat si trouvé
        """
        _logger.info(f"Recherche du candidat avec le nom : {name}")

        # Vérification si le nom est valide
        if not name or not isinstance(name, str) or not name.strip():
            _logger.warning(f"Nom invalide fourni : {name}")
            return {'success': False, 'message': 'Nom invalide'}

        try:
            # Normalisation du nom
            candidate_name_normalized = unidecode(name.strip().lower())

            # Récupérer les candidats dans Odoo avec un nom similaire
            applicants = request.env['hr.applicant'].search([])

            # Construire un dictionnaire des noms normalisés
            applicant_names = {applicant.id: unidecode(applicant.partner_name.strip().lower())
                               for applicant in applicants
                               if applicant.partner_name}

            _logger.info(f"Nombre de candidats dans la base : {len(applicant_names)}")

            # Recherche floue du meilleur match
            if applicant_names:
                best_match = process.extractOne(candidate_name_normalized, applicant_names.values(),
                                                score_cutoff=70)  # Seuil à 70%

                if best_match:
                    matched_name = best_match[0]
                    match_score = best_match[1]
                    matched_id = list(applicant_names.keys())[list(applicant_names.values()).index(matched_name)]

                    _logger.info(f"Match trouvé pour '{name}': ID={matched_id}, Score={match_score}%")

                    return {
                        'success': True,
                        'applicant_id': matched_id,
                        'match_score': match_score
                    }

            _logger.warning(f"Aucun candidat trouvé pour '{name}'")
            return {'success': False, 'message': f"Aucun candidat trouvé pour '{name}'"}

        except Exception as e:
            _logger.error(f"Erreur lors de la recherche du candidat '{name}': {str(e)}")
            return {'success': False, 'message': str(e)}