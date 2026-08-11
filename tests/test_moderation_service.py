from app.config import get_settings
from app.services.moderation_service import contains_banned_words


def test_contains_banned_words_detects_banned_word() -> None:
    assert contains_banned_words("this is a scam") is True


def test_contains_banned_words_allows_clean_message() -> None:
    assert contains_banned_words("hey, want to grab coffee?") is False


def test_contains_banned_words_reads_list_from_config(monkeypatch) -> None:
    monkeypatch.setenv("MODERATION_BANNED_WORDS", "banana")
    get_settings.cache_clear()
    try:
        assert contains_banned_words("this is a scam") is False
        assert contains_banned_words("i like banana") is True
    finally:
        get_settings.cache_clear()
