"""Regressions for the missing Chinese Unicode maps in the delivered PDF."""

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from scripts.pdf_quality import audit_pdf, embed_cjk_unicode

CMAP = Path(__file__).resolve().parents[1] / "paper/fonts/cmaps/Adobe-GB1-UCS2"


def cid_pdf(path, collection="GB1"):
    """Small valid CID-text fixture; rendering uses the reader's fallback font.

    Adobe GB1 CID 1465 (0x05b9) is U+5730 地. No font binary is needed to
    reproduce the text-extraction bug, and this fixture is never delivered.
    """
    writer = PdfWriter()
    page = writer.add_blank_page(200, 100)
    descendant = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/CIDFontType0"),
            NameObject("/BaseFont"): NameObject("/STSong-Light"),
            NameObject("/CIDSystemInfo"): DictionaryObject(
                {
                    NameObject("/Registry"): TextStringObject("Adobe"),
                    NameObject("/Ordering"): TextStringObject(collection),
                    NameObject("/Supplement"): NumberObject(5),
                }
            ),
        }
    )
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type0"),
            NameObject("/BaseFont"): NameObject("/STSong-Light"),
            NameObject("/Encoding"): NameObject("/Identity-H"),
            NameObject("/DescendantFonts"): ArrayObject(
                [writer._add_object(descendant)]
            ),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F0"): writer._add_object(font)}
            )
        }
    )
    contents = DecodedStreamObject()
    contents.set_data(b"BT /F0 12 Tf 20 50 Td <05b9> Tj ET")
    page[NameObject("/Contents")] = writer._add_object(contents)
    with path.open("wb") as stream:
        writer.write(stream)


def test_quality_gate_rejects_missing_chinese_mapping(tmp_path):
    pdf = tmp_path / "unmapped.pdf"
    cid_pdf(pdf)
    with pytest.raises(ValueError, match="Missing ToUnicode"):
        audit_pdf(pdf)


def test_mapping_restores_real_chinese_and_is_idempotent(tmp_path):
    pdf = tmp_path / "mapped.pdf"
    cid_pdf(pdf)
    assert "地" not in PdfReader(pdf).pages[0].extract_text()
    assert embed_cjk_unicode(pdf, CMAP) == 1
    assert PdfReader(pdf).pages[0].extract_text() == "地"
    frozen = pdf.read_bytes()
    assert embed_cjk_unicode(pdf, CMAP) == 0
    assert pdf.read_bytes() == frozen


def test_unknown_collection_is_not_guessed_or_overwritten(tmp_path):
    pdf = tmp_path / "unknown.pdf"
    cid_pdf(pdf, collection="Unknown")
    frozen = pdf.read_bytes()
    with pytest.raises(ValueError, match="Unknown missing Unicode mapping"):
        embed_cjk_unicode(pdf, CMAP)
    assert pdf.read_bytes() == frozen
