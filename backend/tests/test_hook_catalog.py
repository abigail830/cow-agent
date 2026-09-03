from unittest.mock import MagicMock
from uuid import uuid4

from app.middleware.proposal_persist import ProposalPersistMiddleware
from app.platform.hook_catalog import build_hook_middleware
from app.platform.hook_context import HookBuildContext


def test_proposal_persist_hook_builds_middleware():
    ctx = HookBuildContext(
        db=MagicMock(),
        chat_id=uuid4(),
        session_store=MagicMock(),
    )
    built = build_hook_middleware("proposal_persist", {}, ctx)
    assert isinstance(built, ProposalPersistMiddleware)


def test_proposal_persist_skipped_without_session_store():
    ctx = HookBuildContext(db=MagicMock(), chat_id=uuid4(), session_store=None)
    assert build_hook_middleware("proposal_persist", {}, ctx) is None
