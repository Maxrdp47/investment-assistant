# Investment Assistant – Projektstatus

Diese Datei enthält nur den aktuell belegten Ist-Stand. Planung und Freigaben stehen in [`ROADMAP.md`](ROADMAP.md). Dauerhafte Forschungsregeln stehen in [`RESEARCH_POLICY.md`](RESEARCH_POLICY.md). Frühere Fassungen wurden unverändert nach [`docs/archive/PROJECT_STATUS_LEGACY_THROUGH_2026-09-06.md`](docs/archive/PROJECT_STATUS_LEGACY_THROUGH_2026-09-06.md) verschoben.

## Current Truth – 2026-09-23

### Git und Dokumentation

- Aktiver Branch der begrenzten Informationslayer-/Data-Health-Runde: `codex/information-layer-data-health`; unveränderter Ausgangs-HEAD ist der abgeschlossene und gepushte R0–R9-Stand `9a1969fd7eb56f3758f3e980069d7ab41a629cb9`.
- Der Review-Stand wurde am 2026-09-15 ohne Divergenz per normalem Fast-Forward auf `origin/main` integriert. Er liegt damit nicht mehr nur auf dem Recovery-Branch.
- Ausgangs-HEAD des Recovery-Auftrags: `9990fbf557b414a51ca450aabb2a89f278d00d47`.
- Geprüfter Projekt-HEAD und Upstream vor dem v7-r2-Review-Commit: `30e26f2157e8a1b3eae761fd1cac73b71a462b92`.
- Die Urlaubs-Workqueue `vacation-workqueue-2026-09-06-v1` ist dokumentiert, aber noch nicht gestartet.
- Vor einem ausdrücklichen Startsignal wurden keine neue Funktion, kein Benchmark, kein Scan, kein Reprocessing-Lauf, kein Collector und keine Agenten-Wiederaufnahme gestartet.
- Der ausdrücklich freigegebene endliche Research-Programmzyklus `finite-research-program-2026-09-15-v1` ist terminal abgeschlossen. R0–R6 wurden innerhalb ihrer jeweiligen Gates abgeschlossen oder begrenzt; R2 blieb vor Performance an fehlender Futures-Kontrakt-/Roll-/Open-Provenienz blockiert. R6 lief nach grünem Smoke #61 und Pilot-/Replay-/Integrity-PASS mit 6 Workern/1 Writer vollständig durch. Der Final Audit ist `PASS`, der Review fand 0 robuste Quality-C-Kandidaten. R7 wurde nicht geöffnet, R8 aktivierte 0 Reserve-Hypothesen und R9 setzte `NO_ROBUST_EDGE_FOUND_IN_APPROVED_RESEARCH_PROGRAM`. Validation, Holdout, External, Forward, Paper, Shadow-Ausführung, Broker und Orders blieben geschlossen.
- Der endgültige Programm-Commit ist der Commit, der die Abschlussfassung enthält; der Abschlussbericht nennt seinen Hash und den CI-Stand.
- Der unmittelbar vorher getrennt abgeschlossene ENTRY-Handoff-Importer liegt in Commit `b1e3802b807649bc2cf871fa31ccf09fd8781cac`. Er gehört nicht zur Urlaubs-Queue und wurde nicht mit diesem Dokumentationspaket vermischt.

### Informationslayer- und Data-Health-Runde

