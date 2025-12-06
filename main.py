#!/usr/bin/env python3
"""
Użycie:
    python main.py --input data.txt --output results.txt
    python main.py --input data.txt --synthetic
    python main.py --text "Jan Kowalski mieszka w Warszawie"
    python main.py --interactive

Opcje:
    --input, -i       Plik wejściowy (.jsonl lub .txt)
    --output, -o      Plik wyjściowy (opcjonalny - generowany automatycznie)
    --text, -t        Pojedynczy tekst do anonimizacji
    --interactive     Tryb interaktywny
    --synthetic       Generuj dane syntetyczne
    --intermediate    Zachowaj pośrednią reprezentację
    --no-ml           Wyłącz warstwę ML (tylko regex)
    --model-path      Ścieżka do wytrenowanego modelu NER
    --morphology      Backend morfologiczny: 'spacy' lub 'stanza'
    --seed            Ziarno dla generatora danych syntetycznych
    --verbose, -v     Szczegółowe logi
    --quiet, -q       Minimalne logi
"""

import argparse
import json
import logging
import sys
from pathlib import Path

try:
    # Próba 1: Import z podkatalogu (struktura: ./anonymizer/anonymizer.py)
    # Składnia: from folder.plik import Klasa
    from anonymizer.anonymizer import Anonymizer, AnonymizerCLI
except ImportError:
    try:
        # Próba 2: Fallback - dodanie bieżącego katalogu do ścieżki (dla pewności)
        sys.path.insert(0, str(Path(__file__).parent))
        from anonymizer.anonymizer import Anonymizer, AnonymizerCLI
    except ImportError:
        # Próba 3: Stara struktura (plik anonymizer.py leży obok main.py)
        try:
            from anonymizer import Anonymizer, AnonymizerCLI
        except ImportError as e:
            logging.error("KRYTYCZNY BŁĄD: Nie znaleziono modułu 'anonymizer'.")
            logging.error(f"Upewnij się, że plik istnieje w './anonymizer/anonymizer.py' lub './anonymizer.py'")
            logging.error(f"Szczegóły błędu: {e}")
            sys.exit(1)

def setup_logging(verbose: bool = False, quiet: bool = False):
    """Konfiguruje system logowania."""
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )


def parse_args():
    """Parsuje argumenty wiersza poleceń."""
    parser = argparse.ArgumentParser(
        description='Dane bez Twarzy - System Anonimizacji',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Wejście/Wyjście
    io_group = parser.add_argument_group('Wejście/Wyjście')
    io_group.add_argument('-i', '--input', type=str, help='Plik wejściowy (.jsonl lub .txt)')
    io_group.add_argument('-o', '--output', type=str, help='Plik wyjściowy (opcjonalny)')
    io_group.add_argument('-t', '--text', type=str, help='Pojedynczy tekst do anonimizacji')
    io_group.add_argument('--interactive', action='store_true', help='Tryb interaktywny')
    
    # Opcje przetwarzania
    proc_group = parser.add_argument_group('Przetwarzanie')
    proc_group.add_argument('--synthetic', action='store_true', help='Generuj dane syntetyczne')
    proc_group.add_argument('--intermediate', action='store_true', help='Zachowaj pośrednią reprezentację')
    proc_group.add_argument('--no-ml', action='store_true', help='Wyłącz warstwę ML (tylko regex)')
    
    # Konfiguracja modeli
    model_group = parser.add_argument_group('Konfiguracja modeli')
    model_group.add_argument('--model-path', type=str, help='Ścieżka do modelu NER')
    model_group.add_argument('--morphology', type=str, choices=['spacy', 'stanza'], default='spacy', help='Backend morfologii')
    
    # Opcje dodatkowe
    extra_group = parser.add_argument_group('Opcje dodatkowe')
    extra_group.add_argument('--seed', type=int, help='Ziarno losowości')
    
    # Logowanie
    log_group = parser.add_argument_group('Logowanie')
    log_group.add_argument('-v', '--verbose', action='store_true', help='Logi DEBUG')
    log_group.add_argument('-q', '--quiet', action='store_true', help='Logi WARNING/ERROR')
    
    return parser.parse_args()


def run_interactive(anonymizer: Anonymizer):
    """Uruchamia tryb interaktywny."""
    print("=" * 50)
    print(" Dane bez Twarzy - Tryb Interaktywny")
    print(" Wpisz 'exit', aby zakończyć.")
    print("=" * 50)
    
    while True:
        try:
            text = input("\nTekst > ").strip()
            if not text: continue
            if text.lower() in ['quit', 'exit']: break
            
            result = anonymizer.anonymize(text)
            
            print(f"Anonim:   {result.anonymized}")
            if result.synthetic:
                print(f"Syntetyk: {result.synthetic}")
            if result.intermediate:
                print(f"Pośredni: {result.intermediate}")
                
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            logging.error(f"Błąd: {e}")


def main():
    args = parse_args()
    setup_logging(args.verbose, args.quiet)
    
    logger = logging.getLogger(__name__)
    
    # Walidacja wejścia
    if not any([args.input, args.text, args.interactive]):
        print("Błąd: Musisz podać --input, --text lub --interactive")
        sys.exit(1)
    
    # Automatyczna nazwa pliku wyjściowego
    if args.input and not args.output:
        inp = Path(args.input)
        # np. dane.txt -> dane_anonymized.txt
        args.output = str(inp.with_name(f"{inp.stem}_anonymized{inp.suffix}"))
        logger.info(f"Automatycznie ustawiono plik wyjściowy: {args.output}")

    # Inicjalizacja CLI (Orkiestratora)
    cli = AnonymizerCLI()
    
    # Konfiguracja anonimizatora (przekazanie argumentów)
    # Tworzymy prostą klasę lub słownik, jeśli AnonymizerCLI oczekuje obiektu args
    # Tutaj zakładamy, że metoda setup przyjmuje po prostu obiekt argparse.Namespace
    cli.setup(args)

    try:
        if args.interactive:
            run_interactive(cli.anonymizer)
        
        elif args.text:
            # Pojedynczy tekst - wynik na stdout jako JSON
            result = cli.process_text(args.text)
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        
        elif args.input:
            # Przetwarzanie pliku (format wykrywany automatycznie z rozszerzenia)
            cli.process_file(args.input, args.output)
            
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.exception("Wystąpił nieoczekiwany błąd podczas przetwarzania.")
        sys.exit(1)

if __name__ == "__main__":
    main()