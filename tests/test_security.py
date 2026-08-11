from app.core.security import decode_access_token


def test_decode_access_token_returns_none_for_invalid_token() -> None:
    assert decode_access_token("not-a-real-token") is None