- Der vollständige read-only A–M-Audit steht in [`RESEARCH_DATA_HEALTH_AND_COVERAGE_2026-09-23.md`](RESEARCH_DATA_HEALTH_AND_COVERAGE_2026-09-23.md); der daraus abgeleitete Lückenbericht steht in [`DATA_COLLECTION_GAP_REPORT_2026-09-23.md`](DATA_COLLECTION_GAP_REPORT_2026-09-23.md). Der Audit liest bestehende SQLite-Stores mit `mode=ro`, prüft die beiden aktiven Windows-Aufgaben und verwendet ausschließlich die kanonischen Zustände `HEALTHY`, `STALE`, `PARTIAL`, `FAILED`, `NOT_CONFIGURED` und `NOT_APPLICABLE`.
- Operativ aktiv und im Windows-Aufgabenplaner jeweils `Ready` sind `InvestmentAssistant-FX-PIT-Observer` und `InvestmentAssistantDailyForecasts`. Der letzte geplante FX-Lauf vom 2026-09-22 21:45 war erfolgreich; der commit-attribuierte Reparaturlauf `fxpit-run-8bc429f20d7df5c68dd130d984205a38` unter `859b4f6abead3aecd0bd0d9dd6b9adb6610227d0` endete am 2026-09-23 ebenfalls `COMPLETED`, mit Store-Integrität `ok`, 0 Providerfehlern und 0 verbotenen Ausgaben. Der letzte Prognoselauf vom 2026-09-22 22:30 endete mit 324 Erfolgen, einem expliziten Fehler für `MATIC-USD` und ohne Rate-Limit-Fehler.
- Repariert wurde ausschließlich Collector-Semantik: Ein verpasster COT-Freitag wird bei zu alter tatsächlicher Quelle nachgeholt; alte COT-Reports werden nicht mehr als aktuelle `AVAILABLE_PIT`-Coverage ausgegeben; `NO_RELIABLE_DATA` und `NOT_SCHEDULED` verschieben `last_success` nicht mehr fälschlich nach vorn.
- Der kontrollierte offizielle CFTC-Nachzug am 2026-09-23 speicherte 747 Reports append-only (196 TFF, 551 Disaggregated), 0 Fehler und 0 Produktionswirkung. Der COT-Store steht danach bei 63.439 Reports, 2.580 Availability-Belegen, Quick-Check `ok`; die Quelle ist operativ wieder aktuell. Die tatsächliche First-Seen-Evidenz umfasst aber erst 31,342 Tage und drei Collection-Tage und reicht daher nicht für einen unabhängigen historischen COT-Test.
- Fundamentals bestehen nur als Capability-/Parsercode: SEC-Snapshot-Cache, konfigurierte SEC-Kontaktkennung und historisches Issuer-Mapping fehlen. Expectations/Macro/Policy-Rates besitzen 0 PIT-Beobachtungen beziehungsweise 0 erwartete/tatsächliche Paare. Company Events umfassen nur 24 veraltete Forward-Snapshots ohne `published_at`. Crypto besitzt 33.675 eingefrorene OHLCV-Bars, aber keine neue PIT-Dominance-, Breadth-, Liquidity- oder On-Chain-Schicht. Gold/Silber bleibt wegen fehlender Futures-Kontrakt-, Roll-, Session-, Open- und Kostenprovenienz blockiert.
- Damit scheitern alle vorgeschriebenen Coverage-Gates vor Development. Es wurden 0 neue Challenger erzeugt und weder Development-Performance, Validation noch Holdout geöffnet. External, Forward, Paper, Shadow, Broker und Orders blieben geschlossen. Keine abgeschlossene negative technische Hypothese wurde erneut getestet.
- Terminaler Stand dieser begrenzten Runde: `RESEARCH_BLOCKED_BY_INSUFFICIENT_PIT_DATA`; finaler Data-Health-Fingerprint `70a6f59462558019eb14b2a818f70b5e25c89c5a3a91bf2a042d5393bb20ee43`.

### R6 Discovery v2 und Programmabschluss

- Run: `mad2-development-v2-20260922-v1`; 60.432/60.432 Receipts, davon 52.992 `COMPLETED`, 7.440 `SKIPPED`, 0 `FAILED`, 0 Retries. Feature- und Outcome-Referenzen: jeweils 2.356.553; 607.428 zensierte Fälle, 245.905 Fälle ohne verfügbares R-Ergebnis.
- [Final Audit](R6_MULTI_ASSET_DISCOVERY_V2_FINAL_AUDIT_2026-09-22.md): `PASS`, Fingerprint `7a83cc352de0c69e47cf41a7659a9999225aa3a6884424751701e9311a8898b0`; SQLite-Quick-Checks `ok`, 0 FK-Fehler, 0 Duplikate, 0 Orphans, 0 Feature-Link-Abweichungen.
- [Descriptive Development Report](R6_MULTI_ASSET_DISCOVERY_V2_DESCRIPTIVE_DEVELOPMENT_REPORT_2026-09-22.md): 2.356.553 Fälle, 31 vorab benannte Features, getrennte 20/60/120/252-Auswertungen; Fingerprint `4ee1cdb2193a0103618ffa6887d8da03f65030addaf93fb1231a1db639d46024`. Es wurden keine Schwellen, Rankings, Featurekombinationen oder Profit-basierte Auswahlen getestet.
- [Completion Summary](R6_MULTI_ASSET_DISCOVERY_V2_COMPLETION_SUMMARY_2026-09-22.md): `R6_COMPLETE_NO_ROBUST_CANDIDATES_R7_NOT_OPENED`, Fingerprint `917bf73aac6c49bef06c292000d7d526c521e6a2342169ee3e2348d9749e7ce2`. Harte Grenze: historisch verifizierte Issuer-Dependencies Effective N = 0; 0 robuste Kandidaten.
- [R8 Trigger-Review](FINITE_RESEARCH_PROGRAM_R8_TRIGGER_REVIEW_2026-09-22.md): `SKIPPED_NO_JUSTIFIED_RESERVE_TRIGGER`, 0/2 Reserve-Attempts, Fingerprint `15d052c53e10ede584092f86fc044f4d74880b5b278bc60518fa112c7129006e`. Kein technischer Reserveindikator kann die belegte Provenienzlücke schließen.
- R9: `NO_ROBUST_EDGE_FOUND_IN_APPROVED_RESEARCH_PROGRAM`, Fingerprint `4cef4088c6fcaf2eee0b8b52975ffe1f8c94e93aad1014d5dab11db484dcf16b`; 3 neue empirische Attempts insgesamt, 0 Validation- und 0 Holdout-Stufen. Das ist eine Aussage über das begrenzte freigegebene Programm, keine universelle Behauptung, dass kein Markt-Edge existiert.
- Knowledge Base: Hypothese `3335b324-63d3-4f88-aa00-bccacdde761e` `REJECTED`; Experiment `b8d0072d-c05f-4eea-bebe-0fd5e39a33e6` `COMPLETED`; Resultat `043ac802-1712-4834-8d84-bdafcf230413` `inconclusive`. Der Wiederholungslauf war idempotent; KB-Quick-Check `ok`, 0 FK-Fehler.
- Produktsoftware und Research-Infrastruktur bleiben aktiv. Ein validierter Trading-Edge ist nicht bestätigt. Automatische Strategiesuche ist pausiert; nur bereits autorisierte signalunabhängige Datensammler dürfen weiterlaufen.

