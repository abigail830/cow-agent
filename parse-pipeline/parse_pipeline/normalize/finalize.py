from __future__ import annotations

from parse_pipeline.normalize.artifacts import NormalizedArtifacts
from parse_pipeline.normalize.figures import figures_to_meta, mirror_markdown_figures
from parse_pipeline.normalize.line_index import build_line_index
from parse_pipeline.normalize.pageindex_pages import build_pages_from_pageindex
from parse_pipeline.normalize.pageindex_synthetic import build_pageindex_from_markdown


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
        docx_probe=artifacts.docx_probe,
        office_source_bytes=artifacts.office_source_bytes,
    )


def finalize_office_markitdown_artifacts(artifacts: NormalizedArtifacts) -> NormalizedArtifacts:
    finalized = finalize_normalized_artifacts(artifacts)
    probe = artifacts.docx_probe
    if probe is None:
        return finalized

    synthetic = build_pageindex_from_markdown(
        finalized.content_md,
        probe,
        file_bytes=artifacts.office_source_bytes,
    )
    if synthetic is None:
        return finalized

    warnings = list(finalized.warnings or [])
    warnings.extend(synthetic.warnings)
    meta = dict(finalized.meta_json)
    meta["pageindex_path"] = "pageindex.json"
    meta["warnings"] = warnings

    pageindex_pages = build_pages_from_pageindex(finalized.content_md, synthetic.pageindex)
    if pageindex_pages:
        meta["pages"] = pageindex_pages
        meta["page_count"] = len(pageindex_pages)

    return NormalizedArtifacts(
        content_md=finalized.content_md,
        meta_json=meta,
        pageindex_json=synthetic.pageindex,
        warnings=warnings,
        figure_files=finalized.figure_files,
    )
