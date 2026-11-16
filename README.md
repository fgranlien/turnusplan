# Turnusplan

Prototype for en radiologisk avdeling som genererer turnusforslag basert på:

- **Arbeidsmiljøloven kap. 10** som harde begrensninger
- **Ansattes preferanser og fridager** som myke vektinger
- **Modalitetskompetanse** per skift som dekningskrav (Røntgen, CT, MR, Ultralyd, Mammografi, Intervensjon)
- **To yrkesgrupper**: radiograf (én modalitet) og fagradiograf (alle modaliteter, kan dekke alle plasser)
- **Bemanning atskilt for hverdag (man–fre) og helg (lør–søn)**

Ledere er ikke med i turnusen (de jobber dagtid). Antall ansatte beregnes
automatisk ut fra bemanningsbehovet.

Støtter både **tredelt turnus** (dag/kveld/natt, 8 t) og **langvakter** (12 t).

## Kjøring på Mac

Krever bare Python 3 (følger med macOS via Command Line Tools; sjekk med `python3 --version`):

```bash
./run.sh                      # tredelt turnus, 14 dager
./run.sh --langvakter         # 12-timers langvakter
./run.sh --dager 28           # lengre horisont
./run.sh --start 2025-04-01 --dager 21 --langvakter
```

### Grafisk grensesnitt (GUI)

```bash
./run.sh --gui
```

Åpner et grafisk grensesnitt i nettleseren din (serveren kjører kun lokalt på
127.0.0.1, ingenting eksponeres mot nettet). Fra GUI-et kan du:

- Generere turnusforslag (velg startdato, lengde og 8 t/12 t-modus)
- Velge modaliteter og bemanning per skift, atskilt for hverdag og helg
- Laste opp en `.ics`-fil fra Minarbeidsplan og validere den mot aml

Ansattpoolen dimensjoneres automatisk etter timer per uke og nattbehov.
Fagradiografer prioriteres til fagradiograf-plassene og brukes som reserve for
modalitetsplasser når radiografene tar slut.

### Valider din eksisterende turnus (iCal fra Minarbeidsplan)

```bash
python3 main.py --valider-fil minturnus.ics
python3 main.py --valider-fil minturnus.ics --stillingsprosent 80
```

Leser arbeidsvakter med eksakte klokkeslett direkte fra filen (uavhengig av
vaktbetegnelser), hopper over heldagshendelser (fridager som F1/F2), og
rapporterer eventuelle brudd på døgnhvile, ukeshvile, uketimer, skiftlengde
og natteserier.

Alternativt direkte: `python3 main.py --langvakter`. Alt kjører på standardbiblioteket – ingen installasjoner nødvendig. Fungerer også på Linux/Windows.

## Regler som håndheves (harde begrensninger)

| Regel | Paragraf | Implementering |
|---|---|---|
| Minst 11 timer døgnhvile mellom skift | aml §10-4 | `regler.dognhvile_ok` |
| Minst 35 timer sammenhengende ukeshvile | aml §10-4/10-5 | `regler.ukeshvile_ok` |
| Maks 40 timer per uke (skalert med stillingsprosent) | aml §10-2/10-3 | `regler.uketimer_ok` |
| Maks 9 t per døgn normalt, 10 t utvidet | aml §10-3 | `regler.valider_plan` |
| Vakter over 10 t krever avtale/tariff, maks 12 t | aml §10-3/10-6 | `langvakt_avtale`-flagg i `regler.kandidat_er_lovlig` |
| Maks 4 nattarbeid i strekk, begrenset nattarbeid | aml §10-7 | `regler.natteserie_lengde` |
| Kompetansebehov dekkes på alle skift | internt krav | `regler.valider_plan` |

## Langvakter (12 t)

Med `--langvakter` brukes DAG12 (07–19) og NATT12 (19–07). Lovlighet ivaretas slik:

- 11 t døgnhvile gjelder fortsatt: DAG12 etter DAG12 gir 12 t hvile (lovlig), NATT12 etter DAG12 samme kveld blokkeres
- 12 t overstiger normal arbeidstid (9 t) og utvidet (10 t), så programmet forutsetter **avtale/tariff etter aml §10-3 og §10-6** – settes `langvakt_avtale=False` avslås alle vakter over 10 t
- Uketimer holdes på maks 40 t (3 langvakter = 36 t/uke), uavhengig av snittberegning over 52 uker
- 35 t ukeshvile og maks 4 natter i strekk håndheves som normalt

## Myke kriterier (poengsummer i generatoren)

- **Preferanser**: +2 for foretrukket skifttype, −3 for skifttype ansatt vil unngå (nattønsker gjelder alle nattskift, også 12 t)
- **Rettferdighet**: jevn fordeling av arbeidstid relativt til stillingsprosent
- **Nattbalanse**: jevn fordeling av nattarbeid
- **Fremoverrotasjon**: senere starttid neste dag belønnes (aml §10-12)
- **Sammenhengende arbeidsdager**: småstraff for å jobbe mange dager på rad

## Arkitektur

```
turnus/
  modeller.py    Ansatt, SkiftDef (konfigurerbare skifftyper), Skift, Krav
  regler.py      Harde regler fra aml + full planvalidering
  generator.py   Greedy-planlegger med poengberegning
  ics_import.py  Import av iCal (.ics) og validering av eksisterende turnus
  webgui.py      Lokal webserver (127.0.0.1) med JSON-API for GUI-et
  demo_data.py   Modaliteter, yrkesgrupper og automatisk ansattdimensjonering
web/
  index.html     Grensesnitt (vanilla HTML/JS, ingen avhengigheter)
main.py          CLI (argparse) som genererer, validerer eller starter GUI
run.sh           Kjøre-skript for Mac/Linux
```

## Utvidelsespunkter

- Egne skifftyper: legg til `SkiftDef` i `modeller.py` (start/slutt-time, `er_natt`)
- Flere kompetanser per ansatt: fyll `kompetanse`-mengden
- Lokale avtaler/tariff: legg til regler i `regler.py` og bruk dem i `kandidat_er_lovlig`
- Bedre optimering: erstatt greedy i `generator.py` med f.eks. OR-Tools CP-SAT
- Vinterhalvåret: nattarbeidsreglene i aml §10-7 er strengere mellom 21:00 og 06:00
