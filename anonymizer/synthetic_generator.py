"""
Synthetic Data Pipeline
Generuje dane syntetyczne na podstawie zanonimizowanego tekstu z metadanymi morfologicznymi.

Integruje:
- synthetic_data_pool.py - pule danych syntetycznych
- morfeusz_inflector.py - odmianę przez przypadki
"""

import re
import random
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Dodaj główny katalog projektu do ścieżki, aby zaimportować moduły z roota
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from morfeusz_inflector import MorfeuszInflector
from synthetic_data_pool import (
    SYNTHETIC_POOL,
    generate_random_email,
    generate_random_phone,
    generate_random_address,
    generate_random_date,
    generate_random_pesel,
    generate_random_bank_account,
    generate_random_document_number,
    generate_random_credit_card_number
)

logger = logging.getLogger(__name__)


# Mapowanie przypadków: pipeline format -> generator format
CASE_MAP_TO_POLISH = {
    'nom': 'mianownik',
    'gen': 'dopełniacz',
    'dat': 'celownik',
    'acc': 'biernik',
    'ins': 'narzędnik',
    'loc': 'miejscownik',
    'voc': 'wołacz',
    # Fallback dla pełnych nazw (gdyby były używane)
    'nominative': 'mianownik',
    'genitive': 'dopełniacz',
    'dative': 'celownik',
    'accusative': 'biernik',
    'instrumental': 'narzędnik',
    'locative': 'miejscownik',
    'vocative': 'wołacz',
}

# Mapowanie rodzaju: pipeline format -> generator format
GENDER_MAP_TO_SYNTHETIC = {
    'm1': 'man',      # męskoosobowy
    'm2': 'man',      # męskożywotny
    'm3': 'man',      # męskonieżywotny
    'f': 'woman',     # żeński
    'n': 'man',       # nijaki -> domyślnie męski
    'masc': 'man',
    'fem': 'woman',
    'neut': 'man',
}

# Wzorzec do parsowania tokenów z metadanymi morfologicznymi
# Format: [entity_type|key1=val1|key2=val2]
MORPHOLOGY_TOKEN_PATTERN = re.compile(
    r'\[([a-z0-9-]+)(?:\|([^\]]*))?\]'
)

# Wzorzec do prostych tokenów bez metadanych
# Format: [entity_type]
SIMPLE_TOKEN_PATTERN = re.compile(
    r'\[([a-z0-9-]+)\]'
)

# Typy encji wymagające unikalności (nie powtarzamy tych samych wartości)
UNIQUE_TOKEN_TYPES = {
    'name', 'surname', 'username', 'company', 'school-name',
    'job-title', 'relative'
}

# Typy encji wrażliwe na płeć
GENDER_SENSITIVE_TYPES = {
    'name', 'surname', 'sexual-orientation',
    'ethnicity', 'job-title', 'relative'
}

# Funkcje generujące dla typów specjalnych
GENERATOR_FUNCTIONS = {
    'phone': generate_random_phone,
    'date': generate_random_date,
    'date-of-birth': lambda: generate_random_date(start_year=1950, end_year=2000),
    'pesel': generate_random_pesel,
    'bank-account': generate_random_bank_account,
    'document-number': generate_random_document_number,
    'credit-card-number': generate_random_credit_card_number,
    'address': lambda: generate_random_address(random.choice(SYNTHETIC_POOL['city'])),
}


