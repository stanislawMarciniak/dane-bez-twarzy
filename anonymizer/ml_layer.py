"""
Warstwa ML (NER + Kontekst) - "Inteligencja"
Wykorzystuje SpaCy lub HerBERT/PolBERT do wykrywania encji kontekstowych.
Rozróżnia city vs address, name vs relative, wykrywa dane wrażliwe.
"""

import logging
import re
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from functools import lru_cache

from .regex_layer import DetectedEntity, EntityType

logger = logging.getLogger(__name__)


# Mapowanie etykiet NER na typy encji
NER_LABEL_MAPPING = {
    # SpaCy
    'PERSON': EntityType.NAME,
    'PER': EntityType.NAME,
    'persName': EntityType.NAME,
    'LOC': EntityType.CITY,  # Domyślnie city, kontekst decyduje
    'GPE': EntityType.CITY,
    'placeName': EntityType.CITY,
    'ORG': EntityType.COMPANY,
    'orgName': EntityType.COMPANY,
    'DATE': EntityType.DATE,
    'TIME': EntityType.DATE,
    # Transformers (HerBERT NER)
    'B-PER': EntityType.NAME,
    'I-PER': EntityType.NAME,
    'B-LOC': EntityType.CITY,
    'I-LOC': EntityType.CITY,
    'B-ORG': EntityType.COMPANY,
    'I-ORG': EntityType.COMPANY,
}


# Polskie miasta (do heurystyk)
POLISH_CITIES = {
    'Warszawa', 'Kraków', 'Łódź', 'Wrocław', 'Poznań', 'Gdańsk', 'Szczecin',
    'Bydgoszcz', 'Lublin', 'Białystok', 'Katowice', 'Gdynia', 'Częstochowa',
    'Radom', 'Toruń', 'Kielce', 'Rzeszów', 'Gliwice', 'Olsztyn', 'Opole'
}

# Formy odmienione miast
CITY_FORMS = {
    'Warszawie': 'Warszawa', 'Warszawy': 'Warszawa', 'Warszawę': 'Warszawa',
    'Krakowie': 'Kraków', 'Krakowa': 'Kraków', 'Krakowem': 'Kraków',
    'Wrocławiu': 'Wrocław', 'Wrocławia': 'Wrocław', 'Wrocławiem': 'Wrocław',
    'Poznaniu': 'Poznań', 'Poznania': 'Poznań', 'Poznaniem': 'Poznań',
    'Gdańsku': 'Gdańsk', 'Gdańska': 'Gdańsk', 'Gdańskiem': 'Gdańsk',
    'Lublinie': 'Lublin', 'Lublina': 'Lublin', 'Lublinem': 'Lublin',
}

# Polskie imiona (skrócona lista - 3 przykłady na płeć zgodnie z wymogami)
POLISH_MALE_NAMES = {'Jan', 'Adam', 'Piotr'}
POLISH_FEMALE_NAMES = {'Anna', 'Maria', 'Katarzyna'}
ALL_NAMES = POLISH_MALE_NAMES | POLISH_FEMALE_NAMES

# Typowe polskie nazwiska (końcówki)
SURNAME_PATTERNS = re.compile(
    r'^[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(ski|ska|cki|cka|wicz|owski|owska|ewski|ewska|ak|ek|ik|uk|czyk|yk)$'
)

# Słowa kluczowe dla kontekstu
ADDRESS_INDICATORS = {
    'mieszkam', 'mieszka', 'zamieszkały', 'zameldowany', 'zamieszkania',
    'adres', 'przy', 'ulica', 'ul.', 'aleja', 'al.', 'osiedle', 'os.',
    'mieszkanie', 'lokal', 'dom', 'blok', 'klatka', 'piętro'
}

CITY_ONLY_INDICATORS = {
    'jadę', 'lecę', 'wybieram', 'podróż', 'wycieczka', 'zwiedzam',
    'odwiedzam', 'pochodzę', 'urodziłem', 'urodziłam', 'z miasta',
    'koncert', 'mecz', 'wydarzenie', 'spotkanie'
}