### Multi-Asset Development v6

- Version: `multi-asset-opportunity-discovery-development-2026.09.05-v6`.
- Run-ID: `mad1-development-v6-f6432d72f806e9b97ea8ac46`.
- Der Run existierte bereits vor diesem Dokumentationsauftrag. Er wurde in diesem Auftrag weder gestartet noch fortgesetzt noch gestoppt.
- Laufstatus: `PAUSED_REQUIRES_REVIEW`.
- Phase: `RUN`.
- Fortschritt: 36,232315 %.
- Geplante Work-Units: 60.504.
- Terminal gezählt: 19.258 `COMPLETED`, 2.664 `SKIPPED`, 14 `FAILED`; 38.568 `PENDING`, 0 `ACTIVE`.
- Feature-Zeilen und Outcome-Zeilen: jeweils 840.517.
- Letzte erfolgreiche Work-Unit: `madv6-unit-97a99277c5720e31d3810ea571c54d85`.
- Letzter Work-Unit-Abschluss: `2026-09-06T00:36:57.959471+00:00`.
- Blocker: `EQUITIES:FLG:OperationalError:attempt to write a readonly database`.
- Nächste erlaubte Runtime-Aktion laut Chain-State: menschliche Prüfung; keine spätere Forschungsstufe öffnen.
- Beim Preflight lief kein Python-Prozess dieser v6-Kette. Die Lock-Datei war vorhanden; ihre bloße Existenz ist kein Beleg für einen gehaltenen Prozess-Lock.

### Development-v6-Vertrag und Belege

- Code-Basis im Run-Manifest: `e3ecdb6a1242c5922213ab489eb337342de0b17e`.
- Vier Worker, genau ein SQLite-Writer.
- Contract-Fingerprint: `bedf1c9297f1a5b409e13c78b5fc5f41eb33912ffb79fe711b0d3009d478a9d2`.
- Contract-Artefakt-Fingerprint: `77b04d19d79a59af63b6edaa0b510fb80bc9ad920a7909abf86e53c031735159`.
- Run-Manifest-Fingerprint: `5f22867717dbab667b3a705e6f481e9b1e88c8dbb4227dc694a4b1963097c232`.
- Code-Fingerprint: `fd1d95ce3c304c9772859b6e389fa67a4d97b5aa290029ec062eab54ef41feaf`.
- Kombinierter Input-Fingerprint: `bf762ed19c3212c849a43d7d0353f009fb7de714c59979f0a3d9cd83f8b38462`.
- Equity-/ETF-Projektion: `321531c482d844df4d5513b58646b3f41553f47a7b2276517cb8473886c298d6`.
- Crypto-Projektion: `475b78ee3dd0a45371b6dc0448b9d915d0a879dadabe4c2d385573fd1fe6bf91`.
- FX-Projektion: `a3c41cddd06d7b24596bac5f1e375868a86784ea5a6feeacd9b44f49598c5c91`.
- Identity: `d8bd34a3bac724f6ff15f4d33a03efe7b517518b2a71208046be11bc1530387e`.
- Dependency-Policy: `706b0b9e438464405f18d0972d49d34c553538c1236c3e7adb8fe37157214393`.
- Input-Precheck: `PASS`, Fingerprint `c69abb258908a1e51096c7782e19fc7443e12d885020a4a0e91388b3d5c7e9d3`.
- Worker-Benchmark: `PASS`, Fingerprint `8b41dc0a6923b2f07e1c8492ddcc67e31096eeba5e2d78bdd72a8af94b008ae2`.
- Deskriptiver Plan: `FROZEN`, Fingerprint `cad8fc8abc2a4962ed0d5f9cc1308740691d5a7bc145158488e43ca53554f94e`.
- Start-Gate: `PASS`, Fingerprint `772ca7498be2dd637ceefa120829b9b99de1f96b53678a7ec1a5f599fd165ecf`.
- Safety-Felder im Run-Manifest: Development-only `true`; Validation, Holdout, External, Forward, Paper, Shadow, Broker und automatische Orders jeweils `false`.

