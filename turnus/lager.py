from __future__ import annotations

import os
from pathlib import Path


def skriv_atomisk(sti: Path, tekst: str) -> None:
    tmp = sti.with_suffix(sti.suffix + ".tmp")
    tmp.write_text(tekst, encoding="utf-8")
    os.replace(tmp, sti)
