"""Human-readable messages for model/stream failures."""

from __future__ import annotations


def user_facing_stream_error(exc: Exception | str) -> str:
    text = str(exc).strip() or (type(exc).__name__ if isinstance(exc, Exception) else "Error")
    lower = text.lower()
    name = type(exc).__name__ if isinstance(exc, Exception) else ""

    if "overloaded" in lower or "overloaded_error" in lower:
        return (
            "Claude model service is overloaded. "
            "Please retry later; if it persists, confirm the model is deployed on Azure with enough capacity."
        )
    if "rate_limit" in lower or "rate limit" in lower:
        return "Rate limit exceeded. Please retry later."
    if "internal server error" in lower or "api_error" in lower:
        return (
            "Claude model service error (500). "
            "Confirm CLAUDE_AZURE_FOUNDRY_MODEL matches your Azure deployment name and retry later."
        )
    if "AuthenticationError" in name or "401" in text or "Unauthorized" in text:
        return (
            "Claude authentication failed (401). Check CLAUDE_AZURE_API_KEY and "
            "CLAUDE_AZURE_FOUNDRY_ENDPOINT in backend/.env match your Azure resource region."
        )
    if "mcp server" in lower and "failed to initialize" in lower:
        if "cancel scope" in lower or "cancelled" in lower:
            return (
                "MCP connection failed (request timed out or stream was interrupted). "
                "Confirm Vercel has MCP_SECRETS_KEY set (same key used during sync) and re-run "
                "python scripts/sync_agent_profiles.py against the production DATABASE_URL. "
                "If it still fails, check Vercel backend logs for the MCP server name and HTTP error."
            )
        return (
            "MCP initialization failed. Confirm Vercel has MCP_SECRETS_KEY configured, "
            "hybrid-search / zhipu MCP credentials are valid, and agent profiles are synced to production."
        )
    return text
