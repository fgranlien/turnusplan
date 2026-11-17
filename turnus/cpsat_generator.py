from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta

from . import regler
from .modeller import Ansatt, Krav, Skift, SkiftDef

PREF_BONUS = 2.0
UNNGA_STRAFF = 3.0
FAGRA_MODALITET_STRAFF = 1.5
AVVIK_VEKT = 0.1
NATT_BALANSE_VEKT = 0.2
SLAKK_STRAFF = 1000.0
TIDSBEGRENSNING = 30.0
RANDOM_SEED = 42


class Losning:
    def __init__(
        self,
        tildelinger: dict[str, list[Skift]],
        status: str,
        losningstid: float,
        udekket: list[tuple[Skift, Krav]] | None = None,
        laaste_feilet: list[str] | None = None,
    ):
        self.tildelinger = tildelinger
        self.status = status
        self.losningstid = losningstid
        self.udekket = udekket or []
        self.laaste_feilet = laaste_feilet or []


def tilgjengelig() -> bool:
    try:
        from ortools.sat.python import cp_model  # noqa: F401
    except ImportError:
        return False
    return True


def loes_med_cpsat(
    ansatte: list[Ansatt],
    behov: dict[str, list[Krav]],
    start: date,
    antall_dager: int,
    skift_defs: list[SkiftDef],
    uke_time_norm: float = 40.0,
    tidsbegrensning: float = TIDSBEGRENSNING,
    laaste: list[tuple[str, Skift]] | None = None,
) -> Losning | None:
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return None

    datoer = [start + timedelta(days=i) for i in range(antall_dager)]
    datoer_set = set(datoer)
    kategori = {d: ("helg" if d.weekday() >= 5 else "hverdag") for d in datoer}
    combos = [(d, sd) for d in datoer for sd in skift_defs if kategori[d] in sd.dager]
    defs_med_navn = {sd.navn: sd for sd in skift_defs}

    model = cp_model.CpModel()

    x: dict[tuple[str, date, str], object] = {}
    for a in ansatte:
        for d, sd in combos:
            if d in a.utilgjengelige_dager:
                continue
            if not regler.helgfrekvens_ok(a, d):
                continue
            if not regler.skift_tilgang_ok(a, sd):
                continue
            x[a.id, d, sd.navn] = model.NewBoolVar(f"x_{a.id}_{d.isoformat()}_{sd.navn}")

    for a in ansatte:
        for d in datoer:
            v = [x[a.id, d, sd.navn] for sd in skift_defs if (a.id, d, sd.navn) in x]
            if len(v) > 1:
                model.Add(sum(v) <= 1)

    plasser: dict[tuple[date, str], list[Krav]] = {}
    for d, sd in combos:
        krav_liste = [k for k in behov.get(kategori[d], {}).get(sd.navn, []) if k.antall > 0]
        utvidet: list[Krav] = []
        for krav in krav_liste:
            utvidet.extend([krav] * krav.antall)
        if utvidet:
            plasser[(d, sd.navn)] = utvidet

    y: dict[tuple[str, date, str, int], object] = {}
    slakk: dict[tuple[date, str, int], tuple[object, Krav]] = {}
    fagra_straff: list = []
    for (d, sd_navn), krav_plasser in plasser.items():
        for p, krav in enumerate(krav_plasser):
            kvalifiserte = [
                a for a in ansatte
                if (a.id, d, sd_navn) in x and krav.kompetanse in a.kompetanse
            ]
            s_var = model.NewBoolVar(f"slakk_{d.isoformat()}_{sd_navn}_{p}")
            slakk[(d, sd_navn, p)] = (s_var, krav)
            y_vars = []
            for a in kvalifiserte:
                v = model.NewBoolVar(f"y_{a.id}_{d.isoformat()}_{sd_navn}_{p}")
                y[a.id, d, sd_navn, p] = v
                y_vars.append(v)
                if "fagradiograf" in a.kompetanse and krav.kompetanse != "fagradiograf":
                    fagra_straff.append(int(FAGRA_MODALITET_STRAFF * 10) * v)
            if y_vars:
                model.Add(sum(y_vars) + s_var == 1)
            else:
                model.Add(s_var == 1)

    for a in ansatte:
        for d, sd in combos:
            if (a.id, d, sd.navn) not in x:
                continue
            ys = [
                y[a.id, d, sd.navn, p]
                for p in range(len(plasser.get((d, sd.navn), [])))
                if (a.id, d, sd.navn, p) in y
            ]
            if ys:
                model.Add(x[a.id, d, sd.navn] == sum(ys))
            else:
                model.Add(x[a.id, d, sd.navn] == 0)

    laaste_feilet: list[str] = []
    for ansatt_id, skift in (laaste or []):
        nokkel = (ansatt_id, skift.dato, skift.type.navn)
        ansatt = next((a for a in ansatte if a.id == ansatt_id), None)
        navn = ansatt.navn if ansatt else ansatt_id
        krav_plasser = plasser.get((skift.dato, skift.type.navn), [])
        if nokkel not in x:
            laaste_feilet.append(
                f"L\u00e5st vakt avvist: {navn} kan ikke ha {skift.type.navn} {skift.dato:%d.%m} "
                "(frav\u00e6r, helgrullering eller skift-tilgang)"
            )
            continue
        if not krav_plasser:
            laaste_feilet.append(
                f"L\u00e5st vakt avvist: {skift.type.navn} {skift.dato:%d.%m} har ingen bemanningsbehov"
            )
            continue
        if ansatt is None or not any(k.kompetanse in ansatt.kompetanse for k in krav_plasser):
            laaste_feilet.append(
                f"L\u00e5st vakt avvist: {navn} mangler kompetanse for {skift.type.navn} {skift.dato:%d.%m}"
            )
            continue
        model.Add(x[nokkel] == 1)

    for a in ansatte:
        for i in range(antall_dager - 1):
            d1, d2 = datoer[i], datoer[i + 1]
            for sd1 in skift_defs:
                if (a.id, d1, sd1.navn) not in x:
                    continue
                slutt1 = datetime.combine(d1, time()) + timedelta(hours=sd1.slutt_time)
                for sd2 in skift_defs:
                    if (a.id, d2, sd2.navn) not in x:
                        continue
                    start2 = datetime.combine(d2, time()) + timedelta(hours=sd2.start_time)
                    if start2 - slutt1 < regler.MIN_DOGNHVILE:
                        model.Add(x[a.id, d1, sd1.navn] + x[a.id, d2, sd2.navn] <= 1)

    uker_start = start - timedelta(days=start.weekday())
    antall_uker = (antall_dager + start.weekday() + 6) // 7

    for a in ansatte:
        for u in range(antall_uker):
            ws = uker_start + timedelta(days=7 * u)
            ws_dt = datetime.combine(ws, time())
            uke_slutt_dt = ws_dt + timedelta(days=7)
            hvile_lengde = regler.MIN_UKESHVILE
            kandidater = [ws_dt]
            for dd, sd in combos:
                if (a.id, dd, sd.navn) in x:
                    kandidater.append(datetime.combine(dd, time()) + timedelta(hours=sd.slutt_time))
            zs = []
            for t in kandidater:
                if t >= uke_slutt_dt or t + hvile_lengde <= ws_dt:
                    continue
                z = model.NewBoolVar(f"hvile_{a.id}_{u}_{t.isoformat()}")
                for dd, sd in combos:
                    if (a.id, dd, sd.navn) not in x:
                        continue
                    s_start = datetime.combine(dd, time()) + timedelta(hours=sd.start_time)
                    s_slutt = datetime.combine(dd, time()) + timedelta(hours=sd.slutt_time)
                    if s_start < t + hvile_lengde and s_slutt > t:
                        model.Add(z <= 1 - x[a.id, dd, sd.navn])
                zs.append(z)
            model.Add(sum(zs) >= 1)

    for a in ansatte:
        for i in range(antall_dager - regler.MAKS_NATTER_ONK):
            vindu = []
            for j in range(i, i + regler.MAKS_NATTER_ONK + 1):
                d = datoer[j]
                vindu.extend(
                    x[a.id, d, sd.navn]
                    for (dd, sd) in combos
                    if dd == d and sd.er_natt and (a.id, d, sd.navn) in x
                )
            if vindu:
                model.Add(sum(vindu) <= regler.MAKS_NATTER_ONK)

    total_behov_minutter = sum(
        int(defs_med_navn[sd_navn].varighet.total_seconds() // 60) * len(krav_plasser)
        for (_d, sd_navn), krav_plasser in plasser.items()
    )
    sum_prosent = sum(a.stillingsprosent for a in ansatte) or 1.0

    obj: list = []
    for a in ansatte:
        grense = round(regler.MAKS_UKETIMER_NORMAL * a.stillingsprosent / 100 * 60)
        total_minutter: list = []
        for u in range(antall_uker):
            ws = uker_start + timedelta(days=7 * u)
            uke_vars = []
            for j in range(7):
                d = ws + timedelta(days=j)
                if d not in datoer_set:
                    continue
                for sd in skift_defs:
                    if kategori[d] not in sd.dager:
                        continue
                    if (a.id, d, sd.navn) in x:
                        minutter = int(sd.varighet.total_seconds() // 60)
                        uke_vars.append(minutter * x[a.id, d, sd.navn])
            if uke_vars:
                model.Add(sum(uke_vars) <= grense)
            total_minutter.extend(uke_vars)
        mal = round(uke_time_norm * a.stillingsprosent / 100 * 60 * antall_dager / 7)
        if total_minutter:
            model.Add(sum(total_minutter) <= mal)
        if total_behov_minutter > 0:
            mal_andel = round(total_behov_minutter * a.stillingsprosent / sum_prosent)
            avvik = model.NewIntVar(0, max(mal_andel, mal), f"avvik_{a.id}")
            if total_minutter:
                model.Add(avvik >= sum(total_minutter) - mal_andel)
                model.Add(avvik >= mal_andel - sum(total_minutter))
            else:
                model.Add(avvik == mal_andel)
            obj.append(int(AVVIK_VEKT * 10) * avvik)

    for a in ansatte:
        if a.langvakt_uke_maks is None:
            continue
        for u in range(antall_uker):
            ws = uker_start + timedelta(days=7 * u)
            lange = []
            for j in range(7):
                d = ws + timedelta(days=j)
                if d not in datoer_set:
                    continue
                for sd in skift_defs:
                    if (
                        kategori[d] in sd.dager
                        and sd.varighet.total_seconds() / 3600 > regler.MAKS_TIMER_PER_DOGN_UTVIDET
                        and (a.id, d, sd.navn) in x
                    ):
                        lange.append(x[a.id, d, sd.navn])
            if lange:
                model.Add(sum(lange) <= a.langvakt_uke_maks)

    for a in ansatte:
        for d, sd in combos:
            v = x.get((a.id, d, sd.navn))
            if v is None:
                continue
            if regler.matcher(a.foretrekker, sd):
                obj.append(-int(PREF_BONUS * 10) * v)
            if regler.matcher(a.unnga, sd):
                obj.append(int(UNNGA_STRAFF * 10) * v)

    natt_vars_liste = []
    for a in ansatte:
        natt_vars = [
            x[a.id, d, sd.navn]
            for (d, sd) in combos
            if sd.er_natt and (a.id, d, sd.navn) in x
        ]
        n = model.NewIntVar(0, antall_dager, f"n_{a.id}")
        model.Add(n == sum(natt_vars) if natt_vars else n == 0)
        natt_vars_liste.append(n)
    nmax = model.NewIntVar(0, antall_dager, "nmax")
    for n in natt_vars_liste:
        model.Add(n <= nmax)
    obj.append(int(NATT_BALANSE_VEKT * 10) * nmax)
    obj.extend(fagra_straff)
    obj.extend(int(SLAKK_STRAFF * 10) * s for s, _ in slakk.values())

    model.Minimize(sum(obj))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = tidsbegrensning
    solver.parameters.num_search_workers = os.cpu_count() or 1
    solver.parameters.random_seed = RANDOM_SEED
    status = solver.Solve(model)
    losningstid = solver.WallTime()

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    tildelinger: dict[str, list[Skift]] = {a.id: [] for a in ansatte}
    for a in ansatte:
        for d, sd in combos:
            v = x.get((a.id, d, sd.navn))
            if v is not None and solver.Value(v):
                tildelinger[a.id].append(Skift(d, sd))

    udekket = [
        (Skift(d, defs_med_navn[sd_navn]), krav)
        for (d, sd_navn, _p), (s_var, krav) in slakk.items()
        if solver.Value(s_var)
    ]

    status_navn = "optimal" if status == cp_model.OPTIMAL else "gjennomf\u00f8rbar"
    return Losning(tildelinger, status_navn, losningstid, udekket, laaste_feilet)
