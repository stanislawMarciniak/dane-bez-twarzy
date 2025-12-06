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
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing

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
    
    def to_dict(self) -> Dict:
        """Konwertuje do słownika."""
        return {
            'original': self.original,
            'anonymized': self.anonymized,
            'intermediate': self.intermediate,
            'synthetic': self.synthetic,
            'entities': self.entities or [],
            'processing_time_ms': self.processing_time_ms
        }


class Anonymizer:
    """
    Główny komponent anonimizujący.
    Łączy warstwę regex, ML i analizę morfologiczną.
    """
    
    def __init__(
        self,
        use_ml: bool = True,
        use_transformer: bool = False,
        custom_model_path: Optional[str] = None,
        morphology_backend: str = "spacy",
        generate_synthetic: bool = False,
        synthetic_seed: Optional[int] = None,
        include_intermediate: bool = False,
        device: str = "cpu",
        num_workers: int = 1
    ):
        """
        Inicjalizuje anonimizator.
        
        Args:
            use_ml: Czy używać warstwy ML (NER)
            use_transformer: Czy używać modelu Transformer zamiast SpaCy
            custom_model_path: Ścieżka do wytrenowanego modelu NER
            morphology_backend: Backend do analizy morfologicznej ('spacy' lub 'stanza')
            generate_synthetic: Czy generować dane syntetyczne
            synthetic_seed: Ziarno dla powtarzalności danych syntetycznych
            include_intermediate: Czy zachować pośrednią reprezentację
            device: Urządzenie dla modeli ML ('cpu' lub 'cuda')
            num_workers: Liczba workerów do przetwarzania równoległego
        """
        # Warstwy
        self.regex_layer = RegexLayer()
        
        self.ml_layer = None
        if use_ml:
            self.ml_layer = MLLayer(
                use_transformer=use_transformer,
                custom_model_path=custom_model_path,
                device=device
            )
        
        self.name_splitter = NameSurnameSplitter()
        
        self.enrichment_pipeline = EnrichmentPipeline(backend=morphology_backend)
        
        self.synthetic_pipeline = None
        if generate_synthetic:
            self.synthetic_pipeline = SyntheticDataPipeline(seed=synthetic_seed)
        
        # Konfiguracja
        self.include_intermediate = include_intermediate
        self.num_workers = num_workers
        
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
        
        # Etap 1: Warstwa Regex
        regex_entities = self.regex_layer.detect(text)
        logger.debug(f"Regex wykrył {len(regex_entities)} encji")
        
        # Etap 2: Warstwa ML
        ml_entities = []
        if self.ml_layer:
            ml_entities = self.ml_layer.detect(text, regex_entities)
            logger.debug(f"ML wykrył {len(ml_entities)} dodatkowych encji")
        
        # Połącz encje
        all_entities = self._merge_entities(regex_entities, ml_entities)
        
        # Etap 3: Rozdziel NAME/SURNAME
        all_entities = self._split_names(text, all_entities)
        
        # Etap 4: Wzbogacenie morfologiczne
        all_entities = self.enrichment_pipeline.enrich(text, all_entities)
        
        # Etap 5: Generowanie wyników
        intermediate = None
        if self.include_intermediate:
            intermediate = self._replace_entities(text, all_entities, include_morphology=True)
        
        anonymized = self._replace_entities(text, all_entities, include_morphology=False)
        
        # Etap 6: Dane syntetyczne (opcjonalnie)
        synthetic = None
        should_generate = generate_synthetic if generate_synthetic is not None else (
            self.synthetic_pipeline is not None
        )
        
        if should_generate and self.synthetic_pipeline:
            synthetic = self.synthetic_pipeline.generate_synthetic_text(
                anonymized,
                intermediate
            )
        
        processing_time = (time.time() - start_time) * 1000
        
        return AnonymizationResult(
            original=text,
            anonymized=anonymized,
            intermediate=intermediate,
            synthetic=synthetic,
            entities=[self._entity_to_dict(e) for e in all_entities],
            processing_time_ms=processing_time
        )
    
    def anonymize_batch(
        self,
        texts: List[str],
        generate_synthetic: Optional[bool] = None,
        show_progress: bool = True
    ) -> List[AnonymizationResult]:
        """
        Anonimizuje wiele tekstów.
        
        Args:
            texts: Lista tekstów do anonimizacji
            generate_synthetic: Czy generować dane syntetyczne
            show_progress: Czy pokazywać postęp
            
        Returns:
            Lista wyników anonimizacji
        """
        self.initialize()
        
        results = []
        total = len(texts)
        
        if self.num_workers > 1:
            # Przetwarzanie równoległe
            with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
                futures = [
                    executor.submit(self.anonymize, text, generate_synthetic)
                    for text in texts
                ]
                
                for i, future in enumerate(futures):
                    result = future.result()
                    results.append(result)
                    
                    if show_progress and (i + 1) % 100 == 0:
                        logger.info(f"Przetworzono {i + 1}/{total} tekstów")
        else:
            # Przetwarzanie sekwencyjne
            for i, text in enumerate(texts):
                result = self.anonymize(text, generate_synthetic)
                results.append(result)
                
                if show_progress and (i + 1) % 100 == 0:
                    logger.info(f"Przetworzono {i + 1}/{total} tekstów")
        
        return results
    
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
            use_transformer=args.transformer,
            custom_model_path=args.model_path,
            morphology_backend=args.morphology,
            generate_synthetic=args.synthetic,
            synthetic_seed=args.seed,
            include_intermediate=args.intermediate,
            device=args.device,
            num_workers=args.workers
        )
    
    def process_file(self, input_path: str, output_path: str, format: str = None):
        """
        Przetwarza plik wejściowy i zapisuje wyniki.
        
        Logika dla formatów:
        - JSONL: Wczytuje obiekty JSON, zapisuje obiekty JSON z metadanymi.
        - TXT: Wczytuje plik LINIA PO LINII (każda linia to osobny przykład).
               Zapisuje plik wyjściowy LINIA PO LINII (czysty tekst).
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Plik nie istnieje: {input_path}")
        
        # Autodetekcja formatu, jeśli nie podano
        if format is None:
            if input_path.suffix.lower() == '.jsonl':
                format = 'jsonl'
            else:
                format = 'txt'  # Domyślnie txt
                
        logger.info(f"Rozpoczynam przetwarzanie pliku: {input_path} (Format: {format})")

        # 1. WCZYTYWANIE DANYCH
        texts = []
        if format == 'jsonl':
            with open(input_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line.strip())
                        texts.append(data.get('text', data.get('content', '')))
        
        elif format == 'txt':
            with open(input_path, 'r', encoding='utf-8') as f:
                # ZMIANA: Czytamy linia po linii. 
                # rstrip() usuwa znak nowej linii, ale zachowuje spacje w treści
                texts = [line.rstrip('\n') for line in f]
                # Opcjonalnie: usuwamy puste linie, jeśli nie chcemy ich przetwarzać
                # texts = [t for t in texts if t.strip()] 
        
        else:
            raise ValueError(f"Nieobsługiwany format: {format}")
        
        logger.info(f"Wczytano {len(texts)} linii/przykładów.")
        
        # 2. PRZETWARZANIE (BATCH)
        if not texts:
            logger.warning("Plik wejściowy jest pusty.")
            return

        results = self.anonymizer.anonymize_batch(texts)
        
        # 3. ZAPISYWANIE WYNIKÓW
        with open(output_path, 'w', encoding='utf-8') as f:
            if format == 'txt':
                # ZMIANA: Zapisujemy tylko wynikowy tekst, linia po linii
                for result in results:
                    # Priorytet: Syntetyk > Anonimizowany > Oryginał
                    if result.synthetic:
                        line_out = result.synthetic
                    else:
                        line_out = result.anonymized
                    
                    f.write(line_out + '\n')
            
            else: # jsonl
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
    format: str = 'jsonl',
    **kwargs
) -> None:
    """
    Anonimizuje plik.
    
    Args:
        input_path: Ścieżka do pliku wejściowego
        output_path: Ścieżka do pliku wyjściowego
        format: Format pliku ('jsonl' lub 'txt')
        **kwargs: Dodatkowe argumenty dla Anonymizer
    """
    cli = AnonymizerCLI()
    
    class Args:
        def __init__(self, **kwargs):
            self.no_ml = kwargs.get('no_ml', False)
            self.transformer = kwargs.get('use_transformer', False)
            self.model_path = kwargs.get('custom_model_path')
            self.morphology = kwargs.get('morphology_backend', 'spacy')
            self.synthetic = kwargs.get('generate_synthetic', False)
            self.seed = kwargs.get('synthetic_seed')
            self.intermediate = kwargs.get('include_intermediate', False)
            self.device = kwargs.get('device', 'cpu')
            self.workers = kwargs.get('num_workers', 1)
    
    cli.setup(Args(**kwargs))
    cli.process_file(input_path, output_path, format)


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