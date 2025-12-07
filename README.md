# Dane bez Twarzy

**System anonimizacji danych osobowych w tekstach polskich**

Biblioteka Python do automatycznej detekcji i anonimizacji danych wrażliwych w tekstach w języku polskim. Zaprojektowana dla projektu PLLuM (Polish Large Language Model).

## Cele projektu

- **Bezpieczeństwo danych** - wykrywanie i anonimizacja danych osobowych zgodnie z RODO
- **Zachowanie struktury** - podmiana encji na tokeny zachowujące sens i gramatykę
- **Wsparcie dla polskiego** - pełna obsługa fleksji i kontekstu językowego
- **Wydajność** - skalowalne rozwiązanie do przetwarzania dużych zbiorów danych

## Architektura

System wykorzystuje wielowarstwową architekturę:

```
┌─────────────────────────────────────────────────────────────┐
│                        WEJŚCIE                              │
│              "Jan Kowalski, PESEL 90010112345"              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               ETAP 1: WARSTWA REGEX                         │
│                    "Szybkie Sito"                           │
│  • PESEL (z walidacją sumy kontrolnej)                      │
│  • Email, telefon, IBAN                                     │
│  • Daty (różne formaty)                                     │
│  • Numery dokumentów                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              ETAP 2: WARSTWA ML (NER)                       │
│                   "Inteligencja"                            │
│  • Imiona i nazwiska                                        │
│  • Miasta vs adresy (rozróżnienie kontekstu)                │
│  • Firmy, szkoły, stanowiska                                │
│  • Dane wrażliwe (zdrowie, religia, poglądy)                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│           ETAP 3: ANALIZA MORFOLOGICZNA                     │
│  • Przypadek (mianownik, dopełniacz, biernik...)            │
│  • Rodzaj (męski, żeński, nijaki)                           │
│  • Liczba (pojedyncza, mnoga)                               │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
    ┌───────────────────────┐   ┌───────────────────────┐
    │   ŚCIEŻKA A           │   │   ŚCIEŻKA B           │
    │   Ewaluacja           │   │   Dane Syntetyczne    │
    │   (F1-score)          │   │   (Bonus 20%)         │
    └───────────────────────┘   └───────────────────────┘
                    │                   │
                    ▼                   ▼
    ┌───────────────────────┐   ┌───────────────────────┐
    │ "{name} {surname},    │   │ "Maria Nowak,         │
    │  PESEL {pesel}"       │   │  PESEL 12345678901"   │
    └───────────────────────┘   └───────────────────────┘
```

## Instalacja

### Wymagania

- Python 3.8+
- pip

### Podstawowa instalacja

```bash
# Klonowanie repozytorium
git clone git@github.com:stanislawMarciniak/dane-bez-twarzy.git
cd dane-bez-twarzy

# Stworzenie wirtualnego środowiska
python -m venv venv
source venv/bin/activate

# Instalacja zależności
pip install -r requirements.txt

# Pobranie modelu SpaCy dla polskiego
python -m spacy download pl_core_news_lg
```

### Instalacja z obsługą GPU (opcjonalna)

```bash
# PyTorch z CUDA
pip install torch --index-url https://download.pytorch.org/whl/cu118

# Użycie GPU
python main.py --device cuda --input dane.txt --output wyniki.txt
```

## Użycie

### Interfejs wiersza poleceń (CLI)

```bash
# Pojedynczy tekst
python main.py -t "Jan Kowalski mieszka w Warszawie"

# Pojedynczy tekst podmieniony
python main.py -t "Jan Kowalski mieszka w Warszawie" --synthetic

# Przetwarzanie pliku
python main.py -i ./data/orig.txt -o ./results/results.txt

# Z generacją danych syntetycznych
python main.py -i ./data/orig.txt -o ./results/results.txt --synthetic

# Tryb interaktywny
python main.py --interactive

# Szczegółowe opcje
python main.py --help
```

### API Python

```python
from anonymizer import anonymize_text, Anonymizer

# Proste użycie
result = anonymize_text(
    "Nazywam się Jan Kowalski, mój PESEL to 90010112345.",
    generate_synthetic=True
)
print(result['anonymized'])
# "Nazywam się {name} {surname}, mój PESEL to {pesel}."

print(result['synthetic'])
# "Nazywam się Adam Nowak, mój PESEL to 85032145678."
```

### Zaawansowane użycie

```python
from anonymizer import Anonymizer

# Pełna konfiguracja
anonymizer = Anonymizer(
    use_ml=True,                    # Włącz warstwę ML (NER)
    use_transformer=False,          # Użyj SpaCy (szybsze) zamiast Transformer
    morphology_backend="spacy",     # Backend morfologiczny
    generate_synthetic=True,        # Generuj dane syntetyczne
    include_intermediate=True,      # Zachowaj pośrednią reprezentację
    device="cpu",                   # Urządzenie (cpu/cuda)
    num_workers=4                   # Liczba workerów
)

# Pojedynczy tekst
result = anonymizer.anonymize("""
Pacjent: Jan Kowalski
PESEL: 90010112345
Adres: ul. Długa 5, 00-001 Warszawa
Email: jan.kowalski@gmail.com
Diagnoza: cukrzyca typu 2
""")

print(result.anonymized)
print(result.intermediate)  # Z metadanymi morfologicznymi
print(result.synthetic)     # Dane syntetyczne
print(result.entities)      # Lista wykrytych encji

# Przetwarzanie wsadowe
texts = ["Tekst 1...", "Tekst 2...", "Tekst 3..."]
results = anonymizer.anonymize_batch(texts, show_progress=True)
```

