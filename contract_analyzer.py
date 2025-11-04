"""
contract_analyzer.py

Simple rule-based contract analyzer:
- input: path to .txt or .docx file
- output: dictionary with extracted parties, dates, money, obligation sentences, termination sentences, and a short keyword-based summary
"""

import re
import sys
from pathlib import Path
from collections import Counter
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

try:
    from docx import Document
except Exception:
    Document = None

# Ensure NLTK resources are present
nltk.download("punkt", quiet=True)
nltk.download("stopwords", quiet=True)

STOPWORDS = set(stopwords.words("english"))

# Regex patterns
DATE_PAT = r'(\b(?:\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|March|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\b\s+\d{2,4})|' \
           r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b|' \
           r'\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2})\b|' \
           r'\b(?:effective\s+as\s+of\s+[A-Za-z0-9 ,]+)\b|' \
           r'\b(?:effective\s+date\s*[:\-]?\s*[A-Za-z0-9 ,]+)\b)'

MONEY_PAT = r'(\b₹\s?\d[\d,]*(?:\.\d+)?\b|\bRs\.?\s?\d[\d,]*(?:\.\d+)?\b|\bUSD\s?\d[\d,]*(?:\.\d+)?\b|\bEUR\s?\d[\d,]*(?:\.\d+)?\b|\b\d[\d,]*(?:\.\d+)?\s?(?:dollars|rupees|INR|USD|EUR)\b)'

# obligation keywords
OBL_KEYWORDS = ['shall', 'must', 'agree', 'agrees', 'obligat', 'responsib', 'undertake', 'require', 'warrant', 'covenant', 'will']

TERMINATION_KEYWORDS = ['terminate', 'termination', 'expire', 'expiry', 'notice period', 'notice', 'breach', 'cancel', 'cancelled']

PARTY_PATTERNS = [
    # “This Agreement is entered into between <Party A> and <Party B>”
    r'\bthis\s+agreement\s+(?:is\s+)?(?:made|entered\s+into)\s+(?:on\s+[A-Za-z0-9 ,]+)?\s*(?:between|by and between)\s+(.+?)\s+and\s+(.+?)\b',
    # “between <Party A> (“Party A”) and <Party B> (“Party B”)”
    r'\bbetween\s+(.+?)\s+\(|between\s+(.+?)\s+and\s+(.+?)\b',
    # “by and between <Party A> and <Party B>”
    r'\bby\s+and\s+between\s+(.+?)\s+and\s+(.+?)\b',
]

def read_docx(path: Path) -> str:
    if Document is None:
        raise RuntimeError("python-docx not installed. Install via pip install python-docx")
    doc = Document(path)
    full = []
    for p in doc.paragraphs:
        full.append(p.text)
    return '\n'.join(full)

def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='ignore')

def load_file(path_str: str) -> str:
    p = Path(path_str)
    if not p.exists():
        raise FileNotFoundError(f"{path_str} not found")
    if p.suffix.lower() in ['.docx']:
        return read_docx(p)
    else:
        return read_text(p)

def extract_dates(text: str):
    matches = re.findall(DATE_PAT, text, flags=re.IGNORECASE)
    # regex returns tuples because of groups; flatten
    flat = [m for grp in matches for m in grp.split('\n') if m] if matches and isinstance(matches[0], str) else []
    # simpler fallback: also look for words like "on 1 January 2024" by capturing "on ... 20xx"
    fallback = re.findall(r'\bon\s+[A-Za-z0-9 ,]+\s+\d{4}\b', text, flags=re.IGNORECASE)
    dates = list({m.strip() for m in flat + fallback})
    return dates[:10]

def extract_money(text: str):
    matches = re.findall(MONEY_PAT, text, flags=re.IGNORECASE)
    cleaned = [m.strip() for m in matches]
    return list(dict.fromkeys(cleaned))[:10]

