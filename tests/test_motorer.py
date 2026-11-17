from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from turnus import ansatte_lager, cpsat_generator, regler
from turnus.demo_data import bygg_behov
from turnus.generator import TurnusGenerator
from turnus.modeller import Ansatt, Skift, SkiftDef

DAG = SkiftDef("DAG", 7, 15)
KVELD = SkiftDef("KVELD", 15, 23)
NATT = SkiftDef("NATT", 23, 31, er_natt=True)
DAG12 = SkiftDef("DAG12", 7, 19)
NATT12 = SkiftDef("NATT12", 19, 31, er_natt=True)

START = date(2025, 3, 3)


def radiograf(navn: str, modaliteter: set[str], **kwargs) -> Ansatt:
    return Ansatt(f"a_{navn}", navn, {"radiograf", *modaliteter}, **kwargs)


def fagradiograf(navn: str, hovedmodalitet: str, **kwargs) -> Ansatt:
    return Ansatt(f"a_{navn}", navn, {"fagradiograf", hovedmodalitet}, **kwargs)


def standard_ansatte_8t() -> list[Ansatt]:
    ansatte = [fagradiograf("Fagra", "R\u00f8ntgen")]
    for i in range(1, 8):
        ansatte.append(radiograf(f"Rad{i}", {"R\u00f8ntgen"}))
    return ansatte


def behov_8t() -> dict:
    bemanning = {
        "DAG": {"fagradiograf": {"hverdag": 1, "helg": 0}, "R\u00f8ntgen": {"hverdag": 2, "helg": 1}},
        "KVELD": {"R\u00f8ntgen": {"hverdag": 1, "helg": 0}},
        "NATT": {"R\u00f8ntgen": {"hverdag": 1, "helg": 0}},
    }
    return bygg_behov(bemanning, [DAG, KVELD, NATT])


def behov_12t() -> dict:
    bemanning = {
        "DAG12": {"R\u00f8ntgen": {"hverdag": 1, "helg": 1}},
        "NATT12": {"R\u00f8ntgen": {"hverdag": 1, "helg": 1}},
    }
    return bygg_behov(bemanning, [DAG12, NATT12])


def ansatte_12t(antall: int = 7, **kwargs) -> list[Ansatt]:
    return [radiograf(f"Rad{i}", {"R\u00f8ntgen"}, **kwargs) for i in range(1, antall + 1)]


