from __future__ import annotations

import json
import sys
from pathlib import Path

from .lager import skriv_atomisk

FIL = Path(__file__).resolve().parent.parent / "forvalg.json"


class ForvalgFeil(ValueError):
    pass


def les_alle() -> list[dict]:
    if not FIL.exists():
        return []
    try:
        data = json.loads(FIL.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(
            f"ADVARSEL: {FIL.name} kunne ikke leses ({e}) \u2013 starter uten lagrede forvalg.",
            file=sys.stderr,
        )
        return []
    if not isinstance(data, list):
        return []
    return [p for p in data if isinstance(p, dict) and str(p.get("navn", "")).strip()]


def les(navn: str) -> dict | None:
    for profil in les_alle():
        if profil.get("navn") == navn:
            return profil
    return None


def lagre(profil: dict) -> dict:
    if not isinstance(profil, dict):
        raise ForvalgFeil("Ugyldig forvalg")
    navn = str(profil.get("navn", "")).strip()
    if not navn:
        raise ForvalgFeil("Forvalget må ha et navn")
    profil["navn"] = navn
    alle = [p for p in les_alle() if p.get("navn") != navn]
    alle.append(profil)
    skriv_atomisk(FIL, json.dumps(alle, ensure_ascii=False, indent=2) + "\n")
    return profil


def slett(navn: str) -> bool:
    alle = les_alle()
    resterende = [p for p in alle if p.get("navn") != navn]
    if len(resterende) == len(alle):
        return False
    skriv_atomisk(FIL, json.dumps(resterende, ensure_ascii=False, indent=2) + "\n")
    return True
