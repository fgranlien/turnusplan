from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from . import regler
from .modeller import Ansatt, Krav, NATT, Skift, SkiftDef, STANDARD_SKIFT

ROTASJON_BONUS = {8: 0.5, 12: 0.3}
BAKLENGS_STRAFF = {16: 1.0, 20: 1.0}

PREF_BONUS = 2.0
UNNGA_STRAFF = 3.0
RETTFERDIGHET_VEKT = 2.0
NATT_BALANSE_VEKT = 0.5
SAMMENHENGENDE_STRAFF = 0.3
YRKESGRUPPER = {"fagradiograf", "radiograf"}
FAGRA_MODALITET_STRAFF = 1.5


@dataclass
class Plan:
    tildelinger: dict[str, list[Skift]]
    udekket: list[tuple[Skift, Krav]] = field(default_factory=list)


class TurnusGenerator:
    def __init__(
        self,
        ansatte: list[Ansatt],
        behov: dict[str, list[Krav]],
        start_dato: date,
        antall_dager: int,
        skift_defs: list[SkiftDef] | None = None,
        langvakt_avtale: bool = True,
    ):
        self.ansatte = ansatte
        self.behov = behov
        self.start_dato = start_dato
        self.antall_dager = antall_dager
        self.skift_defs = skift_defs if skift_defs is not None else STANDARD_SKIFT
        self.langvakt_avtale = langvakt_avtale
        self._plan: dict[str, list[Skift]] = {a.id: [] for a in ansatte}
        self._udekket: list[tuple[Skift, Krav]] = []

    def generer(self) -> Plan:
        for i in range(self.antall_dager):
            dato = self.start_dato + timedelta(days=i)
            kategori = "helg" if dato.weekday() >= 5 else "hverdag"
            for skift_def in self.skift_defs:
                skift = Skift(dato, skift_def)
                for krav in self.behov.get(kategori, {}).get(skift_def.navn, []):
                    for _ in range(krav.antall):
                        self._fyll(skift, krav)
        return Plan(dict(self._plan), list(self._udekket))

    def _fyll(self, skift: Skift, krav: Krav) -> None:
        kandidater = [
            a
            for a in self.ansatte
            if krav.kompetanse in a.kompetanse
            and regler.kandidat_er_lovlig(a, self._plan[a.id], skift, self.langvakt_avtale)
        ]
        if not kandidater:
            self._udekket.append((skift, krav))
            return
        beste = max(kandidater, key=lambda a: (self._score(a, skift, krav), a.id))
        self._plan[beste.id].append(skift)

    def _score(self, ansatt: Ansatt, skift: Skift, krav: Krav) -> float:
        s = 0.0
        if krav.kompetanse not in YRKESGRUPPER and "fagradiograf" in ansatt.kompetanse:
            s -= FAGRA_MODALITET_STRAFF
        if self._matcher(ansatt.foretrekker, skift):
            s += PREF_BONUS
        if self._matcher(ansatt.unnga, skift):
            s -= UNNGA_STRAFF
        tildelt = self._plan[ansatt.id]
        s -= RETTFERDIGHET_VEKT * len(tildelt) / max(1, self._kapasitet(ansatt))
        if skift.type.er_natt:
            s -= NATT_BALANSE_VEKT * sum(1 for x in tildelt if x.type.er_natt)

        forrige = self._skift_paa_dag(ansatt.id, skift.dato - timedelta(days=1))
        neste = self._skift_paa_dag(ansatt.id, skift.dato + timedelta(days=1))
        if forrige is not None:
            diff = (skift.type.start_time - forrige.type.start_time) % 24
            s += ROTASJON_BONUS.get(diff, 0.0) - BAKLENGS_STRAFF.get(diff, 0.0)
            s -= SAMMENHENGENDE_STRAFF
        if neste is not None:
            s -= SAMMENHENGENDE_STRAFF
        return s

    @staticmethod
    def _matcher(onsker: set[SkiftDef], skift: Skift) -> bool:
        return skift.type in onsker or (NATT in onsker and skift.type.er_natt)

    def _kapasitet(self, ansatt: Ansatt) -> int:
        uke_grense = regler.MAKS_UKETIMER_NORMAL * ansatt.stillingsprosent / 100
        snitt_varighet = sum(d.varighet.total_seconds() / 3600 for d in self.skift_defs) / len(self.skift_defs)
        uker = self.antall_dager / 7
        return max(1, round(uker * uke_grense / snitt_varighet))

    def _skift_paa_dag(self, ansatt_id: str, dato: date) -> Skift | None:
        for skift in self._plan[ansatt_id]:
            if skift.dato == dato:
                return skift
        return None
