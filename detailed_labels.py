# import re
# import time
# import logging
# from rapidfuzz.distance import Levenshtein
# import morfeusz2

# # ================= LOGOWANIE =================
# logger = logging.getLogger("detailed_labels")
# logger.setLevel(logging.DEBUG)
# logging.disable(logging.CRITICAL)

# fh = logging.FileHandler("detailed_labels.log", encoding="utf8")
# fh.setLevel(logging.DEBUG)
# formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
# fh.setFormatter(formatter)
# logger.addHandler(fh)

# ch = logging.StreamHandler()
# ch.setLevel(logging.INFO)
# ch.setFormatter(formatter)
# logger.addHandler(ch)

# logger.info("=== START DETAILED LABELS ===")

# # ================= KONFIGURACJA =================
# FILE_ORIGINAL = "data/orig.txt"
# FILE_ANONYMIZED = "data/anonimized.txt"
# FILE_OUTPUT = "outputs/wyniki.txt"

# KEEP_LABELS = {"name", "surname", "city", "sex", "relative", "job-title", "sexual-orientation"}
# TOKEN_RE = re.compile(r'(\[[a-zA-Z0-9-]+\])|(\w+)|(\s+)|([^\w\s\[\]]+)')

# PRZYPADKI = {
#     "nom": "mianownik",
#     "gen": "dopełniacz",
#     "dat": "celownik",
#     "acc": "biernik",
#     "inst": "narzędnik",
#     "loc": "miejscownik",
#     "voc": "wołacz"
# }

# morfeusz = morfeusz2.Morfeusz()
# logger.info("Uruchomiono Morfeusz2")

# # ================= FUNKCJE =================
# def tokenize_keep_delimiters(text):
#     return [m.group(0) for m in TOKEN_RE.finditer(text)]

# # ---------- pomocniczne extractory ----------
# def extract_przypadek(tag_string):
#     """
#     Wyciąga pierwszy pasujący przypadek z tag_string.
#     Obsługuje np. 'subst:sg:nom.acc:m3' i 'adj:sg:nom.voc:f:pos'
#     """
#     if not tag_string or not isinstance(tag_string, str):
#         return None
#     parts = tag_string.split(":")
#     for p in parts:
#         # p może być 'nom.acc' albo 'nom.voc' -> rozbijamy po '.'
#         for sub in p.split("."):
#             if sub in PRZYPADKI:
#                 return PRZYPADKI[sub]
#     return None

# def extract_rodzaj_from_tagparts(tag_parts):
#     """
#     Zamapuj symbole z tagów na 'męski' / 'żeński'.
#     Przyjmuje listę części (np. ['adj','sg','nom.voc','f','pos'] lub ['subst','sg','nom.acc','m3'])
#     """
#     if not tag_parts:
#         return None
#     # najpierw sprawdź bezpośrednie oznaczenia 'f' lub 'm'
#     for t in tag_parts:
#         if t == "f" or t == "subst:f" or t == "adj:f":
#             return "woman"
#         if t in ("m1", "m2", "m3", "m", "subst:m", "adj:m"):
#             return "man"
#     # czasem mamy 'm3' jako oddzielny token po split(":") lub po "." — już uwzględnione wyżej
#     # heurystyka: jeśli żadnego nie ma, sprawdź końcówkę bazowej formy (ale caller musi przekazać base)
#     return None


# def analizuj_slowo_city(tokens):
#     kand_full = " ".join(tokens)
#     for tok in tokens:
#         analizy = morfeusz.analyse(tok)
#         for item in analizy:
#             base = item[2][0] if isinstance(item[2], tuple) else item[2]
#             tags = item[2][2] if isinstance(item[2], tuple) else ""
#             dodatkowe = item[3] if len(item) > 3 else []
#             if "nazwa_geograficzna" in dodatkowe or "subst" in tags:
#                 przypadek = extract_przypadek(tags)
#                 if przypadek:
#                     logger.info("Analiza miasta: %r -> przypadek=%r", kand_full, przypadek)
#                     return kand_full, przypadek
#     return kand_full, None

