
import tempfile
import logging
from datetime import datetime

import docx
from PIL import Image
import pytesseract
import pdfplumber

import spacy



_logger = logging.getLogger(__name__)
from odoo.http import request

import os
import logging
import traceback

# Configuration du logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Configuration du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Charger le modèle spaCy en français
# Disable unused pipeline components
nlp = spacy.load("fr_core_news_sm")

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
    """
    Extract location information from CV text using advanced pattern matching.
    Returns a string containing the location or None if no location is found.
    """
    if not cv_text or not isinstance(cv_text, str):
        return None

    # List of countries and major cities (deduplicated)
    countries = [
        "France", "Germany", "Allemagne", "Tunisia", "Tunisie", "Morocco", "Maroc",
        "Algeria", "Algérie", "United States", "USA", "US", "États-Unis", "Canada", "Belgium",
        "Belgique", "Switzerland", "Suisse", "Italy", "Italie", "Spain", "Espagne", "UK",
        "United Kingdom", "Royaume-Uni", "Netherlands", "Pays-Bas", "Luxembourg", "Portugal",
        "Ireland", "Irlande", "Sweden", "Suède", "Norway", "Norvège", "Denmark", "Danemark",
        "Finland", "Finlande", "Greece", "Grèce", "Austria", "Autriche", "Poland", "Pologne",
        "Czech Republic", "République Tchèque", "Japan", "Japon", "China", "Chine", "Australia",
        "Australie", "New Zealand", "Nouvelle-Zélande", "Brazil", "Brésil", "Mexico", "Mexique",
        "Argentina", "Argentine", "Chile", "Chili", "India", "Inde", "Russia", "Russie"
    ]

    major_cities = list(set([
        "Paris", "London", "Londres", "Berlin", "Madrid", "Rome", "Roma", "Brussels", "Bruxelles",
        "Amsterdam", "Vienna", "Vienne", "Zurich", "Geneva", "Genève", "Milan", "Milano",
        "Barcelona", "Barcelone", "Lisbon", "Lisbonne", "Dublin", "Stockholm", "Oslo", "Copenhagen",
        "Copenhague", "Helsinki", "Athens", "Athènes", "Warsaw", "Varsovie", "Prague", "Tokyo",
        "Beijing", "Pékin", "Shanghai", "Sydney", "Melbourne", "Auckland", "São Paulo",
        "Mexico City", "Buenos Aires", "Santiago", "Mumbai", "Delhi", "Moscow", "Moscou",
        "New York", "Los Angeles", "Chicago", "Toronto", "Montreal", "Montréal", "Vancouver",
        "Munich", "München", "Frankfurt", "Hamburg", "Lyon", "Marseille", "Bordeaux",
        "Toulouse", "Lille", "Nice", "Nantes", "Strasbourg", "Montpellier", "Rennes", "Reims",
        "Toulon", "Grenoble", "Dijon", "Tunis", "Sfax", "Sousse", "Casablanca", "Rabat",
        "Marrakech", "Alger", "Oran", "Luxembourg", "Dakar", "Abidjan", "Bamako", "Yaoundé", "Douala"
    ]))

    # Build pattern from sorted locations
    locations = sorted(set(countries + major_cities), key=len, reverse=True)
    locations_pattern = "|".join(map(re.escape, locations))

    location_patterns = [
        r'([A-Z][a-zÀ-ÿ]+(?:[\s-][A-Z][a-zÀ-ÿ]+)*)\s*,\s*(' + locations_pattern + r')',
        r'([A-Z][a-zÀ-ÿ]+(?:[\s-][A-Z][a-zÀ-ÿ]+)*)\s*-\s*(' + locations_pattern + r')',
        r'(?:^|\(|\n)\s*(' + locations_pattern + r')',
        r'(?:Location|Address|Adresse|Localisation|Based in|Located in|Living in|Lieu|Ville)[\s:]*([A-Z][a-zÀ-ÿ]+(?:[\s,.-][A-Z][a-zÀ-ÿ]+)*)',
        r'(?:Born in|Native of|Originaire de|De)\s+([A-Z][a-zÀ-ÿ]+(?:[\s-][A-Z][a-zÀ-ÿ]+)*)',
        r'(Remote|Télétravail|Work from home|Home office|Hybrid|Hybride)[\s-]*([A-Z][a-zÀ-ÿ]*(?:[\s-][A-Z][a-zÀ-ÿ]+)*)?',
        r'\b(' + locations_pattern + r')\b'
    ]

    for pattern in location_patterns:
        matches = re.findall(pattern, cv_text, re.IGNORECASE)
        if matches:
            match = matches[0]
            if isinstance(match, tuple):
                parts = [p.strip() for p in match if p.strip()]
                if parts:
                    return ", ".join(parts)
            elif isinstance(match, str):
                return match.strip()

    # Fallback: postal code formats
    postal_code_patterns = [
        r'([A-Z][a-zÀ-ÿ]+(?:[\s-][A-Z][a-zÀ-ÿ]+)*)\s+\d{5}',  # City + 5-digit postal code
        r'([A-Z][a-zÀ-ÿ]+(?:[\s-][A-Z][a-zÀ-ÿ]+)*)\s+[A-Z]\d[A-Z]\s*\d[A-Z]\d',  # Canada
        r'([A-Z][a-zÀ-ÿ]+(?:[\s-][A-Z][a-zÀ-ÿ]+)*)\s+[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}',  # UK
    ]

    for pattern in postal_code_patterns:
        postal_matches = re.findall(pattern, cv_text, re.IGNORECASE)
        if postal_matches:
            return postal_matches[0].strip()

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
        'projet académique', 'vie associative', 'langue', 'competence morale',

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
        # 1. PRIORITÉ 1: Récupérer le nom directement depuis l'objet candidat Odoo
        if candidate_id:
            try:
                candidate = request.env['hr.applicant'].browse(candidate_id)
                if candidate and candidate.exists() and candidate.name and candidate.name.strip() and candidate.name != "aa":
                    nom_candidat = candidate.name.strip()
                    logger.info(f"Nom récupéré depuis Odoo (ID {candidate_id}): {nom_candidat}")
            except Exception as e:
                logger.error(f"Erreur lors de la récupération du candidat Odoo: {str(e)}")

        # 2. Extraire le texte du CV selon le type de fichier
        if file_type.lower() == 'pdf':
            cv_text = extract_pdf_text(cv_file)
        elif file_type.lower() in ['docx', 'doc']:
            cv_text = extract_docx_text(cv_file)
        elif file_type.lower() in ['jpg', 'jpeg', 'png']:
            cv_text = extract_ocr_text(cv_file)
        else:
            raise ValueError("Format de fichier non supporté. Utilisez 'pdf', 'docx' ou des images.")

        logger.info(f"Texte extrait (50 premiers caractères): {cv_text[:50]}")

        # Extraire les informations de base du CV
        cv_info = extract_cv_info(cv_text)

        # 3. Si le nom n'est pas encore défini, essayer de l'extraire du contenu du CV
        if not nom_candidat or nom_candidat == "aa":
            try:
                extracted_name = extract_name_from_cv(cv_text)
                if extracted_name and extracted_name.strip() and extracted_name != "aa":
                    nom_candidat = extracted_name.strip()
                    logger.info(f"Nom extrait du contenu du CV: {nom_candidat}")
            except Exception as e:
                logger.error(f"Erreur lors de l'extraction du nom depuis le CV: {str(e)}")

        # 4. Si toujours pas de nom, essayer d'extraire du nom du fichier
        if not nom_candidat or nom_candidat == "aa":
            try:
                filename = os.path.basename(cv_file)
                # Plusieurs patterns pour extraire un nom du fichier
                patterns = [
                    r'^(?:CV[_\s-]*)?([A-Za-z\s\'-]+?)(?:[\s_-]*CV)?\.',  # CV_Nom.pdf ou Nom_CV.pdf
                    r'([A-Za-z\s\'-]+?)[\s_-]+(?:resume|cv|curriculum)',  # Nom resume.pdf
                    r'([A-Za-z\s\'-]{3,30})\.'  # Simplement Nom.pdf (min 3 chars)
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

        # 5. Appliquer le nom trouvé ou conserver celui qui était dans cv_info s'il est valide
        if nom_candidat and nom_candidat != "aa":
            cv_info["Nom"] = nom_candidat
        elif cv_info.get("Nom") and cv_info["Nom"] != "aa" and cv_info["Nom"] != "Candidat Sans Nom":
            # On garde le nom déjà extrait par extract_cv_info si valide
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

        # Retourne le DataFrame avec les informations extraites
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


import re
import json
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tensorflow.keras.models import Sequential,load_model
from tensorflow.keras.layers import Dense, Dropout
import spacy
from sentence_transformers import SentenceTransformer
import logging

# Configuration du logging
_logger = logging.getLogger(__name__)

# Charger les modèles NLP
try:
    nlp = spacy.load("fr_core_news_md")  # Modèle français pour l'analyse linguistique
    sentence_model = SentenceTransformer('distiluse-base-multilingual-cased-v1')  # Pour les embeddings de phrases
except Exception as e:
    _logger.error(f"Erreur lors du chargement des modèles NLP: {e}")

    # Créer des fonctions simplifiées en cas d'échec de chargement des modèles

    nlp = None
    sentence_model = None

# Charger le modèle depuis le répertoire "models"
try:
    experience_model = load_model("/home/jbilisamar/pfe/odoo18.0/odoo-docker/custom_addons/recruitement_ai/models/experience_model.keras")
except Exception as e:
    _logger.error(f"Erreur de chargement du modèle : {e}")
    experience_model = None

def calculate_experience_score(cv_experience, required_experience):
    if not cv_experience or not required_experience or experience_model is None:
        return 0

    try:
        cv_exp = float(cv_experience)
        req_exp = float(required_experience)

        features = np.array([[cv_exp, req_exp, cv_exp - req_exp,
                              cv_exp / max(req_exp, 1),
                              min(cv_exp, req_exp) / max(cv_exp, req_exp, 1)]])

        prediction = experience_model.predict(features, verbose=0)
        score = float(prediction[0][0])
        return max(min(score, 1.0), 0.0)

    except Exception as e:
        _logger.error(f"Erreur lors du calcul : {e}")
        return 0


# Charger le modèle d'éducation
try:
    education_model = load_model(
        "/home/jbilisamar/pfe/odoo18.0/odoo-docker/custom_addons/recruitement_ai/models/education_model.keras")
except Exception as e:
    _logger.error(f"Erreur de chargement du modèle : {e}")
    education_model = None
education_model = None  # À remplacer par le chargement réel de ton modèle

# Dictionnaire global des niveaux d'éducation
education_levels = {
    'autre': 1,
    'baccalauréat': 2, 'bac': 2,
    'bac+2': 3, 'dut': 3, 'bts': 3, 'deug': 3,
    'licence': 4, 'bac+3': 4, 'bac_plus_3': 4,
    'maîtrise': 5, 'bac+4': 5,
    'master': 6, 'ingénieur': 6, 'ingenierie': 6, 'bac+5': 6, 'mba': 6,
    'doctorat': 7, 'phd': 7, 'bac+8': 7
}
import re
import numpy as np
from tensorflow.keras.models import load_model
import logging

# Configuration du logger
_logger = logging.getLogger(__name__)

# Charger le modèle d'éducation
try:
    education_model = load_model(
        "/home/jbilisamar/pfe/odoo18.0/odoo-docker/custom_addons/recruitement_ai/models/education_model.keras")
except Exception as e:
    _logger.error(f"Erreur de chargement du modèle : {e}")
    education_model = None

# Dictionnaire global des niveaux d'éducation
education_levels = {
    'autre': 1,
    'baccalauréat': 2, 'bac': 2,
    'bac+2': 3, 'dut': 3, 'bts': 3, 'deug': 3,
    'licence': 4, 'bac+3': 4, 'bac_plus_3': 4,
    'maîtrise': 5, 'bac+4': 5,
    'master': 6, 'ingénieur': 6, 'ingenierie': 6, 'bac+5': 6, 'mba': 6,
    'doctorat': 7, 'phd': 7, 'bac+8': 7
}


def map_education_level(text):
    """Convertit un texte en niveau numérique d'éducation."""
    if not text:
        return 0

    text = text.strip().lower()

    # Chercher un niveau d'éducation de type "bac+2", "bac+3", "bac+5", etc.
    match = re.search(r'(bac\+[\d]+)', text)
    if match:
        level = match.group(1)  # Extraire le niveau (ex: 'bac+3')
        return education_levels.get(level, 0)

    # Correspondance avec des termes comme "master", "ingenierie", "doctorat"
    if 'master' in text:
        return education_levels.get('master', 6)
    elif 'ingenierie' in text or 'ingénieur' in text:
        return education_levels.get('ingenierie', 6)
    elif 'doctorat' in text or 'phd' in text:
        return education_levels.get('doctorat', 7)

    # Retourne 0 si aucun niveau reconnu
    return 0


def calculate_education_score(cv_education, required_education):
    """Calcule un score d'adéquation éducation entre le CV et le poste à l'aide d'un modèle."""
    if not cv_education or not required_education or education_model is None:
        _logger.error("Les niveaux d'éducation ne peuvent être None")
        return 0

    try:
        # Mapping des niveaux
        cv_edu_level = map_education_level(cv_education)
        req_edu_level = map_education_level(required_education)

        if cv_edu_level == 0 or req_edu_level == 0:
            _logger.warning(f"Niveau d'éducation non reconnu: CV='{cv_education}', Requis='{required_education}'")
            # 0.1 si niveau CV inconnu, 0.5 si uniquement requis inconnu
            return 0.1 if cv_edu_level == 0 else 0.5

        # Construction des features
        diff = cv_edu_level - req_edu_level
        ratio = cv_edu_level / max(req_edu_level, 1)
        rel = min(cv_edu_level, req_edu_level) / max(cv_edu_level, req_edu_level)

        features = np.array([[cv_edu_level, req_edu_level, diff, ratio, rel]])

        # Prédiction
        prediction = education_model.predict(features, verbose=0)
        score = float(prediction[0][0])

        # Nettoyage du score
        return max(min(score, 1.0), 0.0)

    except Exception as e:
        _logger.error(f"Erreur lors du calcul du score d'éducation : {e}")
        return 0




def calculate_skills_match(cv_skills, job_skills):
    """
    Utilise des embeddings de phrases et des techniques d'IA avancées pour
    évaluer la correspondance sémantique entre les compétences du CV et celles
    requises pour le poste.
    """
    if not cv_skills or not job_skills or len(job_skills) == 0:
        return 0.0

    try:
        # Assurer que les compétences sont sous forme de liste
        if isinstance(cv_skills, str):
            cv_skills = [cv_skills]
        elif not isinstance(cv_skills, list):
            cv_skills = [str(cv_skills)]

        if isinstance(job_skills, str):
            job_skills = [job_skills]
        elif not isinstance(job_skills, list):
            job_skills = [str(job_skills)]

        # Nettoyer et préparer les données
        cv_skills_clean = [re.sub(r'\W+', ' ', skill).lower().strip() for skill in cv_skills]
        job_skills_clean = [re.sub(r'\W+', ' ', skill).lower().strip() for skill in job_skills]

        # 1. Approche basée sur les embeddings de phrases (plus sophistiquée)
        if sentence_model:
            cv_skills_text = ' '.join(cv_skills_clean)
            job_skills_text = ' '.join(job_skills_clean)

            # Calculer les embeddings pour chaque compétence individuelle
            cv_skills_embeddings = sentence_model.encode(cv_skills_clean)
            job_skills_embeddings = sentence_model.encode(job_skills_clean)

            # Calculer la similarité entre chaque paire de compétences
            skill_match_scores = []
            for job_emb in job_skills_embeddings:
                # Trouver la meilleure correspondance dans le CV pour cette compétence requise
                similarities = cosine_similarity([job_emb], cv_skills_embeddings)[0]
                best_match = np.max(similarities) if len(similarities) > 0 else 0
                skill_match_scores.append(best_match)

            # Calculer le score moyen de correspondance des compétences
            semantic_score = np.mean(skill_match_scores) if skill_match_scores else 0.0

            # Calculer également un score global pour l'ensemble des compétences
            cv_full_embedding = sentence_model.encode([cv_skills_text])[0]
            job_full_embedding = sentence_model.encode([job_skills_text])[0]
            overall_similarity = cosine_similarity([cv_full_embedding], [job_full_embedding])[0][0]

            # Combiner les scores
            embedding_score = (semantic_score * 0.7) + (overall_similarity * 0.3)
        else:
            # 2. Repli sur TF-IDF si les modèles d'embeddings ne sont pas disponibles
            cv_skills_text = ' '.join(cv_skills_clean)
            job_skills_text = ' '.join(job_skills_clean)

            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform([cv_skills_text, job_skills_text])
            embedding_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]

        # 3. Calcul de correspondance directe (exact match)
        matched_skills = 0
        total_required_skills = len(job_skills)

        for job_skill in job_skills_clean:
            if any(job_skill in cv_skill for cv_skill in cv_skills_clean):
                matched_skills += 1

        direct_match_score = matched_skills / total_required_skills if total_required_skills > 0 else 0

        # 4. Modèle de machine learning pour prédire l'adéquation des compétences
        # Dans un système réel, on utiliserait un modèle pré-entraîné
        # Ici, nous simulons un score basé sur les caractéristiques calculées

        features = np.array([[
            embedding_score,
            direct_match_score,
            len(cv_skills) / max(len(job_skills), 1),
            matched_skills,
            total_required_skills - matched_skills
        ]])

        # Combinaison pondérée des différentes approches
        final_score = (embedding_score * 0.6) + (direct_match_score * 0.4)

        return min(max(final_score, 0.0), 1.0)  # Normaliser entre 0 et 1

    except Exception as e:
        _logger.error(f"Erreur lors de l'évaluation des compétences avec IA: {e}")
        return 0.0



