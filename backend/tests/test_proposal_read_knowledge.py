import pytest

from app.tools.proposal import _validate_read_path


@pytest.mark.parametrize(
    "path",
    [
        "peripheral/required-docs/harneys/Individual KYC Requirements.md",
        "peripheral/credentials/AU/audit-clients.csv",
        "templates/au-advisory/template.yaml",
        "templates/au-advisory/blocks/terms-au-advisory.md",
        "templates/harneys-bvi/blocks/terms-bvi.md",
    ],
)
def test_validate_read_path_allowed(path: str) -> None:
    _validate_read_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "knowledge-index.yaml",
        "../peripheral/x.md",
        "templates/foo.md",
        "templates/au-advisory/proposal.md",
    ],
)
def test_validate_read_path_rejected(path: str) -> None:
    with pytest.raises(ValueError):
        _validate_read_path(path)