# def analizuj_slowo_sex(tokens):
#     # tokens = lista tokenów (najczęściej 1 token: ["kobieta"])
#     kand_full = " ".join(tokens)
#     analizy = morfeusz.analyse(kand_full)
#     for idx, item in enumerate(analizy):
#         logger.debug("  RAW_SEX[%d]: %r", idx, item)
#         base = item[2][0] if isinstance(item[2], tuple) else item[2]
#         tags = item[2][2] if isinstance(item[2], tuple) else ""
#         dodatkowe = item[3] if len(item) > 3 else []
#         if "subst" in tags:  # rzeczownik
#             przypadek = extract_przypadek(tags)
#             if przypadek:
#                 logger.info("Analiza płci zakończona: %r -> przypadek=%r", kand_full, przypadek)
#                 return kand_full, przypadek
#     logger.warning("Nie znaleziono wiarygodnej analizy dla płci: %r", kand_full)
#     return kand_full, None


# def analizuj_slowo(slowo, label):
#     """
#     Zwraca (base, rodzaj, przypadek) lub (None, None, None)
#     Rozpoznaje subst i adj (przymiotniki) - 
#     """
#     logger.debug("Analiza słowa: %r, etykieta: %r", slowo, label)
#     try:
#         analizy = morfeusz.analyse(slowo)
#     except Exception:
#         logger.exception("Błąd morfeusz.analyse dla: %r", slowo)
#         return None, None, None

#     logger.debug("Morfeusz zwrócił %d analiz dla słowa %r", len(analizy), slowo)
#     for idx, item in enumerate(analizy):
#         logger.debug("  RAW[%d]: %r", idx, item)
#         # ujednolicamy parts jak wcześniej
#         parts = list(item[2]) if isinstance(item[2], tuple) else list(item[2:])
#         # base = pierwszy string
#         base = next((p for p in parts if isinstance(p, str)), None)
#         # tags = ostatni string zawierający ":" (np. 'subst:sg:nom.acc:m3' lub 'adj:sg:nom.voc:f:pos')
#         tags = next((p for p in reversed(parts) if isinstance(p, str) and ":" in p), None)

#         # dodatkowe elementy (np. ['nazwa_geograficzna'])
#         dodatkowe = item[3] if len(item) > 3 else []

#         logger.debug("    parsed parts=%r -> base=%r, tags=%r, dodatkowe=%r", parts, base, tags, dodatkowe)

#         if not base:
#             continue

#         # przygotuj listę "tag_parts" z split(":") i rozbiciem po "."
#         tag_parts = []
#         if tags:
#             for part in tags.split(":"):
#                 tag_parts.extend(part.split("."))

#         # spróbuj wyciągnąć przypadek
#         przypadek = extract_przypadek(tags) if tags else None

#         # spróbuj wyciągnąć rodzaj z tag_parts
#         rodzaj = extract_rodzaj_from_tagparts(tag_parts)

#         # Jeśli nie znaleziono rodzaju, dodatkowa heurystyka: końcówka -a -> żeński
#         if not rodzaj and isinstance(base, str) and base.endswith("a"):
#             rodzaj = "woman"

#         # Akceptujemy zarówno rzeczowniki (subst) jak i przymiotniki (adj)
#         # oraz przydatne dodatkowe info (np. 'nazwa_geograficzna').
#         accept = False
#         if tags and ("subst" in tags or "adj" in tags):
#             accept = True
#         if dodatkowe:
#             # jeżeli w dodatkowych tagach są przydatne info (np. 'nazwa_geograficzna'), też akceptujemy
#             accept = True

#         logger.debug("    decyzja: accept=%r, base=%r, rodzaj=%r, przypadek=%r", accept, base, rodzaj, przypadek)

#         if accept and przypadek:
#             logger.info("Analiza zakończona: %r -> base=%r, rodzaj=%r, przypadek=%r", slowo, base, rodzaj, przypadek)
#             return base, rodzaj, przypadek

#     logger.warning("Nie znaleziono wiarygodnej analizy dla słowa: %r", slowo)
#     return None, None, None


# def process_text_tokenized(original, anonymized, allowed_labels):
#     orig_tokens = tokenize_keep_delimiters(original)
#     anon_tokens = tokenize_keep_delimiters(anonymized)
#     ops = Levenshtein.opcodes(anon_tokens, orig_tokens)
#     output = []

