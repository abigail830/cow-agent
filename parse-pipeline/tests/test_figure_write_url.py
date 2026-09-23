from parse_pipeline.schemas.storage import WriteTarget
from parse_pipeline.storage.io import _figure_write_url


def test_figure_write_url_http_uses_bare_figure_id() -> None:
    target = WriteTarget(
        url="https://example.test/internal/parse/v1/files/abc/artifacts/content_md",
        method="PUT",
    )
    url = _figure_write_url(target, "f1", "jpeg")
    assert url == "https://example.test/internal/parse/v1/files/abc/figures/f1"
    assert not url.endswith(".jpeg")