def calculate_language_score(cv_languages, required_language):
    """
    Évalue la correspondance linguistique avec analyse contextuelle et niveaux de maîtrise.
    """
    if not cv_languages or not required_language:
        return 0.5  # Score neutre si l'information est manquante

    try:
        # Niveau de compétence linguistique et leur valeur numérique
        language_levels = {
            'débutant': 0.4,
            'a1': 0.4, 'a2': 0.5,
            'intermédiaire': 0.7,
            'b1': 0.6, 'b2': 0.8,
            'avancé': 0.9,
            'c1': 0.9, 'c2': 1.0,
            'courant': 0.95,
            'bilingue': 1.0,
            'natif': 1.0,
            'langue maternelle': 1.0
        }

        cv_langs = []
        cv_lang_levels = {}

        # Traiter différents formats d'entrée pour les langues du CV
        if isinstance(cv_languages, str):
            try:
                parsed = json.loads(cv_languages.replace("'", '"'))
                if isinstance(parsed, list):
                    for lang_item in parsed:
                        if isinstance(lang_item, dict):
                            if 'language' in lang_item:
                                lang_name = lang_item['language'].lower()
                                cv_langs.append(lang_name)

                                # Extraire le niveau si disponible
                                if 'level' in lang_item:
                                    level = lang_item['level'].lower()
                                    for key, value in language_levels.items():
                                        if key in level:
                                            cv_lang_levels[lang_name] = value
                                            break
                                    if lang_name not in cv_lang_levels:
                                        cv_lang_levels[lang_name] = 0.7  # Niveau par défaut
            except json.JSONDecodeError:
                # Si ce n'est pas un JSON valide, essayer de traiter comme texte
                if nlp:
                    doc = nlp(cv_languages.lower())
                    # Recherche de motifs linguistiques courants (ex: "français: courant")
                    for sent in doc.sents:
                        sent_text = sent.text.lower()
                        # Logique pour extraire langue et niveau à partir du texte
                        for common_lang in ["français", "anglais", "espagnol", "allemand", "italien", "chinois",
                                            "russe"]:
                            if common_lang in sent_text:
                                cv_langs.append(common_lang)
                                # Recherche de niveau
                                for level_key, level_value in language_levels.items():
                                    if level_key in sent_text:
                                        cv_lang_levels[common_lang] = level_value
                                        break
                                if common_lang not in cv_lang_levels:
                                    cv_lang_levels[common_lang] = 0.7  # Niveau par défaut

        elif isinstance(cv_languages, list):
            for lang_item in cv_languages:
                if isinstance(lang_item, dict) and 'language' in lang_item:
                    lang_name = lang_item['language'].lower()
                    cv_langs.append(lang_name)

                    # Extraire le niveau si disponible
                    if 'level' in lang_item:
                        level = lang_item['level'].lower()
                        for key, value in language_levels.items():
                            if key in level:
                                cv_lang_levels[lang_name] = value
                                break
                        if lang_name not in cv_lang_levels:
                            cv_lang_levels[lang_name] = 0.7  # Niveau par défaut
                elif isinstance(lang_item, str):
                    cv_langs.append(lang_item.lower())
                    cv_lang_levels[lang_item.lower()] = 0.7  # Niveau par défaut

        # Traiter la langue requise
        if not cv_langs or not required_language:
            return 0.5

        required_lang_lower = required_language.lower()
        required_level = 0.7  # Niveau par défaut si non spécifié

        # Extraire le niveau requis si spécifié
        for key, value in language_levels.items():
            if key in required_lang_lower:
                required_level = value
                # Nettoyer le nom de la langue des mentions de niveau
                required_lang_lower = required_lang_lower.replace(key, '').strip()
                break

        # Vérifier la correspondance avec prise en compte du niveau
        best_match_score = 0.0
        for lang in cv_langs:
            # Utiliser une similarité sémantique pour les noms de langues
            if nlp and sentence_model:
                lang_similarity = sentence_model.encode([lang, required_lang_lower])
                similarity_score = cosine_similarity([lang_similarity[0]], [lang_similarity[1]])[0][0]

                if similarity_score > 0.8:  # Seuil de similarité élevée
                    # Obtenir le niveau de compétence
                    lang_level = cv_lang_levels.get(lang, 0.7)

                    # Calculer un score basé sur la correspondance de niveau
                    if lang_level >= required_level:
                        level_match = 1.0
                    else:
                        level_match = lang_level / required_level

                    match_score = (similarity_score * 0.3) + (level_match * 0.7)
                    best_match_score = max(best_match_score, match_score)
            else:
                # Approche simplifiée sans NLP
                if required_lang_lower in lang or lang in required_lang_lower:
                    lang_level = cv_lang_levels.get(lang, 0.7)

                    if lang_level >= required_level:
                        best_match_score = 1.0
                    else:
                        best_match_score = lang_level / required_level

        return best_match_score

    except Exception as e:
        _logger.error(f"Erreur lors du calcul du score de langue avec IA: {e}")
        return 0.5





