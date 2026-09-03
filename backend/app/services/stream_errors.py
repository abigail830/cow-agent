"""Human-readable messages for model/stream failures."""

from __future__ import annotations


def user_facing_stream_error(exc: Exception | str) -> str:
    text = str(exc).strip() or (type(exc).__name__ if isinstance(exc, Exception) else "Error")
    lower = text.lower()
    name = type(exc).__name__ if isinstance(exc, Exception) else ""

    if "overloaded" in lower or "overloaded_error" in lower:
        return (
            "Claude 模型服务繁忙（Overloaded）。"
            "请稍后重试；若持续失败，请确认 Azure 资源已部署该模型且有足够容量。"
        )
    if "rate_limit" in lower or "rate limit" in lower:
        return "请求过于频繁，请稍后重试。"
    if "internal server error" in lower or "api_error" in lower:
        return (
            "Claude 模型服务异常（500）。"
            "请确认 CLAUDE_AZURE_FOUNDRY_MODEL 与 Azure 部署名称一致，并稍后重试。"
        )
    if "AuthenticationError" in name or "401" in text or "Unauthorized" in text:
        return (
            "Claude 模型认证失败（401）：请检查 backend/.env 中的 "
            "CLAUDE_AZURE_API_KEY 与 CLAUDE_AZURE_FOUNDRY_ENDPOINT 是否与 Azure 资源区域一致。"
        )
    return text
