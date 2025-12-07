#!/usr/bin/env python3
"""
Frontend Flask API dla Dane bez Twarzy - System Anonimizacji
"""

import sys
from pathlib import Path

# Dodaj katalog główny projektu do ścieżki
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify
from anonymizer.anonymizer import Anonymizer, AnonymizationResult
import logging

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Globalny anonimizator (lazy initialization)
_anonymizer = None

def get_anonymizer():
    """Lazy initialization anonimizatora."""
    global _anonymizer
    if _anonymizer is None:
        logger.info("Inicjalizacja anonimizatora...")
        _anonymizer = Anonymizer(
            use_ml=True,
            generate_synthetic=True,
            include_intermediate=True
        )
    return _anonymizer


@app.route('/')
def index():
    """Strona główna."""
    return render_template('index.html')


@app.route('/api/anonymize', methods=['POST'])
def anonymize():
    """
    Endpoint do anonimizacji tekstu.
    
    Request JSON:
        {
            "text": "Tekst do anonimizacji",
            "generate_synthetic": true  // opcjonalne
        }
    
    Response JSON:
        {
            "original": "...",
            "anonymized": "...",
            "intermediate": "...",
            "synthetic": "...",
            "entities": [...],
            "processing_time_ms": 123.45
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({'error': 'Brak tekstu do anonimizacji'}), 400
        
        text = data['text']
        generate_synthetic = data.get('generate_synthetic', True)
        
        if not text.strip():
            return jsonify({'error': 'Tekst nie może być pusty'}), 400
        
        anonymizer = get_anonymizer()
        result = anonymizer.anonymize(text, generate_synthetic=generate_synthetic)
        
        return jsonify(result.to_dict())
    
    except Exception as e:
        logger.exception("Błąd podczas anonimizacji")
        return jsonify({'error': str(e)}), 500


@app.route('/api/anonymize/batch', methods=['POST'])
def anonymize_batch():
    """
    Endpoint do anonimizacji wielu tekstów.
    
    Request JSON:
        {
            "texts": ["Tekst 1", "Tekst 2", ...],
            "generate_synthetic": true  // opcjonalne
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'texts' not in data:
            return jsonify({'error': 'Brak tekstów do anonimizacji'}), 400
        
        texts = data['texts']
        generate_synthetic = data.get('generate_synthetic', True)
        
        if not texts:
            return jsonify({'error': 'Lista tekstów nie może być pusta'}), 400
        
        anonymizer = get_anonymizer()
        results, avg_times = anonymizer.anonymize_batch(
            texts, 
            generate_synthetic=generate_synthetic,
            show_progress=False
        )
        
        return jsonify({
            'results': [r.to_dict() for r in results],
            'avg_layer_times': avg_times
        })
    
    except Exception as e:
        logger.exception("Błąd podczas anonimizacji batch")
        return jsonify({'error': str(e)}), 500


@app.route('/api/entity-types', methods=['GET'])
def get_entity_types():
    """Zwraca listę dostępnych typów encji."""
    from anonymizer.regex_layer import EntityType
    
    entity_types = [
        {'value': et.value, 'name': et.name}
        for et in EntityType
    ]
    
    # Grupowanie po kategorii
    categories = {
        'Dane osobowe': ['name', 'surname', 'age', 'date-of-birth', 'sex'],
        'Kontakt i lokalizacja': ['city', 'address', 'email', 'phone'],
        'Dokumenty': ['pesel', 'document-number', 'bank-account', 'credit-card-number'],
        'Dane wrażliwe': ['religion', 'political-view', 'ethnicity', 'sexual-orientation', 'health'],
        'Praca i edukacja': ['company', 'school-name', 'job-title'],
        'Inne': ['username', 'secret', 'date', 'relative']
    }
    
    return jsonify({
        'entity_types': entity_types,
        'categories': categories
    })


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  Dane bez Twarzy - Frontend")
    print("  http://localhost:5001")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5001)

