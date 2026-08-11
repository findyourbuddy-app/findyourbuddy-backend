_BANNED_WORDS = frozenset({"spam", "scam"})


def contains_banned_words(content: str) -> bool:
    words = set(content.lower().split())
    return not words.isdisjoint(_BANNED_WORDS)
