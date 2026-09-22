# Investment-Assistent – kanonische Roadmap

Stand: 2026-09-22

Diese Datei enthält ausschließlich zukünftige Arbeit, ihre Reihenfolge und ihre Freigabe. Der belegte Ist-Stand steht in [`PROJECT_STATUS.md`](PROJECT_STATUS.md). Dauerhafte Forschungsregeln stehen in [`RESEARCH_POLICY.md`](RESEARCH_POLICY.md). Frühere Roadmap-Fassungen bleiben unverändert im [Historienarchiv](docs/archive/ROADMAP_LEGACY_THROUGH_2026-09-06.md).

## Verbindliches Start-Gate

Der Nutzer hat am 2026-09-15 genau den unten beschriebenen endlichen Research-Programmzyklus `R0` bis `R9` freigegeben. Diese Freigabe ersetzt für Wasser, Gold/Silber, die bedingte Overnight-Prüfung und Multi-Asset Discovery v2 die frühere Warteposition, erweitert den Umfang aber nicht über `R9` hinaus.

Der getrennte Multi-Asset-Development-v7-r2-Recovery-Lauf und sein fachlicher Development-Review sind abgeschlossen. Der Review fand 0 `ROBUST_CANDIDATE_FOR_NEW_HYPOTHESIS`; v6, v7-r1 und sämtliche v7-r2-Stores und Artefakte bleiben immutable. Validation und Holdout dürfen innerhalb dieses Programms nur für eine vorher eingefrorene Version und nur nach bestandenem vorgelagertem Gate automatisch geöffnet werden. External, True Forward, Paper, Shadow, Broker, Orders, Live und Produktionsintegration bleiben geschlossen.

Historische Großläufe werden sequenziell ausgeführt. Vor Start oder Resume entscheiden ausschließlich reale Prozess-, Lock-, Integritäts- und Ressourcen-Gates; alte starre Uhrzeitfenster besitzen keine Steuerungswirkung. Ein terminales Research-Fail darf technisch dokumentiert, aber nicht durch Retuning, neue Schwellen oder zusätzliche Filter repariert werden.

## Aktiver endlicher Research-Programmzyklus R0–R9

- Programm-ID: `finite-research-program-2026-09-15-v1`
- Ausgangs-HEAD: `fb56ea820ec28befc57a67e091a18d9c19d77b72`
- Ausführungsreihenfolge: `R0 → R1 → R2 → R3 → R4 → R5 → R6 → R7 → gegebenenfalls R8 → R9`
- Early-Success-Stop: erster unveränderter Kandidat mit Development-/Robustheits-PASS, Validation-PASS und Holdout-PASS führt zu `ROBUST_HOLDOUT_CANDIDATE_FOUND_AWAITING_USER_REVIEW` und beendet alle weiteren automatischen Strategieprüfungen.
- Negativer Stop: nach Ausschöpfung der zugelassenen Versuche führt fehlender Holdout-PASS zu `NO_ROBUST_EDGE_FOUND_IN_APPROVED_RESEARCH_PROGRAM`.
- Technischer Stop: eine nicht innerhalb des Vertrags sauber behebbare Daten- oder Technikgrenze führt zu `RESEARCH_PROGRAM_BLOCKED_BY_DATA_OR_TECHNICAL_LIMIT_REQUIRES_REVIEW`.

