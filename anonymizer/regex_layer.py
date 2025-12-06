"""
Warstwa Regułowa (Regex) - "Szybkie Sito"
Wykrywa encje o stałym formacie: PESEL, email, telefon, numery kont, daty.

Zastosowano logikę i kolejność operacji z regex.py.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, Tuple
from enum import Enum
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
    
    def __init__(self, cache_size: int = 1024):
        self._cache_size = cache_size
        self._compile_patterns()
        self._result_cache: Dict[str, List[DetectedEntity]] = {}
    
    def _compile_patterns(self):
        """Kompiluje wszystkie wzorce regex."""
        
        # =================================================================
        # KROK 1: Adresy
        # =================================================================
        # self.address_regex = re.compile(
        #     r"\b(?i:ul\.|ulica|al\.|aleja|aleje|pl\.|plac|os\.|osiedle|skwer|rondo)\s+" # Prefiks
        #     r"(" # Grupa 1: Nazwa ulicy
        #         r"(?:"
        #             # ZABEZPIECZENIE 1: Nie dopasowuj, jeśli tuż za spacją jest kolejny prefiks (np. "na os.")
        #             r"(?!\s+(?i:ul\.|ulica|al\.|aleja|pl\.|plac|os\.|osiedle|skwer|rondo))"
        #             r"(?:"
        #                 r"[a-zA-ZĄĆĘŁŃÓŚŹŻąćęłńóśźż0-9][\wą-ż\.-]*" # Pierwsze słowo nazwy (może być małą literą)
        #                 r"|"
        #                 r"(?i:św\.|gen\.|ks\.|bp\.|abp\.|prof\.|dr\.?|im\.|al\.|pl\.)" # Tytuły
        #                 r"|"
        #                 r"[A-Z]\.?" # Inicjały
        #             r")"
        #             r"(?:[\s-]" # Separator kolejnych członów
        #                 # ZABEZPIECZENIE 2: Powtórzenie lookahead przy każdym kolejnym członie
        #                 r"(?!\s*(?i:ul\.|ulica|al\.|aleja|pl\.|plac|os\.|osiedle|skwer|rondo))"
        #                 r"(?:"
        #                    r"[A-ZĄĆĘŁŃÓŚŹŻ0-9][\wą-ż\.-]*" # Kolejne słowa muszą być z Dużej (lub cyfry)
        #                    r"|"
        #                    r"(?i:św\.|gen\.|ks\.|bp\.|abp\.|prof\.|dr\.?|im\.)" # Tytuły
        #                    r"|"
        #                    r"[A-Z]\.?" # Inicjały
        #                    r"|"
        #                    r"(?i:i|w|z|nad|pod|przy|ku)" # Dozwolone łączniki (małą literą)
        #                 r")"
        #             r")*" 
        #         r")"
        #     r")"
        #     r"\s+" # Spacja przed numerem
        #     # Grupa 2: Numer. Dodano \b na końcu, żeby nie łapać początku telefonu (np. 600-500)
        #     r"(\d+(?:[a-zA-Z])?(?:[/-]\d+(?:[a-zA-Z])?)?(?:\s*(?i:m\.|lok\.|m|lok)\s*\d+)?)\b", 
        #     re.IGNORECASE
        # )

        # =================================================================
        # KROK 2: PESEL
        # =================================================================
        self.pesel_regex = re.compile(r"\b\d{11}\b")

        # =================================================================
        # KROK 3: Wiek
        # =================================================================
        # LEGACY: Model ML radzi sobie lepiej.
        # Przechowujemy krotki (regex, group_index_of_entity), gdzie group_index to numer grupy, która jest encją
        # self.age_patterns = [
        #     # Wariant A: "25 lat" -> "{age} lat" (Entity: 25)
        #     (re.compile(r"\b(\d{1,3})(\s?(?:lat|lata|l\.|r\.ż\.))", flags=re.IGNORECASE), 1),
        #     # Wariant B: "Wiek: 25" -> "Wiek: {age}" (Entity: 25)
        #     (re.compile(r"\b(wiek:?\s?)(\d{1,3})", flags=re.IGNORECASE), 2),
        #     # Wariant C: "18+" -> "{age}+" (Entity: 18)
        #     (re.compile(r"\b(\d{1,3})(\+)", flags=re.IGNORECASE), 1)
        # ]

        # =================================================================
        # KROK 4: Reszta prostych regexów
        # =================================================================
        # LEGACY: Model ML radzi sobie lepiej z username, secret, dokumentami i datami.
        self.simple_patterns = [
            (EntityType.EMAIL, re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
            
            # POPRAWKA 1: Username
            # Wymusza, by ostatni znak NIE był kropką (żeby nie zjadać kropki kończącej zdanie)
            # (EntityType.USERNAME, re.compile(r"(?<![\w])@[\w](?:[\w._-]*[\w_-])?")), 
            
            # (EntityType.SECRET, re.compile(r"Bearer\s+[a-zA-Z0-9\-\._~+/]+=*")),
            (EntityType.BANK_ACCOUNT, re.compile(r"\b(?i:PL)[ ]?\d{2}(?:[ ]?\d{4}){6}\b")),  # Full Polish IBAN: PL dd dddd dddd dddd dddd dddd dddd
            (EntityType.BANK_ACCOUNT, re.compile(r"\b\d{4}[ ]\d{4}[ ]\d{4}[ ]\d{4}\b")),  # 4x4 digits with spaces: 1234 0234 9054 0012
            # (EntityType.CREDIT_CARD_NUMBER, re.compile(r"(?<!\d)(?<!\d[ -])(?:(?:\d{4} \d{4} \d{4} \d{4})|(?:\d{4}-\d{4}-\d{4}-\d{4}))(?!\d)")),
            
            # POPRAWKA 2: Telefon
            # - Accepts any international prefix (+1 to +999, or 00X to 00XXX)
            # - WITHOUT prefix: requires at least one separator to avoid matching random 9-digit numbers
            
            # Mobile WITH international prefix (separators optional): +48 123456789 or +1 555 123 4567
            (EntityType.PHONE, re.compile(r"(?<!\w)(?:(?:\+|00)\d{1,3}[ .-]?|\(\+?\d{1,3}\)[ .-]?)\d{3}[ .-]?\d{3}[ .-]?\d{3}(?!\w)")),
            # Mobile WITHOUT prefix (separators REQUIRED): 123 456 789 or 123-456-789
            (EntityType.PHONE, re.compile(r"(?<!\w)\d{3}[ .-]\d{3}[ .-]\d{3}(?!\w)")),
            # Landline WITH prefix: +48 22 123 45 67
            (EntityType.PHONE, re.compile(r"(?<!\w)(?:(?:\+|00)\d{1,3}[ .-]?|\(\+?\d{1,3}\)[ .-]?)\d{2}[ .-]?\d{3}[ .-]?\d{2}[ .-]?\d{2}(?!\w)")),
            # Landline WITHOUT prefix (separators REQUIRED): 22 123 45 67 or (22) 123-45-67
            (EntityType.PHONE, re.compile(r"(?<!\w)\(?\d{2}\)?[ .-]\d{3}[ .-]\d{2}[ .-]\d{2}(?!\w)"))

            # (EntityType.DOCUMENT_NUMBER, re.compile(r"\b[A-Z]{3}\s?\d{6}\b", re.IGNORECASE)), # Dowód
            # (EntityType.DOCUMENT_NUMBER, re.compile(r"\b[A-Z]{2}\s?\d{7}\b")), # Paszport
            # (EntityType.DOCUMENT_NUMBER, re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")), # VIN
            # (EntityType.DATE, re.compile(r"\b\d{4}[-./]\d{1,2}[-./]\d{1,2}\b|\b\d{1,2}[-./]\d{1,2}[-./]\d{4}\b")),
        ]

    def _validate_pesel_checksum(self, pesel: str) -> bool:
        """
        Walidacja matematyczna numeru PESEL.
        """
        if len(pesel) != 11:
            return False
        
        weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
        
        try:
            checksum = sum(int(pesel[i]) * weights[i] for i in range(10))
            control_digit = (10 - (checksum % 10)) % 10
            
            return control_digit == int(pesel[10])
        except ValueError:
            return False

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
        
        def is_occupied(start: int, end: int) -> bool:
            for o_start, o_end in occupied_ranges:
                # Check for overlap
                if not (end <= o_start or start >= o_end):
                    return True
            return False
        
        def add_entity(entity: DetectedEntity) -> bool:
            if is_occupied(entity.start, entity.end):
                return False
            entities.append(entity)
            occupied_ranges.add((entity.start, entity.end))
            return True

        # =================================================================
        # KROK 1: Adresy
        # =================================================================
        # LEGACY: Model ML radzi sobie lepiej z adresami, wiekiem, username, secret, dokumentami i datami.
        # for match in self.address_regex.finditer(text):
        #     add_entity(DetectedEntity(
        #         text=match.group(),
        #         entity_type=EntityType.ADDRESS,
        #         start=match.start(),
        #         end=match.end(),
        #         confidence=0.90,
        #         source='regex'
        #     ))

        # =================================================================
        # KROK 2: PESEL z Walidacją
        # =================================================================
        for match in self.pesel_regex.finditer(text):
            pesel = match.group()
            if self._validate_pesel_checksum(pesel):
                add_entity(DetectedEntity(
                    text=pesel,
                    entity_type=EntityType.PESEL,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.99,
                    source='regex'
                ))

        # =================================================================
        # KROK 3: Wiek
        # =================================================================
        # LEGACY: Model ML radzi sobie lepiej.
        # for pattern, group_idx in self.age_patterns:
        #     for match in pattern.finditer(text):
        #         # Dla wieku, encją jest tylko liczba, nie cały kontekst (zgodnie z logiką regex.py)
        #         try:
        #             start = match.start(group_idx)
        #             end = match.end(group_idx)
        #             val = match.group(group_idx)
        #             
        #             if is_occupied(start, end):
        #                 continue
        #                 
        #             add_entity(DetectedEntity(
        #                 text=val,
        #                 entity_type=EntityType.AGE,
        #                 start=start,
        #                 end=end,
        #                 confidence=0.85,
        #                 source='regex'
        #             ))
        #         except IndexError:
        #             continue

        # =================================================================
        # KROK 4: Reszta prostych regexów
        # =================================================================
        for entity_type, pattern in self.simple_patterns:
            for match in pattern.finditer(text):
                add_entity(DetectedEntity(
                    text=match.group(),
                    entity_type=entity_type,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.90,
                    source='regex'
                ))

        entities.sort(key=lambda e: (e.start, -e.end))
        
        if use_cache:
            self._result_cache[text_hash] = entities.copy()
            if len(self._result_cache) > self._cache_size:
                # Simple cleanup
                keys = list(self._result_cache.keys())
                for k in keys[:-self._cache_size]:
                    del self._result_cache[k]
        
        return entities
    
    def clear_cache(self):
        """Czyści cache."""
        self._result_cache.clear()

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