def extract_parties(text: str):
    # try patterns
    text_clean = ' '.join(text.split())  # one-line
    found = []
    for pat in PARTY_PATTERNS:
        m = re.search(pat, text_clean, flags=re.IGNORECASE)
        if m:
            groups = [g for g in m.groups() if g]
            # return top 2 meaningful strings
            for g in groups:
                g_clean = re.sub(r'\s{2,}', ' ', g).strip()
                # remove parenthetical short forms
                g_clean = re.sub(r'\([^)]+\)', '', g_clean).strip()
                if g_clean and len(g_clean) > 2:
                    found.append(g_clean)
            if found:
                break
    # fallback: look for "Between: <X>" or "Party A:" patterns
    if not found:
        # look for uppercase phrases in top part of the doc
        head = text.splitlines()[:40]
        caps = re.findall(r'\b([A-Z][A-Z0-9 &(),\.-]{3,})\b', '\n'.join(head))
        # choose top 2 unique
        uniq = []
        for c in caps:
            c_s = c.strip()
            if c_s.lower() not in STOPWORDS and len(c_s) > 3 and c_s not in uniq:
                uniq.append(c_s)
            if len(uniq) >= 2:
                break
        found = uniq
    return found[:2]

def find_sentences_by_keywords(text: str, keywords):
    sents = sent_tokenize(text)
    results = []
    for s in sents:
        low = s.lower()
        for kw in keywords:
            if kw in low:
                results.append(s.strip())
                break
    return results

def keyword_summary(text: str, top_n=10):
    words = [w.lower() for w in word_tokenize(text) if w.isalpha() and w.lower() not in STOPWORDS]
    freqs = Counter(words)
    common = [w for w, _ in freqs.most_common(top_n)]
    return common

def analyze_contract(path: str):
    text = load_file(path)
    parties = extract_parties(text)
    dates = extract_dates(text)
    money = extract_money(text)
    obligations = find_sentences_by_keywords(text, OBL_KEYWORDS)
    termination = find_sentences_by_keywords(text, TERMINATION_KEYWORDS)
    keywords = keyword_summary(text, top_n=12)

    # short summary: first 4 sentences
    sents = sent_tokenize(text)
    short_summary = ' '.join(sents[:4]) if sents else ''

    result = {
        "parties": parties,
        "dates_found": dates,
        "money_values": money,
        "obligation_sentences": obligations[:10],
        "termination_sentences": termination[:8],
        "top_keywords": keywords,
        "short_summary": short_summary
    }
    return result

def pretty_print(result):
    print("\n--- Contract Analysis ---\n")
    print("Parties (guessed):")
    for p in result["parties"]:
        print(" -", p)
    print("\nImportant Dates (guessed):")
    for d in result["dates_found"]:
        print(" -", d)
    print("\nMoney / Amounts:")
    for m in result["money_values"]:
        print(" -", m)
    print("\nObligation sentences (contain shall/must/agree/...):")
    for s in result["obligation_sentences"]:
        print(" -", s)
    print("\nTermination / Notice sentences:")
    for s in result["termination_sentences"]:
        print(" -", s)
    print("\nTop keywords (quick):", ', '.join(result["top_keywords"]))
    print("\nShort extractive summary (first sentences):\n", result["short_summary"])
    print("\n-------------------------\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python contract_analyzer.py path/to/contract.txt")
        sys.exit(1)
    path = sys.argv[1]
    res = analyze_contract(path)
    pretty_print(res)

    # Save output to a file (for report)
    output_file = "report_output.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("--- Contract Analysis ---\n\n")
        f.write("Parties (guessed):\n")
        for p in res["parties"]:
            f.write(f" - {p}\n")
        f.write("\nImportant Dates (guessed):\n")
        for d in res["dates_found"]:
            f.write(f" - {d}\n")
        f.write("\nMoney / Amounts:\n")
        for m in res["money_values"]:
            f.write(f" - {m}\n")
        f.write("\nObligation sentences:\n")
        for s in res["obligation_sentences"]:
            f.write(f" - {s}\n")
        f.write("\nTermination / Notice sentences:\n")
        for s in res["termination_sentences"]:
            f.write(f" - {s}\n")
        f.write("\nTop keywords:\n")
        f.write(", ".join(res["top_keywords"]))
        f.write("\n\nShort extractive summary:\n")
        f.write(res["short_summary"])
        f.write("\n\n-------------------------\n")

    print(f"\nAnalysis saved to {output_file}")