#     for tag, i1, i2, j1, j2 in ops:
#         anon_chunk = anon_tokens[i1:i2]
#         orig_chunk = orig_tokens[j1:j2]

#         if tag == "equal":
#             output.extend(anon_chunk)
#         elif tag == "replace":
#             for idx, token in enumerate(anon_chunk):
#                 label_name = token[1:-1]
#                 if label_name in allowed_labels:
#                     if idx + j1 < len(orig_tokens):
#                         # obsługa wielowyrazowych nazw dla city
#                         if label_name == "city":
#                             city_tokens = []
#                             for t_idx in range(j1 + idx, len(orig_tokens)):
#                                 t = orig_tokens[t_idx].rstrip(".,;:()[]{}")
#                                 if t.istitle():  # wielka litera
#                                     city_tokens.append(t)
#                                 else:
#                                     break
#                             base, przypadek = analizuj_slowo_city(city_tokens)
#                             if base and przypadek:
#                                 tag_new = f"[city][{przypadek}]"
#                             else:
#                                 tag_new = "[city]"
#                             output.append(tag_new)
#                             logger.info("Zastąpiono %r -> %r (city: %r)", token, tag_new, " ".join(city_tokens))

#                         elif label_name == "sex":
#                             kand = orig_tokens[j1 + idx].rstrip(".,;:()[]{}")
#                             base, przypadek = analizuj_slowo_sex([kand])
#                             if base and przypadek:
#                                 tag_new = f"[sex][{przypadek}]"
#                             else:
#                                 tag_new = "[sex]"
#                             output.append(tag_new)
#                             logger.info("Zastąpiono %r -> %r (sex: %r)", token, tag_new, kand)

#                         else:
#                             # name, surname
#                             kand = orig_tokens[j1 + idx].rstrip(".,;:()[]{}")
#                             base, rodzaj, przypadek = analizuj_slowo(kand, label_name)
#                             if base:
#                                 tag_new = f"[{label_name}][{rodzaj}][{przypadek}]" if rodzaj and przypadek else f"[{label_name}]"
#                                 output.append(tag_new)
#                                 logger.info("Zastąpiono %r -> %r", token, tag_new)
#                             else:
#                                 output.append(token)
#                                 logger.warning("Nie udało się zinterpretować słowa %r dla placeholdera %r", kand, token)
#                     else:
#                         output.append(token)
#                         logger.warning("Brak słowa w pliku oryginalnym dla placeholdera %r", token)
#                 else:
#                     output.extend([token])
#         elif tag == "delete":
#             output.extend(anon_chunk)
#         elif tag == "insert":
#             pass
#     return "".join(output)

# def read_file(filepath):
#     try:
#         with open(filepath, "r", encoding="utf-8") as f:
#             return f.read()
#     except FileNotFoundError:
#         logger.error("Brak pliku: %s", filepath)
#         return None

# def save_file(filepath, content):
#     with open(filepath, "w", encoding="utf-8") as f:
#         f.write(content)
#     logger.info("Zapisano wynik do: %s", filepath)

# if __name__ == "__main__":
#     start = time.perf_counter()
#     orig = read_file(FILE_ORIGINAL)
#     anon = read_file(FILE_ANONYMIZED)

#     if orig and anon:
#         print("\n================= TEKST ORYGINALNY =================")
#         # print(orig)

#         # --- GENEROWANIE LABELI ---
#         result = process_text_tokenized(orig, anon, KEEP_LABELS)
#         save_file(FILE_OUTPUT, result)

#         print("\n================= TEKST PO DODANIU LABELI =================")
#         # print(result)

#         # # --- GENEROWANIE DANYCH SYNTETYCZNYCH ---
#         # from synthetic_generator import generate_synthetic_output
#         # synthetic = generate_synthetic_output(result)
#         # save_file("wyniki_syntetyczne.txt", synthetic)

#         # print("\n================= TEKST SYNTETYCZNY =================")
#         # print(synthetic)

#         # print("\n✔ Wygenerowano syntetyczny tekst -> wyniki_syntetyczne.txt")

#     end = time.perf_counter()
#     print("Czas wykonania: sekundy", end - start)
#     logger.info("=== KONIEC ===")


# # import re
# # import time
# # import logging
# # from rapidfuzz.distance import Levenshtein
# # import morfeusz2
# # from functools import lru_cache