RELATIVE_INDICATORS = {
    'mój', 'moja', 'moje', 'nasz', 'nasza', 'nasze',
    'brat', 'siostra', 'ojciec', 'matka', 'mama', 'tata',
    'syn', 'córka', 'dziadek', 'babcia', 'wujek', 'ciocia',
    'mąż', 'żona', 'partner', 'partnerka', 'narzeczony', 'narzeczona',
    'teść', 'teściowa', 'szwagier', 'szwagierka', 'kuzyn', 'kuzynka'
}

# Wzorce dla danych wrażliwych (heurystyki)
HEALTH_INDICATORS = {
    'choroba', 'diagnoza', 'leczenie', 'szpital', 'lekarz', 'operacja',
    'rak', 'cukrzyca', 'depresja', 'alergia', 'astma', 'nadciśnienie',
    'pacjent', 'recepta', 'tabletki', 'leki', 'terapia', 'rehabilitacja',
    'choruje', 'zachorował', 'wyleczył', 'przyjęto', 'wypis', 'badanie'
}

RELIGION_INDICATORS = {
    'katolik', 'protestant', 'prawosławny', 'muzułmanin', 'żyd', 'buddysta',
    'ateista', 'agnostyk', 'wierzący', 'niewierzący', 'wyznanie', 'religia',
    'kościół', 'meczet', 'synagoga', 'świątynia', 'modlitwa', 'msza'
}

POLITICAL_INDICATORS = {
    'głosuję', 'popieram', 'partia', 'polityk', 'wybory', 'kandydat',
    'lewica', 'prawica', 'liberał', 'konserwatyst', 'socjalista',
    'związek zawodowy', 'protest', 'manifestacja', 'strajk'
}

ETHNICITY_INDICATORS = {
    'narodowość', 'pochodzenie', 'etniczn', 'romski', 'żydowski',
    'ukraiński', 'białoruski', 'wietnamski', 'mniejszość', 'obcokrajowiec'
}

ORIENTATION_INDICATORS = {
    'gej', 'lesbijka', 'biseksualny', 'homoseksualny', 'heteroseksualny',
    'transpłciowy', 'lgbt', 'orientacja', 'coming out', 'partner życiowy'
}


