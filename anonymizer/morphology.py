"""
Moduł Analizy Morfologicznej
Analizuje i zachowuje cechy gramatyczne wykrytych encji.
"""

import logging
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

from .regex_layer import DetectedEntity, EntityType

logger = logging.getLogger(__name__)


class Case(Enum):
    """Przypadki gramatyczne w języku polskim."""
    NOMINATIVE = "nom"      # Mianownik (kto? co?)
    GENITIVE = "gen"        # Dopełniacz (kogo? czego?)
    DATIVE = "dat"          # Celownik (komu? czemu?)
    ACCUSATIVE = "acc"      # Biernik (kogo? co?)
    INSTRUMENTAL = "ins"    # Narzędnik (kim? czym?)
    LOCATIVE = "loc"        # Miejscownik (o kim? o czym?)
    VOCATIVE = "voc"        # Wołacz


class Gender(Enum):
    """Rodzaje gramatyczne."""
    MASCULINE_PERSONAL = "m1"      # męskoosobowy
    MASCULINE_ANIMATE = "m2"       # męskożywotny
    MASCULINE_INANIMATE = "m3"     # męskonieżywotny
    FEMININE = "f"                 # żeński
    NEUTER = "n"                   # nijaki


class Number(Enum):
    """Liczba gramatyczna."""
    SINGULAR = "sg"
    PLURAL = "pl"


@dataclass
class MorphologyInfo:
    """Informacje morfologiczne o encji."""
    case: Optional[Case] = None
    gender: Optional[Gender] = None
    number: Optional[Number] = None
    lemma: Optional[str] = None
    pos: Optional[str] = None  # Part of Speech
    raw_features: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, str]:
        """Konwertuje do słownika."""
        result = {}
        if self.case:
            result['case'] = self.case.value
        if self.gender:
            result['gender'] = self.gender.value
        if self.number:
            result['number'] = self.number.value
        if self.lemma:
            result['lemma'] = self.lemma
        return result


