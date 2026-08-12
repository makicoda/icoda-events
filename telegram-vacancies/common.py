import re

import config


def load_chats(path):
    chats = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            chats.append(line)
    return chats


def matches_marketing_vacancy(text):
    if not text:
        return None, None
    lowered = text.lower()
    vacancy_hits = [kw for kw in config.VACANCY_KEYWORDS if kw in lowered]
    marketing_hits = [kw for kw in config.MARKETING_KEYWORDS if kw in lowered]
    if vacancy_hits and marketing_hits:
        return vacancy_hits, marketing_hits
    return None, None


def clean_snippet(text, limit=2000):
    snippet = re.sub(r"\s+", " ", text).strip()
    return snippet if len(snippet) <= limit else snippet[:limit] + "…"
