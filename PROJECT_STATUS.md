# Investment Assistant – Projektstatus

Diese Datei enthält nur den aktuell belegten Ist-Stand. Planung und Freigaben stehen in [`ROADMAP.md`](ROADMAP.md). Dauerhafte Forschungsregeln stehen in [`RESEARCH_POLICY.md`](RESEARCH_POLICY.md). Frühere Fassungen wurden unverändert nach [`docs/archive/PROJECT_STATUS_LEGACY_THROUGH_2026-09-06.md`](docs/archive/PROJECT_STATUS_LEGACY_THROUGH_2026-09-06.md) verschoben.

## Current Truth – 2026-09-22

### Git und Dokumentation

- Aktiver Branch des endlichen Research-Programms: `codex/final-finite-research-program`; Ausgangs-HEAD ist der vollständig geprüfte v7-r2-Review-Commit `fb56ea820ec28befc57a67e091a18d9c19d77b72`.
- Der Review-Stand wurde am 2026-09-15 ohne Divergenz per normalem Fast-Forward auf `origin/main` integriert. Er liegt damit nicht mehr nur auf dem Recovery-Branch.
- Ausgangs-HEAD des Recovery-Auftrags: `9990fbf557b414a51ca450aabb2a89f278d00d47`.
- Geprüfter Projekt-HEAD und Upstream vor dem v7-r2-Review-Commit: `30e26f2157e8a1b3eae761fd1cac73b71a462b92`.
- Die Urlaubs-Workqueue `vacation-workqueue-2026-09-06-v1` ist dokumentiert, aber noch nicht gestartet.
- Vor einem ausdrücklichen Startsignal wurden keine neue Funktion, kein Benchmark, kein Scan, kein Reprocessing-Lauf, kein Collector und keine Agenten-Wiederaufnahme gestartet.
- Der Nutzer hat den endlichen Research-Programmzyklus `finite-research-program-2026-09-15-v1` von R0 bis spätestens R9 ausdrücklich gestartet und am 2026-09-22 mit „weiter“ fortgesetzt. R0 und der einzelne R1-Wasser-Versuch sind abgeschlossen. R2 Gold/Silber scheiterte **vor jedem Performance-Lauf** am Futures-Daten-/Methodik-Gate. Die frühere Einstufung als globaler technischer Stop ist überholt. R3 ist nach einem einzigen deskriptiven Development-Versuch terminal ohne robusten Zusatznutzen. R4-A–I sind outcome-frei abgeschlossen oder ehrlich begrenzt: nur kausale Preis-/Struktur-, globale Benchmark- und Crypto-OHLCV-Familien sind begrenzt nutzbar; Fundamentals, Events, Makro, Politik, COT, historische FX-Discovery, historische Issuer-Abhängigkeiten und historische Universe-Mitgliedschaft sind shadow/unavailable/not-testable. Das Frozen Equity-/ETF-Panel ist rückblickend aus einem 2026er Universum ausgewählt und trägt eine nicht quantifizierbare Survivorship-Grenze. R5 ist erst nach grünem R4-H/I-CI zu öffnen; R6–R9 bleiben geschlossen.
- Der endgültige Programm-Commit ist der Commit, der die Abschlussfassung enthält; der Abschlussbericht nennt seinen Hash und den CI-Stand.
- Der unmittelbar vorher getrennt abgeschlossene ENTRY-Handoff-Importer liegt in Commit `b1e3802b807649bc2cf871fa31ccf09fd8781cac`. Er gehört nicht zur Urlaubs-Queue und wurde nicht mit diesem Dokumentationspaket vermischt.

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
- Finaler fachlicher Stand: `V7_R2_DEVELOPMENT_REVIEW_COMPLETE_AWAITING_HYPOTHESIS_DECISION`. Keine Hypothese, keine Folgeforschung und keine spätere Stufe wurde automatisch geöffnet; die Knowledge Base erhielt kein Strategieergebnis.

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
| `InvestmentAssistant-FX-PIT-Observer` | aktiviert / bereit | 2026-09-14 21:45 | 0 | getrennter append-only Datenobserver; letzter Lauf erfolgreich |
| `InvestmentAssistantDailyForecasts` | aktiviert / bereit | 2026-09-14 22:30 | 0 | allgemeine Abendkette; letzter Lauf erfolgreich |
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
- `TECHNIK VORHANDEN`, `DATEN VORHANDEN`, `EVIDENZ VORHANDEN` und `AKTIVIERT` sind unterschiedliche Zustände. Ein vollständiger Coverage-Bericht ist als U3 geplant, aber noch nicht erstellt.

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

R0 bleibt abgeschlossen und v7-r2 immutable mit 0 robusten Kandidaten. R1 ist als unterpowerter Einzelversuch terminal. R2 ist vor Research-Freeze/Development an der fehlenden überprüfbaren Kontrakt-/Roll-/Open-Provenienz blockiert. Der [einzige R3-Versuch](OVERNIGHT_INTRADAY_R3_REVIEW_2026-09-22.md) ist nach 2.297 Asset-/Listing-Einheiten abgeschlossen: medianes partielles r für 1/5/20 Sitzungen +0,0041/+0,0012/−0,0103, zeitlich instabil und nur auf bereits gesehenen Development-Daten. KB-Resultat `3cc7e3a9-47a9-4e01-a20a-fd4e1e6f43d1`, kein Challenger; Validation und Holdout ungeöffnet. R4-A–H sind in den verlinkten Capability-Berichten begrenzt. Der [R4-I-Survivorship-Audit](R4_I_SURVIVORSHIP_UNIVERSE_AUDIT_2026-09-22.md) belegt: 2.488 Equity-/ETF-Einheiten im 2026 zusammengestellten Frozen Scope, 2.297 mit aktiven historischen Balken, aber keine historische Constituent-/Delisting-/Pleite- oder Vorgängerzuordnung. Eine Gesamtmarktrepräsentativität und die Richtung des Survivorship-Effekts sind nicht quantifizierbar. R4 ist damit outcome-frei vollständig; R5 wartet auf grünen R4-CI, R6–R9 bleiben geschlossen. External, Forward, Paper, Shadow-Ausführung, Broker, Orders und Produktion bleiben geschlossen.
