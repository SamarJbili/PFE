import pandas as pd
import os
import tempfile
import logging
from datetime import datetime
import re
import nltk
from bs4 import BeautifulSoup
import PyPDF2
import spacy
import docx
from PIL import Image
import pytesseract
import pdfplumber
import traceback

from odoo.http import request

# Configuration du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Charger le modèle spaCy en français
nlp = spacy.load("fr_core_news_md")

from spacy.matcher import Matcher
matcher = Matcher(nlp.vocab)
# Liste des mots-clés
keywords = ['compétence', 'formation', 'éducation', 'certification', 'expérience', 'expérience professionnelle']

# Fonction pour extraire du texte d'une image (OCR)
def extract_ocr_text(image_file):
    try:
        image = Image.open(image_file)
        text = pytesseract.image_to_string(image, lang='fra')
        return text
    except Exception as e:
        logger.error(f"OCR error: {str(e)}")
        return ""

def extract_pdf_text(pdf_file):
    try:
        with pdfplumber.open(pdf_file) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
            return text
    except Exception as e:
        logger.error(f"PDF extraction error: {str(e)}")
        return ""

def extract_docx_text(docx_file):
    try:
        doc = docx.Document(docx_file)
        text = ""
        for para in doc.paragraphs:
            text += para.text + '\n'
        return text
    except Exception as e:
        logger.error(f"DOCX extraction error: {str(e)}")
        return ""

def clean_text(text):
    """ Nettoyer le texte des espaces et caractères inutiles. """
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

pdf_file = '/home/jbilisamar/Téléchargements/aHR0cHM6Ly9jZG4uZW5oYW5jdi5jb20vcHJlZGVmaW5lZC1leGFtcGxlcy9KcnRXZnE3NkY5ZnpGdERDMUNPTXhibVA4ZnRjTUhiclRsUkZDTmZaL2ltYWdlLnBuZw~~.png'
text = extract_ocr_text(pdf_file)
print(text)


def save_text_to_file(text, filename="extracted_text.txt"):
    try:
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(text)

        logger.info(f"Fichier sauvegardé à : {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde du texte dans le fichier : {str(e)}")
        return None

def extract_candidate_name(text):
    doc = nlp(text)

    # List to store detected names
    person_names = []

    # Chercher toutes les entités de type "PER" (personne)
    for ent in doc.ents:
        if ent.label_ == 'PER':  # Vérifie si l'entité est un nom de personne
            person_names.append(ent.text)

    # Si plusieurs noms sont détectés, on renvoie le premier ou tous les noms
    if person_names:
        return person_names[0]  # Renvoie le premier nom détecté
    else:
        return None


def extract_phone(cv_text):
    phone_patterns = [
        r'(?:(?:\+|00)(?:33|216|1|44|49))\s*[1-9](?:[\s.-]*\d{1,2}){4,}',
        r'(?:0|\+)\s*[1-9](?:[\s.-]*\d{2}){4}',
        r'\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}',
        r'\+\d{3}\s*\d{2}\s*\d{2}\s*\d{2}\s*\d{2}'
    ]

    for pattern in phone_patterns:
        phone_matches = re.search(pattern, cv_text)
        if phone_matches:
            phone = phone_matches.group()
            phone = re.sub(r'[\s.-]', '', phone)
            if phone.startswith('00'):
                phone = '+' + phone[2:]
            elif phone.startswith('0') and not phone.startswith('+'):
                phone = '+33' + phone[1:]
            return phone

    return None