### Przetwarzanie plików

```python
from anonymizer import anonymize_file

# JSONL
anonymize_file(
    "dane_wejsciowe.jsonl",
    "dane_wyjsciowe.jsonl",
    format="jsonl",
    generate_synthetic=True
)

# TXT (jeden tekst na linię)
anonymize_file(
    "teksty.txt",
    "teksty_anonimizowane.txt",
    format="txt"
)
```

## Obsługiwane kategorie danych

### 1. Dane identyfikacyjne osobowe

| Token                  | Opis                 | Przykład            |
| ---------------------- | -------------------- | ------------------- |
| `{name}`               | Imiona               | Jan, Anna           |
| `{surname}`            | Nazwiska             | Kowalski, Nowak     |
| `{age}`                | Wiek                 | 25 lat              |
| `{date-of-birth}`      | Data urodzenia       | 15.03.1990          |
| `{date}`               | Inne daty            | przyjęto 23.09.2023 |
| `{sex}`                | Płeć                 | mężczyzna, kobieta  |
| `{religion}`           | Wyznanie             | katolik             |
| `{political-view}`     | Poglądy polityczne   | konserwatysta       |
| `{ethnicity}`          | Pochodzenie etniczne | Ukrainiec           |
| `{sexual-orientation}` | Orientacja seksualna | heteroseksualny     |
| `{health}`             | Dane zdrowotne       | cukrzyca typu 2     |
| `{relative}`           | Relacje rodzinne     | mój brat Piotr      |

### 2. Dane kontaktowe i lokalizacyjne

| Token       | Opis                        | Przykład                     |
| ----------- | --------------------------- | ---------------------------- |
| `{city}`    | Miasto (lokalizacja ogólna) | Jadę do Krakowa              |
| `{address}` | Pełny adres                 | ul. Długa 5, 00-001 Warszawa |
| `{email}`   | Adres email                 | jan@gmail.com                |
| `{phone}`   | Numer telefonu              | +48 123 456 789              |

### 3. Identyfikatory dokumentów

| Token               | Opis              | Przykład    |
| ------------------- | ----------------- | ----------- |
| `{pesel}`           | Numer PESEL       | 90010112345 |
| `{document-number}` | Numery dokumentów | ABC123456   |

### 4. Dane zawodowe i edukacyjne

| Token           | Opis         | Przykład               |
| --------------- | ------------ | ---------------------- |
| `{company}`     | Nazwa firmy  | TechPol Sp. z o.o.     |
| `{school-name}` | Nazwa szkoły | Uniwersytet Warszawski |
| `{job-title}`   | Stanowisko   | programista            |

### 5. Informacje finansowe

| Token                  | Opis        | Przykład            |
| ---------------------- | ----------- | ------------------- |
| `{bank-account}`       | Numer konta | PL12 1234 ...       |
| `{credit-card-number}` | Numer karty | 4111 1111 1111 1111 |

### 6. Identyfikatory cyfrowe

| Token        | Opis                    | Przykład        |
| ------------ | ----------------------- | --------------- |
| `{username}` | Login/nazwa użytkownika | @janek123       |
| `{secret}`   | Hasła, klucze API       | hasło: tajne123 |

## Konfiguracja

### Opcje CLI

```
Wejście/Wyjście:
  -i, --input       Plik wejściowy (JSONL lub TXT)
  -o, --output      Plik wyjściowy
  -t, --text        Pojedynczy tekst do anonimizacji
  --interactive     Tryb interaktywny
  --format          Format pliku: jsonl lub txt

Przetwarzanie:
  --synthetic       Generuj dane syntetyczne
  --intermediate    Zachowaj pośrednią reprezentację
  --no-ml           Wyłącz warstwę ML (tylko regex)

Modele:
  --transformer     Użyj modelu Transformer
  --model-path      Ścieżka do własnego modelu NER
  --morphology      Backend: spacy lub stanza
  --device          cpu lub cuda

Wydajność:
  --workers         Liczba workerów (domyślnie: 1)
  --seed            Ziarno dla generatora

Logowanie:
  -v, --verbose     Szczegółowe logi
  -q, --quiet       Minimalne logi
```

## Format danych

### Wejście (JSONL)

```json
{"text": "Jan Kowalski mieszka w Warszawie."}
{"text": "Kontakt: anna@email.pl, tel. 123456789"}
```

### Wyjście (JSONL)

```json
{
  "original": "Jan Kowalski mieszka w Warszawie.",
  "anonymized": "{name} {surname} mieszka w {city}.",
  "intermediate": "{name|case=nom|gender=m} {surname|case=nom|gender=m} mieszka w {city|case=loc}.",
  "synthetic": "Adam Nowak mieszka w Krakowie.",
  "entities": [
    { "text": "Jan", "type": "name", "start": 0, "end": 3, "confidence": 0.95 },
    {
      "text": "Kowalski",
      "type": "surname",
      "start": 4,
      "end": 12,
      "confidence": 0.95
    },
    {
      "text": "Warszawie",
      "type": "city",
      "start": 24,
      "end": 33,
      "confidence": 0.9
    }
  ],
  "processing_time_ms": 45.2
}
```

## Testowanie

```bash
# Uruchomienie testów
python -m pytest tests/ -v

# Z pokryciem kodu
python -m pytest tests/ --cov=anonymizer --cov-report=html

# Testy wydajności
python -m pytest tests/test_performance.py -v
```
