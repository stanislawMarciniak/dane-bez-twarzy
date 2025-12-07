# Preprocessing - Zespół Overfitters

> **Uwaga:** W kontekście tego projektu termin "preprocessing" jest używany w rozumieniu zadania konkursowego. W rzeczywistości system **nie wykonuje klasycznego preprocessingu NLP** - tekst przechodzi przez pipeline w formie niezmienionej. Jedynym prawdziwym preprocessingiem jest wewnętrzna tokenizacja wykonywana przez SpaCy.

## 1. Pozyskiwanie Danych (Data Acquisition)

System obsługuje trzy główne źródła danych wejściowych:

- **Pliki JSONL** (JSON Lines) - format strumieniowy, każda linia = 1 przykład
- **Pliki TXT** - tekst czysty, każda linia = 1 przykład do przetworzenia
- **Stdin/Interactive** - pojedyncze teksty wprowadzane przez użytkownika

### 1.1. Autodetekcja Formatu

System automatycznie rozpoznaje format danych na podstawie rozszerzenia pliku:

```python
suffix = input_path.suffix.lower()
if suffix == '.jsonl':
    file_format = 'jsonl'
elif suffix == '.txt':
    file_format = 'txt'
```

## 2. Wczytywanie Danych

### 2.1. Format JSONL

Każda linia pliku jest parsowana jako osobny obiekt JSON:

```python
with open(input_path, 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():  # Pomija puste linie
            data = json.loads(line.strip())
            texts.append(data.get('text', data.get('content', '')))
```

**Kroki wczytywania dla JSONL:**

1. Wczytanie linii z pliku (encoding: UTF-8)
2. Strip białych znaków (`line.strip()`)
3. Filtrowanie pustych linii
4. Parsowanie JSON
5. Ekstrakcja pola tekstowego (próba `'text'`, fallback na `'content'`)
6. Dodanie do listy tekstów do przetworzenia

### 2.2. Format TXT

Linie są wczytywane sekwencyjnie, każda jako osobny przykład:

```python
with open(input_path, 'r', encoding='utf-8') as f:
    texts = [line.rstrip('\n') for line in f]
```

**Kroki wczytywania dla TXT:**

1. Wczytanie pliku (encoding: UTF-8)
2. Każda linia = 1 przykład
3. Usunięcie znaku nowej linii z końca (`rstrip('\n')`)
4. **Zachowanie spacji i białych znaków wewnątrz linii**

## 3. Brak Klasycznego Preprocessingu

System **celowo NIE wykonuje** typowych operacji preprocessingu NLP:

- ❌ Lowercase (konwersja na małe litery)
- ❌ Usuwanie znaków specjalnych
- ❌ Usuwanie stopwords
- ❌ Stemming/Lemmatization na wejściu
- ❌ Normalizacja Unicode
- ❌ Czyszczenie HTML/Markdown
- ❌ **Chunking** (dzielenie długich tekstów)

**Dlaczego brak preprocessingu?**

1. Regex musi wykryć wzorce z wielkimi literami (np. inicjały, numery dokumentów ABC123456)
2. Model NER (SpaCy) sam wykonuje wewnętrzną tokenizację
3. Zachowanie oryginalnej struktury dla mapowania pozycji (start/end char)
4. Warstwa morfologiczna wymaga oryginalnych form (odmiana przez przypadki)

## 4. Jedyny "Prawdziwy" Preprocessing - Tokenizacja SpaCy

Jedynym miejscem gdzie następuje rzeczywiste przetwarzanie tekstu jest **wewnętrzna tokenizacja SpaCy**:

```python
# W ml_layer.py
doc = self.nlp(text)  # SpaCy wykonuje tokenizację
for ent in doc.ents:
    # Przetwarzanie wykrytych encji
```

SpaCy wewnętrznie wykonuje:

- Tokenizację (podział na tokeny)
- Tagowanie POS (części mowy)
- Dependency parsing
- Named Entity Recognition (NER)

**Ważne:** Tekst jest przekazywany do SpaCy w formie niezmienionej - nie ma żadnego chunking'u dla długich tekstów. System zakłada, że pojedyncze linie/przykłady mieszczą się w limitach pamięci modelu.

## 5. Pipeline Przetwarzania

Faktyczna kolejność przetwarzania w pipeline:

> **Uwaga:** W pierwotnym założeniu zadania warstwa Regex miała działać jako preprocessing przed modelem ML. W obecnej implementacji kolejność jest odwrotna - najpierw ML (SpaCy), potem Regex. Warstwa Regex nadal pełni ważną rolę w wykrywaniu wzorców strukturalnych, ale technicznie nie jest już "preprocessingiem".

