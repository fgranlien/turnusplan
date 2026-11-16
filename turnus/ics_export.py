from __future__ import annotations

from datetime import datetime, timezone

from .demo_data import MODALITETER
from .modeller import Ansatt, Skift, SkiftDef

PRODID = "-//turnusplan//turnus 2.5//NO"


def _esc(tekst: str) -> str:
    return (
        tekst.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(linje: str) -> str:
    data = linje.encode("utf-8")
    if len(data) <= 75:
        return linje
    deler = []
    while data:
        deler.append(data[:75].decode("utf-8", errors="ignore"))
        data = data[len(deler[-1].encode("utf-8")):]
    return ("\r\n ").join(deler)


def bygg_ics(
    tildelinger: dict[str, list[Skift]],
    ansatte: list[Ansatt],
    skift_defs: list[SkiftDef],
    kalender_navn: str = "Turnusforslag",
) -> str:
    ansatt_med_id = {a.id: a for a in ansatte}
    dtstemp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
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
                f"DTSTAMP:{dtstemp}",
                f"DTSTART:{start}",
                f"DTEND:{slutt}",
                f"SUMMARY:{_esc(sammendrag)}",
                f"CATEGORIES:{_esc(skift.type.navn)}",
                "END:VEVENT",
            ]
    linjer.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in linjer) + "\r\n"
