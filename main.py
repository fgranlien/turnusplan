#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date, timedelta

from turnus import regler
from turnus.demo_data import demo_ansatte, demo_behov, demo_behov_langvakt, skift_defs_for
from turnus.generator import TurnusGenerator
from turnus.modeller import Skift, SkiftDef

UKEDAGER = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Genererer lovlig turnusforslag (aml kap. 10)")
    parser.add_argument("--start", default="2025-03-03", help="Startdato (ÅÅÅÅ-MM-DD, må være mandag)")
    parser.add_argument("--dager", type=int, default=14, help="Antall dager i horisonten")
    parser.add_argument("--langvakter", action="store_true", help="Bruk 12-timers langvakter (dag 07-19, natt 19-07)")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    antall_dager = args.dager
    langvakt_avtale = True

    ansatte = demo_ansatte()
    behov = demo_behov_langvakt() if args.langvakter else demo_behov()
    skift_defs = skift_defs_for(args.langvakter)

    plan = TurnusGenerator(ansatte, behov, start, antall_dager, skift_defs, langvakt_avtale).generer()
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
        print(f"\n{UKEDAGER[dato.weekday()]} {dato:%d.%m}")
        for skift_def in skift_defs:
            skift = Skift(dato, skift_def)
            bemanning = []
            for a_id, skift_liste in plan.tildelinger.items():
                if skift in skift_liste:
                    a = ansatt_med_id[a_id]
                    kompetanse = sorted(a.kompetanse)[0]
                    bemanning.append(f"{a.navn} ({kompetanse})")
            mangler = sum(1 for s, _ in plan.udekket if s == skift)
            ekstra = f"  [MANGLER {mangler}]" if mangler else ""
            print(f"  {skift_def.navn:6} {', '.join(bemanning) or '-'}{ekstra}")

    print("\n" + "=" * 78)
    print("OPPSUMMERING PER ANSATT")
    print("=" * 78)
    print(f"{'Navn':<12} {'Komp.':<12} {'%':>4} {'Skift':>5} {'Timer':>6} {'Natt':>5}")
    for a in ansatte:
        skift_liste = sorted(plan.tildelinger[a.id])
        timer = sum(s.varighet.total_seconds() / 3600 for s in skift_liste)
        n = sum(1 for s in skift_liste if s.type.er_natt)
        print(
            f"{a.navn:<12} {sorted(a.kompetanse)[0]:<12} {a.stillingsprosent:>4.0f} "
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

    feil = regler.valider_plan(plan.tildelinger, ansatte, behov, start, antall_dager, skift_defs, langvakt_avtale)
    print("\n" + "=" * 78)
    print("VALIDERING MOT ARBEIDSMILJØLOVEN KAP. 10")
    print("=" * 78)
    if feil:
        for feil_melding in feil:
            print(f"  ✗ {feil_melding}")
    else:
        print("  ✓ Ingen brudd: døgnhvile (11 t), ukeshvile (35 t), uketimer (40 t),")
        print("    skiftlengde, natteserier (maks 4) og dekning av kompetansebehov er oppfylt.")


if __name__ == "__main__":
    main()
