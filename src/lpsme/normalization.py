from __future__ import annotations

import re
import unicodedata

_LEGAL_FORMS = {"sarl", "spa", "eurl", "snc", "scs", "sca", "epic", "epe", "groupe", "group", "algerie", "algeria", "dz", "ets", "etablissement", "societe", "ste"}

def normalize_arabic_text(text: str) -> str:
    cleaned = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    cleaned = re.sub(r"[إأآا]", "ا", cleaned)
    cleaned = cleaned.replace("ى", "ي").replace("ؤ", "ء").replace("ئ", "ء").replace("ة", "ه")
    return " ".join(cleaned.split())

def normalize_organization_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    if not text.strip():
        return normalize_arabic_text(name)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [t for t in text.split() if t not in _LEGAL_FORMS]
    return " ".join(tokens) if tokens else " ".join(text.split())

def normalize_registry_code(code: str | None) -> str | None:
    if not code:
        return None
    cleaned = re.sub(r"[^A-Z0-9]", "", code.upper())
    return cleaned if cleaned else None
