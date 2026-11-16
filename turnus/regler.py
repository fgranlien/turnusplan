from __future__ import annotations

from datetime import date, datetime, timedelta

from .modeller import Ansatt, Krav, Skift, SkiftDef

MIN_DOGNHVILE = timedelta(hours=11)
MIN_UKESHVILE = timedelta(hours=35)
MAKS_TIMER_PER_DOGN = 9.0
MAKS_TIMER_PER_DOGN_UTVIDET = 10.0
MAKS_SKIFTLENGDE_MED_AVTALE = 12.0
MAKS_UKETIMER_NORMAL = 40.0
MAKS_NATTER_ONK = 4
UKELANGD = timedelta(days=7)


def _timer(skift: Skift) -> float:
    return skift.varighet.total_seconds() / 3600


def _midnatt(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time())


def dognhvile_ok(eksisterende: list[Skift], kandidat: Skift) -> bool:
    for skift in eksisterende:
        if skift.start - MIN_DOGNHVILE < kandidat.slutt and kandidat.start < skift.slutt + MIN_DOGNHVILE:
            return False
    return True


def ukeshvile_ok(alle_skift: list[Skift], uke_start: date) -> bool:
    uke_start_dt = _midnatt(uke_start)
    uke_slutt = uke_start_dt + UKELANGD
    vindu_start = uke_start_dt - UKELANGD
    vindu_slutt = uke_slutt + UKELANGD
    relevante = sorted(
        (s for s in alle_skift if s.slutt > vindu_start and s.start < vindu_slutt),
        key=lambda s: s.start,
    )
    forrige = vindu_start
    for skift in relevante:
        if skift.start > forrige:
            if _overlapper_uke(forrige, skift.start, uke_start_dt, uke_slutt) and skift.start - forrige >= MIN_UKESHVILE:
                return True
        forrige = max(forrige, skift.slutt)
    if vindu_slutt > forrige and _overlapper_uke(forrige, vindu_slutt, uke_start_dt, uke_slutt) and vindu_slutt - forrige >= MIN_UKESHVILE:
        return True
    return False


def _overlapper_uke(a: datetime, b: datetime, uke_start: datetime, uke_slutt: datetime) -> bool:
    return a < uke_slutt and b > uke_start


def uketimer_ok(ansatt: Ansatt, eksisterende: list[Skift], kandidat: Skift) -> bool:
    grense = MAKS_UKETIMER_NORMAL * ansatt.stillingsprosent / 100
    timer = _timer(kandidat)
    uke_start = _midnatt(kandidat.dato - timedelta(days=kandidat.dato.weekday()))
    uke_slutt = uke_start + UKELANGD
    for skift in eksisterende:
        if uke_start <= skift.start < uke_slutt:
            timer += _timer(skift)
    return timer <= grense + 1e-9


def natteserie_lengde(skift_liste: list[Skift], dato: date) -> int:
    natt_dager = {s.dato for s in skift_liste if s.type.er_natt}
    lengde = 0
    d = dato - timedelta(days=1)
    while d in natt_dager:
        lengde += 1
        d -= timedelta(days=1)
    return lengde


def kandidat_er_lovlig(
    ansatt: Ansatt,
    eksisterende: list[Skift],
    kandidat: Skift,
    langvakt_avtale: bool = True,
) -> bool:
    if kandidat.dato in ansatt.utilgjengelige_dager:
        return False
    if not langvakt_avtale and _timer(kandidat) > MAKS_TIMER_PER_DOGN_UTVIDET:
        return False
    if not dognhvile_ok(eksisterende, kandidat):
        return False
    if not uketimer_ok(ansatt, eksisterende, kandidat):
        return False
    if kandidat.type.er_natt and natteserie_lengde(eksisterende, kandidat.dato) >= MAKS_NATTER_ONK:
        return False
    uke_start = kandidat.dato - timedelta(days=kandidat.dato.weekday())
    plan_uke = eksisterende + [kandidat]
    for uke in (uke_start - UKELANGD, uke_start, uke_start + UKELANGD):
        if not ukeshvile_ok(plan_uke, uke):
            return False
    return True


