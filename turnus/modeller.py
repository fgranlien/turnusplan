from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta


@dataclass(frozen=True, order=True)
class SkiftDef:
    navn: str
    start_time: float
    slutt_time: float
    er_natt: bool = False
    dager: tuple[str, ...] = ("hverdag", "helg")

    @property
    def varighet(self) -> timedelta:
        return timedelta(hours=(self.slutt_time - self.start_time) % 24)


DAG = SkiftDef("DAG", 7, 15)
KVELD = SkiftDef("KVELD", 15, 23)
NATT = SkiftDef("NATT", 23, 31, er_natt=True)
DAG12 = SkiftDef("DAG12", 7, 19)
NATT12 = SkiftDef("NATT12", 19, 31, er_natt=True)

STANDARD_SKIFT = [DAG, KVELD, NATT]
LANGVAKT_SKIFT = [DAG12, NATT12]


@dataclass(frozen=True, order=True)
class Skift:
    dato: date
    type: SkiftDef

    @property
    def start(self) -> datetime:
        return datetime.combine(self.dato, datetime.min.time()) + timedelta(hours=self.type.start_time)

    @property
    def slutt(self) -> datetime:
        return datetime.combine(self.dato, datetime.min.time()) + timedelta(hours=self.type.slutt_time)

    @property
    def varighet(self) -> timedelta:
        return self.type.varighet

    @property
    def etikett(self) -> str:
        return self.type.navn


@dataclass
class Ansatt:
    id: str
    navn: str
    kompetanse: set[str]
    stillingsprosent: float = 100.0
    foretrekker: set[str] = field(default_factory=set)
    unnga: set[str] = field(default_factory=set)
    utilgjengelige_dager: set[date] = field(default_factory=set)
    langvakt_uke_maks: int | None = None
    helg_hver_n: int | None = None
    helg_offset: int = 0
    skift_tilgang: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Krav:
    kompetanse: str
    antall: int
