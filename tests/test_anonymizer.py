"""
Testy jednostkowe dla systemu anonimizacji.
Uruchomienie: pytest tests/ -v
"""

import pytest
import sys
from pathlib import Path

# Dodaj ścieżkę do modułu
sys.path.insert(0, str(Path(__file__).parent.parent))

from anonymizer import (
    Anonymizer,
    RegexLayer,
    EntityType,
    anonymize_text,
)


class TestRegexLayer:
    """Testy warstwy regex."""
    
    @pytest.fixture
    def layer(self):
        return RegexLayer()
    
    def test_pesel_detection(self, layer):
        """Test wykrywania PESEL z prawidłową sumą kontrolną."""
        text = "PESEL: 55030101230"
        entities = layer.detect(text)
        
        pesel_entities = [e for e in entities if e.entity_type == EntityType.PESEL]
        assert len(pesel_entities) == 1
        assert pesel_entities[0].text == "55030101230"
    
    def test_pesel_validation(self, layer):
        """Test walidacji sumy kontrolnej PESEL."""
        assert layer._validate_pesel("55030101230") == True
        assert layer._validate_pesel("12345678901") == False
        assert layer._validate_pesel("abc") == False
    
    def test_email_detection(self, layer):
        """Test wykrywania email."""
        text = "Kontakt: jan.kowalski@gmail.com"
        entities = layer.detect(text)
        
        email_entities = [e for e in entities if e.entity_type == EntityType.EMAIL]
        assert len(email_entities) == 1
        assert "jan.kowalski@gmail.com" in email_entities[0].text
    
    def test_phone_detection(self, layer):
        """Test wykrywania telefonu."""
        test_cases = [
            "+48 123 456 789",
            "+48123456789",
            "123-456-789",
        ]
        
        for phone in test_cases:
            entities = layer.detect(f"Tel: {phone}")
            phone_entities = [e for e in entities if e.entity_type == EntityType.PHONE]
            assert len(phone_entities) >= 1, f"Nie wykryto: {phone}"
    
    def test_address_detection(self, layer):
        """Test wykrywania adresu."""
        text = "Mieszkam przy ul. Długa 15/3"
        entities = layer.detect(text)
        
        addr_entities = [e for e in entities if e.entity_type == EntityType.ADDRESS]
        assert len(addr_entities) >= 1
    
    def test_date_detection(self, layer):
        """Test wykrywania dat."""
        test_cases = [
            "15.03.1990",
            "15-03-1990",
            "1990/03/15",
            "15 marca 1990",
        ]
        
        for date in test_cases:
            entities = layer.detect(f"Data: {date}")
            date_entities = [e for e in entities 
                          if e.entity_type in (EntityType.DATE, EntityType.DATE_OF_BIRTH)]
            assert len(date_entities) >= 1, f"Nie wykryto daty: {date}"
    
    def test_age_detection(self, layer):
        """Test wykrywania wieku."""
        test_cases = [
            "Mam 25 lat",
            "Wiek: 30",
            "55-letnia kobieta",
        ]
        
        for text in test_cases:
            entities = layer.detect(text)
            age_entities = [e for e in entities if e.entity_type == EntityType.AGE]
            assert len(age_entities) >= 1, f"Nie wykryto wieku: {text}"


class TestAnonymizer:
    """Testy głównego anonimizatora."""
    
    @pytest.fixture
    def anonymizer(self):
        return Anonymizer(
            use_ml=True,
            generate_synthetic=False,
            include_intermediate=False
        )
    
    def test_basic_anonymization(self, anonymizer):
        """Test podstawowej anonimizacji."""
        text = "Email: jan@gmail.com, PESEL: 55030101230"
        result = anonymizer.anonymize(text)
        
        assert "{email}" in result.anonymized
        assert "{pesel}" in result.anonymized
        assert "jan@gmail.com" not in result.anonymized
    
    def test_anonymization_result_structure(self, anonymizer):
        """Test struktury wyniku."""
        result = anonymizer.anonymize("Test: jan@email.pl")
        
        assert hasattr(result, 'original')
        assert hasattr(result, 'anonymized')
        assert hasattr(result, 'entities')
        assert hasattr(result, 'processing_time_ms')
    
    def test_entity_detection_count(self, anonymizer):
        """Test liczby wykrytych encji."""
        text = "Jan, email: jan@wp.pl, tel: +48 111 222 333, PESEL: 55030101230"
        result = anonymizer.anonymize(text)
        
        # Powinno wykryć minimum 3 encje (email, phone, pesel)
        assert len(result.entities) >= 3


class TestCityAddressDistinction:
    """Testy rozróżniania city vs address."""
    
    @pytest.fixture
    def anonymizer(self):
        return Anonymizer(use_ml=True, generate_synthetic=False)
    
    def test_city_context(self, anonymizer):
        """Test - miasto w kontekście podróży."""
        text = "Jadę do Krakowa na wycieczkę."
        result = anonymizer.anonymize(text)
        
        city_entities = [e for e in result.entities if e['type'] == 'city']
        assert len(city_entities) >= 1, "Kraków powinien być wykryty jako city"
    
    def test_address_context(self, anonymizer):
        """Test - miasto w kontekście zamieszkania."""
        text = "Mieszkam w Krakowie przy ul. Długiej."
        result = anonymizer.anonymize(text)
        
        addr_entities = [e for e in result.entities if e['type'] == 'address']
        assert len(addr_entities) >= 1, "Kraków powinien być wykryty jako address"


class TestSyntheticGeneration:
    """Testy generacji danych syntetycznych."""
    
    @pytest.fixture
    def anonymizer(self):
        return Anonymizer(
            use_ml=True,
            generate_synthetic=True,
            synthetic_seed=42  # Dla powtarzalności
        )
    
    def test_synthetic_generation(self, anonymizer):
        """Test generacji danych syntetycznych."""
        text = "Email: jan@wp.pl, PESEL: 55030101230"
        result = anonymizer.anonymize(text)
        
        assert result.synthetic is not None
        assert "{email}" not in result.synthetic
        assert "{pesel}" not in result.synthetic
    
    def test_synthetic_reproducibility(self, anonymizer):
        """Test powtarzalności z tym samym seedem."""
        text = "PESEL: 55030101230"
        
        # Dwa wywołania z tym samym seedem powinny dać ten sam wynik
        # (nowy anonimizator z tym samym seedem)
        anon1 = Anonymizer(use_ml=True, generate_synthetic=True, synthetic_seed=42)
        anon2 = Anonymizer(use_ml=True, generate_synthetic=True, synthetic_seed=42)
        
        result1 = anon1.anonymize(text)
        result2 = anon2.anonymize(text)
        
        assert result1.synthetic == result2.synthetic


class TestSimpleAPI:
    """Testy uproszczonego API."""
    
    def test_anonymize_text_function(self):
        """Test funkcji anonymize_text."""
        result = anonymize_text(
            "Email: jan@gmail.com",
            generate_synthetic=False
        )
        
        assert isinstance(result, dict)
        assert 'anonymized' in result
        assert '{email}' in result['anonymized']


# Uruchomienie testów
if __name__ == "__main__":
    pytest.main([__file__, "-v"])