```
Tekst wejściowy (bez zmian)
       ↓
┌──────────────────────────────────────────┐
│ Etap 1: Warstwa ML (SpaCy NER)           │
│ - Wykrywa: imiona, nazwiska, miasta,     │
│   firmy, daty (encje kontekstowe)        │
│ - Zwraca: ml_entities                    │
└──────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────┐
│ Etap 2: Warstwa REGEX                    │
│ - Otrzymuje: tekst + ml_entities         │
│ - Pomija obszary już wykryte przez ML    │
│ - Wykrywa: PESEL, email, telefon,        │
│   konta bankowe, adresy (wzorce stałe)   │
│ - Zwraca: regex_entities                 │
└──────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────┐
│ Etap 3: Merge + Name Splitting           │
│ - Łączy encje z obu warstw               │
│ - Rozdziela "Jan Kowalski" → name+surname│
└──────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────┐
│ Etap 4: Wzbogacenie Morfologiczne        │
│ - Dodaje: przypadek, rodzaj, liczbę      │
│ - Źródło: SpaCy/Stanza                   │
└──────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────┐
│ Etap 5: Generowanie Wyników              │
│ - anonymized: [email], [phone]           │
│ - intermediate: [email|case=nom|...]     │
└──────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────┐
│ Etap 6: Syntetyzacja (opcjonalnie)       │
│ - Zamiana tagów na dane syntetyczne      │
│ - Odmiana przez przypadki (Morfeusz2)    │
└──────────────────────────────────────────┘
```

## 6. Inicjalizacja Pipeline'u (Lazy Loading)

Przed pierwszym przetworzeniem tekstu następuje **lazy initialization** komponentów:

```python
def initialize(self):
    if self._initialized:
        return

    # Warstwa ML (NER)
    if self.ml_layer:
        self.ml_layer.initialize()  # Ładowanie SpaCy: pl_core_news_lg

    # Analiza morfologiczna
    self.enrichment_pipeline.analyzer.initialize()  # Ładowanie analizatora
```

**Komponenty ładowane podczas inicjalizacji:**

1. **SpaCy NER Model** (`pl_core_news_lg` lub `pl_core_news_sm` jako fallback)
2. **Analizator Morfologiczny** (backend: SpaCy lub Stanza)
3. **Kompilacja wzorców Regex** (pre-compiled patterns dla wydajności)

### 6.1. Kompilacja Wzorców Regex

Wszystkie wyrażenia regularne są prekompilowane przy inicjalizacji `RegexLayer`:

```python
def _compile_patterns(self):
    # Adresy
    self.address_regex = re.compile(
        r"\b(?i:ul\.|ulica|al\.|aleja|...)\s+..."
    )

    # PESEL
    self.pesel_regex = re.compile(r"\b\d{11}\b")

    # Email, telefon, konta bankowe
    self.simple_patterns = [
        (EntityType.EMAIL, re.compile(r"\b[A-Za-z0-9._%+-]+@...")),
        (EntityType.PHONE, re.compile(r"(?<!\w)(?:(?:\+|00)\d{1,3}...)")),
        ...
    ]
```

Kompilacja tylko raz (nie przy każdym tekście) = znaczący wzrost wydajności.

## 7. Batch Processing

System grupuje teksty i przetwarza je sekwencyjnie:

```python
texts = [...]  # Lista wczytanych tekstów
results, avg_layer_times = self.anonymizer.anonymize_batch(texts)
```

**Uwaga:** Każdy tekst jest przetwarzany indywidualnie - nie ma batch processing na poziomie modelu SpaCy (`nlp.pipe()`). Jest to potencjalna optymalizacja na przyszłość.

**Zalety obecnego podejścia:**

- Amortyzacja kosztów inicjalizacji modeli
- Zbieranie statystyk per-layer timing
- Prostsza obsługa błędów (izolacja per-tekst)

## 8. Podsumowanie

| Aspekt                      | Status                            |
| --------------------------- | --------------------------------- |
| Klasyczny preprocessing NLP | ❌ Brak                           |
| Chunking długich tekstów    | ❌ Brak                           |
| Tokenizacja                 | ✅ Wewnętrznie przez SpaCy        |
| Normalizacja tekstu         | ❌ Brak                           |
| Batch processing modelu     | ❌ Sekwencyjne (tekst po tekście) |
| Prekompilacja regex         | ✅ Przy inicjalizacji             |
| Lazy loading modeli         | ✅ Przy pierwszym użyciu          |

**Kluczowy wniosek:** System świadomie unika preprocessingu, aby zachować integralność tekstu potrzebną do precyzyjnego mapowania pozycji encji i poprawnej analizy morfologicznej.
