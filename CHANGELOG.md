# Endringslogg

Versjonsnummerering: **heltall** (2.0 → 3.0) for større omstruktureringer,
**desimal** (2.3 → 2.4) for mindre endringer og forbedringer.

## 2.21 – Feilretting etter v3.0-gjennomgang

- **Hall-matching i `valider_plan`:** per-krav-sjekken godtok bemanninger
  der kompetansene overlapper (motbevis: P1{CT}, P2{CT}, P3{MR, Ultralyd}
  mot kravene CT+MR+Ultralyd ble godtatt selv om 3 plasser ikke kan fylles
  av 3 personer). Ny `maks_matching` (Kuhn) sjekker nå at alle plasser kan
  fylles samtidig; rammer også vaktbytte og importerte planer
- **CP-SAT-ukeshvile:** `timedelta(hours=regler.MIN_UKESHVILE)` krasjet
  (MIN_UKESHVILE er allerede en timedelta) og fikk alle CP-SAT-løp til å
  feile; brukes nå direkte
- **iCal-eksport:** `_fold` kuttet på bytegrenser og kunne miste tegn (æøå)
  som deles av en fold-grense; kutter nå på tegngrenser (maks 75 byte per
  linje, fortsettelseslinjer med mellomrom)
- **Tester:** CP-SAT-avhengige tester hoppes nå pent over med
  `skipUnless(cpsat_generator.tilgjengelig())` når ortools mangler,
  i stedet for å feile med importfeil

## 2.20 – Kombinere turnusgrupper: hard skift-tilgang per ansatt

- Ny kolonne «Skift» i Ansatte-fanen: kommaseparert liste av skiftnavnet
  den ansatte KUN kan jobbe (f.eks. «DAG, KVELD»), tom = alle skift
- Håndheves hardt av begge motorer: greedy (lovighetssjekk) og CP-SAT
  (skift utenfor tilgangen fjernes fra modellen), og av vaktbytte
- Gjør det mulig å kombinere grupper med ulik turnus i samme plan, f.eks.
  7 personer uten nattevakter som jobber helg hver tredje helg, samtidig
  som 10 personer går i en 10-ukers rullering med 12-timersvakter hver
  femte helg (Skift-tilgang + «Helg hver N.» + generering over 10 uker)
- Ny valideringsregel «Skifttilgang» i `valider_plan` så også importerte
  planer og vaktbytt fanges
- Lagres i `ansatte.json` (`skift_tilgang`) og rundtur via API-et
- To nye motor-tester: grupper med ulik tilgang + helgrullering i samme
  plan (begge motorer), og validering/lovighetssjekk av tilgangen

## 2.19 – GUI-rydding av Ansatte-fanen

- Tabellen fikk mindre celler og kortere kolonneoverskrifter («Fravær»,
  «12-t/uke») så alt får plass
- Modalitetene for radiografer vises nå i et kompakt rutenett (to kolonner)
  i stedet for én lang rekke som presset resten av tabellen utenfor kortet
- Tabellen ruller horisontalt innenfor kortet hvis vinduet er smalt
  (samme rulle-atferd som vaktmatrisen), i stedet for at teksten renner ut
- Fraværsfeltet er smalere med kortere eksempel-tekst
- Den lange forklaringsteksten nederst er nå sammenleggbar
  («Tips om feltene») så fanen starter ryddig

## 3.0 – Motor-omstrukturering: plassmodell, snittnorm og felles ukeshvile i CP-SAT

Større omstrukturering av CP-SAT-motoren etter ekstern kodegjennomgang
(«Forslag fra Claude»), pluss nye motor-tester.

- **Plassmodell i CP-SAT**: hvert bemanningskrav er nå en egen plass
  (`y[ansatt, dato, skift, plass]`) som må fylles av nøyaktig én kvalifisert
  person. Tidligere kunne én person (f.eks. en fagradiograf med Røntgen som
  hovedmodalitet) «telle» for to krav på samme skift i modellen. Dekning er
  ikke lenger en hard betingelse som gjør modellen infeasible: plasser som
  ikke kan fylles får en straffet slakkvariabel, så du får alltid en plan med
  minst mulig udekket behov – og udekket-listen kommer direkte fra modellen