def valider_vakter(
    vakter: list,
    stillingsprosent: float = 100.0,
    navn: str = "Ansatt",
    langvakt_avtale: bool = True,
) -> list[str]:
    feil: list[str] = []
    sortert = sorted(vakter, key=lambda v: v.start)
    if not sortert:
        return feil

    for v in sortert:
        t = v.varighet.total_seconds() / 3600
        if t > MAKS_SKIFTLENGDE_MED_AVTALE + 1e-9:
            feil.append(
                f"Skiftlengde: {v.etikett} {v.start:%d.%m} varer {t:.1f} t (over maks {MAKS_SKIFTLENGDE_MED_AVTALE:.0f} t)"
            )
        elif t > MAKS_TIMER_PER_DOGN_UTVIDET + 1e-9 and not langvakt_avtale:
            feil.append(
                f"Skiftlengde: {v.etikett} {v.start:%d.%m} varer {t:.1f} t uten avtale (maks {MAKS_TIMER_PER_DOGN_UTVIDET:.0f} t per aml §10-3)"
            )

    for a, b in zip(sortert, sortert[1:]):
        if not dognhvile_ok([a], b):
            feil.append(
                f"Døgnhvile: under 11 t mellom {a.etikett} ({a.start:%d.%m %H:%M}–{a.slutt:%d.%m %H:%M}) "
                f"og {b.etikett} ({b.start:%d.%m %H:%M})"
            )

    forste_uke = sortert[0].start.date() - timedelta(days=sortert[0].start.weekday())
    siste_dag = sortert[-1].slutt.date()
    antall_uker = (siste_dag - forste_uke).days // 7 + 1
    grense = MAKS_UKETIMER_NORMAL * stillingsprosent / 100
    for u in range(antall_uker + 1):
        ws = forste_uke + timedelta(days=7 * u)
        if not ukeshvile_ok(sortert, ws):
            feil.append(f"Ukeshvile: {navn} mangler 35 t sammenhengende hvile i uke {ws.isocalendar()[1]}")
        timer = sum(
            v.varighet.total_seconds() / 3600
            for v in sortert
            if _midnatt(ws) <= v.start < _midnatt(ws) + UKELANGD
        )
        if timer > grense + 1e-9:
            feil.append(
                f"Uketimer: {navn} har {timer:.1f} t i uke {ws.isocalendar()[1]} (grense {grense:.0f} t)"
            )

    natt = lambda v: v.slutt.date() > v.start.date()
    natt_dager = sorted({v.start.date() for v in sortert if natt(v)})
    lengde = 0
    forrige = None
    for d in natt_dager:
        lengde = lengde + 1 if forrige is not None and (d - forrige).days == 1 else 1
        if lengde > MAKS_NATTER_ONK:
            feil.append(f"Natteserie: {navn} har {lengde} nattarbeid i strekk (maks {MAKS_NATTER_ONK})")
        forrige = d

    dogn_grense = MAKS_SKIFTLENGDE_MED_AVTALE if langvakt_avtale else MAKS_TIMER_PER_DOGN
    timer_per_dogn: dict[date, float] = {}
    for v in sortert:
        timer_per_dogn[v.start.date()] = timer_per_dogn.get(v.start.date(), 0.0) + v.varighet.total_seconds() / 3600
    for d, t in timer_per_dogn.items():
        if t > dogn_grense + 1e-9:
            feil.append(
                f"Døgntimer: {navn} har {t:.1f} t arbeid den {d:%d.%m} (maks {dogn_grense:.0f} t)"
            )

    return feil