class MorphologyAnalyzer:
    """
    Analizator morfologiczny dla języka polskiego.
    Wykorzystuje SpaCy lub Stanza do analizy gramatycznej.
    """
    
    # Mapowanie tagów SpaCy na nasze enumy
    SPACY_CASE_MAP = {
        'Nom': Case.NOMINATIVE,
        'Gen': Case.GENITIVE,
        'Dat': Case.DATIVE,
        'Acc': Case.ACCUSATIVE,
        'Ins': Case.INSTRUMENTAL,
        'Loc': Case.LOCATIVE,
        'Voc': Case.VOCATIVE,
    }
    
    SPACY_GENDER_MAP = {
        'Masc': Gender.MASCULINE_PERSONAL,
        'Fem': Gender.FEMININE,
        'Neut': Gender.NEUTER,
    }
    
    SPACY_NUMBER_MAP = {
        'Sing': Number.SINGULAR,
        'Plur': Number.PLURAL,
    }
    
    def __init__(self, backend: str = "spacy"):
        """
        Inicjalizuje analizator.
        
        Args:
            backend: 'spacy' lub 'stanza'
        """
        self.backend = backend
        self.nlp = None
        self._initialized = False
    
    def initialize(self):
        """Inicjalizuje backend NLP."""
        if self._initialized:
            return
        
        if self.backend == "spacy":
            self._init_spacy()
        elif self.backend == "stanza":
            self._init_stanza()
        
        self._initialized = True
    
    def _init_spacy(self):
        """Inicjalizuje SpaCy."""
        try:
            import spacy
            
            try:
                self.nlp = spacy.load("pl_core_news_lg")
            except OSError:
                logger.warning("Model pl_core_news_lg nie znaleziony, próbuję pl_core_news_sm")
                try:
                    self.nlp = spacy.load("pl_core_news_sm")
                except OSError:
                    logger.error("Brak modelu SpaCy dla polskiego")
                    self.nlp = None
            
            logger.info(f"SpaCy zainicjalizowane: {self.nlp.meta['name'] if self.nlp else 'brak'}")
            
        except ImportError:
            logger.warning("SpaCy nie zainstalowane")
            self.nlp = None
    
    def _init_stanza(self):
        """Inicjalizuje Stanza."""
        try:
            import stanza
            
            # Sprawdź czy model pobrany
            try:
                self.nlp = stanza.Pipeline('pl', processors='tokenize,mwt,pos,lemma')
            except:
                logger.info("Pobieranie modelu Stanza dla polskiego...")
                stanza.download('pl')
                self.nlp = stanza.Pipeline('pl', processors='tokenize,mwt,pos,lemma')
            
            logger.info("Stanza zainicjalizowane")
            
        except ImportError:
            logger.warning("Stanza nie zainstalowane")
            self.nlp = None
    
    def analyze(
        self,
        text: str,
        entity: DetectedEntity
    ) -> MorphologyInfo:
        """
        Analizuje morfologię encji w kontekście tekstu.
        
        Args:
            text: Pełny tekst
            entity: Wykryta encja
            
        Returns:
            Informacje morfologiczne
        """
        self.initialize()
        
        if not self.nlp:
            return MorphologyInfo()
        
        if self.backend == "spacy":
            return self._analyze_spacy(text, entity)
        elif self.backend == "stanza":
            return self._analyze_stanza(text, entity)
        
        return MorphologyInfo()
    
    def _analyze_spacy(
        self,
        text: str,
        entity: DetectedEntity
    ) -> MorphologyInfo:
        """Analiza za pomocą SpaCy."""
        doc = self.nlp(text)
        
        # Znajdź token odpowiadający encji
        for token in doc:
            if token.idx == entity.start or (
                token.idx <= entity.start < token.idx + len(token.text)
            ):
                morph = token.morph.to_dict()
                
                info = MorphologyInfo(
                    lemma=token.lemma_,
                    pos=token.pos_,
                    raw_features=morph
                )
                
                # Mapuj cechy
                if 'Case' in morph:
                    info.case = self.SPACY_CASE_MAP.get(morph['Case'])
                if 'Gender' in morph:
                    info.gender = self.SPACY_GENDER_MAP.get(morph['Gender'])
                if 'Number' in morph:
                    info.number = self.SPACY_NUMBER_MAP.get(morph['Number'])
                
                return info
        
        return MorphologyInfo()
    
    def _analyze_stanza(
        self,
        text: str,
        entity: DetectedEntity
    ) -> MorphologyInfo:
        """Analiza za pomocą Stanza."""
        doc = self.nlp(text)
        
        for sentence in doc.sentences:
            for word in sentence.words:
                if word.start_char == entity.start or (
                    word.start_char <= entity.start < word.end_char
                ):
                    feats = {}
                    if word.feats:
                        feats = dict(f.split('=') for f in word.feats.split('|'))
                    
                    info = MorphologyInfo(
                        lemma=word.lemma,
                        pos=word.upos,
                        raw_features=feats
                    )
                    
                    if 'Case' in feats:
                        info.case = self.SPACY_CASE_MAP.get(feats['Case'])
                    if 'Gender' in feats:
                        info.gender = self.SPACY_GENDER_MAP.get(feats['Gender'])
                    if 'Number' in feats:
                        info.number = self.SPACY_NUMBER_MAP.get(feats['Number'])
                    
                    return info
        
        return MorphologyInfo()
    
    def analyze_batch(
        self,
        text: str,
        entities: List[DetectedEntity]
    ) -> List[Tuple[DetectedEntity, MorphologyInfo]]:
        """
        Analizuje morfologię wielu encji jednocześnie (wydajniej).
        """
        self.initialize()
        
        if not self.nlp:
            return [(e, MorphologyInfo()) for e in entities]
        
        results = []
        
        if self.backend == "spacy":
            doc = self.nlp(text)
            
            for entity in entities:
                info = MorphologyInfo()
                
                for token in doc:
                    if token.idx <= entity.start < token.idx + len(token.text):
                        morph = token.morph.to_dict()
                        
                        info = MorphologyInfo(
                            lemma=token.lemma_,
                            pos=token.pos_,
                            raw_features=morph
                        )
                        
                        if 'Case' in morph:
                            info.case = self.SPACY_CASE_MAP.get(morph['Case'])
                        if 'Gender' in morph:
                            info.gender = self.SPACY_GENDER_MAP.get(morph['Gender'])
                        if 'Number' in morph:
                            info.number = self.SPACY_NUMBER_MAP.get(morph['Number'])
                        
                        break
                
                results.append((entity, info))
        
        elif self.backend == "stanza":
            doc = self.nlp(text)
            
            for entity in entities:
                info = MorphologyInfo()
                
                for sentence in doc.sentences:
                    for word in sentence.words:
                        if word.start_char <= entity.start < word.end_char:
                            feats = {}
                            if word.feats:
                                feats = dict(f.split('=') for f in word.feats.split('|'))
                            
                            info = MorphologyInfo(
                                lemma=word.lemma,
                                pos=word.upos,
                                raw_features=feats
                            )
                            
                            if 'Case' in feats:
                                info.case = self.SPACY_CASE_MAP.get(feats['Case'])
                            if 'Gender' in feats:
                                info.gender = self.SPACY_GENDER_MAP.get(feats['Gender'])
                            if 'Number' in feats:
                                info.number = self.SPACY_NUMBER_MAP.get(feats['Number'])
                            
                            break
                
                results.append((entity, info))
        
        return results


