from __future__ import annotations

import json
from pathlib import Path

from .modeller import LANGVAKT_SKIFT, SkiftDef

FIL = Path(__file__).resolve().parent.parent / "skift.json"

MAKS_VARIGHET = 12.0

PRESETS: dict[str, list[dict]] = {
    "standard": [
        {"navn": "DAG", "start": "07:00", "slutt": "15:00", "hverdag": True, "helg": True},
        {"navn": "KVELD", "start": "15:00", "slutt": "23:00", "hverdag": True, "helg": True},
        {"navn": "NATT", "start": "23:00", "slutt": "07:00", "hverdag": True, "helg": True},
    ],
    "mellomvakt": [
        {"navn": "DAG", "start": "07:00", "slutt": "15:00", "hverdag": True, "helg": True},
        {"navn": "MELLOM", "start": "11:30", "slutt": "19:00", "hverdag": True, "helg": False},
        {"navn": "KVELD", "start": "15:00", "slutt": "23:00", "hverdag": True, "helg": True},
        {"navn": "NATT", "start": "23:00", "slutt": "07:00", "hverdag": True, "helg": True},
    ],
    "langvakter": [
        {"navn": "DAG12", "start": "07:00", "slutt": "19:00", "hverdag": True, "helg": True},
        {"navn": "NATT12", "start": "19:00", "slutt": "07:00", "hverdag": True, "helg": True},
    ],
}


class SkiftFeil(ValueError):
    pass


def _parse_time(verdi, felt: str, navn: str) -> float:
    if isinstance(verdi, (int, float)):
        return float(verdi)
    tekst = str(verdi or "").strip()
    deler = tekst.split(":")
    try:
        if len(deler) == 2:
            return int(deler[0]) + int(deler[1]) / 60
        return float(tekst)
    except ValueError:
        raise SkiftFeil(f"{navn}: ugyldig klokkeslett for {felt}: '{tekst}'")


def til_skift_def(rad: dict) -> SkiftDef:
    if not isinstance(rad, dict):
        raise SkiftFeil("Ugyldig skiftformat")
    navn = str(rad.get("navn", "")).strip()
    if not navn:
        raise SkiftFeil("Skiftnavn mangler")
    start = _parse_time(rad.get("start"), "start", navn) % 24
    slutt = _parse_time(rad.get("slutt"), "slutt", navn) % 24
    er_natt = bool(rad.get("er_natt", False))
    if slutt <= start:
        slutt += 24
        er_natt = True
    varighet = slutt - start
    if varighet > MAKS_VARIGHET + 1e-9:
        raise SkiftFeil(f"{navn}: skiftlengde {varighet:.1f} t overstiger maks {MAKS_VARIGHET:.0f} t")
    dager = tuple(k for k in ("hverdag", "helg") if rad.get(k, True))
    if not dager:
        dager = ("hverdag",)
    return SkiftDef(navn, start, slutt, er_natt, dager)


def til_rad(d: SkiftDef) -> dict:
    def hm(timer: float) -> str:
        timer %= 24
        return f"{int(timer):02d}:{round((timer % 1) * 60):02d}"

    return {
        "navn": d.navn,
        "start": hm(d.start_time),
        "slutt": hm(d.slutt_time),
        "er_natt": d.er_natt,
        "hverdag": "hverdag" in d.dager,
        "helg": "helg" in d.dager,
    }


def parse_liste(data: list) -> list[SkiftDef]:
    if not isinstance(data, list) or not data:
        raise SkiftFeil("Minst ett skift må være definert")
    defs: list[SkiftDef] = []
    navn_sett: set[str] = set()
    for rad in data:
        d = til_skift_def(rad)
        if d.navn in navn_sett:
            raise SkiftFeil(f"Skiftnavnet '{d.navn}' er brukt to ganger")
        navn_sett.add(d.navn)
        defs.append(d)
    return defs


def les_lagrede() -> list[SkiftDef] | None:
    if not FIL.exists():
        return None
    try:
        data = json.loads(FIL.read_text(encoding="utf-8"))
        return parse_liste(data)
    except (OSError, json.JSONDecodeError, SkiftFeil):
        return None


def lagre(data: list) -> tuple[int, list[SkiftDef]]:
    defs = parse_liste(data)
    FIL.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(defs), defs


def standard() -> list[SkiftDef]:
    return parse_liste(PRESETS["mellomvakt"])


def skift_defs_for(langvakter: bool) -> list[SkiftDef]:
    return les_lagrede() or (parse_liste(PRESETS["langvakter"]) if langvakter else standard())