| Block | Status | Voraussetzungen | Scope | Attempt Count | Inputs / Fingerprints | Gate | Kill Rule | `next_step` |
|---|---|---|---|---:|---|---|---|---|
| R0 – v7-r2 kanonisch abschließen | `DONE` | Final Audit, Descriptive Report, Completion Summary und fachlicher Review | Run `mad1-development-v7-recovery-20260913-v2`; reine Bestandsprüfung | 0 neue Research-Versuche | Code `86156d17a9b43febf34cb2a94e72529ad7916f23`; Review-Commit `fb56ea820ec28befc57a67e091a18d9c19d77b72`; Contract `77cbb53de9a61fb9c68cc3169d2d14da20c6d38b2e669a870c804ec91b783ee5`; Audit `b3dcb95ccfa0e603842358d8ebb2146b58230d852863d596b09c4ae949f53903` | Audit `PASS`; Review vollständig; 0 robuste Kandidaten | v7-r2 nie verändern oder daraus nachträglich eine Regel ableiten | R1-Vertrag, Splits, Kosten, Datenqualität und Duplicate-Status vor Ergebnis einfrieren |
| R1 – Wasser-Hypothese | `DONE_DEVELOPMENT_INCONCLUSIVE` | R0 `DONE`; Vertrag und Dataset vor Ergebnissichtung eingefroren | `XYL`, `BMI`, `PNR`, `SPY`, `PHO`; Einzelwerte und Wasser-Korb getrennt; Daily; outcome-unabhängige Splits | 1/1 | Work Request `3721453e-158f-42cb-8d76-a28f054b7d97` `COMPLETED`; Dataset `a12525a8a6b4c1165fe7cea2ee725d42ef6b6f858c49b4ccac9899abd4b2c78d`; Review `ed7439b8b4446d40428a0f6ec2eeb57bc22a4501c2ac18e208f3cf1593fdf5dc` | Development `UNDERPOWERED`: 7 Primärfälle, Effective N 3/4 statt 100; Validation/Holdout ungeöffnet | kein Wasser-Retune, keine Einzeltitelauswahl, kein Performance-Claim | [R1-Review](WATER_INFRASTRUCTURE_R1_REVIEW_2026-09-22.md); R2-Futures-Preflight öffnen |
| R2 – Gold/Silber | `ACTIVE_PREFLIGHT` | R1 terminal ohne Holdout-PASS | `GC=F`, `SI=F`, relative Divergenz; Futures-Roll, Sessions, PIT, Next-Open, Kosten und Slippage | 0 | Work Request `4fdfb983-ddbc-4178-bd36-7aa34267df0b`; Hypothese `f8e6a64b-1cf9-431f-9477-4a7a17ab5478`; Experiment `255532e0-3b54-412a-a29e-866bfe4bda82`; Fingerprints vor erstem Ergebnis | Development → Freeze → Validation-PASS → einmaliger Holdout | kein Equity-Runner mit falscher Semantik; keine Roll-Lücke verstecken; kein Rescue | Futures-Quelle, Roll-/Adjustment-Semantik und isolierten Vertrag prüfen, bevor Daten oder Outcomes geöffnet werden |
| R3 – Overnight/Intraday | `BLOCKED_BY_SEQUENCE` | R2 terminal ohne Holdout-PASS; Contract-Deduplizierung | Zuerst prüfen, ob v7-r2 den geplanten Vertrag vollständig beantwortet; andernfalls genau eine fachlich eigenständige Version | 0 | v7-r2-Review und bestehender Overnight-Research-Vertrag; neue Fingerprints nur falls echte Vertragslücke | Dedupe-PASS ohne neuen Run oder einmaliger Development-/Validation-/Holdout-Pfad | kein Doppeltest, keine neue Schwelle, keine Kombination | erst nach terminalem R2 deduplizieren |
| R4 – Historical/PIT Capability Expansion | `BLOCKED_BY_SEQUENCE` | R3 terminal ohne Holdout-PASS; keine v2-Outcomes betrachtet | A Identity/Dependencies; B Relative Strength/Struktur; C Fundamentals; D Events; E Makro/Rates; F Politik; G FX; H Crypto; I Survivorship | 0 Research-Versuche; Infrastruktur zählt nicht als Strategie-Attempt | vorhandene Identity-, Equity/ETF-, Crypto-, FX-, COT-, Event-, SEC- und KB-Stores; genaue Fingerprints im Capability Freeze | ausschließlich Coverage, Zeitstempel, Quelle, Missingness, Revisionen und Integrität | keine Capability nach Performance aktivieren; heutige Daten nie rückdatieren; keine minderwertige Ersatzquelle | nach R3 Daten-/Messlücken isoliert schließen und auditieren |
| R5 – Discovery-v2 Contract Freeze | `BLOCKED_BY_SEQUENCE` | R4 abgeschlossen oder ehrlich begrenzt; Capability Report und Coverage Matrix vorhanden | Feature-, Source-, Missingness-, Outcome-, Seen-Data-, Kosten- und Split-Vertrag | 0 | neue Dataset-/Contract-/Code-/Capability-Fingerprints vor Outcomes | jede Familie genau `ACTIVE_PIT`, `ACTIVE_PIT_LIMITED_SCOPE`, `SHADOW`, `UNAVAILABLE` oder `STRUCTURAL_NOT_APPLICABLE`; bestehendes Quality-C-Gate unverändert | kein Freeze nach Ergebnissichtung; Missing nicht zu False/0 | alle v2-Verträge und Fingerprints unveränderlich persistieren |
| R6 – Discovery v2 Development | `BLOCKED_BY_SEQUENCE` | R5 Freeze vollständig und Integritäts-/Replay-Pilot `PASS` | Horizon-spezifische 20/60/120/252-Populationen; Einzelfeatures/-familien; keine Massenkombination | 0 | neue Run-ID und neue append-only Stores; Fingerprints aus R5 | vollständiger vorab definierter deskriptiver Review und kanonisches C-/Robustheitsgate | keine Validation während Discovery; kein Gesamt-Score; keine Top-Auswahl nach Profit | Development vollständig ausführen und deskriptiv reviewen |
| R7 – maximal drei v2-Challenger | `BLOCKED_BY_SEQUENCE` | R6 Review; höchstens drei fachlich plausible, nicht redundante C-Kandidaten | pro Kandidat eine einfache Featurefamilie oder einzelne Bedingung; Interaktion nur separat präregistriert | 0 von maximal 3 | je Version eigene Rule-, Scope-, Feature-, Dataset-, Entry-, Outcome-, Kosten-, Split- und Fingerprint-Freeze | Development-Gate → Validation; nur Validation-PASS → einmaliger Holdout | Validation-/Holdout-Fail terminal; keine Änderung nach Freeze; erster Holdout-PASS beendet das Programm | Kandidaten nach Evidenzqualität, Einfachheit und Nicht-Redundanz priorisieren |
| R8 – begrenzte Research Reserve | `BLOCKED_CONDITIONAL` | kein Holdout-PASS in R1–R7; keine offenen validierbaren R7-Kandidaten; konkrete dokumentierte Informationslücke | maximal zwei Einzelhypothesen insgesamt aus genau begründeter Momentum-, Trend-, ROC- oder kleiner Candle-Reserve | 0 von maximal 2 | je Hypothese eigener KB-/Ledger-Eintrag, Mechanismus, Scope, Parameter, Attempt und Freeze | individuelle Development-/Validation-/Holdout-Gates | kein pauschaler Indikatorlauf, keine Grid Search, keine Auswahl nach Profit, kein Rettungstest | nur bei erfülltem fachlichem Trigger aktivieren; sonst direkt R9 |
| R9 – Gesamtentscheidung und STOP | `BLOCKED_BY_SEQUENCE` | alle zulässigen Pfade terminal oder Early Success | vollständiges Ledger, Seen-Data-Register, Capability-/Coverage-Grenzen und Safety-Abschluss | keine neuen Attempts | sämtliche R0–R8-Artefakte und Fingerprints | genau einer der drei freigegebenen finalen Gesamtzustände | nach Finalstatus keine weitere automatische Trading-Forschung | finalen Abschlussbericht erzeugen, offene automatischen Strategietests pausieren und auf Nutzerreview warten |

