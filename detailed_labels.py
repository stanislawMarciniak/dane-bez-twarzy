import re
import time
import logging
from rapidfuzz.distance import Levenshtein
import morfeusz2

# ================= LOGOWANIE =================
logger = logging.getLogger("detailed_labels")
logger.setLevel(logging.DEBUG)

# Plik logów
fh = logging.FileHandler("detailed_labels.log", encoding="utf8")
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)

# Konsola (opcjonalnie)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

logger.info("=== START DETAILED LABELS ===")

# ================= KONFIGURACJA =================
FILE_ORIGINAL = "data/single_orig.txt"
FILE_ANONYMIZED = "data/single_anon.txt"
FILE_OUTPUT = "wyniki.txt"

# Etykiety, które analizujemy
KEEP_LABELS = {"name", "surname", "city"}
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

morfeusz = morfeusz2.Morfeusz()
logger.info("Uruchomiono Morfeusz2")

# ================= FUNKCJE =================
def tokenize_keep_delimiters(text):
    return [m.group(0) for m in TOKEN_RE.finditer(text)]

def analizuj_slowo(slowo, label):
    logger.debug("Analiza słowa: %r, etykieta: %r", slowo, label)
    analizy = morfeusz.analyse(slowo)
    logger.debug("Morfeusz zwrócił %d analiz dla słowa %r", len(analizy), slowo)

    for idx, item in enumerate(analizy):
        logger.debug("  RAW[%d]: %r", idx, item)
        parts = list(item[2]) if isinstance(item[2], tuple) else list(item[2:])
        base = next((p for p in parts if isinstance(p, str)), None)
        tags = next((p for p in reversed(parts) if isinstance(p, str) and ":" in p), None)
        if not base or not tags:
            continue

        tag_parts = tags.split(":")
        przypadek = next((p for p in tag_parts if p in PRZYPADKI), None)

        rodzaj = None
        if label in ["name", "surname"]:
            if any(t in tag_parts for t in ["m1","m2","m3","m","subst:m"]):
                rodzaj = "męski"
            elif any(t in tag_parts for t in ["f","subst:f"]):
                rodzaj = "żeński"
            else:
                if base.endswith("a"):
                    rodzaj = "żeński"

        logger.debug("  Wybrane: base=%r, rodzaj=%r, przypadek=%r", base, rodzaj, przypadek)
        if przypadek:
            if label in ["city"]:
                # tylko przypadek dla city
                logger.info("Analiza zakończona: %r -> przypadek=%r", slowo, PRZYPADKI[przypadek])
                return base, None, PRZYPADKI[przypadek]
            else:
                logger.info("Analiza zakończona: %r -> base=%r, rodzaj=%r, przypadek=%r", slowo, base, rodzaj, PRZYPADKI[przypadek])
                return base, rodzaj, PRZYPADKI[przypadek]

    logger.warning("Nie znaleziono wiarygodnej analizy dla słowa: %r", slowo)
    return None, None, None

def process_text_tokenized(original, anonymized, allowed_labels):
    orig_tokens = tokenize_keep_delimiters(original)
    anon_tokens = tokenize_keep_delimiters(anonymized)
    ops = Levenshtein.opcodes(anon_tokens, orig_tokens)
    output = []

    for tag, i1, i2, j1, j2 in ops:
        anon_chunk = anon_tokens[i1:i2]
        orig_chunk = orig_tokens[j1:j2]

        if tag == "equal":
            output.extend(anon_chunk)
        elif tag == "replace":
            for idx, token in enumerate(anon_chunk):
                label_name = token[1:-1]
                if label_name in allowed_labels:
                    if idx + j1 < len(orig_tokens):
                        kand = orig_tokens[j1 + idx].rstrip(".,;:()[]{}")
                        base, rodzaj, przypadek = analizuj_slowo(kand, label_name)
                        if base:
                            if label_name == "city":
                                tag_new = f"[{label_name}][{przypadek}]"
                            else:
                                tag_new = f"[{label_name}][{rodzaj}][{przypadek}]" if rodzaj and przypadek else f"[{label_name}][unknown]"
                            output.append(tag_new)
                            logger.info("Zastąpiono %r -> %r", token, tag_new)
                        else:
                            output.append(token)
                            logger.warning("Nie udało się zinterpretować słowa %r dla placeholdera %r", kand, token)
                    else:
                        output.append(token)
                        logger.warning("Brak słowa w pliku oryginalnym dla placeholdera %r", token)
                else:
                    output.extend([token])
        elif tag == "delete":
            output.extend(anon_chunk)
        elif tag == "insert":
            pass
    return "".join(output)

def read_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error("Brak pliku: %s", filepath)
        return None

def save_file(filepath, content):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("Zapisano wynik do: %s", filepath)

# ================= GŁÓWNY BLOK =================
if __name__ == "__main__":
    start = time.perf_counter()
    orig = read_file(FILE_ORIGINAL)
    anon = read_file(FILE_ANONYMIZED)
    if orig and anon:
        result = process_text_tokenized(orig, anon, KEEP_LABELS)
        save_file(FILE_OUTPUT, result)
    end = time.perf_counter()
    logger.info("Czas wykonania: %.4f sekundy", end - start)
    logger.info("=== KONIEC ===")
