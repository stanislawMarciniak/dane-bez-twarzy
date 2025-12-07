import re
import time
import logging
from rapidfuzz.distance import Levenshtein
import morfeusz2
from functools import lru_cache
import multiprocessing 
import os

logger = logging.getLogger("detailed_labels")
logger.setLevel(logging.INFO)  
logging.disable(logging.CRITICAL) # off

fh = logging.FileHandler("detailed_labels.log", encoding="utf8")
fh.setLevel(logging.INFO)  
formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)  
ch.setFormatter(formatter)
logger.addHandler(ch)


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

# Morfeusz i cache będą inicjalizowane lokalnie w każdym procesie
# Usunięto globalną inicjalizację morfeusz by uniknąc bottleneck i MORFEUSZ_CACHE 

# Definicje Morfeusza, które będą działać wewnątrz każdego procesu (11 procesów)
# Używamy globalnych dla modułu (choć tylko dla danego procesu) wymagałoby to dodatkowych struktór
# która jest zbędna tutaj oraz zakłócała by izolację procesów i ich cachowania
MORFEUSZ_CACHE_PROCESS = {}
MORFEUSZ_PROCESS = None

def get_morfeusz_objects():
    """Zapewnia, że Morfeusz i Cache są inicjalizowane raz na proces."""
    global MORFEUSZ_PROCESS, MORFEUSZ_CACHE_PROCESS
    if MORFEUSZ_PROCESS is None:
        MORFEUSZ_PROCESS = morfeusz2.Morfeusz()
        MORFEUSZ_CACHE_PROCESS = {}
        logger.debug("Zainicjalizowano Morfeusz2 w nowym procesie.")
    return MORFEUSZ_PROCESS, MORFEUSZ_CACHE_PROCESS

def analyse_with_cache(word):
    """Cache dla wywołań Morfeusz2 - kluczowe tutaj"""
    morfeusz_inst, cache = get_morfeusz_objects()
    if word not in cache:
        try:
            cache[word] = morfeusz_inst.analyse(word)
        except Exception as e:
            logger.error(f"Błąd morfeusz dla '{word}': {e}")
            cache[word] = []
    return cache[word]


def tokenize_keep_delimiters(text):
    """Zoptymalizowana tokenizacja"""
    tokens = []
    for match in TOKEN_RE.finditer(text):
        tokens.append(match.group(0))
    return tokens

def extract_przypadek(tag_string):
    """Wyciąga pierwszy pasujący przypadek z tag_string"""
    if not tag_string:
        return None
    
    for case_key, case_name in PRZYPADKI.items():
        if case_key in tag_string:
            return case_name
    return None

def extract_rodzaj_from_tagparts(tag_parts):
    """Mapuje symbole z tagów na 'man' / 'woman'"""
    if not tag_parts:
        return None
    
    for t in tag_parts:
        if 'f' in t:
            return "woman"
        if any(m in t for m in ('m1', 'm2', 'm3', 'm')):
            return "man"
    return None

def analizuj_slowo_city(tokens):
    """Analiza miasta"""
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
    """Analiza płci"""
    kand_full = " ".join(tokens)
    analizy = analyse_with_cache(kand_full)
    
    for item in analizy:
        # rozpatrywanie kolejnych elementów krotki
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
    """Główna analiza słowa"""
    analizy = analyse_with_cache(slowo)
    
    if not analizy:
        return None, None, None
    
    for item in analizy:
        # wyodrębnienie base i tags z item[2]
        base = None
        tags = None
        if len(item) >= 3 and isinstance(item[2], tuple):
            base = item[2][0]
            tags = item[2][2]
        elif len(item) >= 3 and isinstance(item[2], str):
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
        
        if not rodzaj and isinstance(base, str) and base.endswith("a"):
            rodzaj = "woman"
        
        accept = (tags and ("subst" in tags or "adj" in tags)) or bool(dodatkowe)
        
        if accept and przypadek:
            return base, rodzaj, przypadek
    
    return None, None, None

