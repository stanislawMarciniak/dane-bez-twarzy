"""
Generator Danych Syntetycznych
Podmienia tokeny zastępcze na realistyczne dane z zachowaniem spójności morfologicznej.
"""

import random
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

from .regex_layer import EntityType
from .morphology import Case, Gender, Number, PolishInflector

logger = logging.getLogger(__name__)


@dataclass
class SyntheticEntity:
    """Wygenerowana encja syntetyczna."""
    original_token: str
    replacement: str
    entity_type: EntityType
    morphology: Optional[Dict] = None


class PolishDataGenerator:
    """
    Generator polskich danych osobowych i innych encji.
    """
    
    # Imiona męskie
    MALE_NAMES = [
        "Adam", "Adrian", "Aleksander", "Andrzej", "Antoni", "Artur", "Bartosz",
        "Błażej", "Bogdan", "Cezary", "Damian", "Daniel", "Dawid", "Dominik",
        "Edward", "Emil", "Filip", "Franciszek", "Gabriel", "Grzegorz", "Henryk",
        "Hubert", "Igor", "Jacek", "Jakub", "Jan", "Janusz", "Jarosław", "Jerzy",
        "Józef", "Kamil", "Karol", "Kazimierz", "Konrad", "Krzysztof", "Leon",
        "Leszek", "Łukasz", "Maciej", "Marcel", "Marcin", "Marek", "Mariusz",
        "Mateusz", "Michał", "Mieczysław", "Mikołaj", "Norbert", "Oskar", "Patryk",
        "Paweł", "Piotr", "Przemysław", "Radosław", "Rafał", "Robert", "Roman",
        "Sebastian", "Sławomir", "Stanisław", "Stefan", "Szymon", "Tadeusz",
        "Tomasz", "Waldemar", "Wiktor", "Witold", "Wojciech", "Zbigniew", "Zenon"
    ]
    
    # Imiona żeńskie
    FEMALE_NAMES = [
        "Agata", "Agnieszka", "Aleksandra", "Alicja", "Amelia", "Anna", "Barbara",
        "Beata", "Bożena", "Celina", "Dagmara", "Danuta", "Daria", "Diana",
        "Dominika", "Dorota", "Edyta", "Elżbieta", "Emilia", "Ewa", "Ewelina",
        "Gabriela", "Grażyna", "Halina", "Hanna", "Helena", "Ilona", "Irena",
        "Iwona", "Izabela", "Jadwiga", "Janina", "Joanna", "Jolanta", "Julia",
        "Justyna", "Kamila", "Karolina", "Katarzyna", "Kinga", "Klaudia", "Kornelia",
        "Krystyna", "Laura", "Lena", "Lidia", "Lucyna", "Magdalena", "Maja",
        "Małgorzata", "Maria", "Marlena", "Marta", "Martyna", "Milena", "Monika",
        "Natalia", "Nina", "Oliwia", "Patrycja", "Paulina", "Renata", "Sandra",
        "Sara", "Sylwia", "Teresa", "Urszula", "Wanda", "Weronika", "Wiktoria",
        "Zofia", "Zuzanna"
    ]
    
    # Nazwiska (odmiana męska/żeńska)
    SURNAMES_BASE = [
        "Nowak", "Kowalski", "Wiśniewski", "Wójcik", "Kowalczyk", "Kamiński",
        "Lewandowski", "Zieliński", "Szymański", "Woźniak", "Dąbrowski", "Kozłowski",
        "Jankowski", "Mazur", "Wojciechowski", "Kwiatkowski", "Krawczyk", "Kaczmarek",
        "Piotrowski", "Grabowski", "Zając", "Pawłowski", "Michalski", "Król",
        "Wieczorek", "Jabłoński", "Wróbel", "Nowakowski", "Majewski", "Olszewski",
        "Stępień", "Malinowski", "Jaworski", "Adamczyk", "Dudek", "Pawlak",
        "Górski", "Witkowski", "Walczak", "Sikora", "Baran", "Rutkowski",
        "Michalak", "Szewczyk", "Ostrowski", "Tomaszewski", "Pietrzak", "Marciniak"
    ]
    
    # Polskie miasta
    CITIES = [
        "Warszawa", "Kraków", "Poznań", "Gdańsk", "Szczecin",
        "Bydgoszcz", "Lublin", "Białystok", "Katowice", "Gdynia", "Częstochowa",
        "Radom", "Sosnowiec", "Toruń", "Kielce", "Rzeszów", "Gliwice", "Zabrze",
        "Olsztyn", "Bielsko-Biała", "Bytom", "Zielona Góra", "Rybnik", "Ruda Śląska",
        "Opole", "Tychy", "Płock", "Elbląg", "Wałbrzych", "Włocławek", "Tarnów",
        "Chorzów", "Koszalin", "Kalisz", "Legnica", "Grudziądz", "Jaworzno", "Słupsk"
    ]
    
    # Ulice
    STREETS = [
        "Główna", "Polna", "Leśna", "Słoneczna", "Krótka", "Szkolna", "Ogrodowa",
        "Lipowa", "Brzozowa", "Łąkowa", "Kwiatowa", "Parkowa", "Zielona", "Kościelna",
        "Akacjowa", "Kolejowa", "Sportowa", "Długa", "Sosnowa", "Klonowa", "Nowa",
        "Piaskowa", "Graniczna", "Spacerowa", "Topolowa", "Wiejska", "Cicha",
        "Dębowa", "Jasna", "Kasztanowa", "Łukasiewicza", "Mickiewicza", "Sienkiewicza",
        "Słowackiego", "Kopernika", "Wojska Polskiego", "Piłsudskiego", "Reymonta"
    ]
    
    # Firmy
    COMPANIES = [
        "TechPol Sp. z o.o.", "Novasoft S.A.", "Grupa Kapitałowa XYZ", 
        "DataStream Polska", "CloudNet Systems", "EuroConsulting", "PolBud S.A.",
        "MediaHouse Sp. z o.o.", "GreenEnergy Polska", "FinanceExpert",
        "LogisTrans", "BioMed Solutions", "AutoParts Sp. z o.o.", "FoodFactory S.A.",
        "SmartCity Technologies", "SafeBank Polska", "DigiMedia Group",
        "InnoTech Labs", "EcoSystems Sp. z o.o.", "CyberSecurity Pro"
    ]
    
    # Szkoły
    SCHOOLS = [
        "Szkoła Podstawowa nr 1", "Liceum Ogólnokształcące im. Adama Mickiewicza",
        "Technikum Informatyczne", "Zespół Szkół Technicznych",
        "Gimnazjum nr 5", "Uniwersytet Warszawski", "Politechnika Wrocławska",
        "Akademia Górniczo-Hutnicza", "Uniwersytet Jagielloński",
        "Szkoła Główna Handlowa", "Politechnika Gdańska",
        "Wyższa Szkoła Informatyki", "Akademia Muzyczna",
        "Uniwersytet Ekonomiczny", "Collegium Medicum"
    ]
    
    # Stanowiska
    JOB_TITLES = [
        "kierownik", "dyrektor", "specjalista", "analityk", "programista",
        "inżynier", "księgowy", "handlowiec", "konsultant", "menedżer",
        "asystent", "koordynator", "projektant", "technik", "administrator",
        "prawnik", "lekarz", "nauczyciel", "sprzedawca", "recepcjonista",
        "magazynier", "kurier", "operator", "sekretarka", "referent"
    ]
    
    # Religie
    RELIGIONS = [
        "katolik", "protestant", "prawosławny", "muzułmanin", "buddysta",
        "żyd", "hinduista", "ateista", "agnostyk", "świadek Jehowy"
    ]
    
    # Poglądy polityczne
    POLITICAL_VIEWS = [
        "konserwatysta", "liberał", "socjaldemokrata", "centrysta",
        "prawicowiec", "lewicowiec", "umiarkowany", "niezależny"
    ]
    
    # Pochodzenie etniczne
    ETHNICITIES = [
        "Polak", "Ukrainiec", "Białorusin", "Niemiec", "Rosjanin",
        "Litwin", "Wietnamczyk", "Rom", "Ślązak", "Kaszub"
    ]
    
    # Orientacje
    ORIENTATIONS = [
        "heteroseksualny", "homoseksualny", "biseksualny"
    ]
    
    # Relacje rodzinne (formy)
    RELATIVES = {
        'male': ["brat", "ojciec", "syn", "dziadek", "wujek", "kuzyn", "mąż", "zięć", "teść"],
        'female': ["siostra", "matka", "córka", "babcia", "ciocia", "kuzynka", "żona", "synowa", "teściowa"]
    }
    
    # Domeny email
    EMAIL_DOMAINS = [
        "gmail.com", "wp.pl", "onet.pl", "o2.pl", "interia.pl",
        "poczta.fm", "yahoo.com", "outlook.com", "hotmail.com"
    ]
    
    def __init__(self, seed: Optional[int] = None):
        """
        Inicjalizuje generator.
        
        Args:
            seed: Ziarno dla powtarzalności wyników
        """
        if seed is not None:
            random.seed(seed)
        
        self.inflector = PolishInflector()
        self._name_gender_cache: Dict[str, str] = {}
    
    def generate(
        self,
        entity_type: EntityType,
        morphology: Optional[Dict] = None,
        context: Optional[str] = None
    ) -> str:
        """
        Generuje syntetyczną wartość dla danego typu encji.
        
        Args:
            entity_type: Typ encji
            morphology: Informacje morfologiczne do zachowania
            context: Kontekst tekstowy
            
        Returns:
            Wygenerowana wartość
        """
        generators = {
            EntityType.NAME: self._generate_name,
            EntityType.SURNAME: self._generate_surname,
            EntityType.AGE: self._generate_age,
            EntityType.DATE_OF_BIRTH: self._generate_date,
            EntityType.DATE: self._generate_date,
            EntityType.SEX: self._generate_sex,
            EntityType.RELIGION: self._generate_religion,
            EntityType.POLITICAL_VIEW: self._generate_political,
            EntityType.ETHNICITY: self._generate_ethnicity,
            EntityType.SEXUAL_ORIENTATION: self._generate_orientation,
            EntityType.HEALTH: self._generate_health,
            EntityType.RELATIVE: self._generate_relative,
            EntityType.CITY: self._generate_city,
            EntityType.ADDRESS: self._generate_address,
            EntityType.EMAIL: self._generate_email,
            EntityType.PHONE: self._generate_phone,
            EntityType.PESEL: self._generate_pesel,
            EntityType.DOCUMENT_NUMBER: self._generate_document,
            EntityType.COMPANY: self._generate_company,
            EntityType.SCHOOL_NAME: self._generate_school,
            EntityType.JOB_TITLE: self._generate_job,
            EntityType.BANK_ACCOUNT: self._generate_bank_account,
            EntityType.CREDIT_CARD_NUMBER: self._generate_credit_card,
            EntityType.USERNAME: self._generate_username,
            EntityType.SECRET: self._generate_secret,
        }
        
        generator = generators.get(entity_type, lambda m, c: "[UNKNOWN]")
        return generator(morphology, context)
    
    def _generate_name(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje imię z zachowaniem morfologii."""
        # Określ płeć z morfologii lub losowo
        gender = None
        if morphology and morphology.get('gender'):
            gender = 'female' if morphology['gender'] == 'f' else 'male'
        else:
            gender = random.choice(['male', 'female'])
        
        names = self.FEMALE_NAMES if gender == 'female' else self.MALE_NAMES
        name = random.choice(names)
        
        # Odmień przez przypadki jeśli wymagane
        if morphology and morphology.get('case'):
            case_map = {
                'nom': Case.NOMINATIVE,
                'gen': Case.GENITIVE,
                'dat': Case.DATIVE,
                'acc': Case.ACCUSATIVE,
                'ins': Case.INSTRUMENTAL,
                'loc': Case.LOCATIVE,
                'voc': Case.VOCATIVE,
            }
            target_case = case_map.get(morphology['case'], Case.NOMINATIVE)
            gender_enum = Gender.FEMININE if gender == 'female' else Gender.MASCULINE_PERSONAL
            name = self.inflector.inflect(name, target_case, gender_enum)
        
        return name
    
    def _generate_surname(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje nazwisko z zachowaniem morfologii."""
        base = random.choice(self.SURNAMES_BASE)
        
        # Określ płeć
        gender = 'male'
        if morphology and morphology.get('gender'):
            gender = 'female' if morphology['gender'] == 'f' else 'male'
        
        # Dostosuj końcówkę dla kobiet
        if gender == 'female':
            if base.endswith('ski'):
                base = base[:-1] + 'a'  # Kowalski -> Kowalska
            elif base.endswith('cki'):
                base = base[:-1] + 'a'
            elif base.endswith('ny'):
                base = base[:-1] + 'a'
        
        # Odmień przez przypadki
        if morphology and morphology.get('case'):
            case_map = {
                'nom': Case.NOMINATIVE,
                'gen': Case.GENITIVE,
                'dat': Case.DATIVE,
                'acc': Case.ACCUSATIVE,
                'ins': Case.INSTRUMENTAL,
                'loc': Case.LOCATIVE,
                'voc': Case.VOCATIVE,
            }
            target_case = case_map.get(morphology['case'], Case.NOMINATIVE)
            gender_enum = Gender.FEMININE if gender == 'female' else Gender.MASCULINE_PERSONAL
            base = self.inflector.inflect(base, target_case, gender_enum)
        
        return base
    
    def _generate_age(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje wiek."""
        age = random.randint(18, 80)
        
        # Zachowaj kontekst (np. "25 lat", "wiek: 30")
        if context:
            if "lat" in context.lower():
                return f"{age} lat"
            elif "wiek" in context.lower():
                return str(age)
        
        return str(age)
    
    def _generate_date(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje datę."""
        # Losowa data z ostatnich 50 lat
        start = datetime(1970, 1, 1)
        end = datetime.now()
        delta = end - start
        random_days = random.randint(0, delta.days)
        date = start + timedelta(days=random_days)
        
        # Różne formaty
        formats = [
            "%d.%m.%Y",
            "%d-%m-%Y",
            "%Y-%m-%d",
            "%d/%m/%Y"
        ]
        
        return date.strftime(random.choice(formats))
    
    def _generate_sex(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje płeć."""
        return random.choice(["mężczyzna", "kobieta"])
    
    def _generate_religion(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje wyznanie."""
        return random.choice(self.RELIGIONS)
    
    def _generate_political(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje poglądy polityczne."""
        return random.choice(self.POLITICAL_VIEWS)
    
    def _generate_ethnicity(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje pochodzenie etniczne."""
        return random.choice(self.ETHNICITIES)
    
    def _generate_orientation(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje orientację seksualną."""
        return random.choice(self.ORIENTATIONS)
    
    def _generate_health(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje dane zdrowotne (zastępuje ogólnikiem)."""
        conditions = [
            "schorzenie przewlekłe",
            "stan po operacji",
            "choroba zakaźna",
            "zaburzenie metaboliczne",
            "problem kardiologiczny"
        ]
        return random.choice(conditions)
    
    def _generate_relative(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje relację rodzinną."""
        gender = random.choice(['male', 'female'])
        relative = random.choice(self.RELATIVES[gender])
        name = self._generate_name({'gender': 'f' if gender == 'female' else 'm'}, None)
        return f"{relative} {name}"
    
    def _generate_city(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje nazwę miasta z odmianą."""
        city = random.choice(self.CITIES)
        
        if morphology and morphology.get('case'):
            case_map = {
                'nom': Case.NOMINATIVE,
                'gen': Case.GENITIVE,
                'dat': Case.DATIVE,
                'acc': Case.ACCUSATIVE,
                'ins': Case.INSTRUMENTAL,
                'loc': Case.LOCATIVE,
                'voc': Case.VOCATIVE,
            }
            target_case = case_map.get(morphology['case'], Case.NOMINATIVE)
            city = self.inflector.inflect(city, target_case)
        
        return city
    
    def _generate_address(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje pełny adres."""
        city = random.choice(self.CITIES)
        street = random.choice(self.STREETS)
        number = random.randint(1, 150)
        apt = random.randint(1, 50) if random.random() > 0.5 else None
        postal = f"{random.randint(10, 99)}-{random.randint(100, 999)}"
        
        if apt:
            return f"ul. {street} {number}/{apt}, {postal} {city}"
        else:
            return f"ul. {street} {number}, {postal} {city}"
    
    def _generate_email(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje adres email."""
        name = random.choice(self.MALE_NAMES + self.FEMALE_NAMES).lower()
        surname = random.choice(self.SURNAMES_BASE).lower()
        domain = random.choice(self.EMAIL_DOMAINS)
        
        patterns = [
            f"{name}.{surname}@{domain}",
            f"{name}{random.randint(1, 99)}@{domain}",
            f"{name[0]}{surname}@{domain}",
            f"{surname}.{name}@{domain}"
        ]
        
        return random.choice(patterns)
    
    def _generate_phone(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje numer telefonu."""
        formats = [
            "+48 {0}{1}{2} {3}{4}{5} {6}{7}{8}",
            "{0}{1}{2}-{3}{4}{5}-{6}{7}{8}",
            "{0}{1}{2} {3}{4}{5} {6}{7}{8}",
            "+48{0}{1}{2}{3}{4}{5}{6}{7}{8}"
        ]
        
        digits = [str(random.randint(0, 9)) for _ in range(9)]
        # Pierwszy cyfra nie może być 0
        digits[0] = str(random.randint(1, 9))
        
        return random.choice(formats).format(*digits)
    
    def _generate_pesel(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje prawidłowy numer PESEL."""
        # Data urodzenia (losowa)
        year = random.randint(1950, 2005)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        
        # Kodowanie roku
        if year >= 2000:
            month += 20
        
        yy = year % 100
        
        # Kolejne 4 cyfry (numer serii + płeć)
        serial = random.randint(0, 999)
        gender_digit = random.choice([0, 2, 4, 6, 8]) if random.random() > 0.5 else random.choice([1, 3, 5, 7, 9])
        
        # Składamy 10 pierwszych cyfr
        pesel_str = f"{yy:02d}{month:02d}{day:02d}{serial:03d}{gender_digit}"
        
        # Obliczamy sumę kontrolną
        weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
        checksum = sum(int(d) * w for d, w in zip(pesel_str, weights)) % 10
        control = (10 - checksum) % 10
        
        return pesel_str + str(control)
    
    def _generate_document(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje numer dokumentu."""
        doc_types = [
            lambda: "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=3)) + 
                    "".join(random.choices("0123456789", k=6)),  # Dowód
            lambda: "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=2)) + 
                    "".join(random.choices("0123456789", k=7)),  # Paszport
        ]
        
        return random.choice(doc_types)()
    
    def _generate_company(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje nazwę firmy."""
        return random.choice(self.COMPANIES)
    
    def _generate_school(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje nazwę szkoły."""
        return random.choice(self.SCHOOLS)
    
    def _generate_job(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje stanowisko."""
        return random.choice(self.JOB_TITLES)
    
    def _generate_bank_account(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje numer konta bankowego."""
        # Format IBAN PL
        digits = "".join(str(random.randint(0, 9)) for _ in range(26))
        return f"PL{digits[:2]} {digits[2:6]} {digits[6:10]} {digits[10:14]} {digits[14:18]} {digits[18:22]} {digits[22:26]}"
    
    def _generate_credit_card(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje numer karty kredytowej (z prawidłową sumą Luhna)."""
        # Prefix dla różnych kart
        prefixes = ["4", "51", "52", "53", "54", "55"]  # Visa, Mastercard
        prefix = random.choice(prefixes)
        
        # Generuj cyfry
        remaining = 15 - len(prefix)
        digits = prefix + "".join(str(random.randint(0, 9)) for _ in range(remaining))
        
        # Oblicz cyfrę kontrolną (Luhn)
        def luhn_checksum(card_number):
            def digits_of(n):
                return [int(d) for d in str(n)]
            
            digits = digits_of(card_number)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d * 2))
            
            return checksum % 10
        
        check_digit = (10 - luhn_checksum(int(digits + "0"))) % 10
        card = digits + str(check_digit)
        
        return f"{card[:4]} {card[4:8]} {card[8:12]} {card[12:16]}"
    
    def _generate_username(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje nazwę użytkownika."""
        name = random.choice(self.MALE_NAMES + self.FEMALE_NAMES).lower()
        patterns = [
            f"{name}{random.randint(1, 999)}",
            f"{name}_{random.choice(['pl', 'dev', 'pro', 'user'])}",
            f"@{name}{random.randint(1, 99)}",
        ]
        return random.choice(patterns)
    
    def _generate_secret(
        self,
        morphology: Optional[Dict],
        context: Optional[str]
    ) -> str:
        """Generuje zastępczy sekret."""
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%"
        length = random.randint(8, 16)
        return "".join(random.choices(chars, k=length))


class SyntheticDataPipeline:
    """
    Pipeline do generacji danych syntetycznych z zachowaniem spójności morfologicznej.
    """
    
    def __init__(self, seed: Optional[int] = None):
        self.generator = PolishDataGenerator(seed=seed)
        
        # Regex do parsowania tokenów z metadanymi (format: [typ] lub [typ|metadata])
        self.token_pattern = re.compile(
            r'\[([a-z-]+)(?:\|([^\]]+))?\]'
        )
    
    def generate_synthetic_text(
        self,
        anonymized_text: str,
        intermediate_text: Optional[str] = None
    ) -> str:
        """
        Generuje tekst syntetyczny na podstawie zanonimizowanego tekstu.
        
        Args:
            anonymized_text: Tekst z tokenami zastępczymi (np. [name])
            intermediate_text: Opcjonalny tekst pośredni z metadanymi (np. [name|case=acc])
            
        Returns:
            Tekst z wygenerowanymi danymi syntetycznymi
        """
        # Użyj pośredniego jeśli dostępny (ma metadane)
        source_text = intermediate_text or anonymized_text
        
        result = source_text
        
        # Znajdź wszystkie tokeny
        for match in self.token_pattern.finditer(source_text):
            full_match = match.group(0)
            entity_type_str = match.group(1)
            metadata_str = match.group(2)
            
            # Parsuj typ encji
            try:
                entity_type = EntityType(entity_type_str)
            except ValueError:
                logger.warning(f"Nieznany typ encji: {entity_type_str}")
                continue
            
            # Parsuj metadane morfologiczne
            morphology = {}
            if metadata_str:
                for part in metadata_str.split('|'):
                    if '=' in part:
                        key, value = part.split('=', 1)
                        morphology[key] = value
            
            # Generuj zamiennik
            replacement = self.generator.generate(entity_type, morphology)
            
            # Podmień (tylko pierwsze wystąpienie, żeby nie podmienić już zamienionych)
            result = result.replace(full_match, replacement, 1)
        
        return result
    
    def batch_generate(
        self,
        texts: List[str],
        intermediate_texts: Optional[List[str]] = None
    ) -> List[str]:
        """
        Generuje dane syntetyczne dla wielu tekstów.
        """
        if intermediate_texts:
            return [
                self.generate_synthetic_text(anon, inter)
                for anon, inter in zip(texts, intermediate_texts)
            ]
        else:
            return [self.generate_synthetic_text(text) for text in texts]


# Testy
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test generatora
    generator = PolishDataGenerator(seed=42)
    
    print("=== Test generatora ===")
    print(f"Imię (żeńskie, biernik): {generator.generate(EntityType.NAME, {'gender': 'f', 'case': 'acc'})}")
    print(f"Nazwisko: {generator.generate(EntityType.SURNAME)}")
    print(f"PESEL: {generator.generate(EntityType.PESEL)}")
    print(f"Email: {generator.generate(EntityType.EMAIL)}")
    print(f"Telefon: {generator.generate(EntityType.PHONE)}")
    print(f"Adres: {generator.generate(EntityType.ADDRESS)}")
    print(f"Miasto (miejscownik): {generator.generate(EntityType.CITY, {'case': 'loc'})}")
    print(f"Firma: {generator.generate(EntityType.COMPANY)}")
    print(f"Karta kredytowa: {generator.generate(EntityType.CREDIT_CARD_NUMBER)}")
    
    # Test pipeline
    pipeline = SyntheticDataPipeline(seed=42)
    
    print("\n=== Test pipeline ===")
    
    # Prosty przypadek
    anonymized = "Nazywam się [name] [surname], mieszkam w [city]."
    synthetic = pipeline.generate_synthetic_text(anonymized)
    print(f"Input:  {anonymized}")
    print(f"Output: {synthetic}")
    
    # Z metadanymi morfologicznymi
    intermediate = "Widziałem [name|case=acc|gender=f] w [city|case=loc]."
    synthetic = pipeline.generate_synthetic_text(anonymized, intermediate)
    print(f"\nIntermediate: {intermediate}")
    print(f"Output: {synthetic}")
    
    # Złożony przykład
    complex_text = """
    Pacjent: [name] [surname]
    PESEL: [pesel]
    Adres: [address]
    Tel: [phone]
    Email: [email]
    Data wizyty: [date]
    Diagnoza: [health]
    """
    
    print("\n=== Złożony przykład ===")
    print(pipeline.generate_synthetic_text(complex_text))