### Multi-Asset Development v7 Recovery

- Der Nutzer hat am 2026-09-13 einen getrennten Recovery-Lauf ausdrücklich freigegeben. v6 wird weder repariert noch zurückgesetzt noch unter seiner alten Run-ID fortgesetzt.
- Kanonische Recovery-Version: `multi-asset-opportunity-discovery-development-recovery-2026.09.13-v7-r2`.
- Kanonische Run-ID: `mad1-development-v7-recovery-20260913-v2`.
- Recovery-Contract-Fingerprint: `77cbb53de9a61fb9c68cc3169d2d14da20c6d38b2e669a870c804ec91b783ee5`.
- Der erste vorbereitete v7-Stand `mad1-development-v7-recovery-20260913-v1` erreichte ein vollständiges `PREPARED`-Gate, wurde aber nicht gestartet: Die Task-Installation stoppte vor der Registrierung, weil das lokale Windows-Modul keine nachträgliche Zuweisung an `Trigger.Repetition.Interval` unterstützt. Seine Stores und immutable Evidenz bleiben als ungestartete technische Vorbereitungsreferenz unverändert; v7-r2 verwendet deshalb eine neue Run-ID, neue Stores, neue Manifeste und neue Gate-Artefakte.
- Parent: v6-Run `mad1-development-v6-f6432d72f806e9b97ea8ac46`, Parent-Code `e3ecdb6a1242c5922213ab489eb337342de0b17e`, Parent-Contract `bedf1c9297f1a5b409e13c78b5fc5f41eb33912ffb79fe711b0d3009d478a9d2`.
- Readonly-Forensik: Die fehlschlagende Datei ist `runtime/multi_asset_discovery_v1_development_v6_outcomes.sqlite3`; der Fehler entstand beim Insert in `outcome_rows` für `EQUITIES:FLG`. Die erhaltene Telemetrie beweist keine einzelne Ursache. Die Klassifikation bleibt deshalb korrekt `I_UNKNOWN`; heutige Dateirechte, Verzeichnis-Schreibprobe, ACLs, Open-Mode und Read-only-Integritätsprüfungen liefern nur negative Gegenwartsbefunde.
- Fachlicher Diff: `research_semantics_diff_count = 0`. Universe, Development-Split, PIT-/Missingness-/Dependency-Verträge, Feature-/Outcome-Trennung, Safe-/Sell-Zonen, Deterioration, Zeitfenster und Censoring werden unverändert aus dem eingefrorenen v6-Contract verwendet.
- Der Lauf ist vollständig terminal `COMPLETED`: 60.504 Work-Units, davon 52.992 `COMPLETED`, 7.512 `SKIPPED`, 0 `FAILED`, 0 `ACTIVE`, 0 `PENDING` und 0 Retries. 21.922 verifizierte v6-Units wurden mit append-only Lineage wiederverwendet; 38.582 wurden ground-up neu berechnet.
- Feature- und Outcome-Store enthalten jeweils 2.356.553 Cases. Davon sind 1.749.125 `COMPLETE`, 486.312 `CENSORED_AT_STAGE_BOUNDARY`, 106.954 `CENSORED_AT_INPUT_GAP` und 14.162 `CENSORED_AT_END_OF_AVAILABLE_DATA`.
- Der Final Audit ist `PASS`: 0 Duplikate, 0 Orphans, 0 Link-Mismatches, 0 Payload-Fehler; alle drei SQLite-Stores bestehen Quick-/Integrity-/Foreign-Key-Prüfung und besitzen die erforderlichen Append-only-Trigger. Audit-Fingerprint: `b3dcb95ccfa0e603842358d8ebb2146b58230d852863d596b09c4ae949f53903`.
- Der Descriptive Development Report ist `DESCRIPTIVE_COMPLETE` mit Fingerprint `2eda1c028f49528253bbf1622493f7b8ef058e262ec3c6417a2d7903aecc2423`; die Completion Summary steht auf `V7_RECOVERY_COMPLETE_AWAITING_REVIEW` und besitzt Fingerprint `5a3e05085d38e513113a6f9a104d39f938146d40cc662beb1216fe13c2e422fc`.
- Der fünfminütige v7-r2-Windows-Task ist nach dem terminalen No-op-Verhalten deaktiviert; der Lauf wird nicht erneut gestartet.
- Validation, Holdout, External, Forward, Paper, Shadow, Broker, Orders und automatische Strategieoptimierung bleiben geschlossen.
- Der fachliche Review ist in [`MULTI_ASSET_DISCOVERY_V7_R2_DEVELOPMENT_REVIEW_2026-09-14.md`](MULTI_ASSET_DISCOVERY_V7_R2_DEVELOPMENT_REVIEW_2026-09-14.md) abgeschlossen. Alle 2.356.553 Feature-/Outcome-Paare wurden read-only auf Identität geprüft; Control-, Feature- und Outcome-Store blieben nach Größe und Änderungszeit unverändert.
- Review-Ergebnis: 0 `ROBUST_CANDIDATE_FOR_NEW_HYPOTHESIS`. Volatilität, RSI/Mean-Reversion, Sell-Zone-A-Distanz und Safe-Zone-Geometrie bleiben `INTERESTING_BUT_INSUFFICIENT`; Overnight/Gap/Intraday und Volume Ratio liefern keinen stabilen eigenständigen Zusatznutzen. Relative Strength, explizite HH/HL-/Konsolidierungs-/Breakout-/Pullback-Felder, Volatilitätsregime sowie Fundamentals/Event/Makro/Politik sind nicht ausreichend interpretierbar beziehungsweise nicht befüllt.
- Dependency-Grenze: Alle 2.356.553 Fälle besitzen `dependency_status = UNKNOWN`; nach dem eingefrorenen Vertrag ergibt sich effektives N 0. Das Signaljahr 2021 ist nur zu 0,5199 % vollständig. FX besitzt 0 vollständige Development-Outcomes.
- Historischer v7-r2-Stufenstand: `V7_R2_DEVELOPMENT_REVIEW_COMPLETE_AWAITING_HYPOTHESIS_DECISION`. Aus v7-r2 selbst wurde keine Hypothese und keine spätere Stufe automatisch geöffnet. Der danach getrennt freigegebene endliche R0–R9-Zyklus ist inzwischen terminal abgeschlossen; sein R6-Katalogeintrag ist oben separat dokumentiert.