def valider_plan(
    tildelinger: dict[str, list[Skift]],
    ansatte: list[Ansatt],
    behov: dict[str, list[Krav]],
    start_dato: date,
    antall_dager: int,
    skift_defs: list[SkiftDef],
    langvakt_avtale: bool = True,
) -> list[str]:
    feil: list[str] = []
    ansatt_med_id = {a.id: a for a in ansatte}

    for i in range(antall_dager):
        dato = start_dato + timedelta(days=i)
        for skift_def in skift_defs:
            skift = Skift(dato, skift_def)
            for krav in behov.get(skift_def.navn, []):
                antall = sum(
                    1
                    for a_id, skift_liste in tildelinger.items()
                    if skift in skift_liste and krav.kompetanse in ansatt_med_id[a_id].kompetanse
                )
                if antall < krav.antall:
                    feil.append(
                        f"Dekning: {skift.etikett} {dato:%d.%m} mangler {krav.antall - antall} med kompetanse '{krav.kompetanse}'"
                    )

    for a_id, skift_liste in tildelinger.items():
        ansatt = ansatt_med_id[a_id]
        sortert = sorted(skift_liste)

        for skift in sortert:
            lengde = _timer(skift)
            if lengde > MAKS_SKIFTLENGDE_MED_AVTALE + 1e-9:
                feil.append(f"Skiftlengde: {ansatt.navn} har {lengde:.0f} t skift {skift.etikett} {skift.dato:%d.%m} (over maks {MAKS_SKIFTLENGDE_MED_AVTALE:.0f} t)")
            elif lengde > MAKS_TIMER_PER_DOGN_UTVIDET + 1e-9 and not langvakt_avtale:
                feil.append(f"Skiftlengde: {ansatt.navn} har {lengde:.0f} t skift {skift.etikett} {skift.dato:%d.%m} uten avtale (maks {MAKS_TIMER_PER_DOGN_UTVIDET:.0f} t per aml §10-3)")

        for a, b in zip(sortert, sortert[1:]):
            if not dognhvile_ok([a], b):
                feil.append(
                    f"Døgnhvile: {ansatt.navn} har under 11 t hvile mellom {a.etikett} {a.dato:%d.%m} og {b.etikett} {b.dato:%d.%m}"
                )

        uke_start = start_dato - timedelta(days=start_dato.weekday())
        for u in range(antall_dager // 7 + 2):
            ws = uke_start + timedelta(days=7 * u)
            if not ukeshvile_ok(sortert, ws):
                feil.append(f"Ukeshvile: {ansatt.navn} mangler 35 t sammenhengende hvile i uke {ws.isocalendar()[1]}")
            grense = MAKS_UKETIMER_NORMAL * ansatt.stillingsprosent / 100
            timer = sum(_timer(s) for s in sortert if _midnatt(ws) <= s.start < _midnatt(ws) + UKELANGD)
            if timer > grense + 1e-9:
                feil.append(f"Uketimer: {ansatt.navn} har {timer:.1f} t i uke {ws.isocalendar()[1]} (grense {grense:.0f} t)")

        natt_dager = sorted(s.dato for s in sortert if s.type.er_natt)
        lengde = 0
        forrige = None
        for d in natt_dager:
            lengde = lengde + 1 if forrige is not None and (d - forrige).days == 1 else 1
            if lengde > MAKS_NATTER_ONK:
                feil.append(f"Natteserie: {ansatt.navn} har {lengde} nattarbeid i strekk (maks {MAKS_NATTER_ONK})")
            forrige = d

        dogn_grense = MAKS_SKIFTLENGDE_MED_AVTALE if langvakt_avtale else MAKS_TIMER_PER_DOGN
        timer_per_dogn: dict[date, float] = {}
        for s in sortert:
            timer_per_dogn[s.dato] = timer_per_dogn.get(s.dato, 0.0) + _timer(s)
        for d, t in timer_per_dogn.items():
            if t > dogn_grense + 1e-9:
                feil.append(f"Døgntimer: {ansatt.navn} har {t:.1f} t den {d:%d.%m} (maks {dogn_grense:.0f} t)")

    return feil