def check_required_criteria(cv_data, job_criteria):
    """
    Vérifie si tous les critères obligatoires sont satisfaits.

    Args:
        cv_data (dict): Données du CV
        job_criteria (dict): Critères du poste

    Returns:
        bool: True si tous les critères obligatoires sont satisfaits, False sinon
    """
    # Vérifier l'expérience (années)
    if job_criteria.get('is_experience_years_required', False):
        cv_exp = float(cv_data.get('experience_years', 0))
        req_exp = float(job_criteria.get('experience_years', 0))
        if cv_exp < req_exp:
            return False

    # Vérifier le niveau d'éducation
    if job_criteria.get('is_education_required', False):
        cv_edu = cv_data.get('education', '').lower()
        req_edu = job_criteria.get('education', '').lower()

        # Hiérarchie des niveaux d'éducation (du plus bas au plus élevé)
        education_levels = {
            'autre': 1,
            'baccalauréat': 2, 'bac': 2,
            'bac+2': 3, 'dut': 3, 'bts': 3, 'deug': 3,
            'licence': 4, 'bac+3': 4, 'bac_plus_3': 4,
            'maîtrise': 5, 'bac+4': 5,
            'master': 6, 'ingénieur': 6, 'bac+5': 6, 'mba': 6,
            'doctorat': 7, 'phd': 7, 'bac+8': 7
        }

        cv_level = 0
        for key, value in education_levels.items():
            if key in cv_edu:
                cv_level = max(cv_level, value)

        req_level = 0
        for key, value in education_levels.items():
            if key in req_edu:
                req_level = max(req_level, value)

        if cv_level < req_level:
            return False

    # Vérifier le lieu si obligatoire
    if job_criteria.get('is_location_required', False):
        cv_location = cv_data.get('location', '').lower()
        job_location = job_criteria.get('location', '').lower()

        if job_location not in cv_location and cv_location not in job_location:
            return False

    # Vérifier les compétences
    if job_criteria.get('is_skills_required', False):
        cv_skills = cv_data.get('skills', [])
        job_skills = job_criteria.get('competences', [])

        # Vérifier les compétences obligatoires
        required_skills = [skill for skill in job_skills if getattr(skill, 'is_required', False)]

        if not all(
                any(req_skill.lower() in cv_skill.lower() for cv_skill in cv_skills) for req_skill in required_skills):
            return False

    # Vérifier les langues obligatoires
    required_languages = [lang for lang in job_criteria.get('language_ids', []) if lang.get('is_required', False)]
    cv_languages = cv_data.get('languages', [])

    for req_lang in required_languages:
        lang_name = req_lang.get('name', '').lower()
        if not any(lang_name in cv_lang.lower() for cv_lang in cv_languages):
            return False

    return True