### Development v5 und ältere Forschung

- Der v5-Run `mad1-development-a073df9096023f1da079a494` bleibt unveränderlich `COMPLETED_WITH_FAILURES`.
- Seine ursprünglichen Stores, Manifeste, Contracts und Ergebnisse bleiben historische Evidenz. v6 ersetzt diese Geschichte nicht.
- Buyer Confirmation v1 bleibt `REJECTED_AT_VALIDATION`. Kein Rescue, Retuning oder Holdout dieser Version.
- Legacy Forward v1 bleibt eingefroren. Er darf keine neuen Strategie-Signale, strategiegebundenen Paper-Trades oder Shadow-Orders erzeugen.
- Fibonacci-Duplikatprüfung und Buyer-Provenienz/Reproduktion sind abgeschlossen.
- Failed Seller bleibt `INCONCLUSIVE_RETAINED`; keine automatische Folgeforschung ist freigegeben.

#### Point-in-Time Event-/News-/Makro-/Geopolitik-Research

Dieser historische Research-/Shadow-Vertrag bleibt als geprüfter Status- und Regressionstest erhalten. Er ist keine aktive Urlaubsaufgabe und besitzt keine Produktionswirkung.

- Event-Schema: `swing-event-pit-2026.08.23-v2`.
- Event-Code-Fingerprint: `627ef8ca6b7be3f7d2e932d89d2f4f1d6f21cfc41e390ed0b98a8607452f20b8`.
- Gespeichert sind 24 generische, damals bekannte Unternehmenstermine für 20 Assets und 29 unveränderbare Sidecars vorhandener Forward-Signale.
- Historische Eventdaten, belastbare Expectations/Surprises sowie Macro-/Geopolitics-/Market-Shock-Coverage bleiben unvollständig beziehungsweise nicht verfügbar.
- Fehlende belastbare Eventinformation bedeutet nicht „kein Event“.
- Legacy Forward v1 ist eingefroren; der Event-Layer verändert keinen Score, kein Signal, keinen Stop, kein Ziel, keine Position und keinen Brokerstatus.

#### Konkreter echter Swing-Forward-Status

