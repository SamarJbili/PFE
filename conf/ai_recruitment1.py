# ai_recruitment1.py - Version améliorée

import pandas as pd
import os
import tempfile
import logging
from datetime import datetime
import nltk
from nltk.tokenize import sent_tokenize
from nltk.tokenize import word_tokenize
import re
import os
from bs4 import BeautifulSoup


# Désactiver CUDA pour éviter les erreurs d'importation
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

# Importation conditionnelle de transformers


logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import spacy

    SPACY_AVAILABLE = True
    try:
        nlp = spacy.load("fr_core_news_sm")
        FRENCH_MODEL_AVAILABLE = True
    except IOError:
        logger.warning("French language model not available. Using blank model.")
        FRENCH_MODEL_AVAILABLE = False
        # Use a basic model as fallback
        nlp = spacy.blank("fr")
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning("spaCy not available. Some features will be limited.")

try:
    import PyPDF2

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("PyPDF2 not available. PDF parsing will be limited.")

try:
    import docx

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.warning("python-docx not available. DOCX parsing will be limited.")

try:
    from PIL import Image
    import pytesseract

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("pytesseract or PIL not available. OCR features will be disabled.")


# Fonction pour extraire du texte d'une image (OCR)
def extract_ocr_text(image_file):
    if not OCR_AVAILABLE:
        return "OCR not available"

    try:
        image = Image.open(image_file)
        text = pytesseract.image_to_string(image, lang='fra')
        return text
    except Exception as e:
        logger.error(f"OCR error: {str(e)}")
        return ""


# Fonction pour extraire du texte d'un fichier PDF
import pdfplumber

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

pdf_file = '/home/jbilisamar/Téléchargements/blue professional modern CV resume.pdf'
text = extract_pdf_text(pdf_file)
print(text)


# Fonction pour extraire du texte d'un fichier DOCX
def extract_docx_text(docx_file):
    if not DOCX_AVAILABLE:
        return "DOCX extraction not available"

    try:
        doc = docx.Document(docx_file)
        text = ""
        for para in doc.paragraphs:
            text += para.text + '\n'
        return text
    except Exception as e:
        logger.error(f"DOCX extraction error: {str(e)}")
        return ""


# Fonction pour nettoyer le texte
def clean_text(text):
    """ Nettoyer le texte des espaces et caractères inutiles. """
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


# Fonction améliorée pour extraire le nom du candidat


def split_text_by_keywords(text):
    paragraphs = []
    current_paragraph = ""
    sentences = nltk.sent_tokenize(text)

    for sentence in sentences:
        sentence = clean_text(sentence)
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', sentence, re.IGNORECASE):
                if current_paragraph:
                    paragraphs.append(current_paragraph)
                current_paragraph = sentence
                break
        else:
            if current_paragraph:
                current_paragraph += " " + sentence
            else:
                current_paragraph = sentence

    if current_paragraph:
        paragraphs.append(current_paragraph)

    return paragraphs

def split_text_by_html_tags(text):
    soup = BeautifulSoup(text, 'html.parser')
    paragraphs = []
    current_paragraph = ""

    for element in soup.find_all(['p', 'b', 'strong', 'span']):
        if elAdministratorement.name == 'p':
            if current_paragraph:
                paragraphs.append(current_paragraph)
            current_paragraph = element.get_text()
        elif element.name in ['b', 'strong']:
            if current_paragraph:
                paragraphs.append(current_paragraph)
            current_paragraph = element.get_text()

    if current_paragraph:
        paragraphs.append(current_paragraph)

    return paragraphs