# # # ================= LOGOWANIE =================
# # logger = logging.getLogger("detailed_labels")
# # logger.setLevel(logging.INFO)  # Zmieniono z DEBUG na INFO
# # logging.disable(logging.CRITICAL)

# # fh = logging.FileHandler("detailed_labels.log", encoding="utf8")
# # fh.setLevel(logging.INFO)  # Zmieniono z DEBUG
# # formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
# # fh.setFormatter(formatter)
# # logger.addHandler(fh)

# # ch = logging.StreamHandler()
# # ch.setLevel(logging.WARNING)  # Zmieniono z INFO
# # ch.setFormatter(formatter)
# # logger.addHandler(ch)

# # logger.info("=== START DETAILED LABELS ===")

# # # ================= KONFIGURACJA =================
# # FILE_ORIGINAL = "data/orig.txt"
# # FILE_ANONYMIZED = "data/anonimized.txt"
# # FILE_OUTPUT = "outputs/wyniki.txt"

# # KEEP_LABELS = {"name", "surname", "city", "sex", "relative", "job-title", "sexual-orientation"}
# # TOKEN_RE = re.compile(r'(\[[a-zA-Z0-9-]+\])|(\w+)|(\s+)|([^\w\s\[\]]+)')

# # PRZYPADKI = {
# #     "nom": "mianownik",
# #     "gen": "dopełniacz",
# #     "dat": "celownik",
# #     "acc": "biernik",
# #     "inst": "narzędnik",
# #     "loc": "miejscownik",
# #     "voc": "wołacz"
# # }

# # # Cache dla Morfeusza - kluczowa optymalizacja!
# # morfeusz = morfeusz2.Morfeusz()
# # MORFEUSZ_CACHE = {}
# # logger.info("Uruchomiono Morfeusz2 z cache'owaniem")

# # # ================= FUNKCJE =================
# # def tokenize_keep_delimiters(text):
# #     """Zoptymalizowana tokenizacja"""
# #     return TOKEN_RE.findall(text)

# # def extract_przypadek(tag_string):
# #     """Wyciąga pierwszy pasujący przypadek z tag_string - zoptymalizowana"""
# #     if not tag_string:
# #         return None
    
# #     # Szybkie sprawdzenie bez split jeśli to możliwe
# #     for case_key, case_name in PRZYPADKI.items():
# #         if case_key in tag_string:
# #             return case_name
# #     return None

# # def extract_rodzaj_from_tagparts(tag_parts):
# #     """Zamapuj symbole z tagów na 'męski' / 'żeński' - zoptymalizowana"""
# #     if not tag_parts:
# #         return None
    
# #     # Jeden przebieg z wczesnym returnem
# #     for t in tag_parts:
# #         if 'f' in t:
# #             return "woman"
# #         if any(m in t for m in ('m1', 'm2', 'm3', 'm')):
# #             return "man"
# #     return None

# # def analyse_with_cache(word):
# #     """Cache dla wywołań Morfeusz2 - KLUCZOWA OPTYMALIZACJA"""
# #     if word not in MORFEUSZ_CACHE:
# #         try:
# #             MORFEUSZ_CACHE[word] = morfeusz.analyse(word)
# #         except Exception as e:
# #             logger.error(f"Błąd morfeusz dla '{word}': {e}")
# #             MORFEUSZ_CACHE[word] = []
# #     return MORFEUSZ_CACHE[word]

# # def analizuj_slowo_city(tokens):
# #     """Zoptymalizowana analiza miasta"""
# #     kand_full = " ".join(tokens)
    
# #     for tok in tokens:
# #         analizy = analyse_with_cache(tok)
        
# #         for item in analizy:
# #             base = item[2][0] if isinstance(item[2], tuple) else item[2]
# #             tags = item[2][2] if isinstance(item[2], tuple) else ""
# #             dodatkowe = item[3] if len(item) > 3 else []
            
# #             if "nazwa_geograficzna" in dodatkowe or "subst" in tags:
# #                 przypadek = extract_przypadek(tags)
# #                 if przypadek:
# #                     return kand_full, przypadek
    
# #     return kand_full, None

# # def analizuj_slowo_sex(tokens):
# #     """Zoptymalizowana analiza płci"""
# #     kand_full = " ".join(tokens)
# #     analizy = analyse_with_cache(kand_full)
    