Kein anderer `READY`-Work-Request und keine außerhalb dieser Tabelle liegende Idee darf als Ersatz ausgewählt werden. Autorisierte signalunabhängige Collector dürfen weiterlaufen, sofern sie keinen echten Prozess-, Lock-, DB- oder Ressourcen-Konflikt verursachen.

## Frühere Urlaubs-Workqueue – nicht mehr aktive Steuerkette

- Queue-ID: `vacation-workqueue-2026-09-06-v1`
- Planungsstatus: `U1_V7_R2_REVIEW_COMPLETE`; übrige Pakete unverändert
- Ausführungsfreigabe jetzt: `false`
- Freigabe nach ausdrücklichem Startsignal: nur U0 bis U7 im unten beschriebenen Umfang
- Priorität: U0 kurz abschließen, danach U1; während eines gesunden isolierten U1-Prozesses dürfen unabhängige Teile von U2 bis U6 folgen
- Schwerer Rechenbetrieb: höchstens ein historischer Großlauf gleichzeitig
- Schreibschutz: genau eine Work-Schreibsitzung für dieselben Projektdateien
- Resume-Stand: [`VACATION_WORKQUEUE_RESUME.md`](VACATION_WORKQUEUE_RESUME.md)

| ID | Hauptziel | Status am 2026-09-06 | `authorized_for_unattended` jetzt | Nach Startsignal |
|---|---|---|---:|---:|
| U0 | Stand übernehmen, Freigaben und Resume organisieren | PARTIAL | false | true |
| U1 | Getrennten Development-v7-Recovery-Lauf, Audit und Bericht abschließen | DONE | false | abgeschlossen; keine weitere Aktion |
| U2 | Roadmap, Current Truth, Historie und Regeln bereinigen | DONE | false | keine weitere Arbeit ohne neue Lücke |
| U3 | Tatsächliche Daten- und Betriebsabdeckung sichtbar machen | READY | false | true |
| U4 | FX-Observer und allgemeinen Prognosebetrieb prüfen | READY | false | true |
| U5 | Begrenzten signalunabhängigen Daten-Observer umsetzen | READY | false | true |
| U6 | Forschungsnachweise und Review-Punkte ordnen | READY | false | true |
| U7 | Gesamtprüfung und Urlaubsabschluss erstellen | BLOCKED | false | true, nachdem U0–U6 terminal sind |

`DONE` bei U2 bezeichnet nur die ausdrücklich vorab erlaubte Dokumentationsbereinigung. Es startet keine übrige Queue-Arbeit.

### U0 – Stand, Freigaben und Resume

- **Ziel und Priorität:** Kanonischen Ist-Stand übernehmen, Doppelstarts verhindern und eine belastbare Fortsetzung vorbereiten. Höchste kurze Startaufgabe.
- **Aktueller Status:** `PARTIAL`. Git, Runtime, vorhandene Scheduler und die pausierte v6-Kette wurden für diese Dokumentation gelesen. Eine Agenten-Wiederaufnahme wurde bewusst nicht eingerichtet.
- **Voraussetzungen:** ausdrückliches Startsignal; unveränderter Queue-Vertrag; keine zweite schreibende Work-Sitzung.
- **Erlaubter Umfang nach Start:** Prozesse, Locks, Scheduler und Queue prüfen; einen unterstützten Resume-Weg untersuchen; ausschließlich eine kanonische Wiederaufnahme einrichten, wenn sie nachweislich Modellarbeit fortsetzen kann.
- **Akzeptanz:** Task-/Automation-ID, Projektzugriff, gespeicherter Auftrag, nächste Ausführung, Registrierung und kontrollierter Funktionstest sind belegt. Andernfalls ehrlich `MANUAL_MODEL_RESUME_REQUIRED`.
- **Stop-Bedingungen:** kein offiziell unterstützter Weg; Kontingent-/Anbietergrenze; unklarer Doppelstart; Nutzerstopp; Queue bereits fertig.
- **Referenzen:** [`VACATION_WORKQUEUE_RESUME.md`](VACATION_WORKQUEUE_RESUME.md), `runtime/multi_asset_discovery_v1_development_v6_chain_state.json`.
- **Nächster zulässiger Schritt:** Nach Startsignal zuerst den v6-Blocker und vorhandene Tasks erneut lesen. Keine Automation vorher anlegen.

### U1 – Development-v7-Recovery abschließen

