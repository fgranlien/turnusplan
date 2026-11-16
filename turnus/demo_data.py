from __future__ import annotations

from datetime import date

from .modeller import Ansatt, DAG12, KVELD, Krav, NATT, NATT12, SkiftDef


def demo_ansatte() -> list[Ansatt]:
    return [
        Ansatt("a1", "Anne", {"leder"}),
        Ansatt("a2", "Bjørn", {"leder"}),
        Ansatt("a3", "Cecilie", {"leder"}, utilgjengelige_dager={date(2025, 3, 12)}),
        Ansatt("a4", "David", {"leder"}),
        Ansatt("a5", "Eva", {"leder"}),
        Ansatt("a6", "Fredrik", {"leder"}),
        Ansatt("a7", "Greta", {"sykepleier"}),
        Ansatt("a8", "Henrik", {"sykepleier"}, foretrekker={KVELD}),
        Ansatt("a9", "Ingrid", {"sykepleier"}),
        Ansatt("a10", "Jonas", {"sykepleier"}, utilgjengelige_dager={date(2025, 3, 5)}),
        Ansatt("a11", "Karin", {"sykepleier"}),
        Ansatt("a12", "Lars", {"sykepleier"}),
        Ansatt("a13", "Marte", {"sykepleier"}),
        Ansatt("a14", "Nina", {"assistent"}, unnga={NATT}),
        Ansatt("a15", "Ola", {"assistent"}, unnga={NATT}, utilgjengelige_dager={date(2025, 3, 17)}),
        Ansatt("a16", "Petra", {"assistent"}, unnga={NATT}),
        Ansatt("a17", "Rune", {"assistent"}, foretrekker={NATT}),
        Ansatt("a18", "Sofia", {"assistent"}, foretrekker={NATT}),
        Ansatt("a19", "Thomas", {"assistent"}),
        Ansatt("a20", "Ulrik", {"assistent"}),
        Ansatt("a21", "Vilde", {"assistent"}, stillingsprosent=80.0),
        Ansatt("a22", "Aksel", {"assistent"}),
        Ansatt("a23", "Birgitte", {"assistent"}),
    ]


def _grunnkrav() -> list[Krav]:
    return [Krav("leder", 1), Krav("sykepleier", 1), Krav("assistent", 2)]


def demo_behov() -> dict[str, list[Krav]]:
    return {
        "DAG": _grunnkrav(),
        "KVELD": _grunnkrav(),
        "NATT": _grunnkrav(),
    }


def demo_behov_langvakt() -> dict[str, list[Krav]]:
    return {
        DAG12.navn: _grunnkrav(),
        NATT12.navn: _grunnkrav(),
    }


def skift_defs_for(langvakter: bool) -> list[SkiftDef]:
    from .modeller import LANGVAKT_SKIFT, STANDARD_SKIFT

    return LANGVAKT_SKIFT if langvakter else STANDARD_SKIFT
