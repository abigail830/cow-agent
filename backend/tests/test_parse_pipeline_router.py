from app.platform.attachments.kinds import AttachmentKind
from app.platform.docstore.gate import assert_parse_ready
from app.platform.parse_pipeline.router import PipelineRoute, resolve_pipeline
from app.platform.parse_pipeline.webhook import verify_webhook_signature


def test_resolve_pipeline_text():
    r = resolve_pipeline(AttachmentKind.TEXT)
    assert r.action == "parse"
    assert r.pipeline_id == "text_standard"


def test_resolve_pipeline_image_skip():
    r = resolve_pipeline(AttachmentKind.IMAGE)
    assert r.action == PipelineRoute.SKIP.value


def test_resolve_pipeline_office_reject():
    r = resolve_pipeline(AttachmentKind.OFFICE)
    assert r.action == PipelineRoute.REJECT.value


def test_webhook_signature_roundtrip():
    import hashlib
    import hmac
    import time

    secret = "whsec_test"
    body = b'{"job_id":"job_1","event":"stage.updated"}'
    ts = str(int(time.time()))
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(
        secret=secret,
        timestamp=ts,
        body=body,
        signature_header=f"v1={digest}",
    )


class _Row:
    def __init__(self, filename: str, parse_status: str) -> None:
        self.filename = filename
        self.parse_status = parse_status


def test_assert_parse_ready_blocks_pending():
    import pytest

    with pytest.raises(ValueError, match="still parsing"):
        assert_parse_ready([_Row("notes.md", "pending")])
