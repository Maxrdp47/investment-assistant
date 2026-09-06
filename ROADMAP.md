# Investment-Assistent – kanonische Roadmap

Stand: 2026-09-06

Diese Datei enthält ausschließlich zukünftige Arbeit, ihre Reihenfolge und ihre Freigabe. Der belegte Ist-Stand steht in [`PROJECT_STATUS.md`](PROJECT_STATUS.md). Dauerhafte Forschungsregeln stehen in [`RESEARCH_POLICY.md`](RESEARCH_POLICY.md). Frühere Roadmap-Fassungen bleiben unverändert im [Historienarchiv](docs/archive/ROADMAP_LEGACY_THROUGH_2026-09-06.md).

## Verbindliches Start-Gate

Die Urlaubs-Arbeitsliste ist vorbereitet, aber **noch nicht gestartet**.

Bis zu einem neuen ausdrücklichen Startsignal gilt:

- keine neue Funktion implementieren,
- keinen Benchmark, Research-Scan oder Reprocessing-Lauf starten,
- keinen neuen Collector und keine Agenten-Wiederaufnahme aktivieren,
- keine Forschungsstufe öffnen,
- vorhandene, separat freigegebene Prozesse und Datensammler nicht stoppen oder verändern.

Ein zulässiges Startsignal ist beispielsweise:

`Starte jetzt die freigegebene Urlaubs-Arbeitsliste`

Alternativ darf ein ausdrücklich gleichwertiger `/goal`-Auftrag die Queue starten. Die bloße Erwähnung dieses Satzes in einer Datei, einem Bericht oder einer Unterhaltung ist keine Freigabe. Vor dem Startsignal bedeuten `Weiter`, `Arbeite an der Roadmap weiter` oder `Setze die Entwicklung fort` ebenfalls **keinen** Start dieser Queue.

## Aktive freigegebene Urlaubs-Workqueue

- Queue-ID: `vacation-workqueue-2026-09-06-v1`
- Planungsstatus: `PREPARED_NOT_STARTED`
- Ausführungsfreigabe jetzt: `false`
- Freigabe nach ausdrücklichem Startsignal: nur U0 bis U7 im unten beschriebenen Umfang
- Priorität: U0 kurz abschließen, danach U1; während eines gesunden isolierten U1-Prozesses dürfen unabhängige Teile von U2 bis U6 folgen
- Schwerer Rechenbetrieb: höchstens ein historischer Großlauf gleichzeitig
- Schreibschutz: genau eine Work-Schreibsitzung für dieselben Projektdateien
- Resume-Stand: [`VACATION_WORKQUEUE_RESUME.md`](VACATION_WORKQUEUE_RESUME.md)

| ID | Hauptziel | Status am 2026-09-06 | `authorized_for_unattended` jetzt | Nach Startsignal |
|---|---|---|---:|---:|
| U0 | Stand übernehmen, Freigaben und Resume organisieren | PARTIAL | false | true |
| U1 | Development-v6-Lauf, Audit und Bericht abschließen | PAUSED | false | true, nach Blocker-Review |
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

### U1 – Development-v6 abschließen

