"""Tests for html-ppt source normalization."""

from __future__ import annotations

from app.slide.html_ppt import build_html_ppt_dist
from app.slide.html_ppt_normalize import collect_html_ppt_warnings, normalize_html_ppt_source


def test_normalize_strips_inspire_meta_from_footer() -> None:
    html = """<!DOCTYPE html><html><body class="tpl-inspire-brand"><div class="deck">
<section class="slide inspire-cover"><h1>Title</h1>
<div class="deck-footer"><span>Inspire Theme 封面页，基于 inspire-brand 主题，保留深蓝品牌底色与蓝色高光。</span></div>
</section></div></body></html>"""
    out = normalize_html_ppt_source(html)
    assert "Inspire Theme" not in out
    assert "inspire-brand 主题" not in out
    assert "Title" in out


def test_normalize_injects_logo_and_copyright_only_when_opted_in() -> None:
    html = """<!DOCTYPE html><html><body class="tpl-inspire-brand"><div class="deck">
<section class="slide inspire-content"><h2>Body</h2></section>
<section class="slide inspire-cover"><h1>Cover</h1></section>
</div></body></html>"""
    out = normalize_html_ppt_source(html)
    assert 'class="inspire-logo"' in out
    assert "logo-white.png" in out
    assert "logo.png" in out
    assert "© Inspire Group" in out
    assert out.count("© Inspire Group") >= 2


def test_normalize_does_not_inject_inspire_without_opt_in() -> None:
    html = """<!DOCTYPE html><html><head>
<link rel="stylesheet" href="../../assets/themes/inspire-brand.css">
</head><body><div class="deck">
<section class="slide inspire-content"><h2>Body</h2>
<img class="inspire-logo" src="../../assets/inspire/logo.png" alt="Inspire">
<span class="inspire-copyright">© Inspire Group</span>
</section></div></body></html>"""
    out = normalize_html_ppt_source(html)
    assert "inspire-brand.css" not in out
    assert 'class="inspire-logo"' not in out
    assert "© Inspire Group" not in out


def test_normalize_strips_presenter_sidebar_blocks() -> None:
    html = """<!DOCTYPE html><html><body><div class="deck">
<section class="slide"><h2>Roadmap</h2>
<aside><h3>本页沟通重点</h3><ul><li>强调 Month 1</li></ul></aside>
</section></div></body></html>"""
    out = normalize_html_ppt_source(html)
    assert "本页沟通重点" not in out
    assert "强调 Month 1" not in out
    assert "Roadmap" in out


def test_normalize_strips_meta_badges_and_comm_focus_suffix() -> None:
    html = """<!DOCTYPE html><html><body><div class="deck">
<section class="slide">
<span class="pill">本页沟通重点</span>
<h2>一期价值交付：当前对外沟通可聚焦的三件事</h2>
</section></div></body></html>"""
    out = normalize_html_ppt_source(html)
    assert "本页沟通重点" not in out
    assert "对外沟通可聚焦" not in out
    assert "一期价值交付" in out


def test_normalize_adds_deck_host_and_default_theme() -> None:
    html = """<!DOCTYPE html><html><head></head><body><div class="deck">
<section class="slide"><h2>Hi</h2></section>
</div></body></html>"""
    out = normalize_html_ppt_source(html)
    assert "deck-host" in out
    assert 'name="viewport"' in out
    assert "corporate-clean.css" in out
    assert "unpkg.com/lucide" in out


def test_normalize_strips_comm_advice_footer_block() -> None:
    html = """<!DOCTYPE html><html><body><div class="deck">
<section class="slide"><h2>路线图</h2>
<div class="grid g2"><div><h3>一期沟通建议：把路线图讲成3个阶段动作</h3></div>
<div><p>一期 → 二期承接</p></div></div>
</section></div></body></html>"""
    out = normalize_html_ppt_source(html)
    assert "沟通建议" not in out
    assert "讲成" not in out
    assert "路线图" in out


def test_collect_html_ppt_warnings_flags_dense_single_slide() -> None:
    items = "".join(f"<li>Item {i}</li>" for i in range(12))
    html = f"""<!DOCTYPE html><html><body><div class="deck">
<section class="slide"><ul>{items}</ul></section></div></body></html>"""
    out = normalize_html_ppt_source(html)
    warnings = collect_html_ppt_warnings(source=html, normalized=out)
    assert any("too many list items" in w.lower() or "list items" in w.lower() for w in warnings)


def test_normalize_injects_scoped_css_for_inspire_layout_classes() -> None:
    html = """<!DOCTYPE html><html><body class="tpl-inspire-brand"><head></head><div class="deck">
<section class="slide inspire-content"><h2>Body</h2></section>
</div></body></html>"""
    out = normalize_html_ppt_source(html)
    assert "inspire-deck-scoped.css" in out


def test_normalize_injects_asc_css_when_opted_in() -> None:
    html = """<!DOCTYPE html><html><head></head><body class="tpl-asc-brand"><div class="deck">
<section class="slide asc-white"><h2>Body</h2></section>
</div></body></html>"""
    out = normalize_html_ppt_source(html)
    assert "asc-brand.css" in out
    assert "asc-deck-scoped.css" in out
    assert "corporate-clean.css" not in out


def test_collect_warnings_missing_asc_scoped_css_in_source() -> None:
    html = """<!DOCTYPE html><html><head>
<link rel="stylesheet" href="../../assets/themes/asc-brand.css">
</head><body class="tpl-asc-brand"><div class="deck">
<section class="slide asc-white"><h2>Hi</h2></section>
</div></body></html>"""
    out = normalize_html_ppt_source(html)
    warnings = collect_html_ppt_warnings(source=html, normalized=out)
    assert any("asc-deck-scoped.css" in w for w in warnings)


