import re

class RegexPreprocessor:
    def __init__(self):
        pass 

    def _validate_pesel(self, match):
        """
        Walidacja matematyczna numeru PESEL.
        """
        pesel = match.group()
        if len(pesel) != 11:
            return pesel
        
        weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
        
        try:
            checksum = sum(int(pesel[i]) * weights[i] for i in range(10))
            control_digit = (10 - (checksum % 10)) % 10
            
            if control_digit == int(pesel[10]):
                return "{pesel}"
            else:
                return pesel 
        except ValueError:
            return pesel

    def process(self, text):
        processed_text = text

        # # =================================================================
        # # KROK 1: Adresy 
        # # =================================================================
        # # Zmiany:
        # # 1. Usunięto kropkę z klasy znaków [\wą-ż-], aby nie zjadać kropki kończącej zdanie.
        # # 2. Dodano obsługę skrótów [a-zA-Z]{1,3}\. (np. mjr., św., al.).
        # # 3. Dodano obsługę cyfr w nazwie ulicy TYLKO jeśli są one częścią nazwy (np. 3 Maja), 
        # #    sprawdzając lookaheadem czy po cyfrze następuje Wielka Litera (np. 3 Maja -> OK, 5 i ma -> NIE).
        # address_regex = re.compile(
        #     r"\b(?i:ul\.|ulica|al\.|aleja|aleje|pl\.|plac|os\.|osiedle|skwer|rondo)\s+" # Prefiks
        #     r"(" # Grupa 1: Nazwa ulicy
        #         r"(?:"
        #             # ZABEZPIECZENIE 1: Nie dopasowuj, jeśli tuż za spacją jest kolejny prefiks (np. "na os.")
        #             r"(?!\s+(?i:ul\.|ulica|al\.|aleja|pl\.|plac|os\.|osiedle|skwer|rondo))"
        #             r"(?:"
        #                 r"[a-zA-ZĄĆĘŁŃÓŚŹŻąćęłńóśźż0-9][\wą-ż\.-]*" # Pierwsze słowo nazwy (może być małą literą)
        #                 r"|"
        #                 r"(?i:św\.|gen\.|ks\.|bp\.|abp\.|prof\.|dr\.?|im\.|al\.|pl\.)" # Tytuły
        #                 r"|"
        #                 r"[A-Z]\.?" # Inicjały
        #             r")"
        #             r"(?:[\s-]" # Separator kolejnych członów
        #                 # ZABEZPIECZENIE 2: Powtórzenie lookahead przy każdym kolejnym członie
        #                 r"(?!\s*(?i:ul\.|ulica|al\.|aleja|pl\.|plac|os\.|osiedle|skwer|rondo))"
        #                 r"(?:"
        #                    r"[A-ZĄĆĘŁŃÓŚŹŻ0-9][\wą-ż\.-]*" # Kolejne słowa muszą być z Dużej (lub cyfry)
        #                    r"|"
        #                    r"(?i:św\.|gen\.|ks\.|bp\.|abp\.|prof\.|dr\.?|im\.)" # Tytuły
        #                    r"|"
        #                    r"[A-Z]\.?" # Inicjały
        #                    r"|"
        #                    r"(?i:i|w|z|nad|pod|przy|ku)" # Dozwolone łączniki (małą literą)
        #                 r")"
        #             r")*" 
        #         r")"
        #     r")"
        #     r"\s+" # Spacja przed numerem
        #     # Grupa 2: Numer. Dodano \b na końcu, żeby nie łapać początku telefonu (np. 600-500)
        #     r"(\d+(?:[a-zA-Z])?(?:[/-]\d+(?:[a-zA-Z])?)?(?:\s*(?i:m\.|lok\.|m|lok)\s*\d+)?)\b", 
        #     re.IGNORECASE
        # )

        # # Uruchomienie regexa adresowego (Najpierw, bo jest najbardziej zachłanny)
        # processed_text = address_regex.sub("{address}", processed_text)

        # =================================================================
        # KROK 2: PESEL z Walidacją
        # =================================================================
        processed_text = re.sub(r"\b\d{11}\b", self._validate_pesel, processed_text)

        # =================================================================
        # KROK 3: Wiek
        # =================================================================
        # Wariant A: "25 lat" -> "{age} lat"
        processed_text = re.sub(
            r"\b(\d{1,3})(\s?(?:lat|lata|l\.|r\.ż\.))", 
            r"{age}\2", 
            processed_text, 
            flags=re.IGNORECASE
        )
        
        # Wariant B: "Wiek: 25" -> "Wiek: {age}"
        processed_text = re.sub(
            r"\b(wiek:?\s?)(\d{1,3})", 
            r"\1{age}", 
            processed_text, 
            flags=re.IGNORECASE
        )

        # Wariant C: "18+"
        processed_text = re.sub(
            r"\b(\d{1,3})(\+)", 
            r"{age}\2", 
            processed_text
        )

        # =================================================================
        # KROK 4: Reszta prostych regexów (POPRAWIONE)
        # =================================================================
        simple_patterns = [
            ("{email}", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
            
            # POPRAWKA 1: Username
            # Wymusza, by ostatni znak NIE był kropką (żeby nie zjadać kropki kończącej zdanie)
            ("{username}", re.compile(r"(?<![\w])@[\w](?:[\w._-]*[\w_-])?")), 
            
            ("{secret}", re.compile(r"Bearer\s+[a-zA-Z0-9\-\._~+/]+=*")),
            ("{bank-account}", re.compile(r"\b(?i:PL)[ ]?\d{2}(?:[ ]?\d{4}){6}\b")),
            ("{credit-card-number}", re.compile(r"(?<!\d)(?<!\d[ -])(?:(?:\d{4} \d{4} \d{4} \d{4})|(?:\d{4}-\d{4}-\d{4}-\d{4}))(?!\d)")),
            # Fix: prevent 16-digit numbers from matching as credit cards if they are just random numbers (unless formatted)
            
            # POPRAWKA 2: Telefon
            # Zmieniona logika prefiksu: Spacja na początku jest dozwolona TYLKO jeśli jest przed nią +48.
            # Jeśli nie ma +48, regex zaczyna łapać od cyfry, nie ruszając spacji przed nią.
            #("{phone}", re.compile(r"(?<!\w)(?:(?:\+|00)48[ -]?)?\d{3}[ -]?\d{3}[ -]?\d{3}(?!\w)")),
            ("{phone}", re.compile(r"(?<!\w)(?:(?:\+|00)48[ .-]?|\(\+?48\)[ .-]?)?\d{3}[ .-]?\d{3}[ .-]?\d{3}(?!\w)")),
            ("{phone}", re.compile(r"(?<!\w)\(?\d{2}\)?[ .-]?\d{3}[ .-]?\d{2}[ .-]?\d{2}(?!\w)")), # Stacjonarne (22) 123 45 67


            
            ("{document-number}", re.compile(r"\b[A-Z]{3}\s?\d{6}\b", re.IGNORECASE)), # Dowód
            ("{document-number}", re.compile(r"\b[A-Z]{2}\s?\d{7}\b")), # Paszport
            ("{document-number}", re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")), # VIN
            ("{date}", re.compile(r"\b\d{4}[-./]\d{1,2}[-./]\d{1,2}\b|\b\d{1,2}[-./]\d{1,2}[-./]\d{4}\b")),
        ]

        for label, pattern in simple_patterns:
            processed_text = pattern.sub(label, processed_text)

        return processed_text

# ==========================================
# TESTY
# ==========================================
# =============================================================================
# MODUŁ TESTOWY (Zastępuje stary main)
# =============================================================================
if __name__ == "__main__":
    preprocessor = RegexPreprocessor()

    # UWAGA: Tutaj testujemy TYLKO to, co potrafi RegEx.
    # Imiona {name}, nazwiska {surname}, miasta {city} (bez adresu) 
    # są zadaniem dla modelu ML (Step 2), więc tutaj ich nie podmieniamy.
    
    test_cases = [
        # # --- KATEGORIA: ADRESY {address} ---
        # {
        #     "desc": "Adres: Ulica prosta",
        #     "input": "Mieszkam przy ul. Polnej 5.",
        #     "expected": "Mieszkam przy {address}."
        # },
        # {
        #     "desc": "Adres: Aleja wieloczłonowa z lokalem",
        #     "input": "Biuro: Al. Jana Pawła II 12/4.",
        #     "expected": "Biuro: {address}."
        # },
        # {
        #     "desc": "Adres: Osiedle ze skrótami",
        #     "input": "Znajdź mnie: os. Słoneczne 7 m 3.",
        #     "expected": "Znajdź mnie: {address}."
        # },
        # {
        #     "desc": "Adres: Wielkość liter (case insensitive)",
        #     "input": "Adres to UL. Długa 10.",
        #     "expected": "Adres to {address}."
        # },
        
        # --- KATEGORIA: PESEL {pesel} ---
        {
            "desc": "PESEL: Poprawny matematycznie",
            "input": "Mój PESEL to 44051401359.", 
            "expected": "Mój PESEL to {pesel}."
        },
        {
            "desc": "PESEL: Błędna suma kontrolna (powinien zignorować)",
            "input": "To fałszywka: 44051401358.",
            "expected": "To fałszywka: 44051401358."
        },

        # --- KATEGORIA: TELEFON {phone} ---
        {
            "desc": "Telefon: Z prefiksem +48 i spacjami",
            "input": "Zadzwoń: +48 600 100 200.",
            "expected": "Zadzwoń: {phone}."
        },
        {
            "desc": "Telefon: Format ciągły",
            "input": "Tel: 600100200.",
            "expected": "Tel: {phone}."
        },
        {
            "desc": "Telefon: Format z myślnikami",
            "input": "Kom: 600-100-200.",
            "expected": "Kom: {phone}."
        },

        # --- KATEGORIA: E-MAIL i LOGINY ---
        {
            "desc": "Email: Standardowy",
            "input": "Pisz na jan.kowalski@firma.com.pl.",
            "expected": "Pisz na {email}."
        },
        {
            "desc": "Username: Twitter/Instagram style",
            "input": "Mój nick to @janek_99.",
            "expected": "Mój nick to {username}."
        },

        # --- KATEGORIA: FINANSE ---
        {
            "desc": "Bank: IBAN ze spacjami",
            "input": "PL 11 2222 3333 4444 5555 6666 7777",
            "expected": "{bank-account}"
        },
        {
            "desc": "Karta: 16 cyfr",
            "input": "Karta: 1234 5678 1234 5678.",
            "expected": "Karta: {credit-card-number}."
        },

        # --- KATEGORIA: WIEK {age} ---
        {
            "desc": "Wiek: Słowo 'lat'",
            "input": "Mam 25 lat.",
            "expected": "Mam {age} lat."
        },
        {
            "desc": "Wiek: Słowo 'lata'",
            "input": "Dziecko ma 4 lata.",
            "expected": "Dziecko ma {age} lata."
        },
        {
            "desc": "Wiek: Format 'Wiek: X'",
            "input": "Pacjent, Wiek: 50.",
            "expected": "Pacjent, Wiek: {age}."
        },
        {
            "desc": "Wiek NEGATYWNY (nie powinien ruszyć)",
            "input": "Mam 5 kotów i 2 domy.",
            "expected": "Mam 5 kotów i 2 domy."
        },

        # --- KATEGORIA: DOKUMENTY ---
        {
            "desc": "Dowód osobisty",
            "input": "DO: ABC 123456.",
            "expected": "DO: {document-number}."
        },
        {
            "desc": "Paszport",
            "input": "Paszport AB 1234567.",
            "expected": "Paszport {document-number}."
        },

        # --- KATEGORIA: DATY ---
        {
            "desc": "Data: Format DD-MM-YYYY",
            "input": "Urodzony 12-05-1990.",
            "expected": "Urodzony {date}."
        },
        {
            "desc": "Data: Format YYYY.MM.DD",
            "input": "Data: 2023.09.01.",
            "expected": "Data: {date}."
        },

        # # --- KATEGORIA: MIX / ZŁOŻONE ---
        # {
        #     "desc": "MIX: Wiele danych w jednym zdaniu",
        #     "input": "Jan (mail: a@b.pl) mieszka na ul. Polnej 5 i ma PESEL 44051401359.",
        #     "expected": "Jan (mail: {email}) mieszka na {address} i ma PESEL {pesel}."
        # },
        # # ==========================================
        # # 1. ADRESY {address} - Różne formaty i skróty
        # # ==========================================
        # {
        #     "desc": "Adres: Ulica prosta",
        #     "input": "Mieszkam przy ul. Polnej 5.",
        #     "expected": "Mieszkam przy {address}."
        # },
        # {
        #     "desc": "Adres: Aleja wieloczłonowa z lokalem",
        #     "input": "Biuro: Al. Jana Pawła II 12/4.",
        #     "expected": "Biuro: {address}."
        # },
        # {
        #     "desc": "Adres: Osiedle ze skrótami",
        #     "input": "Znajdź mnie: os. Słoneczne 7 m 3.",
        #     "expected": "Znajdź mnie: {address}."
        # },
        # {
        #     "desc": "Adres: Plac z myślnikiem w nazwie",
        #     "input": "Spotkajmy się: pl. Grunwaldzki 10-12.",
        #     "expected": "Spotkajmy się: {address}."
        # },
        # {
        #     "desc": "Adres: Numer z literą",
        #     "input": "Adres: ul. Krótka 7a.",
        #     "expected": "Adres: {address}."
        # },
        # {
        #     "desc": "Adres: Skrót 'lok.' zamiast 'm.'",
        #     "input": "Firma: Al. Jerozolimskie 100 lok. 55.",
        #     "expected": "Firma: {address}."
        # },
        # {
        #     "desc": "Adres: Mała litera nazwy (błąd użytkownika/gramatyka)",
        #     "input": "Idę na ul. prostą.",
        #     "expected": "Idę na {address}."
        # },

        # ==========================================
        # 2. TELEFONY {phone} - Prefiksy i separatory
        # ==========================================
        {
            "desc": "Telefon: Z prefiksem +48 i spacjami",
            "input": "Zadzwoń: +48 600 100 200.",
            "expected": "Zadzwoń: {phone}."
        },
        {
            "desc": "Telefon: Prefiks 0048",
            "input": "Tel: 0048 500 123 456.",
            "expected": "Tel: {phone}."
        },
        {
            "desc": "Telefon: Prefiks w nawiasie (48)",
            "input": "Fax: (+48) 123 456 789.",
            "expected": "Fax: {phone}."
        },
        {
            "desc": "Telefon: Ciągły bez spacji",
            "input": "Awaria: 600100200.",
            "expected": "Awaria: {phone}."
        },
        {
            "desc": "Telefon: Myślniki",
            "input": "Kontakt: 501-200-300.",
            "expected": "Kontakt: {phone}."
        },
        {
            "desc": "Telefon NEGATYWNY: Zbyt krótki (przypadkowe cyfry)",
            "input": "To jest 123 456.",
            "expected": "To jest 123 456."
        },

        # ==========================================
        # 3. PESEL {pesel} - Walidacja sumy kontrolnej
        # ==========================================
        {
            "desc": "PESEL: Poprawny (matematycznie)",
            "input": "Mój PESEL to 44051401359.", 
            "expected": "Mój PESEL to {pesel}."
        },
        {
            "desc": "PESEL: Inny NIE poprawny (kobieta ur. 2002)",
            "input": "PESEL dziecka: 02211300009.", # 02211300009 nie jest poprawny matematycznie
            "expected": "PESEL dziecka: 02211300009."
        },
        {
            "desc": "PESEL NEGATYWNY: Błędna suma kontrolna",
            "input": "To fałszywka: 44051401358.",
            "expected": "To fałszywka: 44051401358."
        },
        {
            "desc": "PESEL NEGATYWNY: Za krótki",
            "input": "Wpisz 9001011234.",
            "expected": "Wpisz 9001011234."
        },

        # ==========================================
        # 4. FINANSE - IBAN i Karty
        # ==========================================
        {
            "desc": "Bank: IBAN ze spacjami (standard)",
            "input": "PL 11 2222 3333 4444 5555 6666 7777",
            "expected": "{bank-account}"
        },
        {
            "desc": "Bank: IBAN ciągły (bez spacji)",
            "input": "Konto PL11222233334444555566667777 do przelewu.",
            "expected": "Konto {bank-account} do przelewu."
        },
        {
            "desc": "Karta: Grupy po 4 cyfry",
            "input": "Visa: 4000 1234 5678 9010.",
            "expected": "Visa: {credit-card-number}."
        },
        {
            "desc": "Karta: Z myślnikami",
            "input": "MC: 5100-1234-5678-9010.",
            "expected": "MC: {credit-card-number}."
        },

        # ==========================================
        # 5. DOKUMENTY {document-number}
        # ==========================================
        {
            "desc": "Dokument: Dowód (3 litery + 6 cyfr)",
            "input": "Nr DO: XYZ 123456.",
            "expected": "Nr DO: {document-number}."
        },
        {
            "desc": "Dokument: Dowód bez spacji",
            "input": "Seria ABC123456.",
            "expected": "Seria {document-number}."
        },
        {
            "desc": "Dokument: Paszport (2 litery + 7 cyfr)",
            "input": "Paszport: AB 1234567.",
            "expected": "Paszport: {document-number}."
        },
        {
            "desc": "Dokument: VIN (17 znaków)",
            "input": "VIN pojazdu: 1HGCM82633A004352.",
            "expected": "VIN pojazdu: {document-number}."
        },

        # ==========================================
        # 6. WIEK {age} - Kontekst i skróty
        # ==========================================
        {
            "desc": "Wiek: Standard 'lat'",
            "input": "Oskarżony ma 25 lat.",
            "expected": "Oskarżony ma {age} lat."
        },
        {
            "desc": "Wiek: Skrót 'l.'",
            "input": "Pacjent 77 l., przyjęty wczoraj.",
            "expected": "Pacjent {age} l., przyjęty wczoraj."
        },
        {
            "desc": "Wiek: Skrót 'r.ż.' (rok życia)",
            "input": "Dziecko w 2 r.ż. wymaga opieki.",
            "expected": "Dziecko w {age} r.ż. wymaga opieki."
        },
        {
            "desc": "Wiek: Prefiks 'Wiek:'",
            "input": "Ankieta. Wiek: 40.",
            "expected": "Ankieta. Wiek: {age}."
        },
        {
            "desc": "Wiek NEGATYWNY: Liczba bez kontekstu",
            "input": "Koszt to 100 złotych.",
            "expected": "Koszt to 100 złotych."
        },
        {
            "desc": "Wiek NEGATYWNY: Gwarancja",
            "input": "Gwarancja na 5 lat.", # To trudne dla regexa, może zostać podmienione
            # Jeśli regex jest prosty (cyfra + lat), to podmieni.
            # W idealnym świecie chcemy to zostawić, ale w MVP regexowym prawdopodobnie zamieni.
            # Sprawdźmy jak zachowa się Twój obecny kod:
            "expected": "Gwarancja na {age} lat." 
        },

        # ==========================================
        # 7. DATY {date} i INTERNET
        # ==========================================
        {
            "desc": "Data: Separator kropka",
            "input": "Urodzony 01.01.2000.",
            "expected": "Urodzony {date}."
        },
        {
            "desc": "Data: Separator myślnik",
            "input": "Termin: 2023-12-31.",
            "expected": "Termin: {date}."
        },
        {
            "desc": "Email: Z plusem (tagowanie)",
            "input": "jan.kowalski+praca@gmail.com",
            "expected": "{email}"
        },
        {
            "desc": "Username: Z podłogą",
            "input": "Mój IG: @super_user_1.",
            "expected": "Mój IG: {username}."
        },
        # # ==========================================
        # # 8. NOWE, BARDZIEJ ZŁOŻONE PRZYKŁADY (EDGE CASES)
        # # ==========================================
        # {
        #     "desc": "Adres: Numer z ukośnikiem i literami",
        #     "input": "Mieszkam: ul. Kręta 12a/14b.",
        #     "expected": "Mieszkam: {address}."
        # },
        # {
        #     "desc": "Adres: Aleja z cyfrą rzymską",
        #     "input": "Biuro: Al. XX-lecia 5.",
        #     "expected": "Biuro: {address}."
        # },
        # {
        #     "desc": "Adres: Plac wieloczłonowy",
        #     "input": "Spotkanie: pl. Konstytucji 3 Maja 10.",
        #     "expected": "Spotkanie: {address}."
        # },
        {
            "desc": "Email: Subdomena",
            "input": "Kontakt: admin@poczta.onet.pl.",
            "expected": "Kontakt: {email}."
        },
        {
            "desc": "Email: Dziwne znaki w local part",
            "input": "Mail: test.user_name-123@example.co.uk",
            "expected": "Mail: {email}"
        },
        {
            "desc": "Telefon: Separator kropka (może wymagać poprawki regexa)",
            "input": "Tel: 600.100.200.",
            "expected": "Tel: {phone}." 
        },
        {
            "desc": "Telefon: Format ze spacjami nieregularnymi (4-3-3)",
            "input": "Tel: 6000 100 200.", 
            "expected": "Tel: 6000 100 200." # Regex oczekuje 3-3-3, wiec to powinno zostac (negatyw)
        },
        {
            "desc": "Telefon: Długi format z +48 (spacje)",
            "input": "Kom: +48 600 123 456.",
            "expected": "Kom: {phone}."
        },
        {
            "desc": "Data: Rok na początku (ISO)",
            "input": "Raport z 2023-05-20.",
            "expected": "Raport z {date}."
        },
        {
            "desc": "MIX: Data, email i telefon",
            "input": "Dnia 2022-01-01 wysłałem maila na x@y.pl i zadzwoniłem pod 500-600-700.",
            "expected": "Dnia {date} wysłałem maila na {email} i zadzwoniłem pod {phone}."
        },
        # {
        #     "desc": "MIX: Dwa adresy w jednym zdaniu",
        #     "input": "Przeprowadzka z ul. Starej 1 na os. Nowe 5.",
        #     "expected": "Przeprowadzka z {address} na {address}."
        # },
        # {
        #     "desc": "MIX: Skomplikowany adres i PESEL",
        #     "input": "Obywatel zameldowany: Al. Jerozolimskie 100/23 m. 5, PESEL: 90010112349.",
        #     "expected": "Obywatel zameldowany: {address}, PESEL: {pesel}."
        # },
        # # ==========================================
        # # 9. JESZCZE WIĘCEJ EDGE CASES (Landlines, Dates, Complex Addrs)
        # # ==========================================
        # {
        #     "desc": "Adres: Nazwa ulicy od cyfr (Data?)",
        #     "input": "Mieszkam na ul. 11 Listopada 4.",
        #     "expected": "Mieszkam na {address}."
        # },
        # {
        #     "desc": "Adres: 'Aleje' zamiast 'Aleja'",
        #     "input": "Biuro: Aleje Jerozolimskie 200.",
        #     "expected": "Biuro: {address}."
        # },
        # {
        #     "desc": "Adres: Ulica z myślnikami i polskimi znakami",
        #     "input": "Adres: ul. Żwirki i Wigury 10.",
        #     "expected": "Adres: {address}."
        # },
        {
            "desc": "Data: Dzień/Miesiąc jednocyfrowy",
            "input": "Data urodzenia: 1.1.1990.",
            "expected": "Data urodzenia: {date}."
        },
        {
            "desc": "Data: Separator ukośnik",
            "input": "Ważne do: 2025/12/31.",
            "expected": "Ważne do: {date}."
        },
        {
            "desc": "Telefon: Ciągły z +48 bez spacji po prefiksie",
            "input": "Tel: +48123456789.",
            "expected": "Tel: {phone}."
        },
        {
            "desc": "Dokument: Dowód z 'spacją' jako błąd OCR (brak spacji)",
            "input": "Nr dowodu: ABA300400.",
            "expected": "Nr dowodu: {document-number}."
        },
        {
            "desc": "Wiek: 'lata' z liczbą słownie (negatyw)",
            "input": "Mam dwa lata.",
            "expected": "Mam dwa lata."
        },
        # {
        #     "desc": "MIX: Adres, Telefon, Data",
        #     "input": "W dniu 01-05-2022 na ul. Prostej 1 zadzwonił 600-500-400.",
        #     "expected": "W dniu {date} na {address} zadzwonił {phone}."
        # },
        # ==========================================
        # 10. KOMPLEKSOWE EDGE CASES (Thorough)
        # ==========================================
        # --- Adresy: Honorifics & formatting ---
        # {
        #     "desc": "Adres: Honorifics (św. - lowercase)",
        #     "input": "Mieszkam przy ul. św. Jana 5.",
        #     "expected": "Mieszkam przy {address}."
        # },
        # {
        #     "desc": "Adres: Honorifics (Gen.)",
        #     "input": "Ulica: ul. Gen. Władysława Andersa 1.",
        #     "expected": "Ulica: {address}."
        # },
        # {
        #     "desc": "Adres: Honorifics (ks.)",
        #     "input": "Parafia: ul. ks. Jerzego Popiełuszki 2.",
        #     "expected": "Parafia: {address}."
        # },
        # {
        #     "desc": "Adres: Honorifics (prof.)",
        #     "input": "Klinika: ul. prof. Religi 3.",
        #     "expected": "Klinika: {address}."
        # },
        # {
        #     "desc": "Adres: Honorifics (Dr z kropką)",
        #     "input": "Gabinet: ul. Dr. Judyma 4.",
        #     "expected": "Gabinet: {address}."
        # },
        # {
        #     "desc": "Adres: Honorifics (im.)",
        #     "input": "Szkoła przy ul. im. Adama Mickiewicza 10.",
        #     "expected": "Szkoła przy {address}."
        # },
        # {
        #     "desc": "Adres: Numer 3-go",
        #     "input": "Święto: ul. 3-go Maja 1.",
        #     "expected": "Święto: {address}."
        # },
        # {
        #     "desc": "Adres: Aleja z cyfrą (1000-lecia)",
        #     "input": "Trasa: Al. 1000-lecia 5.",
        #     "expected": "Trasa: {address}."
        # },
        # {
        #     "desc": "Adres: Wieloczłonowy (Bohaterów Monte Cassino)",
        #     "input": "Spacer: ul. Bohaterów Monte Cassino 5.",
        #     "expected": "Spacer: {address}."
        # },
        # {
        #     "desc": "Adres: Plac (Wielka litera)",
        #     "input": "Spotkanie: Plac Zbawiciela 1.",
        #     "expected": "Spotkanie: {address}."
        # },
        # {
        #     "desc": "Adres: Inicjał imienia",
        #     "input": "Patron: ul. A. Mickiewicza 1.",
        #     "expected": "Patron: {address}."
        # },
        # {
        #     "desc": "Adres: Inicjał bez spacji (typowe typo)",
        #     "input": "Błąd: ul. A.Mickiewicza 1.",
        #     "expected": "Błąd: {address}."
        # },
        # {
        #     "desc": "Adres: Nazwa dwuczłonowa (Nowy Świat)",
        #     "input": "Centrum: ul. Nowy Świat 22.",
        #     "expected": "Centrum: {address}."
        # },
        
        # --- Telefony: Różne formaty ---
        {
            "desc": "Telefon: +48 ze spacjami (standard)",
            "input": "Tel: +48 123 456 789.",
            "expected": "Tel: {phone}."
        },
        {
            "desc": "Telefon: +48 z myślnikami",
            "input": "Tel: +48 123-456-789.",
            "expected": "Tel: {phone}."
        },
        {
            "desc": "Telefon: 0048 prefix",
            "input": "Tel: 0048 123 456 789.",
            "expected": "Tel: {phone}."
        },
        {
            "desc": "Telefon: Prefix w nawiasie (48)",
            "input": "Tel: (48) 123 456 789.",
            "expected": "Tel: {phone}."
        },
        {
            "desc": "Telefon: Prefix (+48)",
            "input": "Tel: (+48) 123 456 789.",
            "expected": "Tel: {phone}."
        },
        {
            "desc": "Telefon: Kropki separator",
            "input": "Tel: 123.456.789.",
            "expected": "Tel: {phone}."
        },
        
        # --- Daty ---
        {
            "desc": "Data: Kropki (krótki rok?)",
            "input": "Data: 01.01.2023.",
            "expected": "Data: {date}."
        },
        {
            "desc": "Data: Slashe",
            "input": "Data: 1/1/2023.",
            "expected": "Data: {date}."
        },
        {
            "desc": "Data: ISO",
            "input": "ISO: 2023-01-01.",
            "expected": "ISO: {date}."
        },
        
        # --- E-mail ---
        {
            "desc": "Email: Krótki (test@test.pl)",
            "input": "Mail: test@test.pl.",
            "expected": "Mail: {email}."
        },
        {
            "desc": "Email: Cyfry w local part",
            "input": "Mail: 123@test.pl.",
            "expected": "Mail: {email}."
        },
        
        # ==========================================
        # 11. ULTRA-EDGE CASES (All types)
        # ==========================================
        
        # --- FINANSE (Bank & Karta) ---
        {
            "desc": "Bank: IBAN z 'PL' małymi literami",
            "input": "Konto: pl 11 2222 3333 4444 5555 6666 7777.",
            "expected": "Konto: {bank-account}." # Obecny regex wymaga [A-Z]{2}
        },
        {
            "desc": "Bank: IBAN bez 'PL'",
            "input": "Konto: 11 2222 3333 4444 5555 6666 7777.",
            "expected": "Konto: 11 2222 3333 4444 5555 6666 7777." # Powinno ignorować (polski standard to 26 cyfr + PL)
        },
        {
            "desc": "Karta: Visa z myślnikami (inny format)",
            "input": "Karta: 4000-1234-5678-9010.",
            "expected": "Karta: {credit-card-number}."
        },
        {
            "desc": "Karta: Karta ukryta (gwiazdki)",
            "input": "Karta: 4000********9010.",
            "expected": "Karta: 4000********9010." # Nie powinno łapać
        },

        # --- DOKUMENTY (Dowód, Paszport, VIN) ---
        {
            "desc": "Dokument: Dowód z małymi literami",
            "input": "DO: abc 123456.",
            "expected": "DO: {document-number}." # Obecny regex wymaga [A-Z]{3}
        },
        {
            "desc": "Dokument: Paszport z 'spacją' jako błąd",
            "input": "Paszport: AB 123 45 67.", 
            "expected": "Paszport: AB 123 45 67." # Zbyt rozbite
        },
        {
            "desc": "VIN: Koniec linii",
            "input": "Mój VIN to 1HGCM82633A004352",
            "expected": "Mój VIN to {document-number}"
        },
        {
            "desc": "VIN: Zawiera I, O, Q (niepoprawne znaki w VIN)",
            "input": "Błędny VIN: 1HGCM82633A00435Q.", # Q jest zakazane w VIN
            "expected": "Błędny VIN: 1HGCM82633A00435Q." # Nie powinno złapać
        },

        # --- WIEK ---
        {
            "desc": "Wiek: 'miesięcy'",
            "input": "Dziecko ma 9 miesięcy.",
            "expected": "Dziecko ma 9 miesięcy." # Nie powinno ruszać
        },
        {
            "desc": "Wiek: '18+'",
            "input": "Film dla widzów 18+.",
            "expected": "Film dla widzów {age}+."
        },
        {
            "desc": "Wiek: Zakres",
            "input": "Wiek: 20-30 lat.",
            "expected": "Wiek: {age}-{age} lat."
        },
        
        # --- TELEFON ---
        {
            "desc": "Telefon: Nawiasy wokół numeru",
            "input": "Tel: (600) 100 200.",
            "expected": "Tel: (600) 100 200." # Obecny regex może tego nie łapać bez +48
        },
        {
            "desc": "Telefon: Zamiast spacji kropki (już było, ale +48)",
            "input": "Tel: +48.600.100.200.",
            "expected": "Tel: {phone}."
        },
        {
            "desc": "Telefon: Stacjonarny (Warszawa)",
            "input": "Biuro: (22) 628 12 34.",
            "expected": "Biuro: {phone}." # 9 cyfr łącznie, format 2+7
        },

        # --- E-MAIL & USERNAME ---
        {
            "desc": "Email: IP domain (rzadkie)",
            "input": "admin@192.168.1.1",
            "expected": "admin@192.168.1.1" # Regex zazwyczaj wymaga domeny tekstowej
        },
        {
            "desc": "Username: Kropka na końcu zdania",
            "input": "To mój nick: @janek.",
            "expected": "To mój nick: {username}."
        },
        {
            "desc": "Username: Tylko @ (błąd)",
            "input": "To nie nick: @",
            "expected": "To nie nick: @"
        },
        
        # # --- MIX ---
        # {
        #     "desc": "MIX: Adres i Wiek",
        #     "input": "Mieszka na ul. Długiej 5, ma 99 lat.",
        #     "expected": "Mieszka na {address}, ma {age} lat."
        # }
    ]

    print(f"{'TEST CASE':<50} | {'STATUS':<10} | {'INFO'}")
    print("-" * 80)

    passed_count = 0
    failed_count = 0

    for test in test_cases:
        result = preprocessor.process(test['input'])
        
        if result == test['expected']:
            print(f"{test['desc']:<50} | ✅ PASS     |")
            passed_count += 1
        else:
            print(f"{test['desc']:<50} | ❌ FAIL     |")
            print(f"   Input:    {test['input']}")
            print(f"   Expected: {test['expected']}")
            print(f"   Got:      {result}")
            print("-" * 80)
            failed_count += 1

    print("\n" + "="*30)
    print(f"WYNIKI TESTÓW: PASS: {passed_count}, FAIL: {failed_count}")
    print("="*30)