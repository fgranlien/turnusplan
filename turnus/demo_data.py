from __future__ import annotations

import math

from .modeller import Ansatt, KVELD, Krav, NATT, SkiftDef

MODALITETER = ["Røntgen", "CT", "MR", "Ultralyd", "Mammografi", "Intervensjon"]
YRKESGRUPPER = ("radiograf", "fagradiograf")

NAVN = {
    "radiograf": ["Ola", "Nina", "Petra", "Rune", "Sofia", "Thomas", "Ulrik", "Vilde", "Aksel", "Birgitte", "Even", "Frida", "Gard", "Hege", "Jens"],
    "fagradiograf": ["Anne", "Bjørn", "Cecilie", "David", "Eva", "Fredrik", "Geir", "Hanna", "Ivar", "Jenny"],
}

STANDARD_PER_SKIFT = {
    "fagradiograf": (1, 1),
    "Røntgen": (2, 1),
    "CT": (1, 1),
    "MR": (1, 1),
}


def bygg_behov(
    bemanning: dict[str, dict[str, dict[str, int]]],
    skift_defs: list[SkiftDef],
) -> dict[str, dict[str, list[Krav]]]:
    behov: dict[str, dict[str, list[Krav]]] = {}
    for kategori in ("hverdag", "helg"):
        rad: dict[str, list[Krav]] = {}
        for skift_def in skift_defs:
            if kategori not in skift_def.dager:
                continue
            skift_cfg = bemanning.get(skift_def.navn, {})
            rekkefolge = ["fagradiograf"] + [k for k in skift_cfg if k != "fagradiograf"]
            krav = [
                Krav(komp, int(skift_cfg.get(komp, {}).get(kategori, 0)))
                for komp in rekkefolge
            ]
            krav = [k for k in krav if k.antall > 0]
            if krav:
                rad[skift_def.navn] = krav
        behov[kategori] = rad
    return behov


def ettersporsel_per_kompetanse(
    behov: dict[str, dict[str, list[Krav]]],
    skift_defs: list[SkiftDef],
) -> tuple[dict[str, float], dict[str, float]]:
    defs_med_navn = {d.navn: d for d in skift_defs}
    timer: dict[str, float] = {}
    natt: dict[str, float] = {}
    for kategori, dager_i_kategori in (("hverdag", 5), ("helg", 2)):
        for skift_navn, krav_liste in behov[kategori].items():
            skift_def = defs_med_navn[skift_navn]
            varighet = skift_def.varighet.total_seconds() / 3600
            for krav in krav_liste:
                timer[krav.kompetanse] = timer.get(krav.kompetanse, 0) + krav.antall * dager_i_kategori * varighet
                if skift_def.er_natt:
                    natt[krav.kompetanse] = natt.get(krav.kompetanse, 0) + krav.antall * dager_i_kategori
    return timer, natt


def _pool_storrelse(timer_per_uke: float, natt_per_uke: float, skift_defs: list[SkiftDef]) -> int:
    natt_varighet = max(
        (d.varighet.total_seconds() / 3600 for d in skift_defs if d.er_natt),
        default=8.0,
    )
    maks_natt_per_ansatt = max(2, int(36 // natt_varighet))
    return max(
        math.ceil(timer_per_uke / 32) + 1,
        math.ceil(natt_per_uke / (0.75 * maks_natt_per_ansatt)) + 1,
        1,
    )


def bygg_ansatte(behov: dict[str, dict[str, list[Krav]]], skift_defs: list[SkiftDef]) -> list[Ansatt]:
    timer, natt = ettersporsel_per_kompetanse(behov, skift_defs)
    aktive_modaliteter = sorted(k for k in timer if k in MODALITETER)

    ansatte: list[Ansatt] = []
    brukte_navn: set[str] = set()
    id_teller = 1

    def unikt_navn(gruppe: str) -> str:
        base = NAVN[gruppe][id_teller % len(NAVN[gruppe])]
        navn = base
        tall = 2
        while navn in brukte_navn:
            navn = f"{base} {tall}"
            tall += 1
        brukte_navn.add(navn)
        return navn

    for modality in aktive_modaliteter:
        antall = _pool_storrelse(timer[modality], natt.get(modality, 0.0), skift_defs)
        for _ in range(antall):
            ansatt = Ansatt(f"a{id_teller}", unikt_navn("radiograf"), {"radiograf", modality})
            if id_teller % 4 == 0:
                ansatt.unnga = {NATT}
            elif id_teller % 4 == 2:
                ansatt.foretrekker = {NATT}
            elif id_teller % 4 == 3:
                ansatt.foretrekker = {KVELD}
            ansatte.append(ansatt)
            id_teller += 1

    if timer.get("fagradiograf", 0) > 0:
        antall = _pool_storrelse(timer["fagradiograf"], natt.get("fagradiograf", 0.0), skift_defs)
        for i in range(antall):
            modalitet = aktive_modaliteter[i % len(aktive_modaliteter)] if aktive_modaliteter else "Røntgen"
            ansatt = Ansatt(f"a{id_teller}", unikt_navn("fagradiograf"), {"fagradiograf", modalitet})
            if id_teller % 4 == 0:
                ansatt.unnga = {NATT}
            elif id_teller % 4 == 2:
                ansatt.foretrekker = {NATT}
            elif id_teller % 4 == 3:
                ansatt.foretrekker = {KVELD}
            ansatte.append(ansatt)
            id_teller += 1

    return ansatte


def standard_bemanning(skift_defs: list[SkiftDef]) -> dict[str, dict[str, dict[str, int]]]:
    cfg: dict[str, dict[str, dict[str, int]]] = {}
    for d in skift_defs:
        rad: dict[str, dict[str, int]] = {}
        for komp, (hverdag, helg) in STANDARD_PER_SKIFT.items():
            if d.navn == "MELLOM":
                rad[komp] = {"hverdag": 1 if komp == "Røntgen" else 0, "helg": 0}
            else:
                rad[komp] = {"hverdag": hverdag, "helg": helg}
        cfg[d.navn] = rad
    return cfg


def skift_defs_for(langvakter: bool) -> list[SkiftDef]:
    from .skift_lager import skift_defs_for as _sdf

    return _sdf(langvakter)
