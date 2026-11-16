from __future__ import annotations

import json
import socket
import threading
import urllib.parse
import webbrowser
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import regler
from .demo_data import MODALITETER, bygg_ansatte, bygg_behov, skift_defs_for, standard_bemanning
from .generator import TurnusGenerator
from .ics_import import les_ics, les_ics_tekst
from .modeller import Skift

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
UKEDAGER = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]


def generer_json(start: date, antall_dager: int, langvakter: bool, bemanning: dict | None = None) -> dict:
    defs = skift_defs_for(langvakter)
    bemanning_cfg = standard_bemanning()
    for komp, verdier in (bemanning or {}).items():
        if komp in bemanning_cfg:
            bemanning_cfg[komp] = {
                "hverdag": max(0, min(12, int(verdier.get("hverdag", bemanning_cfg[komp]["hverdag"])))),
                "helg": max(0, min(12, int(verdier.get("helg", bemanning_cfg[komp]["helg"])))),
            }
    behov = bygg_behov(bemanning_cfg, defs)
    ansatte = bygg_ansatte(behov, defs)
    plan = TurnusGenerator(ansatte, behov, start, antall_dager, defs, True).generer()
    med_id = {a.id: a for a in ansatte}

    dager = []
    for i in range(antall_dager):
        dato = start + timedelta(days=i)
        skift_rader = []
        for skift_def in defs:
            skift = Skift(dato, skift_def)
            bemanning = [
                {
                    "navn": med_id[a_id].navn,
                    "yrkesgruppe": "fagradiograf" if "fagradiograf" in med_id[a_id].kompetanse else "radiograf",
                    "modaliteter": sorted(med_id[a_id].kompetanse & set(MODALITETER)),
                }
                for a_id, skift_liste in plan.tildelinger.items()
                if skift in skift_liste
            ]
            mangler = sum(1 for s, _ in plan.udekket if s == skift)
            skift_rader.append({"navn": skift_def.navn, "bemanning": bemanning, "mangler": mangler})
        dager.append(
            {"dato": dato.isoformat(), "ukedag": UKEDAGER[dato.weekday()], "skift": skift_rader}
        )

    ansatt_rader = []
    for a in ansatte:
        skift_liste = sorted(plan.tildelinger[a.id])
        ansatt_rader.append(
            {
                "navn": a.navn,
                "yrkesgruppe": "fagradiograf" if "fagradiograf" in a.kompetanse else "radiograf",
                "modaliteter": sorted(a.kompetanse & set(MODALITETER)),
                "prosent": a.stillingsprosent,
                "skift": len(skift_liste),
                "timer": sum(s.varighet.total_seconds() / 3600 for s in skift_liste),
                "natt": sum(1 for s in skift_liste if s.type.er_natt),
            }
        )

    pref_innfridd = pref_totalt = 0
    for a in ansatte:
        for s in plan.tildelinger[a.id]:
            if TurnusGenerator._matcher(a.foretrekker, s):
                pref_innfridd += 1
                pref_totalt += 1
            elif TurnusGenerator._matcher(a.unnga, s):
                pref_totalt += 1

    feil = regler.valider_plan(plan.tildelinger, ansatte, behov, start, antall_dager, defs, True)

    return {
        "modus": "langvakter 12 t" if langvakter else "tredelt turnus 8 t",
        "bemanning": bemanning_cfg,
        "antall_ansatte": len(ansatte),
        "periode": {
            "start": start.isoformat(),
            "slutt": (start + timedelta(days=antall_dager - 1)).isoformat(),
        },
        "dager": dager,
        "ansatte": ansatt_rader,
        "preferanser": {"innfridd": pref_innfridd, "totalt": pref_totalt},
        "udekket": [
            {"skift": s.etikett, "dato": s.dato.isoformat(), "kompetanse": k.kompetanse}
            for s, k in plan.udekket
        ],
        "validering": feil,
    }


def valider_json(tekst: str, filnavn: str, stillingsprosent: float) -> dict:
    vakter, merknader = les_ics_tekst(tekst)
    if not vakter:
        return {"fil": filnavn, "vakter": 0, "merknader": merknader, "feil": [], "typer": {}}
    typer: dict[str, dict] = {}
    for v in vakter:
        rad = typer.setdefault(v.etikett, {"antall": 0, "timer": 0.0, "kategori": v.kategori})
        rad["antall"] += 1
        rad["timer"] += v.varighet.total_seconds() / 3600
    return {
        "fil": filnavn,
        "vakter": len(vakter),
        "timer": sum(v.varighet.total_seconds() / 3600 for v in vakter),
        "periode": {"start": vakter[0].start.isoformat(), "slutt": vakter[-1].slutt.isoformat()},
        "typer": typer,
        "merknader": merknader,
        "feil": regler.valider_vakter(vakter, stillingsprosent, "Deg"),
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, kode: int, innhold: bytes, type_: str) -> None:
        self.send_response(kode)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(innhold)))
        self.end_headers()
        self.wfile.write(innhold)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send(200, (WEB_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
        else:
            self._send(404, b"ikke funnet", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        lengde = int(self.headers.get("Content-Length", 0))
        kropp = self.rfile.read(lengde)
        try:
            if self.path == "/api/generer":
                data = json.loads(kropp)
                start = date.fromisoformat(data["start"])
                dager = max(1, min(int(data.get("dager", 14)), 84))
                resultat = generer_json(start, dager, bool(data.get("langvakter")), data.get("bemanning"))
            elif self.path.startswith("/api/valider"):
                spørring = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                filnavn = spørring.get("filnavn", ["turnus.ics"])[0]
                prosent = float(spørring.get("prosent", ["100"])[0])
                resultat = valider_json(kropp.decode("utf-8-sig", errors="replace"), filnavn, prosent)
            else:
                self._send(404, b'{"feil": "ukjent endepunkt"}', "application/json; charset=utf-8")
                return
            self._send(200, json.dumps(resultat, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        except Exception as e:
            melding = json.dumps({"feil": str(e)}, ensure_ascii=False).encode("utf-8")
            self._send(400, melding, "application/json; charset=utf-8")

    def log_message(self, *args) -> None:
        pass


ADRESSE_KANDIDATER = (
    ("127.0.0.1", socket.AF_INET),
    ("::1", socket.AF_INET6),
    ("", socket.AF_INET),
)


def start(port: int = 8765) -> None:
    server = None
    url = None
    sistefeil: Exception | None = None
    for adresse, familie in ADRESSE_KANDIDATER:
        for p in range(port, port + 20):
            try:
                ThreadingHTTPServer.address_family = familie
                server = ThreadingHTTPServer((adresse, p), Handler)
                url = f"http://[{adresse}]:{p}" if familie == socket.AF_INET6 else f"http://{adresse or 'localhost'}:{p}"
                break
            except OSError as e:
                sistefeil = e
                if p == port:
                    print(f"Port {p} på '{adresse or 'alle grensesnitt'}' utilgjengelig: {e}")
        if server is not None:
            break
    if server is None:
        raise SystemExit(
            f"Fant ingen ledig adresse/port fra {port}. Siste feil: {sistefeil}\n"
            f"Sjekk om gamle instanser kjører: lsof -nP -iTCP:{port}-{port + 19} -sTCP:LISTEN\n"
            f"Eller start på en annen port: ./run.sh --gui --port 9000"
        )
    if server.server_address[0] not in ("127.0.0.1", "::1"):
        print("MERK: Serveren lytter på alle lokale grensesnitt (kunne ikke binde loopback).")
    print(f"Turnusplan kjører på {url}  (Ctrl+C for å avslutte)")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