- **Snittnorm i stedet for hard ukegrense**: tariffnormen (f.eks. 35,5 t ved
  helkontinuerlig drift) håndheves nå som snitt over hele perioden
  (`total_minutter <= norm × stillingsprosent × dager/7`), med straff for
  avvik fra måltimer per ansatt. Ukegrensen per kalenderuke er lov-taket
  (40 t × stillingsprosent). Tidligere gjorde 35,5-normen som hard ukegrense
  at normen aldri kunne nås med 8-timersvakter
- **Felles ukeshvile-definisjon**: CP-SAT bruker nå samme definisjon som
  `regler.ukeshvile_ok` – minst 35 sammenhengende hviletimer modellert som
  tre sammenhengende frie 12-timersblokker per kalenderuke. Tidligere var
  CP-SAT-versjonen (to hele kalenderdøgn uten vaktstart) strengere enn
  reglene og avviste lovlige mønstre som lørdag dag → mandag dag
- **Låste vakter støttes i CP-SAT**: låste vakter legges inn som
  `x[a, d, s] == 1` i modellen i stedet for å falle tilbake til greedy;
  ulovlige eller umulige lås rapporteres i `laaste_feilet`
- **Preferanser matches på skiftnavn**: `foretrekker`/`unnga` er nå mengder av
  skiftnavn (store bokstaver) i stedet for `SkiftDef`-objekter. Ønsker om
  mellomvakt og egendefinerte skift virker nå, og endring av klokkeslett på
  et skift ødelegger ikke lenger lagrede ønsker. `regler.matcher(ønsker,
  skift)` er ny felles hjelpefunksjon (navn-match, med NATT-fallback til alle
  nattskift), brukt av begge motorer og GUI-et
- **Plass-basert dekning i `valider_plan`**: valideringen teller nå
  kvalifiserte tildelinger per krav-plass (samme person kan ikke fylle to
  plasser på samme skift) – samme tolkning som greedy og CP-SAT
- **CP-SAT-parametre**: `num_search_workers = os.cpu_count()`, `random_seed`
  for reproduserbare planer, og `TIDSRENSNING` omdøpt til `TIDSBEGRENSNING`
- **Nye motor-tester** (`tests/test_motorer.py`): 10 unittests som kjører
  greedy og CP-SAT på samme input og krever at begge består samme
  `valider_plan` – dekker 8-t og 12-t med snittnorm, fagradiograf-telling,
  låste vakter (lovlig og ulovlig), 12-timers-tilvalg, helgrullering,
  preferanser på navn inkl. mellomvakt og ansatte-lagring runt-trip
- **Målfunksjonsretting**: belønningsledd (preferanser) og straffledd
  (unngå, fagra-modalitet, avvik, slakk) blandet feil vei etter omskrivingen
  – preferanser ble straffet i stedet for belønnet. Alle ledd er nå skalerte
  heltall (vekter × 10) med vakt mot at små vekter trunkeres til 0

## 2.18 – Sikkerhet og feilretting (etter ekstern kodegjennomgang)

- **GUI-serveren**: Host- og Origin-sjekk (kun localhost aksepteres), krav om
  `Content-Type: application/json` på JSON-endepunktene og maksgrense 5 MB på
  forespørselskropp – beskytter mot CSRF/DNS-rebinding mot 127.0.0.1
