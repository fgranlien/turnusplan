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

TARIFF_NORMER = {
    "lov": {"timer": 40.0, "navn": "Kun lovens maks (40 t)"},
    "standard": {"timer": 37.5, "navn": "Standard arbeidsuke (37,5 t)"},
    "spekter_35_5": {"timer": 35.5, "navn": "Spekter A2 pkt 1.3 (35,5 t)"},
    "helkontinuerlig": {"timer": 33.6, "navn": "Helkontinuerlig/sammenlignbart (33,6 t)"},
}


def _overlapper_20_06(skift_def: SkiftDef) -> bool:
    return skift_def.start_time < 6 or skift_def.slutt_time > 20


def turnus_kriterier(
    tildelinger: dict[str, list[Skift]],
    ansatte: list[Ansatt],
    start_dato: date,
    antall_dager: int,
    skift_defs: list[SkiftDef],
) -> list[str]:
    kriterier: list[str] = []
    if any(_overlapper_20_06(d) for d in skift_defs):
        kriterier.append("Turnusen har arbeid mellom kl. 20.00 og 06.00")
    uke_start = start_dato - timedelta(days=start_dato.weekday())
    antall_uker = (antall_dager + start_dato.weekday() + 6) // 7
    sondager = [uke_start + timedelta(days=7 * u + 6) for u in range(antall_uker)]
    relevante = [d for d in sondager if start_dato <= d < start_dato + timedelta(days=antall_dager)]
    if relevante:
        for skift_liste in tildelinger.values():
            arbeidet = sum(1 for d in relevante if any(s.dato == d for s in skift_liste))
            if 3 * arbeidet >= len(relevante):
                kriterier.append(f"S\u00f8ndagsarbeid minst hver 3. s\u00f8ndag ({arbeidet} av {len(relevante)} s\u00f8ndager)")
                break
    return kriterier


def tariff_sjekk(
    tildelinger: dict[str, list[Skift]],
    ansatte: list[Ansatt],
    start_dato: date,
    antall_dager: int,
    uke_time_norm: float,
) -> list[str]:
    brudd: list[str] = []
    if uke_time_norm >= MAKS_UKETIMER_NORMAL:
        return brudd
    uker = antall_dager / 7
    ansatt_med_id = {a.id: a for a in ansatte}
    for a_id, skift_liste in tildelinger.items():
        ansatt = ansatt_med_id[a_id]
        timer = sum(_timer(s) for s in skift_liste)
        snitt = timer / uker if uker else 0.0
        grense = uke_time_norm * ansatt.stillingsprosent / 100
        if snitt > grense + 1e-9:
            brudd.append(
                f"Tariff: {ansatt.navn} har snitt {snitt:.1f} t/uke over perioden "
                f"(norm {grense:.1f} t ved {ansatt.stillingsprosent:.0f} % stilling)"
            )
    return brudd


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


def skift_tilgang_ok(ansatt: Ansatt, skift_def: SkiftDef) -> bool:
    if not ansatt.skift_tilgang:
        return True
    return skift_def.navn.upper() in ansatt.skift_tilgang


def matcher(onsker: set[str], skift_def: SkiftDef) -> bool:
    if skift_def.navn.upper() in onsker:
        return True
    return "NATT" in onsker and skift_def.er_natt


_EPOCH_LORDAG = date(2020, 1, 4)


def sett_global_helgfrekvens(ansatte: list[Ansatt], n: int | None) -> None:
    """Sett helgefrekvens for alle som ikke har eget ønske (None = ingen endring)."""
    if n is None:
        return
    for ansatt in ansatte:
        if ansatt.helg_hver_n is None:
            ansatt.helg_hver_n = max(0, min(12, int(n)))


def sett_helg_offsatter(ansatte: list[Ansatt]) -> None:
    teller: dict[int, int] = {}
    for ansatt in sorted(ansatte, key=lambda a: a.id):
        n = ansatt.helg_hver_n
        if n is None or n <= 0:
            ansatt.helg_offset = 0
            continue
        ansatt.helg_offset = teller.get(n, 0) % n
        teller[n] = teller.get(n, 0) + 1


def helgfrekvens_ok(ansatt: Ansatt, dato: date) -> bool:
    if ansatt.helg_hver_n is None:
        return True
    if dato.weekday() < 5:
        return True
    if ansatt.helg_hver_n == 0:
        return False
    helg_nr = (dato - _EPOCH_LORDAG).days // 7
    return (helg_nr + ansatt.helg_offset) % ansatt.helg_hver_n == 0


