"""Build all paper figures and the Chinese XeLaTeX manuscript from existing results.
AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""

from pathlib import Path
import argparse
import subprocess
import sys
import shutil
import tempfile
from pdf_quality import audit_pdf, embed_cjk_unicode

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-figures", action="store_true")
    parser.add_argument(
        "--compatible",
        action="store_true",
        help="Also export a vector outlined PDF; requires Ghostscript",
    )
    args = parser.parse_args()
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/generate_paper_tables.py")],
        cwd=ROOT,
        check=True,
    )
    if not args.skip_figures:
        for script in sorted((ROOT / "scripts/figures").glob("fig*.py")):
            subprocess.run([sys.executable, str(script)], cwd=ROOT, check=True)
    if shutil.which("xelatex") is None:
        raise RuntimeError("Install XeLaTeX with ctex, xeCJK and Fandol fonts")
    out = ROOT / "outputs/paper"
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out) as staging:
        for _ in range(3):
            build = subprocess.run(
                [
                    "xelatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    f"-output-directory={staging}",
                    "main.tex",
                ],
                cwd=ROOT / "paper",
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            (out / "build.log").write_text(build.stdout, encoding="utf-8")
            if build.returncode:
                print(build.stdout[-6000:], file=sys.stderr)
                build.check_returncode()
        staged_pdf = Path(staging) / "main.pdf"
        embed_cjk_unicode(staged_pdf, ROOT / "paper/fonts/cmaps/Adobe-GB1-UCS2")
        audit_pdf(staged_pdf)
        if args.compatible:
            from export_compatible_pdf import export_compatible

            export_compatible(staged_pdf, Path(staging) / "main-compatible.pdf")
        for artifact in Path(staging).iterdir():
            artifact.replace(out / artifact.name)
    print(out / "main.pdf")


if __name__ == "__main__":
    main()
