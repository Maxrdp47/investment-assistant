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
