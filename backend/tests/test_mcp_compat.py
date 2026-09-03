"""Tests for MCP 1.x / 2.x compatibility shim."""

from mcp import types


def test_initialize_result_protocol_version_compat(monkeypatch):
    from app.platform import mcp_compat

    monkeypatch.setattr(mcp_compat, "_applied", False)
    mcp_compat.apply_mcp_compat_patches()

    if hasattr(types.InitializeResult, "protocolVersion"):
        result = types.InitializeResult(
            protocolVersion="2025-11-25",
            capabilities={},
            serverInfo={"name": "test", "version": "1.0"},
        )
        assert result.protocolVersion == "2025-11-25"
    elif hasattr(types.InitializeResult, "protocol_version"):
        result = types.InitializeResult(
            protocol_version="2025-11-25",
            capabilities={},
            server_info={"name": "test", "version": "1.0"},
        )
        assert result.protocolVersion == "2025-11-25"
