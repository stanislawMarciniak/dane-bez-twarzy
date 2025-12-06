"""
Główny Anonimizator - Orkiestrator
Łączy wszystkie warstwy w jeden spójny pipeline przetwarzania.
"""

import logging
import json
from typing import List, Dict, Optional, Tuple, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import time

from .regex_layer import RegexLayer, DetectedEntity, EntityType
from .ml_layer import MLLayer, NameSurnameSplitter
from .morphology import EnrichmentPipeline, MorphologyAnalyzer
from .synthetic_generator import SyntheticDataPipeline

logger = logging.getLogger(__name__)


@dataclass
class AnonymizationResult:
    """Wynik anonimizacji pojedynczego tekstu."""
    original: str
    anonymized: str
    intermediate: Optional[str] = None
    synthetic: Optional[str] = None
    entities: List[Dict] = None
    processing_time_ms: float = 0.0
    layer_times: Optional[Dict[str, float]] = None
    
    def to_dict(self) -> Dict:
        """Konwertuje do słownika."""
        return {
            'original': self.original,
            'anonymized': self.anonymized,
            'intermediate': self.intermediate,
            'synthetic': self.synthetic,
            'entities': self.entities or [],
            'processing_time_ms': self.processing_time_ms,
            'layer_times': self.layer_times or {}
        }