def langvakt_uke_ok(ansatt: Ansatt, eksisterende: list[Skift], kandidat: Skift) -> bool:
    if ansatt.langvakt_uke_maks is None:
        return True
    uke_start = kandidat.dato - timedelta(days=kandidat.dato.weekday())
    uke_slutt = uke_start + UKELANGD
    antall = sum(
        1 for s in eksisterende
        if uke_start <= s.dato < uke_slutt and _timer(s) > MAKS_TIMER_PER_DOGN_UTVIDET
    )
    if _timer(kandidat) > MAKS_TIMER_PER_DOGN_UTVIDET:
        antall += 1
    return antall <= ansatt.langvakt_uke_maks


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
    if not skift_tilgang_ok(ansatt, kandidat.type):
        return False
    if not helgfrekvens_ok(ansatt, kandidat.dato):
        return False
    if not langvakt_avtale and _timer(kandidat) > MAKS_TIMER_PER_DOGN_UTVIDET:
        return False
    if not dognhvile_ok(eksisterende, kandidat):
        return False
    if not uketimer_ok(ansatt, eksisterende, kandidat):
        return False
    if not langvakt_uke_ok(ansatt, eksisterende, kandidat):
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


def maks_matching(plasser: list[str], personer: list[set[str]]) -> int:
    """Maksimal bipartitt matching (Kuhn): hvor mange plasser som kan fylles samtidig."""
    eier: dict[int, int] = {}

    def prov(p: int, sett: set[int]) -> bool:
        for i, kompetanse in enumerate(personer):
            if i in sett or plasser[p] not in kompetanse:
                continue
            sett.add(i)
            if i not in eier or prov(eier[i], sett):
                eier[i] = p
                return True
        return False

    return sum(1 for p in range(len(plasser)) if prov(p, set()))


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
        kategori = "helg" if dato.weekday() >= 5 else "hverdag"
        for skift_def in skift_defs:
            skift = Skift(dato, skift_def)
            krav_liste = [k for k in behov.get(kategori, {}).get(skift_def.navn, []) if k.antall > 0]
            if not krav_liste:
                continue
            tildelte = [a_id for a_id, skift_liste in tildelinger.items() if skift in skift_liste]
            for krav in krav_liste:
                kvalifiserte = {
                    a_id for a_id in tildelte
                    if krav.kompetanse in ansatt_med_id[a_id].kompetanse
                }
                if len(kvalifiserte) < krav.antall:
                    feil.append(
                        f"Dekning: {skift.etikett} {dato:%d.%m} mangler {krav.antall - len(kvalifiserte)} med kompetanse '{krav.kompetanse}'"
                    )
            totalt_behov = sum(k.antall for k in krav_liste)
            plasser = [k.kompetanse for k in krav_liste for _ in range(k.antall)]
            personer = [ansatt_med_id[a_id].kompetanse for a_id in tildelte]
            matchet = maks_matching(plasser, personer)
            if matchet < totalt_behov:
                feil.append(
                    f"Dekning: {skift.etikett} {dato:%d.%m} krever {totalt_behov} personer, "
                    f"men de tildelte kan bare fylle {matchet} plasser samtidig "
                    "(kompetansene overlapper – én person kan ikke fylle to krav på samme skift)"
                )

    for a_id, skift_liste in tildelinger.items():
        ansatt = ansatt_med_id[a_id]
        sortert = sorted(skift_liste)

        for skift in sortert:
            if not skift_tilgang_ok(ansatt, skift.type):
                feil.append(
                    f"Skifttilgang: {ansatt.navn} har skift {skift.etikett} {skift.dato:%d.%m} "
                    "utenfor sin tillatte skiftliste"
                )
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

        if ansatt.helg_hver_n is not None:
            rullering = "aldri helg" if ansatt.helg_hver_n == 0 else f"hver {ansatt.helg_hver_n}. helg"
            for s in sortert:
                if not helgfrekvens_ok(ansatt, s.dato):
                    feil.append(
                        f"Helgfrekvens: {ansatt.navn} har vakt i en helg utenfor sin rullering "
                        f"({rullering}) {s.dato:%d.%m}"
                    )

        if ansatt.langvakt_uke_maks is not None:
            for u in range(antall_dager // 7 + 2):
                ws = uke_start + timedelta(days=7 * u)
                lange = sum(
                    1 for s in sortert
                    if ws <= s.dato < ws + UKELANGD and _timer(s) > MAKS_TIMER_PER_DOGN_UTVIDET
                )
                if lange > ansatt.langvakt_uke_maks:
                    feil.append(
                        f"Langvaktstilvalg: {ansatt.navn} har {lange} 12-timersvakter i uke "
                        f"{ws.isocalendar()[1]} (tilvalg {ansatt.langvakt_uke_maks})"
                    )

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