def test_build_html_ppt_dist_rewrites_injected_logo_paths() -> None:
    html = """<!DOCTYPE html><html><body class="tpl-inspire-brand"><div class="deck">
<section class="slide inspire-content"><h2>Hi</h2></section>
</div><script src="../../assets/runtime.js"></script></body></html>"""
    dist = build_html_ppt_dist(html)
    index = dist["index.html"].decode("utf-8")
    assert "./assets/inspire/logo.png" in index
    assert "assets/inspire/logo.png" in dist


def test_build_html_ppt_dist_bundles_inspire_scoped_css() -> None:
    html = """<!DOCTYPE html><html><body class="tpl-inspire-brand"><head></head><div class="deck">
<section class="slide inspire-content"><h2>Hi</h2></section>
</div></body></html>"""
    dist = build_html_ppt_dist(html)
    assert "assets/inspire-deck-scoped.css" in dist
    scoped = dist["assets/inspire-deck-scoped.css"].decode("utf-8")
    assert ".tpl-inspire-brand" in scoped
    assert ".slide-main" in scoped
    assert ".inspire-logo" in scoped


def test_build_html_ppt_dist_bundles_asc_brand_css() -> None:
    html = """<!DOCTYPE html><html><head></head><body class="tpl-asc-brand"><div class="deck">
<section class="slide asc-white"><h2>Hi</h2></section>
</div></body></html>"""
    dist = build_html_ppt_dist(html)
    index = dist["index.html"].decode("utf-8")
    assert "./assets/themes/asc-brand.css" in index
    assert "./assets/asc-deck-scoped.css" in index
    assert "assets/themes/asc-brand.css" in dist
    assert "assets/asc-deck-scoped.css" in dist
    scoped = dist["assets/asc-deck-scoped.css"].decode("utf-8")
    assert ".tpl-asc-brand" in scoped
    assert ".slide.asc-midnight" in scoped


def test_collect_warnings_missing_inspire_scoped_css_in_source() -> None:
    html = """<!DOCTYPE html><html><head>
<link rel="stylesheet" href="../../assets/themes/inspire-brand.css">
</head><body class="tpl-inspire-brand"><div class="deck">
<section class="slide inspire-content"><div class="slide-main"><h2>Hi</h2></div></section>
</div></body></html>"""
    out = normalize_html_ppt_source(html)
    warnings = collect_html_ppt_warnings(source=html, normalized=out)
    assert any("inspire-deck-scoped.css" in w for w in warnings)


def test_collect_warnings_missing_slide_main_when_scoped_css_missing() -> None:
    html = """<!DOCTYPE html><html><head>
<link rel="stylesheet" href="../../assets/themes/inspire-brand.css">
</head><body class="tpl-inspire-brand"><div class="deck">
<section class="slide inspire-content"><h2>Hi</h2></section>
</div></body></html>"""
    out = normalize_html_ppt_source(html)
    warnings = collect_html_ppt_warnings(source=html, normalized=out)
    assert any("inspire-deck-scoped.css" in w for w in warnings)
    assert any("slide-main" in w for w in warnings)


def test_collect_warnings_no_slide_main_noise_for_full_deck_template() -> None:
    html = """<!DOCTYPE html><html><head>
<link rel="stylesheet" href="templates/full-decks/inspire-brand/style.css">
</head><body class="tpl-inspire-brand"><div class="deck">
<section class="slide inspire-content"><h2>Hi</h2></section>
</div></body></html>"""
    out = normalize_html_ppt_source(html)
    warnings = collect_html_ppt_warnings(source=html, normalized=out)
    assert not any("slide-main" in w for w in warnings)


def test_normalize_wraps_content_slide_header_and_main() -> None:
    html = """<!DOCTYPE html><html><body><div class="deck">
<section class="slide inspire-content"><p class="kicker">Overview</p>
<h2 class="inspire-content-title">Title here</h2>
<ul class="inspire-bullets"><li>One</li><li>Two</li></ul>
</section></div></body></html>"""
    out = normalize_html_ppt_source(html)
    assert "slide-header" in out
    assert "slide-main" in out
    assert out.index("slide-header") < out.index("slide-main")
    assert "Title here" in out


def test_normalize_fixes_legacy_data_icon_markup() -> None:
    html = """<!DOCTYPE html><html><body><div class="deck">
<section class="slide"><div class="grid g4">
<div class="card"><span class="slide-icon-box sm" data-icon="database"></span><h4>A</h4></div>
<div class="card"><span class="slide-icon-box sm" data-icon="users"></span><h4>B</h4></div>
</div></section></div>
<script src="../../assets/runtime.js"></script></body></html>"""
    out = normalize_html_ppt_source(html)
    assert 'data-lucide="database"' in out
    assert 'data-lucide="users"' in out
    assert "data-icon=" not in out
    assert out.index("unpkg.com/lucide") < out.index("runtime.js")


def test_normalize_fixes_empty_slide_icon_box() -> None:
    html = """<!DOCTYPE html><html><body><div class="deck">
<section class="slide"><span class="slide-icon-box sm"></span><h4>Col</h4></section>
</div><script src="../../assets/runtime.js"></script></body></html>"""
    out = normalize_html_ppt_source(html)
    assert 'data-lucide="layers"' in out


def test_collect_warnings_flags_emoji_on_slide() -> None:
    html = """<!DOCTYPE html><html><body><div class="deck">
<section class="slide"><h2>Goals 🎯</h2></section></div></body></html>"""
    out = normalize_html_ppt_source(html)
    warnings = collect_html_ppt_warnings(source=html, normalized=out)
    assert any("emoji" in w.lower() for w in warnings)
    assert any("data-lucide" in w for w in warnings)