def extract_candidate_name_advanced(text):
    """
    Extrait le nom du candidat en se basant sur les premiers mots du texte.

    Args:
    text (str): Texte du CV

    Returns:
    str: Nom du candidat
    """
    # Vérifier les paramètres d'entrée
    if not text or not isinstance(text, str):
        return None

    # Mots à exclure
    mots_exclus = [
        'resume', 'Resume', 'cv', 'candidat', 'nom', 'prenom', 'societe',
        'contact', 'tel', 'telephone', 'email', 'adresse'
    ]

    # Nettoyer et diviser le texte
    lignes = [ligne.strip() for ligne in text.split('\n') if ligne.strip()]

    # Si pas de lignes, retourner None
    if not lignes:
        return None

    # Fonction pour vérifier si un nom est valide
    def est_nom_valide(nom_possible):
        # Convertir en mots
        mots = nom_possible.split()

        # Critères de validation
        return (
            # Entre 2 et 3 mots
                2 <= len(mots) <= 3 and
                # Tous les mots commencent par une majuscule
                all(mot[0].isupper() for mot in mots) and
                # Aucun mot n'est un mot exclu
                not any(mot.lower() in mots_exclus for mot in mots) and
                # Pas de chiffres
                not any(char.isdigit() for char in nom_possible)
        )

    # Stratégies d'extraction
    strategies = [
        # 1. Première ligne entière
        lambda: lignes[0] if est_nom_valide(lignes[0]) else None,

        # 2. Deux premiers mots de la première ligne
        lambda: ' '.join(lignes[0].split()[:2]) if est_nom_valide(' '.join(lignes[0].split()[:2])) else None,

        # 3. Trois premiers mots de la première ligne
        lambda: ' '.join(lignes[0].split()[:3]) if est_nom_valide(' '.join(lignes[0].split()[:3])) else None
    ]

    # Tester chaque stratégie
    for strategie in strategies:
        nom = strategie()
        if nom:
            return nom

    return None


# Fonction de test
def test_extraction():
    # Exemples de CV
    cv_samples = [
        "Saif Eddine Jbili\n+216 28 69 97 27\nIngénieur",
        "SAMAR JBILI\nSociété Tech Solutions\nIngénieur",
        "Jean Pierre Dupont\nCV - Ingénieur\nContact: ...",
        "Resume de Marie Claire Dubois\nProfil professionnel"
    ]

    for cv in cv_samples:
        print("CV:")
        print(cv.split('\n')[0])

        nom_extrait = extract_candidate_name_advanced(cv)
        print("Nom extrait :", nom_extrait)
        print()


# Lancer les tests
test_extraction()
def extract_phone(cv_text):
    """Extract phone number from CV text with improved pattern matching."""
    phone_patterns = [
        r'(?:(?:\+|00)(?:33|216|1|44|49))\s*[1-9](?:[\s.-]*\d{1,2}){4,}',  # Format international avec indicatif pays
        r'(?:0|\+)\s*[1-9](?:[\s.-]*\d{2}){4}',  # Format français
        r'\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}',  # Format basique 10 chiffres
        r'\+\d{3}\s*\d{2}\s*\d{2}\s*\d{2}\s*\d{2}'  # Format spécifique +216 XX XX XX XX
    ]

    for pattern in phone_patterns:
        phone_matches = re.search(pattern, cv_text)
        if phone_matches:
            phone = phone_matches.group()
            # Nettoyer le numéro (enlever espaces, tirets)
            phone = re.sub(r'[\s.-]', '', phone)
            # Formater correctement
            if phone.startswith('00'):
                phone = '+' + phone[2:]
            elif phone.startswith('0') and not phone.startswith('+'):
                # Assumez +33 pour la France si pas d'indicatif
                phone = '+33' + phone[1:]
            return phone

    return None

# Fonction améliorée pour extraire les années d'expérience
import re
from datetime import datetime
import re
from datetime import datetime

def extract_experience_years(cv_text):
    """
    Extract the number of years of experience by analyzing employment history.
    """
    # Obtenir l'année actuelle
    current_year = datetime.now().year

    # Chercher toutes les plages de dates dans les formats "YYYY - YYYY", "YYYY - Présent", ou similaire
    date_pattern = r'(\d{4})\s*[-–]\s*(\d{4}|Actuelle|actuelle|Présent|présent|Present|present)'
    date_matches = re.findall(date_pattern, cv_text)

    total_years = 0

    for date_range in date_matches:
        start_year_str, end_year_str = date_range

        # Extraire l'année de début
        start_year = int(start_year_str)

        # Déterminer l'année de fin
        if any(end_term in end_year_str for end_term in
               ["Actuelle", "actuelle", "Présent", "présent", "Present", "present"]):
            end_year = current_year
        else:
            end_year = int(end_year_str)

        # Calculer la durée en années
        if start_year <= end_year and start_year >= 1950 and end_year <= current_year:
            experience_years = end_year - start_year
            total_years += experience_years

    # Vérifier également les années mentionnées directement
    direct_exp_pattern = r'(\d+)\s*(?:ans|années|an|année)\s*d.expérience'
    direct_match = re.search(direct_exp_pattern, cv_text, re.IGNORECASE)
    if direct_match:
        direct_years = int(direct_match.group(1))
        if direct_years > 0 and (total_years == 0 or direct_years > total_years):
            total_years = direct_years

    return total_years if total_years > 0 else None