# Fonction améliorée pour extraire les années d'expérience
def extract_experience_years2(cv_text):
    """
    Extract the number of years of experience from a CV - Version améliorée
    """
    if not cv_text or not isinstance(cv_text, str):
        return None

    # Méthode 1: Recherche directe des années d'expérience
    experience_patterns = [
        r'(\d+)[\s-]*(ans|années|an|année)[\s-]*(d\'|de\s+)?(expérience|exp[ée]riences?)',
        r'(expérience|exp[ée]riences?)[\s-]*(de|:)[\s-]*(\d+)[\s-]*(ans|années|an|année)',
        r'(\d+)[\s-]*(years|year)[\s-]*(of)?[\s-]*(experience)',
        r'(experience)[\s-]*(of|:)[\s-]*(\d+)[\s-]*(years|year)'
    ]

    for pattern in experience_patterns:
        matches = re.findall(pattern, cv_text.lower())
        if matches:
            for match in matches:
                # Extraire le nombre d'années
                years_str = next((m for m in match if m.isdigit()), None)
                if years_str:
                    years = int(years_str)
                    if 0 < years <= 50:  # Vérification de plausibilité
                        return years

    # Méthode 2: Calcul basé sur les dates d'emploi
    try:
        # Recherche des plages de dates (format 20XX - 20XX ou 20XX - Present)
        date_pattern = r'(?:19|20)\d{2}\s*(?:-|–|à|to)\s*(?:(?:19|20)\d{2}|pr[ée]sent|current|actuel|aujourd\'hui|now)'
        date_ranges = re.findall(date_pattern, cv_text, re.IGNORECASE)

        if date_ranges:
            total_years = 0
            current_year = datetime.now().year

            for date_range in date_ranges:
                years = re.findall(r'(?:19|20)\d{2}', date_range)
                if len(years) >= 1:
                    start_year = int(years[0])

                    # Déterminer l'année de fin
                    if len(years) >= 2:
                        end_year = int(years[1])
                    elif any(end_term in date_range.lower() for end_term in
                             ["present", "présent", "current", "actuel", "aujourd'hui", "now"]):
                        end_year = current_year
                    else:
                        continue

                    # Calculer la durée
                    if start_year <= end_year and start_year >= 1950 and end_year <= current_year:
                        total_years += (end_year - start_year)

            if total_years > 0:
                return min(total_years, 50)  # Limite à 50 ans d'expérience maximum

    except Exception as e:
        logger.warning(f"Erreur lors du calcul des années d'expérience: {str(e)}")

    # Méthode 3: Compter les entrées d'emploi distinctes
    try:
        # Recherche des sections d'expérience professionnelle
        experience_sections = re.findall(
            r'(?:expérience|experience|parcours|employment)\s+(?:professionnelle?|history|professionnel)', cv_text,
            re.IGNORECASE)

        if experience_sections:
            # Compter les entrées d'emploi
            job_patterns = [
                r'(?:^|\n)(?:19|20)\d{2}\s*[-–]\s*(?:(?:19|20)\d{2}|présent|present)',
                r'(?:^|\n)(?:[A-Z][a-zÀ-ÿ]+(?:\s+[^\n]+){0,5})\s*(?:19|20)\d{2}\s*[-–]'
            ]

            job_count = 0
            for pattern in job_patterns:
                job_entries = re.findall(pattern, cv_text)
                job_count += len(job_entries)

            if job_count >= 1:
                # Heuristique: assume 2 ans par poste en moyenne
                return min(job_count * 2, 50)  # Limite à 50 ans d'expérience maximum

    except Exception as e:
        logger.warning(f"Erreur lors du comptage des postes: {str(e)}")

    return None

def extract_experience_years(cv_text):
    """
    Extrait les années d'expérience professionnelle
    - Calcul précis avec validation des dates
    - Gère différents formats de dates
    """
    if not cv_text or not isinstance(cv_text, str):
        return None

    # Dictionnaire des mois en français (pour les écritures en lettres)
    mois_dict = {
        'janvier': 1, 'jan': 1,
        'février': 2, 'fev': 2,
        'mars': 3,
        'avril': 4, 'avr': 4,
        'mai': 5,
        'juin': 6,
        'juillet': 7, 'jul': 7,
        'août': 8,
        'septembre': 9, 'sept': 9,
        'octobre': 10, 'oct': 10,
        'novembre': 11, 'nov': 11,
        'décembre': 12, 'dec': 12
    }

    # Normaliser le texte
    cv_text = cv_text.lower()

    # Variables pour le calcul
    current_year = datetime.now().year
    total_years = 0

    # Motifs de recherche spécifiques pour les années d'expérience
    experience_patterns = [
        # Recherche de mentions directes d'années d'expérience
        r'(\d+)\s*(?:ans|années|an|année)\s*d.expérience',

        # Recherche de plages de dates avec années
        r'(\d{4})\s*[-–]\s*(\d{4}|actuelle|présent|present)'
    ]

    # Calcul des années d'expérience
    for pattern in experience_patterns:
        matches = re.findall(pattern, cv_text, re.IGNORECASE)

        for match in matches:
            # Gestion des mentions directes d'années
            if len(match) == 1:
                years = int(match[0])
                total_years = max(total_years, years)

            # Gestion des plages de dates
            elif len(match) == 2:
                start_year = int(match[0])

                # Gestion de l'année de fin
                if match[1].lower() in ['actuelle', 'présent', 'present']:
                    end_year = current_year
                else:
                    end_year = int(match[1])

                # Validation et calcul
                if 1950 <= start_year <= end_year <= current_year:
                    experience_years = end_year - start_year
                    total_years = max(total_years, experience_years)

    return total_years if total_years > 0 else None