class MotorerTest(unittest.TestCase):
    def sjekk_begge(self, ansatte, behov, defs, dager, norm=40.0, laaste=None):
        greedy = TurnusGenerator(
            ansatte, behov, START, dager, defs, True, norm, None, laaste
        ).generer()
        feil_greedy = regler.valider_plan(greedy.tildelinger, ansatte, behov, START, dager, defs, True)
        self.assertEqual(feil_greedy, [])

        los = cpsat_generator.loes_med_cpsat(
            ansatte, behov, START, dager, defs, norm, tidsbegrensning=25.0, laaste=laaste
        )
        self.assertIsNotNone(los)
        feil_cpsat = regler.valider_plan(los.tildelinger, ansatte, behov, START, dager, defs, True)
        self.assertEqual(feil_cpsat, [])
        return greedy, los

    @unittest.skipUnless(cpsat_generator.tilgjengelig(), "ortools er ikke installert")
    def test_begge_motorer_gyldig_8t(self):
        greedy, los = self.sjekk_begge(standard_ansatte_8t(), behov_8t(), [DAG, KVELD, NATT], 14)
        self.assertEqual(greedy.udekket, [])
        self.assertEqual(los.udekket, [])

    @unittest.skipUnless(cpsat_generator.tilgjengelig(), "ortools er ikke installert")
    def test_begge_motorer_gyldig_12t_snittnorm(self):
        ansatte = ansatte_12t()
        greedy, los = self.sjekk_begge(ansatte, behov_12t(), [DAG12, NATT12], 28, norm=35.5)
        self.assertEqual(greedy.udekket, [])
        self.assertEqual(los.udekket, [])
        for a in ansatte:
            for u in range(4):
                ws = START + timedelta(days=7 * u)
                timer = sum(
                    s.varighet.total_seconds() / 3600
                    for s in los.tildelinger[a.id]
                    if ws <= s.dato < ws + timedelta(days=7)
                )
                self.assertLessEqual(timer, 40.0 + 1e-9)

    @unittest.skipUnless(cpsat_generator.tilgjengelig(), "ortools er ikke installert")
    def test_fagradiograf_teller_ikke_dobbelt(self):
        ansatte = [fagradiograf("Fagra", "R\u00f8ntgen"), radiograf("CT1", {"CT"})]
        bemanning = {
            "DAG": {
                "fagradiograf": {"hverdag": 1, "helg": 0},
                "R\u00f8ntgen": {"hverdag": 1, "helg": 0},
                "CT": {"hverdag": 1, "helg": 0},
            }
        }
        behov = bygg_behov(bemanning, [DAG])
        greedy = TurnusGenerator(ansatte, behov, START, 5, [DAG]).generer()
        fagra = ansatte[0]
        antall_fagra_dag1 = sum(1 for s in greedy.tildelinger[fagra.id] if s.dato == START)
        self.assertLessEqual(antall_fagra_dag1, 1)
        self.assertTrue(any(k.kompetanse == "R\u00f8ntgen" for _, k in greedy.udekket))

        los = cpsat_generator.loes_med_cpsat(ansatte, behov, START, 5, [DAG], tidsbegrensning=15.0)
        self.assertIsNotNone(los)
        antall_fagra_dag1 = sum(1 for s in los.tildelinger[fagra.id] if s.dato == START)
        self.assertLessEqual(antall_fagra_dag1, 1)
        self.assertTrue(any(k.kompetanse == "R\u00f8ntgen" for _, k in los.udekket))
        feil = regler.valider_plan(los.tildelinger, ansatte, behov, START, 5, [DAG], True)
        self.assertTrue(any("R\u00f8ntgen" in f for f in feil))

    @unittest.skipUnless(cpsat_generator.tilgjengelig(), "ortools er ikke installert")
    def test_laaste_vakter_cpsat(self):
        ansatte = standard_ansatte_8t()
        behov = behov_8t()
        laast = (ansatte[1].id, Skift(START + timedelta(days=2), NATT))
        greedy = TurnusGenerator(ansatte, behov, START, 14, [DAG, KVELD, NATT], laaste=[laast]).generer()
        self.assertIn(laast[1], greedy.tildelinger[ansatte[1].id])

        los = cpsat_generator.loes_med_cpsat(
            ansatte, behov, START, 14, [DAG, KVELD, NATT], tidsbegrensning=25.0, laaste=[laast]
        )
        self.assertIsNotNone(los)
        self.assertEqual(los.laaste_feilet, [])
        self.assertIn(laast[1], los.tildelinger[ansatte[1].id])

    @unittest.skipUnless(cpsat_generator.tilgjengelig(), "ortools er ikke installert")
    def test_laaste_ulovlig_vakt_avvises_cpsat(self):
        ansatte = standard_ansatte_8t()
        ansatte[1].utilgjengelige_dager = {START + timedelta(days=2)}
        behov = behov_8t()
        laast = (ansatte[1].id, Skift(START + timedelta(days=2), NATT))
        los = cpsat_generator.loes_med_cpsat(
            ansatte, behov, START, 14, [DAG, KVELD, NATT], tidsbegrensning=25.0, laaste=[laast]
        )
        self.assertIsNotNone(los)
        self.assertEqual(len(los.laaste_feilet), 1)

    @unittest.skipUnless(cpsat_generator.tilgjengelig(), "ortools er ikke installert")
    def test_langvakt_tilvalg_cpsat(self):
        ansatte = ansatte_12t(6, langvakt_uke_maks=1)
        los = cpsat_generator.loes_med_cpsat(
            ansatte, behov_12t(), START, 14, [DAG12, NATT12], tidsbegrensning=25.0
        )
        self.assertIsNotNone(los)
        for a in ansatte:
            for u in range(2):
                ws = START + timedelta(days=7 * u)
                lange = sum(
                    1 for s in los.tildelinger[a.id]
                    if ws <= s.dato < ws + timedelta(days=7) and s.varighet.total_seconds() / 3600 > 10
                )
                self.assertLessEqual(lange, 1)

    @unittest.skipUnless(cpsat_generator.tilgjengelig(), "ortools er ikke installert")
    def test_helg_hver_n_aldri_cpsat(self):
        ansatte = ansatte_12t(6, helg_hver_n=0)
        los = cpsat_generator.loes_med_cpsat(
            ansatte, behov_12t(), START, 14, [DAG12, NATT12], tidsbegrensning=25.0
        )
        self.assertIsNotNone(los)
        for a in ansatte:
            for s in los.tildelinger[a.id]:
                self.assertLess(s.dato.weekday(), 5)

    @unittest.skipUnless(cpsat_generator.tilgjengelig(), "ortools er ikke installert")
    def test_preferanser_paa_navn_inkl_mellomvakt(self):
        mellom = SkiftDef("MELLOM", 11.5, 19, dager=("hverdag",))
        ansatte = [radiograf("Mellomfan", {"R\u00f8ntgen"}, foretrekker={"MELLOM"})]
        for i in range(1, 4):
            ansatte.append(radiograf(f"Rad{i}", {"R\u00f8ntgen"}))
        bemanning = {"MELLOM": {"R\u00f8ntgen": {"hverdag": 1, "helg": 0}}, "NATT": {"R\u00f8ntgen": {"hverdag": 1, "helg": 0}}}
        behov = bygg_behov(bemanning, [mellom, NATT])
        greedy = TurnusGenerator(ansatte, behov, START, 7, [mellom, NATT]).generer()
        self.assertTrue(greedy.tildelinger[ansatte[0].id])
        for s in greedy.tildelinger[ansatte[0].id]:
            self.assertEqual(s.type.navn, "MELLOM")

        los = cpsat_generator.loes_med_cpsat(ansatte, behov, START, 7, [mellom, NATT], tidsbegrensning=15.0)
        self.assertIsNotNone(los)
        egne = los.tildelinger[ansatte[0].id]
        self.assertTrue(any(s.type.navn == "MELLOM" for s in egne))

    def test_natt_onske_gjelder_alle_nattskift(self):
        self.assertTrue(regler.matcher({"NATT"}, NATT12))
        self.assertTrue(regler.matcher({"NATT12"}, NATT12))
        self.assertFalse(regler.matcher({"NATT"}, DAG12))
        self.assertTrue(regler.matcher({"DAG"}, DAG))

    @unittest.skipUnless(cpsat_generator.tilgjengelig(), "ortools er ikke installert")
    def test_skift_tilgang_kombinerer_grupper(self):
        gruppe_a = [
            radiograf(f"Dag{i}", {"R\u00f8ntgen"}, skift_tilgang={"DAG", "KVELD"}, helg_hver_n=3)
            for i in range(1, 4)
        ]
        gruppe_b = [
            radiograf(f"Lang{i}", {"R\u00f8ntgen"}, skift_tilgang={"DAG12", "NATT12"}, helg_hver_n=5)
            for i in range(1, 4)
        ]
        ansatte = gruppe_a + gruppe_b
        regler.sett_helg_offsatter(ansatte)
        bemanning = {
            "DAG": {"R\u00f8ntgen": {"hverdag": 1, "helg": 1}},
            "NATT12": {"R\u00f8ntgen": {"hverdag": 1, "helg": 0}},
        }
        behov = bygg_behov(bemanning, [DAG, KVELD, NATT, DAG12, NATT12])
        greedy, los = self.sjekk_begge(ansatte, behov, [DAG, KVELD, NATT, DAG12, NATT12], 14)
        for motor, tildelinger in (("greedy", greedy.tildelinger), ("cpsat", los.tildelinger)):
            for a in gruppe_a:
                for s in tildelinger[a.id]:
                    self.assertFalse(s.type.er_natt, f"{motor}: {a.navn} fikk nattskift {s}")
                    self.assertNotIn(s.type.navn, ("NATT", "NATT12"), f"{motor}: {a.navn} fikk {s.type.navn}")
            for a in gruppe_b:
                for s in tildelinger[a.id]:
                    self.assertIn(s.type.navn, ("DAG12", "NATT12"), f"{motor}: {a.navn} fikk {s.type.navn}")

    def test_skift_tilgang_valideres(self):
        a = radiograf("KunDag", {"R\u00f8ntgen"}, skift_tilgang={"DAG"})
        plan = {a.id: [Skift(START, NATT)]}
        feil = regler.valider_plan(plan, [a], {}, START, 1, [DAG, NATT])
        self.assertTrue(any("Skifttilgang" in f for f in feil))
        self.assertFalse(regler.kandidat_er_lovlig(a, [], Skift(START, NATT)))
        self.assertTrue(regler.kandidat_er_lovlig(a, [], Skift(START, DAG)))

    @unittest.skipUnless(cpsat_generator.tilgjengelig(), "ortools er ikke installert")
    def test_ukeshvile_40t_hvile_cpsat(self):
        a = radiograf("Ana", {"R\u00f8ntgen"})
        b = radiograf("Bora", {"R\u00f8ntgen"})
        ansatte = [a, b]
        bemanning = {"DAG": {"R\u00f8ntgen": {"hverdag": 1, "helg": 1}}}
        behov = bygg_behov(bemanning, [DAG])
        laaste = [
            (a.id, Skift(START + timedelta(days=d), DAG)) for d in (0, 1, 2, 3, 5, 7, 8, 9, 10, 12)
        ]
        los = cpsat_generator.loes_med_cpsat(
            ansatte, behov, START, 14, [DAG], 40.0, tidsbegrensning=25.0, laaste=laaste
        )
        self.assertIsNotNone(los)
        self.assertEqual(los.laaste_feilet, [])
        self.assertEqual(regler.valider_plan(los.tildelinger, ansatte, behov, START, 14, [DAG], True), [])

    @unittest.skipUnless(cpsat_generator.tilgjengelig(), "ortools er ikke installert")
    def test_rettferdig_fordeling_stillingsprosent_cpsat(self):
        a = radiograf("Ana", {"R\u00f8ntgen"}, foretrekker={"DAG"})
        b = radiograf("Bora", {"R\u00f8ntgen"})
        c = radiograf("Cara", {"R\u00f8ntgen"}, stillingsprosent=50.0)
        ansatte = [a, b, c]
        bemanning = {"DAG": {"R\u00f8ntgen": {"hverdag": 1, "helg": 1}}}
        behov = bygg_behov(bemanning, [DAG])
        los = cpsat_generator.loes_med_cpsat(
            ansatte, behov, START, 14, [DAG], 40.0, tidsbegrensning=25.0
        )
        self.assertIsNotNone(los)
        per_pct = {
            x.id: sum(s.varighet.total_seconds() / 3600 for s in los.tildelinger[x.id])
            / (x.stillingsprosent / 100)
            for x in ansatte
        }
        self.assertLessEqual(max(per_pct.values()) - min(per_pct.values()), 8.5)

    def test_hall_motbevis_valider_plan(self):
        p1 = radiograf("P1", {"CT"})
        p2 = radiograf("P2", {"CT"})
        p3 = radiograf("P3", {"MR", "Ultralyd"})
        ansatte = [p1, p2, p3]
        bemanning = {"DAG": {"CT": {"hverdag": 1, "helg": 0}, "MR": {"hverdag": 1, "helg": 0}, "Ultralyd": {"hverdag": 1, "helg": 0}}}
        behov = bygg_behov(bemanning, [DAG])
        plan = {a.id: [Skift(START, DAG)] for a in ansatte}
        feil = regler.valider_plan(plan, ansatte, behov, START, 1, [DAG], True)
        self.assertTrue(any("krever 3" in f or "fylle" in f for f in feil), feil)

        p3b = radiograf("P3b", {"MR", "Ultralyd"})
        p1b = radiograf("P1b", {"CT"})
        p2b = radiograf("P2b", {"MR"})
        ansatte2 = [p1b, p2b, p3b]
        plan2 = {a.id: [Skift(START, DAG)] for a in ansatte2}
        feil2 = regler.valider_plan(plan2, ansatte2, behov, START, 1, [DAG], True)
        self.assertEqual(feil2, [])

    def test_ics_fold_teangrenser(self):
        from turnus.ics_export import _fold
        linje = "SUMMARY:" + "a" * 66 + "\u00f8re-\u00c5se"
        foldet = _fold(linje)
        sammen = foldet.replace("\r\n ", "")
        self.assertEqual(sammen, linje)
        for linje_del in foldet.split("\r\n"):
            self.assertLessEqual(len(linje_del.encode("utf-8")), 75)

    @unittest.skipUnless(cpsat_generator.tilgjengelig(), "ortools er ikke installert")
    def test_laast_vakt_uten_kompetanse_cpsat(self):
        a = radiograf("Ana", {"R\u00f8ntgen"})
        b = radiograf("Bora", {"R\u00f8ntgen"})
        ansatte = [a, b]
        bemanning = {"DAG": {"CT": {"hverdag": 1, "helg": 0}}}
        behov = bygg_behov(bemanning, [DAG])
        laaste = [(a.id, Skift(START, DAG))]
        los = cpsat_generator.loes_med_cpsat(
            ansatte, behov, START, 1, [DAG], 40.0, tidsbegrensning=25.0, laaste=laaste
        )
        self.assertIsNotNone(los)
        self.assertEqual(len(los.laaste_feilet), 1, los.laaste_feilet)

    def test_ansatte_lager_rundertrip_navn_preferanser(self):
        with tempfile.TemporaryDirectory() as tmp:
            ansatte_lager.FIL = Path(tmp) / "ansatte.json"
            try:
                antall, advarsler = ansatte_lager.lagre([
                    {"navn": "Dupont d'Azur", "yrkesgruppe": "radiograf", "modaliteter": ["CT"], "foretrekker": ["MELLOM"], "unnga": ["NATT"]},
                ])
                self.assertEqual(antall, 1)
                self.assertEqual(advarsler, [])
                lagret = ansatte_lager.les_lagrede()
                self.assertIsNotNone(lagret)
                self.assertEqual(lagret[0].foretrekker, {"MELLOM"})
                self.assertEqual(lagret[0].unnga, {"NATT"})
            finally:
                ansatte_lager.FIL = Path(__file__).resolve().parent.parent / "ansatte.json"


