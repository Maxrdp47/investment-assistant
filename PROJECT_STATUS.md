# Investment Assistant – Projektstatus

Diese Datei enthält nur den aktuell belegten Ist-Stand. Planung und Freigaben stehen in [`ROADMAP.md`](ROADMAP.md). Dauerhafte Forschungsregeln stehen in [`RESEARCH_POLICY.md`](RESEARCH_POLICY.md). Frühere Fassungen wurden unverändert nach [`docs/archive/PROJECT_STATUS_LEGACY_THROUGH_2026-09-06.md`](docs/archive/PROJECT_STATUS_LEGACY_THROUGH_2026-09-06.md) verschoben.

## Current Truth – 2026-09-06

### Git und Dokumentation

- Aktiver Branch beim Dokumentations-Preflight: `codex/multi-asset-development-v6`.
- Geprüfter Projekt-HEAD und Upstream vor dem Dokumentationscommit: `b1e3802b807649bc2cf871fa31ccf09fd8781cac`.
- Die Urlaubs-Workqueue `vacation-workqueue-2026-09-06-v1` ist dokumentiert, aber noch nicht gestartet.
- Vor einem ausdrücklichen Startsignal wurden keine neue Funktion, kein Benchmark, kein Scan, kein Reprocessing-Lauf, kein Collector und keine Agenten-Wiederaufnahme gestartet.
- Der endgültige Dokumentations-Commit ist der Commit, der diese Fassung enthält; der Abschlussbericht nennt seinen Hash und den CI-Stand.
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

Der folgende Stand wurde nur lesend geprüft. Keine Aufgabe wurde in diesem Dokumentationsauftrag geändert.

| Windows-Aufgabe | Zustand | Letzter belegter Lauf | Ergebnis | Bedeutung |
|---|---|---|---:|---|
| `InvestmentAssistant-MultiAssetDiscoveryV1-Development-v6-Chain` | aktiviert / bereit | 2026-09-06 03:54 | 2 | vorhandene fünfminütige Kette; Chain-State bleibt review-pausiert |
| `InvestmentAssistant-FX-PIT-Observer` | aktiviert / bereit | 2026-09-05 21:45 | 0 | getrennter append-only Datenobserver, nächste reguläre Zeit 21:45 |
| `InvestmentAssistantDailyForecasts` | aktiviert / bereit | 2026-09-05 22:30 | 0 | allgemeine Abendkette, nächste reguläre Zeit 22:30 |
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
- Aktuell sind genau zwei Work Requests `READY`: Gold/Silber `4fdfb983-ddbc-4178-bd36-7aa34267df0b` und Wasseraktien `3721453e-158f-42cb-8d76-a28f054b7d97`.
- `READY` in der KB ist keine Urlaubsfreigabe. Beide Aufträge sind in der aktuellen Queue ausdrücklich nicht autorisiert.

### Produkt- und Handelsgrenze

- Die Anwendung ist Analyse- und Research-Infrastruktur, keine Echtgeld-Handelsfreigabe.
- Es gibt keine Brokeranbindung und keine automatische Orderausführung.
- Keine Strategie-, Score-, Ranking-, Risiko- oder Produktionsregel wurde durch die Dokumentationsbereinigung geändert.
- Das langfristige Zielbild steht in [`SWINGTRADER_PRODUCT_ARCHITECTURE.md`](SWINGTRADER_PRODUCT_ARCHITECTURE.md) und ist keine Behauptung über aktuelle Funktionen.

### Aktuelle nächste Entscheidung

Die nächste erlaubte Umsetzung beginnt erst nach einem ausdrücklichen Startsignal für die Urlaubs-Workqueue. Dann ist zuerst U0 abzuschließen und der technische Schreibfehler des vorhandenen Development-v6-Runs sicher zu prüfen. Vorher bleibt die Queue `PREPARED_NOT_STARTED`.