class PolishInflector:
    """
    Odmienia słowa polskie przez przypadki.
    Używa pymorphy2 lub słownika SGJP.
    """
    
    def __init__(self):
        self.morph = None
        self._initialized = False
        
        # Słownik końcówek dla podstawowych odmian
        # (fallback gdy pymorphy2 niedostępne)
        self.endings = {
            'masculine': {
                Case.NOMINATIVE: '',
                Case.GENITIVE: 'a',
                Case.DATIVE: 'owi',
                Case.ACCUSATIVE: 'a',
                Case.INSTRUMENTAL: 'em',
                Case.LOCATIVE: 'e',
                Case.VOCATIVE: 'e',
            },
            'feminine_a': {
                Case.NOMINATIVE: 'a',
                Case.GENITIVE: 'y',
                Case.DATIVE: 'e',
                Case.ACCUSATIVE: 'ę',
                Case.INSTRUMENTAL: 'ą',
                Case.LOCATIVE: 'e',
                Case.VOCATIVE: 'o',
            },
            'feminine_hard': {
                Case.NOMINATIVE: '',
                Case.GENITIVE: 'y',
                Case.DATIVE: 'ie',
                Case.ACCUSATIVE: '',
                Case.INSTRUMENTAL: 'ą',
                Case.LOCATIVE: 'ie',
                Case.VOCATIVE: 'o',
            },
        }
    
    def initialize(self):
        """Inicjalizuje pymorphy2."""
        if self._initialized:
            return
        
        try:
            import pymorphy2
            self.morph = pymorphy2.MorphAnalyzer(lang='pl')
            logger.info("pymorphy2 zainicjalizowane")
        except ImportError:
            logger.warning("pymorphy2 nie zainstalowane, używam podstawowego słownika")
        except Exception as e:
            logger.warning(f"Błąd inicjalizacji pymorphy2: {e}")
        
        self._initialized = True
    
    def inflect(
        self,
        word: str,
        target_case: Case,
        gender: Optional[Gender] = None,
        number: Number = Number.SINGULAR
    ) -> str:
        """
        Odmienia słowo przez przypadki.
        
        Args:
            word: Słowo do odmiany
            target_case: Docelowy przypadek
            gender: Rodzaj gramatyczny (opcjonalny)
            number: Liczba gramatyczna
            
        Returns:
            Odmienione słowo
        """
        self.initialize()
        
        if self.morph:
            return self._inflect_pymorphy(word, target_case, gender, number)
        else:
            return self._inflect_fallback(word, target_case, gender)
    
    def _inflect_pymorphy(
        self,
        word: str,
        target_case: Case,
        gender: Optional[Gender],
        number: Number
    ) -> str:
        """Odmiana za pomocą pymorphy2."""
        try:
            parsed = self.morph.parse(word)
            
            if not parsed:
                return word
            
            # Wybierz najlepszą interpretację
            best = parsed[0]
            
            # Mapuj przypadek
            case_map = {
                Case.NOMINATIVE: 'nomn',
                Case.GENITIVE: 'gent',
                Case.DATIVE: 'datv',
                Case.ACCUSATIVE: 'accs',
                Case.INSTRUMENTAL: 'ablt',
                Case.LOCATIVE: 'loct',
                Case.VOCATIVE: 'voct',
            }
            
            target = case_map.get(target_case, 'nomn')
            
            # Dodaj liczbę
            if number == Number.PLURAL:
                target = target + ',plur'
            else:
                target = target + ',sing'
            
            inflected = best.inflect({target.split(',')[0], target.split(',')[1] if ',' in target else 'sing'})
            
            if inflected:
                return inflected.word
            
            return word
            
        except Exception as e:
            logger.debug(f"Błąd odmiany pymorphy2: {e}")
            return word
    
    def _inflect_fallback(
        self,
        word: str,
        target_case: Case,
        gender: Optional[Gender]
    ) -> str:
        """Podstawowa odmiana gdy brak pymorphy2."""
        if not word:
            return word
        
        # Określ wzorzec odmiany
        if word.endswith('a'):
            pattern = 'feminine_a'
            stem = word[:-1]
        elif gender == Gender.FEMININE:
            pattern = 'feminine_hard'
            stem = word
        else:
            pattern = 'masculine'
            stem = word
        
        ending = self.endings[pattern].get(target_case, '')
        
        return stem + ending
    
    def get_all_forms(self, word: str) -> Dict[Case, str]:
        """Zwraca wszystkie formy przypadkowe słowa."""
        self.initialize()
        
        forms = {}
        
        for case in Case:
            forms[case] = self.inflect(word, case)
        
        return forms