def extract_location(cv_text):
    location_patterns = [
        r'(?:Adresse|Address|Location|Localisation)\s*(?::|;)?\s*([^,\n]+(?:,\s*[^,\n]+){0,3})',
        r'(?:\n|^)([A-Z][a-zA-ZÀ-ÿ\s]+(?:,\s*[A-Z][a-zA-ZÀ-ÿ\s]+){1,2})(?:\n|$)',
        r'(\d+\s*(?:rue|avenue|boulevard|bd|place)\s+[^,\n]+(?:,\s*[^,\n]+){0,3})'
    ]

    for pattern in location_patterns:
        matches = re.search(pattern, cv_text, re.IGNORECASE)
        if matches:
            location = matches.group(1).strip()
            if not re.search(r'@|\+|\d{2}[\s.-]?\d{2}[\s.-]?\d{2}', location):
                parts = [part.strip() for part in location.split(',') if part.strip()]
                if len(parts) <= 3:
                    return ', '.join(parts)

    cities = ["Paris", "Lyon", "Marseille", "Tunis", "Sfax", "Sousse", "Casablanca", "Rabat", "Alger", "Oran"]

    for city in cities:
        city_pattern = rf'{city}\s*(?:,\s*|\s+-\s*|\s+)?'
        matches = re.search(city_pattern, cv_text, re.IGNORECASE)
        if matches:
            location = matches.group(0).strip()
            return location

    return None
