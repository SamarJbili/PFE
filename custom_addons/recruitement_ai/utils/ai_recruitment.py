# ai_recruitment.py

import pandas as pd
import re
import os
import tempfile
import logging

_logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import spacy

    SPACY_AVAILABLE = True
    try:
        nlp = spacy.load("fr_core_news_sm")
        FRENCH_MODEL_AVAILABLE = True
    except IOError:
        _logger.warning("French language model not available. Installing a basic model instead.")
        FRENCH_MODEL_AVAILABLE = False
        # Use a basic model as fallback
        nlp = spacy.blank("fr")
except ImportError:
    SPACY_AVAILABLE = False
    _logger.warning("spaCy not available. Some features will be limited.")

try:
    import PyPDF2

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    _logger.warning("PyPDF2 not available. PDF parsing will be limited.")

try:
    import docx

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    _logger.warning("python-docx not available. DOCX parsing will be limited.")

try:
    from PIL import Image
    import pytesseract

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    _logger.warning("pytesseract or PIL not available. OCR features will be disabled.")

# Optional translation support
try:
    from googletrans import Translator

    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False
    _logger.warning("googletrans not available. Translation features will be disabled.")


# Fonction pour extraire du texte d'une image (OCR)
def extract_ocr_text(image_file):
    if not OCR_AVAILABLE:
        return "OCR not available"

    try:
        image = Image.open(image_file)
        text = pytesseract.image_to_string(image, lang='fra')
        return text
    except Exception as e:
        _logger.error(f"OCR error: {str(e)}")
        return ""


# Fonction pour extraire du texte d'un fichier PDF
def extract_pdf_text(pdf_file):
    if not PDF_AVAILABLE:
        return "PDF extraction not available"

    try:
        with open(pdf_file, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
            return text
    except Exception as e:
        _logger.error(f"PDF extraction error: {str(e)}")
        return ""


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
        _logger.error(f"DOCX extraction error: {str(e)}")
        return ""


# Fonction pour traduire le texte extrait
def translate_text(text, target_language='fr'):
    if not TRANSLATION_AVAILABLE:
        return text

    try:
        translator = Translator()
        translated = translator.translate(text, dest=target_language)
        return translated.text
    except Exception as e:
        _logger.error(f"Translation error: {str(e)}")
        return text


# Fonction pour extraire des informations d'un texte (CV)
def extract_cv_info(text):
    cv_info = {"Nom": "", "Expérience": "", "Compétences": "", "Formation": ""}

    # Extract name using spaCy if available
    if SPACY_AVAILABLE:
        doc = nlp(text[:1000])  # Limit to first 1000 chars for performance
        for ent in doc.ents:
            if ent.label_ == "PERSON" and cv_info["Nom"] == "":
                cv_info["Nom"] = ent.text
                break

    # Fallback for name extraction
    if cv_info["Nom"] == "":
        # Try to find patterns like "Nom: John Doe" or "Name: John Doe"
        name_match = re.search(r"(Nom|Name)[\s:]+([A-Za-zÀ-ÿ\s\-]+)", text, re.IGNORECASE)
        if name_match:
            cv_info["Nom"] = name_match.group(2).strip()

    # Extract experience
    experience_match = re.search(r"(\d+)\s*(ans?|years?|année?s?)\s*(d[e']expérience|experience)?", text, re.IGNORECASE)
    if experience_match:
        cv_info["Expérience"] = experience_match.group(1)

    # Extract skills
    skills_match = re.search(r"(Compétences|Competences|Skills|Expertises?)[\s:]*([^\.]+)", text, re.IGNORECASE)
    if skills_match:
        cv_info["Compétences"] = skills_match.group(2).strip()

    # Extract education
    education_match = re.search(r"(Formation|Éducation|Education|Diplôme|Diplome|Degree)[\s:]*([^\.]+)", text,
                                re.IGNORECASE)
    if education_match:
        cv_info["Formation"] = education_match.group(2).strip()

    return cv_info


# Fonction pour traiter un CV à partir de son fichier et type
def process_cv(cv_file, file_type='pdf'):
    cv_text = ""

    try:
        if file_type == 'pdf':
            cv_text = extract_pdf_text(cv_file)
            if not cv_text.strip() and OCR_AVAILABLE:  # Si le texte est vide, utiliser OCR
                cv_text = extract_ocr_text(cv_file)
        elif file_type == 'docx':
            cv_text = extract_docx_text(cv_file)
        else:
            raise ValueError("Format de fichier non supporté. Utilisez 'pdf' ou 'docx'.")

        # Traduction du texte extrait si nécessaire
        if TRANSLATION_AVAILABLE and cv_text:
            cv_text = translate_text(cv_text, target_language='fr')

        # Extraction des informations
        cv_info = extract_cv_info(cv_text)

        # Convertir en DataFrame
        cv_df = pd.DataFrame([cv_info])
        return cv_df

    except Exception as e:
        _logger.error(f"Error processing CV: {str(e)}")
        # Return empty DataFrame with correct structure
        return pd.DataFrame([{"Nom": "", "Expérience": "", "Compétences": "", "Formation": ""}])