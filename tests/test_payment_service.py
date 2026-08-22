from app.services.payment_service import claim_payment_callback


def test_claim_payment_callback_first_call_returns_true(db_session) -> None:
    result = claim_payment_callback(db_session, "token-abc", "subscription", user_id=1)
    assert result is True


def test_claim_payment_callback_duplicate_returns_false(db_session) -> None:
    claim_payment_callback(db_session, "token-dup", "subscription", user_id=1)
    result = claim_payment_callback(db_session, "token-dup", "subscription", user_id=1)
    assert result is False


def test_claim_payment_callback_different_tokens_both_succeed(db_session) -> None:
    r1 = claim_payment_callback(db_session, "token-1", "purchase", user_id=1)
    r2 = claim_payment_callback(db_session, "token-2", "purchase", user_id=1)
    assert r1 is True
    assert r2 is True


def test_claim_payment_callback_same_token_different_purpose_is_still_duplicate(db_session) -> None:
    claim_payment_callback(db_session, "token-shared", "subscription", user_id=1)
    # Same token, different purpose — still a duplicate (token is the unique key)
    result = claim_payment_callback(db_session, "token-shared", "purchase", user_id=1)
    assert result is False


def test_claim_payment_callback_same_token_different_user_is_duplicate(db_session) -> None:
    claim_payment_callback(db_session, "token-multi", "subscription", user_id=1)
    result = claim_payment_callback(db_session, "token-multi", "subscription", user_id=2)
    assert result is False


def test_claim_payment_callback_rollback_does_not_corrupt_session(db_session) -> None:
    """After a duplicate claim (which triggers rollback), the session must
    still be usable for subsequent DB operations."""
    claim_payment_callback(db_session, "token-rb", "subscription", user_id=1)
    claim_payment_callback(db_session, "token-rb", "subscription", user_id=1)  # duplicate → rollback
    # Session should still work
    result = claim_payment_callback(db_session, "token-rb-2", "subscription", user_id=1)
    assert result is True