# #     for item in analizy:
# #         base = item[2][0] if isinstance(item[2], tuple) else item[2]
# #         tags = item[2][2] if isinstance(item[2], tuple) else ""
        
# #         if "subst" in tags:
# #             przypadek = extract_przypadek(tags)
# #             if przypadek:
# #                 return kand_full, przypadek
    
# #     return kand_full, None

# # def analizuj_slowo(slowo, label):
# #     """Zoptymalizowana główna analiza słowa"""
# #     analizy = analyse_with_cache(slowo)
    
# #     if not analizy:
# #         return None, None, None
    
# #     for item in analizy:
# #         parts = list(item[2]) if isinstance(item[2], tuple) else list(item[2:])
# #         base = next((p for p in parts if isinstance(p, str)), None)
# #         tags = next((p for p in reversed(parts) if isinstance(p, str) and ":" in p), None)
# #         dodatkowe = item[3] if len(item) > 3 else []
        
# #         if not base:
# #             continue
        
# #         tag_parts = []
# #         if tags:
# #             for part in tags.split(":"):
# #                 tag_parts.extend(part.split("."))
        
# #         przypadek = extract_przypadek(tags) if tags else None
# #         rodzaj = extract_rodzaj_from_tagparts(tag_parts)
        
# #         if not rodzaj and isinstance(base, str) and base.endswith("a"):
# #             rodzaj = "woman"
        
# #         accept = (tags and ("subst" in tags or "adj" in tags)) or bool(dodatkowe)
        
# #         if accept and przypadek:
# #             return base, rodzaj, przypadek
    
# #     return None, None, None

# # def process_text_tokenized(original, anonymized, allowed_labels):
# #     """Zoptymalizowane przetwarzanie tekstu"""
# #     # Tokenizacja raz na początku
# #     orig_tokens = [m[0] if isinstance(m, tuple) else m for m in tokenize_keep_delimiters(original)]
# #     anon_tokens = [m[0] if isinstance(m, tuple) else m for m in tokenize_keep_delimiters(anonymized)]
    
# #     ops = Levenshtein.opcodes(anon_tokens, orig_tokens)
# #     output = []
    
# #     # Pre-kompiluj regex dla czyszczenia tokenów
# #     cleanup_re = re.compile(r'[.,;:(){}\[\]]+$')

# #     for tag, i1, i2, j1, j2 in ops:
# #         anon_chunk = anon_tokens[i1:i2]
        
# #         if tag == "equal":
# #             output.extend(anon_chunk)
# #         elif tag == "replace":
# #             for idx, token in enumerate(anon_chunk):
# #                 if not (token.startswith('[') and token.endswith(']')):
# #                     output.append(token)
# #                     continue
                
# #                 label_name = token[1:-1]
# #                 if label_name not in allowed_labels:
# #                     output.append(token)
# #                     continue
                
# #                 orig_idx = j1 + idx
# #                 if orig_idx >= len(orig_tokens):
# #                     output.append(token)
# #                     continue
                
# #                 # Obsługa różnych typów etykiet
# #                 if label_name == "city":
# #                     city_tokens = []
# #                     for t_idx in range(orig_idx, len(orig_tokens)):
# #                         t = cleanup_re.sub('', orig_tokens[t_idx])
# #                         if t and t[0].isupper():
# #                             city_tokens.append(t)
# #                         else:
# #                             break
                    
# #                     _, przypadek = analizuj_slowo_city(city_tokens)
# #                     tag_new = f"[city][{przypadek}]" if przypadek else "[city]"
# #                     output.append(tag_new)
                
# #                 elif label_name == "sex":
# #                     kand = cleanup_re.sub('', orig_tokens[orig_idx])
# #                     _, przypadek = analizuj_slowo_sex([kand])
# #                     tag_new = f"[sex][{przypadek}]" if przypadek else "[sex]"
# #                     output.append(tag_new)
                
# #                 else:
# #                     kand = cleanup_re.sub('', orig_tokens[orig_idx])
# #                     base, rodzaj, przypadek = analizuj_slowo(kand, label_name)
                    