if __name__ == "__main__":
    unittest.main()

class HelgTest(unittest.TestCase):
    def samlet_helg_scenario(self):
        ansatte = ansatte_12t(9)
        bemanning = {
            "DAG12": {"R\u00f8ntgen": {"hverdag": 1, "helg": 1}},
            "NATT12": {"R\u00f8ntgen": {"hverdag": 1, "helg": 0}},
        }
        return ansatte, bygg_behov(bemanning, [DAG12, NATT12]), [DAG12, NATT12]

    @staticmethod
    def delte_helger(tildelinger, ansatte, start, dager):
        delte = 0
        for a in ansatte:
            helg_dager = {
                (s.dato - timedelta(days=s.dato.weekday())): set()
                for s in tildelinger[a.id] if s.dato.weekday() >= 5
            }
            for s in tildelinger[a.id]:
                if s.dato.weekday() >= 5:
                    helg_dager[s.dato - timedelta(days=s.dato.weekday())].add(s.dato.weekday())
            for dager_i_helg in helg_dager.values():
                if dager_i_helg == {5} or dager_i_helg == {6}:
                    delte += 1
        return delte

    def test_samlet_helg_greedy(self):
        ansatte, behov, defs = self.samlet_helg_scenario()
        plan = TurnusGenerator(ansatte, behov, START, 28, defs).generer()
        self.assertEqual(plan.udekket, [])
        self.assertEqual(self.delte_helger(plan.tildelinger, ansatte, START, 28), 0)

    @unittest.skipUnless(cpsat_generator.tilgjengelig(), "ortools er ikke installert")
    def test_samlet_helg_cpsat(self):
        ansatte, behov, defs = self.samlet_helg_scenario()
        los = cpsat_generator.loes_med_cpsat(ansatte, behov, START, 28, defs, tidsbegrensning=25.0)
        self.assertIsNotNone(los)
        self.assertEqual(self.delte_helger(los.tildelinger, ansatte, START, 28), 0)

    def test_global_helgfrekvens_setter_bare_manglende(self):
        a = radiograf("UtenOnske", {"R\u00f8ntgen"})
        b = radiograf("MedOnske", {"R\u00f8ntgen"}, helg_hver_n=0)
        regler.sett_global_helgfrekvens([a, b], 3)
        self.assertEqual(a.helg_hver_n, 3)
        self.assertEqual(b.helg_hver_n, 0)
        regler.sett_global_helgfrekvens([a, b], None)
        self.assertEqual(a.helg_hver_n, 3)

    def test_global_helgfrekvens_haandheves(self):
        ansatte = ansatte_12t(9, helg_hver_n=None)
        regler.sett_global_helgfrekvens(ansatte, 2)
        regler.sett_helg_offsatter(ansatte)
        bemanning = {"DAG12": {"R\u00f8ntgen": {"hverdag": 1, "helg": 1}}}
        behov = bygg_behov(bemanning, [DAG12])
        plan = TurnusGenerator(ansatte, behov, START, 28, [DAG12]).generer()
        for a in ansatte:
            for s in plan.tildelinger[a.id]:
                if s.dato.weekday() >= 5:
                    self.assertTrue(regler.helgfrekvens_ok(a, s.dato), f"{a.navn} jobbet helg {s.dato}")
        jobbet_helg = {a.id for a in ansatte if any(s.dato.weekday() >= 5 for s in plan.tildelinger[a.id])}
        self.assertTrue(jobbet_helg)
