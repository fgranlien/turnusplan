#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date, timedelta

from turnus import regler
from turnus.demo_data import MODALITETER, bygg_ansatte, bygg_behov, skift_defs_for, standard_bemanning
from turnus.generator import TurnusGenerator
from turnus.ics_import import les_ics
from turnus.modeller import Skift, SkiftDef

UKEDAGER = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]


def valider_ics_fil(sti: str, stillingsprosent: float) -> None:
    vakter, merknader = les_ics(sti)
    print("=" * 78)
    print(f"VALIDERING AV EKSISTERENDE TURNUS: {sti}")
    print("=" * 78)

    if not vakter:
        print("\nIngen arbeidsvakter funnet i filen.")
        for m in merknader:
            print(f"  • {m}")
        return

    total_timer = sum(v.varighet.total_seconds() / 3600 for v in vakter)
    print(f"\nPeriode: {vakter[0].start:%d.%m.%Y} – {vakter[-1].slutt:%d.%m.%Y}")
    print(f"Arbeidsvakter: {len(vakter)}  |  Totalt: {total_timer:.1f} timer")

    print(f"\n{'Vakttype':<10} {'Antall':>6} {'Timer':>7} {'Kategori':>9}")
    typer: dict[str, list] = {}
    for v in vakter:
        typer.setdefault(v.etikett, []).append(v)
    for etikett, liste in sorted(typer.items()):
        timer = sum(v.varighet.total_seconds() / 3600 for v in liste)
        print(f"{etikett:<10} {len(liste):>6} {timer:>7.1f} {liste[0].kategori:>9}")

    fridager = sum(1 for m in merknader if "heldag" in m)
    if fridager:
        print(f"\nFridager (heldagshendelser): {fridager}")
    for m in merknader:
        if "heldag" not in m:
            print(f"  ⚠ {m}")

    feil = regler.valider_vakter(vakter, stillingsprosent, "Deg")
    print("\n" + "=" * 78)
    print(f"VALIDERING MOT ARBEIDSMILJØLOVEN KAP. 10 (stillingsprosent {stillingsprosent:.0f} %)")
    print("=" * 78)
    if feil:
        for f in feil:
            print(f"  ✗ {f}")
        print(f"\n  Totalt {len(feil)} mulig(e) lovbrudd – verifiser mot gjeldende avtaler.")
    else:
        print("  ✓ Ingen brudd funnet: døgnhvile (11 t), ukeshvile (35 t), uketimer (40 t),")
        print("    skiftlengde og kveld-/natteserier er innenfor grensene.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genererer lovlig turnusforslag (aml kap. 10)")
    parser.add_argument("--start", default="2025-03-03", help="Startdato (ÅÅÅÅ-MM-DD, må være mandag)")
    parser.add_argument("--dager", type=int, default=14, help="Antall dager i horisonten")
    parser.add_argument("--langvakter", action="store_true", help="Bruk 12-timers langvakter (dag 07-19, natt 19-07)")
    parser.add_argument("--gui", action="store_true", help="Start grafisk grensesnitt i nettleseren")
    parser.add_argument("--port", type=int, default=8765, help="Port for GUI-et (standard 8765)")
    parser.add_argument("--valider-fil", metavar="FIL.ICS", help="Valider en eksisterende turnus i iCal-format i stedet for å generere")
    parser.add_argument("--stillingsprosent", type=float, default=100.0, help="Stillingsprosent for validering (standard 100)")
    parser.add_argument("--maks-natter", type=int, default=3, choices=[1, 2, 3, 4], help="Maks nattarbeid i strekk (standard 3, unngår fire på rad; aml-tak 4)")
    parser.add_argument("--maks-kvelder", type=int, default=2, choices=[1, 2, 3, 4], help="Maks kveldsvakter i strekk (standard 2, unngår tre og fire på rad)")
    args = parser.parse_args()

    if args.gui:
        from turnus.webgui import start

        start(args.port)
        return

    if args.valider_fil:
        valider_ics_fil(args.valider_fil, args.stillingsprosent)
        return

    start = date.fromisoformat(args.start)
    antall_dager = args.dager
    langvakt_avtale = True

    skift_defs = skift_defs_for(args.langvakter)
    bemanning = standard_bemanning(skift_defs)
    behov = bygg_behov(bemanning, skift_defs)
    ansatte = bygg_ansatte(behov, skift_defs)

    plan = TurnusGenerator(ansatte, behov, start, antall_dager, skift_defs, langvakt_avtale, maks_natter=args.maks_natter, maks_kvelder=args.maks_kvelder).generer()
    ansatt_med_id = {a.id: a for a in ansatte}

    slutt = start + timedelta(days=antall_dager - 1)
    modus = "langvakter 12 t" if args.langvakter else "tredelt turnus 8 t"
    print("=" * 78)
    print(f"TURNUSFORSLAG  {start:%d.%m.%Y} – {slutt:%d.%m.%Y}  ({modus})")
    if args.langvakter:
        print("Vakter over 10 t forutsetter avtale/tariff etter aml §10-3 og §10-6.")
    print("=" * 78)

    for i in range(antall_dager):
        dato = start + timedelta(days=i)
        kategori = "helg" if dato.weekday() >= 5 else "hverdag"
        print(f"\n{UKEDAGER[dato.weekday()]} {dato:%d.%m}")
        for skift_def in skift_defs:
            if kategori not in skift_def.dager:
                continue
            skift = Skift(dato, skift_def)
            bemanning = []
            for a_id, skift_liste in plan.tildelinger.items():
                if skift in skift_liste:
                    a = ansatt_med_id[a_id]
                    yrkesgruppe = "FAGR" if "fagradiograf" in a.kompetanse else "rad"
                    modaliteter = "/".join(sorted(a.kompetanse & set(MODALITETER)))
                    bemanning.append(f"{a.navn} [{yrkesgruppe} {modaliteter}]")
            mangler = sum(1 for s, _ in plan.udekket if s == skift)
            ekstra = f"  [MANGLER {mangler}]" if mangler else ""
            print(f"  {skift_def.navn:6} {', '.join(bemanning) or '-'}{ekstra}")

    print("\n" + "=" * 78)
    print("OPPSUMMERING PER ANSATT")
    print("=" * 78)
    print(f"{'Navn':<14} {'Yrkesgruppe':<14} {'Modaliteter':<28} {'Skift':>5} {'Timer':>6} {'Natt':>5}")
    for a in ansatte:
        skift_liste = sorted(plan.tildelinger[a.id])
        timer = sum(s.varighet.total_seconds() / 3600 for s in skift_liste)
        n = sum(1 for s in skift_liste if s.type.er_natt)
        yrkesgruppe = "fagradiograf" if "fagradiograf" in a.kompetanse else "radiograf"
        modaliteter = ", ".join(sorted(a.kompetanse & set(MODALITETER)))
        print(
            f"{a.navn:<14} {yrkesgruppe:<14} {modaliteter:<28} "
            f"{len(skift_liste):>5} {timer:>6.0f} {n:>5}"
        )

    preferanser = 0
    relevante = 0
    for a in ansatte:
        for s in plan.tildelinger[a.id]:
            if TurnusGenerator._matcher(a.foretrekker, s):
                preferanser += 1
                relevante += 1
            elif TurnusGenerator._matcher(a.unnga, s):
                relevante += 1
    if relevante:
        andel = 100.0 * preferanser / relevante
        print(f"\nPreferanser: {preferanser} av {relevante} markerte ønsker innfridd ({andel:.0f} %)")

    if plan.udekket:
        print("\nUDEKKET BEHOV:")
        for skift, krav in plan.udekket:
            print(f"  {skift.etikett} {skift.dato:%d.%m}: mangler {krav.antall} '{krav.kompetanse}'")

    feil = regler.valider_plan(plan.tildelinger, ansatte, behov, start, antall_dager, skift_defs, langvakt_avtale, args.maks_natter, args.maks_kvelder)
    print("\n" + "=" * 78)
    print("VALIDERING MOT ARBEIDSMILJØLOVEN KAP. 10")
    print("=" * 78)
    if feil:
        for feil_melding in feil:
            print(f"  ✗ {feil_melding}")
    else:
        print("  ✓ Ingen brudd: døgnhvile (11 t), ukeshvile (35 t), uketimer (40 t),")
        print(f"    skiftlengde, kveldeserier (maks {args.maks_kvelder}), natteserier (maks {args.maks_natter})")
        print("    og dekning av kompetansebehov er oppfylt.")


if __name__ == "__main__":
    main()