def get_importance_weights(job_criteria):
    """
    Convertit les niveaux d'importance (étoiles) en poids pour le calcul du score.
    Ajoute également le pourcentage correspondant aux étoiles.
    """
    # Récupérer les niveaux d'importance (1-5 étoiles) avec valeur par défaut
    importance = {
        'experience': {
            'stars': int(job_criteria.get('experience_years_importance', '3')),
            'required': job_criteria.get('is_experience_years_required', False)
        },
        'education': {
            'stars': int(job_criteria.get('education_importance', '3')),
            'required': job_criteria.get('is_education_required', False)
        },
        'skills': {
            'stars': int(job_criteria.get('competences_importance', '3')),
            'required': job_criteria.get('is_skills_required', False)
        },
        'language': {
            'stars': int(job_criteria.get('languages_importance', '3')),
            'required': False  # Géré séparément via les langues individuelles
        }
    }

    # Si des langues individuelles sont marquées comme obligatoires,
    # définir 'language.required' à True
    if job_criteria.get('language_ids'):
        for lang in job_criteria.get('language_ids', []):
            if lang.get('is_required', False):
                importance['language']['required'] = True
                break

    # Calculer la somme des étoiles pour normaliser
    total_stars = sum(item['stars'] for item in importance.values())

    # Normaliser les poids et calculer les pourcentages
    weights = {}
    for key, value in importance.items():
        weights[key] = {
            'weight': value['stars'] / total_stars if total_stars > 0 else 0.25,
            'stars': value['stars'],
            'percentage': (value['stars'] / 5) * 100,  # Conversion en pourcentage
            'required': value['required']
        }

    return weights