def extract_education_level(cv_text):
    if not cv_text or not isinstance(cv_text, str):
        return None
    degree_mapping = {
        # Anglais - positionnés en priorité pour éviter les mauvaises correspondances
        "\\bengineering\\b": ("Engineering/Bac+5", 5),
        "\\bengineer\\b": ("Engineer/Bac+5", 5),
        "\\bengineering degree\\b": ("Engineering/Bac+5", 5),
        "\\bdegree in engineering\\b": ("Engineering/Bac+5", 5),
        "\\bbachelor of engineering\\b": ("Engineering/Bac+5", 5),
        "\\beng[.]?\\b": ("Engineer/Bac+5", 5),
        "ph[.]*d": ("PhD/Bac+8", 8),
        "doctorate": ("Doctorate/Bac+8", 8),
        "master['s]*\\s*degree": ("Master/Bac+5", 5),
        "master['s]*\\s*of\\s*science": ("MSc/Bac+5", 5),
        "\\bmsc\\b": ("MSc/Bac+5", 5),
        "\\bmeng\\b": ("MEng/Bac+5", 5),
        "bachelor['s]*\\s*degree": ("Bachelor/Bac+3", 3),
        "bachelor['s]*\\s*of\\s*science": ("BSc/Bac+3", 3),
        "bachelor['s]*\\s*of\\s*engineering": ("BEng/Bac+3", 3),
        "\\bbsc\\b": ("BSc/Bac+3", 3),
        "\\bbeng\\b": ("BEng/Bac+3", 3),
        "associate\\s*degree": ("Associate Degree/Bac+2", 2),
        "high\\s*school\\s*diploma": ("High School Diploma/Bac", 0),
        "high\\s*school\\s*degree": ("High School Degree/Bac", 0),

        # Français
        "bac[-+]?\\s*\\+?\\s*(8|7|6)": ("Bac+\\1", 8),
        "bac[-+]?\\s*\\+?\\s*5": ("Bac+5", 5),
        "bac[-+]?\\s*\\+?\\s*4": ("Bac+4", 4),
        "bac[-+]?\\s*\\+?\\s*3": ("Bac+3", 3),
        "bac[-+]?\\s*\\+?\\s*2": ("Bac+2", 2),
        "bac[-+]?\\s*\\+?\\s*1": ("Bac+1", 1),
        "ph[.]*d": ("Doctorat/Bac+8", 8),
        "doctorat": ("Doctorat/Bac+8", 8),
        "thèse": ("Doctorat/Bac+8", 8),
        "master\\s*2": ("Master/Bac+5", 5),
        "master\\s*1": ("Master/Bac+4", 4),
        "m2\\b": ("Master/Bac+5", 5),
        "m1\\b": ("Master/Bac+4", 4),
        "\\bmast[eè]re\\b": ("Master/Bac+5", 5),
        "\\bmaster\\b": ("Master/Bac+5", 5),
        "\\bmba\\b": ("MBA/Bac+5", 5),
        "\\bmsc\\b": ("MSc/Bac+5", 5),
        "ingénieur": ("Ingénieur/Bac+5", 5),
        "ingé": ("Ingénieur/Bac+5", 5),
        "école\\s*d['e]\\s*ingénieur": ("Ingénieur/Bac+5", 5),
        "diplôme\\s*d['e]\\s*ingénieur": ("Ingénieur/Bac+5", 5),
        "maîtrise": ("Maîtrise/Bac+4", 4),
        "licence\\s*pro": ("Licence Pro/Bac+3", 3),
        "licence": ("Licence/Bac+3", 3),
        "bachelor": ("Bachelor/Bac+3", 3),
        "bts": ("BTS/Bac+2", 2),
        "dut": ("DUT/Bac+2", 2),
        "deug": ("DEUG/Bac+2", 2),
        "bac\\s*pro": ("Bac Pro/Bac", 0),
        "bac\\s*technologique": ("Bac Techno/Bac", 0),
        "bac\\s*général": ("Bac Général/Bac", 0),
        "baccalauréat": ("Baccalauréat/Bac", 0),
        "\\bbac\\b": ("Baccalauréat/Bac", 0),
    }

    normalized_text = ' '.join(cv_text.lower().split())
    current_level = None
    current_degree_name = None

    current_education_indicators = [
        r"niveau\s+d['e]\s*(?:formation|étude|qualification)[:]\s(\w+)",
        r"je\s+suis\s+diplômé\s+(?:de|d'une|du|d'un)\s+(\w+)",
        r"diplôme\s+(?:actuel|en\s+cours|obtenu)[:]\s(\w+)",
        r"titulaire\s+d['e]un[e]?\s+(\w+)",
        r"actuellement\s+en\s+(\w+)",
        r"j['e]\s+possède\s+un[e]?\s+(\w+)",
        # Patterns en anglais
        r"education\s+level[:]\s(\w+)",
        r"graduated\s+with\s+a\s+(\w+)",
        r"holding\s+a\s+(\w+)",
        r"currently\s+studying\s+(\w+)",
        r"i\s+have\s+a\s+(\w+)"
    ]

    for pattern in current_education_indicators:
        match = re.search(pattern, normalized_text)
        if match:
            stated_level = match.group(1)
            for degree_pattern, (degree_name, level) in degree_mapping.items():
                if re.search(r'\b' + degree_pattern + r'\b', stated_level):
                    current_level = level
                    current_degree_name = degree_name
                    break
            if current_level is not None:
                break

    if current_level is not None:
        return current_degree_name

    found_degrees = []
    for degree_pattern, (degree_name, level) in degree_mapping.items():
        if re.search(r'\b' + degree_pattern + r'\b', normalized_text):
            found_degrees.append((level, degree_name, degree_pattern))

    if found_degrees:
        in_progress_indicators = [
            r"en\s+cours\s+d['e]\s*(\w+)",
            r"je\s+prépare\s+un[e]?\s+(\w+)",
            r"formation\s+non\s+terminée",
            r"diplôme\s+non\s+obtenu",
            r"étudiant\s+en\s+(\w+)",
            r"n['e]\s+pas\s+terminé",
            # Patterns en anglais
            r"currently\s+studying\s+(\w+)",
            r"in\s+progress\s+(\w+)",
            r"pursuing\s+a\s+(\w+)",
            r"working\s+towards\s+a\s+(\w+)",
            r"student\s+in\s+(\w+)",
            r"not\s+completed\s+yet"
        ]

        in_progress_degrees = []
        for pattern in in_progress_indicators:
            matches = re.finditer(pattern, normalized_text)
            for match in matches:
                if match.groups():
                    degree_mentioned = match.group(1)
                    for degree_pattern, (degree_name, level) in degree_mapping.items():
                        if re.search(r'\b' + degree_pattern + r'\b', degree_mentioned):
                            in_progress_degrees.append((level, degree_name, degree_pattern))

        if in_progress_degrees:
            for level, degree_name, pattern in in_progress_degrees:
                found_degrees = [(l, dn, p) for l, dn, p in found_degrees if p != pattern]

        found_degrees.sort(reverse=True, key=lambda x: x[0])

        if found_degrees:
            return found_degrees[0][1]

    years_of_study_pattern = r"(\d+)\s*(ans|years?)\s*(?:d['e]\s*(?:formation|études)?)?"
    years_match = re.search(years_of_study_pattern, normalized_text)
    if years_match:
        years = int(years_match.group(1))
        if years >= 8:
            return "Doctorat/Bac+8"
        elif years == 7:
            return "Bac+7"
        elif years == 6:
            return "Bac+6"
        elif years == 5:
            return "Bac+5"
        elif years == 4:
            return "Bac+4"
        elif years == 3:
            return "Licence/Bac+3"
        elif years == 2:
            return "Bac+2"
        else:
            return "Baccalauréat/Bac"

    return None


