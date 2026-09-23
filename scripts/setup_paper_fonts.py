"""Install a checksum-verified TrueType Chinese font for portable vector figures.

Noto Sans SC: Google/Noto, SIL Open Font License 1.1.
AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""

import hashlib
from pathlib import Path
import urllib.request

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf"
FONT_SHA256 = "a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da"


def main():
    target = ROOT / "paper/fonts/NotoSansSC-Regular.ttf"
    if target.is_file():
        print(target)
        return
    cache = ROOT / "outputs/font-cache"
    cache.mkdir(parents=True, exist_ok=True)
    source = cache / "NotoSansSC-variable.ttf"
    urllib.request.urlretrieve(FONT_URL, source)
    if hashlib.sha256(source.read_bytes()).hexdigest() != FONT_SHA256:
        raise ValueError(
            "Font source changed; verify the new release before updating its checksum"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    font = instantiateVariableFont(TTFont(source), {"wght": 400}, inplace=True)
    font.save(target)
    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/OFL.txt",
        target.parent / "OFL.txt",
    )
    print(target)


if __name__ == "__main__":
    main()