class MLLayer:
    """
    Warstwa ML do wykrywania encji wymagających kontekstu.
    Obsługuje SpaCy (szybszy) lub Transformers (dokładniejszy).
    """
    
    def __init__(
        self,
        use_transformer: bool = False,
        custom_model_path: Optional[str] = None,
        device: str = "cpu"
    ):
        """
        Args:
            use_transformer: Czy używać HerBERT zamiast SpaCy
            custom_model_path: Ścieżka do fine-tuned modelu
            device: 'cpu' lub 'cuda'
        """
        self.use_transformer = use_transformer
        self.custom_model_path = custom_model_path
        self.device = device
        
        self.nlp = None
        self.transformer_pipeline = None
        self._initialized = False
    
    def initialize(self):
        """Lazy initialization."""
        if self._initialized:
            return
        
        if self.custom_model_path:
            self._load_custom_model()
        elif self.use_transformer:
            self._init_transformer()
        else:
            self._init_spacy()
        
        self._initialized = True
    
    def _init_spacy(self):
        """Inicjalizuje SpaCy NER."""
        try:
            import spacy
            
            try:
                self.nlp = spacy.load("pl_core_news_lg")
                logger.info("SpaCy pl_core_news_lg załadowany")
            except OSError:
                try:
                    self.nlp = spacy.load("pl_core_news_sm")
                    logger.info("SpaCy pl_core_news_sm załadowany (fallback)")
                except OSError:
                    logger.warning("Brak modelu SpaCy - używam tylko heurystyk")
                    self.nlp = None
                    
        except ImportError:
            logger.warning("SpaCy niezainstalowane - używam tylko heurystyk")
            self.nlp = None
    
    def _init_transformer(self):
        """Inicjalizuje HerBERT/PolBERT dla NER."""
        try:
            from transformers import pipeline, AutoModelForTokenClassification, AutoTokenizer
            import torch
            
            model_name = "allegro/herbert-base-cased"
            
            # Sprawdź czy jest fine-tuned model NER
            try:
                self.transformer_pipeline = pipeline(
                    "ner",
                    model="clarin-pl/herbert-ner",  # Polski NER
                    device=0 if self.device == "cuda" and torch.cuda.is_available() else -1,
                    aggregation_strategy="simple"
                )
                logger.info("HerBERT NER załadowany")
            except Exception as e:
                logger.warning(f"Nie można załadować modelu NER: {e}")
                # Fallback do SpaCy
                self._init_spacy()
                
        except ImportError:
            logger.warning("Transformers niezainstalowane - używam SpaCy")
            self._init_spacy()
    
    def _load_custom_model(self):
        """Ładuje własny wytrenowany model."""
        try:
            import spacy
            self.nlp = spacy.load(self.custom_model_path)
            logger.info(f"Załadowano własny model: {self.custom_model_path}")
        except Exception as e:
            logger.error(f"Błąd ładowania modelu: {e}")
            self._init_spacy()
    
    def detect(
        self,
        text: str,
        regex_entities: List[DetectedEntity] = None
    ) -> List[DetectedEntity]:
        """
        Wykrywa encje wymagające analizy kontekstowej.
        
        Args:
            text: Tekst do analizy
            regex_entities: Encje już wykryte przez regex (do unikania duplikatów)
            
        Returns:
            Lista wykrytych encji
        """
        self.initialize()
        
        entities = []
        regex_spans = set()
        
        if regex_entities:
            regex_spans = {(e.start, e.end) for e in regex_entities}
        
        # NER z modelu
        if self.transformer_pipeline:
            entities.extend(self._detect_transformer(text, regex_spans))
        elif self.nlp:
            entities.extend(self._detect_spacy(text, regex_spans))
        
        # Heurystyki kontekstowe (zawsze)
        entities.extend(self._detect_context_heuristics(text, regex_spans))
        
        # Deduplikacja
        entities = self._deduplicate(entities)
        
        return entities
    
    def _detect_spacy(
        self,
        text: str,
        regex_spans: Set[Tuple[int, int]]
    ) -> List[DetectedEntity]:
        """Detekcja za pomocą SpaCy NER."""
        entities = []
        doc = self.nlp(text)
        
        for ent in doc.ents:
            # Pomiń jeśli pokrywa się z regex
            if self._overlaps_with(ent.start_char, ent.end_char, regex_spans):
                continue
            
            entity_type = self._map_spacy_label(ent.label_, text, ent.start_char, ent.end_char)
            
            if entity_type:
                entities.append(DetectedEntity(
                    text=ent.text,
                    entity_type=entity_type,
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=0.75,
                    source='ml_spacy'
                ))
        
        return entities
    
    def _detect_transformer(
        self,
        text: str,
        regex_spans: Set[Tuple[int, int]]
    ) -> List[DetectedEntity]:
        """Detekcja za pomocą Transformer NER."""
        entities = []
        
        try:
            results = self.transformer_pipeline(text)
            
            for result in results:
                start = result['start']
                end = result['end']
                
                if self._overlaps_with(start, end, regex_spans):
                    continue
                
                entity_type = self._map_transformer_label(
                    result['entity_group'],
                    text, start, end
                )
                
                if entity_type:
                    entities.append(DetectedEntity(
                        text=result['word'],
                        entity_type=entity_type,
                        start=start,
                        end=end,
                        confidence=result['score'],
                        source='ml_transformer'
                    ))
                    
        except Exception as e:
            logger.warning(f"Błąd Transformer NER: {e}")
        
        return entities
    
    def _detect_context_heuristics(
        self,
        text: str,
        regex_spans: Set[Tuple[int, int]]
    ) -> List[DetectedEntity]:
        """
        Wykrywa encje wrażliwe za pomocą heurystyk kontekstowych.
        Szczególnie ważne dla: health, religion, political-view, ethnicity, sexual-orientation
        """
        entities = []
        text_lower = text.lower()
        
        # Wykrywanie imion i nazwisk (gdy brak SpaCy)
        if not self.nlp and not self.transformer_pipeline:
            entities.extend(self._detect_names_heuristic(text, regex_spans))
            entities.extend(self._detect_cities_heuristic(text, text_lower, regex_spans))
        
        # Wykrywanie zdrowia
        entities.extend(self._detect_sensitive_category(
            text, text_lower, HEALTH_INDICATORS, EntityType.HEALTH, regex_spans
        ))
        
        # Wykrywanie religii
        entities.extend(self._detect_sensitive_category(
            text, text_lower, RELIGION_INDICATORS, EntityType.RELIGION, regex_spans
        ))
        
        # Wykrywanie poglądów politycznych
        entities.extend(self._detect_sensitive_category(
            text, text_lower, POLITICAL_INDICATORS, EntityType.POLITICAL_VIEW, regex_spans
        ))
        
        # Wykrywanie pochodzenia etnicznego
        entities.extend(self._detect_sensitive_category(
            text, text_lower, ETHNICITY_INDICATORS, EntityType.ETHNICITY, regex_spans
        ))
        
        # Wykrywanie orientacji seksualnej
        entities.extend(self._detect_sensitive_category(
            text, text_lower, ORIENTATION_INDICATORS, EntityType.SEXUAL_ORIENTATION, regex_spans
        ))
        
        # Wykrywanie relacji rodzinnych
        entities.extend(self._detect_relatives(text, text_lower, regex_spans))
        
        return entities
    
    def _detect_names_heuristic(
        self,
        text: str,
        regex_spans: Set[Tuple[int, int]]
    ) -> List[DetectedEntity]:
        """Wykrywa imiona i nazwiska za pomocą heurystyk (gdy brak SpaCy)."""
        entities = []
        
        # Rozszerzone listy imion
        all_names = POLISH_MALE_NAMES | POLISH_FEMALE_NAMES | {
            'Andrzej', 'Tomasz', 'Michał', 'Krzysztof', 'Paweł', 'Marek', 'Jakub',
            'Małgorzata', 'Agnieszka', 'Joanna', 'Ewa', 'Barbara', 'Zofia', 'Magdalena'
        }
        
        # Wzorzec: imię + nazwisko
        pattern = re.compile(
            r'\b([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)\s+([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:ski|ska|cki|cka|wicz|owski|owska|ak|ek|ik|uk))\b'
        )
        
        for match in pattern.finditer(text):
            name, surname = match.group(1), match.group(2)
            
            # Sprawdź czy to prawdopodobnie imię
            if name in all_names or self._looks_like_name(name):
                name_start = match.start()
                name_end = match.start() + len(name)
                
                if not self._overlaps_with(name_start, name_end, regex_spans):
                    entities.append(DetectedEntity(
                        text=name,
                        entity_type=EntityType.NAME,
                        start=name_start,
                        end=name_end,
                        confidence=0.80,
                        source='ml_heuristic'
                    ))
                
                # Nazwisko
                surname_start = match.start() + len(name) + 1
                surname_end = match.end()
                
                if not self._overlaps_with(surname_start, surname_end, regex_spans):
                    entities.append(DetectedEntity(
                        text=surname,
                        entity_type=EntityType.SURNAME,
                        start=surname_start,
                        end=surname_end,
                        confidence=0.80,
                        source='ml_heuristic'
                    ))
        
        # Wykrywanie samodzielnych imion (gdy są w słowniku)
        for name in all_names:
            pattern = re.compile(r'\b' + re.escape(name) + r'\b')
            for match in pattern.finditer(text):
                if not self._overlaps_with(match.start(), match.end(), regex_spans):
                    # Sprawdź czy nie jest już wykryte
                    already_detected = any(
                        e.start == match.start() and e.end == match.end()
                        for e in entities
                    )
                    if not already_detected:
                        entities.append(DetectedEntity(
                            text=match.group(),
                            entity_type=EntityType.NAME,
                            start=match.start(),
                            end=match.end(),
                            confidence=0.75,
                            source='ml_heuristic'
                        ))
        
        return entities
    
    def _detect_cities_heuristic(
        self,
        text: str,
        text_lower: str,
        regex_spans: Set[Tuple[int, int]]
    ) -> List[DetectedEntity]:
        """Wykrywa miasta za pomocą heurystyk."""
        entities = []
        
        # Sprawdź miasta i ich formy odmienione
        all_city_forms = set(POLISH_CITIES)
        all_city_forms.update(CITY_FORMS.keys())
        
        for city_form in all_city_forms:
            pattern = re.compile(r'\b' + re.escape(city_form) + r'\b', re.IGNORECASE)
            
            for match in pattern.finditer(text):
                start, end = match.start(), match.end()
                
                if self._overlaps_with(start, end, regex_spans):
                    continue
                
                # Klasyfikuj jako city lub address na podstawie kontekstu
                context_start = max(0, start - 50)
                context_end = min(len(text), end + 50)
                context = text[context_start:context_end].lower()
                
                entity_type = self._classify_location(context, match.group())
                
                entities.append(DetectedEntity(
                    text=match.group(),
                    entity_type=entity_type,
                    start=start,
                    end=end,
                    confidence=0.75,
                    source='ml_heuristic'
                ))
        
        return entities
    
    def _looks_like_name(self, word: str) -> bool:
        """Sprawdza czy słowo wygląda jak imię."""
        if len(word) < 3 or not word[0].isupper():
            return False
        
        # Typowe końcówki imion
        name_endings = ('a', 'ek', 'usz', 'aw', 'an', 'el', 'il', 'at', 'ot')
        return word.endswith(name_endings)
    
    def _detect_sensitive_category(
        self,
        text: str,
        text_lower: str,
        indicators: Set[str],
        entity_type: EntityType,
        regex_spans: Set[Tuple[int, int]]
    ) -> List[DetectedEntity]:
        """Wykrywa wrażliwe kategorie na podstawie słów kluczowych."""
        entities = []
        
        for indicator in indicators:
            pattern = re.compile(
                r'\b' + re.escape(indicator) + r'[a-ząćęłńóśźż]*\b',
                re.IGNORECASE
            )
            
            for match in pattern.finditer(text_lower):
                start, end = match.start(), match.end()
                
                if self._overlaps_with(start, end, regex_spans):
                    continue
                
                # Pobierz oryginalny tekst (z zachowaniem wielkości liter)
                original_text = text[start:end]
                
                entities.append(DetectedEntity(
                    text=original_text,
                    entity_type=entity_type,
                    start=start,
                    end=end,
                    confidence=0.70,
                    source='ml_heuristic'
                ))
        
        return entities
    
    def _detect_relatives(
        self,
        text: str,
        text_lower: str,
        regex_spans: Set[Tuple[int, int]]
    ) -> List[DetectedEntity]:
        """
        Wykrywa relacje rodzinne w kontekście (np. "mój brat Jan").
        """
        entities = []
        
        # Wzorzec: [zaimek dzierżawczy] + [relacja] + [imię]
        pattern = re.compile(
            r'(m[oó]j[aeo]?|nasz[aeo]?)\s+'
            r'(brat|siostra|ojciec|matka|mama|tata|syn|córka|'
            r'dziadek|babcia|wujek|ciocia|mąż|żona|'
            r'kuzyn|kuzynka|teść|teściowa)\s+'
            r'([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)',
            re.IGNORECASE
        )
        
        for match in pattern.finditer(text):
            # Cała fraza jako relative
            start, end = match.start(), match.end()
            
            if self._overlaps_with(start, end, regex_spans):
                continue
            
            entities.append(DetectedEntity(
                text=match.group(),
                entity_type=EntityType.RELATIVE,
                start=start,
                end=end,
                confidence=0.85,
                source='ml_heuristic'
            ))
        
        # Wzorzec: [relacja] + [nazwisko w dopełniaczu] (np. "syn Kowalskiego")
        pattern2 = re.compile(
            r'(syn|córka|brat|siostra)\s+'
            r'(pana|pani)?\s*'
            r'([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:skiego|skiej|ego|iej))',
            re.IGNORECASE
        )
        
        for match in pattern2.finditer(text):
            start, end = match.start(), match.end()
            
            if self._overlaps_with(start, end, regex_spans):
                continue
            
            entities.append(DetectedEntity(
                text=match.group(),
                entity_type=EntityType.RELATIVE,
                start=start,
                end=end,
                confidence=0.80,
                source='ml_heuristic'
            ))
        
        return entities
    
    def _map_spacy_label(
        self,
        label: str,
        text: str,
        start: int,
        end: int
    ) -> Optional[EntityType]:
        """Mapuje etykiety SpaCy na nasze typy encji z uwzględnieniem kontekstu."""
        
        # Pobierz kontekst (50 znaków przed i po)
        context_start = max(0, start - 50)
        context_end = min(len(text), end + 50)
        context = text[context_start:context_end].lower()
        
        if label in ('persName', 'PERSON', 'PER'):
            return EntityType.NAME
        
        elif label in ('placeName', 'LOC', 'GPE'):
            # Rozróżnij city vs address
            return self._classify_location(context, text[start:end])
        
        elif label in ('orgName', 'ORG'):
            # Rozróżnij company vs school
            entity_text = text[start:end].lower()
            if any(word in entity_text for word in ['szkoła', 'uniwersytet', 'liceum', 'technikum', 'akademia']):
                return EntityType.SCHOOL_NAME
            return EntityType.COMPANY
        
        elif label == 'DATE':
            return EntityType.DATE
        
        return None
    
    def _map_transformer_label(
        self,
        label: str,
        text: str,
        start: int,
        end: int
    ) -> Optional[EntityType]:
        """Mapuje etykiety Transformer NER na nasze typy."""
        
        context_start = max(0, start - 50)
        context_end = min(len(text), end + 50)
        context = text[context_start:context_end].lower()
        
        label_upper = label.upper()
        
        if 'PER' in label_upper:
            return EntityType.NAME
        elif 'LOC' in label_upper or 'GPE' in label_upper:
            return self._classify_location(context, text[start:end])
        elif 'ORG' in label_upper:
            return EntityType.COMPANY
        elif 'DATE' in label_upper:
            return EntityType.DATE
        
        return None
    
    def _classify_location(self, context: str, entity_text: str) -> EntityType:
        """
        Klasyfikuje lokalizację jako city lub address na podstawie kontekstu.
        Kluczowa funkcja dla rozróżnienia wymaganego w zadaniu.
        """
        context_lower = context.lower()
        
        # Sprawdź wskaźniki adresu
        address_score = sum(1 for word in ADDRESS_INDICATORS if word in context_lower)
        
        # Sprawdź wskaźniki samego miasta
        city_score = sum(1 for word in CITY_ONLY_INDICATORS if word in context_lower)
        
        # Jeśli jest numer domu/mieszkania - to adres
        if re.search(r'\d+[a-z]?(?:\s*/\s*\d+)?', context):
            address_score += 2
        
        # Jeśli jest kod pocztowy - to adres
        if re.search(r'\d{2}-\d{3}', context):
            address_score += 3
        
        # Jeśli jest "ul." lub "ulica" - to adres
        if re.search(r'\b(ul\.?|ulica|al\.?|aleja|os\.?|osiedle)\b', context_lower):
            address_score += 3
        
        # Klasyfikacja
        if address_score > city_score:
            return EntityType.ADDRESS
        else:
            return EntityType.CITY
    
    def _overlaps_with(
        self,
        start: int,
        end: int,
        spans: Set[Tuple[int, int]]
    ) -> bool:
        """Sprawdza czy span nachodzi na istniejące."""
        for s, e in spans:
            if start < e and end > s:
                return True
        return False
    
    def _deduplicate(
        self,
        entities: List[DetectedEntity]
    ) -> List[DetectedEntity]:
        """Usuwa duplikaty i nakładające się encje."""
        if not entities:
            return entities
        
        # Sortuj po pozycji, potem po pewności (malejąco)
        sorted_entities = sorted(
            entities,
            key=lambda e: (e.start, -e.confidence)
        )
        
        result = []
        covered_spans = set()
        
        for entity in sorted_entities:
            # Sprawdź czy nie nakłada się z już dodanymi
            overlaps = False
            for s, e in covered_spans:
                if entity.start < e and entity.end > s:
                    overlaps = True
                    break
            
            if not overlaps:
                result.append(entity)
                covered_spans.add((entity.start, entity.end))
        
        return result