def extract_location(cv_text):
    """Extract location from CV text with improved pattern matching."""
    # Chercher les adresses après des mots clés
    location_patterns = [
        r'(?:Adresse|Address|Location|Localisation)\s*(?::|;)?\s*([^,\n]+(?:,\s*[^,\n]+){0,3})',
        r'(?:\n|^)([A-Z][a-zA-ZÀ-ÿ\s]+(?:,\s*[A-Z][a-zA-ZÀ-ÿ\s]+){1,2})(?:\n|$)',
        r'(\d+\s*(?:rue|avenue|boulevard|bd|place)\s+[^,\n]+(?:,\s*[^,\n]+){0,3})'
    ]

    for pattern in location_patterns:
        matches = re.search(pattern, cv_text, re.IGNORECASE)
        if matches:
            location = matches.group(1).strip()
            # Vérifier que ce n'est pas un numéro de téléphone ou email
            if not re.search(r'@|\+|\d{2}[\s.-]?\d{2}[\s.-]?\d{2}', location):
                return location

    # Chercher des villes spécifiques suivies de pays
    cities = ["Paris", "Lyon", "Marseille", "Tunis", "Sfax", "Sousse", "Casablanca", "Rabat", "Alger", "Oran"]
    countries = ["France", "Tunisie", "Maroc", "Algérie"]

    for city in cities:
        city_pattern = rf'{city}\s*(?:,\s*|\s+-\s*|\s+)?({"|".join(countries)})?'
        matches = re.search(city_pattern, cv_text, re.IGNORECASE)
        if matches:
            location = city
            if matches.group(1):  # Si le pays est mentionné
                location += f", {matches.group(1)}"
            return location

    return None

import re

import re


import re