def extract_skills(cv_text):
    """
    Extrait les compétences de manière flexible
    - Recherche les mots 'compétence', 'compétences', 'compétence technique'
    - S'arrête à la rencontre de mots-clés de section suivante
    """
    if not cv_text or not isinstance(cv_text, str):
        return []

    # Normaliser le texte
    cv_text = cv_text.lower()

    # Mots-clés pour trouver la section des compétences
    skill_start_patterns = [
        r'compétence[s]*\s*[:]*\s*technique[s]*',
        r'compétence[s]*\s*[:]*',
        r'compétence[s]*\s*technique[s]*\s*:',
        r'skill[s]'
    ]

    # Liste étendue des mots-clés pour arrêter l'extraction
    stop_keywords = [
        # Sections administratives et personnelles
        'formation', 'éducation', 'education', 'expérience', 'experience',
        'formation académique', 'études', 'diplôme', 'certification',
        'projet académique', 'projets académiques', 'projet de fin d\'études', 'pfe',
        'vie associative', 'langue', 'competence morale',

        # Sections professionnelles
        'emploi', 'poste', 'position', 'stage', 'alternance',
        'missions', 'responsabilités', 'réalisations',

        # Informations personnelles
        'coordonnées', 'contact', 'adresse', 'téléphone', 'email',
        'profil', 'objectif professionnel', 'motivation',

        # Développement personnel
        'centres d\'intérêt', 'loisirs', 'soft skills', 'compétences transversales',
        'compétences comportementales', 'qualités',

        # Autres sections
        'références', 'recommandations', 'parcours', 'historique',
        'activités', 'réalisations personnelles', 'distinctions',

        # Termes génériques
        'info', 'informations', 'détails', 'autre', 'autres'
    ]

    # Trouver l'index de départ des compétences
    start_match = None
    start_index = -1
    for pattern in skill_start_patterns:
        match = re.search(pattern, cv_text, re.IGNORECASE)
        if match:
            start_match = match
            start_index = match.end()
            break

    if start_index == -1:
        return []

    # Extraire le texte à partir de l'index de départ
    extracted_text = cv_text[start_index:]

    # Chercher le premier mot-clé d'arrêt
    stop_index = len(extracted_text)
    for keyword in stop_keywords:
        keyword_match = re.search(rf'\b{keyword}\b', extracted_text, re.IGNORECASE)
        if keyword_match:
            stop_index = min(stop_index, keyword_match.start())

    # Limiter le texte jusqu'au premier mot-clé d'arrêt
    skills_text = extracted_text[:stop_index]

    # Séparateurs pour extraire les compétences
    separators = [',', ';', '/', '•', '-', '\n']

    # Extraire les compétences
    skills = []
    for sep in separators:
        skill_list = [s.strip() for s in skills_text.split(sep)]

        # Filtrer les compétences
        filtered_skills = [
            skill for skill in skill_list
            if (skill
                and len(skill) > 2
                and not skill.isdigit()
                and not any(stop_keyword in skill.lower() for stop_keyword in stop_keywords)
                )
        ]

        skills.extend(filtered_skills)

    # Supprimer les doublons et retourner
    return list(dict.fromkeys(skills))