# #                     if base and rodzaj and przypadek:
# #                         tag_new = f"[{label_name}][{rodzaj}][{przypadek}]"
# #                     else:
# #                         tag_new = token
# #                     output.append(tag_new)
        
# #         elif tag == "delete":
# #             output.extend(anon_chunk)
# #         # insert - pomijamy

# #     return "".join(output)

# # def read_file(filepath):
# #     try:
# #         with open(filepath, "r", encoding="utf-8") as f:
# #             return f.read()
# #     except FileNotFoundError:
# #         logger.error("Brak pliku: %s", filepath)
# #         return None

# # def save_file(filepath, content):
# #     with open(filepath, "w", encoding="utf-8") as f:
# #         f.write(content)
# #     logger.info("Zapisano wynik do: %s", filepath)

# # if __name__ == "__main__":
# #     start = time.perf_counter()
# #     orig = read_file(FILE_ORIGINAL)
# #     anon = read_file(FILE_ANONYMIZED)

# #     if orig and anon:
# #         print("\n================= PRZETWARZANIE =================")
        
# #         result = process_text_tokenized(orig, anon, KEEP_LABELS)
# #         save_file(FILE_OUTPUT, result)
        
# #         end = time.perf_counter()
# #         cache_size = len(MORFEUSZ_CACHE)
        
# #         print(f"✔ Przetworzono w {end - start:.3f} sekund")
# #         print(f"✔ Cache Morfeusz: {cache_size} unikalnych słów")
# #         print(f"✔ Wynik zapisano do: {FILE_OUTPUT}")
    
# #     logger.info("=== KONIEC ===")
import re
import time
import logging
from rapidfuzz.distance import Levenshtein
import morfeusz2
from functools import lru_cache

# ================= LOGOWANIE =================
logger = logging.getLogger("detailed_labels")
logger.setLevel(logging.INFO)  # Zmieniono z DEBUG na INFO
# Wyłączam logowanie w tym przykładzie, aby nie tworzyć pliku, 
# ale pozostawiam konfigurację, zgodnie z oryginalnym kodem.
# logging.disable(logging.CRITICAL) 

fh = logging.FileHandler("detailed_labels.log", encoding="utf8")
fh.setLevel(logging.INFO)  # Zmieniono z DEBUG
formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)  # Zmieniono z INFO
ch.setFormatter(formatter)
logger.addHandler(ch)

logger.info("=== START DETAILED LABELS ===")

# ================= KONFIGURACJA =================
FILE_ORIGINAL = "data/orig.txt"
FILE_ANONYMIZED = "data/anonimized.txt"
FILE_OUTPUT = "outputs/wyniki.txt"

KEEP_LABELS = {"name", "surname", "city", "sex", "relative", "job-title", "sexual-orientation"}
TOKEN_RE = re.compile(r'(\[[a-zA-Z0-9-]+\])|(\w+)|(\s+)|([^\w\s\[\]]+)')

PRZYPADKI = {
    "nom": "mianownik",
    "gen": "dopełniacz",
    "dat": "celownik",
    "acc": "biernik",
    "inst": "narzędnik",
    "loc": "miejscownik",
    "voc": "wołacz"
}

# Cache dla Morfeusza - kluczowa optymalizacja!
morfeusz = morfeusz2.Morfeusz()
MORFEUSZ_CACHE = {}
logger.info("Uruchomiono Morfeusz2 z cache'owaniem")

# ================= FUNKCJE =================
def tokenize_keep_delimiters(text):
    """Zoptymalizowana tokenizacja"""
    tokens = []
    for match in TOKEN_RE.finditer(text):
        tokens.append(match.group(0))
    return tokens

def extract_przypadek(tag_string):
    """Wyciąga pierwszy pasujący przypadek z tag_string - zoptymalizowana"""
    if not tag_string:
        return None
    
    # Szybkie sprawdzenie bez split jeśli to możliwe
    for case_key, case_name in PRZYPADKI.items():
        if case_key in tag_string:
            return case_name
    return None

def extract_rodzaj_from_tagparts(tag_parts):
    """Zamapuj symbole z tagów na 'męski' / 'żeński' - zoptymalizowana"""
    if not tag_parts:
        return None
    
    # Jeden przebieg z wczesnym returnem
    for t in tag_parts:
        if 'f' in t:
            return "woman"
        if any(m in t for m in ('m1', 'm2', 'm3', 'm')):
            return "man"
    return None

