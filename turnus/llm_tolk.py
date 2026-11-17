from __future__ import annotations

import json
import os
import urllib.request
from datetime import date, timedelta

OLLAMA_URL = "http://127.0.0.1:11434"
STANDARD_MODELL = os.environ.get("TURNUS_OLLAMA_MODELL", "llama3.1")
TOLK_TIMEOUT = 120
STATUS_TIMEOUT = 2
MAKS_FRITEKST = 4000
MAKS_FRAVAER_DAGER = 366

TALLFELT: dict[str, tuple[int, int]] = {
    "langvakt_uke_maks": (0, 7),
    "helg_hver_n": (0, 12),
}
LISTEFELT = ("foretrekker", "unnga", "skift_tilgang")
TILLATTE_FELT = LISTEFELT + ("utilgjengelige_dager",) + tuple(TALLFELT) + ("stillingsprosent",)


def ollama_status() -> dict:
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=STATUS_TIMEOUT) as svar:
            data = json.loads(svar.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {"tilgjengelig": False, "modeller": [], "standard": STANDARD_MODELL, "feil": str(e)}
    modeller = sorted(m.get("name", "") for m in data.get("models", []) if m.get("name"))
    return {"tilgjengelig": True, "modeller": modeller, "standard": STANDARD_MODELL, "feil": None}


def bygg_prompt(fritekst: str, ansatt: dict, skift_navn: list[str], modaliteter: list[str]) -> list[dict]:
    skift_tekst = ", ".join(skift_navn)
    modal_tekst = ", ".join(modaliteter) or "(ingen)"
    naaverende = {
        "foretrekker": sorted(ansatt.get("foretrekker") or []),
        "unnga": sorted(ansatt.get("unnga") or []),
        "utilgjengelige_dager": list(ansatt.get("utilgjengelige_dager") or []),
        "langvakt_uke_maks": ansatt.get("langvakt_uke_maks"),
        "helg_hver_n": ansatt.get("helg_hver_n"),
        "skift_tilgang": sorted(ansatt.get("skift_tilgang") or []),
        "stillingsprosent": ansatt.get("stillingsprosent"),
    }
    system = (
        "Du er en assistent for turnusplanlegging på en radiologisk avdeling i Norge. "
        "Du oversetter frie ønsker fra én ansatt til strukturerte JSON-felter. "
        "Svar KUN med ett JSON-objekt, uten forklaringstekst. Tillatte felter:\n"
        "- foretrekker, unnga, skift_tilgang: lister av skiftnavn (nøyaktig disse: " + skift_tekst + ")\n"
        "- utilgjengelige_dager: liste av ISO-datoer (ÅÅÅÅ-MM-DD) eller objekter {\"fra\": \"ÅÅÅÅ-MM-DD\", \"til\": \"ÅÅÅÅ-MM-DD\"}\n"
        "- langvakt_uke_maks: antall 12-timersvakter per uke (heltall 0-7, 0 = aldri)\n"
        "- helg_hver_n: jobber helg hver N. helg (heltall 0-12, 0 = aldri helg, 3 = hver tredje)\n"
        "- stillingsprosent: heltall 10-100\n"
        "Skift-tilgang betyr at den ansatte KUN kan jobbe de oppgitte skiftene. "
        "Utelat felter som ikke nevnes eller kan utledes av ønsket. Modaliteter som finnes: " + modal_tekst + "."
    )
    bruker = (
        f"Ansatt: {ansatt.get('navn', '?')}. Nåværende verdier: {json.dumps(naaverende, ensure_ascii=False)}\n"
        f"Ønsker: {fritekst}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": bruker}]


def _skift_navn_fra(verdi, skift_navn: list[str], felt: str, advarsler: list[str]) -> list[str]:
    lavt = {s.lower(): s for s in skift_navn}
    ut: list[str] = []
    for v in verdi if isinstance(verdi, list) else []:
        navn = lavt.get(str(v).strip().lower())
        if navn and navn not in ut:
            ut.append(navn)
        elif not navn:
            advarsler.append(f"{felt}: ukjent skiftnavn '{v}' ble utelatt (gyldige: {', '.join(skift_navn)})")
    return ut