def extract_name_from_cv(cv_text):
    """
    Extrait le nom du candidat du texte du CV avec des méthodes avancées.
    """
    if not cv_text:
        return None

    # Nettoyer le texte pour l'analyse
    cv_text = cv_text.strip()
    lines = [l.strip() for l in cv_text.split('\n') if l.strip()]

    # Liste de mots à ignorer dans les noms
    ignore_words = ["CV", "CURRICULUM", "VITAE", "RESUME", "PROFIL", "PROFILE",
                    "TÉLÉPHONE", "EMAIL", "ADRESSE", "COMPÉTENCES", "SKILLS"]

    # MÉTHODE 1: Recherche dans les premières lignes du CV
    for i, line in enumerate(lines[:10]):  # Examiner les 10 premières lignes
        # Un nom est généralement court et en haut du CV
        words = line.split()
        if 1 <= len(words) <= 4:  # Un nom a généralement entre 1 et 4 mots
            # Vérifier si tous les mots commencent par une majuscule
            if all(word[0].isupper() for word in words if word and word[0].isalpha()):
                # Ignorer les lignes qui contiennent des mots-clés
                if not any(keyword.upper() in line.upper() for keyword in ignore_words):
                    # S'assurer que la ligne ne contient pas de caractères spéciaux excessifs
                    if len(re.findall(r'[^\w\s\'-]', line)) <= 1:
                        return line

    # MÉTHODE 2: Recherche de patterns courants pour les noms
    name_patterns = [
        # Prénom NOM (en France souvent le nom est en majuscules)
        r'\b([A-Z][a-zéèêëàâäôöùûüïî]+)\s+([A-ZÉÈÊËÀÂÄÔÖÙÛÜÏÎ]+)\b',
        # NOM Prénom
        r'\b([A-ZÉÈÊËÀÂÄÔÖÙÛÜÏÎ]+)\s+([A-Z][a-zéèêëàâäôöùûüïî]+)\b',
        # Prénom Nom (première lettre en majuscule pour chaque mot)
        r'\b([A-Z][a-zéèêëàâäôöùûüïî]+)\s+([A-Z][a-zéèêëàâäôöùûüïî]+)\b',
        # NOM PRÉNOM (tout en majuscules)
        r'\b([A-ZÉÈÊËÀÂÄÔÖÙÛÜÏÎ]{2,})\s+([A-ZÉÈÊËÀÂÄÔÖÙÛÜÏÎ]{2,})\b'
    ]

    for pattern in name_patterns:
        matches = re.findall(pattern, cv_text)
        if matches:
            # Vérifier chaque match pour éviter les fausses détections
            for match in matches:
                full_name = ' '.join(match)
                # Ignorer les matches qui contiennent des mots-clés
                if not any(keyword.upper() in full_name.upper() for keyword in ignore_words):
                    return full_name

    # MÉTHODE 3: Examiner les lignes après des déclencheurs spécifiques
    triggers = ["nom:", "name:", "je suis", "i am", "candidat:"]
    lower_cv = cv_text.lower()

    for trigger in triggers:
        if trigger in lower_cv:
            pos = lower_cv.find(trigger) + len(trigger)
            potential_name = cv_text[pos:pos + 50].strip().split('\n')[0].strip()
            # Nettoyer le résultat
            potential_name = re.sub(r'^\s*[:-]\s*', '', potential_name)
            words = potential_name.split()
            if 1 <= len(words) <= 4:
                return potential_name

    return None