- **Ziel und Priorität:** v6 als unveränderliche terminal pausierte Referenz erhalten und die exakt kompatible Restarbeit in einem neuen v7-Recovery-Run ausführen; anschließend Voll-Audit, begrenzten deskriptiven Bericht und Summary erzeugen. Höchste fachliche Priorität.
- **Aktueller Status:** `DONE`. v6 bleibt bei 36,232315 % und `PAUSED_REQUIRES_REVIEW`; der ungestartete v7-r1-Stand bleibt unverändert. `mad1-development-v7-recovery-20260913-v2` ist mit 60.504 terminalen Work-Units abgeschlossen, sein Final Audit ist `PASS`, und der fachliche Review steht auf `V7_R2_DEVELOPMENT_REVIEW_COMPLETE_AWAITING_HYPOTHESIS_DECISION`.
- **Voraussetzungen:** v6 read-only; Root-Cause-Kategorie ehrlich belegt; Research-Semantik-Diff null; nur receipt- und digest-verifizierte terminale Units wiederverwenden; neue Stores/Run-ID; lokaler Gesamtcheck, Commit/Push/CI und echter Scheduler-Kontext-Pilot `PASS`.
- **Erlaubter Umfang:** 21.922 verifizierte v6-Units mit expliziter Lineage importieren, 38.582 Units ground-up rechnen, Checkpoints nutzen, genau einen Writer und vier Worker beibehalten, danach Audit → Bericht → Summary → Stop.
- **Nicht erlaubt:** neue Hypothese, Parameter-/Filter-/Kombinationssuche, Clipping, Imputation, Interpolation, Änderung eingefrorener Regeln, neue Validation, Holdout, External, Forward, Paper oder Shadow.
- **Akzeptanz:** 60.504 Work-Units terminal; Feature-/Outcome-Case-IDs und Digests konsistent; keine Duplikate/Orphans; PIT-, Contract- und Control-Bezug bestanden; SQLite und append-only Schutz bestanden; deskriptiver Plan eingehalten; terminaler Summary-Stand ohne wiederholte Heavy-Audits.
- **Stop-Bedingungen:** Semantik-Diff > 0; Fingerprint-/Inputänderung; unvollständige/inkonsistente Reuse-Evidenz; systematischer Daten-, Rechte- oder Schreibfehler; erneut readonly; fremder aktiver Writer; Ressourcenrisiko; späteres Gate würde geöffnet.
- **Referenzen:** v7-r2-Config `config/multi_asset_discovery_development_v7_recovery.json`; Recovery-Contract `77cbb53de9a61fb9c68cc3169d2d14da20c6d38b2e669a870c804ec91b783ee5`; Parent-Contract `bedf1c9297f1a5b409e13c78b5fc5f41eb33912ffb79fe711b0d3009d478a9d2`; v6-Code-Basis `e3ecdb6a1242c5922213ab489eb337342de0b17e`.
- **Review-Ergebnis:** 0 robuste neue Hypothesenkandidaten. Volatilität, RSI/Mean-Reversion, Sell-Zone-A-Distanz und Safe-Zone-Geometrie bleiben nur `INTERESTING_BUT_INSUFFICIENT`; Dependency ist für alle Fälle `UNKNOWN`, vertragliches effektives N 0, und 2021 ist zu 99,48 % zensiert.
- **Referenz:** [`MULTI_ASSET_DISCOVERY_V7_R2_DEVELOPMENT_REVIEW_2026-09-14.md`](MULTI_ASSET_DISCOVERY_V7_R2_DEVELOPMENT_REVIEW_2026-09-14.md).
- **Nächster zulässiger Schritt:** keiner innerhalb U1. Der Planungs-Chat entscheidet getrennt; keine v7-r2-abgeleitete Hypothese automatisch öffnen.

### U2 – Dokumentstruktur bereinigen

- **Ziel und Priorität:** Aktuelle Planung, Current Truth, Historie, Forschungsregeln und Produktziel klar trennen.
- **Status:** `DONE` im vorab erlaubten Dokumentationspaket.
- **Umfang:** alte aktive Anweisungen aus der kanonischen Roadmap entfernt; vollständige Fassungen unverändert archiviert; genau ein aktueller Current-Truth-Block erstellt; dauerhafte Regeln in `RESEARCH_POLICY.md`; Historieneintrag in `CHANGELOG.md`.
- **Akzeptanz:** keine historische Aussage steuert mehr die aktuelle Queue; Quell-IDs und alte Texte bleiben im Archiv und in Git erhalten; Start-Gate ist eindeutig.
- **Stop-Bedingungen:** keine historischen Forschungsartefakte, Contracts, Reports oder Datenbankresultate umschreiben.
- **Referenzen:** diese Datei, [`PROJECT_STATUS.md`](PROJECT_STATUS.md), [`CHANGELOG.md`](CHANGELOG.md), [`RESEARCH_POLICY.md`](RESEARCH_POLICY.md), `docs/archive/`.
- **Nächster zulässiger Schritt:** keiner; nur bei neuer belegter Dokumentationslücke erneut öffnen.

### U3 – Daten- und Betriebsabdeckung

- **Ziel und Priorität:** Reproduzierbaren Bericht über tatsächliche Datenverfügbarkeit und Nutzung erstellen. Hohe Priorität nach beziehungsweise parallel zu einem sicher isolierten U1.
- **Voraussetzungen:** ausdrückliches Startsignal; vorhandene Quellen und Stores nur lesend; U1-Inputs und Ressourcenbudget unberührt.
- **Erlaubter Umfang nach Start:** vorhandenen Status-/Reportmechanismus nutzen; Preis/Technik, Markt/Sektor, Fundamentals, Makro/Zinsen/FX, Unternehmensereignisse, Politik/Regulierung, Identity/Dependencies und Kosten-Proxies getrennt ausweisen.
- **Akzeptanz:** je Familie Schnittstelle, aktive Quelle, historisch/Forward, Zeitraum, letzte Beobachtung, Anzahl, gültig/fehlend/nicht anwendbar, PIT, Revisionen, Source Health, Research-Nutzung und Grenzen. Klare Trennung: `TECHNIK VORHANDEN ≠ DATEN VORHANDEN ≠ EVIDENZ VORHANDEN ≠ AKTIVIERT`.
- **Stop-Bedingungen:** neues Dashboard-Framework nötig; schreibender Zugriff auf U1-Stores; heutige Identity müsste historisch rückdatiert werden; Daten müssten erfunden werden.
- **Referenzen:** vorhandene Runtime-Exports und Stores; keine neue Datenquelle allein für diesen Bericht.
- **Nächster zulässiger Schritt:** nach Startsignal festen Reportpfad und reine Leseabfragen bestimmen.

### U4 – FX-Observer und Prognosebetrieb

