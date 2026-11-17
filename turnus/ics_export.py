from __future__ import annotations

from datetime import datetime, timezone

from . import VERSJON
from .demo_data import MODALITETER
from .modeller import Ansatt, Skift, SkiftDef

PRODID = f"-//turnusplan//turnus {VERSJON}//NO"


def _esc(tekst: str) -> str:
    return (
        tekst.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(linje: str) -> str:
    deler: list[str] = []
    naa = ""
    n = 0
    for ch in linje:
        b = len(ch.encode("utf-8"))
        if n + b > 75:
            deler.append(naa)
            naa, n = " ", 1
        naa += ch
        n += b
    deler.append(naa)
    return "\r\n".join(deler)


def bygg_ics(
    tildelinger: dict[str, list[Skift]],
    ansatte: list[Ansatt],
    skift_defs: list[SkiftDef],
    kalender_navn: str = "Turnusforslag",
) -> str:
    ansatt_med_id = {a.id: a for a in ansatte}
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    linjer = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_esc(kalender_navn)}",
    ]
    for a_id in sorted(tildelinger):
        ansatt = ansatt_med_id[a_id]
        gruppe = "FAGR" if "fagradiograf" in ansatt.kompetanse else "rad"
        modaliteter = "/".join(sorted(ansatt.kompetanse & set(MODALITETER)))
        for skift in sorted(tildelinger[a_id]):
            start = skift.start.strftime("%Y%m%dT%H%M%S")
            slutt = skift.slutt.strftime("%Y%m%dT%H%M%S")
            uid = f"turnus-{a_id}-{skift.dato.isoformat()}-{skift.type.navn}@turnusplan"
            sammendrag = f"{skift.type.navn} – {ansatt.navn} [{gruppe} {modaliteter}]"
            linjer += [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART:{start}",
                f"DTEND:{slutt}",
                f"SUMMARY:{_esc(sammendrag)}",
                f"CATEGORIES:{_esc(skift.type.navn)}",
                "END:VEVENT",
            ]
    linjer.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in linjer) + "\r\n"
