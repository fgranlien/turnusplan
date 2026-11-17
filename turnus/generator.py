from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from . import regler
from .modeller import Ansatt, Krav, Skift, SkiftDef, STANDARD_SKIFT

ROTASJON_BONUS = {8: 0.5, 12: 0.3}
BAKLENGS_STRAFF = {16: 1.0, 20: 1.0}

PREF_BONUS = 2.0
UNNGA_STRAFF = 3.0
RETTFERDIGHET_VEKT = 2.0
NATT_BALANSE_VEKT = 0.5
SAMMENHENGENDE_STRAFF = 0.3
SAMLET_HELG_BONUS = 1.5
YRKESGRUPPER = {"fagradiograf", "radiograf"}
FAGRA_MODALITET_STRAFF = 1.5


@dataclass
class Plan:
    tildelinger: dict[str, list[Skift]]
    udekket: list[tuple[Skift, Krav]] = field(default_factory=list)
    laaste_feilet: list[str] = field(default_factory=list)


class TurnusGenerator:
    def __init__(
        self,
        ansatte: list[Ansatt],
        behov: dict[str, list[Krav]],
        start_dato: date,
        antall_dager: int,
        skift_defs: list[SkiftDef] | None = None,
        langvakt_avtale: bool = True,
        uke_time_norm: float = 40.0,
        rotasjon: tuple[int, int] | None = None,
        laaste: list[tuple[str, Skift]] | None = None,
        maks_natter: int = 4,
        maks_kvelder: int = 2,
    ):
        self.ansatte = ansatte
        self.behov = behov
        self.start_dato = start_dato
        self.antall_dager = antall_dager
        self.skift_defs = skift_defs if skift_defs is not None else STANDARD_SKIFT
        self.langvakt_avtale = langvakt_avtale
        self.uke_time_norm = uke_time_norm
        self.rotasjon = rotasjon
        self.maks_natter = max(1, int(maks_natter))
        self.maks_kvelder = max(1, int(maks_kvelder))
        if rotasjon is not None:
            syklus, grupper = rotasjon
            self._grupper = {
                a.id: i % grupper
                for i, a in enumerate(sorted(ansatte, key=lambda a: a.id))
            }
        else:
            self._grupper = {}
        self._laaste = laaste or []
        self._plan: dict[str, list[Skift]] = {a.id: [] for a in ansatte}
        self._udekket: list[tuple[Skift, Krav]] = []
        self._laaste_feilet: list[str] = []

    def generer(self) -> Plan:
        for ansatt_id, skift in self._laaste:
            self._laas(ansatt_id, skift)
        for i in range(self.antall_dager):
            dato = self.start_dato + timedelta(days=i)
            kategori = "helg" if dato.weekday() >= 5 else "hverdag"
            for skift_def in self.skift_defs:
                skift = Skift(dato, skift_def)
                for krav in self.behov.get(kategori, {}).get(skift_def.navn, []):
                    for _ in range(krav.antall):
                        self._fyll(skift, krav)
        return Plan(dict(self._plan), list(self._udekket), list(self._laaste_feilet))

    def _laas(self, ansatt_id: str, skift: Skift) -> None:
        ansatt = next((a for a in self.ansatte if a.id == ansatt_id), None)
        if ansatt is None:
            self._laaste_feilet.append(
                f"L\u00e5st vakt avvist: ukjent ansatt for {skift.type.navn} {skift.dato:%d.%m}"
            )
            return
        kategori = "helg" if skift.dato.weekday() >= 5 else "hverdag"
        krav_liste = self.behov.get(kategori, {}).get(skift.type.navn, [])
        if not krav_liste or not any(k.kompetanse in ansatt.kompetanse for k in krav_liste):
            self._laaste_feilet.append(
                f"L\u00e5st vakt avvist: {ansatt.navn} har ikke kompetansen som trengs p\u00e5 "
                f"{skift.type.navn} {skift.dato:%d.%m}"
            )
            return
        if skift.dato in ansatt.utilgjengelige_dager:
            self._laaste_feilet.append(
                f"L\u00e5st vakt avvist: {ansatt.navn} er utilgjengelig {skift.dato:%d.%m}"
            )
            return
        if not regler.kandidat_er_lovlig(ansatt, self._plan[ansatt.id], skift, self.langvakt_avtale, self.maks_natter, self.maks_kvelder):
            self._laaste_feilet.append(
                f"L\u00e5st vakt avvist: {ansatt.navn} kan ikke ha {skift.type.navn} {skift.dato:%d.%m} "
                "innenfor aml-reglene (d\u00f8gnhvile, uketimer, ukeshvile, kveld- eller natteserie)"
            )
            return
        self._plan[ansatt.id].append(skift)

    def _fyll(self, skift: Skift, krav: Krav) -> None:
        kandidater = [
            a
            for a in self.ansatte
            if krav.kompetanse in a.kompetanse
            and regler.kandidat_er_lovlig(a, self._plan[a.id], skift, self.langvakt_avtale, self.maks_natter, self.maks_kvelder)
        ]
        if not kandidater:
            self._udekket.append((skift, krav))
            return
        if self.uke_time_norm < regler.MAKS_UKETIMER_NORMAL:
            stramme = [a for a in kandidater if self._under_norm(a, skift)]
            if stramme:
                kandidater = stramme
        beste = max(kandidater, key=lambda a: (self._score(a, skift, krav), a.id))
        self._plan[beste.id].append(skift)

    def _preferanser(self, ansatt: Ansatt, dato: date) -> tuple[set[str], set[str]]:
        if self.rotasjon is not None:
            syklus, grupper = self.rotasjon
            syklus_nr = (dato - self.start_dato).days // syklus
            idx = (self._grupper[ansatt.id] + syklus_nr) % grupper
            return {self.skift_defs[idx].navn}, set()
        return ansatt.foretrekker, ansatt.unnga

    def _under_norm(self, ansatt: Ansatt, skift: Skift) -> bool:
        uker_brukt = (skift.dato - self.start_dato).days // 7 + 1
        timer = skift.varighet.total_seconds() / 3600 + sum(
            s.varighet.total_seconds() / 3600 for s in self._plan[ansatt.id]
        )
        grense = self.uke_time_norm * ansatt.stillingsprosent / 100
        return timer / uker_brukt <= grense + 1e-9

    def _score(self, ansatt: Ansatt, skift: Skift, krav: Krav) -> float:
        s = 0.0
        if krav.kompetanse not in YRKESGRUPPER and "fagradiograf" in ansatt.kompetanse:
            s -= FAGRA_MODALITET_STRAFF
        foretrekker, unnga = self._preferanser(ansatt, skift.dato)
        if self._matcher(foretrekker, skift):
            s += PREF_BONUS
        if self._matcher(unnga, skift):
            s -= UNNGA_STRAFF
        tildelt = self._plan[ansatt.id]
        s -= RETTFERDIGHET_VEKT * len(tildelt) / max(1, self._kapasitet(ansatt))
        if skift.type.er_natt:
            s -= NATT_BALANSE_VEKT * sum(1 for x in tildelt if x.type.er_natt)

        helg_forrige = skift.dato.weekday() == 6 and (skift.dato - timedelta(days=1)).weekday() == 5
        helg_neste = skift.dato.weekday() == 5 and (skift.dato + timedelta(days=1)).weekday() == 6
        forrige = self._skift_paa_dag(ansatt.id, skift.dato - timedelta(days=1))
        neste = self._skift_paa_dag(ansatt.id, skift.dato + timedelta(days=1))
        if forrige is not None:
            diff = (skift.type.start_time - forrige.type.start_time) % 24
            s += ROTASJON_BONUS.get(diff, 0.0) - BAKLENGS_STRAFF.get(diff, 0.0)
            s += SAMLET_HELG_BONUS if helg_forrige else -SAMMENHENGENDE_STRAFF
        if neste is not None and not helg_neste:
            s -= SAMMENHENGENDE_STRAFF
        return s

    @staticmethod
    def _matcher(onsker: set[str], skift: Skift) -> bool:
        return regler.matcher(onsker, skift.type)

    def _kapasitet(self, ansatt: Ansatt) -> int:
        uke_grense = self.uke_time_norm * ansatt.stillingsprosent / 100
        snitt_varighet = sum(d.varighet.total_seconds() / 3600 for d in self.skift_defs) / len(self.skift_defs)
        uker = self.antall_dager / 7
        return max(1, round(uker * uke_grense / snitt_varighet))

    def _skift_paa_dag(self, ansatt_id: str, dato: date) -> Skift | None:
        for skift in self._plan[ansatt_id]:
            if skift.dato == dato:
                return skift
        return None
