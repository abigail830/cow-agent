from __future__ import annotations

from parse_pipeline.normalize.artifacts import NormalizedArtifacts
from parse_pipeline.normalize.figures import figures_to_meta, mirror_markdown_figures
from parse_pipeline.normalize.line_index import build_line_index
from parse_pipeline.normalize.pageindex_pages import build_pages_from_pageindex


def finalize_normalized_artifacts(
    artifacts: NormalizedArtifacts,
    *,
    mirror_figures: bool = True,
) -> NormalizedArtifacts:
    content = artifacts.content_md
    warnings = list(artifacts.warnings or artifacts.meta_json.get("warnings") or [])
    figure_files: dict[str, tuple[bytes, str, str]] = {}
    mirrored_figures = ()

    if mirror_figures:
        mirror_result = mirror_markdown_figures(content)
        content = mirror_result.content_md
        warnings.extend(mirror_result.warnings)
        mirrored_figures = mirror_result.figures
        for fig in mirrored_figures:
            figure_files[fig.figure_id] = (fig.data, fig.mime_type, fig.extension)

    line_count, pages, sections = build_line_index(content)
    pageindex_pages = build_pages_from_pageindex(content, artifacts.pageindex_json)
    if pageindex_pages:
        pages = pageindex_pages

    meta = dict(artifacts.meta_json)
    meta["line_count"] = line_count
    meta["page_count"] = len(pages)
    meta["pages"] = pages
    meta["sections"] = sections
    meta["warnings"] = warnings
    meta["figures"] = figures_to_meta(mirrored_figures) if mirrored_figures else list(meta.get("figures") or [])

    return NormalizedArtifacts(
        content_md=content,
        meta_json=meta,
        pageindex_json=artifacts.pageindex_json,
        warnings=warnings,
        figure_files=figure_files,
    )
