"""Tests for Slidev source normalization."""

from __future__ import annotations

from app.slide.source_normalize import normalize_slidev_source


def test_dedents_indented_html_tags() -> None:
    source = """---
theme: default
---

# Title

    <div class="grid">
      <div class="card">Hello</div>
    </div>
"""
    out = normalize_slidev_source(source)
    assert "\n<div class=\"grid\">" in out
    assert "\n    <div class=\"grid\">" not in out


def test_unwraps_layout_html_fence() -> None:
    source = """---
theme: default
---

# Title

```html
<div class="grid">
<div class="card">Hello</div>
</div>
```
"""
    out = normalize_slidev_source(source)
    assert "```html" not in out
    assert '<div class="grid">' in out


def test_keeps_real_code_fence() -> None:
    source = """# Demo

```ts
const html = '<div />'
```
"""
    out = normalize_slidev_source(source)
    assert "```ts" in out
    assert "const html" in out
