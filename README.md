# Turnusplan

Prototype for en radiologisk avdeling som genererer turnusforslag basert på:

- **Arbeidsmiljøloven kap. 10** som harde begrensninger
- **Ansattes preferanser og fridager** som myke vektinger
- **Modalitetskompetanse** per skift som dekningskrav (Røntgen, CT, MR, Ultralyd, Mammografi, Intervensjon)
- **To yrkesgrupper**: radiograf (én eller flere modaliteter) og fagradiograf (én hovedmodalitet, kan i tillegg dekke fagradiograf-plassene)
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

- Generere turnusforslag med konfigurerbare skift (mellomvakt, kveld, natt osv.)
- Rullende turnuser på 4, 6, 8 eller 12 uker
- Velge modaliteter og bemanning per skift, atskilt for hverdag og helg
- Redigere ansatte direkte: navn, yrkesgruppe, modaliteter, stillingsprosent
  og preferanser – lagres i `ansatte.json` og brukes av generatoren i stedet
  for demopoolen
- **Nøyaktig planmotor (OR-Tools CP-SAT)** som valgfritt alternativ til den
  raske greedy-motoren: modellerer hele horisonten samtidig med en
  plassmodell (hvert bemanningskrav er en egen plass som må fylles av én
  kvalifisert person) og finner optimal turnus innenfor modellens aml- og
  tariffregler (optimalitet verifiseres innenfor modellen, ikke mot
  lovteksten). Ukegrensen er lov-taket (40 t × stillingsprosent), mens
  tariffnormen (f.eks. 35,5 t) håndheves som snitt over hele perioden med
  straff for avvik fra måltimer per ansatt. Udekket behov og avviste låste
  vakter kommer direkte fra modellen. Installer valgfritt med
  `pip3 install ortools` – uten den brukes greedy automatisk
- **Helgrullering per ansatt** – kolonnen «Helg hver N.» i Ansatte-fanen:
  3 = hver tredje helg, 4 = hver fjerde helg, 0 = aldri helg; ansatte med samme
  frekvens staggres automatisk så helgene fordeles jevnt
- **Skift-tilgang per ansatt** – kolonnen «Skift» i Ansatte-fanen begrenser
  hvilke skift den ansatte kan jobbe (f.eks. «DAG, KVELD» = aldri natt).
  Kombiner med «Helg hver N.» for å kjøre flere turnusgrupper med ulik
  lengde og innhold parallellt i samme plan
- **12-timers-tilvalg per ansatt** – kolonnen «12-t vakter/uke» i Ansatte-fanen
  setter hvor mange 12-timersvakter den ansatte ønsker per uke (tom = ingen
  grense, 0 = nei); håndheves av generatoren og ved vaktbytte
- **Huskede innstillinger** – startdato, lengde, norm, motor og rotasjon gjenopprettes
  ved neste oppstart
- **Min uke** – personlig ukeliste med klokkeslett i Turnus-fanen
- **Tastatur** – Enter = generer, 1–4 = faner, ESC = lukk modal
- **Ukekort per ansatt** – klikk på navnet i vaktmatrisen for alle vakter med
  klokkeslett, timer per uke, natt-/helgetelling og tariffstatus
- **Låste vakter** – lås faste vakter i Generer-fanen; de fordeles først, og ulovlige
  lås avvises med begrunnelse
- **Sammenligning** – «Sammenlign med forrige» viser differansen per ansatt mellom to
  genererte forslag
- **Dekningsforslag** – udekket behov følges av konkrete løsningsforslag
- **Skriv ut / lagre som PDF** i Turnus-fanen – A4 landskap med kun turnusen,
  fargekoder bevart
- **Vaktbytte mellom ansatte** i Turnus-fanen – bytte eller overtagelse av en
  vakt, kun gjennomført hvis alle aml-regler, kompetanse og dekning fortsatt
  stemmer
- **Ferie/fravær per ansatt**: enkelt datoer eller intervaller
  («2025-07-01 til 2025-07-14») i Ansatte-fanen – generatoren tildeler ingen
  vakter disse dagene
- **Rotasjonsrullering**: del de ansatte i grupper som roterer gjennom
  skiftene per 4-ukers syklus (valgfri lengde), planlagt dag for dag slik at
  alle aml-regler overholdes ved syklusgrensene
- Lagre hele oppsettet (skift, bemanning, arbeidsuke-norm og ansatte) som et
  **forvalg** under et eget navn, og last det tilbake senere – lagres i
  `forvalg.json`
- Laste opp en `.ics`-fil fra Minarbeidsplan og validere den mot aml
- Laste ned generert turnus som `.ics` (én hendelse per vakt) for import i
  kalender eller Minarbeidsplan – hele avdelingen eller per person
  («↓ .ics»-knappen per ansatt i oppsummeringstabellen)

Generert turnus vises i egen fane som vaktmatrise per uke per ansatt (D/K/N/M),
med sum timer per uke, totalt og snitt per uke mot valgt arbeidsuke-norm.

### Skift og mellomvakter

Skiftene er fullt konfigurerbare i GUI-et (navn, start, slutt, hverdag/helg) og
lagres i `skift.json`. Standard inkluderer mellomvakt MELLOM 11:30–19:00 på
hverdager; endre tidene (f.eks. til 15:00–23:00) for å gjøre den om til
kveldsvakt. Slutt før start tolkes som nattskift over midnatt. Bemanningen
gis per skift og kompetanse. Maks skiftlengde er 12 t (aml §10-3/§10-6 med
avtale).

