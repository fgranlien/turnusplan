# Endringslogg

Versjonsnummerering: **heltall** (2.0 → 3.0) for større omstruktureringer,
**desimal** (2.3 → 2.4) for mindre endringer og forbedringer.

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