class EnrichmentPipeline:
    """
    Pipeline wzbogacania encji o informacje morfologiczne.
    """
    
    def __init__(self, backend: str = "spacy"):
        self.analyzer = MorphologyAnalyzer(backend=backend)
        self.inflector = PolishInflector()
    
    def enrich(
        self,
        text: str,
        entities: List[DetectedEntity]
    ) -> List[DetectedEntity]:
        """
        Wzbogaca encje o informacje morfologiczne.
        """
        results = self.analyzer.analyze_batch(text, entities)
        
        for entity, morph_info in results:
            entity.morphology = morph_info.to_dict()
        
        return entities
    
    def generate_intermediate(
        self,
        text: str,
        entities: List[DetectedEntity]
    ) -> str:
        """
        Generuje pośrednią reprezentację z metadanymi gramatycznymi.
        
        Przykład: "Widziałem {name|case=acc|gender=fem} w {city|case=loc}"
        """
        # Wzbogać encje
        entities = self.enrich(text, entities)
        
        # Sortuj od końca (żeby indeksy się nie psuły)
        sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)
        
        result = text
        
        for entity in sorted_entities:
            token = entity.to_token(include_morphology=True)
            result = result[:entity.start] + token + result[entity.end:]
        
        return result
    
    def generate_final(
        self,
        text: str,
        entities: List[DetectedEntity]
    ) -> str:
        """
        Generuje finalną anonimizowaną wersję (bez metadanych).
        """
        # Sortuj od końca
        sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)
        
        result = text
        
        for entity in sorted_entities:
            token = entity.to_token(include_morphology=False)
            result = result[:entity.start] + token + result[entity.end:]
        
        return result


# Testy
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test analizatora
    analyzer = MorphologyAnalyzer(backend="spacy")
    
    text = "Widziałem Kasię w Gdańsku."
    entity = DetectedEntity(
        text="Kasię",
        entity_type=EntityType.NAME,
        start=11,
        end=16,
        confidence=0.9,
        source="test"
    )
    
    info = analyzer.analyze(text, entity)
    print(f"Morfologia '{entity.text}':")
    print(f"  Przypadek: {info.case}")
    print(f"  Rodzaj: {info.gender}")
    print(f"  Lemma: {info.lemma}")
    
    # Test inflektora
    inflector = PolishInflector()
    
    print("\nOdmiana 'Anna':")
    for case in Case:
        form = inflector.inflect("Anna", case, Gender.FEMININE)
        print(f"  {case.name}: {form}")
    
    # Test pipeline
    pipeline = EnrichmentPipeline()
    
    entities = [
        DetectedEntity(
            text="Kasię",
            entity_type=EntityType.NAME,
            start=11,
            end=16,
            confidence=0.9,
            source="test"
        ),
        DetectedEntity(
            text="Gdańsku",
            entity_type=EntityType.CITY,
            start=19,
            end=26,
            confidence=0.9,
            source="test"
        )
    ]
    
    intermediate = pipeline.generate_intermediate(text, entities)
    print(f"\nIntermediate: {intermediate}")
    
    final = pipeline.generate_final(text, entities)
    print(f"Final: {final}")