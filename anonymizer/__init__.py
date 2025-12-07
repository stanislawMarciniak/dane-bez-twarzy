"""
Dane bez Twarzy - System Anonimizacji Tekstów Polskich
======================================================

Biblioteka do automatycznej detekcji i anonimizacji danych osobowych
w tekstach w języku polskim.

Podstawowe użycie:
    from anonymizer import anonymize_text, Anonymizer
    
    # Proste API
    result = anonymize_text("Nazywam się Jan Kowalski, mój PESEL to 90010112345.")
    print(result['anonymized'])  # "Nazywam się {name} {surname}, mój PESEL to {pesel}."
    
    # Zaawansowane użycie
    anonymizer = Anonymizer(
        use_ml=True,
        generate_synthetic=True,
        include_intermediate=True
    )
    result = anonymizer.anonymize(text)

Obsługiwane kategorie danych:
    - Dane identyfikacyjne: name, surname, age, date-of-birth, date, sex,
      religion, political-view, ethnicity, sexual-orientation, health, relative
    - Dane kontaktowe: city, address, email, phone
    - Identyfikatory: pesel, document-number
    - Dane zawodowe: company, school-name, job-title
    - Dane finansowe: bank-account, credit-card-number
    - Identyfikatory cyfrowe: username, secret

Architektura:
    1. Warstwa Regex - szybkie wykrywanie danych o stałym formacie
    2. Warstwa ML (NER) - wykrywanie encji wymagających kontekstu
    3. Analiza morfologiczna - zachowanie spójności gramatycznej
    4. Generator syntetyczny - tworzenie realistycznych zamienników
"""

__version__ = "1.0.0"
__author__ = "PLLuM Team"

from .regex_layer import (
    RegexLayer,
    DetectedEntity,
    EntityType,
)

from .ml_layer import (
    MLLayer,
    NameSurnameSplitter,
)

from .morphology import (
    MorphologyAnalyzer,
    MorphologyInfo,
    EnrichmentPipeline,
    PolishInflector,
    Case,
    Gender,
    Number,
)

from .synthetic_generator import (
    SyntheticDataPipeline,
    generate_synthetic_output,
)

from .anonymizer import (
    Anonymizer,
    AnonymizationResult,
    AnonymizerCLI,
    create_anonymizer,
    anonymize_text,
    anonymize_file,
)

# Eksportowane symbole
__all__ = [
    # Główne klasy
    'Anonymizer',
    'AnonymizationResult',
    'create_anonymizer',
    
    # Uproszczone API
    'anonymize_text',
    'anonymize_file',
    
    # Warstwy
    'RegexLayer',
    'MLLayer',
    
    # Encje
    'DetectedEntity',
    'EntityType',
    
    # Morfologia
    'MorphologyAnalyzer',
    'MorphologyInfo',
    'PolishInflector',
    'Case',
    'Gender',
    'Number',
    
    # Generacja syntetyczna
    'SyntheticDataPipeline',
    'generate_synthetic_output',
    
    # Narzędzia
    'NameSurnameSplitter',
    'EnrichmentPipeline',
    'AnonymizerCLI',
]