class Anonymizer:
    """
    Główny komponent anonimizujący.
    Łączy warstwę regex, ML i analizę morfologiczną.
    """
    
    def __init__(
        self,
        use_ml: bool = True,
        custom_model_path: Optional[str] = None,
        morphology_backend: str = "spacy",
        generate_synthetic: bool = False,
        synthetic_seed: Optional[int] = None,
        include_intermediate: bool = False
    ):
        """
        Inicjalizuje anonimizator.
        
        Args:
            use_ml: Czy używać warstwy ML (NER)
            custom_model_path: Ścieżka do wytrenowanego modelu NER
            morphology_backend: Backend do analizy morfologicznej ('spacy' lub 'stanza')
            generate_synthetic: Czy generować dane syntetyczne
            synthetic_seed: Ziarno dla powtarzalności danych syntetycznych
            include_intermediate: Czy zachować pośrednią reprezentację
        """
        # Warstwy
        self.regex_layer = RegexLayer()
        
        self.ml_layer = None
        if use_ml:
            self.ml_layer = MLLayer(
                custom_model_path=custom_model_path
            )
        
        self.name_splitter = NameSurnameSplitter()
        
        self.enrichment_pipeline = EnrichmentPipeline(backend=morphology_backend)
        
        self.synthetic_pipeline = None
        if generate_synthetic:
            self.synthetic_pipeline = SyntheticDataPipeline(seed=synthetic_seed)
        
        # Konfiguracja
        self.include_intermediate = include_intermediate
        
        self._initialized = False
    
    def initialize(self):
        """Lazy initialization wszystkich komponentów."""
        if self._initialized:
            return
        
        logger.info("Inicjalizacja anonimizatora...")
        
        if self.ml_layer:
            self.ml_layer.initialize()
        
        self.enrichment_pipeline.analyzer.initialize()
        
        self._initialized = True
        logger.info("Anonimizator zainicjalizowany")
    
    def anonymize(
        self,
        text: str,
        generate_synthetic: Optional[bool] = None
    ) -> AnonymizationResult:
        """
        Anonimizuje pojedynczy tekst.
        
        Args:
            text: Tekst do anonimizacji
            generate_synthetic: Czy generować dane syntetyczne (nadpisuje domyślne)
            
        Returns:
            Wynik anonimizacji
        """
        self.initialize()
        
        start_time = time.time()
        layer_times = {}
        
        # Etap 1: Warstwa Regex
        t0 = time.time()
        regex_entities = self.regex_layer.detect(text)
        layer_times['regex'] = (time.time() - t0) * 1000
        logger.debug(f"Regex wykrył {len(regex_entities)} encji ({layer_times['regex']:.2f} ms)")
        
        # Etap 2: Warstwa ML
        ml_entities = []
        if self.ml_layer:
            t0 = time.time()
            ml_entities = self.ml_layer.detect(text, regex_entities)
            layer_times['ml'] = (time.time() - t0) * 1000
            logger.debug(f"ML wykrył {len(ml_entities)} dodatkowych encji ({layer_times['ml']:.2f} ms)")
        
        # Połącz encje
        t0 = time.time()
        all_entities = self._merge_entities(regex_entities, ml_entities)
        layer_times['merge'] = (time.time() - t0) * 1000
        
        # Etap 3: Rozdziel NAME/SURNAME
        t0 = time.time()
        all_entities = self._split_names(text, all_entities)
        layer_times['split_names'] = (time.time() - t0) * 1000
        
        # Etap 4: Wzbogacenie morfologiczne
        t0 = time.time()
        all_entities = self.enrichment_pipeline.enrich(text, all_entities)
        layer_times['morphology'] = (time.time() - t0) * 1000
        logger.debug(f"Wzbogacenie morfologiczne ({layer_times['morphology']:.2f} ms)")
        
        # Etap 5: Generowanie wyników
        t0 = time.time()
        intermediate = None
        if self.include_intermediate:
            intermediate = self._replace_entities(text, all_entities, include_morphology=True)
        anonymized = self._replace_entities(text, all_entities, include_morphology=False)
        layer_times['replace'] = (time.time() - t0) * 1000
        
        # Etap 6: Dane syntetyczne (opcjonalnie)
        synthetic = None
        should_generate = generate_synthetic if generate_synthetic is not None else (
            self.synthetic_pipeline is not None
        )
        
        if should_generate and self.synthetic_pipeline:
            t0 = time.time()
            synthetic = self.synthetic_pipeline.generate_synthetic_text(
                anonymized,
                intermediate
            )
            layer_times['synthetic'] = (time.time() - t0) * 1000
            logger.debug(f"Generowanie syntetyczne ({layer_times['synthetic']:.2f} ms)")
        
        processing_time = (time.time() - start_time) * 1000
        
        return AnonymizationResult(
            original=text,
            anonymized=anonymized,
            intermediate=intermediate,
            synthetic=synthetic,
            entities=[self._entity_to_dict(e) for e in all_entities],
            processing_time_ms=processing_time,
            layer_times=layer_times
        )
    
    def anonymize_batch(
        self,
        texts: List[str],
        generate_synthetic: Optional[bool] = None,
        show_progress: bool = True
    ) -> Tuple[List[AnonymizationResult], Dict[str, float]]:
        """
        Anonimizuje wiele tekstów.
        
        Args:
            texts: Lista tekstów do anonimizacji
            generate_synthetic: Czy generować dane syntetyczne
            show_progress: Czy pokazywać postęp
            
        Returns:
            Tuple: (Lista wyników anonimizacji, średnie czasy warstw)
        """
        self.initialize()
        
        results = []
        total = len(texts)
        
        # Zbierz wszystkie czasy warstw
        all_layer_times = []
        
        # Przetwarzanie sekwencyjne
        for i, text in enumerate(texts):
            result = self.anonymize(text, generate_synthetic)
            results.append(result)
            
            if result.layer_times:
                all_layer_times.append(result.layer_times)
            
            if show_progress and (i + 1) % 100 == 0:
                logger.info(f"Przetworzono {i + 1}/{total} tekstów")
        
        # Oblicz średnie czasy dla każdej warstwy
        avg_layer_times = {}
        if all_layer_times:
            # Zbierz wszystkie klucze
            all_keys = set()
            for layer_times in all_layer_times:
                all_keys.update(layer_times.keys())
            
            # Oblicz średnie
            for key in all_keys:
                values = [lt.get(key, 0) for lt in all_layer_times if key in lt]
                if values:
                    avg_layer_times[key] = sum(values) / len(values)
        
        return results, avg_layer_times
    
    def _merge_entities(
        self,
        regex_entities: List[DetectedEntity],
        ml_entities: List[DetectedEntity]
    ) -> List[DetectedEntity]:
        """Łączy encje z obu warstw, preferując regex."""
        all_entities = regex_entities.copy()
        
        for ml_entity in ml_entities:
            # Sprawdź czy nie nakłada się z regex
            overlaps = False
            for regex_entity in regex_entities:
                if not (ml_entity.end <= regex_entity.start or 
                        ml_entity.start >= regex_entity.end):
                    overlaps = True
                    break
            
            if not overlaps:
                all_entities.append(ml_entity)
        
        # Sortuj po pozycji
        all_entities.sort(key=lambda e: e.start)
        
        return all_entities
    
    def _split_names(
        self,
        text: str,
        entities: List[DetectedEntity]
    ) -> List[DetectedEntity]:
        """Rozdziela encje typu NAME na NAME i SURNAME."""
        result = []
        
        for entity in entities:
            if entity.entity_type == EntityType.NAME and ' ' in entity.text:
                # Spróbuj rozdzielić
                split = self.name_splitter.split_person(text, entity)
                result.extend(split)
            else:
                result.append(entity)
        
        return result
    
    def _replace_entities(
        self,
        text: str,
        entities: List[DetectedEntity],
        include_morphology: bool = False
    ) -> str:
        """Podmienia encje na tokeny zastępcze."""
        # Sortuj od końca żeby indeksy się nie psuły
        sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)
        
        result = text
        
        for entity in sorted_entities:
            token = entity.to_token(include_morphology=include_morphology)
            result = result[:entity.start] + token + result[entity.end:]
        
        return result
    
    def _entity_to_dict(self, entity: DetectedEntity) -> Dict:
        """Konwertuje encję do słownika."""
        return {
            'text': entity.text,
            'type': entity.entity_type.value,
            'start': entity.start,
            'end': entity.end,
            'confidence': entity.confidence,
            'source': entity.source,
            'morphology': entity.morphology
        }


