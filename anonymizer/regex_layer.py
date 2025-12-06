"""
Warstwa Regułowa (Regex) - "Szybkie Sito"
Wykrywa encje o stałym formacie: PESEL, email, telefon, numery kont, daty, IP.

Optymalizacje:
- Prekompilowane wzorce
- LRU cache dla walidacji
- Rozszerzone wzorce dla polskich dokumentów
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, Tuple
from enum import Enum
from functools import lru_cache
import hashlib


class EntityType(Enum):
    """Typy encji obsługiwane przez system."""
    # Dane identyfikacyjne
    NAME = "name"
    SURNAME = "surname"
    AGE = "age"
    DATE_OF_BIRTH = "date-of-birth"
    DATE = "date"
    SEX = "sex"
    RELIGION = "religion"
    POLITICAL_VIEW = "political-view"
    ETHNICITY = "ethnicity"
    SEXUAL_ORIENTATION = "sexual-orientation"
    HEALTH = "health"
    RELATIVE = "relative"
    
    # Dane kontaktowe i lokalizacyjne
    CITY = "city"
    ADDRESS = "address"
    EMAIL = "email"
    PHONE = "phone"
    
    # Identyfikatory dokumentów
    PESEL = "pesel"
    DOCUMENT_NUMBER = "document-number"
    
    # Dane zawodowe
    COMPANY = "company"
    SCHOOL_NAME = "school-name"
    JOB_TITLE = "job-title"
    
    # Informacje finansowe
    BANK_ACCOUNT = "bank-account"
    CREDIT_CARD_NUMBER = "credit-card-number"
    
    # Identyfikatory cyfrowe
    USERNAME = "username"
    SECRET = "secret"


@dataclass
class DetectedEntity:
    """Reprezentacja wykrytej encji."""
    text: str
    entity_type: EntityType
    start: int
    end: int
    confidence: float
    source: str  # 'regex' lub 'ml'
    morphology: Optional[Dict] = field(default=None)
    
    def to_token(self, include_morphology: bool = False) -> str:
        """Konwertuje encję na token zastępczy."""
        if include_morphology and self.morphology:
            morph_str = "|".join(f"{k}={v}" for k, v in self.morphology.items())
            return f"[{self.entity_type.value}|{morph_str}]"
        return f"[{self.entity_type.value}]"
    
    def __hash__(self):
        return hash((self.text, self.entity_type, self.start, self.end))
    
    def __eq__(self, other):
        if not isinstance(other, DetectedEntity):
            return False
        return (self.text == other.text and 
                self.entity_type == other.entity_type and
                self.start == other.start and 
                self.end == other.end)


class RegexLayer:
    """
    Warstwa regułowa do wykrywania encji o stałym formacie.
    Zapewnia wysoką precyzję i szybkość dla danych strukturalnych.
    """
    
    # Wagi kontrolne PESEL
    PESEL_WEIGHTS = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
    
    # Polskie miesiące
    POLISH_MONTHS = (
        'stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca',
        'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'
    )
    
    def __init__(self, cache_size: int = 1024):
        self._cache_size = cache_size
        self._compile_patterns()
        self._result_cache: Dict[str, List[DetectedEntity]] = {}
    
    def _compile_patterns(self):
        """Kompiluje wszystkie wzorce regex."""
        
        # === PESEL ===
        self.pesel_pattern = re.compile(r'\b(\d{11})\b')
        
        # === Email ===
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b',
            re.IGNORECASE
        )
        
        # === Telefon ===
        self.phone_patterns = [
            re.compile(r'\+48[-\s]?(\d{3}[-\s]?\d{3}[-\s]?\d{3}|\d{9})'),
            re.compile(r'\(?\d{2}\)?[-\s]?\d{3}[-\s]?\d{2}[-\s]?\d{2}'),
            re.compile(r'(?<!\d)\d{3}[-\s]\d{3}[-\s]\d{3}(?!\d)'),
            re.compile(r'(?:tel\.?|telefon|nr tel\.?|numer)[:\s]*(\d{9})', re.IGNORECASE),
        ]
        
        # === Konto bankowe ===
        self.bank_account_patterns = [
            re.compile(r'\bPL[-\s]?(\d{2}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4})\b'),
            re.compile(r'\b(\d{2}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4})\b'),
            re.compile(r'(?:konto|rachunek|nr konta)[:\s]*(\d{26})\b', re.IGNORECASE),
        ]
        
        # === Karta kredytowa ===
        self.credit_card_patterns = [
            re.compile(r'\b(\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4})\b'),
            re.compile(r'(?:kart[ay]|visa|mastercard)[:\s]*(\d{16})\b', re.IGNORECASE),
        ]
        
        # === Daty ===
        self.date_patterns = [
            re.compile(r'\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\b'),
            re.compile(r'\b(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\b'),
            re.compile(r'\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2})\b'),
            re.compile(
                r'\b(\d{1,2})\s+(' + '|'.join(self.POLISH_MONTHS) + r')\s+(\d{4})(\s*r\.?)?\b',
                re.IGNORECASE
            ),
        ]
        
        self.dob_context = re.compile(
            r'(urodzony|urodzona|urodzenia|ur\.|data ur|dob)[:\s]*',
            re.IGNORECASE
        )
        
        # === Dokumenty ===
        self.document_patterns = [
            re.compile(r'\b([A-Z]{3}\d{6})\b'),
            re.compile(r'\b([A-Z]{2}\d{7})\b'),
            re.compile(r'\b(\d{5}/\d{2}/\d{4})\b'),
            re.compile(r'(?:dowód|paszport|prawo jazdy)[:\s]*([A-Z0-9]{7,9})\b', re.IGNORECASE),
        ]
        
        # === Wiek ===
        self.age_patterns = [
            re.compile(r'\b(\d{1,3})\s*[-]?\s*(lat|lata|rok|roku|letni[aey]?|latek)\b', re.IGNORECASE),
            re.compile(r'\b(?:wiek|lat)[:\s]+(\d{1,3})\b', re.IGNORECASE),
            re.compile(r'\bw\s+wieku\s+(\d{1,3})\s*(lat|lata)?\b', re.IGNORECASE),
        ]
        
        # === Kod pocztowy ===
        self.postal_code_pattern = re.compile(r'\b(\d{2}-\d{3})\b')
        
        # === Adresy ===
        self.address_patterns = [
            re.compile(
                r'(?:ul\.?|ulica|al\.?|aleja|os\.?|osiedle|pl\.?|plac)\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?\s+\d+(?:[a-z])?(?:\s*/\s*\d+)?',
                re.IGNORECASE
            ),
        ]
        
        # === IP ===
        self.ip_pattern = re.compile(
            r'\b((?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'
        )
        
        # === Sekrety ===
        self.secret_patterns = [
            re.compile(r'(?:hasło|password|pass|pwd)[:\s]+["\']?(\S{4,})["\']?', re.IGNORECASE),
            re.compile(r'(?:api[_\s]?key|token|klucz)[:\s]+["\']?(\S{8,})["\']?', re.IGNORECASE),
        ]
        
        # === Username ===
        self.username_patterns = [
            re.compile(r'(?:login|użytkownik|user|nick)[:\s]+["\']?(\S{3,})["\']?', re.IGNORECASE),
            re.compile(r'@([A-Za-z0-9_]{3,30})\b'),
        ]
        
        # === Płeć ===
        self.sex_patterns = [
            re.compile(r'(?:płeć|sex|gender)[:\s]+(mężczyzna|kobieta|m|k)\b', re.IGNORECASE),
        ]
    
    @lru_cache(maxsize=10000)
    def _validate_pesel(self, pesel: str) -> bool:
        """Waliduje sumę kontrolną PESEL."""
        if len(pesel) != 11 or not pesel.isdigit():
            return False
        
        digits = tuple(int(d) for d in pesel)
        checksum = sum(d * w for d, w in zip(digits[:10], self.PESEL_WEIGHTS)) % 10
        control = (10 - checksum) % 10
        
        return control == digits[10]
    
    @lru_cache(maxsize=10000)
    def _validate_credit_card(self, number: str) -> bool:
        """Waliduje numer karty algorytmem Luhna."""
        digits = [int(d) for d in re.sub(r'[-\s]', '', number)]
        if len(digits) != 16:
            return False
        
        checksum = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            checksum += d
        
        return checksum % 10 == 0
    
    @lru_cache(maxsize=1000)
    def _validate_ip(self, ip: str) -> bool:
        """Waliduje adres IP."""
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        
        for part in parts:
            try:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            except ValueError:
                return False
        return True
    
    def _is_valid_date(self, day: int, month: int, year: int) -> bool:
        """Sprawdza czy data jest prawidłowa."""
        if month < 1 or month > 12 or day < 1 or day > 31:
            return False
        
        if year < 100:
            year = 1900 + year if year > 30 else 2000 + year
        
        if year < 1900 or year > 2100:
            return False
        
        days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        
        if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
            days_in_month[1] = 29
        
        return day <= days_in_month[month - 1]
    
    def _get_text_hash(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()
    
    def detect(self, text: str, use_cache: bool = True) -> List[DetectedEntity]:
        """
        Wykrywa wszystkie encje w tekście.
        
        Args:
            text: Tekst do analizy
            use_cache: Czy używać cache
            
        Returns:
            Lista wykrytych encji
        """
        if use_cache:
            text_hash = self._get_text_hash(text)
            if text_hash in self._result_cache:
                return self._result_cache[text_hash].copy()
        
        entities: List[DetectedEntity] = []
        occupied_ranges: Set[Tuple[int, int]] = set()
        
        def add_entity(entity: DetectedEntity) -> bool:
            for start, end in occupied_ranges:
                if not (entity.end <= start or entity.start >= end):
                    return False
            entities.append(entity)
            occupied_ranges.add((entity.start, entity.end))
            return True
        
        # PESEL
        for match in self.pesel_pattern.finditer(text):
            pesel = match.group(1)
            if self._validate_pesel(pesel):
                add_entity(DetectedEntity(
                    text=pesel,
                    entity_type=EntityType.PESEL,
                    start=match.start(1),
                    end=match.end(1),
                    confidence=0.99,
                    source='regex'
                ))
        
        # Email
        for match in self.email_pattern.finditer(text):
            add_entity(DetectedEntity(
                text=match.group(),
                entity_type=EntityType.EMAIL,
                start=match.start(),
                end=match.end(),
                confidence=0.98,
                source='regex'
            ))
        
        # Telefon
        for pattern in self.phone_patterns:
            for match in pattern.finditer(text):
                add_entity(DetectedEntity(
                    text=match.group(),
                    entity_type=EntityType.PHONE,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.90,
                    source='regex'
                ))
        
        # Konto bankowe
        for pattern in self.bank_account_patterns:
            for match in pattern.finditer(text):
                add_entity(DetectedEntity(
                    text=match.group(),
                    entity_type=EntityType.BANK_ACCOUNT,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95,
                    source='regex'
                ))
        
        # Karta kredytowa
        for pattern in self.credit_card_patterns:
            for match in pattern.finditer(text):
                number = re.sub(r'[-\s]', '', match.group(1) if match.lastindex else match.group())
                if len(number) == 16 and self._validate_credit_card(number):
                    add_entity(DetectedEntity(
                        text=match.group(),
                        entity_type=EntityType.CREDIT_CARD_NUMBER,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.97,
                        source='regex'
                    ))
        
        # Adresy
        for pattern in self.address_patterns:
            for match in pattern.finditer(text):
                add_entity(DetectedEntity(
                    text=match.group(),
                    entity_type=EntityType.ADDRESS,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.85,
                    source='regex'
                ))
        
        # Daty
        for i, pattern in enumerate(self.date_patterns):
            for match in pattern.finditer(text):
                context_start = max(0, match.start() - 30)
                context = text[context_start:match.start()].lower()
                
                is_dob = bool(self.dob_context.search(context))
                entity_type = EntityType.DATE_OF_BIRTH if is_dob else EntityType.DATE
                
                if i < 3:
                    try:
                        groups = match.groups()
                        if i == 1:
                            year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                        else:
                            day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                        
                        if not self._is_valid_date(day, month, year):
                            continue
                    except (ValueError, IndexError):
                        continue
                
                add_entity(DetectedEntity(
                    text=match.group(),
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.85 if is_dob else 0.80,
                    source='regex'
                ))
        
        # Dokumenty
        for pattern in self.document_patterns:
            for match in pattern.finditer(text):
                add_entity(DetectedEntity(
                    text=match.group(),
                    entity_type=EntityType.DOCUMENT_NUMBER,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.88,
                    source='regex'
                ))
        
        # Wiek
        for pattern in self.age_patterns:
            for match in pattern.finditer(text):
                try:
                    age_value = int(match.group(1))
                    if 0 < age_value < 130:
                        add_entity(DetectedEntity(
                            text=match.group(),
                            entity_type=EntityType.AGE,
                            start=match.start(),
                            end=match.end(),
                            confidence=0.80,
                            source='regex'
                        ))
                except (ValueError, IndexError):
                    pass
        
        # Kod pocztowy
        for match in self.postal_code_pattern.finditer(text):
            already_covered = any(
                e.start <= match.start() and e.end >= match.end()
                for e in entities if e.entity_type == EntityType.ADDRESS
            )
            if not already_covered:
                add_entity(DetectedEntity(
                    text=match.group(),
                    entity_type=EntityType.ADDRESS,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.75,
                    source='regex'
                ))
        
        # IP
        for match in self.ip_pattern.finditer(text):
            ip = match.group()
            if self._validate_ip(ip):
                add_entity(DetectedEntity(
                    text=ip,
                    entity_type=EntityType.SECRET,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.92,
                    source='regex'
                ))
        
        # Sekrety
        for pattern in self.secret_patterns:
            for match in pattern.finditer(text):
                add_entity(DetectedEntity(
                    text=match.group(),
                    entity_type=EntityType.SECRET,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.88,
                    source='regex'
                ))
        
        # Username
        for pattern in self.username_patterns:
            for match in pattern.finditer(text):
                add_entity(DetectedEntity(
                    text=match.group(),
                    entity_type=EntityType.USERNAME,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.75,
                    source='regex'
                ))
        
        # Płeć
        for pattern in self.sex_patterns:
            for match in pattern.finditer(text):
                add_entity(DetectedEntity(
                    text=match.group(),
                    entity_type=EntityType.SEX,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.90,
                    source='regex'
                ))
        
        entities.sort(key=lambda e: (e.start, -e.end))
        
        if use_cache:
            text_hash = self._get_text_hash(text)
            self._result_cache[text_hash] = entities.copy()
            if len(self._result_cache) > self._cache_size:
                keys_to_remove = list(self._result_cache.keys())[:len(self._result_cache) - self._cache_size]
                for key in keys_to_remove:
                    del self._result_cache[key]
        
        return entities
    
    def clear_cache(self):
        """Czyści cache."""
        self._result_cache.clear()
        self._validate_pesel.cache_clear()
        self._validate_credit_card.cache_clear()
        self._validate_ip.cache_clear()


if __name__ == "__main__":
    layer = RegexLayer()
    
    test_cases = [
        "Mój PESEL to 90010112345.",
        "Email: jan.kowalski@email.pl",
        "Zadzwoń: +48 123 456 789",
        "Urodziłem się 23 września 2023 r.",
        "Mam 25 lat",
        "ul. Długa 15/3",
    ]
    
    print("=== Test warstwy Regex ===\n")
    
    for text in test_cases:
        print(f"Input: {text}")
        entities = layer.detect(text)
        for e in entities:
            print(f"  -> {e.entity_type.value}: '{e.text}' ({e.confidence:.2f})")
        print()