def _datoer_fra(verdi, advarsler: list[str]) -> list[str]:
    ut: list[str] = []
    for v in verdi if isinstance(verdi, list) else []:
        try:
            if isinstance(v, dict):
                fra = date.fromisoformat(str(v["fra"]))
                til = date.fromisoformat(str(v["til"]))
                if til < fra:
                    fra, til = til, fra
                d = fra
                while d <= til and len(ut) < MAKS_FRAVAER_DAGER:
                    if d.isoformat() not in ut:
                        ut.append(d.isoformat())
                    d += timedelta(days=1)
            else:
                d = date.fromisoformat(str(v).strip())
                if d.isoformat() not in ut:
                    ut.append(d.isoformat())
        except (KeyError, ValueError, TypeError):
            advarsler.append(f"utilgjengelige_dager: ugyldig dato '{v}' ble utelatt")
    if len(ut) >= MAKS_FRAVAER_DAGER:
        advarsler.append(f"utilgjengelige_dager: begrenset til {MAKS_FRAVAER_DAGER} dager")
    return sorted(ut)


def saniter(data: dict, skift_navn: list[str], modaliteter: list[str]) -> tuple[dict, list[str]]:
    felter: dict = {}
    advarsler: list[str] = []
    if not isinstance(data, dict):
        return {}, ["Svaret fra modellen var ikke et JSON-objekt"]
    for nokkel, verdi in data.items():
        if nokkel not in TILLATTE_FELT:
            advarsler.append(f"Ukjent felt '{nokkel}' ble utelatt")
            continue
        if nokkel in ("foretrekker", "unnga", "skift_tilgang"):
            felter[nokkel] = _skift_navn_fra(verdi, skift_navn, nokkel, advarsler)
        elif nokkel == "utilgjengelige_dager":
            felter[nokkel] = _datoer_fra(verdi, advarsler)
        elif nokkel in TALLFELT:
            lav, hoy = TALLFELT[nokkel]
            try:
                tall = int(verdi)
            except (TypeError, ValueError):
                advarsler.append(f"{nokkel}: ugyldig verdi '{verdi}' ble utelatt")
                continue
            if not lav <= tall <= hoy:
                advarsler.append(f"{nokkel}: {tall} er utenfor {lav}-{hoy}, ble utelatt")
                continue
            felter[nokkel] = tall
        elif nokkel == "stillingsprosent":
            try:
                prosent = float(verdi)
            except (TypeError, ValueError):
                advarsler.append(f"stillingsprosent: ugyldig verdi '{verdi}' ble utelatt")
                continue
            if not 10 <= prosent <= 100:
                advarsler.append(f"stillingsprosent: {prosent} er utenfor 10-100, ble utelatt")
                continue
            felter[nokkel] = prosent
    for nokkel in list(felter):
        if not felter[nokkel] and nokkel != "stillingsprosent":
            del felter[nokkel]
    return felter, advarsler


def tolk(
    fritekst: str,
    ansatt: dict,
    skift_navn: list[str],
    modaliteter: list[str],
    modell: str | None = None,
) -> dict:
    fritekst = (fritekst or "").strip()
    if not fritekst:
        raise ValueError("Skriv inn ønsker i tekstfeltet først")
    if len(fritekst) > MAKS_FRITEKST:
        raise ValueError(f"Teksten er for lang (maks {MAKS_FRITEKST} tegn)")
    status = ollama_status()
    if not status["tilgjengelig"]:
        raise ValueError(
            "Fant ingen Ollama-tjener på 127.0.0.1:11434. "
            "Start Ollama og last ned en modell (f.eks. 'ollama pull llama3.1')."
        )
    valgt = modell or status["standard"]
    if status["modeller"] and valgt not in status["modeller"]:
        kandidat = next((m for m in status["modeller"] if m.split(":")[0] == valgt.split(":")[0]), None)
        valgt = kandidat or status["modeller"][0]
    nyttelast = {
        "model": valgt,
        "messages": bygg_prompt(fritekst, ansatt, skift_navn, modaliteter),
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(nyttelast).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TOLK_TIMEOUT) as svar:
            data = json.loads(svar.read().decode("utf-8"))
    except OSError as e:
        raise ValueError(f"Klarte ikke å snakke med Ollama: {e}") from e
    innhold = (data.get("message") or {}).get("content", "")
    try:
        tolket = json.loads(innhold)
    except json.JSONDecodeError as e:
        raise ValueError(f"Modellen svarte ikke med gyldig JSON: {innhold[:200]}") from e
    felter, advarsler = saniter(tolket, skift_navn, modaliteter)
    if not felter:
        raise ValueError(
            "Modellen fant ingen relevante felter. Omformuler ønsket, f.eks. "
            "'ikke natt', 'helg hver tredje' eller 'fravær 1. til 14. juli 2025'."
        )
    return {"felter": felter, "advarsler": advarsler, "modell": valgt}
