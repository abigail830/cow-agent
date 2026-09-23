from __future__ import annotations

from pydantic import BaseModel, Field


class ReadSpec(BaseModel):
    url: str
    method: str = "GET"
    sha256: str | None = None
    size_bytes: int | None = None
    filename: str | None = None
    content_type: str | None = None


class WriteTarget(BaseModel):
    url: str
    method: str = "PUT"
    content_type: str | None = None


class StorageSpec(BaseModel):
    read: ReadSpec
    write: dict[str, WriteTarget | None] = Field(default_factory=dict)
