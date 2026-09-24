"""Export an outlined vector PDF for viewers that fail to draw CJK fonts.

The searchable LaTeX PDF is preserved. The compatibility copy uses vector
glyph outlines, so its text cannot be searched/copied or read by a screen reader.
AI assistance: ChatGPT/Codex, OpenAI, 2026-09-24; exact model unavailable.
"""

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

from pypdf import PdfReader

from pdf_quality import resource_fonts

ROOT = Path(__file__).resolve().parents[1]


def export_compatible(source: Path, destination: Path):
    source, destination = source.resolve(), destination.resolve()
    if source == destination:
        raise ValueError("Preserve the searchable original; choose a separate output")
    executable = next(
        (
            path
            for name in ("gs", "gswin64c", "gswin32c")
            if (path := shutil.which(name))
        ),
        None,
    )
    if executable is None:
        raise RuntimeError("Install Ghostscript to export the vector compatibility PDF")
    original = PdfReader(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as staging:
        converted = Path(staging) / "outlined.pdf"
        subprocess.run(
            [
                executable,
                "-q",
                "-dSAFER",
                "-dBATCH",
                "-dNOPAUSE",
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                "-dNoOutputFonts",
                "-dAutoRotatePages=/None",
                "-dDownsampleColorImages=false",
                "-dDownsampleGrayImages=false",
                "-dDownsampleMonoImages=false",
                f"-sOutputFile={converted}",
                str(source),
            ],
            check=True,
        )
        result = PdfReader(converted)
        if len(result.pages) != len(original.pages):
            raise ValueError("Compatibility export changed the page count")
        if list(resource_fonts(result.pages)):
            raise ValueError("Compatibility PDF still depends on fonts")
        for before, after in zip(original.pages, result.pages):
            if any(
                abs(float(a) - float(b)) > 0.02
                for a, b in zip(before.mediabox, after.mediabox)
            ):
                raise ValueError("Compatibility export changed the page dimensions")
        converted.replace(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "outputs/paper/main.pdf")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/paper/main-compatible.pdf"
    )
    args = parser.parse_args()
    print(export_compatible(args.input, args.output))
