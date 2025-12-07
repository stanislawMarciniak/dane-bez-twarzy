# synthetic_data_pool.py

import random
from typing import Dict, List, Any
import datetime
import re

# --- Główne Pule Danych (PL) ---
SYNTHETIC_POOL: Dict[str, List[Any]] = {
    # 1. Dane identyfikacyjne osobowe (Z PODZIAŁEM NA PŁEĆ)
    'name-man': [
        'Piotr', 'Krzysztof', 'Andrzej', 'Tomasz', 'Jan', 'Michał', 'Paweł',
        'Adam', 'Kamil', 'Jakub', 'Filip', 'Antoni', 'Stanisław', 'Marcin',
        'Rafał', 'Robert', 'Daniel', 'Marek', 'Stefan', 'Tomek'
    ],
    'name-woman': [
        'Anna', 'Maria', 'Katarzyna', 'Małgorzata', 'Agnieszka', 'Ewa',
        'Magdalena', 'Barbara', 'Hanna', 'Zofia', 'Julia', 'Lena',
        'Maja', 'Alicja', 'Weronika', 'Natalia', 'Joanna', 'Monika'
    ],

    'surname-man': [
        'Nowak', 'Kowalski', 'Wiśniewski', 'Wójcik', 'Kowalczyk', 'Lewandowski',
        'Zieliński', 'Szymański', 'Woźniak', 'Dąbrowski', 'Kozłowski', 'Jankowski',
        'Mazur', 'Wojciechowski', 'Kwiatkowski', 'Kaczmarek', 'Krawczyk', 'Piotrowski',
        'Grabowski', 'Zając', 'Pawłowski', 'Michalski', 'Nowicki', 'Adamczyk',
        'Dudek', 'Nowakowski', 'Stępień', 'Wróbel', 'Zalewski', 'Jasiński',
        'Kruk', 'Gajewski', 'Sikora', 'Szczepański', 'Walczak', 'Baran', 'Głowacki',
        'Szewczyk', 'Ostrowski', 'Górecki', 'Chmielewski', 'Bąk', 'Włodarczyk',
        'Czarnecki', 'Sawicki', 'Lis', 'Klimczak', 'Sokołowski', 'Wieczorek',
        'Jaworski', 'Borkowski', 'Witkowski', 'Marciniak', 'Olszewski', 'Krupa',
        'Pawlak', 'Kozak', 'Barański', 'Szewc', 'Cieslak', 'Ziobro', 'Konieczny',
        'Błaszczyk', 'Gajda', 'Kubiak', 'Kopeć', 'Mazurek', 'Królikowski', 'Klimek'
    ],
    'surname-woman': [
        'Wójcik', 'Kowalczyk',
    'Woźniak',
    'Mazur',
    'Kaczmarek',
    'Krawczyk',
    'Dudek',
    'Wróbel',
    'Zając',
    'Baran',
    'Bąk',
    'Lis',
    'Kruk',
    'Kozak',
    'Pawlak',
    'Szewc',
    'Cieslak',
    'Ziobro',
    'Konieczny',
    'Kubiak',
    'Kopeć',
    'Mazurek',
    'Klimek',
    'Marciniak',
    'Walczak'
    ],
    'age': [str(x) for x in range(18, 70)],
    'sex': ['mężczyzna', 'kobieta'],
    'religion': ['katolik', 'ateista', 'ewangelik', 'buddyzm'],

    'ethnicity-man': ['Polak', 'Ukrainiec', 'Niemiec', 'Czech', 'Słowak'],
    'ethnicity-woman': ['Polka', 'Ukrainka', 'Niemka', 'Czeszka', 'Słowaczka'],
    'sexual-orientation-man': ['heteroseksualny', 'homoseksualny', 'biseksualny', 'aseksualny'],
    'sexual-orientation-woman': ['heteroseksualna', 'homoseksualna', 'biseksualna', 'aseksualna'],

    'city': ['Warszawa', 'Kraków', 'Gdańsk', 'Poznań', 'Wrocław', 'Zgierz', 'Szczecin', 'Dąbrówka', 'Borchówka', 'Włocławek', 'Bydgoszcz', 'Malbork', 'Gdynia', 'Sopot'],
    'email_domain': ['gmail.com', 'poczta.onet.pl', 'wp.pl', 'vp.pl', 'sklep.pl', 'buziaczek.pl', 'info.pl',
                     'tech.com'],
    'company': ['EkoBud Sp. z o.o.', 'TechNet S.A.', 'Global Consulting', 'Ericson',
                'EY', 'Apple Store', 'Media Expert', 'PZU', 'ZUS', 'Dino'],
    'school-name': ['Liceum nr 5 w Poznaniu', 'Uniwersytet Jagielloński', 'Liceum nr 1 w Łodzi', 'Liceum nr 1 w Bełchatowie',
                    'Uniwersytet Warszawski', 'Uniwersytet Łódzki', 'Uniwersytet Jagielloński', 'Uniwersytet Gdański'],
    'job-title-man': ['inżynier oprogramowania', 'specjalista ds. kadr', 'analityk finansowy', 'lekarz',
                      'kierownik budowy', 'programista', 'ekonomista', 'informatyk', 'nauczyciel'],
    'job-title-woman': ['inżynierka oprogramowania', 'specjalistka ds. kadr', 'analityczka finansowa', 'lekarka',
                        'kierowniczka budowy', 'programistka', 'ekonomistka', 'nauczycielka', 'informatyczka'],
    'political-view': ['lewicowe', 'prawicowe', 'neutralne', 'centrowe'],

    # 6. Identyfikatory cyfrowe
    'username': ['user_pl', 'AnonimPL', 'Tester99', 'JanKow', 'MartaW_23', 'Anonimowy1', 'Anonimowy2', 'Anonimowy3'],
    'secret': ['haslo123', 'APIKEY_XYZ', 'tajne_klucze_numeryczne'],
    'relative-man': ['brat', 'mąż', 'ojciec', 'syn', 'dziadek', 'kolega', 'szwagier'],
    'relative-woman': ['siostra', 'żona', 'matka', 'córka', 'babcia', 'koleżanka'],
    'health': ['grypa', 'angina', 'gorączka', 'migrena', 'astma', 'cukrzyca'],
}


