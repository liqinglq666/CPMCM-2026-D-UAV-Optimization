"""Embed explicit CJK Unicode maps and reject unreadable paper PDFs.

AI assistance: ChatGPT/Codex, OpenAI, 2026-09-24; exact model unavailable.
"""

from pathlib import Path
import re

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject


def resource_fonts(pages):
    """Include fonts in nested figure forms, not only page text."""
    seen_resources = set()
    seen_fonts = set()

    def visit(resources):
        resources = resources.get_object()
        if id(resources) in seen_resources:
            return
        seen_resources.add(id(resources))
        for reference in resources.get("/Font", {}).values():
            font = reference.get_object()
            if id(font) not in seen_fonts:
                seen_fonts.add(id(font))
                yield font
        for reference in resources.get("/XObject", {}).values():
            form = reference.get_object()
            if "/Resources" in form:
                yield from visit(form["/Resources"])

    for page in pages:
        yield from visit(page["/Resources"])


def embed_cjk_unicode(pdf_path: Path, cmap_path: Path):
    """Supply Adobe's actual GB1 mapping; never guess a font's encoding.

    Some xdvipdfmx versions omit ToUnicode for standard Adobe CJK collections.
    Such PDFs rely on reader-specific external CMaps. Embed the licensed map
    explicitly so independent readers can recover the same Chinese text.
    """
    writer = PdfWriter(clone_from=pdf_path)
    missing = []
    for font in resource_fonts(writer.pages):
        if font.get("/Subtype") != "/Type0" or "/ToUnicode" in font:
            continue
        descendant = font["/DescendantFonts"][0].get_object()
        system = descendant.get("/CIDSystemInfo", {})
        if (str(system.get("/Registry")), str(system.get("/Ordering"))) != (
            "Adobe",
            "GB1",
        ) or font.get("/Encoding") not in ("/Identity-H", "/Identity-V"):
            raise ValueError(
                f"Unknown missing Unicode mapping: {font.get('/BaseFont')}"
            )
        missing.append(font)
    if not missing:
        return 0
    content = cmap_path.read_bytes()
    if b"/CMapName /Adobe-GB1-UCS2" not in content:
        raise ValueError("Expected the licensed Adobe-GB1-UCS2 CMap")
    stream = DecodedStreamObject()
    stream.set_data(content)
    reference = writer._add_object(stream.flate_encode())
    for font in missing:
        font[NameObject("/ToUnicode")] = reference
    temporary = pdf_path.with_suffix(".mapped.pdf")
    with temporary.open("wb") as output:
        writer.write(output)
    temporary.replace(pdf_path)
    return len(missing)


def audit_pdf(pdf_path: Path):
    """Require embedded fonts, explicit mappings and readable Chinese per page."""
    reader = PdfReader(pdf_path)
    fonts = list(resource_fonts(reader.pages))
    for font in fonts:
        name = str(font.get("/BaseFont", "unknown"))
        if "/ToUnicode" not in font:
            raise ValueError(f"Missing ToUnicode mapping: {name}")
        descendant = (
            font["/DescendantFonts"][0].get_object()
            if font.get("/Subtype") == "/Type0"
            else font
        )
        descriptor = descendant.get("/FontDescriptor", {})
        descriptor = (
            descriptor.get_object() if hasattr(descriptor, "get_object") else descriptor
        )
        if not any(
            key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3")
        ):
            raise ValueError(f"Font is not embedded: {name}")
    counts = []
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        count = len(re.findall(r"[\u3400-\u9fff]", text))
        if count < 10 or "\ufffd" in text:
            raise ValueError(f"Unreadable Chinese text on page {number}")
        counts.append(count)
    first = re.sub(r"\s+", "", reader.pages[0].extract_text())
    for anchor in (
        "地形与能量约束下的山区无人机运输、通信与资源分区",
        "摘要",
        "关键词",
    ):
        if anchor not in first:
            raise ValueError(f"Missing Chinese abstract anchor: {anchor}")
    return {
        "status": "PASS",
        "embedded_fonts_with_unicode": len(fonts),
        "pages": len(reader.pages),
        "chinese_characters_per_page": counts,
    }