class SyntheticDataPipeline:
    """
    Pipeline generowania danych syntetycznych.
    
    Przetwarza tekst z tokenami zastępczymi i generuje realistyczne
    dane syntetyczne z odpowiednią odmianą przez przypadki.
    """
    
    def __init__(self, seed: Optional[int] = None):
        """
        Inicjalizuje pipeline.
        
        Args:
            seed: Ziarno losowości dla powtarzalności wyników
        """
        if seed is not None:
            random.seed(seed)
        
        self.inflector = MorfeuszInflector()
        self._token_memory: Dict[str, str] = {}
        self._available_pools: Dict[str, List[str]] = {}
        self._reset_pools()
    
    def _reset_pools(self):
        """Resetuje pule dostępnych wartości."""
        self._available_pools = {
            token_type: list(SYNTHETIC_POOL[token_type])
            for token_type in UNIQUE_TOKEN_TYPES
            if token_type in SYNTHETIC_POOL
        }
        # Dodaj pule z sufiksami płci
        for token_type in GENDER_SENSITIVE_TYPES:
            for suffix in ['-man', '-woman']:
                pool_key = f"{token_type}{suffix}"
                if pool_key in SYNTHETIC_POOL:
                    self._available_pools[pool_key] = list(SYNTHETIC_POOL[pool_key])
    
    def _parse_morphology_metadata(self, metadata_str: str) -> Dict[str, str]:
        """
        Parsuje metadane morfologiczne z formatu 'key1=val1|key2=val2'.
        
        Args:
            metadata_str: String z metadanymi
            
        Returns:
            Słownik z metadanymi
        """
        if not metadata_str:
            return {}
        
        result = {}
        for part in metadata_str.split('|'):
            if '=' in part:
                key, val = part.split('=', 1)
                result[key.strip()] = val.strip()
        
        return result
    
    def _get_polish_case(self, morph: Dict[str, str]) -> Optional[str]:
        """Pobiera polski przypadek z metadanych morfologicznych."""
        case = morph.get('case', '')
        return CASE_MAP_TO_POLISH.get(case.lower(), None)
    
    def _get_gender_suffix(self, morph: Dict[str, str]) -> str:
        """Pobiera sufiks płci (man/woman) z metadanych morfologicznych."""
        gender = morph.get('gender', '')
        return GENDER_MAP_TO_SYNTHETIC.get(gender.lower(), 'man')
    
    def _get_value_from_pool(
        self,
        base_type: str,
        pool_key: str,
        use_unique: bool = True
    ) -> Optional[str]:
        """
        Pobiera wartość z puli, opcjonalnie usuwając ją (dla unikalności).
        
        Args:
            base_type: Bazowy typ encji (np. 'name')
            pool_key: Klucz puli (np. 'name-man')
            use_unique: Czy usuwać wartość z puli po użyciu
            
        Returns:
            Wartość z puli lub None
        """
        if pool_key in self._available_pools and use_unique:
            pool = self._available_pools[pool_key]
            if pool:
                value = random.choice(pool)
                pool.remove(value)
                return value
            # Pula wyczerpana - losuj z oryginalnej
            if pool_key in SYNTHETIC_POOL:
                return random.choice(SYNTHETIC_POOL[pool_key])
        
        if pool_key in SYNTHETIC_POOL:
            return random.choice(SYNTHETIC_POOL[pool_key])
        
        return None
    
    def _generate_replacement(
        self,
        entity_type: str,
        morph: Dict[str, str],
        full_token: str
    ) -> str:
        """
        Generuje wartość zastępczą dla tokenu.
        
        Args:
            entity_type: Typ encji
            morph: Metadane morfologiczne
            full_token: Pełny oryginalny token (dla pamięci)
            
        Returns:
            Wygenerowana wartość syntetyczna
        """
        # Sprawdź pamięć - te same tokeny powinny dawać te same wartości
        if full_token in self._token_memory:
            return self._token_memory[full_token]
        
        base_type = re.sub(r'\d+$', '', entity_type)  # Usuń numery z końca
        gender_suffix = self._get_gender_suffix(morph)
        polish_case = self._get_polish_case(morph)
        
        new_value = None
        
        # 1. Najpierw sprawdź funkcje generujące
        if base_type in GENERATOR_FUNCTIONS:
            new_value = GENERATOR_FUNCTIONS[base_type]()
        
        # 2. Email - specjalna logika
        elif base_type == 'email':
            all_names = SYNTHETIC_POOL.get('name-man', []) + SYNTHETIC_POOL.get('name-woman', [])
            temp_name = random.choice(all_names) if all_names else 'user'
            temp_surname = random.choice(SYNTHETIC_POOL.get('surname-man', ['kowalski']))
            new_value = generate_random_email(temp_name, temp_surname)
        
        # 3. Typy wrażliwe na płeć
        elif base_type in GENDER_SENSITIVE_TYPES:
            pool_key = f"{base_type}-{gender_suffix}"
            use_unique = base_type in UNIQUE_TOKEN_TYPES
            new_value = self._get_value_from_pool(base_type, pool_key, use_unique)
        
        # 4. Standardowe typy
        else:
            use_unique = base_type in UNIQUE_TOKEN_TYPES
            new_value = self._get_value_from_pool(base_type, base_type, use_unique)
        
        # Jeśli nie znaleziono wartości, zwróć oryginalny token
        if new_value is None:
            logger.warning(f"Brak wartości syntetycznej dla typu: {entity_type}")
            return full_token
        
        # 5. Odmiana przez przypadki
        if polish_case and polish_case != 'mianownik':
            is_female = (gender_suffix == 'woman')
            
            # Dla niektórych typów odmieniamy całą frazę
            full_phrase_types = {'company', 'school-name'}
            
            if base_type in full_phrase_types:
                # Odmiana każdego słowa
                parts = new_value.split()
                inflected_parts = [
                    self.inflector.inflect_word(word, polish_case, is_female)
                    for word in parts
                ]
                new_value = ' '.join(inflected_parts)
            else:
                # Odmiana tylko pierwszego słowa
                parts = new_value.split()
                if parts:
                    inflected_first = self.inflector.inflect_word(
                        parts[0], polish_case, is_female
                    )
                    new_value = ' '.join([inflected_first] + parts[1:])
        
        # Zapisz do pamięci
        self._token_memory[full_token] = new_value
        
        return new_value
    
    def _replacer(self, match: re.Match) -> str:
        """Funkcja zamieniająca dla re.sub."""
        full_token = match.group(0)
        entity_type = match.group(1)
        metadata_str = match.group(2) if len(match.groups()) > 1 else None
        
        morph = self._parse_morphology_metadata(metadata_str or '')
        
        return self._generate_replacement(entity_type, morph, full_token)
    
    def generate_synthetic_text(
        self,
        anonymized_text: str,
        intermediate_text: Optional[str] = None
    ) -> str:
        """
        Generuje tekst z danymi syntetycznymi.
        
        Preferuje intermediate_text (z metadanymi morfologicznymi),
        ale może pracować też z czystym anonymized_text.
        
        Args:
            anonymized_text: Zanonimizowany tekst (bez metadanych)
            intermediate_text: Tekst pośredni z metadanymi morfologicznymi
            
        Returns:
            Tekst z danymi syntetycznymi
        """
        # Resetuj pamięć dla nowego tekstu
        self._token_memory.clear()
        self._reset_pools()
        
        # Preferuj tekst z metadanymi
        text_to_process = intermediate_text if intermediate_text else anonymized_text
        
        # Zamień tokeny z metadanymi: [type|key=val]
        result = MORPHOLOGY_TOKEN_PATTERN.sub(self._replacer, text_to_process)
        
        return result
    
    def generate_batch(
        self,
        texts: List[Tuple[str, Optional[str]]]
    ) -> List[str]:
        """
        Generuje dane syntetyczne dla wielu tekstów.
        
        Args:
            texts: Lista krotek (anonymized, intermediate)
            
        Returns:
            Lista tekstów z danymi syntetycznymi
        """
        results = []
        for anonymized, intermediate in texts:
            result = self.generate_synthetic_text(anonymized, intermediate)
            results.append(result)
        return results


