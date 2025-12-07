# morfeusz_inflector.py

import morfeusz2 as m2
from typing import Dict, List

CASE_MAP: Dict[str, str] = {
    'mianownik': 'nom',
    'dopełniacz': 'gen',
    'celownik': 'dat',
    'biernik': 'acc',
    'narzędnik': 'inst',
    'miejscownik': 'loc',
    'wołacz': 'voc'
}

class MorfeuszInflector:
    def __init__(self):
        try:
            self.morf = m2.Morfeusz()
        except Exception:
            print("OSTRZEŻENIE: Morfeusz nie załadowany. Funkcja będzie zwracać tylko lematy.")
            self.morf = None

    def inflect_word(self, lemma: str, target_case: str, is_female: bool) -> str:
        if not self.morf or not lemma:
            return lemma

        target_tag = CASE_MAP.get(target_case, "nom")
        gender_codes = ['f'] if is_female else ['m1', 'm2', 'm3']

        print(f"\n--- DEBUG FLEXJA ---")
        print(f"Lemat: {lemma}, Płeć: {'kobieta' if is_female else 'mężczyzna'}, Szukany przypadek: {target_case} ({target_tag})")

        try:
            results = self.morf.generate(lemma)
        except Exception as e:
            print(f"DEBUG: Błąd Morfeusza: {e}. Zwracam lemat.")
            return lemma

        found_form = None
        for result in results:
            # result ma 5 elementów: (form, lemma, tag, pospolitosc, kwalifikatory)
            if len(result) < 3:
                continue

            form = result[0]
            tag = result[2]

            if not tag:
                continue

            # tylko rzeczowniki, imiona i nazwiska
            is_valid_type = any(prefix in tag for prefix in ['subst', 'imie', 'nazwisko', 'prop'])

            # sprawdzenie czy tag zawiera odpowiedni przypadek i płeć
            def tag_matches(tag_str: str) -> bool:
                # Sprawdzenie przypadku
                case_ok = target_tag in tag_str
                # Sprawdzenie płci
                gender_ok = any(g in tag_str for g in gender_codes)
                return case_ok and gender_ok

            is_correct_inflection = tag_matches(tag)

            if is_valid_type:
                print(f"  > FORMA: {form:<12} | POPRAWNY TYP: {is_valid_type} | POPRAWNA FLEKSJA: {is_correct_inflection} | TAG: {tag}")

            if is_valid_type and is_correct_inflection:
                found_form = form
                break

        if found_form:
            print(f"DEBUG: ZNALEZIONO FLEXJĘ: {found_form}")
            return found_form
        else:
            print("DEBUG: FLEXJA NIEZNAJDZIONA. Zwracam lemat.")
            return lemma
