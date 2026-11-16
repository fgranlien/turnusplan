from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .modeller import Krav, NATT, Skift, SkiftDef
from .modeller import Ansatt
from . import regler

PREF_BONUS = 2.0
UNNGA_STRAFF = 3.0
FAGRA_MODALITET_STRAFF = 1.5
RETTFERDIGHET_VEKT = 0.3
NATT_BALANSE_VEKT = 0.2
TIDSRENSNING = 30.0


class Losning:
    def __init__(self, tildelinger: dict[str, list[Skift]], status: str, losningstid: float):
        self.tildelinger = tildelinger
        self.status = status
        self.losningstid = losningstid


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
    tidsbegrensning: float = TIDSRENSNING,
) -> Losning | None:
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return None

    datoer = [start + timedelta(days=i) for i in range(antall_dager)]
    datoer_set = set(datoer)
    kategori = {d: ("helg" if d.weekday() >= 5 else "hverdag") for d in datoer}
    combos = [(d, sd) for d in datoer for sd in skift_defs if kategori[d] in sd.dager]

    model = cp_model.CpModel()
    x: dict[tuple[str, date, str], object] = {}
    for a in ansatte:
        for d, sd in combos:
            if d in a.utilgjengelige_dager:
                continue
            x[a.id, d, sd.navn] = model.NewBoolVar(f"x_{a.id}_{d.isoformat()}_{sd.navn}")

    def vars_for(a: Ansatt, d: date) -> list:
        return [x[a.id, dd, sd.navn] for (dd, sd) in combos if dd == d and (a.id, d, sd.navn) in x]

    for a in ansatte:
        for d in datoer:
            v = vars_for(a, d)
            if len(v) > 1:
                model.Add(sum(v) <= 1)

    for d in datoer:
        for sd in skift_defs:
            if kategori[d] not in sd.dager:
                continue
            for krav in behov.get(kategori[d], {}).get(sd.navn, []):
                if krav.antall <= 0:
                    continue
                v = [
                    x[a.id, d, sd.navn]
                    for a in ansatte
                    if (a.id, d, sd.navn) in x and krav.kompetanse in a.kompetanse
                ]
                if v:
                    model.Add(sum(v) >= krav.antall)

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
            par_vars = []
            for j in range(7):
                d1 = ws + timedelta(days=j)
                d2 = ws + timedelta(days=j + 1)
                if d1 not in datoer_set or d2 not in datoer_set:
                    continue
                b = model.NewBoolVar(f"fri_{a.id}_{d1.isoformat()}")
                for v in vars_for(a, d1) + vars_for(a, d2):
                    model.Add(b <= 1 - v)
                par_vars.append(b)
            if par_vars:
                model.Add(sum(par_vars) >= 1)

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

    for a in ansatte:
        grense = uke_time_norm * a.stillingsprosent / 100
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
                model.Add(sum(uke_vars) <= round(grense * 60))

    def matcher(onsker: set[SkiftDef], sd: SkiftDef) -> bool:
        return sd in onsker or (NATT in onsker and sd.er_natt)

    def har_fagra_krav(d: date, sd: SkiftDef) -> bool:
        krav_liste = behov.get(kategori[d], {}).get(sd.navn, [])
        return any(k.kompetanse == "fagradiograf" for k in krav_liste)

    obj = []
    for a in ansatte:
        for d, sd in combos:
            v = x.get((a.id, d, sd.navn))
            if v is None:
                continue
            if matcher(a.foretrekker, sd):
                obj.append(int(PREF_BONUS * 10) * v)
            if matcher(a.unnga, sd):
                obj.append(-int(UNNGA_STRAFF * 10) * v)
            if "fagradiograf" in a.kompetanse and not har_fagra_krav(d, sd):
                obj.append(-int(FAGRA_MODALITET_STRAFF * 10) * v)

    tvars = []
    nvars = []
    for a in ansatte:
        alle = [x[a.id, d, sd.navn] for (d, sd) in combos if (a.id, d, sd.navn) in x]
        t = model.NewIntVar(0, len(combos), f"t_{a.id}")
        model.Add(t == sum(alle) if alle else t == 0)
        tvars.append(t)
        natt_vars = [
            x[a.id, d, sd.navn]
            for (d, sd) in combos
            if sd.er_natt and (a.id, d, sd.navn) in x
        ]
        n = model.NewIntVar(0, antall_dager, f"n_{a.id}")
        model.Add(n == sum(natt_vars) if natt_vars else n == 0)
        nvars.append(n)
    tmax = model.NewIntVar(0, len(combos), "tmax")
    for t in tvars:
        model.Add(t <= tmax)
    nmax = model.NewIntVar(0, antall_dager, "nmax")
    for n in nvars:
        model.Add(n <= nmax)
    mal = [int(RETTFERDIGHET_VEKT * 10) * tmax, int(NATT_BALANSE_VEKT * 10) * nmax]
    if obj:
        model.Minimize(sum(mal) - sum(obj))
    else:
        model.Minimize(sum(mal))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = tidsbegrensning
    solver.parameters.num_search_workers = 8
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

    status_navn = "optimal" if status == cp_model.OPTIMAL else "gjennomførbar"
    return Losning(tildelinger, status_navn, losningstid)