Endringslogg: se [CHANGELOG.md](CHANGELOG.md). Versjon vises i GUI-overskriften.

### Arbeidsuke-norm (tariff)

Generatoren planlegger mot valgt uketimer-norm (gjennomsnitt over perioden):

| Norm | Gjelder |
|---|---|
| 40 t | Lovens maks (aml §10-2/10-3), ingen tariffreduksjon |
| 37,5 t | Standard arbeidsuke uten turnusreduksjon |
| 35,5 t | Spekter-overenskomsten del A2 pkt 1.3 (område 10 – helseforetak, bl.a. Helse Møre og Romsdal): turnus med arbeid mellom kl. 20.00–06.00 og/eller søndagsarbeid minst hver 3. søndag, samt døgnkontinuerlig skiftarbeid |
| 33,6 t | Helkontinuerlig skiftarbeid og turnus sammenlignbart med dette (minst 539 t nattarbeid og 231 t søndagsarbeid per år, jf. NITO-overenskomsten) |

GUI-et viser automatisk om den genererte turnusen utløser 35,5-timers kriteriene.
Aml (40 t per uke) håndheves alltid som lovfestet tak; tariffnormen brukes som
planleggingsnorm for snittet og rapporteres som egne tariffbrudd når snittet
overskrides. Norsk Radiografforbund (NRF) forhandler for radiografer i Spekter-
området gjennom NITO/SAN; lokale avtaler hos arbeidsgiveren kan avvike, sjekk
eventuell lokal overenskomst del B.

Uten `ansatte.json` dimensjoneres demopoolen automatisk etter timer per uke og
nattbehov. Fagradiografer prioriteres til fagradiograf-plassene og kan i tillegg
dekke plasser innenfor sin hovedmodalitet når radiografene tar slut.

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
| Minst 11 timer døgnhvile mellom skift | aml §10-8 (1. ledd) | `regler.dognhvile_ok` |
| Minst 35 timer sammenhengende ukeshvile | aml §10-8 (2. ledd) | `regler.ukeshvile_ok` |
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
- **Fremoverrotasjon**: senere starttid neste dag belønnes (anbefalt fremoverrotasjon)
- **Sammenhengende arbeidsdager**: småstraff for å jobbe mange dager på rad

## Arkitektur

```
turnus/
  modeller.py    Ansatt, SkiftDef (konfigurerbare skifftyper), Skift, Krav
  regler.py      Harde regler fra aml + full planvalidering
  generator.py   Greedy-planlegger med poengberegning
  cpsat_generator.py  CP-SAT-planlegger (plassmodell, snittnorm, slakk)
  ics_import.py  Import av iCal (.ics) og validering av eksisterende turnus
  ics_export.py  Eksport av turnus og enkeltansatte til iCal (.ics)
  skift_lager.py Lager/leser av egendefinerte skift (skift.json)
  ansatte_lager.py  Lager/leser av ansatte (ansatte.json)
  forvalg_lager.py  Lager/leser av forvalg (forvalg.json)
  lager.py       Atomisk filskriving (tmp-fil + os.replace)
  webgui.py      Lokal webserver (127.0.0.1) med JSON-API for GUI-et
  demo_data.py   Modaliteter, yrkesgrupper og automatisk ansattdimensjonering
web/
  index.html     Grensesnitt (vanilla HTML/JS, ingen avhengigheter)
main.py          CLI (argparse) som genererer, validerer eller starter GUI
run.sh           Kjøre-skript for Mac/Linux
tests/
  test_motorer.py  Unittests som kjører greedy og CP-SAT på samme input
                   og krever at begge består samme regelvalidering
```

## Helger

- **Samlete helger:** generatoren foretrekker at lørdag og søndag i samme
  helg jobbes av samme person (både greedy og CP-SAT)
- **Helgefrekvens:** i Generer-fanen velger du hvor ofte helg jobbes for
  hele planen (hver helg, hver 2./3./4., aldri). Gjelder alle som ikke har
  egen «Helg hver N.»-verdi i Ansatte-fanen; egne ønsker beholder forrang

## Ønsker med fritekst (valgfri AI via Ollama)

I Ansatte-fanen kan du skrive en ansattes ønsker i fritekst og få dem
oversatt til strukturerte felt (foretrekker, unngå, fravær, helgrullering
osv.). Dette krever [Ollama](https://ollama.com) installert lokalt:

```bash
ollama pull llama3.1   # eller en annen modell
```

Alt kjøres på din egen maskin – ingen ansatdata sendes ut. Modellen
foreslår bare preferanser; du ser og bekrefter forslaget før det brukes,
og generatoren håndhever fortsatt alle aml-regler selv.

## Utvidelsespunkter

- Egne skifftyper: legg til `SkiftDef` i `modeller.py` (start/slutt-time, `er_natt`)
- Flere kompetanser per ansatt: fyll `kompetanse`-mengden
- Lokale avtaler/tariff: legg til regler i `regler.py` og bruk dem i `kandidat_er_lovlig`
- CP-SAT som bakgrunnsjobb med fremdriftsindikator (i dag blokkerer
  optimeringen HTTP-kallet i opptil 30 sekunder)
- Vinterhalvåret: nattarbeidsreglene i aml §10-7 er strengere mellom 21:00 og 06:00
