# Preprocessing - Zespół Overfitters

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

## 2. Preprocessing - Wczytywanie i Parsowanie

### 2.1. Format JSONL

Każda linia pliku jest parsowana jako osobny obiekt JSON:

```python
with open(input_path, 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():  # Pomija puste linie
            data = json.loads(line.strip())
            texts.append(data.get('text', data.get('content', '')))
```

**Kroki preprocessingu dla JSONL:**

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

**Kroki preprocessingu dla TXT:**

1. Wczytanie pliku (encoding: UTF-8)
2. Każda linia = 1 przykład
3. Usunięcie znaku nowej linii z końca (`rstrip('\n')`)
4. **Zachowanie spacji i białych znaków wewnątrz linii** (important dla struktury tekstu)

### 2.3. Preprocessing Wejściowy - Co NIE Jest Robione

System **celowo NIE wykonuje** typowych operacji preprocessingu NLP:

- ❌ Lowercase (konwersja na małe litery)
- ❌ Usuwanie znaków specjalnych
- ❌ Usuwanie stopwords
- ❌ Stemming/Lemmatization na wejściu
- ❌ Normalizacja Unicode
- ❌ Czyszczenie HTML/Markdown

Tekst musi pozostać nienaruszony, aby:

1. Regex mógł wykryć wzorce z wielkimi literami (np. inicjały, numery dokumentów ABC123456)
2. Model NER (SpaCy) sam wykonuje tokenizację i preprocessing
3. Zachować oryginalną strukturę dla mapowania pozycji (start/end char)
4. Zachować formatowanie dla warstwy morfologicznej (odmiana przez przypadki wymaga oryginalnych form)

## 3. Inicjalizacja Pipeline'u (Lazy Loading)

Przed pierwszym przetworzeniem tekstu następuje **lazy initialization** komponentów:

### 3.1. Inicjalizacja Modeli

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

### 3.2. Kompilacja Wzorców Regex

Wszystkie wyrażenia regularne są prekompilowane przy inicjalizacji `RegexLayer`:

```python
def _compile_patterns(self):
    # PESEL
    self.pesel_regex = re.compile(r"\b\d{11}\b")

    # Email, telefon, konta bankowe
    self.simple_patterns = [
        (EntityType.EMAIL, re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
        (EntityType.PHONE, re.compile(r"(?<!\w)(?:(?:\+|00)\d{1,3}[ .-]?...)")),
        ...
    ]
```

Kompilacja tylko raz (nie przy każdym tekście) = znaczący wzrost wydajności.

## 4. Batch Processing

System grupuje teksty w batche dla efektywności:

```python
texts = [...]  # Lista wczytanych tekstów
results, avg_layer_times = self.anonymizer.anonymize_batch(texts)
```

**Zalety batch processing:**

- Amortyzacja kosztów inicjalizacji modeli
- Możliwość optymalizacji (np. vectorized operations w przyszłości)
- Zbieranie statystyk per-layer timing
