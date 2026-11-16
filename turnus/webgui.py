from __future__ import annotations

import json
import socket
import threading
import urllib.parse
import webbrowser
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import VERSJON, ansatte_lager, forvalg_lager, regler, skift_lager
from .demo_data import MODALITETER, bygg_ansatte, bygg_behov, standard_bemanning
from .ics_export import bygg_ics
from .modeller import SkiftDef
from .cpsat_generator import loes_med_cpsat, tilgjengelig as cpsat_tilgjengelig
from .generator import Plan, TurnusGenerator
from .ics_import import les_ics, les_ics_tekst
from .modeller import Skift

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
UKEDAGER = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]

_siste_eksport: dict[str, str] = {}
_siste_plan: dict | None = None


def generer_json(
    start: date,
    antall_dager: int,
    langvakter: bool,
    bemanning: dict | None = None,
    uke_time_norm: float = 40.0,
    skift_defs: list[SkiftDef] | None = None,
    rotasjon: bool = False,
    syklus_uker: int = 4,
    motor: str = "greedy",
) -> dict:
    defs = skift_defs if skift_defs is not None else skift_lager.skift_defs_for(langvakter)
    bemanning_cfg = standard_bemanning(defs)
    for skift_navn, skift_komp in (bemanning or {}).items():
        if skift_navn not in bemanning_cfg or not isinstance(skift_komp, dict):
            continue
        for komp, verdier in skift_komp.items():
            if komp not in bemanning_cfg[skift_navn] or not isinstance(verdier, dict):
                continue
            bemanning_cfg[skift_navn][komp] = {
                "hverdag": max(0, min(12, int(verdier.get("hverdag", 0)))),
                "helg": max(0, min(12, int(verdier.get("helg", 0)))),
            }
    behov = bygg_behov(bemanning_cfg, defs)
    lagrede = ansatte_lager.les_lagrede()
    if lagrede:
        ansatte = lagrede
        ansatte_kilde = "lagret"
    else:
        ansatte = bygg_ansatte(behov, defs)
        ansatte_kilde = "demo"
    rotasjon_arg = (syklus_uker * 7, len(defs)) if rotasjon and syklus_uker > 0 else None
    motor_brukt = "greedy"
    motor_status = ""
    motor_tid = None
    motor_merknad = ""
    if motor == "cpsat" and not rotasjon_arg:
        if not cpsat_tilgjengelig():
            motor_merknad = "ortools er ikke installert (pip3 install ortools) \u2013 bruker greedy."
        else:
            los = loes_med_cpsat(ansatte, behov, start, antall_dager, defs, uke_time_norm)
            if los is not None:
                motor_brukt = "cpsat"
                motor_status = los.status
                motor_tid = round(los.losningstid, 2)
                udekket_liste = _udekket_for(los.tildelinger, ansatte, behov, start, antall_dager, defs)
                plan = Plan(los.tildelinger, udekket_liste)
            else:
                motor_merknad = "CP-SAT fant ingen gjennomf\u00f8rbar l\u00f8sning innen tidsbegrensningen \u2013 bruker greedy."
    elif motor == "cpsat" and rotasjon_arg:
        motor_merknad = "Rotasjonsrullering st\u00f8ttes forel\u00f8pig bare av greedy-motoren."
    if motor_brukt == "greedy":
        plan = TurnusGenerator(ansatte, behov, start, antall_dager, defs, True, uke_time_norm, rotasjon_arg).generer()
    global _siste_plan
    _siste_plan = {
        "tildelinger": plan.tildelinger,
        "udekket": plan.udekket,
        "ansatte": ansatte,
        "behov": behov,
        "bemanning": bemanning_cfg,
        "start": start,
        "antall_dager": antall_dager,
        "defs": defs,
        "uke_time_norm": uke_time_norm,
        "rotasjon_arg": rotasjon_arg,
        "ansatte_kilde": ansatte_kilde,
    }
    motor_info = {"navn": motor_brukt, "status": motor_status, "tid": motor_tid, "merknad": motor_merknad}
    return _resultat_fra_plan(
        plan, ansatte, behov, bemanning_cfg, start, antall_dager, defs,
        uke_time_norm, rotasjon_arg, ansatte_kilde, motor_info=motor_info,
    )