- **Ziel und Priorität:** FX-PIT-Observer, allgemeinen Prognoserunner und eingefrorenen Legacy-Swing-Forward getrennt betrieblich prüfen.
- **Voraussetzungen:** ausdrückliches Startsignal; keine Veränderung von Gewichten, Eignungsregeln, Universum oder Modelllogik; bestehende Datensammler weiterlaufen lassen.
- **Erlaubter Umfang nach Start:** Registrierung, Nutzerkontext, echte Läufe, Soll/Ist-Coverage, Staleness, Rate Limits, offene Auswertungen, Retry/Lock/Resume, DB-Wachstum und Backups prüfen; nur Betriebsfehler reparieren.
- **Akzeptanz:** tatsächliche Laufbelege statt bloßer Zeitpläne; fehlende Aufnahmen bleiben echte Lücken; Nachholungen tragen tatsächliche Zeit; FX und Prognosen nicht wegen des Legacy-Swing-Status pauschal deaktiviert.
- **Stop-Bedingungen:** neue Modell-/Scorelogik nötig; Quellen- oder Scheduler-Berechtigung fehlt; Eingriff in U1-Ressourcen; historische Rückdatierung erforderlich.
- **Referenzen:** `InvestmentAssistant-FX-PIT-Observer`, `InvestmentAssistantDailyForecasts`, Legacy-Aufgabenstatus in `PROJECT_STATUS.md`.
- **Nächster zulässiger Schritt:** nach Startsignal letzten echten FX- und Prognoselauf erneut prüfen.

### U5 – Signalunabhängiger Daten-Observer

- **Ziel und Priorität:** Unternehmens-, Makro-, politische und regulatorische Beobachtungen ohne aktive Tradingstrategie sammeln. Mittlere Priorität nach U3/U4.
- **Voraussetzungen:** ausdrückliches Startsignal; vorhandene Event-, COT-, FX-, Filing- und Quellenverträge wiederverwenden; feste outcome-unabhängige Pilotstichprobe; U1 abgeschlossen oder technisch vollständig isoliert.
- **Erlaubter Umfang nach Start:** kleinen Quellenvertrag speichern; erlaubte öffentliche Quellen und vorhandene Adapter entkoppeln; Rohbeobachtung/Referenz, Source-Zeit, Veröffentlichung, erstes lokales Sehen, Wirksamkeit, Revision, belegte Zuordnung, Qualität und Missingness append-only speichern.
- **Akzeptanz:** Dedupe, Revision, Resume, Source Health und Zeitsemantik getestet; keine Signale, Scores, Tradepläne, Paper-/Shadow-Orders oder Brokerpfade; tatsächliche Coverage als `PARTIAL`, falls unvollständig.
- **Stop-Bedingungen:** neuer Anbieteraccount, Kosten, fehlende Kontaktkennung, unfreigegebener Scraper, unklare Datenschutzfolge, U1-Ressourcenverdrängung oder nicht trennbarer Strategiepfad.
- **Referenzen:** bestehende Event-, COT-, SEC- und FX-Module; vor Pilot neu zu speichernder Quellenvertrag.
- **Nächster zulässiger Schritt:** nach Startsignal Adapterinventar und festen kleinen Pilotscope festlegen.

### U6 – Forschungsnachweise und Reviews

- **Ziel und Priorität:** Bereits betrachtete Forschungsdaten, Failed-Seller-Vertrag und spätere Methodikfragen dokumentarisch ordnen. Keine neue Statistik.
- **Voraussetzungen:** ausdrückliches Startsignal; bekannte Artefakte und Manifeste reichen aus; keine ungesehenen Holdout-Ergebnisse öffnen.
- **Erlaubter Umfang nach Start:** auditierbares Nutzungsregister; belegter Failed-Seller-Abgleich; Dependency-Reviewfragen; späteren Gesamtsystemtest als Abnahmevertrag vormerken.
- **Akzeptanz:** Run/Version, Asset/Zeitraum/Split, bisherige Nutzung, tatsächlich betrachtete Ergebnisse, Quelle und Unsicherheit erfasst; Abweichungen nur als belegtes Erratum; keine rückwirkende Präregistrierung.
- **Stop-Bedingungen:** unbekannte Daten müssten geöffnet, Performance neu gerechnet oder eingefrorene Policy geändert werden.
- **Referenzen:** bekannte Runmanifeste, KB und bestehende Reports.
- **Nächster zulässiger Schritt:** nach Startsignal bestehende Register- und Reportpfade inventarisieren.

### U7 – Gesamtprüfung und Abschluss

- **Ziel und Priorität:** Alle freigegebenen Pakete prüfen, echte Restaufgaben reduzieren und einen kopierbaren Abschluss erstellen. Letzte Queue-Aufgabe.
- **Voraussetzungen:** U0 bis U6 sind `DONE`, `PARTIAL` oder mit konkretem Grund `BLOCKED`; kein aktiver unbeaufsichtigter Work-Schreibprozess.
- **Erlaubter Umfang nach Start:** Gesamtprüfung, Current Truth, Roadmap, Entscheidungen, Git/Push/CI und Resume-Endzustand konsolidieren.
- **Akzeptanz:** Abschluss enthält Git, jede U-ID, Development-Run, Dokumentbereinigung, Datensammlung, Forschungsnachweise, Automation, Sicherheit sowie konkrete Pfade/Befehle für Status, Fortsetzen, Pausieren und Stoppen.
- **Stop-Bedingungen:** offene schreibende Prozesse; unklarer Git-Stand; beschädigte Evidenz; fehlende Abnahme eines nicht sicher überspringbaren Pakets.
- **Referenzen:** Ergebnisse U0–U6 und [`VACATION_WORKQUEUE_RESUME.md`](VACATION_WORKQUEUE_RESUME.md).
- **Nächster zulässiger Schritt:** erst nach Abschluss der vorgelagerten Pakete.

## Automatische Aufgabenauswahl nach dem jeweiligen Startsignal

1. `PROJECT_STATUS.md` und `VACATION_WORKQUEUE_RESUME.md` lesen.
2. Prozesse, Locks und bestehende Run-IDs prüfen.
3. Bereits laufende oder erledigte Arbeit nicht doppelt starten.
4. Höchste freigegebene, nicht blockierte Aufgabe mit erfüllten Voraussetzungen wählen.
5. Eine sichere Teilphase bearbeiten und prüfen.
6. Status, Referenzen und Resume-Punkt aktualisieren.
7. Nächste zulässige Aufgabe wählen.

