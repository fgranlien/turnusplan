# Endringslogg

Versjonsnummerering: **heltall** (2.0 → 3.0) for større omstruktureringer,
**desimal** (2.3 → 2.4) for mindre endringer og forbedringer.

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
