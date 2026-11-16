from __future__ import annotations

import math

from .modeller import Ansatt, KVELD, Krav, NATT, SkiftDef

KOMPETANSE_ANDLER = [("leder", 0.25), ("sykepleier", 0.25), ("assistent", 0.5)]

NAVN = {
    "leder": ["Anne", "Bjørn", "Cecilie", "David", "Eva", "Fredrik", "Geir", "Hanna", "Ivar", "Jenny", "Karl", "Lene", "Mons", "Nora", "Odd"],
    "sykepleier": ["Greta", "Henrik", "Ingrid", "Jonas", "Karin", "Lars", "Marte", "Nils", "Oda", "Per", "Ragnhild", "Stian", "Tiril", "Una", "Vera"],
    "assistent": ["Nina", "Ola", "Petra", "Rune", "Sofia", "Thomas", "Ulrik", "Vilde", "Aksel", "Birgitte", "Even", "Frida", "Gard", "Hege", "Jens"],
}


def fordel_bemanning(total: int) -> list[Krav]:
    if total <= 0:
        return []
    if total == 1:
        return [Krav("leder", 1)]
    if total == 2:
        return [Krav("leder", 1), Krav("sykepleier", 1)]
    leder = max(1, round(total * 0.25))
    sykepleier = max(1, round(total * 0.25))
    assistent = max(1, total - leder - sykepleier)
    return [Krav("leder", leder), Krav("sykepleier", sykepleier), Krav("assistent", assistent)]


def bygg_behov(
    bemanning_hverdag: dict[str, int],
    bemanning_helg: dict[str, int],
) -> dict[str, dict[str, list[Krav]]]:
    behov: dict[str, dict[str, list[Krav]]] = {}
    for kategori, bemanning in (("hverdag", bemanning_hverdag), ("helg", bemanning_helg)):
        behov[kategori] = {
            skift: fordel_bemanning(antall) for skift, antall in bemanning.items() if antall > 0
        }
    return behov


def uketlig_ettersporsel(behov: dict[str, dict[str, list[Krav]]]) -> dict[str, int]:
    ettersporsel: dict[str, int] = {}
    for kategori, dager_i_kategori in (("hverdag", 5), ("helg", 2)):
        for krav_liste in behov[kategori].values():
            for krav in krav_liste:
                ettersporsel[krav.kompetanse] = ettersporsel.get(krav.kompetanse, 0) + krav.antall * dager_i_kategori
    return ettersporsel


def bygg_ansatte(behov: dict[str, dict[str, list[Krav]]], skift_defs: list[SkiftDef]) -> list[Ansatt]:
    defs_med_navn = {d.navn: d for d in skift_defs}
    timer_ettersporsel: dict[str, float] = {}
    natt_ettersporsel: dict[str, float] = {}
    for kategori, dager_i_kategori in (("hverdag", 5), ("helg", 2)):
        for skift_navn, krav_liste in behov[kategori].items():
            skift_def = defs_med_navn[skift_navn]
            varighet = skift_def.varighet.total_seconds() / 3600
            for krav in krav_liste:
                timer_ettersporsel[krav.kompetanse] = timer_ettersporsel.get(krav.kompetanse, 0) + krav.antall * dager_i_kategori * varighet
                if skift_def.er_natt:
                    natt_ettersporsel[krav.kompetanse] = natt_ettersporsel.get(krav.kompetanse, 0) + krav.antall * dager_i_kategori

    ansatte: list[Ansatt] = []
    id_teller = 1
    for kompetanse in sorted(timer_ettersporsel):
        timer_per_uke = timer_ettersporsel[kompetanse]
        natt_behov_per_uke = natt_ettersporsel.get(kompetanse, 0.0)
        natt_varighet = max(
            (d.varighet.total_seconds() / 3600 for d in skift_defs if d.er_natt),
            default=8,
        )
        maks_natt_per_ansatt = max(2, int(36 // natt_varighet))
        antall = max(
            math.ceil(timer_per_uke / 32) + 1,
            math.ceil(natt_behov_per_uke / (0.75 * maks_natt_per_ansatt)) + 1,
            1,
        )
        navneliste = NAVN[kompetanse]
        for i in range(antall):
            navn = navneliste[i % len(navneliste)]
            if i >= len(navneliste):
                navn += f" {i // len(navneliste) + 1}"
            ansatt = Ansatt(f"a{id_teller}", navn, {kompetanse})
            if i % 4 == 0:
                ansatt.unnga = {NATT}
            elif i % 4 == 2:
                ansatt.foretrekker = {NATT}
            elif i % 4 == 3:
                ansatt.foretrekker = {KVELD}
            ansatte.append(ansatt)
            id_teller += 1
    return ansatte


def skift_defs_for(langvakter: bool) -> list[SkiftDef]:
    from .modeller import LANGVAKT_SKIFT, STANDARD_SKIFT

    return LANGVAKT_SKIFT if langvakter else STANDARD_SKIFT


def standard_bemanning(langvakter: bool) -> tuple[dict[str, int], dict[str, int]]:
    from .modeller import LANGVAKT_SKIFT, STANDARD_SKIFT

    navn = [d.navn for d in (LANGVAKT_SKIFT if langvakter else STANDARD_SKIFT)]
    return ({n: 4 for n in navn}, {n: 3 for n in navn})
