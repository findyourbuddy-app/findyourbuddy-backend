from app.services.moderation_service import contains_banned_words


def test_contains_banned_words_detects_banned_word() -> None:
    assert contains_banned_words("this is a scam") is True


def test_contains_banned_words_allows_clean_message() -> None:
    assert contains_banned_words("hey, want to grab coffee?") is False