def extract_education_level(cv_text):
    """
    Extract the education level from a CV - Improved version with context analysis
    """
    if not cv_text or not isinstance(cv_text, str):
        return None

    # Dictionary of degrees with their Bac+N equivalents
    degree_mapping = {
        "bac[-+]?\\s*\\+?\\s*(8|7|6)": 8,  # Bac+8, Bac+7, Bac+6
        "bac[-+]?\\s*\\+?\\s*5": 5,  # Bac+5
        "bac[-+]?\\s*\\+?\\s*4": 4,  # Bac+4
        "bac[-+]?\\s*\\+?\\s*3": 3,  # Bac+3
        "bac[-+]?\\s*\\+?\\s*2": 2,  # Bac+2
        "bac[-+]?\\s*\\+?\\s*1": 1,  # Bac+1
        "ph[.]*d": 8,  # PhD
        "doctorat": 8,  # Doctorat
        "thèse": 8,  # Thèse
        "master\\s*2": 5,  # Master 2
        "master\\s*1": 4,  # Master 1
        "m2\\b": 5,  # M2
        "m1\\b": 4,  # M1
        "\\bmast[eè]re\\b": 5,  # Mastère
        "\\bmaster\\b": 5,  # Master
        "\\bmba\\b": 5,  # MBA
        "\\bmsc\\b": 5,  # MSc
        "ingénieur": 5,  # Ingénieur
        "ingé": 5,  # Ingé
        "école\\s*d['e]\\s*ingénieur": 5,  # École d'ingénieur
        "diplôme\\s*d['e]\\s*ingénieur": 5,  # Diplôme d'ingénieur
        "maîtrise": 4,  # Maîtrise
        "licence\\s*pro": 3,  # Licence pro
        "licence": 3,  # Licence
        "bachelor": 3,  # Bachelor
        "bts": 2,  # BTS
        "dut": 2,  # DUT
        "deug": 2,  # DEUG
        "bac\\s*pro": 0,  # Bac pro
        "bac\\s*technologique": 0,  # Bac technologique
        "bac\\s*général": 0,  # Bac général
        "baccalauréat": 0,  # Baccalauréat
        "\\bbac\\b": 0,  # Bac
    }

    # Normalize the text
    normalized_text = ' '.join(cv_text.lower().split())

    # Analyze the context - check if the candidate mentions a higher degree in active context
    # Look for phrases that might indicate current level versus past education

    # Check if the candidate explicitly mentions their current education level
    current_education_indicators = [
        r"niveau\s+d['e]\s*(?:formation|étude|qualification)[:]*\s*(\w+)",
        r"je\s+suis\s+diplômé\s+(?:de|d'une|du|d'un)\s+(\w+)",
        r"diplôme\s+(?:actuel|en\s+cours|obtenu)[:]*\s*(\w+)",
        r"titulaire\s+d['e]un[e]?\s+(\w+)",
        r"actuellement\s+en\s+(\w+)",
        r"j['e]\s+possède\s+un[e]?\s+(\w+)"
    ]

    # Search for directly stated education level
    current_level = None
    for pattern in current_education_indicators:
        match = re.search(pattern, normalized_text)
        if match:
            stated_level = match.group(1)
            # Check if the stated level matches one of our known degrees
            for degree_pattern, level in degree_mapping.items():
                if re.search(r'\b' + degree_pattern + r'\b', stated_level):
                    current_level = level
                    break
            if current_level is not None:
                break

    # If we found a clearly stated current level, use it
    if current_level is not None:
        if current_level == 0:
            return "Baccalauréat"
        return f"Bac+{current_level}"

    # Otherwise, search for all degrees in the text
    found_degrees = []
    for degree_pattern, level in degree_mapping.items():
        if re.search(r'\b' + degree_pattern + r'\b', normalized_text):
            found_degrees.append((level, degree_pattern))

    # Check for contradictions - if someone mentions they have a license but then says they only have a baccalaureate
    if found_degrees:
        # Check if there are indications this is a "in progress" or "unfinished" degree
        in_progress_indicators = [
            r"en\s+cours\s+d['e]\s*(\w+)",
            r"je\s+prépare\s+un[e]?\s+(\w+)",
            r"formation\s+non\s+terminée",
            r"diplôme\s+non\s+obtenu",
            r"étudiant\s+en\s+(\w+)",
            r"n['e]\s+pas\s+terminé"
        ]

        # Find if any higher education degree is mentioned as in progress
        in_progress_degrees = []
        for pattern in in_progress_indicators:
            matches = re.finditer(pattern, normalized_text)
            for match in matches:
                if match.groups():
                    degree_mentioned = match.group(1)
                    for degree_pattern, level in degree_mapping.items():
                        if re.search(r'\b' + degree_pattern + r'\b', degree_mentioned):
                            in_progress_degrees.append((level, degree_pattern))

        # If we found in-progress degrees, adjust our found degrees accordingly
        if in_progress_degrees:
            for level, pattern in in_progress_degrees:
                # Remove in-progress degrees from found degrees
                found_degrees = [(l, p) for l, p in found_degrees if p != pattern]

        # Sort remaining degrees by level
        found_degrees.sort(reverse=True)

        # Return the highest education level found
        if found_degrees:
            highest_level = found_degrees[0][0]
            if highest_level == 0:
                return "Baccalauréat"
            return f"Bac+{highest_level}"

    # Now, check for years of study mentioned in the text (e.g., "4 ans", "3 years")
    years_of_study_pattern = r"(\d+)\s*(ans|years?)\s*(?:d['e]\s*(?:formation|études)?)?"
    years_match = re.search(years_of_study_pattern, normalized_text)
    if years_match:
        years = int(years_match.group(1))
        if years >= 8:
            return "Bac+8 (Doctorat)"
        elif years == 7:
            return "Bac+7"
        elif years == 6:
            return "Bac+6"
        elif years == 5:
            return "Bac+5"
        elif years == 4:
            return "Bac+3"
        elif years == 3:
            return "Bac+2"
        elif years == 2:
            return "Bac+1"
        else:
            return "Baccalauréat"

    return None