def analyse_with_cache(word):
    """Cache dla wywołań Morfeusz2 - KLUCZOWA OPTYMALIZACJA"""
    if word not in MORFEUSZ_CACHE:
        try:
            MORFEUSZ_CACHE[word] = morfeusz.analyse(word)
        except Exception as e:
            logger.error(f"Błąd morfeusz dla '{word}': {e}")
            MORFEUSZ_CACHE[word] = []
    return MORFEUSZ_CACHE[word]

def analizuj_slowo_city(tokens):
    """Zoptymalizowana analiza miasta"""
    kand_full = " ".join(tokens)
    
    for tok in tokens:
        analizy = analyse_with_cache(tok)
        
        for item in analizy:
            base = item[2][0] if isinstance(item[2], tuple) else item[2]
            tags = item[2][2] if isinstance(item[2], tuple) else ""
            dodatkowe = item[3] if len(item) > 3 else []
            
            if "nazwa_geograficzna" in dodatkowe or "subst" in tags:
                przypadek = extract_przypadek(tags)
                if przypadek:
                    return kand_full, przypadek
    
    return kand_full, None

def analizuj_slowo_sex(tokens):
    """Zoptymalizowana analiza płci"""
    kand_full = " ".join(tokens)
    analizy = analyse_with_cache(kand_full)
    
    for item in analizy:
        # Base i tags są w trzecim elemencie krotki
        if len(item) >= 3 and isinstance(item[2], tuple):
            base = item[2][0]
            tags = item[2][2]
        else:
            base = None
            tags = None
        
        if tags and "subst" in tags:
            przypadek = extract_przypadek(tags)
            if przypadek:
                return kand_full, przypadek
    
    return kand_full, None

def analizuj_slowo(slowo, label):
    """Zoptymalizowana główna analiza słowa"""
    analizy = analyse_with_cache(slowo)
    
    if not analizy:
        return None, None, None
    
    for item in analizy:
        # Wyodrębnienie base i tags z item[2]
        base = None
        tags = None
        if len(item) >= 3 and isinstance(item[2], tuple):
            base = item[2][0]
            tags = item[2][2]
        elif len(item) >= 3 and isinstance(item[2], str):
             # Prostszy przypadek, jeśli Morfeusz zwraca tylko string
            base = item[2]
            tags = ""
        
        dodatkowe = item[3] if len(item) > 3 else []
        
        if not base:
            continue
        
        tag_parts = []
        if tags:
            for part in tags.split(":"):
                tag_parts.extend(part.split("."))
        
        przypadek = extract_przypadek(tags) if tags else None
        rodzaj = extract_rodzaj_from_tagparts(tag_parts)
        
        # Heurystyka dla rodzaju - jeśli nie wykryto rodzaju, a słowo kończy się na 'a', zakładamy 'żeński'
        if not rodzaj and isinstance(base, str) and base.endswith("a"):
            rodzaj = "woman"
        
        # Akceptujemy, jeśli tag zawiera 'subst' (rzeczownik), 'adj' (przymiotnik) lub są dodatkowe informacje
        accept = (tags and ("subst" in tags or "adj" in tags)) or bool(dodatkowe)
        
        if accept and przypadek:
            return base, rodzaj, przypadek
    
    return None, None, None

