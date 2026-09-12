from app.platform.integrations.oauth.pkce import (
    consume_oauth_state,
    create_oauth_state,
    generate_code_challenge,
    generate_code_verifier,
)


def test_oauth_state_roundtrip():
    signing_key = "test-signing-key"
    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)
    assert challenge
    state = create_oauth_state(
        user_id="00000000-0000-0000-0000-000000000001",
        provider="notion",
        code_verifier=verifier,
        signing_key=signing_key,
    )
    pending = consume_oauth_state(state, signing_key=signing_key)
    assert pending is not None
    assert pending.user_id == "00000000-0000-0000-0000-000000000001"
    assert pending.provider == "notion"
    assert pending.code_verifier == verifier


def test_oauth_state_rejects_tampered_signature():
    signing_key = "test-signing-key"
    verifier = generate_code_verifier()
    state = create_oauth_state(
        user_id="00000000-0000-0000-0000-000000000001",
        provider="notion",
        code_verifier=verifier,
        signing_key=signing_key,
    )
    tampered = state[:-1] + ("a" if state[-1] != "a" else "b")
    assert consume_oauth_state(tampered, signing_key=signing_key) is None