def extract_cv_info(cv_text):
    """
    Extract key information from a CV text - Version améliorée
    """
    result = {
        "Nom": None,
        "phone": None,
        "email": None,
        "education": None,
        "experience_years": None,
        "location": None
    }

    if not cv_text or not isinstance(cv_text, str):
        logger.warning("Invalid CV text provided")
        return result

    # Nettoyage du texte
    cv_text = clean_text(cv_text)

    # Extraction du nom
    result["Nom"] = extract_candidate_name_advanced(cv_text)

    # Extraction du numéro de téléphone
    result["phone"] = extract_phone(cv_text)
    # Extraction de l'email
    email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
    email_matches = re.findall(email_pattern, cv_text)
    if email_matches:
        result["email"] = email_matches[0].lower()  # Convert to lowercase
        # Validate email format
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', result["email"]):
            # Try to clean the email
            result["email"] = re.sub(r'[^\w\.-@]', '', result["email"])

    # Extraction de la localisation
    result["location"] = extract_location(cv_text)
    # Extraction du niveau d'éducation
    result["education"] = extract_education_level(cv_text)

    # Extraction des années d'expérience
    result["experience_years"] = extract_experience_years(cv_text)



    return result


# Fix for CV data processing
def process_cv(cv_file, file_type='pdf'):
    cv_text = ""

    try:
        if file_type.lower() == 'pdf':
            cv_text = extract_pdf_text(cv_file)
            if not cv_text.strip() and OCR_AVAILABLE:  # If text is empty, use OCR
                cv_text = extract_ocr_text(cv_file)
        elif file_type.lower() in ['docx', 'doc']:
            cv_text = extract_docx_text(cv_file)
        elif file_type.lower() in ['jpg', 'jpeg', 'png'] and OCR_AVAILABLE:
            cv_text = extract_ocr_text(cv_file)
        else:
            raise ValueError("Unsupported file format. Use 'pdf', 'docx' or images.")

        # Log the extracted text for debugging
        logger.info(f"Extracted text (first 50 characters): {cv_text[:50]}")

        # Extract information
        cv_info = extract_cv_info(cv_text)

        # Data validation and cleaning
        if not cv_info["Nom"] or cv_info["Nom"] == "":
            # Try to extract name from filename
            filename = os.path.basename(cv_file)
            name_match = re.search(r'CV[\s_-]*([\w\s]+)\.', filename)
            if name_match:
                cv_info["Nom"] = name_match.group(1).strip()
            else:
                cv_info["Nom"] = "Candidat Sans Nom"

        # Ensure experience_years is numeric
        if cv_info["experience_years"] and not isinstance(cv_info["experience_years"], (int, float)):
            try:
                cv_info["experience_years"] = float(str(cv_info["experience_years"]).replace(',', '.'))
            except:
                cv_info["experience_years"] = 0

        logger.info(f"Extracted CV information: {cv_info}")

        # Convert to DataFrame
        cv_df = pd.DataFrame([cv_info])
        return cv_df

    except Exception as e:
        logger.error(f"Error processing CV: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # Return empty DataFrame with correct structure
        return pd.DataFrame([{
            "Nom": "",
            "phone": "",
            "email": "",
            "education": "",
            "experience_years": "",
            "location": ""}])

    def split_text_by_keywords(text):
        paragraphs = []
        current_paragraph = ""
        sentences = nltk.sent_tokenize(text)

        for sentence in sentences:
            sentence = clean_text(sentence)
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', sentence, re.IGNORECASE):
                    if current_paragraph:
                        paragraphs.append(current_paragraph)
                    current_paragraph = sentence
                    break
            else:
                if current_paragraph:
                    current_paragraph += " " + sentence
                else:
                    current_paragraph = sentence

        if current_paragraph:
            paragraphs.append(current_paragraph)

        return paragraphs

    def split_text_by_html_tags(text):
        soup = BeautifulSoup(text, 'html.parser')
        paragraphs = []
        current_paragraph = ""

        for element in soup.find_all(['p', 'b', 'strong', 'span']):
            if element.name == 'p':
                if current_paragraph:
                    paragraphs.append(current_paragraph)
                current_paragraph = element.get_text()
            elif element.name in ['b', 'strong']:
                if current_paragraph:
                    paragraphs.append(current_paragraph)
                current_paragraph = element.get_text()

        if current_paragraph:
            paragraphs.append(current_paragraph)

        return paragraphs