def calculate_weighted_score(scores, importance_weights):
    """
    Calcule le score total pondéré en tenant compte de l'importance de chaque critère.

    Args:
        scores (dict): Scores par critère
        importance_weights (dict): Poids d'importance pour chaque critère

    Returns:
        int: Score total (0-100)
    """
    weighted_sum = 0

    for criterion, score in scores.items():
        weight = importance_weights[criterion]['weight']
        weighted_sum += score * weight

    # Convertir en score sur 100
    return int(weighted_sum * 100)

def get_match_quality_label(score):
    """
    Retourne une étiquette qualitative pour le score de correspondance.

    Args:
        score (float): Score entre 0 et 1

    Returns:
        str: Étiquette qualitative
    """
    if score == 0:
        return "Non éligible"
    elif score < 0.4:
        return "Faible"
    elif score < 0.6:
        return "Moyen"
    elif score < 0.8:
        return "Bon"
    elif score < 0.9:
        return "Très bon"
    else:
        return "Excellent"


def identify_critical_missing_skills(cv_skills, job_skills):
    """
    Identifie les compétences critiques qui manquent dans le CV.

    Args:
        cv_skills (list): Compétences du CV
        job_skills (list): Compétences requises pour le poste

    Returns:
        list: Compétences critiques manquantes
    """
    missing_skills = []

    # Normaliser les compétences du CV
    normalized_cv_skills = [skill.lower() for skill in cv_skills]

    for job_skill in job_skills:
        skill_name = job_skill.get('name') if isinstance(job_skill, dict) else job_skill
        is_required = job_skill.get('is_required', False) if isinstance(job_skill, dict) else False
        importance = job_skill.get('importance_level', '3') if isinstance(job_skill, dict) else '3'

        # Vérifier si c'est une compétence critique (obligatoire ou importance élevée)
        is_critical = is_required or importance in ('4', '5')

        if is_critical and not any(skill_name.lower() in cv_skill for cv_skill in normalized_cv_skills):
            missing_skills.append({
                'name': skill_name,
                'is_required': is_required,
                'importance': importance
            })

    return missing_skills


