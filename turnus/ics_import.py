from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Vakt:
    start: datetime
    slutt: datetime
    etikett: str

    @property
    def varighet(self) -> timedelta:
        return self.slutt - self.start

    @property
    def dato(self):
        return self.start.date()

    @property
    def kategori(self) -> str:
        if self.slutt.date() > self.start.date():
            return "NATT"
        if self.start.hour >= 14:
            return "KVELD"
        return "DAG"


def _felt(blokk: str, navn: str) -> str | None:
    treff = re.search(rf"^{navn}[^:]*:(.+)$", blokk, re.M)
    return treff.group(1).strip() if treff else None


def les_ics(sti: str) -> tuple[list[Vakt], list[str]]:
    with open(sti, encoding="utf-8-sig") as f:
        return les_ics_tekst(f.read())


def les_ics_tekst(tekst: str) -> tuple[list[Vakt], list[str]]:
    tekst = tekst.replace("\r\n ", "").replace("\n ", "")

    vakter: list[Vakt] = []
    merknader: list[str] = []
    sett_uid: set[str] = set()

    for blokk in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", tekst, re.S):
        uid = _felt(blokk, "UID") or ""
        summary = (_felt(blokk, "SUMMARY") or "?").strip()
        if uid and uid in sett_uid:
            continue
        sett_uid.add(uid)

        dtstart = _felt(blokk, "DTSTART")
        dtend = _felt(blokk, "DTEND")
        if not dtstart or not dtend:
            merknader.append(f"{summary}: mangler start- eller sluttid, hoppes over")
            continue

        if re.fullmatch(r"\d{8}", dtstart):
            merknader.append(f"{summary} {dtstart[:4]}-{dtstart[4:6]}-{dtstart[6:]}: heldag (fridag), telles ikke som arbeid")
            continue

        if not (re.fullmatch(r"\d{8}T\d{6}", dtstart) and re.fullmatch(r"\d{8}T\d{6}", dtend)):
            merknader.append(f"{summary}: ukjent tidsformat, hoppes over")
            continue

        start = datetime.strptime(dtstart, "%Y%m%dT%H%M%S")
        slutt = datetime.strptime(dtend, "%Y%m%dT%H%M%S")
        if slutt <= start:
            merknader.append(f"{summary} {start:%d.%m}: slutt før start, hoppes over")
            continue
        vakter.append(Vakt(start, slutt, summary))

    vakter.sort(key=lambda v: v.start)
    return vakter, merknader