def _resultat_fra_plan(
    plan,
    ansatte,
    behov,
    bemanning_cfg,
    start,
    antall_dager,
    defs,
    uke_time_norm,
    rotasjon_arg,
    ansatte_kilde,
    udekket=None,
    motor_info=None,
):
    if udekket is None:
        udekket = plan.udekket
    if motor_info is None:
        motor_info = {"navn": "greedy", "status": "", "tid": None, "merknad": ""}
    med_id = {a.id: a for a in ansatte}

    uke_start = start - timedelta(days=start.weekday())
    antall_uker = (antall_dager + start.weekday() + 6) // 7
    uker = [
        {
            "nr": u + 1,
            "iso": (uke_start + timedelta(days=7 * u)).isocalendar()[1],
            "start": (uke_start + timedelta(days=7 * u)).isoformat(),
        }
        for u in range(antall_uker)
    ]

    dager = []
    for i in range(antall_dager):
        dato = start + timedelta(days=i)
        kategori = "helg" if dato.weekday() >= 5 else "hverdag"
        skift_rader = []
        for skift_def in defs:
            if kategori not in skift_def.dager:
                continue
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
    for idx_a, a in enumerate(ansatte):
        skift_liste = sorted(plan.tildelinger[a.id])
        skift_per_dag = {s.dato: s for s in skift_liste}
        uke_rader = []
        for u in range(antall_uker):
            ws = uke_start + timedelta(days=7 * u)
            koder = []
            for d in range(7):
                dato = ws + timedelta(days=d)
                if start <= dato < start + timedelta(days=antall_dager):
                    s = skift_per_dag.get(dato)
                    koder.append(s.type.navn[0] if s else "")
                else:
                    koder.append(None)
            timer = sum(
                s.varighet.total_seconds() / 3600
                for s in skift_liste
                if ws <= s.dato < ws + timedelta(days=7)
            )
            uke_rader.append({"timer": round(timer, 1), "skift": koder})
        total_timer = sum(s.varighet.total_seconds() / 3600 for s in skift_liste)
        ansatt_rader.append(
            {
                "navn": a.navn,
                "yrkesgruppe": "fagradiograf" if "fagradiograf" in a.kompetanse else "radiograf",
                "modaliteter": sorted(a.kompetanse & set(MODALITETER)),
                "prosent": a.stillingsprosent,
                "skift": len(skift_liste),
                "timer": total_timer,
                "snitt_uke": round(total_timer / (antall_dager / 7), 1),
                "natt": sum(1 for s in skift_liste if s.type.er_natt),
                "uker": uke_rader,
                **({"rotasjonsgruppe": (idx_a % rotasjon_arg[1]) + 1} if rotasjon_arg else {}),
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
    kriterier = regler.turnus_kriterier(plan.tildelinger, ansatte, start, antall_dager, defs)
    tariff_brudd = regler.tariff_sjekk(plan.tildelinger, ansatte, start, antall_dager, uke_time_norm)

    maks_var = max(d.varighet.total_seconds() / 3600 for d in defs)
    modus = "langvakter 12 t" if maks_var > 10 else "8-timers turnus"
    if rotasjon_arg:
        modus += f" (rotasjonsrullering: {rotasjon_arg[1]} grupper, {rotasjon_arg[0] // 7} ukers syklus)"
    resultat = {
        "modus": modus,
        "bemanning": bemanning_cfg,
        "antall_ansatte": len(ansatte),
        "ansatte_kilde": ansatte_kilde,
        "periode": {
            "start": start.isoformat(),
            "slutt": (start + timedelta(days=antall_dager - 1)).isoformat(),
        },
        "rotasjon": {
            "aktiv": rotasjon_arg is not None,
            "syklus_uker": (rotasjon_arg[0] // 7) if rotasjon_arg else 0,
            "grupper": rotasjon_arg[1] if rotasjon_arg else 0,
        },
        "motor": motor_info,
        "dager": dager,
        "ansatte": ansatt_rader,
        "preferanser": {"innfridd": pref_innfridd, "totalt": pref_totalt},
        "uker": uker,
        "tariff": {
            "norm": uke_time_norm,
            "kriterier": kriterier,
            "brudd": tariff_brudd,
            "grunnlag": [
                "Spekter-overenskomsten del A2 pkt 1.3 (omr\u00e5de 10 \u2013 helseforetak, bl.a. Helse M\u00f8re og Romsdal): "
                "gjennomsnittlig 35,5 t/uke ved arbeid mellom kl. 20.00\u201306.00 og/eller s\u00f8ndagsarbeid minst hver 3. s\u00f8ndag, "
                "og ved d\u00f8gnkontinuerlig skiftarbeid.",
                "33,6 t/uke gjelder helkontinuerlig skiftarbeid og turnus sammenlignbart med dette "
                "(minst 539 t nattarbeid og 231 t s\u00f8ndagsarbeid per \u00e5r, jf. NITO-overenskomsten).",
                "Arbeidsmilj\u00f8loven \u00a7 10-2/10-3 (40 t) er lovfestet tak og gjelder uansett.",
            ],
        },
        "udekket": [
            {"skift": s.etikett, "dato": s.dato.isoformat(), "kompetanse": k.kompetanse}
            for s, k in udekket
        ],
        "validering": feil,
        "ics": bygg_ics(plan.tildelinger, ansatte, defs, f"Turnusforslag {start.isoformat()}")
    }

    _siste_eksport.clear()
    for a in ansatte:
        if not plan.tildelinger.get(a.id):
            continue
        _siste_eksport[a.navn] = bygg_ics(
            {a.id: plan.tildelinger[a.id]},
            [a],
            defs,
            f"Turnus {a.navn} {start.isoformat()}",
        )
    return resultat


def _udekket_for(tildelinger, ansatte, behov, start, antall_dager, defs) -> list:
    med_id = {a.id: a for a in ansatte}
    udekket = []
    for i in range(antall_dager):
        dato = start + timedelta(days=i)
        kat = "helg" if dato.weekday() >= 5 else "hverdag"
        for sd in defs:
            if kat not in sd.dager:
                continue
            skift = Skift(dato, sd)
            for krav in behov.get(kat, {}).get(sd.navn, []):
                antall = sum(
                    1 for aid, sl in tildelinger.items()
                    if skift in sl and krav.kompetanse in med_id[aid].kompetanse
                )
                for _ in range(max(0, krav.antall - antall)):
                    udekket.append((skift, krav))
    return udekket


def vaktbytte_json(navn_a: str, navn_b: str, dato_iso: str, skift_navn: str) -> dict:
    if not _siste_plan:
        raise ValueError("Generer en turnus først")
    ctx = _siste_plan
    dato = date.fromisoformat(dato_iso)
    if not ctx["start"] <= dato < ctx["start"] + timedelta(days=ctx["antall_dager"]):
        raise ValueError("Datoen er utenfor den genererte perioden")
    med_navn = {a.navn: a for a in ctx["ansatte"]}
    if navn_a not in med_navn or navn_b not in med_navn:
        raise ValueError("Ukjent ansatt")
    if navn_a == navn_b:
        raise ValueError("Velg to ulike ansatte")
    a, b = med_navn[navn_a], med_navn[navn_b]
    skift_def = next((d for d in ctx["defs"] if d.navn == skift_navn), None)
    if skift_def is None:
        raise ValueError(f"Ukjent skift '{skift_navn}'")
    kategori = "helg" if dato.weekday() >= 5 else "hverdag"
    if kategori not in skift_def.dager:
        raise ValueError(f"{skift_navn} går ikke den dagen")
    skift = Skift(dato, skift_def)

    liste_a = ctx["tildelinger"].get(a.id, [])
    liste_b = ctx["tildelinger"].get(b.id, [])
    if skift not in liste_a:
        raise ValueError(f"{a.navn} har ikke {skift_navn} {dato_iso}")
    skift_b = next((s for s in liste_b if s.dato == dato), None)

    if skift.dato in b.utilgjengelige_dager:
        raise ValueError(f"{b.navn} er utilgjengelig {dato_iso}")
    if skift_b is not None and skift_b.dato in a.utilgjengelige_dager:
        raise ValueError(f"{a.navn} er utilgjengelig {dato_iso}")

    ny_a = [s for s in liste_a if s != skift]
    ny_b = [s for s in liste_b if skift_b is None or s != skift_b]
    if skift_b is not None:
        ny_a.append(skift_b)
    ny_b.append(skift)

    nye_tildelinger = {aid: list(v) for aid, v in ctx["tildelinger"].items()}
    nye_tildelinger[a.id] = sorted(ny_a)
    nye_tildelinger[b.id] = sorted(ny_b)

    feil = regler.valider_plan(
        nye_tildelinger, ctx["ansatte"], ctx["behov"], ctx["start"],
        ctx["antall_dager"], ctx["defs"], True,
    )
    if feil:
        return {"ok": False, "brudd": feil}

    ctx["tildelinger"] = nye_tildelinger
    plan = Plan(dict(nye_tildelinger), list(ctx["udekket"]))
    resultat = _resultat_fra_plan(
        plan, ctx["ansatte"], ctx["behov"], ctx["bemanning"], ctx["start"],
        ctx["antall_dager"], ctx["defs"], ctx["uke_time_norm"],
        ctx["rotasjon_arg"], ctx["ansatte_kilde"], ctx["udekket"],
    )
    if skift_b is not None:
        melding = f"{navn_a} og {navn_b} byttet vakter {dato_iso}: {skift_navn} mot {skift_b.type.navn}"
    else:
        melding = f"{navn_b} overtok {skift_navn} {dato_iso} fra {navn_a}"
    return {"ok": True, "melding": melding, "resultat": resultat}


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
        sti = urllib.parse.urlsplit(self.path).path
        if sti == "/api/eksport":
            spørring = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            navn = spørring.get("navn", [""])[0]
            ics = _siste_eksport.get(navn)
            if not ics:
                self._send(404, b'{"feil": "Ingen generert turnus funnet for denne personen"}', "application/json; charset=utf-8")
                return
            filnavn = "".join(c if c.isalnum() else "_" for c in navn) or "ansatt"
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="turnus_{filnavn}.ics"')
            self.send_header("Content-Length", str(len(ics.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(ics.encode("utf-8"))
        elif sti in ("/", "/index.html"):
            self._send(200, (WEB_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif sti == "/api/ansatte":
            lagrede = ansatte_lager.les_lagrede()
            if lagrede:
                kilde = "lagret"
                rader = [ansatte_lager.til_rad(a) for a in lagrede]
            else:
                kilde = "demo"
                defs = skift_lager.skift_defs_for(False)
                pool = bygg_ansatte(bygg_behov(standard_bemanning(defs), defs), defs)
                rader = [ansatte_lager.til_rad(a) for a in pool]
            resultat = {"kilde": kilde, "modaliteter": MODALITETER, "ansatte": rader}
            self._send(200, json.dumps(resultat, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        elif sti == "/api/forvalg":
            resultat = {"forvalg": forvalg_lager.les_alle()}
            self._send(200, json.dumps(resultat, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        elif sti == "/api/skift":
            lagrede = skift_lager.les_lagrede()
            defs = lagrede or skift_lager.standard()
            resultat = {
                "kilde": "lagret" if lagrede else "standard",
                "versjon": VERSJON,
                "skift": [skift_lager.til_rad(d) for d in defs],
            }
            self._send(200, json.dumps(resultat, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
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
                norm = float(data.get("uke_time_norm", 40) or 40)
                norm = max(20.0, min(40.0, norm))
                skift_defs = skift_lager.parse_liste(data["skift"]) if data.get("skift") else None
                resultat = generer_json(
                    start, dager, bool(data.get("langvakter")), data.get("bemanning"), norm, skift_defs,
                    bool(data.get("rotasjon")), int(data.get("syklus_uker", 4) or 4),
                    str(data.get("motor", "greedy")),
                )
            elif self.path == "/api/skift":
                data = json.loads(kropp)
                antall, defs = skift_lager.lagre(data)
                resultat = {"ok": True, "antall": antall, "skift": [skift_lager.til_rad(d) for d in defs]}
            elif self.path == "/api/forvalg":
                data = json.loads(kropp)
                profil = forvalg_lager.lagre(data)
                resultat = {"ok": True, "navn": profil["navn"], "antall": len(forvalg_lager.les_alle())}
            elif self.path == "/api/forvalg/last":
                data = json.loads(kropp)
                navn = str(data.get("navn", "")).strip()
                profil = forvalg_lager.les(navn)
                if not profil:
                    self._send(404, json.dumps({"feil": f"Fant ikke forvalg '{navn}'"}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                    return
                skift = profil.get("skift")
                if isinstance(skift, list) and skift:
                    skift_lager.lagre(skift)
                ansatte = profil.get("ansatte")
                if isinstance(ansatte, list) and ansatte:
                    ansatte_lager.lagre(ansatte)
                resultat = {"ok": True, "profil": profil}
            elif self.path == "/api/vaktbytte":
                data = json.loads(kropp)
                resultat = vaktbytte_json(
                    str(data.get("navn_a", "")).strip(),
                    str(data.get("navn_b", "")).strip(),
                    str(data.get("dato", "")).strip(),
                    str(data.get("skift", "")).strip(),
                )
            elif self.path == "/api/ansatte":
                data = json.loads(kropp)
                antall, advarsler = ansatte_lager.lagre(data)
                resultat = {"ok": True, "antall": antall, "advarsler": advarsler}
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

    def do_DELETE(self) -> None:
        sti = urllib.parse.urlsplit(self.path).path
        if sti == "/api/forvalg":
            spørring = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            navn = spørring.get("navn", [""])[0].strip()
            if not navn:
                self._send(400, json.dumps({"feil": "navn må oppgis"}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                return
            slettet = forvalg_lager.slett(navn)
            self._send(200, json.dumps({"ok": slettet}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        else:
            self._send(404, b"ikke funnet", "text/plain; charset=utf-8")

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
