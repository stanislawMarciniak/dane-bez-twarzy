# Frontend - Dane bez Twarzy

Prosty interfejs webowy do systemu anonimizacji tekstu.

## Instalacja

```bash
# Z głównego katalogu projektu
cd frontend
pip install -r requirements.txt
```

## Uruchomienie

```bash
# Z głównego katalogu projektu
python frontend/app.py
```

Lub:

```bash
# Z katalogu frontend
cd frontend
python app.py
```

Aplikacja będzie dostępna pod adresem: **http://localhost:5001**

## Funkcjonalności

- **Trzy kolumny**: Tekst oryginalny, Zanonimizowany, Syntetyczny
- **Filtry encji**: Włączaj/wyłączaj widoczność różnych typów danych
- **Nawigacja po tokenach**: Użyj strzałek ← → do przeskakiwania między encjami
- **Podświetlanie**: Kliknij na token aby go podświetlić
- **Skróty klawiszowe**:
  - `Ctrl+Enter` - Anonimizuj tekst
  - `←` `→` - Nawiguj po tokenach
  - `Esc` - Usuń podświetlenie

## API Endpoints

### POST `/api/anonymize`

Anonimizuje pojedynczy tekst.

**Request:**
```json
{
    "text": "Jan Kowalski mieszka w Warszawie",
    "generate_synthetic": true
}
```

**Response:**
```json
{
    "original": "...",
    "anonymized": "...",
    "intermediate": "...",
    "synthetic": "...",
    "entities": [...],
    "processing_time_ms": 123.45
}
```

### POST `/api/anonymize/batch`

Anonimizuje wiele tekstów naraz.

### GET `/api/entity-types`

Zwraca listę dostępnych typów encji.