# =============================================================================
# Backward compatibility: funkcja z oryginalnego synthetic_generator.py
# =============================================================================

def generate_synthetic_output(anon_text: str) -> str:
    """
    Funkcja kompatybilna wstecz z oryginalnym synthetic_generator.py.
    
    Przetwarza tekst z tagami w formacie [type][gender][case].
    
    Args:
        anon_text: Tekst z tagami do zamiany
        
    Returns:
        Tekst z danymi syntetycznymi
    """
    # Wzorzec dla starego formatu: [type][man/woman][przypadek]
    OLD_FORMAT_PATTERN = re.compile(
        r'\[([a-z0-9-]+)\](\[(?:man|woman|męski|żeński)\])?(\[(?:mianownik|dopełniacz|celownik|biernik|narzędnik|miejscownik|wołacz)\])?',
        re.IGNORECASE
    )
    
    # Mapowanie polskich nazw rodzaju
    POLISH_GENDER_MAP = {
        'man': 'man',
        'woman': 'woman',
        'męski': 'man',
        'żeński': 'woman',
    }
    
    pipeline = SyntheticDataPipeline()
    
    def old_format_replacer(match: re.Match) -> str:
        full_token = match.group(0)
        entity_type = match.group(1)
        gender_attr = match.group(2)
        case_attr = match.group(3)
        
        # Konwertuj do formatu morph
        morph = {}
        
        if gender_attr:
            gender_raw = gender_attr.strip('[]').lower()
            gender = POLISH_GENDER_MAP.get(gender_raw, 'man')
            morph['gender'] = 'f' if gender == 'woman' else 'm1'
        
        if case_attr:
            case_polish = case_attr.strip('[]').lower()
            # Odwróć mapowanie
            for eng, pol in CASE_MAP_TO_POLISH.items():
                if pol == case_polish:
                    morph['case'] = eng
                    break
        
        return pipeline._generate_replacement(entity_type, morph, full_token)
    
    result = OLD_FORMAT_PATTERN.sub(old_format_replacer, anon_text)
    return result


# =============================================================================
# CLI / Testy
# =============================================================================

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Test 1: Nowy format (z metadanymi)
    print("=== Test nowego formatu ===")
    test_intermediate = """
    Nazywam się [name|case=nom|gender=m1], mój PESEL to [pesel].
    Mieszkam w [city|case=loc].
    Mój email to [email], telefon: [phone].
    Pracuję jako [job-title|case=nom|gender=m1] w firmie [company|case=loc].
    """
    
    pipeline = SyntheticDataPipeline(seed=42)
    result = pipeline.generate_synthetic_text(test_intermediate)
    
    print(f"Input:\n{test_intermediate}")
    print(f"\nOutput:\n{result}")
    
    # Test 2: Stary format (kompatybilność wsteczna)
    print("\n=== Test starego formatu ===")
    test_old_format = """
    Nazywam się [name][man][mianownik] [surname][man][mianownik].
    Mieszkam w [city][miejscownik].
    Pracuję jako [job-title][woman][mianownik].
    """
    
    result_old = generate_synthetic_output(test_old_format)
    print(f"Input:\n{test_old_format}")
    print(f"\nOutput:\n{result_old}")