Historischer Diagnosevertrag vom 2026-08-22. Die 14 abgeschlossenen Legacy-Fälle bleiben read-only erhalten. Spätere Kursfenster und alternative Stops sind ausschließlich Counterfactual und keine echten Forward-Ergebnisse. Die Tabellen bleiben in der kanonischen Statusdatei, weil Regressionstests den konkreten Trade-Level-Vertrag absichern.

| Ticker | Setup | Entry | Stop | Ergebnis R | MFE R / % | MAE R / % | Sitzungen MFE / Exit | schlechter als Stop; Abweichung R/% |
|---|---|---:|---:|---:|---:|---:|---:|---|
| EWL | Breakout | 64,39 | 63,67 | -1,09 | 0,33 / 0,36 % | -1,02 / -1,14 % | 3 / 3 | ja; -0,02 R/-0,03 % |
| BANR | Breakout | 72,83 | 71,90 | -1,07 | 2,17 / 2,77 % | -1,01 / -1,28 % | 5 / 7 | nein; 0,00 R/0,00 % |
| ASB | Breakout | 32,16 | 31,68 | -1,06 | 0,63 / 0,94 % | -1,07 / -1,60 % | 2 / 5 | nein; 0,00 R/0,00 % |
| UMBF | Breakout | 150,89 | 148,35 | -1,05 | 0,96 / 1,61 % | -1,04 / -1,75 % | 3 / 5 | nein; 0,00 R/0,00 % |
| HOPE | Breakout | 14,46 | 14,34 | -1,10 | 1,02 / 0,91 % | -1,00 / -0,89 % | 1 / 3 | nein; 0,00 R/0,00 % |
| BATRK | Breakout | 53,21 | 52,44 | -1,06 | 1,04 / 1,49 % | -1,03 / -1,48 % | 1 / 3 | nein; 0,00 R/0,00 % |
| IJH | Breakout | 78,60 | 77,72 | -1,06 | 0,04 / 0,05 % | -1,02 / -1,15 % | 1 / 2 | nein; 0,00 R/0,00 % |
| LLYVA | Breakout | 104,25 | 103,05 | -1,11 | 0,00 / 0,00 % | -1,03 / -1,18 % | 1 / 1 | ja; -0,03 R/-0,03 % |
| LYV | Breakout | 186,93 | 185,58 | -1,12 | 0,26 / 0,19 % | -1,00 / -0,72 % | 1 / 1 | nein; 0,00 R/0,00 % |
| LT.NS | Breakout | 4061,45 | 4039,20 | -1,16 | 1,06 / 0,58 % | -1,19 / -0,65 % | 1 / 2 | nein; 0,00 R/0,00 % |
| LLYVK | Breakout | 108,51 | 106,94 | -1,06 | 0,00 / 0,00 % | -1,10 / -1,58 % | 1 / 1 | nein; 0,00 R/0,00 % |
| EWBC | Breakout | 136,25 | 134,99 | -1,14 | 0,96 / 0,89 % | -1,04 / -0,97 % | 1 / 2 | ja; -0,04 R/-0,04 % |
| SREN.SW | Breakout | 140,58 | 138,40 | -1,06 | 0,61 / 0,94 % | -1,05 / -1,62 % | 2 / 3 | nein; 0,00 R/0,00 % |
| BBT | Breakout | 32,61 | 32,19 | -1,07 | 0,27 / 0,34 % | -1,01 / -1,29 % | 2 / 2 | nein; 0,00 R/0,00 % |

Signalkontext und maschinell erzeugte sachliche Ursache bleiben je Fall im vollständigen historischen Statusarchiv erhalten.

5-/20-Sitzungs-Diagnose nach dem Stop, ausschließlich Counterfactual: Die späteren Felder bleiben `n/v`, solange die jeweils fünf beziehungsweise zwanzig Sitzungen nicht vollständig aus append-only Kontrollereignissen oder dem unveränderten Frozen-Datensatz verfügbar sind. Daily-Daten erfinden keine Intrabar-Reihenfolge.

Bei einem ausdrücklich freigegebenen relevanten Legacy-Diagnoseupdate wird dieser Block read-only mit `scripts/run_swing_edge_diagnostics.py --markdown` neu erzeugt. Er darf keine Strategie reaktivieren.

### Scheduler und laufender Betrieb

Der folgende Stand ist der zuletzt belegte Betriebszustand. Der v7-r2-Task wurde nach dem terminalen Lauf deaktiviert; dieser fachliche Review hat keinen Scheduler verändert.