Ein Blocker darf unabhängige freigegebene Arbeit nicht stoppen. Er darf aber nie durch eine gesperrte Forschungsstufe oder eine neue Hypothese umgangen werden. Neu entdeckte Ideen kommen als `DEFERRED / NOT_VACATION_AUTHORIZED` in den Backlog und werden nicht automatisch ausgeführt.

Die Urlaubs-Workqueue und der nachfolgende Trading-Research-Backlog besitzen getrennte Freigaben. Das bereits erteilte v7-Recovery-Signal oder ein Startsignal für U0 bis U7 startet keinen der folgenden Research-Aufträge. Der Trading-Research-Backlog darf erst durch einen späteren ausdrücklichen `/goal`-Auftrag beziehungsweise „Roadmap abarbeiten“ ausgeführt werden.

## Trading-Research-Backlog nach dem aktuellen Development-Pfad

- Backlog-ID: `trading-research-backlog-2026-09-13-v1`
- Planungsstatus: `PLANNED_NOT_STARTED`
- Aktuelle Ausführungsfreigabe: `false`
- Gemeinsame Voraussetzung: `ERFÜLLT_2026-09-14` – der aktuelle Multi-Asset-Discovery-/Development-Pfad ist vollständig terminal, geprüft und mit einem dokumentierten Review abgeschlossen. Dies ist keine Ausführungsfreigabe für den Backlog.
- Aktivierung: ausschließlich durch einen späteren ausdrücklichen `/goal`-Auftrag beziehungsweise „Roadmap abarbeiten“.
- Evidenzgrenze: `READY`, `DRAFT`, `PLANNED`, `TESTABLE_NOW`, `CODE_EXTENSION_REQUIRED` und `ALREADY_AVAILABLE` beschreiben nur Arbeits- oder Technikstatus. Sie sind weder positive Evidenz noch Validation-, Produktions- oder Handelsfreigaben.
- Forschungsgrenze: Jede Ausführung folgt [`RESEARCH_POLICY.md`](RESEARCH_POLICY.md). Keine Stufe darf automatisch Validation, Holdout, External, Forward, Paper, Shadow, Broker oder Produktion öffnen.

Verbindliche Auswahlreihenfolge für einen später gestarteten Roadmap-Lauf:

1. Aktuellen Multi-Asset-Discovery-/Development-Pfad vollständig abschließen und reviewen.
2. `TR-01` Wasser-Infrastruktur-Research bearbeiten.
3. `TR-02` Gold-/Silber-Research bearbeiten, sofern die dann aktuelle Sicherheits- und Prioritätsprüfung keinen höherwertigen Blocker oder Auftrag ergibt.
4. `TR-03` Overnight-/Intraday-Renditetrennung nur bei dokumentiert begründeter Aktivierung bearbeiten.
5. Weitere Hypothesen ausschließlich nach der bestehenden Research Policy auswählen.

### TR-01 – Wasser-Infrastruktur-Aktien

- **Ausführungsart:** `DIRECT_AFTER_PREREQUISITES`; bei einem späteren Roadmap-Start selbstständig auswählbar, aber nicht jetzt.
- **Aktueller Stand:** Capability `TESTABLE_NOW`; Work Request `READY`; Experiment `DRAFT`; kein Resultat.
- **Voraussetzungen:** gemeinsames Development-/Review-Gate erfüllt; Work Request und Experimentvertrag vor Ausführung unverändert zugeordnet und erneut geprüft; keine höherrangige Sicherheits- oder Datenqualitätslücke.
- **Scope:** `XYL`, `BMI`, `PNR`, `SPY` und `PHO`; Einzelwerte getrennt auswerten; einen gleichgewichteten Wasser-Korb getrennt auswerten; keine nachträgliche Auswahl nur erfolgreicher Aktien.
- **Akzeptanz:** reproduzierbarer Development-Bericht für alle vorab festgelegten Einzelwerte und den getrennten Korb; Kosten, Datenqualität, fehlende Werte und Mehrfachtests sichtbar; Resultat sauber in der Knowledge Base verknüpft.
- **Stop-Bedingungen:** Scope müsste nach Ergebniskenntnis geändert werden; PIT-, Kosten- oder Listing-Semantik ist nicht belastbar; eine gesperrte Forschungsstufe wäre nötig; fremde beziehungsweise laufende Evidenz würde verändert.
- **Referenzen:** Work Request `3721453e-158f-42cb-8d76-a28f054b7d97`; Hypothese `78bcdab6-e542-4844-bc95-fbdf1b3b1f9b`; Experiment `b2e990f1-16f9-4bad-a5ad-09184c4225c2`.
- **Nächster zulässiger Schritt:** nach späterem Roadmap-Start und erfüllten Voraussetzungen den bestehenden Experimentvertrag und die unveränderte Fallauswahl prüfen; erst danach Development ausführen.

### TR-02 – Gold-/Silber-Nachzügler

- **Ausführungsart:** `DIRECT_AFTER_PREREQUISITES`; bei einem späteren Roadmap-Start nach `TR-01` selbstständig auswählbar, aber nicht jetzt.
- **Aktueller Stand:** Capability `CODE_EXTENSION_REQUIRED`; Work Request `READY`; Experiment `DRAFT`; kein Resultat.
- **Voraussetzungen:** `TR-01` terminal dokumentiert; dann aktuelle Prioritäts- und Sicherheitsprüfung ohne höherwertigen Auftrag; isolierter Gold-/Silber-Research-Runner; vorab fester Experiment- und Ausführungsvertrag.
- **Scope:** `GC=F`, `SI=F`, Gold-/Silber-relative Divergenz, Futures-/Roll-Semantik, Session Alignment, Point-in-Time-Korrektheit, Kosten/Slippage sowie Selection-/Multiple-Testing-Schutz.
- **Akzeptanz:** isolierter und reproduzierbarer Development-Bericht mit sichtbarer Roll-, Session-, PIT- und Kostensemantik; Resultat sauber in der Knowledge Base verknüpft; keine automatische Übertragung auf Aktien-/ETF-SwingTrading.
- **Stop-Bedingungen:** kein sauber isolierbarer Runner; unklare Futures-/Roll- oder Session-Semantik; fehlende realistische Kosten; Auswahl oder Parameter müssten nach Ergebniskenntnis verändert werden; eine gesperrte Forschungsstufe wäre nötig.
- **Referenzen:** Work Request `4fdfb983-ddbc-4178-bd36-7aa34267df0b`; Hypothese `f8e6a64b-1cf9-431f-9477-4a7a17ab5478`; Experiment `255532e0-3b54-412a-a29e-866bfe4bda82`.
- **Nächster zulässiger Schritt:** nach späterem Roadmap-Start und erfüllten Voraussetzungen zuerst den isolierten Runner und seinen festen Daten-/Kostenvertrag erstellen und prüfen; erst danach Development ausführen.