def extract_language(cv_text):
    if not cv_text or not isinstance(cv_text, str):
        return []

    cv_text = cv_text.replace('\r', '\n')
    text = ' '.join(cv_text.lower().split())

    languages = {
        "français": ["français", "french", "francais"],
        "anglais": ["anglais", "english", "ingles"],
        "allemand": ["allemand", "german", "deutsch"],
        "espagnol": ["espagnol", "spanish", "español", "espanol"],
        "italien": ["italien", "italian", "italiano"],
        "arabe": ["arabe", "arabic", "arab"],  # ajouté "arab"
        "chinois": ["chinois", "chinese", "mandarin"],
        "russe": ["russe", "russian"],
        "portugais": ["portugais", "portuguese"],
        "japonais": ["japonais", "japanese"],
        "néerlandais": ["néerlandais", "dutch", "hollandais"],
    }

    levels = {
        "Natif": ["natif", "native", "langue maternelle", "mother tongue"],
        "Bilingue": ["bilingue", "bilingual"],
        "Courant": ["courant", "fluent", "fluide", "aisance", "couramment"],
        "Avancé": ["avancé", "advanced", "c1", "c2"],
        "Intermédiaire": ["intermédiaire", "intermediate", "moyen", "b1", "b2"],
        "Débutant": ["débutant", "beginner", "basic", "basique", "notions", "a1", "a2"],
    }

    # Reverse map pour chercher rapidement les niveaux
    level_reverse_map = {}
    for std_level, keywords in levels.items():
        for word in keywords:
            level_reverse_map[word] = std_level

    results = []

    # Générer les combinaisons niveau-langue et langue-niveau
    for lang_key, lang_variants in languages.items():
        for variant in lang_variants:
            found = False
            for level_word, std_level in level_reverse_map.items():
                pattern1 = r'\b' + re.escape(level_word) + r'\b.{0,10}\b' + re.escape(variant) + r'\b'
                pattern2 = r'\b' + re.escape(variant) + r'\b.{0,10}\b' + re.escape(level_word) + r'\b'
                if re.search(pattern1, text) or re.search(pattern2, text):
                    results.append({
                        "language": lang_key.capitalize(),
                        "level": std_level
                    })
                    found = True
                    break
            # Si on a trouvé la langue avec son niveau, on arrête ici
            if found:
                break

    # Ajouter les langues sans niveau précisé
    for lang_key, lang_variants in languages.items():
        for variant in lang_variants:
            if any(r["language"] == lang_key.capitalize() for r in results):
                continue
            if re.search(r'\b' + re.escape(variant) + r'\b', text):
                results.append({
                    "language": lang_key.capitalize(),
                    "level": "Niveau non précisé"
                })
                break

    return results


def extract_cv_info(cv_text, nom_formulaire=None):
    result = {
        "Nom": None,
        "phone": None,
        "email": None,
        "education": None,
        "experience_years": None,
        "location": None,
        "skills": None,
        "languages": None  # Add this new field
    }

    if not cv_text or not isinstance(cv_text, str):
        logger.warning("Texte de CV invalide fourni")
        return result

    cv_text = clean_text(cv_text)

    # Utiliser le nom du formulaire en priorité s'il est valide
    if nom_formulaire and nom_formulaire.strip() and nom_formulaire != "aa":
        result["Nom"] = nom_formulaire
    else:
        # Extraire le nom du CV avec notre méthode de base
        # (sera complété par les méthodes plus avancées dans process_cv)
        name_pattern = r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})'
        name_match = re.search(name_pattern, cv_text)
        if name_match:
            result["Nom"] = name_match.group(1)

    result["phone"] = extract_phone(cv_text)
    result["skills"] = extract_skills(cv_text)
    result["languages"] = extract_language(cv_text)  # Add this new line

    email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
    email_matches = re.findall(email_pattern, cv_text)
    if email_matches:
        result["email"] = email_matches[0].lower()
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', result["email"]):
            result["email"] = re.sub(r'[^\w\.-@]', '', result["email"])

    result["location"] = extract_location(cv_text)
    result["education"] = extract_education_level(cv_text)
    result["experience_years"] = extract_experience_years2(cv_text)

    return result