| Windows-Aufgabe | Zustand | Letzter belegter Lauf | Ergebnis | Bedeutung |
|---|---|---|---:|---|
| `InvestmentAssistant-MultiAssetDiscoveryV1-Development-v7-Recovery-r2` | deaktiviert | 2026-09-14 | 0 | v7-r2 terminal; kein erneuter Scanstart |
| `InvestmentAssistant-MultiAssetDiscoveryV1-Development-v6-Chain` | deaktiviert | 2026-09-13 21:24 | 2 | v6 bleibt `PAUSED_REQUIRES_REVIEW`; keine Wiederaufnahme |
| `InvestmentAssistant-FX-PIT-Observer` | aktiviert / bereit | 2026-09-22 21:45 | 0 | getrennter append-only Datenobserver; COT-Catch-up repariert und Quelle am 2026-09-23 nachgezogen |
| `InvestmentAssistantDailyForecasts` | aktiviert / bereit | 2026-09-22 22:30 | 0 | allgemeine Abendkette; 324 erfolgreich, 1 expliziter Assetfehler, 0 Rate-Limits |
| `InvestmentAssistant-MultiAssetDiscoveryV1-Development` | deaktiviert | 2026-09-03 14:40 | 267014 | alter Development-v5-Scheduler |
| `InvestmentAssistantSwingResearchCampaign` | deaktiviert | 2026-08-28 13:10 | 0 | alte historische Kampagne |
| `InvestmentAssistantSwingScan-asia` | deaktiviert | 2026-08-28 10:30 | 0 | Legacy-Swing |
| `InvestmentAssistantSwingScan-europe` | deaktiviert | 2026-08-27 18:15 | 0 | Legacy-Swing |
| `InvestmentAssistantSwingWalkForward` | deaktiviert | 2026-08-22 11:00 | 1073807364 | alte Walk-Forward-Aufgabe |

`Ergebnis 0` bedeutet bei den Windows-Aufgaben einen erfolgreichen Prozessabschluss. Der pausierte v6-Chain-State ist maßgeblich für den Research-Fortschritt; wiederholte Scheduler-Aufrufe sind keine Freigabe zum Übergehen des Review-Stopps.

#### Uhrzeitfreie Historical-Research-Gates

- Die früheren allgemeinen Sperren 09:00–11:30, 15:45–18:45 und 20:00–23:59 sind Legacy-Betriebslogik. Ihre ursprünglichen Fenster und 90-Minuten-Vorläufe bleiben in der historischen Konfiguration und im Archiv nachvollziehbar, besitzen aber keine aktive Start-, Fortsetzungs- oder Resume-Wirkung mehr auf Historical Research/Development.
- Alle aktiven historischen Einstiegspfade verwenden die gemeinsame deterministische Entscheidung `historical_research_runtime_gate`. Diese Entscheidung wertet keine Uhrzeit aus. Sie blockiert bei einem gehaltenen oder nicht sicher prüfbaren, als inkompatibel konfigurierten Produktions-Lock mit `BLOCKED_REAL_CONFLICT`; eine bloß vorhandene verwaiste Lock-Datei blockiert nicht.
- Der globale Research-Lock, kampagnen- beziehungsweise runspezifische Doppelstart-Locks, SQLite-Sicherheitspausen, Integritätsgates sowie belegte Disk-/RAM-Grenzen bleiben unverändert fail-closed. Nach Ende eines realen Prozesskonflikts darf der nächste Trigger wieder starten beziehungsweise resumieren.
- Die konfigurierten echten Produktionskonflikte bleiben der aktive Swing-Live-/Forward-Prozess und die allgemeine Prognose-Abendkette – jeweils nur für die tatsächliche Dauer ihres gehaltenen Locks, nicht schon Stunden vor ihrem geplanten Start.
- Legacy Forward v1 und seine regionalen Aufgaben bleiben eingefroren beziehungsweise deaktiviert. Diese Änderung reaktiviert keine Signale, Paper-/Shadow-Trades oder Handelsfunktion.
- Der FX-PIT-Observer bleibt aktiviert und getrennt: eigene DB `runtime/fx_forward_pit.sqlite3`, eigener Lock `runtime/fx_forward_pit.collector.lock`, drei tägliche FX-Paare und höchstens drei Yahoo-Daily-Anfragen pro Lauf. Er schreibt nicht in die Multi-Asset-Evidence-Stores und ist deshalb kein pauschaler Multi-Asset-Research-Blocker.
- Multi-Asset Development v6 war bereits uhrzeitunabhängig. Sein aktueller Zustand bleibt unverändert `PAUSED_REQUIRES_REVIEW` bei 36,232315 % wegen `EQUITIES:FLG:OperationalError:attempt to write a readonly database`. Die neue Lock-Logik hebt diese SQLite-Sicherheitspause nicht auf und hat den Lauf nicht gestartet oder resumiert.

### Daten- und Identity-Stand