### TR-03 – Overnight-/Intraday-Renditetrennung

- **Ausführungsart und Status:** `CONDITIONAL_RESEARCH_RESERVE`; nicht unmittelbar ausführbar und nicht automatisch auszuwählen.
- **Aktueller Stand:** Capability `ALREADY_AVAILABLE`; Experiment `PLANNED`; kein offener Work Request; kein Resultat.
- **Aktivierungsvoraussetzungen:** eine konkrete Informationslücke ist dokumentiert; der bestehende Experimentvertrag reicht aus oder wird vor Kenntnis neuer Ergebnisse sauber ergänzt; keine wichtigere Research-Stufe wird blockiert; ein eigener Work Request und eine ausdrückliche Aktivierungsentscheidung liegen vor.
- **Erlaubter Umfang nach Aktivierung:** Overnight- und Intraday-Renditeanteile isoliert auf zusätzlichen Informationswert gegenüber der einfacheren Baseline prüfen; nur wenige fachlich begründete, vorab festgelegte Vergleiche.
- **Nicht erlaubt:** Grid Search, automatische Feature-Kombinationen, zusätzlicher Pflichtfilter für bestehende Setups, automatische Regel-/Gewichtsänderung oder Mehrfachzählung korrelierter Merkmale.
- **Akzeptanz:** isolierter, reproduzierbarer Zusatznutzen oder transparente Null-/Negativ-Evidenz gegenüber der Baseline; Out-of-Sample- und Walk-Forward-Anforderungen bleiben vollständig unter der Research Policy.
- **Stop-Bedingungen:** keine konkrete Messlücke; Vertrag unvollständig; nur enge oder nachträglich gewählte Parameter wirken; wichtigere Research-Arbeit würde verzögert; eine gesperrte Forschungsstufe wäre nötig.
- **Nächster zulässiger Schritt:** Reserve unverändert lassen, bis alle Aktivierungsvoraussetzungen nachweislich erfüllt sind.

### Historische Punkte, die nicht erneut geöffnet werden

- Buyer Confirmation v1 bleibt `REJECTED_AT_VALIDATION`.
- Fibonacci bleibt abgeschlossen beziehungsweise inconclusive.
- Failed Seller Attempts bleibt abgeschlossen als `INCONCLUSIVE_RETAINED`; kein automatischer Folgeversuch.
- FX Carry PIT bleibt abgeschlossen beziehungsweise inconclusive; der getrennte PIT-Collector darf nach seinem bestehenden Vertrag weiterlaufen.

Diese vier Punkte sind historische Research-Evidenz und keine offenen Aufgaben des Trading-Research-Backlogs.

## Dauerhafte Grenzen der Queue

Auch nach dem Startsignal bleiben verboten:

- Validation, Holdout, External oder neue Strategie-Forward-Tests,
- Paper-/Shadow-Trades, Brokeranbindung und automatische Orders,
- neue Hypothesen-, Parameter-, Filter- oder Kombinationssuche,
- produktive Score-, Ranking-, Handels- oder Risikoregeländerungen,
- Retuning oder Reaktivierung verworfener beziehungsweise eingefrorener Strategien,
- kostenpflichtige Anbieter, Credits, neue Konten oder externe Infrastruktur,
- Übertragung privater Thesen, Portfolios, Zugangsdaten oder Historien an neue Dienste,
- Löschen oder Überschreiben historischer Forschung und Nutzerdaten,
- Force Push, `git reset --hard`, `git clean` oder Verlust fremder Änderungen,
- Short, ML, vollständiger Opportunity-Feed, Live-Bot oder größeres Redesign.

## Verbindlicher Betriebsgrundsatz für Historical Research

- Historical Research und Development dürfen unabhängig von der lokalen Uhrzeit starten, fortsetzen und resumieren. Die früheren allgemeinen Fenster 09:00–11:30, 15:45–18:45 und 20:00–23:59 einschließlich ihrer 90-Minuten-Vorläufe sind ausschließlich Legacy-Historie.
- Die zentrale aktive Startentscheidung ist process-/lock-basiert. Blockierend bleiben ein real gehaltener oder nicht sicher prüfbarer inkompatibler Produktions-/Writer-Lock, der globale exklusive Research-Lock, ein bereits aktiver gleicher Run, eine gespeicherte SQLite-Sicherheitspause, ein fehlgeschlagenes Integritätsgate oder eine belegte kritische Ressourcenlage.
- Geplante zukünftige Forecast-/Collector-Zeitpunkte sind keine Konflikte. Ein als inkompatibel konfigurierter Produktionsprozess blockiert nur während seiner tatsächlichen Lockdauer; nach Lockfreigabe darf der nächste Trigger wieder arbeiten.
- Der getrennte FX-PIT-Observer ist wegen eigener DB, eigenem Lock und begrenztem Providerumfang kein pauschaler Multi-Asset-Research-Blocker. Unbekannte tatsächliche Lock-/Writer-Zustände bleiben fail-closed.
- Legacy Forward v1 bleibt eingefroren. Die uhrzeitfreie Research-Regel ist keine Freigabe für neue Forward-, Validation-, Holdout-, External-, Paper-, Shadow-, Broker- oder Orderstufen.
- Für Development v6 bleibt die bestehende SQLite-Review-Pause unabhängig von dieser Bereinigung maßgeblich. Erst eine getrennt geprüfte technische Recovery darf den vorhandenen Run fortsetzen; alte Uhrzeitfenster sind dabei kein Gate.

