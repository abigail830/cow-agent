from app.platform.passwords import hash_password, verify_password


def test_hash_and_verify_roundtrip():
    digest = hash_password("Pilot-123")
    assert digest.startswith("$2")
    assert verify_password("Pilot-123", digest)
    assert not verify_password("wrong", digest)


def test_verify_rejects_empty():
    assert not verify_password("", None)
    assert not verify_password("x", None)
