# synthetic_generator.py

import re
import random
import sys

# Importy z plików zewnętrznych
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

SYNTHETIC_PATTERN = r'\[([a-z0-9-]+)\](\[man\]|\[woman\])?(\[mianownik\]|\[dopełniacz\]|\[celownik\]|\[biernik\]|\[narzędnik\]|\[miejscownik\]|\[wołacz\])?'

GENERATOR_MAP_FUNCTIONS = {
    'phone': generate_random_phone,
    'date': generate_random_date,
    'date-of-birth': lambda: generate_random_date(start_year=1950, end_year=2000),
    'pesel': generate_random_pesel,
    'bank-account': generate_random_bank_account,
    'document-number': generate_random_document_number,
    'credit-card-number': generate_random_credit_card_number,
    'address': lambda: generate_random_address(random.choice(SYNTHETIC_POOL['city'])),

}

# Lista tokenów, które MUSZĄ być unikalne (UAKTUALNIONA O NAZWISKA)
UNIQUE_TOKENS = ['name-man', 'name-woman', 'username', 'company', 'school-name',
                 'job-title-man', 'job-title-woman',
                 'surname-man', 'surname-woman', 'relative-man', 'relative-woman']

# Inicjalizacja serwisu Morfeusza
INFLECTOR_SERVICE = MorfeuszInflector()


def generate_synthetic_output(anon_text: str) -> str:
    """
    Główna funkcja generacji syntetycznej, koordynująca unikalność, płeć i fleksję.
    """

    # Pamięć tokenów jest lokalna dla tej sesji
    TOKEN_MEMORY = {}

    # Utworzenie KOPII puli dla tokenów, które muszą być unikalne
    available_pool = {
        token_type: list(SYNTHETIC_POOL[token_type])
        for token_type in UNIQUE_TOKENS if token_type in SYNTHETIC_POOL
    }

    def replacer(match):
        """Logika zamiany: generuje wartość tylko raz i zapisuje w pamięci."""

        raw_token_name = match.group(1)
        gender_attr = match.group(2)
        case_attr = match.group(3)

        token_key = match.group(0)

        # A. Sprawdzenie Spójności
        if token_key in TOKEN_MEMORY:
            return TOKEN_MEMORY[token_key]

        # B. Określanie klucza puli (base_pool_key)

        base_key = re.sub(r'\d+$', '', raw_token_name)
        base_pool_key = base_key

        gender_suffix = gender_attr.strip('[]') if gender_attr else None

        GENDER_SENSITIVE_KEYS = ['name', 'surname', 'sexual-orientation', 'ethnicity', 'job-title', 'relative']

        # Jeśli token jest czuły na płeć (jest w GENDER_SENSITIVE_KEYS)
        if base_key in GENDER_SENSITIVE_KEYS:
            final_gender = gender_suffix if gender_suffix in ['man', 'woman'] else 'man'
            base_pool_key = f'{base_key}-{final_gender}'

        new_value = None

        # 3. GENERACJA WŁAŚCIWEJ WARTOŚCI

        # 3.1. GENERACJA UNIKALNA (name-man, surname-woman, company, job-title-man/woman)
        if base_pool_key in available_pool:
            current_pool = available_pool[base_pool_key]
            if not current_pool:
                new_value = random.choice(SYNTHETIC_POOL[base_pool_key])
            else:
                new_value = random.choice(current_pool)
                current_pool.remove(new_value)

        # 3.2. Generacja EMail (Specjalny przypadek)
        elif base_key == 'email':
            all_names = SYNTHETIC_POOL['name-man'] + SYNTHETIC_POOL['name-woman']
            temp_name = random.choice(all_names)
            temp_surname = random.choice(
                SYNTHETIC_POOL['surname-man'])  # Używamy surname-man, bo jest większe/bardziej ogólne
            new_value = generate_random_email(temp_name, temp_surname)

        # 3.3. Generacja przez Funkcje Specjalne
        elif base_key in GENERATOR_MAP_FUNCTIONS:
            new_value = GENERATOR_MAP_FUNCTIONS[base_key]()

        # 3.4. Generacja z Puli Ogólnej
        elif base_pool_key in SYNTHETIC_POOL:
            new_value = random.choice(SYNTHETIC_POOL[base_pool_key])

        # 4. Zapis, ODMIANA i Zwrot:
        if new_value is not None:

            # ⭐️ KROK FLEKSJI (ODMIANA)
            if case_attr:
                case = case_attr.strip('[]')
                is_female = ('woman' in base_pool_key)

                new_value = INFLECTOR_SERVICE.inflect_word(new_value, case, is_female)

            TOKEN_MEMORY[token_key] = new_value
            return new_value

        return match.group(0)

    # 5. Wykonanie podmiany
    final_text = re.sub(SYNTHETIC_PATTERN, replacer, anon_text)

    return final_text


# --- Blok Uruchamiający (bez zmian) ---
if __name__ == '__main__':

    if len(sys.argv) < 2:
        print("Użycie: python synthetic_generator.py <ścieżka_do_pliku.txt>")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            anon_input = f.read()

        synthetic_output = generate_synthetic_output(anon_input)
        print("--- Oryginalna Zanonimizowana Treść ---")
        print(anon_input)
        print("\n--- Treść Syntetyczna ---")
        print(synthetic_output)

    except FileNotFoundError:
        print(f"Błąd: Plik '{file_path}' nie został znaleziony.")
        sys.exit(1)