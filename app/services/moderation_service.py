from app.config import get_settings


def _banned_words() -> frozenset[str]:
    return frozenset(word.strip().lower() for word in get_settings().moderation_banned_words.split(","))


def contains_banned_words(content: str) -> bool:
    words = set(content.lower().split())
    return not words.isdisjoint(_banned_words())
