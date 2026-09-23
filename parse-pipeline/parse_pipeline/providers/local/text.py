from __future__ import annotations


def decode_text_bytes(data: bytes) -> str:
    encodings = ["utf-8-sig", "utf-8"]
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings.append("utf-16")
    encodings.extend(["gb18030", "latin-1"])
    for encoding in encodings:
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