# --- Funkcje Pomocnicze do Generowania Identyfikatorów Złożonych ---

def generate_random_phone() -> str:
    """Generuje realistyczny polski numer telefonu komórkowego."""
    prefix = "+48"
    first_digit = random.choice(['5', '6', '7', '8'])
    return f"{prefix} {first_digit}{random.randint(0, 9)}{random.randint(0, 9)} {random.randint(100, 999)} {random.randint(100, 999)}"


def generate_random_address(city: str) -> str:
    """Generuje realistyczny adres z pełnymi danymi."""
    street_types = ['ul.', 'al.', 'os.', 'pl.']
    street_names = ['Długa', 'Słoneczna', 'Kwiatowa', 'Niepodległości', 'Zielona', 'Akacjowa', 'Leśna']

    postal_code = f"{random.randint(10, 99)}-{random.randint(100, 999)}"
    street_name = random.choice(street_names)
    house_num = random.randint(1, 150)
    flat_num = random.choice([f'/{random.randint(1, 20)}', ''])

    return f"{random.choice(street_types)} {street_name} {house_num}{flat_num}, {postal_code} {city}"


def generate_random_email(name: str, surname: str) -> str:
    """Tworzy realistyczny adres e-mail."""

    def normalize(text):
        text = text.lower()
        replacements = {'ą': 'a', 'ę': 'e', 'ł': 'l', 'ś': 's', 'ć': 'c', 'ń': 'n', 'ó': 'o', 'ź': 'z', 'ż': 'z'}
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    name_part = normalize(name)
    surname_part = normalize(surname)

    username_options = [
        f"{name_part[0]}{surname_part}",
        f"{name_part}.{surname_part}",
        f"{surname_part}{random.randint(10, 99)}",
        f"{name_part}{surname_part}{random.randint(1, 5)}"
    ]
    username = random.choice(username_options)
    domain = random.choice(SYNTHETIC_POOL['email_domain'])

    return f"{username}@{domain}"


def generate_random_date(start_year: int = 1990, end_year: int = 2025) -> str:
    """Generuje losową datę w formacie dd.mm.rrrr r."""
    start_date = datetime.date(start_year, 1, 1)
    end_date = datetime.date(end_year, 12, 31)

    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    random_date = start_date + datetime.timedelta(days=random_number_of_days)

    return random_date.strftime("%d.%m.%Y r.")


def generate_random_pesel() -> str:
    """Generuje losowy ciąg 11 cyfr (UPROSZCZONY)."""
    return ''.join([str(random.randint(0, 9)) for _ in range(11)])


def generate_random_bank_account() -> str:
    """Generuje losowy numer konta (26 cyfr, UPROSZCZONY)."""
    return f"PL{''.join([str(random.randint(0, 9)) for _ in range(24)])}"


def generate_random_document_number() -> str:
    """Generuje losowy numer dokumentu (np. seria i 6 cyfr, UPROSZCZONY)."""
    letters = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=3))
    numbers = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    return f"{letters} {numbers}"


def generate_random_credit_card_number() -> str:
    """Generuje losowy numer karty (16 cyfr, UPROSZCZONY)."""
    groups = [''.join([str(random.randint(0, 9)) for _ in range(4)]) for _ in range(4)]
    return ' '.join(groups)