- **XSS**: `esc()` escaper nå også enkeltnavnstegn ('), og navn sendes ikke
  lenger inn i JavaScript-strenger – ukekort og iCal-eksport bruker indeks
- **Unike skiftkoder** i vaktmatrisen: to skift som begynner på samme bokstav
  (f.eks. DAG og DAG12) får nå ulike koder (D/DA) med egne farger, og teksten
  under matrisen lister kodene dynamisk
- **Vaktbytte** avvises bare hvis byttet tilkommer **nye** regelbrudd – brudd som
  fantes i planen fra før (f.eks. udekket behov) stopper ikke lenger byttet
- **Atomisk lagring** av `ansatte.json`, `skift.json` og `forvalg.json`
  (midlertidig fil + `os.replace`) så en avbrutt lagring ikke ødelegger filen
- **Advarsel på stderr** hvis en av lagringsfilene er korrupt, i stedet for
  stille fallback til demodata
- **Advarsel ved duplikatnavn** når ansatte lagres (navn brukes av låste vakter,
  vaktbytte og iCal-eksport)
- **iCal-eksport**: PRODID bruker versjonsnummeret fra koden, linjefolding
  holder maks 75 byte inkludert fortsettelsesmellomrommet (jf. RFC 5545), og
  skrivefeilen `dtstemp` er rettet til `dtstamp`
- **README**: korrigerte lovhenvisningene for døgnhvile og ukeshvile til
  aml §10-8 (1. og 2. ledd), rettet fagradiograf-beskrivelsen (én hovedmodalitet)
  og formulerte CP-SAT-optimaliteten mer presist

## 2.17 – Helgrullering per ansatt

- Ny kolonne «Helg hver N.» i Ansatte-fanen: tom = ingen begrensning,
  3 = hver tredje helg, 4 = hver fjerde helg, 0 = aldri helgvakt
- Ansatte med samme frekvens får automatisk forskjellige picker, slik at
  helgvaktene fordeles jevnt (ikke alle samme helg)
- Håndheves av begge motorene: greedy (lovighetssjekk) og CP-SAT (fjerner
  helgvakter utenfor rulleringen fra modellen)
- Vaktbytte avvises hvis mottakeren får helgvakt utenfor sin rullering
- Merk: hvis tilvalgene gjør helgedekningen umulig, vises udekket behov med
  løsningsforslag (CP-SAT faller da tilbake til greedy med merknad)

## 2.16 – Tilvalg for 12-timersvakter per ansatt

- Ny kolonne «12-t vakter/uke» i Ansatte-fanen: hvor mange 12-timersvakter
  (DAG12/NATT12 e.l.) den ansatte ønsker per uke
  – tom = ingen begrensning, 0 = ønsker ikke 12-timersvakter
- Tilvalget håndheves av begge motorene: greedy (via lovighetssjekken) og
  CP-SAT (egen ukentlig begrensning)
- Vaktbytte avvises hvis byttet ville gitt den mottakende ansatte flere
  12-timersvakter i uka enn tilvalget
- Lagres i ansatte.json sammen med resten av ansettelisten

## 2.15 – Feilretting: fanene i GUI-et

- Faneknappene (Generer/Turnus/Ansatte/Valider iCal) fungerte ikke ved klikk:
  funksjonen `visTab` ble ved et uhell slettet i v2.4-refaktoren og er nå gjenopprettet
- «4/6/8/12 uker»-knappene (rullende lengde) fikk også tilbake sin `settUker`-funksjon

## 2.14 – Daglig bruk og polish

- Siste innstillinger (startdato, dager, norm, motor, rotasjon og syklus) huskes i
  nettleseren og gjenopprettes ved neste oppstart
- «Min uke» – velg deg selv i Turnus-fanen og se dine vakter per uke med klokkeslett
  og timer (mobilvennlig liste, skjules på utskrift)
- Spinner på Generer-knappen mens turnusen beregnes, og markør-heving (hover) på
  raden i vaktmatrisen
- Tastaturstøtte: Enter genererer forslag, 1–4 bytter fane, ESC lukker ukekort-modalen

## 2.13 – Brukbarhet: ukekort, låste vakter, sammenligning og dekningsforslag

- Fargekodete kompetanse-markører: modalitetene vises som korte badges (RX/CT/MR/UL/MG/IV)
  ved navnet i vaktmatrisen
- «X t under»-merknad i oransje i oppsummeringen for ansatte som ligger merkbart under
  arbeidsuke-normen (norm × stillingsprosent)
- Klikk på navnet i matrisen åpner ukekort per ansatt: alle vakter med klokkeslett,
  timer per uke, natt-/helgetelling og tariffstatus
- Manuell låsing av vakter i Generer-fanen: låste vakter fordeles først av generatoren,
  ulovlige låste vakter avvises med begrunnelse (kompetanse, fravær, døgnhvile e.l.)
- «Sammenlign med forrige» viser differanser per ansatt (skift, timer, snitt/uke, natt, helg)
  mot forrige genererte forslag
- Konkrete løsningsforslag per udekket krav (f.eks. «gi flere radiografer CT-kompetanse,
  eller reduser bemanningen for CT på NATT»)
- Skift-listen og versjonsnummeret lastes nå ved oppstart

## 2.12 – Nøyaktig planmotor (OR-Tools CP-SAT)

- Ny «Motor»-velger i Generer-fanen: Rask (greedy) eller Nøyaktig (CP-SAT)
- CP-SAT modellerer hele horisonten samtidig: dekning, døgnhvile, ukeshvile,
  uketimer mot valgt norm, natteserier, ferie og preferanser – og finner en
  bevist optimal løsning (status og løsningstid vises i Turnus-fanen)
- Målfunksjonen vekter preferanser, rettferdig fordeling av vakter og natter,
  og straff for fagradiograf på modalitetsplasser
- Faller automatisk tilbake til greedy hvis `ortools` ikke er installert,
  hvis ingen løsning finnes innen 30 sekunder, eller ved rotasjonsrullering
  (støttes kun av greedy) – med forklarende merknad i resultatet
- Valgfri installasjon på Mac: `pip3 install ortools` – uten den fungerer
  alt som før med greedy

## 2.11 – Utskrift og PDF

- «Skriv ut / lagre som PDF»-knapp i Turnus-fanen
- Utskriften formateres automatisk som A4 landskap med kun turnusen: meny,
  knapper, skjemafelter og vaktbytte-boksen skjules
- Vaktmatrisen beholder fargekodene (D/K/N/M) på utskrift, også i mørk modus
  som tvinges tilbake til lyse farger
- Rader og overskrifter deles ikke over sideskifter

## 2.10 – Vaktbytte mellom ansatte

- Nytt «Vaktbytte»-kort i Turnus-fanen: velg «Fra», «Til», dato og skift
- Har mottakeren en vakt samme dag byttes de to vaktene; ellers overtar
  mottakeren vakten
- Byttet gjennomføres bare hvis alt fortsatt er lovlig: døgnhvile 11 t,
  ukeshvile 35 t, uketimer, natteserier, skiftlengde, kompetanse/dekning og
  ferie/fravær – ellers vises en liste over regelbruddene og planen endres ikke
- Etter gjennomført bytte oppdateres matrisen, oppsummeringen og
  iCal-eksportene automatisk

## 2.9 – Ferie og fravær per ansatt

- Ny «Ferie/fravær»-kolonne i Ansatte-fanen
- Angi enkelt datoer eller intervaller (f.eks. «2025-07-01 til 2025-07-14»),
  atskilt med komma; «til», «/» og tankestrek støttes som skille
- Intervaller ekspanderes til enkeltdager ved lagring, ugyldige datoer gir
  advarsel og hoppes over
- Generatoren tildeler ingen vakter på utilgjengelige dager, og dekningen
  fordeles automatisk på de andre

## 2.8 – Rotasjonsrullering

- Ny «Rotasjonsrullering»-bryter i Generer-fanen med valgfri sykluslengde
  (standard 4 uker)
- Ansatte deles i like mange grupper som det er aktive skift; gruppe 1 starter
  på første skift, gruppe 2 på neste osv., og gruppene roterer ett skift frem
  for hver syklus
- Rotasjonen planlegges dag for dag med alle aml-sjekker intakte (døgnhvile,
  ukeshvile, uketimer, natteserier) – i motsetning til å kopiere ferdige
  mønstre, som kan bryte døgnhvilen ved syklusgrenser
- Personlige preferanser deaktiveres i rotasjonsmodus; rotasjonsgruppe vises i
  oppsummeringstabellen

## 2.7 – Forvalg: lagre og last komplett oppsett

- Nytt «Forvalg (lagret oppsett)»-kort i Generer-fanen
- «Lagre nåværende oppsett» lagrer skift, bemanning per skift,
  arbeidsuke-norm og ansattliste samlet i `forvalg.json`
- «Last» gjenoppretter et lagret oppsett: skift og ansatte skrives tilbake
  til `skift.json`/`ansatte.json` og lastes inn i GUI-et
- «Slett» fjerner et lagret forvalg

## 2.6 – Per-person iCal-eksport og mørk modus

- «↓ .ics»-knapp per ansatt i oppsummeringstabellen – eksporterer kun den
  personens vakter, klar for å sendes til den enkelte
- Mørk modus med lagret valg (følger systeminnstillingen første gang)
- Navnekolonnen i vaktmatrisen er frossen ved horisontal rulling

## 2.5 – iCal-eksport av generert turnus

- «Last ned iCal (.ics)»-knapp i Turnus-fanen – én kalenderhendelse per vakt
  med skifttype, navn, yrkesgruppe og modaliteter
- Filen kan importeres i kalenderappen eller Minarbeidsplan
- Riktig CRLF-format, UID per vakt (idempotent import) og linjefolding etter
  iCal-standarden

## 2.4 – Mellomvakt og konfigurerbare skift

- Nytt «Skift og mellomvakter»-kort i GUI-et: rediger navn, start, slutt og
  hverdag/helg per skift; legg til/fjern skift fritt
- Forhåndsvalg: 8 t (DAG/KVELD/NATT), 8 t + mellomvakt, 12 t (DAG12/NATT12)
- Mellomvakt MELLOM 11:30–19:00 på hverdager som standard, lett å endre til
  kveldsvakt ved å justere tidene
- Slutt før start tolkes automatisk som nattskift over midnatt
- Bemanning konfigureres per skift (ikke lenger felles for alle skift)
- Skiftene lagres i `skift.json` og brukes igjen ved neste oppstart
- Skiftlengde valideres (maks 12 t), duplikatnavn avvises

## 2.3 – Turnus-fane, ukematrise og tariffnorm

- Generert turnus i egen fane som vaktmatrise per uke per ansatt (D/K/N) med
  sum timer per uke, totalsum og snitt per uke
- Rullende turnuser: hurtigknapper for 4, 6, 8 og 12 uker
- Arbeidsuke-norm valgbar: 40 t (kun lov), 37,5 t, 35,5 t (Spekter A2 pkt 1.3),
  33,6 t (helkontinuerlig) – generator planlegger mot snittet, brudd rapporteres
- Automatisk deteksjon av om turnusen utløser 35,5-timers kriteriene
  (arbeid 20–06 og/eller søndagsarbeid minst hver 3. søndag)

## 2.2 – Fagradiograf med hovedmodalitet

- Fagradiograf er knyttet til én hovedmodalitet (ikke alle); kan fortsatt dekte
  fagradiograf-plassene uavhengig av modalitet

## 2.1 – Redigerbare ansatte

- Nytt «Ansatte»-kort: navn, yrkesgruppe, modaliteter, stillingsprosent og
  preferanser redigeres direkte i GUI-et
- Lagring til `ansatte.json`; generatoren bruker den lagrede listen i stedet
  for demopoolen (faller tilbake til demopool hvis filen mangler)
- Validering: radiograf krever minst én modalitet, fagradiograf krever
  hovedmodalitet

## 2.0 – Radiologisk domenemodell

- Større omstrukturering: radiograf og fagradiograf (ingen ledere eller
  assistenter – ledere jobber dagtid utenfor turnusen)
- Modalitetskompetanse: Røntgen, CT, MR, Ultralyd, Mammografi, Intervensjon
- Bemanningsbehov spesifiseres per kompetanse; fagradiografer prioriteres til
  fagradiograf-plassene og brukes sparsomt på modalitetsplasser

## 1.4 – Bemanning per kategori

- Antall ansatte per skift konfigurerbart, atskilt for hverdag og helg
- Ansattpoolen dimensjoneres automatisk etter timer per uke og nattbehov

## 1.3 – Grafisk grensesnitt

- Lokal webserver (kun loopback) med JSON-API og nettleser-GUI
- Port-/adresse-fallback: 127.0.0.1 → ::1 → alle grensesnitt (macOS errno 49)

## 1.2 – iCal-import og validering

- Lese eksisterende turnus fra Minarbeidsplan (.ics) med eksakte klokkeslett
- Validere mot aml: døgnhvile, ukeshvile, uketimer, skiftlengde, natteserier
- CLI: `--valider-fil` og `--stillingsprosent`

## 1.1 – Mac-støtte og langvakter

- Ren Python-stdlib (ingen pip/avhengigheter), shebang og `run.sh`
- Konfigurerbare skiftdefinisjoner; 12-timers langvakter (DAG12/NATT12) med
  avtaleflagg per aml §10-3/§10-6

## 1.0 – Første versjon

- CLI som genererer lovlig turnusforslag etter aml kap. 10
- Harde regler: døgnhvile 11 t, ukeshvile 35 t, 40 t/uke, maks 4 natter on-k
- Greedy-planlegger med preferanser, rettferdighet og rotasjonsscoring
- Demodata med tredelt turnus (DAG/KVELD/NATT)
