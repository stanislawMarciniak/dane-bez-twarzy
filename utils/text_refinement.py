import re
import time
from rapidfuzz.distance import Levenshtein

# --- KONFIGURACJA ---
FILE_ORIGINAL = "data/orig.txt"
FILE_ANONYMIZED = "data/anonimized.txt"
FILE_OUTPUT = "output_final1.txt"

# Lista etykiet, które mają zostać (zanonimizowane)
KEEP_LABELS = {
    "name", "surname", "age", "date-of-birth", "date", "sex", "religion",
    "political-view", "ethnicity", "sexual-orientation", "health", "relative",
    "city", "address",
    "phone", "document-number",
    "company", "school-name", "job-title",
    "bank-account", "credit-card-number",
    "credit-card-number",
    "username", "secret"
}

# --- SUPER SZYBKI PREKOMPILOWANY REGEX ---
TOKEN_RE = re.compile(
    r'(\[[a-zA-Z0-9-]+\])|(\w+)|(\s+)|([^\w\s\[\]]+)'
)

def tokenize_keep_delimiters(text):
    return [m.group(0) for m in TOKEN_RE.finditer(text)]


def process_text_tokenized(original, anonymized, allowed_labels):
    # 1. Szybka tokenizacja
    orig_tokens = tokenize_keep_delimiters(original)
    anon_tokens = tokenize_keep_delimiters(anonymized)

    # 2. RapidFuzz – generowanie opcodów (SUPER SZYBKIE)
    ops = Levenshtein.opcodes(anon_tokens, orig_tokens)

    output = []

    for tag, i1, i2, j1, j2 in ops:

        # Pobranie fragmentów
        anon_chunk = anon_tokens[i1:i2]
        orig_chunk = orig_tokens[j1:j2]

        if tag == "equal":
            output.extend(anon_chunk)

        elif tag == "replace":
            # Zastępuj zawsze jeśli jest [phone] lub forbidden
            has_phone = any("[phone]" in t for t in anon_chunk)
            contains_forbidden = any(
                t.startswith("[") and t.endswith("]") and t[1:-1] not in allowed_labels
                for t in anon_chunk
            )
            if has_phone or contains_forbidden:
                output.extend(orig_chunk)
            else:
                output.extend(anon_chunk)


        elif tag == "delete":
            # To jest w anon, ale nie ma w oryginale → przepisujemy
            output.extend(anon_chunk)

        elif tag == "insert":
            # Ignorujemy — tak samo jak w twojej wersji
            pass

    return "".join(output)


def read_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Brak pliku: {filepath}")
        return None


def save_file(filepath, content):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Zapisano wynik: {filepath}")


# --- URUCHOMIENIE ---
if __name__ == "__main__":
    start = time.perf_counter()
    print("Wczytywanie plików...")

    orig = read_file(FILE_ORIGINAL)
    anon = read_file(FILE_ANONYMIZED)

    if orig and anon:
        print("Przetwarzanie (RapidFuzz Tokenized Diff)...")
        result = process_text_tokenized(orig, anon, KEEP_LABELS)
        save_file(FILE_OUTPUT, result)

    end = time.perf_counter()
    print(f"Czas wykonania: {end - start:.4f} sekundy")