def process_text_tokenized(original, anonymized, allowed_labels):
    """Przetwarzanie tekstu, korzystające z Levenshtein.opcodes"""
    
    orig_tokens = tokenize_keep_delimiters(original)
    anon_tokens = tokenize_keep_delimiters(anonymized)
    
    ops = Levenshtein.opcodes(anon_tokens, orig_tokens)
    output = []
    
    cleanup_re = re.compile(r'[.,;:(){}\[\]\n]+')
    
    for tag, i1, i2, j1, j2 in ops:
        anon_chunk = anon_tokens[i1:i2]
        
        if tag == "equal":
            output.extend(anon_chunk)
        elif tag == "replace":
            for idx, token in enumerate(anon_chunk):
                if not (token.startswith('[') and token.endswith(']')):
                    output.append(token)
                    continue
                
                label_name = token[1:-1]
                if label_name not in allowed_labels:
                    output.append(token)
                    continue
                
                orig_idx = j1 + idx
                if orig_idx >= len(orig_tokens):
                    output.append(token)
                    continue
                
                # Logika analizy gramatycznej
                
                if label_name == "city":
                    city_tokens = []
                    for t_idx in range(orig_idx, len(orig_tokens)):
                        t = cleanup_re.sub('', orig_tokens[t_idx])
                        if t and t[0].isupper():
                            city_tokens.append(t)
                        else:
                            break
                    
                    _, przypadek = analizuj_slowo_city(city_tokens)
                    tag_new = f"[{label_name}][{przypadek}]" if przypadek else f"[{label_name}]"
                    output.append(tag_new)
                
                elif label_name == "sex":
                    kand = cleanup_re.sub('', orig_tokens[orig_idx])
                    _, przypadek = analizuj_slowo_sex([kand])
                    tag_new = f"[{label_name}][{przypadek}]" if przypadek else f"[{label_name}]"
                    output.append(tag_new)
                
                else:
                    kand = cleanup_re.sub('', orig_tokens[orig_idx])
                    base, rodzaj, przypadek = analizuj_slowo(kand, label_name)
                    
                    if base and rodzaj and przypadek:
                        tag_new = f"[{label_name}][{rodzaj}][{przypadek}]"
                    else:
                        tag_new = token 
                    output.append(tag_new)
        
        elif tag == "delete":
            output.extend(anon_chunk)

    return "".join(output)

# multiprocessing
def split_text_into_chunks(orig_text, anon_text):
    """Dzieli teksty na fragmenty (linie) dla przetwarzania równoległego."""
    orig_lines = orig_text.splitlines(keepends=True) 
    anon_lines = anon_text.splitlines(keepends=True)
    
    # tworzymy listę par (oryginalna linia, anonimizowana linia)
    chunks = []
    min_len = min(len(orig_lines), len(anon_lines))
    
    for i in range(min_len):
        chunks.append((orig_lines[i], anon_lines[i]))
        
    return chunks

def process_chunk(chunk):
    """Funkcja do wykonania w każdym procesie."""
    # inicjalizacja Morfeusza i cache'a nastąpi wewnątrz tego procesu przy pierwszym wywołaniu analyse_with_cache
    
    # chunk to para (original_tekst_fragment, anon_tekst_fragment)
    orig_fragment, anon_fragment = chunk
    
    # wykonujemy logikę przetwarzania na fragmencie
    result = process_text_tokenized(orig_fragment, anon_fragment, KEEP_LABELS)
    
    # zwracamy wynik i rozmiar cache'a (dla statystyk)
    _, cache = get_morfeusz_objects()
    return result, len(cache)

def read_file(filepath):
    """Odczytuje zawartość pliku"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error("Brak pliku: %s", filepath)
        return None

def save_file(filepath, content):
    """Zapisuje zawartość do pliku."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("Zapisano wynik do: %s", filepath)


if __name__ == "__main__":
    # wszystkie dostępnych rdzeni minus jeden (lub min. 1) w ruchu.
    NUM_PROCESSES = max(1, os.cpu_count() - 1) 
    
    start = time.perf_counter()
    orig = read_file(FILE_ORIGINAL)
    anon = read_file(FILE_ANONYMIZED)

    if orig and anon:
        print("\nStart of multiple parallel")
        print(f"Używanie {NUM_PROCESSES} procesów...")
        
        # fragmenty tekstów
        chunks = split_text_into_chunks(orig, anon)
        
        # równoległe przetwarzanie w puli procesów
        try:
            with multiprocessing.Pool(NUM_PROCESSES) as pool:
                # pool.map uruchamia process_chunk dla każdego elementu w chunks
                results_with_cache_size = pool.map(process_chunk, chunks)
        except Exception as e:
            logger.critical(f"Krytyczny błąd w puli procesów: {e}")
            results_with_cache_size = []
            
        # scalenie 
        if results_with_cache_size:
            results = [res[0] for res in results_with_cache_size]
            cache_sizes = [res[1] for res in results_with_cache_size]
            
            # sumujemy rozmiary cache'ów, aby uzyskać sumaryczny wskaźnik pracy
            total_cache_size = sum(cache_sizes) 
            result = "".join(results)
            
            # zapis do pliku
            save_file(FILE_OUTPUT, result)
            
            end = time.perf_counter()
            
            print(f"Przetworzono w {end - start:.3f} sekund")
            print(f"Sumaryczny Cache Morfeusz (wszystkie procesy): {total_cache_size} wpisów")
            print(f"Wynik zapisano do: {FILE_OUTPUT}")
        else:
            print("Błąd przetwarzania: nie uzyskano wyników.")
            end = time.perf_counter()

    else:
        print("\nbłąd plików")
        print("Nie można przetworzyć tekstu: brak jednego lub obu plików źródłowych.")
        