def generate_score_explanations(cv_data, job_criteria, scores):
    """
    Génère des explications textuelles pour les scores de chaque critère.

    Args:
        cv_data (dict): Données du CV
        job_criteria (dict): Critères du poste
        scores (dict): Scores calculés pour chaque critère

    Returns:
        dict: Explications textuelles pour chaque critère
    """
    explanations = {}

    # Explication pour l'expérience
    cv_exp = float(cv_data.get('experience_years', 0))
    req_exp = float(job_criteria.get('experience_years', 0))

    if cv_exp >= req_exp:
        explanations[
            'experience'] = f"Le candidat possède {cv_exp} années d'expérience, ce qui satisfait ou dépasse l'exigence de {req_exp} années."
    else:
        explanations[
            'experience'] = f"Le candidat possède {cv_exp} années d'expérience, ce qui est inférieur à l'exigence de {req_exp} années."

    # Explication pour l'éducation
    cv_edu = cv_data.get('education', '')
    req_edu = job_criteria.get('education', '')

    if scores['education'] >= 0.8:
        explanations[
            'education'] = f"Le niveau d'éducation du candidat ({cv_edu}) correspond très bien aux exigences du poste ({req_edu})."
    elif scores['education'] >= 0.5:
        explanations[
            'education'] = f"Le niveau d'éducation du candidat ({cv_edu}) correspond moyennement aux exigences du poste ({req_edu})."
    else:
        explanations[
            'education'] = f"Le niveau d'éducation du candidat ({cv_edu}) ne correspond pas bien aux exigences du poste ({req_edu})."

    # Explication pour les compétences
    if scores['skills'] >= 0.8:
        explanations['skills'] = "Le candidat possède la plupart des compétences requises pour le poste."
    elif scores['skills'] >= 0.5:
        explanations[
            'skills'] = "Le candidat possède certaines des compétences clés, mais il lui en manque d'autres importantes."
    else:
        explanations['skills'] = "Le candidat ne possède pas suffisamment des compétences requises pour ce poste."

    # Explication pour les langues
    if scores['language'] >= 0.8:
        explanations['language'] = "Les compétences linguistiques du candidat correspondent très bien aux exigences."
    elif scores['language'] >= 0.5:
        explanations[
            'language'] = "Les compétences linguistiques du candidat sont partiellement alignées avec les exigences."
    else:
        explanations['language'] = "Les compétences linguistiques du candidat ne répondent pas aux exigences du poste."

    return explanations