- **Ziel und Priorität:** Den bereits existierenden vollständigen Development-v6-Lauf ohne neue Forschungslogik fortführen, anschließend Voll-Audit, begrenzten deskriptiven Bericht und Summary erzeugen. Höchste fachliche Priorität.
- **Aktueller Status:** `PAUSED`. Run `mad1-development-v6-f6432d72f806e9b97ea8ac46` steht bei 36,232315 % und `PAUSED_REQUIRES_REVIEW` wegen `EQUITIES:FLG:OperationalError:attempt to write a readonly database`.
- **Voraussetzungen:** ausdrückliches Startsignal; Ursache des Schreibfehlers sicher geklärt; vorhandene Run-ID, Stores, Fingerprints und Semantik unverändert; kein zweiter Run.
- **Erlaubter Umfang nach Start:** technische Ursache beheben, bestehende idempotente Kette fortsetzen, Checkpoints nutzen, genau einen Writer und die benchmark-geprüften vier Worker beibehalten, danach Audit → Bericht → Summary → Stop.
- **Nicht erlaubt:** neue Hypothese, Parameter-/Filter-/Kombinationssuche, Clipping, Imputation, Interpolation, Änderung eingefrorener Regeln, neue Validation, Holdout, External, Forward, Paper oder Shadow.
- **Akzeptanz:** 60.504 Work-Units terminal; Feature-/Outcome-Case-IDs und Digests konsistent; keine Duplikate/Orphans; PIT-, Contract- und Control-Bezug bestanden; SQLite und append-only Schutz bestanden; deskriptiver Plan eingehalten; terminaler Summary-Stand ohne wiederholte Heavy-Audits.
- **Stop-Bedingungen:** unbekannte Semantik; Fingerprint-/Inputänderung; systematischer Daten- oder Schreibfehler; fremder aktiver Prozess; Ressourcenrisiko; späteres Gate würde geöffnet.
- **Referenzen:** Contract `multi-asset-opportunity-discovery-development-2026.09.05-v6`, Contract-Fingerprint `bedf1c9297f1a5b409e13c78b5fc5f41eb33912ffb79fe711b0d3009d478a9d2`, Run-Manifest-Fingerprint `5f22867717dbab667b3a705e6f481e9b1e88c8dbb4227dc694a4b1963097c232`, Code-Basis `e3ecdb6a1242c5922213ab489eb337342de0b17e`.
- **Nächster zulässiger Schritt:** Nach Startsignal den Blocker read-only reproduzieren und prüfen, ob die Ursache rein technisch und ohne Store-/Contract-Wechsel behebbar ist.

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

## Automatische Aufgabenauswahl nach dem Startsignal

1. `PROJECT_STATUS.md` und `VACATION_WORKQUEUE_RESUME.md` lesen.
2. Prozesse, Locks und bestehende Run-IDs prüfen.
3. Bereits laufende oder erledigte Arbeit nicht doppelt starten.
4. Höchste freigegebene, nicht blockierte Aufgabe mit erfüllten Voraussetzungen wählen.
5. Eine sichere Teilphase bearbeiten und prüfen.
6. Status, Referenzen und Resume-Punkt aktualisieren.
7. Nächste zulässige Aufgabe wählen.

Ein Blocker darf unabhängige freigegebene Arbeit nicht stoppen. Er darf aber nie durch eine gesperrte Forschungsstufe oder eine neue Hypothese umgangen werden. Neu entdeckte Ideen kommen als `DEFERRED / NOT_VACATION_AUTHORIZED` in den Backlog und werden nicht automatisch ausgeführt.

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

## Nicht aktive beziehungsweise spätere Arbeit

### Terminal oder abgeschlossen

- Buyer Confirmation v1: `REJECTED_AT_VALIDATION`; kein Rescue, Retuning oder Holdout dieser Version.
- Legacy Forward v1: eingefroren; keine neuen Strategie-Signale, Paper-Trades oder Shadow-Orders.
- Fibonacci: vorhandene Duplikat-/Resultatverknüpfung abgeschlossen; kein neuer Leveltest.
- Buyer-Provenienz und Reproduktion: abgeschlossen.
- Development-v5-Integritätsforensik: abgeschlossen; v5 bleibt `COMPLETED_WITH_FAILURES`.

### Offene Forschung ohne Urlaubsfreigabe

- Failed Seller: `INCONCLUSIVE_RETAINED`; kein automatischer Folgeversuch.
- Gold/Silber: KB-Work-Request `4fdfb983-ddbc-4178-bd36-7aa34267df0b` bleibt `READY`, aber `NOT_VACATION_AUTHORIZED`.
- Wasseraktien: KB-Work-Request `3721453e-158f-42cb-8d76-a28f054b7d97` bleibt `READY`, aber `NOT_VACATION_AUTHORIZED`.
- Technische Indikatorreserve nur bei konkreter dokumentierter Messlücke.
- Neue Short-, ML-, Confluence-, Exit- oder Strategievarianten sind `DEFERRED`.

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