def process_text_tokenized(original, anonymized, allowed_labels):
    """Zoptymalizowane przetwarzanie tekstu, korzystające z Levenshtein.opcodes"""
    
    # Tokenizacja raz na początku
    orig_tokens = tokenize_keep_delimiters(original)
    anon_tokens = tokenize_keep_delimiters(anonymized)
    
    # Obliczenie operacji edycyjnych, co pozwala zsynchronizować tokeny
    ops = Levenshtein.opcodes(anon_tokens, orig_tokens)
    output = []
    
    # Pre-kompiluj regex dla czyszczenia tokenów
    cleanup_re = re.compile(r'[.,;:(){}\[\]\n]+') # Dodałem \n do czyszczenia
    
    for tag, i1, i2, j1, j2 in ops:
        anon_chunk = anon_tokens[i1:i2]
        
        if tag == "equal":
            output.extend(anon_chunk)
        elif tag == "replace":
            # Iterujemy po tokenach w sekcji replace z pliku anonimizowanego
            for idx, token in enumerate(anon_chunk):
                # Sprawdzamy, czy token jest etykietą [LABEL]
                if not (token.startswith('[') and token.endswith(']')):
                    output.append(token)
                    continue
                
                label_name = token[1:-1]
                # Pomijamy etykiety, których nie chcemy analizować
                if label_name not in allowed_labels:
                    output.append(token)
                    continue
                
                # Ustalanie indeksu w oryginalnym tekście
                orig_idx = j1 + idx
                if orig_idx >= len(orig_tokens):
                    output.append(token)
                    continue
                
                # --- Logika analizy gramatycznej ---
                
                if label_name == "city":
                    # Heurystyka dla miast - szukamy ciągu tokenów zaczynających się z dużej litery
                    city_tokens = []
                    # Zaczynamy od potencjalnego pierwszego słowa miasta w tekście oryginalnym
                    for t_idx in range(orig_idx, len(orig_tokens)):
                        # Czyścimy słowo z interpunkcji
                        t = cleanup_re.sub('', orig_tokens[t_idx])
                        # Bierzemy tylko słowa z dużej litery (wielowyrazowe nazwy miast)
                        if t and t[0].isupper():
                            city_tokens.append(t)
                        else:
                            break # Przerywamy, jeśli trafimy na słowo niebędące częścią nazwy
                    
                    _, przypadek = analizuj_slowo_city(city_tokens)
                    tag_new = f"[{label_name}][{przypadek}]" if przypadek else f"[{label_name}]"
                    output.append(tag_new)
                
                elif label_name == "sex":
                    # Analiza płci
                    kand = cleanup_re.sub('', orig_tokens[orig_idx])
                    _, przypadek = analizuj_slowo_sex([kand])
                    tag_new = f"[{label_name}][{przypadek}]" if przypadek else f"[{label_name}]"
                    output.append(tag_new)
                
                else:
                    # Ogólna analiza dla pozostałych etykiet
                    kand = cleanup_re.sub('', orig_tokens[orig_idx])
                    base, rodzaj, przypadek = analizuj_slowo(kand, label_name)
                    
                    if base and rodzaj and przypadek:
                        tag_new = f"[{label_name}][{rodzaj}][{przypadek}]"
                    else:
                        # W przypadku niepowodzenia analizy, zostawiamy oryginalną etykietę [LABEL]
                        tag_new = token 
                    output.append(tag_new)
        
        elif tag == "delete":
            # Tokeny usunięte z pliku oryginalnego (widoczne w anonimizowanym, ale nie w oryginalnym)
            output.extend(anon_chunk)
        # insert - operacje wstawienia (insert) z operacji Levenshtein,
        # czyli tokeny występujące tylko w tekście oryginalnym (orig_tokens[j1:j2]),
        # są ignorowane, ponieważ pracujemy na tokenach z tekstu anonimizowanego.

    return "".join(output)

def read_file(filepath):
    """Odczytuje zawartość pliku, obsługując błąd FileNotFoundError."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error("Brak pliku: %s", filepath)
        # print(f"Brak pliku: {filepath}") # Można włączyć dla szybkiego debugowania
        return None

def save_file(filepath, content):
    """Zapisuje zawartość do pliku."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("Zapisano wynik do: %s", filepath)

if __name__ == "__main__":
    start = time.perf_counter()
    orig = read_file(FILE_ORIGINAL)
    anon = read_file(FILE_ANONYMIZED)

    if orig and anon:
        print("\n================= PRZETWARZANIE =================")
        
        result = process_text_tokenized(orig, anon, KEEP_LABELS)
        save_file(FILE_OUTPUT, result)
        
        end = time.perf_counter()
        cache_size = len(MORFEUSZ_CACHE)
        
        print(f"✔ Przetworzono w {end - start:.3f} sekund")
        print(f"✔ Cache Morfeusz: {cache_size} unikalnych słów")
        print(f"✔ Wynik zapisano do: {FILE_OUTPUT}")
    else:
        print("\n================= BŁĄD PLIKÓW =================")
        print("Nie można przetworzyć tekstu: brak jednego lub obu plików źródłowych.")
        
    logger.info("=== KONIEC ===")