## Nicht aktive beziehungsweise spätere Arbeit

### Bewahrter Research-/Shadow-Vertrag ohne Urlaubsfreigabe

##### G2.7 – getrennter Point-in-Time Event-/News-/Makro-/Geopolitik-Edge-Layer

Der vorhandene versionierte Eventvertrag, seine append-only Sidecars, getrennten späteren Labels und Coverage-Regeln bleiben als historische Research-/Shadow-Infrastruktur erhalten. Sie besitzen keine Signal-, Score-, Risiko-, Trade- oder Brokerwirkung. Neue Eventforschung oder Collector-Arbeit ist nur innerhalb U5 nach ausdrücklichem Startsignal und dessen Quellenvertrag zulässig.

Der technische Broad-Vollpass wartet ausdrücklich **nicht** auf eine vollständige historische Eventdatenbank. Unvollständige Event-Coverage darf keine vorhandene Forschungsstufe umdeuten. Dieser Abschnitt bewahrt einen methodischen Vertrag und ist kein Auftrag, den alten Broad- oder Legacy-Forward-Pfad wieder zu starten.

### Terminal oder abgeschlossen

- Buyer Confirmation v1: `REJECTED_AT_VALIDATION`; kein Rescue, Retuning oder Holdout dieser Version.
- Legacy Forward v1: eingefroren; keine neuen Strategie-Signale, Paper-Trades oder Shadow-Orders.
- Fibonacci: vorhandene Duplikat-/Resultatverknüpfung abgeschlossen; kein neuer Leveltest.
- Buyer-Provenienz und Reproduktion: abgeschlossen.
- Development-v5-Integritätsforensik: abgeschlossen; v5 bleibt `COMPLETED_WITH_FAILURES`.

### Weitere offene Forschung ohne Ausführungsfreigabe

- Technische Indikatorreserve nur bei konkreter dokumentierter Messlücke.
- Neue Short-, ML-, Confluence-, Exit- oder Strategievarianten sind `DEFERRED`.

Wasser, Gold/Silber und Overnight/Intraday sind mit ihrer späteren Reihenfolge und ihren getrennten Freigabebedingungen im Abschnitt `Trading-Research-Backlog nach dem aktuellen Development-Pfad` kanonisch beschrieben. Sie gehören nicht zur laufenden v7-Recovery und nicht zur Urlaubs-Workqueue.

### Spätere Produktarbeit

- intelligente Einstiegs-Watchlist,
- vollständige quellenbasierte Long-Term-Analyse,
- Investment-Opportunities-Feed,
- app-weites Designsystem,
- gemeinsame Systemvalidierung von Discovery, Entry, Risk, Position Management und Exit,
- spätere autonome Paper-, Shadow-, Echtgeld- und Live-Bot-Stufen nur über die Gates aus `RESEARCH_POLICY.md`.

Diese Punkte gehören nicht zur Urlaubs-Queue.

## Begriffe

| Begriff | Bedeutung |
|---|---|
| Quellenbewertung A/B/C | Qualität einer Quelle, keine Strategie- oder Integrationsfreigabe |
| Development-Empfehlung | Ergebnis innerhalb der Entwicklungsdaten; kein ungesehenes Ergebnis |
| Validation-/Holdout-Ergebnis | Entscheidung einer getrennten, zuvor gesperrten Stufe |
| Kampagnenrunde A/B/C | fest getrennte historische Forschungsrunden; nicht mit Quellenklassen verwechseln |
| Integrationsfreigabe | eigene spätere Entscheidung nach allen erforderlichen Evidenzgates |
| Messzeitpunkt | Zeitpunkt, zu dem ein Merkmal berechnet wird |
| Beobachtungsende | Ende eines festgelegten Outcome-Fensters |
| tatsächlicher Exit | realer oder vertraglich simulierter Positionsausstieg; nicht automatisch das Beobachtungsende |

Die frühere Grenze von 20/50 Fällen bleibt nur Diagnose- und Hinweisgrenze. Sie ist keine Wahrscheinlichkeits-, Strategie- oder Produktionsfreigabe.

## Dokumentzuordnung und Historie

| Alter Bereich | Neuer kanonischer Ort | Status |
|---|---|---|
| alte Roadmap-Prioritäten und Arbeitsmodi | `docs/archive/ROADMAP_LEGACY_THROUGH_2026-09-06.md` | HISTORICAL |
| frühere Current-Truth- und Änderungsblöcke | `docs/archive/PROJECT_STATUS_LEGACY_THROUGH_2026-09-06.md` | HISTORICAL |
| heutiger belegter Ist-Stand | `PROJECT_STATUS.md` | CURRENT |
| dauerhafte Forschungs- und Gate-Regeln | `RESEARCH_POLICY.md` | CURRENT |
| abgeschlossene Dokumentänderungen | `CHANGELOG.md` | CURRENT |
| aktive Freigaben und künftige Arbeit | `ROADMAP.md` | CURRENT |
| langfristiges SwingTrader-Zielbild | `SWINGTRADER_PRODUCT_ARCHITECTURE.md` | CURRENT, keine Funktionsbehauptung |
| kompakter Fortsetzungsstand | `VACATION_WORKQUEUE_RESUME.md` | CURRENT |

Die Archive sind keine Ausführungsaufträge. IDs, Links und historische Aussagen bleiben dort und in Git nachvollziehbar erhalten.
