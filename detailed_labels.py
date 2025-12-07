import re
import time
import logging
from rapidfuzz.distance import Levenshtein
import morfeusz2

# ================= LOGOWANIE =================
logger = logging.getLogger("detailed_labels")
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler("detailed_labels.log", encoding="utf8")
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

logger.info("=== START DETAILED LABELS ===")

# ================= KONFIGURACJA =================
FILE_ORIGINAL = "data/single_orig.txt"
FILE_ANONYMIZED = "data/single_anon.txt"
FILE_OUTPUT = "wyniki.txt"

KEEP_LABELS = {"name", "surname", "city", "sex", "relative", "job-title"}
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

def extract_przypadek(tag_string):
    # tag_string np. 'subst:sg:nom.acc:m3'
    parts = tag_string.split(":")
    for p in parts:
        for sub in p.split("."):
            if sub in PRZYPADKI:
                return PRZYPADKI[sub]
    return None

def analizuj_slowo_city(tokens):
    kand_full = " ".join(tokens)
    for tok in tokens:
        analizy = morfeusz.analyse(tok)
        for item in analizy:
            base = item[2][0] if isinstance(item[2], tuple) else item[2]
            tags = item[2][2] if isinstance(item[2], tuple) else ""
            dodatkowe = item[3] if len(item) > 3 else []
            if "nazwa_geograficzna" in dodatkowe or "subst" in tags:
                przypadek = extract_przypadek(tags)
                if przypadek:
                    logger.info("Analiza miasta: %r -> przypadek=%r", kand_full, przypadek)
                    return kand_full, przypadek
    return kand_full, None

def analizuj_slowo_sex(tokens):
    # tokens = lista tokenów (najczęściej 1 token: ["kobieta"])
    kand_full = " ".join(tokens)
    analizy = morfeusz.analyse(kand_full)
    for idx, item in enumerate(analizy):
        logger.debug("  RAW_SEX[%d]: %r", idx, item)
        base = item[2][0] if isinstance(item[2], tuple) else item[2]
        tags = item[2][2] if isinstance(item[2], tuple) else ""
        dodatkowe = item[3] if len(item) > 3 else []
        if "subst" in tags:  # rzeczownik
            przypadek = extract_przypadek(tags)
            if przypadek:
                logger.info("Analiza płci zakończona: %r -> przypadek=%r", kand_full, przypadek)
                return kand_full, przypadek
    logger.warning("Nie znaleziono wiarygodnej analizy dla płci: %r", kand_full)
    return kand_full, None


def analizuj_slowo(slowo, label):
    if label == "city":
        # dla city używamy analizuj_slowo_city
        return analizuj_slowo_city([slowo]) + (None,)  # dodaj trzeci element dla zgodności
    if label == "sex":
        return analizuj_slowo_sex([slowo]) + (None,)
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
        if label in ["name", "surname", "relative", "job-title"]:
            if any(t in tag_parts for t in ["m1","m2","m3","m","subst:m"]):
                rodzaj = "man"
            elif any(t in tag_parts for t in ["f","subst:f"]):
                rodzaj = "woman"
            else:
                if base.endswith("a"):
                    rodzaj = "woman"

        logger.debug("  Wybrane: base=%r, rodzaj=%r, przypadek=%r", base, rodzaj, przypadek)
        if przypadek:
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
                        # obsługa wielowyrazowych nazw dla city
                        if label_name == "city":
                            city_tokens = []
                            for t_idx in range(j1 + idx, len(orig_tokens)):
                                t = orig_tokens[t_idx].rstrip(".,;:()[]{}")
                                if t.istitle():  # wielka litera
                                    city_tokens.append(t)
                                else:
                                    break
                            base, przypadek = analizuj_slowo_city(city_tokens)
                            if base and przypadek:
                                tag_new = f"[city][{przypadek}]"
                            else:
                                tag_new = "[city]"
                            output.append(tag_new)
                            logger.info("Zastąpiono %r -> %r (city: %r)", token, tag_new, " ".join(city_tokens))

                        elif label_name == "sex":
                            kand = orig_tokens[j1 + idx].rstrip(".,;:()[]{}")
                            base, przypadek = analizuj_slowo_sex([kand])
                            if base and przypadek:
                                tag_new = f"[sex][{przypadek}]"
                            else:
                                tag_new = "[sex]"
                            output.append(tag_new)
                            logger.info("Zastąpiono %r -> %r (sex: %r)", token, tag_new, kand)

                        else:
                            # name, surname
                            kand = orig_tokens[j1 + idx].rstrip(".,;:()[]{}")
                            base, rodzaj, przypadek = analizuj_slowo(kand, label_name)
                            if base:
                                tag_new = f"[{label_name}][{rodzaj}][{przypadek}]" if rodzaj and przypadek else f"[{label_name}]"
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

if __name__ == "__main__":
    start = time.perf_counter()
    orig = read_file(FILE_ORIGINAL)
    anon = read_file(FILE_ANONYMIZED)

    if orig and anon:
        print("\n================= TEKST ORYGINALNY =================")
        print(orig)

        # --- GENEROWANIE LABELI ---
        result = process_text_tokenized(orig, anon, KEEP_LABELS)
        save_file(FILE_OUTPUT, result)

        print("\n================= TEKST PO DODANIU LABELI =================")
        print(result)

        # --- GENEROWANIE DANYCH SYNTETYCZNYCH ---
        from synthetic_generator import generate_synthetic_output
        synthetic = generate_synthetic_output(result)
        save_file("wyniki_syntetyczne.txt", synthetic)

        print("\n================= TEKST SYNTETYCZNY =================")
        print(synthetic)

        print("\n✔ Wygenerowano syntetyczny tekst -> wyniki_syntetyczne.txt")

    end = time.perf_counter()
    logger.info("Czas wykonania: %.4f sekundy", end - start)
    logger.info("=== KONIEC ===")

