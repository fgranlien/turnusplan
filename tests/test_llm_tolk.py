from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from turnus import llm_tolk

SKIFT = ["DAG", "KVELD", "NATT", "DAG12", "NATT12", "MELLOM"]
MODALITETER = ["Røntgen", "CT", "MR"]


class SaniterTest(unittest.TestCase):
    def test_tolkbare_felter_bevares(self):
        felter, advarsler = llm_tolk.saniter(
            {
                "foretrekker": ["dag", "KVELD"],
                "unnga": ["NATT"],
                "skift_tilgang": ["dag12", "natt12"],
                "langvakt_uke_maks": 2,
                "helg_hver_n": 3,
                "stillingsprosent": 80,
            },
            SKIFT,
            MODALITETER,
        )
        self.assertEqual(felter["foretrekker"], ["DAG", "KVELD"])
        self.assertEqual(felter["unnga"], ["NATT"])
        self.assertEqual(felter["skift_tilgang"], ["DAG12", "NATT12"])
        self.assertEqual(felter["langvakt_uke_maks"], 2)
        self.assertEqual(felter["helg_hver_n"], 3)
        self.assertEqual(felter["stillingsprosent"], 80.0)
        self.assertEqual(advarsler, [])

    def test_ukjente_felter_og_skift_dropes(self):
        felter, advarsler = llm_tolk.saniter(
            {"hjemmekontor": ["ja"], "foretrekker": ["NATTVAKT", "DAG"], "helg_hver_n": 99},
            SKIFT,
            MODALITETER,
        )
        self.assertNotIn("hjemmekontor", felter)
        self.assertEqual(felter["foretrekker"], ["DAG"])
        self.assertNotIn("helg_hver_n", felter)
        self.assertEqual(len(advarsler), 3)

    def test_datointervaller_utvides(self):
        felter, advarsler = llm_tolk.saniter(
            {"utilgjengelige_dager": [{"fra": "2025-07-01", "til": "2025-07-03"}, "2025-07-05", "ikke en dato"]},
            SKIFT,
            MODALITETER,
        )
        self.assertEqual(felter["utilgjengelige_dager"], ["2025-07-01", "2025-07-02", "2025-07-03", "2025-07-05"])
        self.assertEqual(len(advarsler), 1)

    def test_ugyldige_tall_dropes(self):
        felter, advarsler = llm_tolk.saniter(
            {"langvakt_uke_maks": "mange", "stillingsprosent": 150, "helg_hver_n": "3"},
            SKIFT,
            MODALITETER,
        )
        self.assertEqual(felter, {"helg_hver_n": 3})
        self.assertEqual(len(advarsler), 2)

    def test_ikke_objekt_gir_advarsel(self):
        felter, advarsler = llm_tolk.saniter(["nei"], SKIFT, MODALITETER)
        self.assertEqual(felter, {})
        self.assertEqual(len(advarsler), 1)


class PromptTest(unittest.TestCase):
    def test_prompt_inneholder_skift_og_fritekst(self):
        meldinger = llm_tolk.bygg_prompt(
            "ikke natt i juli",
            {"navn": "Kari", "foretrekker": ["DAG"]},
            SKIFT,
            MODALITETER,
        )
        self.assertEqual(meldinger[0]["role"], "system")
        self.assertIn("DAG, KVELD, NATT, DAG12, NATT12, MELLOM", meldinger[0]["content"])
        self.assertIn("Røntgen", meldinger[0]["content"])
        self.assertIn("ikke natt i juli", meldinger[1]["content"])
        self.assertIn("Kari", meldinger[1]["content"])


if __name__ == "__main__":
    unittest.main()