- Das Research-Identity-System trennt Asset, Listing und Issuer. Verifizierte Beziehungen und unbekannte Abhängigkeiten bleiben getrennt.
- Die heutige Identity-Zuordnung wird nicht als historische Beziehung rückdatiert.
- Die v6-Inputs verwenden getrennte geprüfte Equity-/ETF-, Crypto- und FX-Projektionen.
- Nichtpositive strukturelle Risiken erhalten keinen erfundenen R-Wert.
- Fehlende oder ausgeschlossene Bars bleiben sichtbar; kein Clipping, keine Imputation und keine Interpolation.
- `TECHNIK VORHANDEN`, `DATEN VORHANDEN`, `EVIDENZ VORHANDEN` und `AKTIVIERT` sind unterschiedliche Zustände. Der vollständige aktuelle A–M-Coverage-Bericht ist erstellt; fehlende PIT-Evidenz bleibt sichtbar und wurde nicht durch heutige Daten rückdatiert.

### Knowledge Base

- Die Research Knowledge Base bleibt die append-only Quelle für Sources, Hypothesen, Experimente, Resultate und Work Requests.
- Der Wasser-Work-Request `3721453e-158f-42cb-8d76-a28f054b7d97` ist `COMPLETED` mit Result-ID `99197886-6ff7-4e37-a811-73ee4abe9b1a`. Der Gold/Silber-Work-Request `4fdfb983-ddbc-4178-bd36-7aa34267df0b` ist `BLOCKED` und hat kein Resultat. Sein Experiment bleibt `DRAFT`; der [R2-Daten-Gate-Bericht](GOLD_SILVER_R2_DATA_GATE_2026-09-22.md) ist als Experimentreferenz in der KB verknüpft.
- R1 Development ist terminal `DEVELOPMENT_INCONCLUSIVE`: 7 Primärfälle, Effective N 3/4, Validity Gate `UNDERPOWERED`; Validation und Holdout wurden nicht geöffnet. Der [R1-Review](WATER_INFRASTRUCTURE_R1_REVIEW_2026-09-22.md) dokumentiert Scope, Kosten, Datenlimit und Fingerprints. R2 wurde danach nur vorgeprüft: Yahoo-Proxies ohne belegte historische Rollkette, alte Einzelkontrakte nicht verfügbar, CME-Alternative lizenzierte Settlement-Serie ohne vorregistrierten Next-Open-Entry. Der [technische Abschluss](FINITE_RESEARCH_PROGRAM_TECHNICAL_STOP_2026-09-22.md) enthält den vollständigen Seen-/Unseen- und Safety-Stand.
- Die Overnight-/Intraday-Renditetrennung war zuvor `CONDITIONAL_RESEARCH_RESERVE`. Im freigegebenen R3 wurde eine eigene Vertragslücke dokumentiert und genau ein deskriptiver Development-Versuch ausgeführt. Das KB-Experiment ist nun `COMPLETED`, Resultat `negative` nur für den vorab definierten Overnight-Bias-Baseline-Vergleich; kein aktiver Filter, kein Challenger und keine Validation/Holdout-Evidenz.
- `READY`, `DRAFT` oder technische Verfügbarkeit sind keine positive Evidenz und keine Validation-, Produktions- oder Handelsfreigabe.
- Durch die Backlog-Dokumentation wurde kein Experiment, Research-Runner, Performance-Lauf, Validation- oder Holdout-Schritt gestartet.

### Produkt- und Handelsgrenze

- Die Anwendung ist Analyse- und Research-Infrastruktur, keine Echtgeld-Handelsfreigabe.
- Es gibt keine Brokeranbindung und keine automatische Orderausführung.
- Keine Strategie-, Score-, Ranking-, Risiko- oder Produktionsregel wurde durch die Dokumentationsbereinigung geändert.
- Das langfristige Zielbild steht in [`SWINGTRADER_PRODUCT_ARCHITECTURE.md`](SWINGTRADER_PRODUCT_ARCHITECTURE.md) und ist keine Behauptung über aktuelle Funktionen.

### Aktueller nächster Schritt

Das endliche Programm R0–R9 bleibt mit `NO_ROBUST_EDGE_FOUND_IN_APPROVED_RESEARCH_PROGRAM` abgeschlossen. Die danach freigegebene begrenzte Informationslayer-Runde endet vor Development mit `RESEARCH_BLOCKED_BY_INSUFFICIENT_PIT_DATA`. Nächster zulässiger Schritt ist ausschließlich prospektive, signalunabhängige Datensammlung über die bereits genehmigten Collector und ein späterer neuer Coverage-Review; es existiert kein freigegebener automatischer Strategietest. Validation, Holdout, External, Forward, Paper, Shadow-Ausführung, Broker, Orders und Produktionsstrategie blieben ungeöffnet beziehungsweise unverändert.