class AnonymizerCLI:
    """
    Interfejs wiersza poleceń dla anonimizatora.
    """
    
    def __init__(self):
        self.anonymizer = None
    
    def setup(self, args):
        """Konfiguruje anonimizator na podstawie argumentów."""
        self.anonymizer = Anonymizer(
            use_ml=not args.no_ml,
            custom_model_path=args.model_path,
            morphology_backend=args.morphology,
            generate_synthetic=args.synthetic,
            synthetic_seed=args.seed,
            include_intermediate=args.intermediate
        )
    
    def process_file(self, input_path: str, output_path: str):
        """
        Przetwarza plik wejściowy i zapisuje wyniki.
        
        Obsługiwane formaty (wykrywane z rozszerzenia):
        - .jsonl: Wczytuje obiekty JSON, zapisuje obiekty JSON z metadanymi.
        - .txt: Wczytuje plik LINIA PO LINII (każda linia to osobny przykład).
                Zapisuje plik wyjściowy LINIA PO LINII (czysty tekst).
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Plik nie istnieje: {input_path}")
        
        # Autodetekcja formatu z rozszerzenia pliku
        suffix = input_path.suffix.lower()
        if suffix == '.jsonl':
            file_format = 'jsonl'
        elif suffix == '.txt':
            file_format = 'txt'
        else:
            print(f"Błąd: Nieobsługiwany typ pliku '{suffix}'. Obsługiwane formaty: .txt, .jsonl")
            return
                
        logger.info(f"Rozpoczynam przetwarzanie pliku: {input_path} (Format: {file_format})")

        # 1. WCZYTYWANIE DANYCH
        texts = []
        if file_format == 'jsonl':
            with open(input_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line.strip())
                        texts.append(data.get('text', data.get('content', '')))
        
        elif file_format == 'txt':
            with open(input_path, 'r', encoding='utf-8') as f:
                # Czytamy linia po linii. 
                # rstrip() usuwa znak nowej linii, ale zachowuje spacje w treści
                texts = [line.rstrip('\n') for line in f]
        
        logger.info(f"Wczytano {len(texts)} linii/przykładów.")
        
        # 2. PRZETWARZANIE (BATCH)
        if not texts:
            logger.warning("Plik wejściowy jest pusty.")
            return

        results, avg_layer_times = self.anonymizer.anonymize_batch(texts)
        
        # 3. ZAPISYWANIE WYNIKÓW
        with open(output_path, 'w', encoding='utf-8') as f:
            if file_format == 'txt':
                # Zapisujemy tylko wynikowy tekst, linia po linii
                for result in results:
                    # Priorytet: Syntetyk > Anonimizowany > Oryginał
                    if result.synthetic:
                        line_out = result.synthetic
                    else:
                        line_out = result.anonymized
                    
                    f.write(line_out + '\n')
            
            else:  # jsonl
                for result in results:
                    f.write(json.dumps(result.to_dict(), ensure_ascii=False) + '\n')
        
        logger.info(f"Zapisano wyniki do: {output_path}")
        
        # Statystyki
        total_time = sum(r.processing_time_ms for r in results)
        avg_time = total_time / len(results) if results else 0
        total_entities = sum(len(r.entities) for r in results)
        
        logger.info(f"Statystyki:")
        logger.info(f"  Łączny czas: {total_time:.2f} ms")
        logger.info(f"  Średni czas/linijkę: {avg_time:.2f} ms")
        logger.info(f"  Wykryto encji: {total_entities}")
        
        # Wyświetl średnie czasy warstw
        if avg_layer_times:
            layer_times_str = ", ".join(f"{k}={v:.2f}ms" for k, v in avg_layer_times.items())
            logger.info(f"  Średnie czasy warstw: {layer_times_str}")

    def process_text(self, text: str):
        return self.anonymizer.anonymize(text)


def create_anonymizer(**kwargs) -> Anonymizer:
    """
    Factory function do tworzenia anonimizatora.
    
    Args:
        **kwargs: Argumenty przekazywane do Anonymizer
        
    Returns:
        Skonfigurowany anonimizator
    """
    return Anonymizer(**kwargs)


# API uproszczone
def anonymize_text(
    text: str,
    generate_synthetic: bool = False,
    include_intermediate: bool = False
) -> Dict:
    """
    Prosty interfejs do anonimizacji pojedynczego tekstu.
    
    Args:
        text: Tekst do anonimizacji
        generate_synthetic: Czy generować dane syntetyczne
        include_intermediate: Czy zachować pośrednią reprezentację
        
    Returns:
        Słownik z wynikami
    """
    anonymizer = Anonymizer(
        use_ml=True,
        generate_synthetic=generate_synthetic,
        include_intermediate=include_intermediate
    )
    
    result = anonymizer.anonymize(text, generate_synthetic)
    return result.to_dict()


def anonymize_file(
    input_path: str,
    output_path: str,
    **kwargs
) -> None:
    """
    Anonimizuje plik.
    
    Args:
        input_path: Ścieżka do pliku wejściowego (.txt lub .jsonl)
        output_path: Ścieżka do pliku wyjściowego
        **kwargs: Dodatkowe argumenty dla Anonymizer
    """
    cli = AnonymizerCLI()
    
    class Args:
        def __init__(self, **kwargs):
            self.no_ml = kwargs.get('no_ml', False)
            self.model_path = kwargs.get('custom_model_path')
            self.morphology = kwargs.get('morphology_backend', 'spacy')
            self.synthetic = kwargs.get('generate_synthetic', False)
            self.seed = kwargs.get('synthetic_seed')
            self.intermediate = kwargs.get('include_intermediate', False)
    
    cli.setup(Args(**kwargs))
    cli.process_file(input_path, output_path)


# Testy
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test podstawowy
    print("=== Test podstawowy ===")
    anonymizer = Anonymizer(
        use_ml=True,
        generate_synthetic=True,
        include_intermediate=True
    )
    
    test_text = """
    Nazywam się Jan Kowalski, mój PESEL to 90010112345. 
    Mieszkam w Warszawie przy ulicy Długiej 5. 
    Mój email to jan.kowalski@gmail.com, telefon: +48 123 456 789.
    Pracuję w firmie TechPol jako programista.
    """
    
    result = anonymizer.anonymize(test_text)
    
    print(f"\nOryginalny tekst:\n{result.original}")
    print(f"\nZanonimizowany:\n{result.anonymized}")
    print(f"\nPośredni (z morfologią):\n{result.intermediate}")
    print(f"\nSyntetyczny:\n{result.synthetic}")
    print(f"\nWykryte encje:")
    for entity in result.entities:
        print(f"  - {entity['type']}: '{entity['text']}' (pewność: {entity['confidence']:.2f})")
    print(f"\nCzas przetwarzania: {result.processing_time_ms:.2f} ms")
    
    # Test uproszczonego API
    print("\n=== Test uproszczonego API ===")
    simple_result = anonymize_text(
        "Cześć, jestem Adam Nowak, mam 30 lat.",
        generate_synthetic=True
    )
    print(f"Wynik: {simple_result['anonymized']}")
    print(f"Syntetyczny: {simple_result['synthetic']}")