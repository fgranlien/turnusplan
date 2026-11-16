from __future__ import annotations

import json
import threading
import urllib.parse
import webbrowser
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import regler
from .demo_data import demo_ansatte, demo_behov, demo_behov_langvakt, skift_defs_for
from .generator import TurnusGenerator
from .ics_import import les_ics, les_ics_tekst
from .modeller import Skift

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
UKEDAGER = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]


def generer_json(start: date, antall_dager: int, langvakter: bool) -> dict:
    ansatte = demo_ansatte()
    behov = demo_behov_langvakt() if langvakter else demo_behov()
    defs = skift_defs_for(langvakter)
    plan = TurnusGenerator(ansatte, behov, start, antall_dager, defs, True).generer()
    med_id = {a.id: a for a in ansatte}

    dager = []
    for i in range(antall_dager):
        dato = start + timedelta(days=i)
        skift_rader = []
        for skift_def in defs:
            skift = Skift(dato, skift_def)
            bemanning = [
                {"navn": med_id[a_id].navn, "kompetanse": sorted(med_id[a_id].kompetanse)[0]}
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
                "kompetanse": sorted(a.kompetanse)[0],
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
                resultat = generer_json(start, dager, bool(data.get("langvakter")))
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


def start(port: int = 8765) -> None:
    server = None
    for p in range(port, port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            break
        except OSError:
            continue
    if server is None:
        raise SystemExit(f"Fant ingen ledig port fra {port}")
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"Turnusplan kjører på {url}  (Ctrl+C for å avslutte)")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
