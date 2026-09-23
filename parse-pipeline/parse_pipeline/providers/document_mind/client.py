from __future__ import annotations

import asyncio
import io
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from parse_pipeline.config import Settings

logger = logging.getLogger(__name__)


# DM SubmitDocParserJobAdvance OutputFormat values (API param name: OutputFormat)
# - markdown: markdown in status/result
# - visualLayoutInfo: page images in QueryDocParserStatus; layout coords in GetDocParserResult
DM_OUTPUT_MARKDOWN = "markdown"
DM_OUTPUT_VISUAL_LAYOUT = "visualLayoutInfo"
DEFAULT_OUTPUT_FORMATS: tuple[str, ...] = (DM_OUTPUT_MARKDOWN, DM_OUTPUT_VISUAL_LAYOUT)


@dataclass
class DocumentMindConfig:
    access_key_id: str
    access_key_secret: str
    endpoint: str
    llm_enhancement: bool = True
    enhancement_mode: str | None = "VLM"
    output_formats: list[str] | None = None
    poll_interval_sec: float = 5.0
    layout_step_size: int = 50


@dataclass
class DocumentMindResult:
    markdown: str
    pageindex: dict[str, Any] | None
    external_job_id: str


class DocumentMindClient:
    def __init__(self, config: DocumentMindConfig) -> None:
        self._config = config
        self._client = self._build_client()

    def _build_client(self):
        from alibabacloud_docmind_api20220711.client import Client as DocMindClient
        from alibabacloud_tea_openapi import models as open_api_models

        cfg = open_api_models.Config(
            access_key_id=self._config.access_key_id,
            access_key_secret=self._config.access_key_secret,
        )
        cfg.endpoint = self._config.endpoint
        return DocMindClient(cfg)

    def submit(
        self,
        file_bytes: bytes,
        filename: str,
        output_formats: list[str] | None = None,
    ) -> str:
        from alibabacloud_docmind_api20220711 import models as dm_models
        from alibabacloud_tea_util import models as util_models

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else None
        formats = output_formats or self._config.output_formats or list(DEFAULT_OUTPUT_FORMATS)
        request = dm_models.SubmitDocParserJobAdvanceRequest(
            file_url_object=io.BytesIO(file_bytes),
            file_name=filename,
            file_name_extension=ext,
            llm_enhancement=self._config.llm_enhancement,
            enhancement_mode=self._config.enhancement_mode,
            output_format=formats,
        )
        runtime = util_models.RuntimeOptions()
        response = self._client.submit_doc_parser_job_advance(request, runtime)
        task_id = response.body.data.id
        if not task_id:
            raise RuntimeError("Document Mind submit returned no task id")
        return task_id

    def query_status(self, task_id: str) -> dict[str, Any]:
        from alibabacloud_docmind_api20220711 import models as dm_models

        request = dm_models.QueryDocParserStatusRequest(id=task_id)
        response = self._client.query_doc_parser_status(request)
        if response.body.data is None:
            return {}
        data = response.body.data.to_map()
        return data if isinstance(data, dict) else {}

    def get_result_chunk(self, task_id: str, layout_num: int, layout_step_size: int) -> dict[str, Any]:
        from alibabacloud_docmind_api20220711 import models as dm_models

        request = dm_models.GetDocParserResultRequest(
            id=task_id,
            layout_num=layout_num,
            layout_step_size=layout_step_size,
        )
        response = self._client.get_doc_parser_result(request)
        if response.body.data is None:
            return {}
        data = response.body.data.to_map() if hasattr(response.body.data, "to_map") else response.body.data
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _table_to_html(table_layout: dict[str, Any]) -> str:
        cells = table_layout.get("cells") or []
        if not cells:
            return ""
        html_parts = ['<table border="1" cellspacing="0" cellpadding="2">']
        processed: set[tuple[int, int]] = set()
        rows: dict[int, list[dict[str, Any]]] = {}
        for cell in cells:
            row_start = cell.get("ysc", 0)
            rows.setdefault(row_start, []).append(cell)
        for row_idx in sorted(rows.keys()):
            html_parts.append("<tr>")
            row_cells = sorted(rows[row_idx], key=lambda x: x.get("xsc", 0))
            for cell in row_cells:
                cell_key = (cell.get("ysc", 0), cell.get("xsc", 0))
                if cell_key in processed:
                    continue
                rowspan = cell.get("yec", 0) - cell.get("ysc", 0) + 1
                colspan = cell.get("xec", 0) - cell.get("xsc", 0) + 1
                for i in range(rowspan):
                    for j in range(colspan):
                        processed.add((cell.get("ysc", 0) + i, cell.get("xsc", 0) + j))
                cell_text = ""
                for layout in cell.get("layouts") or []:
                    if "text" in layout:
                        cell_text += layout["text"]
                cell_text = cell_text.strip().replace("\n", "<br>")
                attrs = []
                if rowspan > 1:
                    attrs.append(f'rowspan="{rowspan}"')
                if colspan > 1:
                    attrs.append(f'colspan="{colspan}"')
                html_parts.append(f'<td {" ".join(attrs)}>{cell_text}</td>')
            html_parts.append("</tr>")
        html_parts.append("</table>")
        return "".join(html_parts)

    @classmethod
    def layouts_to_markdown(cls, layouts: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for layout in layouts:
            if layout.get("type") == "table":
                parts.append(cls._table_to_html(layout))
                parts.append("")
            else:
                parts.append(layout.get("markdownContent") or layout.get("markdown_content") or "")
        return "\n".join(p for p in parts if p).strip() + "\n"

    def collect_all_layouts(self, task_id: str) -> list[dict[str, Any]]:
        all_layouts: list[dict[str, Any]] = []
        layout_num = 0
        step = self._config.layout_step_size
        while True:
            chunk = self.get_result_chunk(task_id, layout_num, step)
            layouts = chunk.get("layouts") or []
            if not layouts:
                break
            all_layouts.extend(layouts)
            layout_num += len(layouts)
            if len(layouts) < step:
                break
        return all_layouts

    def wait_until_done(
        self,
        task_id: str,
        on_poll: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        while True:
            status_data = self.query_status(task_id)
            if on_poll:
                on_poll(status_data)
            if self._is_terminal_status(status_data):
                if self._is_success_status(status_data):
                    return
                message = status_data.get("Message") or status_data.get("message") or "Document Mind failed"
                raise RuntimeError(str(message))
            time.sleep(self._config.poll_interval_sec)

    async def poll_until_done(
        self,
        task_id: str,
        on_poll: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        """Async poll loop: QueryDocParserStatus until success/failed."""
        while True:
            status_data = await asyncio.to_thread(self.query_status, task_id)
            if on_poll is not None:
                result = on_poll(status_data)
                if asyncio.iscoroutine(result):
                    await result
            if self._is_terminal_status(status_data):
                if self._is_success_status(status_data):
                    return
                message = status_data.get("Message") or status_data.get("message") or "Document Mind failed"
                raise RuntimeError(str(message))
            await asyncio.sleep(self._config.poll_interval_sec)

    @staticmethod
    def _status_value(status_data: dict[str, Any]) -> str:
        return str(status_data.get("Status") or status_data.get("status") or "").lower()

    @classmethod
    def _is_success_status(cls, status_data: dict[str, Any]) -> bool:
        return cls._status_value(status_data) == "success"

    @classmethod
    def _is_terminal_status(cls, status_data: dict[str, Any]) -> bool:
        return cls._status_value(status_data) in {"success", "failed"}

    def parse_document(
        self,
        file_bytes: bytes,
        filename: str,
        on_poll: Callable[[dict[str, Any]], None] | None = None,
    ) -> DocumentMindResult:
        task_id = self.submit(file_bytes, filename)
        self.wait_until_done(task_id, on_poll=on_poll)
        layouts = self.collect_all_layouts(task_id)
        markdown = self.layouts_to_markdown(layouts)
        pageindex = {"layouts": layouts, "external_job_id": task_id} if layouts else None
        return DocumentMindResult(markdown=markdown, pageindex=pageindex, external_job_id=task_id)


def build_client_from_settings(settings: Settings, job_options: dict[str, Any] | None = None) -> DocumentMindClient:
    if not settings.document_mind_configured:
        raise RuntimeError("Document Mind credentials not configured")
    dm_opts = (job_options or {}).get("document_mind") or {}
    raw_formats = dm_opts.get("output_formats")
    output_formats = list(raw_formats) if raw_formats else list(DEFAULT_OUTPUT_FORMATS)
    config = DocumentMindConfig(
        access_key_id=settings.document_mind_access_key_id or "",
        access_key_secret=settings.document_mind_access_key_secret or "",
        endpoint=settings.document_mind_endpoint,
        llm_enhancement=dm_opts.get("llm_enhancement", settings.document_mind_llm_enhancement),
        enhancement_mode=dm_opts.get("enhancement_mode", settings.document_mind_enhancement_mode),
        output_formats=output_formats,
        poll_interval_sec=settings.document_mind_poll_interval_sec,
        layout_step_size=settings.document_mind_layout_step_size,
    )
    return DocumentMindClient(config)


async def parse_document_async(
    settings: Settings,
    file_bytes: bytes,
    filename: str,
    job_options: dict[str, Any] | None = None,
    on_poll: Callable[[dict[str, Any]], None] | None = None,
) -> DocumentMindResult:
    client = build_client_from_settings(settings, job_options)

    def _run() -> DocumentMindResult:
        return client.parse_document(file_bytes, filename, on_poll=on_poll)

    return await asyncio.to_thread(_run)