def process_cv(cv_file, file_type='pdf', candidate_id=None):
    cv_text = ""
    nom_candidat = None

    try:
        # 1. PRIORITÉ 1: Récupérer le nom depuis l'objet candidat Odoo
        if candidate_id:
            try:
                candidate = request.env['hr.applicant'].browse(candidate_id)
                if candidate and candidate.exists() and candidate.name and candidate.name.strip() and candidate.name != "aa":
                    nom_candidat = candidate.name.strip()
                    logger.info(f"Nom récupéré depuis Odoo (ID {candidate_id}): {nom_candidat}")
            except Exception as e:
                logger.error(f"Erreur lors de la récupération du candidat Odoo: {str(e)}")

        # Nettoyer et extraire l'extension si le type contient un slash (ex: "image/png")
        file_type = file_type.strip()
        if '/' in file_type:
            file_type = file_type.split('/')[-1].lower()
        logger.info(f"Type de fichier normalisé: {file_type}")

        if file_type == 'pdf':
            cv_text = extract_pdf_text(cv_file)

        elif file_type in ['docx', 'doc']:
            cv_text = extract_docx_text(cv_file)

        elif file_type in ['jpg', 'jpeg', 'png']:
            try:
                image = Image.open(cv_file)
                cv_text = pytesseract.image_to_string(image, lang='fra')
            except Exception as e:
                logger.error(f"OCR error: {e}")
                cv_text = ""
        else:
            # Si le type ne correspond à aucun attendu, lever une exception
            raise ValueError(f"Format de fichier non supporté. Utilisez 'pdf', 'docx' ou des images (jpg/png), obtenu: {file_type}")

        logger.info(f"Texte extrait (50 premiers caractères): {cv_text[:50].replace('\n', ' ')}")
        # Extraire les informations du CV
        cv_info = extract_cv_info(cv_text)

        # 3. Extraction du nom depuis le contenu du CV si nécessaire
        if not nom_candidat or nom_candidat == "aa":
            try:
                extracted_name = extract_name_from_cv(cv_text)
                if extracted_name and extracted_name.strip() and extracted_name != "aa":
                    nom_candidat = extracted_name.strip()
                    logger.info(f"Nom extrait du contenu du CV: {nom_candidat}")
            except Exception as e:
                logger.error(f"Erreur lors de l'extraction du nom depuis le CV: {str(e)}")

        # 4. Extraction du nom depuis le nom du fichier si toujours absent
        if not nom_candidat or nom_candidat == "aa":
            try:
                filename = os.path.basename(cv_file)
                patterns = [
                    r'^(?:CV[_\s-]*)?([A-Za-z\s\'-]+?)(?:[\s_-]*CV)?\.',  # Exemple: CV_Nom.pdf ou Nom_CV.pdf
                    r'([A-Za-z\s\'-]+?)[\s_-]+(?:resume|cv|curriculum)',      # Exemple: Nom_resume.pdf
                    r'([A-Za-z\s\'-]{3,30})\.'                                # Exemple: Nom.pdf (min 3 chars)
                ]
                for pattern in patterns:
                    name_match = re.search(pattern, filename, re.IGNORECASE)
                    if name_match:
                        potential_name = name_match.group(1).strip()
                        if potential_name and len(potential_name) > 2 and potential_name.lower() != "aa":
                            nom_candidat = potential_name
                            logger.info(f"Nom extrait du nom du fichier: {nom_candidat}")
                            break
            except Exception as e:
                logger.error(f"Erreur lors de l'extraction du nom depuis le fichier: {str(e)}")

        # 5. Appliquer le nom récupéré ou extraire celui déjà présent dans cv_info
        if nom_candidat and nom_candidat != "aa":
            cv_info["Nom"] = nom_candidat
        elif cv_info.get("Nom") and cv_info["Nom"] != "aa" and cv_info["Nom"] != "Candidat Sans Nom":
            logger.info(f"Utilisation du nom déjà extrait: {cv_info['Nom']}")
        else:
            cv_info["Nom"] = "Candidat Sans Nom"
            logger.warning("Impossible de déterminer le nom du candidat après toutes les tentatives")

        # Conversion des années d'expérience
        if cv_info.get("experience_years") and not isinstance(cv_info["experience_years"], (int, float)):
            try:
                cv_info["experience_years"] = float(str(cv_info["experience_years"]).replace(',', '.'))
            except ValueError:
                cv_info["experience_years"] = 0

        logger.info(f"Informations extraites du CV: {cv_info}")
        return pd.DataFrame([cv_info])

    except Exception as e:
        logger.error(f"Erreur lors du traitement du CV: {str(e)}")
        logger.error(traceback.format_exc())
        return pd.DataFrame([{
            "Nom": nom_candidat if nom_candidat and nom_candidat != "aa" else "Candidat Sans Nom",
            "phone": "",
            "email": "",
            "education": "",
            "experience_years": "",
            "location": "",
            "skills": [],
            "languages": ""
        }])
