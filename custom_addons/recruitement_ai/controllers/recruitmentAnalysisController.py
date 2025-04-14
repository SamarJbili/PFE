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
                    # Ajouter la prise en charge des fichiers image
                    elif attachment.mimetype and ('image' in attachment.mimetype or
                                                  any(attachment.name.lower().endswith(ext) for ext in
                                                      ['.png', '.jpg', '.jpeg'])):
                        # Determiner précisément le type d'image
                        if 'png' in attachment.mimetype or attachment.name.lower().endswith('.png'):
                            file_type = 'png'
                        elif 'jpeg' in attachment.mimetype or attachment.name.lower().endswith(
                                '.jpg') or attachment.name.lower().endswith('.jpeg'):
                            file_type = 'jpg'
                    else:
                        # Si on ne peut pas déterminer par MIME, essayer par extension
                        if attachment.name.lower().endswith('.pdf'):
                            file_type = 'pdf'
                        elif attachment.name.lower().endswith('.docx') or attachment.name.lower().endswith('.doc'):
                            file_type = 'docx'
                        elif attachment.name.lower().endswith('.png'):
                            file_type = 'png'
                        elif attachment.name.lower().endswith('.jpg') or attachment.name.lower().endswith('.jpeg'):
                            file_type = 'jpg'

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
                    # Créer le dictionnaire de données CV à partir du DataFrame
                    if not cv_df.empty:
                        cv_data = {
                            "Nom": "",
                            "phone": "",
                            "email": "",
                            "education": "",
                            "experience_years": "",
                            "location": "",
                            "skills": [],
                            "languages": []  # Add this new field
                        }

                        # Récupérer les données de la première ligne du DataFrame
                        row = cv_df.iloc[0]

                        if 'Nom' in cv_df.columns and not pd.isna(row['Nom']) and row['Nom']:
                            cv_data['Nom'] = row['Nom']

                        if 'phone' in cv_df.columns and not pd.isna(row['phone']) and row['phone']:
                            cv_data['phone'] = row['phone']

                        if 'email' in cv_df.columns and not pd.isna(row['email']) and row['email']:
                            cv_data['email'] = row['email']

                            # Fix for education field - check if list is not empty
                            if 'education' in cv_df.columns and isinstance(row['education'], list) and len(
                                    row['education']) > 0:
                                cv_data['education'] = row['education']
                            elif 'education' in cv_df.columns and not pd.isna(row['education']):
                                cv_data['education'] = row['education']

                        if 'experience_years' in cv_df.columns and not pd.isna(row['experience_years']) and row[
                            'experience_years']:
                            cv_data['experience_years'] = row['experience_years']

                        if 'location' in cv_df.columns and not pd.isna(row['location']) and row['location']:
                            cv_data['location'] = row['location']

                        if 'skills' in cv_df.columns and isinstance(row['skills'], list) and any(row['skills']):
                            cv_data['skills'] = row['skills']

                        # Add handling for languages
                        if 'languages' in cv_df.columns and isinstance(row['languages'], list) and any(
                                row['languages']):
                            cv_data['languages'] = row['languages']

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

            # Tri des données par expérience (en ordre décroissant)
            sorted_cv_data = sorted(all_cv_data,
                                    key=lambda x: float(x['Nom']) if x['Nom'].isdigit() else 0,
                                    reverse=True)

            try:
                with open(csv_file_path, mode='w', newline='', encoding='utf-8') as file:
                    # Déterminer tous les champs possibles dans les CV
                    all_fields = set()
                    for cv_data in sorted_cv_data:
                        all_fields.update(cv_data.keys())

                    # Définir l'ordre des champs principaux
                    fieldnames = [
                        "Nom",
                        "phone",
                        "email",
                        "education",
                        "experience_years",
                        "location",
                        "skills",
                        "languages"  # Add this new field
                    ]

                    # Ajouter les autres champs qui pourraient être présents dans certains CV
                    for field in all_fields:
                        if field not in fieldnames:
                            fieldnames.append(field)

                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(sorted_cv_data)  # Utiliser les données triées

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

    def load_csv(self, job_id):
        file_path = f"/tmp/cv_analysis_{job_id}.csv"
        _logger.info(f"Chargement du fichier CSV depuis : {file_path}")
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path)
                _logger.info(f"Fichier CSV chargé avec succès, nombre de lignes : {len(df)}")
                return df
            except Exception as e:
                _logger.error(f"Erreur lors du chargement du fichier CSV : {str(e)}")
        else:
            _logger.warning(f"Fichier CSV non trouvé à {file_path}")
        return None

    def calculate_score(self, candidate, criteria):
        score = 0
        _logger.info(f"Calcul du score pour le candidat : {candidate.get('name')}")

        # Expérience (40%)
        experience = float(candidate.get('experience_years', 0))
        if experience >= criteria.get('experience_years', 0):
            score += 40
            _logger.info(f"Expérience : {experience} années -> score ajouté : 40")

        # Diplôme (30%) - Amélioration de la correspondance
        candidate_education = str(candidate.get('education', '')).lower().replace(' ', '').replace('+', '')
        job_education = str(criteria.get('education', '')).lower().replace('bac_', 'bac').replace('_', ' ')

        education_mapping = {
            'bac+3': ['bac+3', 'bac 3', 'licence', 'bachelors'],
            'master': ['master', 'm1', 'm2', 'postgraduate'],
            'doctorat': ['doctorat', 'phd', 'doctorate'],
            'autre': ['autre', 'other']
        }

        for level, variants in education_mapping.items():
            if job_education == level and any(variant in candidate_education for variant in variants):
                score += 30
                _logger.info(f"Diplôme requis trouvé : {candidate['education']} -> score ajouté : 30")
                break

        # Localisation (20%)
        if 'location' in candidate and criteria.get('location', '').lower() in str(candidate['location']).lower():
            score += 20
            _logger.info(f"Localisation : {candidate['location']} -> score ajouté : 20")

        # Bonus (10%)
        if 'phone' in candidate and 'email' in candidate:
            score += 10
            _logger.info(f"Candidat a un téléphone et un email -> score ajouté : 10")

        _logger.info(f"Score total pour {candidate['Nom']} : {score}")
        return score

    @http.route('/recruitment/evaluate_cvs/<int:job_id>', type='json', auth='user')
    def evaluate_cvs(self, job_id):
        _logger.info(f"Évaluation des CVs pour le job ID : {job_id}")
        df = self.load_csv(job_id)
        if df is None:
            return {'success': False, 'message': 'Aucun fichier CSV trouvé'}

        # Récupérer les critères de l'offre
        criteria = request.env['hr.job'].browse(job_id).get_job_criteria()
        if not criteria:
            return {'success': False, 'message': 'Aucun critère défini pour cette offre'}

        results = []
        for _, row in df.iterrows():
            candidate = row.to_dict()
            _logger.info(f"Traitement du candidat : {candidate.get('Nom')}")
            candidate['score'] = self.calculate_score(candidate, criteria)
            results.append(candidate)

        # Trier les résultats par score décroissant
        results_sorted = sorted(results, key=lambda x: x['score'], reverse=True)

        _logger.info("Résultats triés par score :")
        for result in results_sorted:
            _logger.info(f"{result.get('Nom', 'Candidat sans nom')} : {result['score']}")

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

        return {'success': True, 'results': results_sorted}
