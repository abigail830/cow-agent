from __future__ import annotations


def decode_text_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "gb18030", "latin-1"):
        try:
            return data.decode(encoding).lstrip("\ufeff")
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace").lstrip("\ufeff")


def extract_text_bytes(data: bytes) -> tuple[str, list[str]]:
    text = decode_text_bytes(data)
    warnings: list[str] = []
    if not text.strip():
        warnings.append("empty document")
        return "[empty document]", warnings
    return text, warnings