def identify_candidate_strengths(cv_data, job_criteria, scores):
    """
    Identifie les points forts du candidat par rapport aux exigences du poste.

    Args:
        cv_data (dict): Données du CV
        job_criteria (dict): Critères du poste
        scores (dict): Scores calculés pour chaque critère

    Returns:
        list: Points forts du candidat
    """
    strengths = []

    # Points forts basés sur l'expérience
    cv_exp = float(cv_data.get('experience_years', 0))
    req_exp = float(job_criteria.get('experience_years', 0))

    if cv_exp > req_exp * 1.5:
        strengths.append(
            f"Expérience professionnelle exceptionnelle: {cv_exp} années (bien au-delà des {req_exp} années requises)")
    elif cv_exp > req_exp:
        strengths.append(f"Bonne expérience professionnelle: {cv_exp} années (dépasse les {req_exp} années requises)")

    # Points forts basés sur l'éducation
    if scores['education'] > 0.9:
        strengths.append("Formation académique parfaitement adaptée au poste")
    elif scores['education'] > 0.7:
        strengths.append("Solide formation académique correspondant au poste")

    # Points forts basés sur les compétences
    cv_skills = cv_data.get('skills', [])
    job_skills = job_criteria.get('competences', [])

    if isinstance(job_skills, list) and len(job_skills) > 0:
        # Compter combien de compétences du poste sont présentes dans le CV
        matched_skills = 0
        critical_matched = 0

        for skill in job_skills:
            skill_name = skill.get('name', skill) if isinstance(skill, dict) else skill
            importance = skill.get('importance_level', '3') if isinstance(skill, dict) else '3'
            is_critical = importance in ('4', '5')

            if any(skill_name.lower() in cv_skill.lower() for cv_skill in cv_skills):
                matched_skills += 1
                if is_critical:
                    critical_matched += 1

        match_rate = matched_skills / len(job_skills) if len(job_skills) > 0 else 0

        if match_rate > 0.8:
            strengths.append("Excellente maîtrise des compétences techniques requises")
        elif match_rate > 0.6:
            strengths.append("Bonne maîtrise des compétences techniques requises")

        if critical_matched > 0:
            strengths.append(f"Maîtrise de {critical_matched} compétences critiques pour le poste")

    return strengths