class NameSurnameSplitter:
    """
    Rozdziela pełne imiona i nazwiska na osobne encje.
    Np. "Jan Kowalski" -> {name} + {surname}
    """
    
    def __init__(self):
        # Rozszerzone listy imion
        self.male_names = POLISH_MALE_NAMES | {
            'Andrzej', 'Tomasz', 'Michał', 'Krzysztof', 'Paweł',
            'Marek', 'Jakub', 'Stanisław', 'Wojciech', 'Marcin'
        }
        
        self.female_names = POLISH_FEMALE_NAMES | {
            'Małgorzata', 'Agnieszka', 'Joanna', 'Ewa', 'Barbara',
            'Zofia', 'Magdalena', 'Aleksandra', 'Karolina', 'Monika'
        }
        
        self.all_names = self.male_names | self.female_names
        
        # Formy odmienione popularnych imion
        self.name_forms = self._build_name_forms()
    
    def _build_name_forms(self) -> Dict[str, str]:
        """Buduje mapowanie form odmienioych -> forma podstawowa."""
        forms = {}
        
        # Proste formy odmienione dla popularnych imion
        common_forms = {
            'Jana': 'Jan', 'Janowi': 'Jan', 'Janem': 'Jan',
            'Adama': 'Adam', 'Adamowi': 'Adam', 'Adamem': 'Adam',
            'Piotra': 'Piotr', 'Piotrowi': 'Piotr', 'Piotrem': 'Piotr',
            'Anny': 'Anna', 'Annie': 'Anna', 'Annę': 'Anna', 'Anną': 'Anna',
            'Marii': 'Maria', 'Marię': 'Maria', 'Marią': 'Maria',
            'Katarzyny': 'Katarzyna', 'Katarzynie': 'Katarzyna',
            'Katarzynę': 'Katarzyna', 'Katarzyną': 'Katarzyna',
            # Zdrobnienia
            'Kasi': 'Katarzyna', 'Kasię': 'Katarzyna', 'Kasią': 'Katarzyna',
            'Ani': 'Anna', 'Anię': 'Anna', 'Anią': 'Anna',
        }
        
        forms.update(common_forms)
        return forms
    
    def is_likely_name(self, word: str) -> bool:
        """Sprawdza czy słowo to prawdopodobnie imię."""
        # Forma podstawowa
        if word in self.all_names:
            return True
        
        # Forma odmieniona
        if word in self.name_forms:
            return True
        
        # Heurystyka: słowo z wielką literą, kończy się typowo dla imion
        if word[0].isupper() and len(word) >= 3:
            # Typowe końcówki imion żeńskich
            if word.endswith(('a', 'ę', 'ą', 'y', 'i', 'e')):
                return True
            # Typowe końcówki imion męskich (formy odmienione)
            if word.endswith(('a', 'owi', 'em', 'ie')):
                return True
        
        return False
    
    def is_likely_surname(self, word: str) -> bool:
        """Sprawdza czy słowo to prawdopodobnie nazwisko."""
        if not word or not word[0].isupper():
            return False
        
        # Wzorzec typowych polskich nazwisk
        if SURNAME_PATTERNS.match(word):
            return True
        
        # Nazwiska kończące się na -icz, -owicz
        if word.endswith(('icz', 'owicz', 'ewicz')):
            return True
        
        return False
    
    def split_person(
        self,
        text: str,
        entity: DetectedEntity
    ) -> List[DetectedEntity]:
        """
        Rozdziela encję osobową na imię i nazwisko.
        
        Args:
            text: Pełny tekst
            entity: Encja do rozdzielenia (zawiera "Imię Nazwisko")
            
        Returns:
            Lista encji (name, surname) lub oryginalna encja
        """
        parts = entity.text.split()
        
        if len(parts) != 2:
            return [entity]
        
        first, second = parts
        
        # Sprawdź czy to imię + nazwisko
        first_is_name = self.is_likely_name(first)
        second_is_surname = self.is_likely_surname(second)
        
        # Może być odwrotnie (nazwisko + imię)?
        first_is_surname = self.is_likely_surname(first)
        second_is_name = self.is_likely_name(second)
        
        if first_is_name and second_is_surname:
            # Standardowa kolejność: Imię Nazwisko
            name_end = entity.start + len(first)
            surname_start = entity.start + len(first) + 1
            
            return [
                DetectedEntity(
                    text=first,
                    entity_type=EntityType.NAME,
                    start=entity.start,
                    end=name_end,
                    confidence=entity.confidence,
                    source=entity.source,
                    morphology=entity.morphology
                ),
                DetectedEntity(
                    text=second,
                    entity_type=EntityType.SURNAME,
                    start=surname_start,
                    end=entity.end,
                    confidence=entity.confidence,
                    source=entity.source,
                    morphology=entity.morphology
                )
            ]
        
        elif first_is_surname and second_is_name:
            # Odwrotna kolejność: Nazwisko Imię
            surname_end = entity.start + len(first)
            name_start = entity.start + len(first) + 1
            
            return [
                DetectedEntity(
                    text=first,
                    entity_type=EntityType.SURNAME,
                    start=entity.start,
                    end=surname_end,
                    confidence=entity.confidence,
                    source=entity.source,
                    morphology=entity.morphology
                ),
                DetectedEntity(
                    text=second,
                    entity_type=EntityType.NAME,
                    start=name_start,
                    end=entity.end,
                    confidence=entity.confidence,
                    source=entity.source,
                    morphology=entity.morphology
                )
            ]
        
        # Nie udało się rozdzielić - zwróć oryginał
        return [entity]


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    ml = MLLayer(use_transformer=False)
    splitter = NameSurnameSplitter()
    
    test_cases = [
        "Jadę do Krakowa na wycieczkę.",
        "Mieszkam w Krakowie przy ul. Długiej 5.",
        "Mój brat Jan pracuje w Warszawie.",
        "Pacjent choruje na cukrzycę typu 2.",
        "Jan Kowalski jest programistą.",
    ]
    
    print("=== Test warstwy ML ===\n")
    
    for text in test_cases:
        print(f"Input: {text}")
        entities = ml.detect(text)
        for e in entities:
            print(f"  -> {e.entity_type.value}: '{e.text}' ({e.confidence:.2f}, {e.source})")
        print()