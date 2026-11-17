from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from .demo_data import MODALITETER, YRKESGRUPPER
from .lager import skriv_atomisk
from .modeller import Ansatt
from .regler import sett_helg_offsatter

FIL = Path(__file__).resolve().parent.parent / "ansatte.json"


class AnsattFeil(ValueError):
    pass


_RANGE_SKILLE = re.compile(r"\s*(?:til|/|\u2013|\u2014)\s*")


def _utvid_datoer(tekst: str) -> tuple[list[date], str | None]:
    deler = [d for d in _RANGE_SKILLE.split(tekst.strip()) if d]
    if not deler or len(deler) > 2:
        return [], tekst
    try:
        fra = date.fromisoformat(deler[0][:10])
        til = date.fromisoformat(deler[-1][:10]) if len(deler) == 2 else fra
    except ValueError:
        return [], tekst
    if til < fra:
        fra, til = til, fra
    if (til - fra).days > 400:
        return [], tekst
    return [fra + timedelta(days=i) for i in range((til - fra).days + 1)], None


def til_ansatt(rad: dict, indeks: int, brukte_ider: set[str]) -> tuple[Ansatt, list[str]]:
    advarsler: list[str] = []
    navn = str(rad.get("navn", "")).strip()
    if not navn:
        raise AnsattFeil(f"Ansatt nr. {indeks + 1}: navn mangler")
    gruppe = str(rad.get("yrkesgruppe", "")).strip().lower()
    if gruppe not in YRKESGRUPPER:
        raise AnsattFeil(f"{navn}: ukjent yrkesgruppe '{gruppe}'")
    modaliteter = sorted(set(rad.get("modaliteter") or []) & set(MODALITETER))
    if gruppe == "radiograf" and not modaliteter:
        raise AnsattFeil(f"{navn}: radiograf må ha minst én modalitet")
    if gruppe == "fagradiograf":
        if not modaliteter:
            raise AnsattFeil(f"{navn}: fagradiograf må ha en hovedmodalitet")
        if len(modaliteter) > 1:
            advarsler.append(f"{navn}: fagradiograf er knyttet til én modalitet – bruker {modaliteter[0]}")
            modaliteter = modaliteter[:1]
    try:
        prosent = float(rad.get("stillingsprosent", 100) or 100)
    except (TypeError, ValueError):
        prosent = 100.0
    prosent = max(10.0, min(100.0, prosent))
    foretrekker = {str(s).strip().upper() for s in (rad.get("foretrekker") or []) if str(s).strip()}
    unnga = {str(s).strip().upper() for s in (rad.get("unnga") or []) if str(s).strip()}
    raa_langvakt = rad.get("langvakt_uke_maks")
    if raa_langvakt is None or str(raa_langvakt).strip() == "":
        langvakt_maks = None
    else:
        try:
            langvakt_maks = max(0, min(7, int(raa_langvakt)))
        except (TypeError, ValueError):
            langvakt_maks = None
            advarsler.append(
                f"{navn}: ugjenkjennelig antall 12-timersvakter '{raa_langvakt}' (ignorerer tilvalget)"
            )
    raa_helg = rad.get("helg_hver_n")
    if raa_helg is None or str(raa_helg).strip() == "":
        helg_n = None
    else:
        try:
            helg_n = max(0, min(12, int(raa_helg)))
        except (TypeError, ValueError):
            helg_n = None
            advarsler.append(
                f"{navn}: ugjenkjennelig helgfrekvens '{raa_helg}' (ignorerer tilvalget)"
            )
    utilgjengelige: set[date] = set()
    for s in rad.get("utilgjengelige_dager") or []:
        datoer, feil = _utvid_datoer(str(s))
        if feil is not None:
            advarsler.append(f"{navn}: ugjenkjennelig dato '{s}' (hoppet over)")
        else:
            utilgjengelige.update(datoer)
    ansatt_id = str(rad.get("id") or "").strip()
    if not ansatt_id or ansatt_id in brukte_ider:
        teller = indeks + 1
        ansatt_id = f"a{teller}"
        while ansatt_id in brukte_ider:
            teller += 1
            ansatt_id = f"a{teller}"
    brukte_ider.add(ansatt_id)
    ansatt = Ansatt(
        ansatt_id,
        navn,
        {gruppe, *modaliteter},
        prosent,
        foretrekker,
        unnga,
        utilgjengelige,
        langvakt_maks,
        helg_n,
    )
    return ansatt, advarsler


def til_rad(a: Ansatt) -> dict:
    gruppe = "fagradiograf" if "fagradiograf" in a.kompetanse else "radiograf"
    return {
        "id": a.id,
        "navn": a.navn,
        "yrkesgruppe": gruppe,
        "modaliteter": sorted(a.kompetanse & set(MODALITETER)),
        "stillingsprosent": a.stillingsprosent,
        "foretrekker": sorted(a.foretrekker),
        "unnga": sorted(a.unnga),
        "utilgjengelige_dager": sorted(d.isoformat() for d in a.utilgjengelige_dager),
        "langvakt_uke_maks": a.langvakt_uke_maks,
        "helg_hver_n": a.helg_hver_n,
    }


def les_lagrede() -> list[Ansatt] | None:
    if not FIL.exists():
        return None
    try:
        data = json.loads(FIL.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(
            f"ADVARSEL: {FIL.name} kunne ikke leses ({e}) \u2013 bruker demopoolen i stedet.",
            file=sys.stderr,
        )
        return None
    if not isinstance(data, list) or not data:
        return None
    try:
        brukte: set[str] = set()
        return [til_ansatt(rad, i, brukte)[0] for i, rad in enumerate(data)]
    except AnsattFeil as e:
        print(
            f"ADVARSEL: {FIL.name} inneholder ugyldige ansattdata ({e}) \u2013 bruker demopoolen i stedet.",
            file=sys.stderr,
        )
        return None


def lagre(data: list) -> tuple[int, list[str]]:
    if not isinstance(data, list) or not data:
        raise AnsattFeil("Ansattlisten kan ikke være tom")
    ansatte: list[Ansatt] = []
    advarsler: list[str] = []
    brukte: set[str] = set()
    for i, rad in enumerate(data):
        if not isinstance(rad, dict):
            raise AnsattFeil(f"Ansatt nr. {i + 1}: ugyldig format")
        ansatt, adv = til_ansatt(rad, i, brukte)
        ansatte.append(ansatt)
        advarsler.extend(adv)
    sett_helg_offsatter(ansatte)
    navne_teller: dict[str, int] = {}
    for a in ansatte:
        navne_teller[a.navn] = navne_teller.get(a.navn, 0) + 1
    for navn, antall in navne_teller.items():
        if antall > 1:
            advarsler.append(
                f"{antall} ansatte heter '{navn}' \u2013 navn må være unike for låste vakter, vaktbytte og iCal-eksport."
            )
    rader = [til_rad(a) for a in ansatte]
    skriv_atomisk(FIL, json.dumps(rader, ensure_ascii=False, indent=2) + "\n")
    return len(ansatte), advarsler
