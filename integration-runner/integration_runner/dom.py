from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lxml import etree, html

IGNORED_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "path",
    "meta",
    "link",
    "head",
}
ACTIONABLE_TAGS = {
    "a",
    "button",
    "input",
    "option",
    "select",
    "textarea",
}
ACTIONABLE_ROLES = {
    "button",
    "checkbox",
    "combobox",
    "link",
    "menuitem",
    "option",
    "radio",
    "switch",
    "tab",
}
TEXT_TAGS = {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "label",
    "legend",
    "li",
    "p",
    "span",
}
STRUCTURE_TAGS = {
    "article",
    "dialog",
    "div",
    "form",
    "main",
    "section",
}
MAX_TEXT_LENGTH = 160
MAX_LINES_PER_FRAME = 200


@dataclass(frozen=True)
class FrameDomSnapshot:
    frame_id: str
    url: str
    html_content: str


def _normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def _truncate(value: str, *, max_length: int = MAX_TEXT_LENGTH) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 3] + "..."


def _local_tag(element: etree._Element) -> str:
    tag = element.tag
    if not isinstance(tag, str):
        return ""

    if "}" in tag:
        return tag.rsplit("}", 1)[-1].lower()
    return tag.lower()


def _element_text(element: etree._Element) -> str:
    return _truncate(_normalize_whitespace(element.text_content()))


def _own_text(element: etree._Element) -> str:
    text_parts = [element.text or ""]
    for child in element:
        text_parts.append(child.tail or "")
    return _truncate(_normalize_whitespace(" ".join(text_parts)))


def _element_depth(element: etree._Element) -> int:
    return len(list(element.iterancestors()))


def _safe_xpath(element: etree._Element) -> str:
    try:
        return element.getroottree().getpath(element)
    except Exception:
        return "<unknown-xpath>"


def _attribute_summary(element: etree._Element) -> list[str]:
    attributes: list[tuple[str, str | None]] = [
        ("role", element.get("role")),
        ("type", element.get("type")),
        ("name", element.get("name")),
        ("id", element.get("id")),
        ("placeholder", element.get("placeholder")),
        ("aria-label", element.get("aria-label")),
        ("value", element.get("value")),
        ("href", element.get("href")),
    ]

    parts: list[str] = []
    for key, value in attributes:
        normalized = _normalize_whitespace(value)
        if normalized:
            parts.append(f'{key}="{_truncate(normalized)}"')

    for boolean_name in ("checked", "disabled", "required", "readonly", "selected"):
        if element.get(boolean_name) is not None:
            parts.append(boolean_name)

    return parts


def _is_actionable(element: etree._Element, tag: str) -> bool:
    if tag in ACTIONABLE_TAGS:
        return True

    role = _normalize_whitespace(element.get("role")).lower()
    return role in ACTIONABLE_ROLES


def _interesting_line(element: etree._Element) -> str | None:
    tag = _local_tag(element)
    if not tag or tag in IGNORED_TAGS:
        return None

    actionable = _is_actionable(element, tag)
    text = (
        _element_text(element) if actionable or tag in TEXT_TAGS else _own_text(element)
    )
    attributes = _attribute_summary(element)
    depth = min(_element_depth(element), 8)
    indent = "  " * depth
    xpath = _safe_xpath(element)

    if actionable:
        parts = [f"{indent}{tag}", f'xpath="{xpath}"']
        parts.extend(attributes)
        if text:
            parts.append(f'text="{text}"')
        return " ".join(parts)

    if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit() and text:
        return f'{indent}heading level={tag[1]} text="{text}"'

    if tag in {"label", "legend"} and text:
        return f'{indent}{tag} text="{text}"'

    if tag in {"p", "li", "span"} and text:
        return f'{indent}{tag} text="{text}"'

    if tag in STRUCTURE_TAGS:
        if not text and not attributes:
            return None

        parts = [f"{indent}{tag}"]
        parts.extend(attributes)
        if text:
            parts.append(f'text="{text}"')
        return " ".join(parts)

    return None


def summarize_html_document(
    *,
    html_content: str,
    frame_id: str,
    url: str,
    max_lines: int = MAX_LINES_PER_FRAME,
) -> str:
    try:
        document = html.document_fromstring(html_content)
    except (etree.ParserError, ValueError):
        normalized_html = _truncate(_normalize_whitespace(html_content), max_length=500)
        return f'FRAME {frame_id} url={url}\n  raw_html text="{normalized_html}"'

    lines = [f"FRAME {frame_id} url={url}"]
    line_count = 0

    for element in document.iter():
        line = _interesting_line(element)
        if not line:
            continue

        lines.append(line)
        line_count += 1
        if line_count >= max_lines:
            lines.append("  ... truncated ...")
            break

    if line_count == 0:
        body_text = _truncate(_normalize_whitespace(document.text_content()))
        if body_text:
            lines.append(f'  body_text text="{body_text}"')
        else:
            lines.append("  <no interesting elements>")

    return "\n".join(lines)


async def snapshot_page_frames(page: Any) -> list[FrameDomSnapshot]:
    snapshots: list[FrameDomSnapshot] = []
    iframe_index = 0

    for frame in page.frames:
        if frame == page.main_frame:
            frame_id = "main"
        else:
            iframe_index += 1
            frame_name = _normalize_whitespace(getattr(frame, "name", ""))
            frame_id = (
                f'iframe[{iframe_index}] name="{frame_name}"'
                if frame_name
                else f"iframe[{iframe_index}]"
            )

        try:
            html_content = await frame.content()
        except Exception:
            html_content = ""

        snapshots.append(
            FrameDomSnapshot(
                frame_id=frame_id,
                url=getattr(frame, "url", "") or "",
                html_content=html_content,
            )
        )

    return snapshots


async def summarize_page_dom(page: Any) -> str:
    frame_summaries = [
        summarize_html_document(
            html_content=snapshot.html_content,
            frame_id=snapshot.frame_id,
            url=snapshot.url,
        )
        for snapshot in await snapshot_page_frames(page)
    ]
    return "\n\n".join(frame_summaries)


async def write_page_dom_summary(
    *,
    page: Any,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"dom-summary-{timestamp}.txt"
    output_path.write_text(await summarize_page_dom(page), encoding="utf-8")
    return output_path