def generate_overall_recommendation(score, cv_data, job_criteria):
    """
    Génère une recommandation globale basée sur le score de correspondance.

    Args:
        score (float): Score total de correspondance (0-1)
        cv_data (dict): Données du CV
        job_criteria (dict): Critères du poste

    Returns:
        str: Recommandation globale
    """
    if score == 0:
        return "Ne pas considérer - Critères obligatoires non satisfaits"
    elif score < 0.4:
        return "Ne pas considérer - Faible correspondance avec le profil recherché"
    elif score < 0.6:
        return "Considérer si peu de candidats - Correspondance moyenne"
    elif score < 0.8:
        return "À considérer - Bonne correspondance avec le profil recherché"
    elif score < 0.9:
        return "Fortement recommandé - Très bonne correspondance avec le profil"
    else:
        return "Candidat prioritaire - Excellente correspondance avec le profil"

def evaluate_cv(cv_data, job_criteria, industry_context=None):
    """
    Évaluation enrichie par l'IA d'un CV par rapport aux critères d'un poste.
    Prend en compte les critères obligatoires et l'importance (étoiles).

    Args:
        cv_data (dict): Données extraites du CV
        job_criteria (dict): Critères du poste
        industry_context (str, optional): Contexte de l'industrie pour améliorer l'analyse

    Returns:
        dict: Résultats d'évaluation détaillés avec explications contextuelles
    """
    try:
        # Vérifier d'abord les critères obligatoires
        if not check_required_criteria(cv_data, job_criteria):
            # Si un critère obligatoire n'est pas satisfait, retourner un score de 0
            return {
                'total_score': 0,
                'match_quality': 'Non éligible',
                'explanation': 'Un ou plusieurs critères obligatoires ne sont pas satisfaits.'
            }

        # Calculer les scores individuels avec l'IA
        exp_score = calculate_experience_score(cv_data.get('experience_years', 0),
                                               job_criteria.get('experience_years', 0))
        edu_score = calculate_education_score(cv_data.get('education', 0),
                                              job_criteria.get('education', 0))

        skills_score = calculate_skills_match(cv_data.get('skills', []),
                                              job_criteria.get('competences', []))
        lang_score = calculate_language_score(cv_data.get('languages', []),
                                              job_criteria.get('languages', ''))

        # Récupérer les niveaux d'importance (étoiles) pour chaque critère
        importance_weights = get_importance_weights(job_criteria)

        # Calculer le score total pondéré en tenant compte de l'importance
        total = calculate_weighted_score(
            {
                'experience': exp_score,
                'education': edu_score,
                'skills': skills_score,
                'language': lang_score
            },
            importance_weights
        )

        # Générer des explications pour chaque critère
        explanations = generate_score_explanations(cv_data, job_criteria, {
            'experience': exp_score,
            'education': edu_score,
            'skills': skills_score,
            'language': lang_score
        })

        # Calculer les compétences manquantes critiques
        missing_skills = identify_critical_missing_skills(cv_data.get('skills', []),
                                                          job_criteria.get('competences', []))

        # Identifier les points forts du candidat
        strengths = identify_candidate_strengths(cv_data, job_criteria, {
            'experience': exp_score,
            'education': edu_score,
            'skills': skills_score
        })

        # Retourner les résultats détaillés
        return {
            'experience_score': exp_score,
            'education_score': edu_score,
            'skills_score': skills_score,
            'language_score': lang_score,
            'total_score': total,  # Score directement en nombre entier
            'match_quality': get_match_quality_label(total / 100),  # Convertir en fraction pour l'étiquette
            'detailed_results': {
                'experience': {
                    'cv_value': cv_data.get('experience_years', 0),
                    'required_value': job_criteria.get('experience_years', 0),
                    'score': exp_score,
                    'importance': importance_weights['experience']['stars'],
                    'is_required': importance_weights['experience']['required'],
                    'explanation': explanations.get('experience', '')
                },
                'education': {
                    'cv_value': cv_data.get('education', ''),
                    'required_value': job_criteria.get('education', ''),
                    'score': edu_score,
                    'importance': importance_weights['education']['stars'],
                    'is_required': importance_weights['education']['required'],
                    'explanation': explanations.get('education', '')
                },
                'skills': {
                    'cv_value': cv_data.get('skills', []),
                    'required_value': job_criteria.get('competences', []),
                    'score': skills_score,
                    'importance': importance_weights['skills']['stars'],
                    'is_required': importance_weights['skills']['required'],
                    'explanation': explanations.get('skills', ''),
                    'missing_critical_skills': missing_skills
                },
                'language': {
                    'cv_value': cv_data.get('languages', []),
                    'required_value': job_criteria.get('languages', ''),
                    'score': lang_score,
                    'importance': importance_weights['language']['stars'],
                    'is_required': importance_weights['language']['required'],
                    'explanation': explanations.get('language', '')
                }
            },
            'candidate_strengths': strengths,
            'overall_recommendation': generate_overall_recommendation(total / 100, cv_data, job_criteria)
        }
    except Exception as e:
        _logger.error(f"Erreur lors de l'évaluation du CV avec IA: {e}")
        return {
            'error': str(e),
            'total_score': 0,
            'match_percentage': 0
        }

