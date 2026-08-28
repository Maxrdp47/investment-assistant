# Investment Assistant – Projektstatus

Stand: 2026-08-28
Konsolidierungs-Start: Branch `codex/swing-forward-diagnostics-status`, HEAD `31ff30eeefd46c7f42993802864687eda0c6e47b`. Der bereits geprüfte Buyer-Validation-Stand bis `e51880b28a681b4bddb7a3c4c770f0468e2bbc09` wurde per Fast-Forward integriert.

Diese Datei fasst den technisch nachweisbaren Projektstand zusammen. Sie ist als kompakte Schnittstelle zwischen Planungs-Chat und Work-Chat gedacht und soll nach relevanten Änderungen fortgeführt werden. Private Portfolio-, Such-, Trade-, Entscheidungs-, Prognose- und Testdaten gehören nicht in dieses Dokument.

## Current Truth – 2026-08-28

- Die vor Ergebnissichtung eingefrorene Version `buyer-confirmation-objective-pullback-v1` wurde ground-up über die vollständige ungesehene Validation ausgeführt. Der unveränderliche Freeze-Fingerprint ist `6c41572e2619e9123c8219d2d51fa61f542c5666fe8304519797caa6a06b9293`; Dataset-, Code- und Feature-Fingerprint blieben `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`, `77ab6ed29d8d08e32fabb8c2aee01c0a94953ded4b69092227f074273b12d946` und `c09d43e3c297b1685796db568b63c23c5878b2f246e69508c409fdbaa77f01dd`.
- Der ursprüngliche Ausführungscode wurde eindeutig auf Commit `a2bc13b` gefunden. Zwischen diesem Ausführungsstand und dem dokumentierten Abschluss `3b73eb3` änderten sich nur `PROJECT_STATUS.md` und `ROADMAP.md`; Result Integrity und Software Provenance sind damit `VERIFIED`.
- Validation ist vollständig: 2.520/2.520 Assets, 181.473 rohe Pullback-Fälle. Die Buyer-Gruppe umfasst 30.352 rohe beziehungsweise 30.294 ausgewertete Fälle und 23.595 effektive Abhängigkeitscluster; die Kontrolle 151.121 rohe beziehungsweise 146.659 ausgewertete Fälle und 51.954 effektive Cluster. Das Validitäts-/Power-Gate bestand.
- Ohne Matching lag die Buyer-Gruppe bei +0,00938 R Expectancy und Profitfaktor 1,01703. In der vorab festgelegten gematchten Treatment-Auswertung lag sie dagegen bei -0,02152 R und Profitfaktor 0,96211.
- Der Challenger verfehlte die verbindlichen Robustheitsgates: Unter konservativer zusätzlicher Ausführung lag die Buyer-Gruppe bei -0,04392 R und Profitfaktor 0,92384; außerdem waren nur 2 von 4 ausgewerteten Jahren positiv statt der geforderten mindestens 60 %. Fehlgeschlagen sind `conservative_execution_treatment_pf_above_one`, `conservative_execution_treatment_positive` und `positive_in_at_least_60pct_of_years`. Der Kandidatenreihenfolge-Drawdown von 2.515,74 R ist ausdrücklich ein Research-Serienmaß und kein Portfolio-Drawdown.
- Deterministische Entscheidung: `VALIDATION_FAIL`, terminal `REJECTED_AT_VALIDATION`. Review-Fingerprint: `64c4b78dbda9fb0d5cc9e828df3338b9cebc24e05bdb22f7578f8073f6833d12`. `next_stage_allowed=false`; Holdout blieb ungeöffnet bei 0 Assets/0 Fällen, External und True Forward wurden nicht gestartet.
- Die isolierte Ground-up-Reproduktion über 2.520/2.520 Assets ist abgeschlossen. Original und Scratch-Reproduktion besitzen identische Counts, Gruppen, Candidate-/Completion-Identitäten, Fingerprints, Metriken, Gates und Entscheidung. Case-Digest `59c5ef691d134b3d9ee2a8dfbcf43cfa9111436a18346f3226369462b765a36b` und Completion-Digest `34c1aa4a306e14e2b4a86b145ee5847a84918ff9edd9538397299399e33d34b6` stimmen exakt überein. Das Decision-JSON ist byte-identisch; nur die physische SQLite-Datei ist wegen Seiten-/Einfügereihenfolge nicht byte-identisch.
- Die negative Evidenz ist im separaten append-only Store `runtime/buyer_confirmation_validation.sqlite3` und im Entscheidungsbericht `runtime/research_exports/buyer_confirmation_validation_decision_2026-08-26-v1.json` erhalten. Die Research-KB führt den bestehenden Work Request `e8fc4673-485c-48d8-a948-c44d5ecb2d49` und das Experiment `fa61d54f-6649-4e8a-a521-15eb02e1bd90` als `COMPLETED`, das Resultat `a5060b1a-0323-40ac-94f2-24f6be6f686b` als negativ sowie die append-only Validation-Bewertung `b0167cd2-e0ae-40c7-8d12-d337b083fea2`. Die breitere Quellhypothese bleibt absichtlich `RAW/B`; Reporting und Planung leiten für den engeren Challenger dennoch terminal `REJECTED_AT_VALIDATION` ab. Synchronisierung ist idempotent und erzeugt keine Duplikate oder positiven Integration Candidates.
- Vollständiger technischer Nachweis und Dateinamens-Erratum: `research_reports/BUYER_CONFIRMATION_VALIDATION_PROVENANCE_ERRATA_2026-08-28.md`. Der alte Dateiname mit `2026-08-26` bleibt unverändert; der tatsächliche gespeicherte Review-Zeitpunkt ist 2026-08-27 03:51:53 Europe/Berlin.
- Abschlussprüfungen des Provenienzstands: 36 gezielte Provenienz-/KB-/Lifecycle-/Validation-Tests und die vollständige Suite mit 772/772 Tests bestanden; Python-Kompilierung, Repository-Sicherheitscheck, Offline-Smoke, separater lokaler Streamlit-Start und `git diff --check` waren erfolgreich.
- Produktionswirkung: keine. Keine Retunes, Zusatzfilter, Baseline-/Strategieänderung, Brokerfunktion oder automatische Aktivierung. Broad-v1, Frozen Dataset, Development-Artefakt und sämtliche historische Forensik-Artefakte blieben unverändert.
- Historische Kampagne: 248/248 Jobs abgeschlossen, A 80/80, B 80/80, C 80/80. Abschluss um 01:47 Uhr; keine Regel- oder Produktionsänderung.
- Frozen-Dataset-Fingerprint: `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`, unverändert.
- Broad-v1 ist vollständig: 2.520/2.520 Assets, je 1.263.423 Kandidaten, Labels und Counterfactuals; Development 631.811, Validation 304.389 und Holdout 327.223. Validation und Holdout wurden im Methodik-Audit nicht geöffnet.
- Broad-Feature-Version: `swing-broad-pit-features-frozen-first-pass-2026.08.22-v3`; Feature-Vertragsfingerprint `c09d43e3c297b1685796db568b63c23c5878b2f246e69508c409fdbaa77f01dd`, Broad-Code-Fingerprint `77ab6ed29d8d08e32fabb8c2aee01c0a94953ded4b69092227f074273b12d946` und Manifest-Fingerprint `7531b0b8411436b3bbaf31d1db4bab94e35ecb0360f094cdbb96baf0d6297bf5` blieben unverändert.
- Der vollständige read-only Broad-v1-Audit ist als `swing-broad-v1-method-audit-2026.08.25-v3` abgeschlossen. Finaler manueller Review-Fingerprint: `1b1dc38b133ebefb6f4397200fdbc5158322ed3588946d0dea3751b023d61f96`. Broad-DB und Research-Quality-Ledger hatten vor und nach dem Audit identische Größe und Änderungszeit.
- Historischer Broad-v1-Auditstand vor dem späteren Buyer-Challenger: Buyer Confirmation B, mindestens drei bearishe Pullback-Kerzen B mit `post_hoc_direction_reversal=true`, Fibonacci 61,8–78,6 % B, EMA A, RSI A, BOS A, Opening Levels `NON_DISCRIMINATING/INVALID`, COT `NOT_TESTABLE`. In diesem Audit erreichte keine Hypothese C und es wurde dort keine ungesehene Stufe geöffnet. Der anschließend separat eingefrorene Buyer-Challenger erhielt im Development eine `C_RECOMMENDATION`, scheiterte danach aber terminal in der vollständigen Validation wie oben dokumentiert.
- Belegte Errata: COT durfte bei 0 Coverage nie B sein; Opening Levels hatten wegen des aktuellen Daily Open 631.809 Treatments gegen nur 2 Controls; Pullback-spezifische Buyer-/Kerzen-/Fib-Merkmale und Breakout-spezifisches BOS wurden im alten Report setupübergreifend ausgewertet; `Max Drawdown` war nur `candidate_sequence_drawdown`, kein Portfolio-Drawdown.
- Long-v1 bleibt die unveränderte Baseline mit CRV-Mindestwert 2,0. Kein Short, kein Broker, kein Live-Handel und keine automatische Strategie-/Regeländerung.
- Research-Quality und Research-Policy sind getrennte Berichtsschichten. Sie gruppieren vorhandene Merkmale, zeigen Redundanz und erzwingen sequenzielle Hypothesen; sie verändern keine Broad-Rohfeatures oder bestehende Evidenz.
- Overnight-/Intraday-Research besitzt jetzt ein zentrales fail-closed Overfiltering-Gate. Isolierter Baseline-Mehrwert, materieller Zusatznutzen nach Kosten, OOS, Walk-Forward, Zeit-/Parameterstabilität und Redundanzkontrolle sind Pflicht vor jeder manuellen Kombinationsprüfung. Kein Ergebnis kann automatisch einen Pflichtfilter, Trade, Score oder Produktionseinfluss erzeugen.
- Die detaillierte, append-only eingeordnete Auswertung steht in `research_reports/BROAD_V1_METHOD_AUDIT_2026-08-25.md`; das vollständige lokale JSON liegt unter `runtime/research_exports/swing_broad_v1_method_audit_2026-08-25-v3-reviewed.json`.
- Abnahme des Auditstands: 61/61 gezielte Broad-/Validity-/Quality-/Policy-/Transition-Tests und 772/772 vollständige Regressionstests erfolgreich. Python-Kompilierung, Repository-Sicherheitscheck, Offline-Smoke einschließlich lokalem Streamlit-Start und `git diff --check` sind erfolgreich.
- Historische ältere Fortschrittsangaben weiter unten sind ausdrücklich damalige Momentaufnahmen und nicht der aktuelle Stand.

## SwingTrader-Produktarchitektur

Das verbindliche langfristige Zielbild steht in [`SWINGTRADER_PRODUCT_ARCHITECTURE.md`](SWINGTRADER_PRODUCT_ARCHITECTURE.md). Der SwingTrader ist kein klassischer Daily-Trading-Bot, sondern soll schrittweise zu einem transparenten, regelbasierten Multi-Factor Swing-/Investment-Assistenten werden.

**Research Baseline != Production Strategy.** Next-Open-/Next-Bar-Entries, fixe Stops, fixe R-Ziele und 5/10/20/25-Sitzungs-Horizonte sind wissenschaftliche Baselines oder Counterfactuals. Sie sind nicht automatisch das spätere Produktverhalten und begrenzen insbesondere nicht zwingend die spätere Haltedauer.

Belegter Modulstand:

- **Aktuell vorhanden:** technisches Asset-Universum und Scanner, versionierte Orderpläne für die vorhandenen Setups, unabhängige brokerlose Risk Engine, Forward-/Paper-/Shadow-Speicher sowie technische Begleitung manuell bestätigter Nutzertrades.
- **Teilweise vorhanden oder Research/Shadow:** Point-in-Time- und Datenqualitätsverträge, Event-/News-/Makro-Research ohne Produktionswirkung, technische Entry-Varianten und eine strikt getrennte langfristige Investment-Verkaufsprüfung.
- **Noch geplant und nicht als Gesamtprodukt validiert:** Multi-Factor Opportunity Ranking, integrierte Swing-Thesis-Engine, vollständiger Entry-/Tranchenplaner, fortlaufender Markt-/Sektor-/Unternehmenskontext, dynamische Swing-Exit-Engine und eine durchgängige Auditkette des zusammengesetzten Produkts.

Die fünf KB-gesteuerten READY-Folgeaufträge aus Roadmap G2.12 sind optionale Planungsgegenstände. Sie sind weder automatisch priorisiert noch gestartet und stellen keine beschlossene nächste Strategie dar.

## Legacy Forward v1 – eingefroren am 2026-08-28

- Der bisherige Strategy-Forward `swing-long-pullback-breakout-2026.08.11-v3` über `scripts/run_swing_scans.py` und `swing_background_runner.py` ist `LEGACY_RESEARCH_FROZEN`. Grund ist nicht die Zahl der Signale im letzten Lauf, sondern: Diese alte Version entspricht nicht mehr dem aktuellen Research-/Produktpfad und besitzt keine ausreichende Evidenz für eine weitere aktive Strategieevaluation.
- Die zentrale Produktionskonfiguration `config/swing_background_settings.json` sperrt neue Strategie-Signale, Paper-Zyklen, Shadow-Entwürfe und Brokerorders fail-closed. Auch ein manueller Aufruf beendet sich vor Marktabruf, Strategieevaluation, Log- oder Datenbankschreibzugriff als wirkungsloser Freeze-Status.
- Die Windows-Aufgaben `InvestmentAssistantSwingScan-asia`, `InvestmentAssistantSwingScan-europe`, `InvestmentAssistantSwingWalkForward` und `InvestmentAssistantSwingResearchCampaign` sind deaktiviert. Die tägliche Prognoseaufgabe um 22:30 Uhr bleibt bestehen; ihre Abendkette führt nur noch Prognosen aus und überspringt Amerika/Global sowie Krypto mit dem Status `LEGACY_RESEARCH_FROZEN`.
- Ein reiner Observer bleibt deaktiviert. Der vorhandene Ablauf trennt Markt-/Feature-Erfassung derzeit nicht sicher von Strategiequalifikation, Forward-Speicherung sowie Paper-/Shadow-Erzeugung. Deshalb wurde kein neuer Observer gebaut.
- Historische Forward-, Paper-, Shadow-, Walk-Forward-, Broad- und Buyer-Daten wurden nicht gelöscht oder rückwirkend verändert. Der letzte Asia-Lauf bleibt unverändert: 65 ausgewählte und geladene Assets, 7 durch den Vorfilter, 0 strategiequalifizierte Kandidaten, 0 Shadow-Signale, 0 Trades; `paper_only=true`, `broker_order_allowed=false`.
- Bestehende Paper-/Shadow-Infrastruktur bleibt im Code und ihre Evidenz bleibt lesbar. Sie erhält aus Legacy Forward v1 keine neuen strategiegebundenen Signale, Paper-Trades oder Shadow-Orders. Es existiert weiterhin kein Live-Brokerpfad.
- Technische Abnahme dieses Konsolidierungsstands: 94 gezielte Buyer-/KB-/Forward-/Paper-/Shadow-/Architekturtests und 775/775 vollständige Regressionstests bestanden. Projektquellen wurden erfolgreich kompiliert; Repository-Sicherheitscheck, Offline-Smoke, lokaler Streamlit-Start, Swing-Preflight und Git-Diff-Prüfung sind erfolgreich. Ein realer manueller Asia-Aufruf gab ausschließlich `legacy_strategy_frozen` zurück und veränderte keine Runtime-Daten.
- Artefaktschutz bestätigt: Frozen Dataset `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`, Broad Feature Contract `c09d43e3c297b1685796db568b63c23c5878b2f246e69508c409fdbaa77f01dd`, Broad Code `77ab6ed29d8d08e32fabb8c2aee01c0a94953ded4b69092227f074273b12d946`, Broad Manifest `7531b0b8411436b3bbaf31d1db4bab94e35ecb0360f094cdbb96baf0d6297bf5`, Buyer Freeze `6c41572e2619e9123c8219d2d51fa61f542c5666fe8304519797caa6a06b9293` und Buyer-Resultat `a5060b1a-0323-40ac-94f2-24f6be6f686b` sind unverändert.

Die Generationen sind verbindlich getrennt:

- **LEGACY FORWARD v1:** eingefrorene historische Evidenz, keine neuen Läufe.
- **MULTI-ASSET DISCOVERY v1:** zukünftige Development-Research-Epoch; noch nicht gestartet und noch kein Forward.
- **FUTURE FORWARD v2:** existiert nicht. Er darf erst nach `Development → Fixed Challenger → Validation → Holdout → External Unseen Universe → Forward` entstehen.

`Multi-Asset Opportunity Discovery` ist damit der nächste separat freizugebende große Schritt. Dieser Konsolidierungsauftrag hat weder Scan noch neue Labels, Kandidaten, Hypothesen, Development-Auswertung oder andere Research-Stufe gestartet.

## Future-only Market-Scope-/Research-Planung – 2026-08-23

- Market-Scope-Vertrag `swing-research-market-scope-2026.08.23-v1` ergänzt. Jede neue Hypothese, jedes neue Research-Feature, Experiment und Ergebnis führt mindestens einen der Scopes `EQUITIES`, `ETF`, `FX`, `FUTURES`, `COMMODITIES`, `CROSS_ASSET` oder `GENERAL_METHOD`; Mehrfachzuordnung ist möglich. Hypothesen-, Feature-, Experiment- und Result-Scope bleiben jeweils fingerprintet erhalten.
- `VALIDATED` allein kann keine Assetklasse freigeben. Der technische Scope-Gate verlangt zusätzlich genau den im Ergebnis separat validierten direkten Asset-Scope. `GENERAL_METHOD` und `CROSS_ASSET` können keine Assetklasse direkt aktivieren. Ein Transfer, beispielsweise COT aus FX/Futures nach Equities, erzeugt stets ein neues Experiment ohne geerbte Validierung und benötigt neue Equity-OOS-/Walk-Forward-Evidenz.
- Research-Ergebnisse führen Testuniversum, Zeitraum, Timeframe, Baseline, Sample Size, IS-, OOS- und Walk-Forward-Status sowie validierte und verworfene Scopes. Die Knowledge-Base-Provenienz trennt `source_scope` und `test_scope`; negative Ergebnisse bleiben gleichrangig sichtbar. Alte Ergebnisse ohne gespeicherten Scope bleiben `LEGACY_SCOPE_NOT_RECORDED`, werden nicht rückwirkend umgedeutet und können keine Aktivierung öffnen.
- Die zukünftige A/B/C-Methodik wurde vor ihrem ersten Start auf `swing-campaign-methodology-2026.08.23-v2.1` beziehungsweise `swing-ground-up-abc-2026.08.23-v2.1` erweitert. Jede spätere Kampagne benötigt vorab eingefrorene konkrete Test-Market-Scopes; die outcome-blinden Pools, Effective-N-/Underpowered-Gates und Entry→Stop→Exit-Sperren bleiben erhalten.
- Verkäufer-Pushs/`failed_seller_attempts` und `close_location = (close-low)/(high-low)` sind ausschließlich als neuer Research-Epoch-Plan registriert. Kontinuierliche Push-Tiefe, Recovery und Zeit bis Recovery bleiben primär; begrenzt sind nur exakt zwei Fehlversuche, Close exakt am Hoch sowie Close-Location ≥0,90 beziehungsweise ≥0,80. `high == low` ergibt fehlend, keine erfundene 0 oder 1. Der laufende Broad-Pass, Long-v1 und aktive Signale wurden nicht verändert.
- FX-/Carry-Research ist ausschließlich `DEFERRED_DOCUMENTATION_ONLY`: erwartete Zinsdifferenzen, Erwartungsänderungen, Zentralbank-Surprises, implied Volatility, Carry-to-Risk, Positionierung und bestätigte Interventionen sind spätere Point-in-Time-Hypothesen. Es wurde keine FX-Datenpipeline und keine Richtungsregel implementiert und keine aktuelle Priorität verändert.
- Produktionswirkung: keine. Keine aktive Baseline, kein bestehender Strategiezweig, kein aktuelles Broad-Feature, kein Live-/Forward-Signal, kein Short und keine Brokerfunktion wurde geändert oder aktiviert.

## 1. Projektziel

Der Investment Assistant ist eine lokale, mit Streamlit entwickelte Analyse- und Entscheidungshilfe für Aktien, ETFs und Kryptowährungen. Markt-, Stamm-, Nachrichten- und ausgewählte Research-Daten werden über Yahoo Finance bezogen. Die Anwendung soll Analysen nachvollziehbar aufbereiten, fehlende Daten offen kennzeichnen und sowohl eine professionelle Research-Sicht als auch verständliche Erklärungen für weniger erfahrene Nutzer anbieten.

Die Anwendung ist keine Finanzberatung. Sie besitzt keine Broker-Anbindung, führt keine Orders aus und enthält keine automatische Kauf- oder Verkaufsfunktion. Die endgültige Anlageentscheidung liegt immer beim Nutzer.

Langfristig soll das Projekt wie ein transparentes professionelles Research-Werkzeug arbeiten. Die bestehende Roadmap nennt als Qualitätsmaßstab insbesondere Equity Research, Hedgefonds-Analyse, Portfoliomanagement, Makro-Research und Krypto-Research. Analysequalität, Stabilität, Datenqualität und nachvollziehbare Lern- und Kalibrierungshinweise haben Vorrang vor Komfortfunktionen.

Für den SwingTrader gilt als kanonisches Zielbild ein modularer Multi-Factor Swing-/Investment-Assistent mit Asset Discovery, Thesis, Entry, unabhängiger Risk Engine, Position Monitoring, Dynamic Exit und Audit. Aktueller und geplanter Stand sind in [`SWINGTRADER_PRODUCT_ARCHITECTURE.md`](SWINGTRADER_PRODUCT_ARCHITECTURE.md) getrennt beschrieben.

Die verbindlich geplanten Hauptbereiche sind:

- **Asset-Analyse:** gezielte Einzelanalyse bekannter oder bewusst ausgewählter Aktien, ETFs und Kryptowährungen. Die bestehende Aktienanalyse bildet die künftige Einstiegsanalyse weitgehend ab; eine getrennte quellenbasierte Long-Term-Analyse für drei bis sieben Jahre ist geplant.
- **Investment Opportunities:** eigener mittel- bis langfristiger Ideenbereich mit den getrennten Modi `Aktuell attraktiv` und `Zukunftschancen 3+ Jahre`. Der Navigationsbereich und ein ehrlicher Leerzustand sind vorhanden; Feed, Scores, Watchlist und Übergaben sind noch nicht umgesetzt. Dieser Bereich darf nicht mit Swing-Trades vermischt werden.
- **Swing Trade Finder:** automatische und regionale Marktsuche über 2.520 intern gepflegte liquide Aktien, ETFs und große Kryptowährungen. Alle Assets durchlaufen einen ATR-normalisierten, assettypgerechten Grobfilter; jeder ernsthaft mögliche Kandidat wird ohne feste Top-N-Grenze vollständig auf Long-Rücksetzer oder bestätigte Ausbrüche geprüft. Der Assetklassen-Funnel misst jeden Grob- und Finalfilter für Aktien, ETFs und Krypto getrennt. Es gibt keine Klassenquote; nur absolut freigegebene Setups erscheinen.

## 2. Technischer Überblick

### Programmiersprache und Framework

- Python
- Streamlit als Weboberfläche
- Git und GitHub für Versionsverwaltung und Remote-Sicherung
- GitHub Actions für den vorhandenen Smoke-Workflow

### Wichtige Bibliotheken

Die in `requirements.txt` eingetragenen Laufzeitabhängigkeiten sind:

- `streamlit`: Benutzeroberfläche und Streamlit-AppTest-Schnittstelle
- `yfinance`: Yahoo-Finance-Suche sowie Kurs-, Stamm-, News- und Earnings-Daten
- `pandas`: Zeitreihen, Tabellen und Datenaufbereitung
- `pyarrow`: schneller lokaler Parquet-Cache für wiederaufnehmbare historische Swing-Forschung
- `numpy`: numerische Berechnungen
- `plotly`: interaktive Kurs-, Indikator- und Volumen-Charts

Für lokale JSON-/CSV-Dateien, SQLite, Pfade, Datenmodelle und Hilfsprozesse nutzt die Anwendung zusätzlich Python-Standardbibliotheken wie `json`, `csv`, `sqlite3`, `pathlib`, `dataclasses`, `logging`, `tempfile` und `subprocess`. `requirements-dev.txt` ergänzt `pytest` für reproduzierbare lokale Regressionstests.

### Projektstruktur und wichtige Dateien

| Datei oder Verzeichnis | Aufgabe |
| --- | --- |
| `app.py` | Zentrale Streamlit-Anwendung. Enthält Oberfläche, Datenabruf, Indikatoren, Scoring, Research, Portfolio-Effekt, Scanner, Trading-Setups, Tracking, Backtesting, lokale Lernlogik und die gemeinsame Snapshot-Erzeugung für den Hintergrundlauf. |
| `analysis_models.py` | Gemeinsame Datenklassen für Scores, Marktphase, Risiko/Chance, Asset-Profil, Portfolio, Research-Paket sowie Aktien- und ETF-Snapshots. |
| `asset_search.py` | Von Streamlit unabhängige Asset-Suche mit bekannten Beispielen, Ticker-Erkennung, Yahoo-Treffernormalisierung, Deduplizierung und Tippfehler-Vorschlägen. |
| `json_history_store.py` | Gemeinsame defensive Lese- und atomare Schreiblogik für lokale JSON-Historien; ein gescheiterter Dateiaustausch erhält den bisherigen Stand. |
| `technical_analysis.py` | Von Streamlit unabhängige Berechnung technischer Indikatoren, Unterstützungen/Widerstände, CRV, Marktphase und gemeinsam genutzter numerischer Hilfsfunktionen. |
| `portfolio_analysis.py` | Von Streamlit und Yahoo unabhängiges, ausschließlich lesendes Laden und Bewerten optionaler Portfolio-Daten; enthält Positionsnormalisierung, Marktwert-, Cash-, Klumpen- und Krypto-Risikologik. |
| `currency_utils.py` | Reine deutsche Betragsformatierung, EUR-Umrechnung sowie nicht mutierende Umrechnung von Kursreihen und technischen Chartmarken. |
| `fundamental_analysis.py` | Von Streamlit und Netzwerkzugriffen unabhängige Aktien- und ETF-Snapshots, Datenlückentexte, Kennzahlgrenzen, Übersichten und Fundamentalscores. |
| `data_quality_analysis.py` | Von Streamlit getrennte vorhandene Warnungs-/Datenqualitätslogik für externe Quellen, Ampelstatus, Identität, Kurshistorie, Volumen und Durchschnitte; behandelt auch vollständig fehlende Kursspalten ohne Absturz. |
| `score_composition.py` | Reine vorhandene Anzeige und Berechnung konfigurierter Score-Gewichte sowie neutraler optionaler Mittelwerte; bewahrt Standardbeiträge, Rundung, Reihenfolge, Erklärungen und nicht mutierende Eingaben. |
| `valuation_analysis.py` | Von Streamlit und Netzwerk unabhängiger vorhandener Bewertungs-Research-Pfad für Aktien, ETFs und Krypto; verarbeitet verfügbare Multiplikatoren mit unveränderten Grenzen und kennzeichnet fehlende historische, Peer-, Index- oder On-Chain-Daten offen. |
| `future_potential_analysis.py` | Reine vorhandene Research-Logik für Zukunftspotenzial und eingepreiste Erwartungen aus Qualität, Wachstum, Margen, Bewertung, Momentum und News; lässt fehlende Produkt-, Adoptions-, Flow- und Spezial-Sentimentdaten offen. |
| `scenario_analysis.py` | Reine Szenario-Wahrscheinlichkeiten, zentrale numerische Kursbereiche, sichtbare Bull-/Basis-/Bear-Zeilen und Expected-Value-Logik aus Kaufsignal, Asset-Qualität, CRV, Marktphase, Trend, Marken und Volatilität; bewahrt 100-Prozent-Summe, Mindest-Basisfall und konservative Fallbacks. |
| `recommendation_synthesis.py` | Von Streamlit getrennte bestehende Entscheidungssynthese für Langfristigkeit, Preis, Timing, Datenqualität, Portfolio-Grenzen und konkreten Mehrpfad-Plan; Schwellen, Kategorien, Tranchierung, Widerlegung und sichtbare Texte bleiben unverändert. |
| `entry_plan.py` | Reine Einstiegsplan-Domain für Kauf-/Bestätigungs-/Widerlegungszonen, technische Aktion, Confidence-Label, Anlagehorizont und Gültigkeit; nutzt nur vorhandene Marken und ignoriert vergangene Earnings-Termine als Deadline. |
| `price_attractiveness.py` | Reine Preiseinordnung aus Bewertung, Expected Value, Zukunftsscore, historischem Hochabstand und ausschließlich aktuellen verfügbaren Fundamentalhinweisen; behandelt den Rückgang nie allein als Kaufsignal und erfindet keinen historischen Stichtagsvergleich. |
| `long_term_analysis.py` | Noch nicht in der UI freigeschalteter, versionierter Quellen-, Evidenz- und Bereitschaftsvertrag für die geplante Long-Term-Analyse; prüft Pflichtabdeckung, Provenienz, Primär-/unabhängige Quellen, quellentypisches Höchstalter, Zukunftszeitpunkte und die Trennung vom technischen Einstiegsplan, ohne bereits eine Empfehlung zu erzeugen. |
| `long_term_research_cache.py` | Noch nicht produktiv befüllte, atomare und versionierte lokale Ablage öffentlicher Long-Term-Quellen und Evidenz; schützt vor unsicheren Tickerpfaden, ungültigen Referenzen, Zukunftsschemata sowie bereits bei Sammlung oder später veralteten Daten. |
| `long_term_scoring.py` | Noch nicht in der UI freigeschaltete, deterministische Long-Term-Bewertung nach erfolgreichem Quellengate; hält sieben gewichtete Faktoren getrennt, berechnet nachvollziehbare Bear-/Basis-/Bull-Szenarien für drei bis sieben Jahre und schließt technisches Einstiegstiming aus den langfristigen Scores aus. |
| `sec_filing_sources.py` | Erster noch nicht aktivierter offizieller Long-Term-Quellenadapter: ordnet exakte US-Ticker einer SEC-CIK zu, entdeckt aktuelle 10-K/20-F/40-F/10-Q-Dokumente, baut sichere EDGAR-URLs und verlangt einen nur zur Laufzeit übergebenen Fair-Access-User-Agent; ein serialisierter Client taktet Abrufe, nutzt die Tickerdatei pro Prozess einmal und begrenzt Retry/Backoff, erzeugt aber keine unverbundenen Evidenzaussagen oder Scores. |
| `sec_json_cache.py` | Noch nicht aktivierter atomarer persistenter Cache ausschließlich für die freigegebene öffentliche SEC-Tickerdatei und einzelne Submissions-JSONs; verwendet getrennte 24-/6-Stunden-Gültigkeiten, feste pfadsichere Dateinamen und speichert niemals die Fair-Access-Kontaktkennung. |
| `sec_financial_facts.py` | Noch nicht aktivierte strukturierte SEC-XBRL-Auswertung für sechs klar definierte aktuelle US-GAAP-Jahreswerte und belegte Vorjahresvergleiche; erzeugt Finanzqualitäts-Evidenz nur bei exakt passenden offiziellen Filing-Accessions und niemals aus Quartals-, Zukunfts-, nicht endlichen oder unverbundenen Werten. |
| `sec_long_term_collection.py` | Nicht schreibende SEC-Orchestrierung für Tickerauflösung, Filingquellen, Company Facts, exakt verknüpfte aktuelle Finanzwerte/Vorjahresvergleiche und Long-Term-Bereitschaft; erhält Teilquellen bei Fehlern, öffnet aber ohne alle übrigen Primär-/unabhängigen Belege niemals das Gesamtgate. |
| `trading_assistant.py` | Von Streamlit unabhängige, zentral konfigurierte Long-Swing-Logik für Qualitätsfilter, Pullback- und Breakout-Setups, versionierte fingerprintete Order-/Stop-Verträge, CRV/Expected Value, Positionsgröße, manuellen Trade-Lebenszyklus und Paper-Statistiken. |
| `swing_scanner.py` | Mehrstufige Swing-Marktsuche mit ATR-normalisiertem Vorfilter, vollständiger Tiefenprüfung aller bestandenen Kandidaten, rechnerischer Grob-/Finalfilterzerlegung je Assetklasse, neutralem ETF-/Aktien-Bias-Audit ohne Quote sowie zentraler konservativer Risikopolitik. |
| `swing_universe.py` | Strikter Lader und Validator des versionierten Scanneruniversums; protokolliert ungültige oder doppelte Zeilen und sperrt bekannte Hebel-/Inverse-Produkte. |
| `swing_forward_store.py` | Getrennte append-only SQLite-Speicherung für echte Swing-Scans, unveränderbare Signalsnapshots und nur angehängte Ereignisse mit Fingerabdruckprüfung und Update-/Delete-Sperren. |
| `swing_forward_evaluation.py` | Konservative spätere Paper-Auswertung vollständiger Kursbalken nach Signal mit Kosten, Gap-, Maximalpreis-, Stop-/Ziel- und Reihenfolgeregeln sowie maximalem günstigen/ungünstigen Kursausschlag ab Einstieg. |
| `historical_fx.py` | Point-in-Time-sichere historische Währungsbelege für Swing-Einstieg und -Ausstieg; bevorzugt Intraday-Kurse bis zum Ereignis und verwendet als Fallback ausschließlich einen bereits bekannten früheren Tagesabschluss. |
| `swing_forward_runner.py` | Wiederholbare Auswertung offener Swing-Signale mit 5-Minuten-, Stunden- und Tagesfallback, retry-fähigem Datenfehlerstatus und separat nachholbarer append-only EUR-Bewertung. |
| `swing_forward_statistics.py` | Ehrliches Swing-Archiv mit Ein-/Ausstiegszeit, Haltedauer, Zwischenbewegungen und Kennzahlen in R, Trefferquote, Profitfaktor und Drawdown; offene, verpasste, unklare und nicht auswertbare Fälle werden getrennt. Stellt nicht mutierende Zeit-/Text-/Ergebnis-/Versions-/Quellen-/Nutzertrade-Filter bereit. |
| `swing_walk_forward.py` | Getrennter historischer Swing-Forschungsbetrieb mit einmalig kausal berechneten Indikatoren, purgierten chronologischen Development-/Validation-/Holdout-Fenstern, nicht überlappenden Ergebnisfällen, vollständigen Daten-/Fallfingerabdrücken, append-only Identitätskonfliktrevisionen, issuer-/listingabhängigen Evidenzclustern, getrenntem beobachtendem RSI-/EMA-Sidecar, Research-Gates und versioniertem Strategie-/Paretovergleich ohne Produktionsaktivierung. |
| `swing_research_dataset.py` | Finalisiert pro Research-Epoch einen unveränderlichen lokalen Parquet-/OHLCV-Datensatz über alle Vertragsfenster und Assets, prüft vollständige Manifest-/Dateifingerabdrücke und sperrt Providerzugriffe sowie stille Aktualisierungen nach dem Freeze. |
| `swing_research_identity.py` | Allgemeine Forschungsidentität für Emittent, Listing, Anteilsklasse, Depositary Receipt und wirtschaftlich identische Mehrfachlistings; bevorzugt explizite IDs/ISIN und leitet Legacy-Fälle konservativ aus normalisierten Universumsmetadaten ab, ohne alte Fallpayloads zu verändern. |
| `swing_walk_forward_campaign.py` | Validierte Forschungswarteschlange mit festen/wochenweisen Verträgen, diversifizierten Shards, 90-Minuten-Restzeitprüfung vor drei Produktionsfenstern, aktiver Produktions-Lock-Prüfung, atomarem Resume-Status und expliziter Produktionssperre. |
| `swing_strategy_freeze.py` | Reproduzierbare append-only Strategie-Freezes mit vollständigem Fachvertrag sowie Code-, Konfigurations-, Komponenten- und Datenfingerabdrücken; Research-Freezes können weder automatisch aktiviert noch aufgrund bisheriger Performance freigegeben werden. |
| `swing_risk_engine.py` | Gemeinsame unabhängige Risk Engine für Scanneranalyse, autonomen Paper-Bot und Shadow-Live. Sie erzwingt denselben versionierten Positions-/Orderplan sowie die ausschließlich brokerlosen Modi `analysis_only`, `paper_only` und `shadow_only`. |
| `swing_paper_bot.py` | Getrennte append-only Simulation des vollständigen kausalen Handelszyklus mit idempotenten Läufen/Ereignissen, persistentem Wiederanlauf, virtuellen Fills, Positionen, Teilverkäufen und Exits; `paper_only` ist technisch erzwungen. |
| `swing_shadow_live.py` | Getrennte append-only Shadow-Orderentwürfe und Execution-Beobachtungs-Sidecars ohne Übertragung. Tatsächliche Marktdaten, theoretischer Systementwurf, spätere Shadow-Auswertung und simulierte Kosten bleiben physisch/logisch getrennt. Listing, Quelle und Quellzeitpunkt sind für reale Quotes Pflicht; fehlende Bid-/Ask-/Spread-/Fill-Daten bleiben ausdrücklich unavailable. |
| `trade_republic_reference.py` | Append-only lokale Referenz für listing-spezifische TR-Handelbarkeit, manuelle dauerhafte Statusmarkierungen, exakt zugeordneten höchstens 15 Minuten alten TR-Preis, zeitgleichen Analyse-Vergleichskurs und einen vom unveränderten Analyseplan getrennten EUR-Ausführungsplan. ISIN-Abweichungen, unbekannte Listings und Yahoo als TR-Preis werden hart abgelehnt; keine Broker-Verbindung und keine Order. |
| `swing_background_runner.py` | Bedienungsfreier regionaler Swing-Betrieb mit exakter Bereichsabdeckung, separater Sperre, rotierendem Log und Schutz gegen vollständigen Provider-Ausfall. |
| `swing_user_store.py` | Strikt getrennte append-only Speicherung persönlicher Nutzertrades und ihrer Stop-, Teilverkaufs- und Abschlussereignisse einschließlich bestätigter Planabweichungen und regelbasierter aktiver Zustände. |
| `swing_trade_monitor.py` | Leakage-sichere laufende Begleitdaten aus abgeschlossenen Tageskerzen: 20-Tage-Struktur, Trend, Gap und relatives Verkaufsvolumen; nicht vorhandene Nachrichten-/Ereignis-/Branchendaten bleiben sichtbar unbekannt. |
| `forecast_store.py` | SQLite-Schema und Datenzugriff für Hintergrundläufe, Prognosen, explizite Analysearten, Prognosezeiträume, Auswertungen, getrennte Trefferquoten, Filterung und Pagination. |
| `forecast_runner.py` | Fortsetzbare, fehlertolerante Orchestrierung des täglichen Prognoselaufs und der fälligen Auswertungen mit früher Startdiagnose und Fortschrittsprotokoll je Asset-Versuch. |
| `forecast_horizon_schedule.py` | Versionierter append-only Horizontkalender: 1W wöchentlich, 1M zweiwöchentlich, 3M monatlich, 6M quartalsweise und 12M halbjährlich; lange Horizonte verlangen ein nachvollziehbares Evidenzgate. |
| `forecast_lock.py` | Plattformübergreifende exklusive Betriebssystem-Sperre für den täglichen Runner; verhindert parallele Prozesse und wird bei Prozessende automatisch freigegeben. |
| `forecast_backup.py` | Sichere SQLite-Integritätsprüfung, zeitgestempelte Online-Sicherung und Wiederherstellung ausschließlich in eine neue Datei ohne Überschreiben oder Datenlöschung. |
| `forecast_probabilities.py` | Versionierte, ausdrücklich unkalibrierte Rohwahrscheinlichkeit für positive Rendite aus gespeicherter Bull-/Base-/Bear-Verteilung und numerischen Szenariozielen. |
| `forecast_learning.py` | Rein lesendes Lern-Datensatz-Gate: schließt Legacy-, offene, unbrauchbare und ungültige Fälle aus, fingerprintet den berechtigten Bestand und erzeugt zeitliche Walk-Forward-Fenster mit Purging. |
| `forecast_model_registry.py` | Append-only Register ausschließlich für spätere Shadow-Challenger mit Dataset-/Walk-Forward-/Code-/Artefakt-Fingerabdrücken sowie getrennten Prüf-, Review-, Canary- und Rollback-Ereignissen; es besitzt bewusst keine automatische Produktionsaktivierung. |
| `forecast_calibration.py` | Versioniertes, reproduzierbar fingerprintetes Kalibrierungsprofil aus echten Prognoseauswertungen mit Mindestdatenregeln, ausschließlich manuellen Prüfhinweisen und atomarer Speicherung ohne automatische Score-Änderung. |
| `forecast_monitoring.py` | Rein lesende rollierende Drift-, Qualitäts- und Betriebsüberwachung. Vergleicht je Analyseart/Horizont jüngste mit vorherigen Zeitfenstern, besitzt feste Mindestfallzahlen und Handelskalender-Puffer und kann weder nachtrainieren noch Produktionsregeln ändern. |
| `forecast_recovery.py` | Strikt getrennte SQLite-Grundlage für historische OHLCV-Datenrettung mit explizitem Point-in-Time-Cutoff, Herkunft, Abdeckung, Fehlerstatus, Datenfingerabdruck und technisch erzwungenem Ausschluss aus Forward-Trefferquoten. |
| `config/forecast_universe.csv` | Versioniertes, kuratiertes und erweiterbares Prognoseuniversum mit 325 eindeutigen Assets sowie Ticker, Asset-Typ, Name, Region und Kategorie. |
| `config/swing_universe.csv` | Versioniertes Scanneruniversum mit 2.520 aktiven Assets und Name, Ticker, Asset-Typ, Region, Kategorie, Aktivstatus, Liquiditätsklasse und Quellengruppe; ServiceNow ist enthalten. |
| `config/swing_universe_sources.json` | Erzeugungsmetadaten und Quellengruppen des Scanneruniversums. |
| `config/swing_walk_forward_settings.json` | Versionierter wöchentlicher Zeit- und Forschungsvertrag für Startdatum, feste Zeitfenster, Batchgröße, Fallabstand, Cacheprofil und harte Sperre automatischer Regel-/Orderänderungen. |
| `config/forecast_settings.json` | Einfache Konfiguration für Laufzeit, Pfade, Batches, Pausen, Wiederholungen, Auswertungslimit und Logikversion. |
| `README.md` | Bedienung, Start, Deployment, Funktionsbeschreibung, Score-Trennung, Datenschutz und Datenformate. |
| `ROADMAP.md` | Projektziel, Prioritäten, Akzeptanzkriterien, offene und umgesetzte Arbeitspakete sowie ausführlicher Änderungsverlauf. |
| `SWINGTRADER_PRODUCT_ARCHITECTURE.md` | Kanonisches langfristiges Zielbild des Multi-Factor Swing-/Investment-Assistenten; trennt vorhandene Module, Research/Shadow und geplante Produktbausteine sowie Research-Baselines von Produktionsstrategien. |
| `cot_positioning.py` | Strikt beobachtender COT-Shadow-Layer mit offiziellem CFTC-Abruf, Point-in-Time-Sperre, originalen Teilnehmerklassen, 52-Wochen-/Extrem-/Umkehrmerkmalen, Marktzuordnung und automatischen append-only Forward-Signal-Sidecars. Ein späterer Report darf nie einem früheren Signal zugeordnet werden; fehlender Kontext bleibt sichtbar. |
| `swing_edge_diagnostics.py` | Rein lesende Forensik aller abgeschlossenen echten Forward-Paper-Trades einschließlich Gewinnern: garantierter Detailvertrag für Einstieg/Stop/Ausstieg, R, MFE/MAE, MFE-Schwellen, Zeit bis MFE/Exit, Gap/Slippage, ATR-/RSI-/EMA-/Käufer-/BOS-Kontext, Segmente und konkrete A–G-Begründung. Gespeicherte oder aus dem unveränderten Frozen-Datensatz ableitbare 5-/20-Sitzungs-Fenster und alternative Stops bleiben strikt getrennte Counterfactuals. Fehlende Werte werden als nicht verfügbar ausgewiesen; Intrabar-Reihenfolgen werden nicht erfunden. |
| `swing_event_research.py` | Getrennter Point-in-Time Event-/News-/Makro-/Geopolitik-Research-Layer: versionierte Events und Revisionen, Quellenhierarchie, hierarchische Assetrelevanz, append-only Signal-Sidecars, physisch getrennte spätere Marktreaktionslabels, transparente Coverage, Übertragungsmatrix und Development-zuerst-Hypothesen-Ledger. Alle Ausgaben sind Research/Shadow ohne Einfluss auf Long-v1, Scores, Stops, Größen, Signale, Short oder Broker. |
| `overnight_intraday_research.py` | Kausale, produktionsneutrale Overnight-/Intraday-Zerlegung mit getrennten Zukunftslabels und A/B/C-Evidenz. Das zentrale Overfiltering-Gate sperrt Pflichtfilter und automatische Confluence, verlangt isolierten materiellen Zusatznutzen gegenüber der Baseline sowie OOS-, Walk-Forward-, Zeit-, Plateau- und Redundanznachweis und erlaubt höchstens eine manuelle Research-Prüfung. |
| `swing_ml_dataset_contract.py` | Strikter Point-in-Time-Datenvertrag für spätere Shadow-ML-Forschung; trennt Features und Labels, sperrt Zukunftsquellen und Ziel-Leakage, bewahrt Missingness und fingerprintet Zeilen sowie Dataset-Manifeste ohne Modell- oder Handelswirkung. |
| `swing_broad_research.py` | Getrennter outcome-unabhängiger Research-Pfad über den eingefrorenen OHLCV-Bestand: breite Long-Pullback-/Breakout-Kandidaten, gemeinsame kausale technische/Struktur-/Opening-/Saisonalitäts-/COT-Merkmale, vorbereitende bearishe Short-Readiness-Features, strikt spätere richtungsneutrale Labels, konservative Long-Stop-/Exit-Kontrafakten, append-only SQLite, Resume und Fingerprints. Short-Signale und Short-Auswertung bleiben gesperrt. Nur ein manuell bestätigtes Long-C darf den sequenziellen Validation-/Holdout-/External-/True-Forward-Pfad beginnen. |
| `swing_research_quality.py` | Produktionsneutraler Research-Qualitätsvertrag mit append-only semantisch dedupliziertem Hypothesen-/Ereignis-Ledger, Versuchszähler, Placebo-Suite, Parameterplateaus, Feature-Ablation, konservativen Abhängigkeitsclustern, Zeit-/Regimestabilität, Entry-Effizienz A–D, Execution-Stress, Komplexität, Survivorship-Audit und Falsch-positiv-Bericht. Er kann weder automatisch C wählen noch Tuning, Validation/Holdout oder Produktion aktivieren. |
| `swing_research_policy.py` | Methodische Berichtsschicht für deterministische Feature-Familien, semantische Redundanz, einfache Komplexitätsdarstellung, sequenzielles Setup/Entry→Stop→Exit→OOS-Ledger, reine 20-Fälle-Diagnostik, unveränderte CRV-Baseline, Fib-Kill-Regel, sekundäre Kontextfeatures und strikt getrennte Evidenzarten. Sie verändert keine Broad-Rohfeatures. |
| `swing_broad_research_transition.py` | Fail-closed Übergang von der unveränderten 248-Job-Kampagne zum breiten Research: verlangt exakt 248/248, denselben finalisierten Frozen-Datensatz, gültige Walk-Forward-Datenbank/Fingerprints und einen einmaligen append-only Übergangsnachweis. |
| `swing_external_validation.py` | Append-only Vertrag für ein vor Ergebnissichtung eingefrorenes, wirklich ungesehenes externes Assetuniversum. Ursprüngliche Ticker, Emittenten und wirtschaftlich identische Instrumente werden ausgeschlossen; ein Ergebnis bleibt bis zum manuell bestandenen Holdout derselben Challenger-Version technisch gesperrt und kann keine Produktion aktivieren. |
| `config/cot_market_mapping.json` | Versionierte explizite Zuordnung von CFTC-Terminmärkten zu breiten Assetgruppen sowie konservative Routen für Swing-Assets; unbekannte und mehrdeutige Fälle werden nicht geraten. |
| `scripts/collect_cot_shadow.py` | Manueller, wiederholbarer und paginierter Sammler für offizielle TFF- und disaggregierte CFTC-Daten; schreibt ausschließlich in den getrennten Shadow-Speicher. |
| `scripts/collect_swing_forward_sidecars.py` | Wiederaufnehmbarer Sammler für kausale COT-Forward-Sidecars und brokerlose Shadow-Execution-Beobachtungen. Die Forward-Datenbank wird ausschließlich read-only geöffnet; ein offizieller CFTC-Abruf ist explizit, echte Quotes benötigen einen belastbaren Adapter, andernfalls wird nur Missingness gespeichert. |
| `requirements.txt` | Laufzeitabhängigkeiten der Python-Anwendung. |
| `requirements-dev.txt` | Laufzeitabhängigkeiten plus `pytest` für Entwicklung und Regressionstests. |
| `start_investment_assistent.bat` | Lokales Windows-Startskript. |
| `.streamlit/config.toml` | Streamlit-Konfiguration für Headless-Betrieb und deaktivierte Nutzungsstatistik. |
| `portfolio.json` | Versionierbare Portfolio-Struktur mit erlaubten Minimalfeldern; darf keine Zugangsdaten oder Identifikationsdaten enthalten. |
| `portfolio.example.json` | Anonymisiertes Beispielschema für den Portfolio-Modus. |
| `search_history.example.json` | Anonymisiertes Beispielschema für den lokalen Suchverlauf. |
| `scripts/smoke_test.py` | Kompiliert `app.py`, prüft den Headless-Start, kann Live-Analysepfade testen und meldet die Qualität lokaler Lernhistorien. |
| `scripts/repo_safety_check.py` | Prüft auf versehentlich getrackte Laufzeit- oder Secret-Dateien sowie auf das erlaubte Minimalformat der Portfolio-Dateien. |
| `scripts/run_forecasts.py` | Kommandozeilen-Einstieg für den täglichen Prognose- und Auswertungslauf ohne Streamlit-Oberfläche sowie für marktfreie Vorprüfung, Wartung und Kalibrierungsprofil. |
| `scripts/run_forecasts.cmd` | Windows-Wrapper mit Projekt-Arbeitsordner und Python aus der lokalen `.venv`; protokolliert Prozessstart, -ende und Rückgabecode getrennt und reicht optionale Diagnose-/Wartungsargumente weiter. |
| `scripts/recover_forecast_market_data.py` | Batchfähige CLI zur konservativen Rettung historischer Tages- und 5-Minuten-OHLCV-Daten bis zu einem expliziten vergangenen Cutoff; erzeugt keine nachträgliche Prognose. |
| `scripts/manage_forecast_backups.py` | Kommandozeilenwerkzeug zum Prüfen, Sichern und Erzeugen einer getrennten Wiederherstellungskopie der privaten Prognosedatenbank. |
| `scripts/install_forecast_task.ps1` | Idempotente benutzerbezogene Registrierung der täglichen Windows-Aufgabe; unterstützt einen sicheren `-WhatIf`-Prüfmodus. |
| `scripts/collect_long_term_sources.py` | Noch nicht geplante SEC-Teilquellen-CLI mit offline/nicht schreibender Vorprüfung; sperrt Live-Abrufe ohne Laufzeit-User-Agent, akzeptiert nur privaten Runtime-Cache und gibt die Kontaktkennung niemals aus. |
| `scripts/build_swing_universe.py` | Reproduzierbarer Wartungshelfer für das Scanneruniversum aus dem breiten Projektbestand, S&P-Indizes und regulären Aktien des offiziellen Nasdaq Global Select Market; Testtitel, ETFs, Warrants, Units, Rights, Preferreds, Notes und Bonds werden aus dieser Zusatzquelle ausgeschlossen. |
| `scripts/run_swing_walk_forward.py` | Batchfähige CLI für das vollständige Swing-Universum mit zentralem kontrolliertem Prozess-Pool, deterministischer Ergebnisreihenfolge, ausschließlich seriellen SQLite-Schreibvorgängen im Hauptprozess, eingefrorenem Epoch-Datensatz, Resume-Verhalten und sichtbaren Workerfehlern. |
| `scripts/run_swing_walk_forward_campaign.py` | Finalisiert vor dem ersten Epoch-Job den gemeinsamen Datensatz, weist dessen vollständigen Fingerabdruck jedem Shard zu, führt pro Aufruf höchstens einen offenen Job unter demselben globalen Lock aus und setzt Fehlerjobs später fort. |
| `scripts/run_swing_broad_research.py` | Prozess-Pool-/Resume-Runner für den getrennten breiten Forschungsbestand. Er verwendet ausschließlich den finalisierten Frozen-Datensatz, schreibt SQLite seriell und verweigert den Start, solange die bestehende 248-Job-Kampagne offen, ein Produktionslauf aktiv oder ein Schutzfenster erreicht ist. |
| `swing_free_pit_reference.py` | Getrennter kostenloser Point-in-Time-Referenzspeicher für filinggenaue SEC-SIC-Klassifikationen ab 2009. Import, Fingerprints, As-of-Abfrage und SQLite sind kausal, append-only und ohne Wirkung auf den eingefrorenen Broad-Pass oder Produktion. |
| `scripts/import_sec_pit_classifications.py` | Manueller Importer für lokale oder ausdrücklich angeforderte offizielle SEC-FSDS-Quartals-ZIPs. Live-Download benötigt eine Laufzeit-Fair-Access-Kontaktkennung, ist größenbegrenzt und resume-fähig. |
| `scripts/run_swing_edge_diagnostics.py` | Rein lesender JSON-Bericht über alle abgeschlossenen echten Forward-Paper-Trades; öffnet die Forward-Datenbank im Read-only-Modus und ergänzt ausschließlich kausale Merkmale aus dem Frozen-Datensatz. `--markdown` erzeugt denselben verbindlichen kompakten Statusblock für künftige PLDatei-/Work-Stände. |
| `scripts/run_swing_event_research.py` | Rein lesender Event-Audit und Forward-Event-Diagnose; ein optionaler kontrollierter Nachzug übernimmt nur bereits im unveränderbaren Signalsnapshot belegte Termine. Aktuelle News können ausschließlich mit tatsächlichem Abrufzeitpunkt gesammelt und niemals auf frühere Signale zurückdatiert werden. |
| `scripts/run_swing_broad_challenger.py` | Manueller, in kleinen Blöcken wiederaufnehmbarer Ground-up-Rescan einer fest eingefrorenen C-Challenger-Version. Development wird nicht erneut zur Regelwahl gelesen; Holdout bleibt bis zur manuellen Validation-Prüfung gesperrt. |
| `scripts/freeze_swing_strategies.py` | Erzeugt unveränderbare JSON-/SQLite-Freezes für die Long-v1-Baseline und die acht getrennten technischen Research-Challenger; identische Wiederholung ist idempotent, fachliche Änderung erzeugt eine neue Strategieversion. |
| `scripts/benchmark_swing_walk_forward_parallel.py` | Datenbankfreier reproduzierbarer Vergleich von Thread- und Prozessmodus auf real gecachten Kampagnenassets mit stabilem Gesamtfingerabdruck aller Fälle. |
| `scripts/run_swing_walk_forward_locked.py` | Gemeinsamer Betriebsschutz für den wöchentlichen Basislauf gegen parallele Kampagnenjobs. |
| `scripts/run_swing_walk_forward.cmd` | Windows-Wrapper des wöchentlichen historischen Volluniversums-Laufs mit lokalem Log und Projekt-Python. |
| `scripts/install_swing_walk_forward_task.ps1` | Idempotente Registrierung der wöchentlichen, aufweckfähigen Windows-Aufgabe am Samstag um 11:00 Uhr. |
| `scripts/install_swing_walk_forward_campaign_task.ps1` | Registriert einen durchgängigen täglichen Windows-Trigger ab 00:00 Uhr mit internem 5-Minuten-Wiederholungsmuster, `IgnoreNew`, Aufwecken, Nachholen und ohne hartes Laufzeitende für die rotierende Forschung. |
| `tests/conftest.py` | Gemeinsame Pytest-Konfiguration für den Projektimport. |
| `tests/test_stability.py` | 56 Stabilitäts- und Regressionstests für Historien, Tracking, Scanner, Research, Lernlogik, Suche und Streamlit-Navigation. |
| `tests/test_forecast_system.py` | 26 isolierte Tests für Universum einschließlich Leerprüfung, marktfreie Laufzeit-Vorprüfung, SQLite-Leerzustand, Schema-Versionierung und Migration einschließlich Analyseart, nicht löschende Wartung, gespeicherte Betriebsmetriken, protokollierte Wrapper-/Start-/Asset-Diagnose, veraltete/unterbrochene Läufe, Wiederaufnahme, versionssichere Tages-Deduplizierung, Modelltrennung, Fehlerisolierung, fällige beziehungsweise noch nicht fällige Auswertung, fehlende Marktdaten und Trefferquote. |
| `tests/test_forecast_recovery.py` | Drei isolierte Tests für harte Cutoff-Grenzen, zeitzonensichere Zeitstempel, idempotente getrennte Speicherung, Integrität, Fingerabdruck und den technisch erzwungenen Ausschluss aus echten Forward-Tests. |
| `tests/test_forecast_backup.py` | Zwei isolierte Tests für geprüfte Sicherung/Wiederherstellung in eine neue Datei, Überschreibschutz und Ablehnung einer beschädigten SQLite-Datei. |
| `tests/test_forecast_calibration.py` | Zwei isolierte Tests für leeres und belastbares Kalibrierungsprofil, reproduzierbaren Datenfingerabdruck, Segmentierung, Mindestdatenregeln, Guardrails und atomare Speicherung. |
| `tests/test_forecast_monitoring.py` | Drei isolierte Tests für erkannte Ergebnis-/Wahrscheinlichkeitsverschlechterung, Schutz vor Driftbehauptungen aus Kleinstichproben sowie einen reproduzierbaren rein beobachtenden Leerbericht. |
| `tests/test_forecast_lock.py` | Zwei Prozess- und Integrationstests für parallele Startablehnung, automatische Sperrfreigabe und Schutz vor Datenbank- oder Marktarbeit. |
| `tests/test_recommendation_synthesis.py` | Einundzwanzig Szenario-, Vertrags- und Schnittstellentests für die zentrale Empfehlung bei Aktien, ETFs, Krypto, großen Kursrückgängen, schwächeren Fundamentaldaten, Datenlücken, bestehenden Positionen, Portfolio-Konflikten, konsistenten Mehrpfad-Plänen und App-Reexporten. |
| `tests/test_analysis_performance.py` | Zwei Regressionstests für die Wiederverwendung täglicher Chartdaten und parallele unabhängige Research-Abrufe. |
| `tests/test_analysis_models.py` | Zwei Kompatibilitätstests für gemeinsame Datenmodelle, App-Reexporte und unveränderte Standardfelder. |
| `tests/test_asset_search.py` | Vier isolierte Tests für bekannte Ticker ohne Netzwerk, direkte Eingaben, Deduplizierung, ungeeignete Yahoo-Treffertypen und Tippfehler-Vorschläge. |
| `tests/test_json_history_store.py` | Drei isolierte Tests für fehlende, ungültige und ältere JSON-Formate, vollständige atomare Speicherung sowie Erhalt der alten Datei bei Austauschfehlern. |
| `tests/test_technical_analysis.py` | Fünf isolierte Tests für App-Kompatibilität, Indikatoren, Intervall-Annualisierung, CRV, Marktphasen und numerische Hilfsfunktionen. |
| `tests/test_portfolio_analysis.py` | Fünf isolierte Tests für read-only Laden, defensive Portfolio-Normalisierung, Marktwertberechnung, Klumpen-/Kryptoabschläge und die unveränderte App-Schnittstelle. |
| `tests/test_currency_utils.py` | Vier isolierte Tests für deutsche Betragsformate, EUR-Anzeige, fehlende Wechselkurse, nicht mutierende Kursumrechnung und App-Kompatibilität. |
| `tests/test_fundamental_analysis.py` | 18 direkte Tests für Aktien-/ETF-Snapshots, Datenlücken, Profitabilitäts- und Bewertungsgrenzen, vollständige Scorebeiträge, Nicht-Mutation und App-Kompatibilität. |
| `tests/test_data_quality_analysis.py` | Sechs direkte Tests für App-Reexporte, vollständige und ausgefallene externe Quellen, unveränderte Ampelschwellen, vollständige Historie, Nicht-Mutation und sicheren komplett leeren Kurszustand. |
| `tests/test_score_composition.py` | Fünf direkte Tests für App-Reexporte, Reihenfolge/Prozentdarstellung, exakten Standardgesamtwert, benutzerdefinierte Gewichte ohne Mutation sowie neutrale und gerundete optionale Werte. |
| `tests/test_valuation_analysis.py` | Fünf direkte Tests für App-Reexport, vollständige Aktien-Multiples, Nicht-Mutation, nicht endliche/fehlende Werte, Krypto-Makrokontext und fehlende ETF-Indexdaten. |
| `tests/test_future_potential_analysis.py` | Fünf direkte Tests für App-Reexporte, Wachstums-/Margen-/News-Beiträge, nicht endliche Werte, Krypto-Lücken, hohe/niedrige Erwartungen, fehlende Spezialdaten und Nicht-Mutation. |
| `tests/test_scenario_analysis.py` | Sieben direkte Tests für App-Reexporte, 100-Prozent-Summe, Mindest-Basisfall, starke/schwache Marktstruktur, zentrale sichtbare/numerische Marken, konservative Fallbacks und Nicht-Mutation. |
| `tests/test_entry_plan.py` | Elf direkte Tests für App-Reexporte, reale und fehlende Zonen, sämtliche Aktionsschwellen, Confidence/Horizont sowie zukünftige beziehungsweise vergangene Earnings-Termine. |
| `tests/test_price_attractiveness.py` | Fünf direkte Tests für App-Reexporte, Fundamentalstärke/-schwäche/-lücken, Kursrückgangsbonus, Regel gegen ein automatisches Kaufsignal aus dem Hochabstand, Asset-Typ-Kontext und Nicht-Mutation. |
| `tests/test_long_term_analysis.py` | Zwölf isolierte Tests für Quellenmetadaten, Yahoo-only-Ablehnung, Pflichtabdeckung, Primär-/unabhängige Belege, Referenzen, Quellenalter nach Typ, Veröffentlichungs- und Zukunftszeitpunkte, Zeitzonen, Techniktrennung, Provenienz und Nicht-Mutation. |
| `tests/test_long_term_research_cache.py` | Neun isolierte Tests für pfadsichere Dateinamen, atomaren Roundtrip, Provenienz, Stale-Sperre, bereits bei Sammlung veraltete Quellen, beschädigte Dateien, Zukunftsschema, Validierung, Austauschfehler und Zeitregeln. |
| `tests/test_long_term_scoring.py` | Vierzehn isolierte Fälle für Quellengate, gewichtete Teil- und Gesamtscores, Szenarioerwartung, Techniktrennung, Pflichtfaktoren, Zahlenbereiche, Drei- bis Sieben-Jahres-Horizont, Wahrscheinlichkeiten, Zielreihenfolge, Bedingungen und Nicht-Mutation. |
| `tests/test_sec_filing_sources.py` | Siebzehn isolierte Fälle für SEC-Ticker-/CIK-Zuordnung, offizielle Archiv-URLs, Jahres-/Quartalsformulare, unbekannte und Klassen-Ticker, veraltete Dokumente, Fair-Access-Kontakt/Anfragetakt, Ticker-Map-Cache, begrenztes Retry/Backoff, dauerhafte HTTP-/JSON-Fehler, Pfadsicherheit und Nicht-Mutation. |
| `tests/test_sec_json_cache.py` | Sieben isolierte Tests für URL-/Pfad-Whitelist, öffentlichen atomaren Roundtrip ohne Kontaktkennung, Netzvermeidung, Kopierschutz, TTL, beschädigte/Zukunfts-/Fremdschemadaten, sicheren Austausch und Zeit-/Dateinamensregeln. |
| `tests/test_sec_financial_facts.py` | Neun isolierte Tests für neueste abgeschlossene Jahreswerte, feste XBRL-Konzeptpriorität, Quartals-/Zukunfts-/Nichtendlichkeitsfilter, sicheren Leerzustand, exakte Ein-/Zwei-Filing-Verknüpfung, sachliche Vorjahresänderung, negative Basiswerte, Evidenz-Provenienz und Nicht-Mutation. |
| `tests/test_sec_long_term_collection.py` | Vier isolierte Integrationstests für vollständige SEC-Teilkollektion, weiterhin geschlossenes Gesamtgate, unbekannte Ticker, Company-Facts-Teilausfall, falsche Accession-Verknüpfung und Nicht-Mutation. |
| `tests/test_sec_collection_cli.py` | Vier isolierte CLI-Fälle für vollständig offline Vorprüfung, fehlende/gültige Kontaktkonfiguration ohne Wertausgabe, privaten Cachepfad und kontaktfreie Live-Ausgabe. |
| `tests/test_trading_assistant.py` | 37 isolierte Tests für beide Swing-Setups, ATR-Normalisierung, diagnostische statt sperrende Langfristqualität, zentrale Ablehnungsregeln, abgeschlossene Signalkerzen, versionierten Orderplan, konservative spätere Balkenprüfung, CRV, Positionsgröße, unveränderlichen Stop-Vertrag, manuellen Trade-Lebenszyklus, Ablauf und Paper-Statistiken. |
| `tests/test_trade_republic_reference.py` | Acht isolierte Tests für sicheren Unbekannt-Standard, listing- und ISIN-spezifische dauerhafte Zuordnung, manuelle ISIN-Ergänzung, abweichende Instrumente, frischen/veralteten TR-Preis ohne Yahoo-Fallback, einheitliche TR-Kursmarken und append-only Integrität. |
| `tests/test_swing_universe.py` | Prüft Mindestgröße, ServiceNow, Pflichtfelder, Eindeutigkeit, Hebelausschluss und sichtbare Behandlung ungültiger Universumszeilen. |
| `tests/test_swing_scanner.py` | Neun Tests für ATR-normalisierten Vorfilter, Volumenabdeckung statt Rohstückzahl-Hard-Gate, vollständige Tiefenprüfung ohne Top-N-Cutoff, rechnerisch erklärten Assetklassen-Funnel/Bias, 1.000-Asset-/850-Daten-Abdeckung, Kein-/Mehrfach-Trade-Fälle und Fehlerisolierung. |
| `tests/test_forecast_horizon_schedule.py` | Prüft alle unabhängigen Startfrequenzen, kalenderbasierte längere Rhythmen, Nicht-Mutation sowie das Langfrist-Evidenzgate einschließlich Stablecoin-Ausschluss. |
| `tests/test_swing_scanner_app.py` | Integriert Universum, Vorfilter, Tiefenanalyse, harte Portfoliofreigabe und Batch-Aufteilung im App-Pfad. |
| `tests/test_swing_forward_store.py` | Fünf isolierte Tests für Null-Trade-Scans, unveränderbare Signalsnapshots, Idempotenz, Konfliktschutz, append-only Datenbanktrigger und Ereignisse. |
| `tests/test_swing_forward_evaluation.py` | Sieben isolierte Tests für Gap-Verpassung, kostenbereinigten Einstieg/Ausstieg, Gap unter Stop, Zielabfolge, unklare Kerzenreihenfolge, abgeschlossene Tageskerzen und Kostenvertrag. |
| `tests/test_historical_fx.py` | Drei Tests für EUR-Identität, Intraday-Kurse nur bis zum Ereignis und sicheren Fallback auf den vorherigen Tagesabschluss. |
| `tests/test_swing_forward_runner.py` | Drei Integrationstests für chronologische Ereignisspeicherung, Terminalstatus, retry-fähige Provider-Ausfälle und nachholbare historische FX-Bewertung. |
| `tests/test_swing_forward_statistics.py` | Sechs Statistiktests für korrekte Ergebnisgrundgesamtheit, Ziel-1/2-Status, Ergebnis in R, Profitfaktor, Drawdown, Segmente, kombinierte Suche/Filter, wiederkehrende Asset-Fehler und den erst ab Mindestfällen sichtbaren ETF-/Aktien-Forward-Vergleich. |
| `tests/test_swing_edge_diagnostics.py` | Neun Regressionstests für read-only Ursachenanalyse, Gewinner-/Verlustgrundgesamtheit, garantierte Trade-Pflichtfelder, MFE-Schwellen/Median, konkrete Stopausführung, strikt getrennte 5-/20-Sitzungs-Counterfactuals, keinen erfundenen Intrabar-Ablauf sowie den verbindlichen Detailblock in `PROJECT_STATUS.md`. |
| `tests/test_swing_event_research.py` | Siebzehn Regressionstests für Eventvertrag/Fingerprints, Kausalität und Revisionen, Expectation/Actual/Surprise, hierarchische Relevanz, klinische Missingness, Marktübertragung ohne Kausalitätsbehauptung, getrennte Reaktionslabels, append-only Resume, Signal-Sidecars, Legacy-Nachzug, Coverage, Hypothesen-Ledger, Dokumentationsvertrag und produktionsneutrale Forward-Diagnose. |
| `tests/test_overnight_intraday_research.py` | Zwölf Tests für kausale Renditezerlegung, getrennte Zukunftslabels, Multi-Asset-/Zeitraum-/OOS-/Walk-Forward-Vertrag, verschärfte C-Einstufung, Baseline-Inkrementalität, semantische Redundanz, begrenzte Kombinationen und die harte Sperre von Pflichtfiltern sowie automatischer Aktivierung. |
| `tests/test_swing_walk_forward.py` | Historische Leakage-, Append-only-, Idempotenz-, Zeitfenster-, Purging-, Profil-, Gate- und Produktionssperrtests für den getrennten Swing-Forschungsbetrieb. |
| `tests/test_swing_strategy_freeze.py` | Prüft reproduzierbare Fingerabdrücke, append-only Historie, neue Versionen bei fachlichen Änderungen und die gesperrte Performance-/Produktionsfreigabe. |
| `tests/test_swing_technical_challengers.py` | Prüft unveränderte Baseline, getrennte Challenger-Versionen, kausale RSI-/EMA-Nutzung, identische zeitliche Forschungsregeln, Robustheitsauswertung und Produktionssperre. |
| `tests/test_swing_bot_architecture.py` | Prüft gemeinsame nicht umgehbare Risk Engine, Paper-/Shadow-Trennung, Brokerlosigkeit, kausale Fills, Idempotenz, Restart, fail-closed Datenfehler und append-only Evidenz. |
| `tests/test_swing_shadow_execution.py` | Prüft den strikt getrennten Execution-Vertrag, ehrliche Missingness, echte Quote-Pflichtfelder, listinggenaue Zuordnung, Stale-Markierung, keine Yahoo-Tages-/Simulationswerte, keinen erfundenen Fill/Spread, Providerfehler, Resume/Dedupe und Append-only-Trigger. |
| `tests/test_swing_research_data_quality.py` | Fünf Regressionstests für dauerhaft lösbare Fallidentitätskonflikte ohne Überschreiben, idempotentes Resume, getrennt sichtbare Share Classes, ADR/Stammaktie, wirtschaftlich identische Mehrfachlistings und unveränderte direkte Einzelnotierungen. |
| `tests/test_swing_walk_forward_campaign.py` | Kampagnen-, Shard-, Wochenepoch-, Resume-, Nachtstart-, Produktions-Lock-, Restzeit-, Schutzfenster- und Befehlsvertragstests. |
| `tests/test_swing_broad_research.py` | Kausalitäts-, Determinismus-, Indikator-Paritäts-, Label-Trennungs-, konservative Ausführungs-, Resume-, Append-only-, Development-Sperr-, Parameter-Nachbarschafts-, Fingerprint-, manuellen Freeze- und sequenziellen Challenger-Rescan-Tests; zusätzlich bearishe Impuls-/Rally-, Bestätigungs-/BOS-, richtungsneutrale Label-, Frozen-Fingerprint- und Schema-3-Prüfungen. |
| `tests/test_swing_broad_research_transition.py` | Prüft die harte 248/248-Sperre, DB-/Dataset-Fingerprints, abweichende Frozen-Daten, reproduzierbare append-only Übergangsnachweise und die Reihenfolge im Windows-Wrapper. |
| `tests/test_swing_research_quality.py` | Prüft append-only Ledger, semantische Deduplizierung und Resume, Produktions-/Tuning-Sperre, deterministische Placebos/Plateaus/Cluster, korrekte Zeitkennzahlen, exakte Ablation, kausale Entry-Effizienz ohne erfundene Intrabar-Reihenfolge, getrennte Stressszenarien, Survivorship-Hinweise und Evidenztrennung. |
| `tests/test_swing_research_policy.py` | Prüft deterministische Feature-Familien ohne Rohfeatureänderung, Redundanz statt künstlicher Bestätigungen, Komplexität ohne automatische Löschung, gesperrte Entry×Stop×Exit-Raster, getrennte sequenzielle Ledger-Hypothesen, reine 20-Fälle-Diagnostik, unverändertes CRV, Fib-Kontrollen, sekundäre COT/Event-Rollen, Evidenztrennung sowie eingefrorene Broad-/Long-v1-Sicherheiten. |
| `tests/test_swing_external_validation.py` | Ausschluss-, Outcome-Blindness-, Freeze-, Append-only- und Versionsschutztests für das ungesehene externe Assetuniversum. |
| `tests/test_swing_background_runner.py` | Regionale Abdeckung, objektive Null-Trade-Speicherung, Produktionsausfälle sowie fail-open Event-, COT- und Shadow-Quote-Sidecars. Die Tests erzwingen, dass Research-/Providerfehler weder Signal, Paper noch Broad blockieren und keine Brokerorder ermöglichen. |
| `tests/test_swing_user_store.py` | Zehn Tests für getrennte unveränderbare Nutzertrades, bestätigungspflichtige Abweichungen, die nicht übersteuerbare Signalzeitgrenze, Zeit-/Preis-/Stückzahlregeln, nur engeren Stop, Teilverkauf, Abschluss, Ergebnis und regelbasierte Begleitung. |
| `tests/test_swing_trade_monitor.py` | Drei Tests für Strukturbruch mit Verkaufsvolumen, regionale Schlusskursgrenze und ehrlichen Leerzustand bei zu kurzer Historie. |
| `tests/test_forecast_model_registry.py` | Vier Tests für unveränderbare Shadow-Kandidaten, vollständige und korrekt geordnete Freigabegates ohne automatische Aktivierung sowie Ablehnung ungültiger Fingerabdrücke vor jeder Speicherung. |
| `tests/test_information_hierarchy.py` | Sechs Regressionstests für verständliche Detailtexte, ausgeblendete Leermodule, kompakte Szenario-/Risikoansichten, vollständigen Textumbruch, die kompakte Drei-Bewertungen-Hauptansicht sowie den nur bei aktivem Modus sichtbaren Portfolio-Bereich. |
| `.github/workflows/smoke.yml` | GitHub-Actions-Workflow für Repository-Sicherheitscheck und Offline-Smoke-Test unter Python 3.11. |
| `.gitignore` | Schließt lokale Umgebungen, Caches, Secrets und private Laufzeithistorien von Git aus. |

Die Anwendung ist fachlich weiterhin weitgehend monolithisch aufgebaut: `app.py` umfasst rund 9.533 Zeilen und 219 eigene Top-Level-Funktionen. Die zehn gemeinsamen Datenklassen sowie Asset-Suche, JSON-Historienspeicherung, technische Analyse, Datenqualität, Score-Zusammensetzung, Portfolio-Bewertung, Währungsumrechnung, Aktien-/ETF-Fundamentalanalyse, Bewertung, Zukunftspotenzial/eingepreiste Erwartungen, Szenarien/Expected Value, Empfehlungssynthese, Entry-Plan, Preisattraktivität, Long-Term-Quellenprüfung, -Cache, -Scoring sowie SEC-Filing-Discovery/-JSON-Cache/-Finanzfakten/-Teilkollektion, Long-Swing-Logik, automatische Prognosehaltung, Kalibrierungsprofil, Drift-/Qualitätsüberwachung und Orchestrierung sind nun in eigenen Modulen getrennt; eine vollständige Aufteilung der Analyse-Domain und UI ist noch nicht vorhanden.

## 3. Aktueller Funktionsstand

### Bereits umgesetzt

#### Anwendung, Suche und Darstellung

- Native Streamlit-Startseite als Hauptmenü bei jeder neuen Sitzung, ohne Analyse-, Opportunity- oder Scanner-Eingaben.
- Drei klar getrennte Einstiege: `Asset-Analyse`, `Investment Opportunities` und `Swing Trade Finder`.
- Kleiner Session-State-Router mit `home`, `analysis`, `opportunities` und `swing_finder`; der ältere Zustand `scanner` wird kompatibel auf `swing_finder` abgebildet, und eine neue Sitzung startet immer mit `home`.
- Sichtbarer Button `← Zurück zur Startseite` in allen drei Arbeitsbereichen.
- `Investment Opportunities` zeigt bis zur fachlichen Umsetzung bewusst nur die beiden geplanten Modi und den Hinweis, dass keine scheinbaren Kandidaten erzeugt werden.
- Erste gemeinsame CSS-Tokens vereinheitlichen Radien, Rahmen, Oberflächen, Schatten und Schaltflächen, ohne Analyse- oder Bewertungslogik zu verändern.
- Kleine Richtungstrefferquote mit Zahl ausgewerteter Prognosezeiträume in der Ecke der Startseite; unter 20 Auswertungen erscheint `Noch nicht belastbar`.
- Die Aktien-Analyse besitzt keine zentrale Sidebar mehr. Zeitraum, Intervall, Auto-Refresh, Währungsdarstellung, Portfolio-Optionen, seltene Asset-Typ-Korrektur und erweiterte Einblicke liegen oben rechts unter `Einstellungen`.
- Große zentrale Suche nach Asset-Namen oder Yahoo-Finance-Ticker mit integrierter Vorschlagsliste und bewusstem Start über `Analysieren`.
- Zuletzt erfolgreich analysierte Assets erscheinen nur innerhalb der Vorschlagsliste und werden dort priorisiert; fehlgeschlagene Suchen werden nicht gespeichert.
- Stabile Fallback-Ticker für ausgewählte Aktien, ETFs und Kryptowährungen, einschließlich ServiceNow (`NOW`).
- Manuelle Asset-Typ-Korrektur nur in den erweiterten Einstellungen oder sichtbar nach unsicherer automatischer Erkennung.
- Automatische Erkennung von Aktie, ETF, Kryptowährung oder unbekanntem Asset-Typ.
- Auswahl von Chart-Zeitraum, Intervall und optionalem Auto-Refresh.
- Trennung von sichtbarer Chart-Historie und langfristiger Analyse-Historie.
- Standardanzeige sichtbarer Kurse und Beträge in Euro; optional `Euro und Originalwährung` unter Einstellungen. Interne Indikatorberechnung bleibt in Originalkursen.
- Dreistufige Informationshierarchie: zuerst ausschließlich kompakte Empfehlung und Mehrpfad-Plan, danach auf Klick verständliche Detailfacetten und zuletzt ein standardmäßig geschlossener Bereich `Erweiterte Analyse`.
- Kompakter Ergebniskopf mit Identität, EUR-Kurs, Asset-Typ, Anlagehorizont und Confidence; darunter zentrale Empfehlung, sichtbar getrennte langfristige Attraktivität, Preisattraktivität und kurzfristiges Timing, höchstens drei Gründe, höchstens zwei Risiken, Prozent-Tranchen für jetzt/Rücksetzer/weitere Stärke, Widerlegungsbedingung und Gültigkeit.
- Detailfacetten: `Investmentthese`, `Preis & Bewertung`, `Einstieg & Vorgehen`, `Chancen`, `Risiken`, `Szenarien` und `Markt & Umfeld`; `Portfolio-Effekt` erscheint ausschließlich bei aktivem Portfolio-Modus.
- Geschlossene erweiterte Analyse mit `Technische Kennzahlen`, `Fundamentale Kennzahlen`, `Datenqualität`, `Methodik` und `Prognosequalität`; RSI, MACD, Durchschnitte, Volatilität, Multiplikatoren, Gewichte, Score-Komponenten, Backtests und Rohdaten sind dort gebündelt.
- Anfänger-Modus mit vereinfachten Erklärungen.
- Interaktive Plotly-Charts für Kurs, RSI, MACD und Volumen sowie eine Rohdatenansicht.

#### Technische Analyse und Timing

- RSI 14.
- MACD und Signal-Linie.
- 50er- und 200er-Durchschnitt.
- Trend-, Volumen- und Volatilitätseinordnung.
- Lokale Unterstützungen und Widerstände.
- Risiko bis Unterstützung, Potenzial bis Widerstand und Chancen-Risiko-Verhältnis.
- Marktphasen wie Bullenmarkt, Bärenmarkt, Korrektur, Bodenbildung und Seitwärtsmarkt.
- Bull-, Base- und Bear-Szenarien mit Wahrscheinlichkeiten und Kursbereichen.
- Nachkaufzonen und entscheidende Widerlegungsmarken, soweit aus vorhandenen Daten ableitbar.

#### Getrennte Bewertungslogik

- **Asset-Qualität** bewertet die langfristige Qualität des Assets.
- **Kaufsignal** bewertet ausschließlich den aktuellen Einstiegszeitpunkt aus Technik, CRV und begrenzten Marktphasen-/Signal-Anpassungen.
- **Depot-Effekt** bewertet ausschließlich die Wirkung auf das optionale Portfolio.
- Portfolio-Daten verändern weder Asset-Qualität noch Kaufsignal.
- Asset-spezifische Research-Gewichtungen für Aktien, ETFs, Kryptowährungen und unbekannte Assets.
- Transparente Erläuterung von Score-Bändern und verwendeten Gewichtungen.
- Zentrale Synthese aus Qualität, Timing, CRV, Marktphase, Bewertung, Risiken, Datenlage und optionalem Depot-Effekt, ohne die vorhandenen Einzel-Scores umzuschreiben.
- Eigenständige Preisattraktivität mit den Stufen `Günstig`, `Fair`, `Erhöht`, `Extrem` und `Nicht belastbar`; sie verbindet vorhandene Bewertung, erwartete Szenariorendite und Kursabstand zum höchsten Kurs der maximal verfügbaren Historie, ohne den Rückgang als automatisches Kaufsignal zu behandeln.
- Für Aktien werden aktuelle Umsatz-, Gewinn- und Cashflow-Signale als Plausibilitätsprüfung verwendet. Da historische Fundamentaldaten genau zum früheren Hoch nicht vollständig vorliegen, wird ein exakter Vorher-/Nachher-Vergleich transparent als nicht belastbar gekennzeichnet. Mehrere aktuelle Schwächesignale verhindern eine falsche `günstig`-Einordnung allein wegen des Kursrückgangs.
- Für Kryptowährungen wird der Abstand zum Hoch als Markt- und Zykluskontext verwendet; fehlende On-Chain-, Flow- und Liquiditätsdaten werden ausdrücklich als Einschränkung genannt.
- Eindeutige Handlungskategorien: `Jetzt kaufen`, `Erste Tranche kaufen`, `Bei Bestätigung kaufen`, `Auf konkrete Kaufzone warten`, `Halten`, `Teilweise reduzieren` sowie `Verkaufen oder vermeiden`.
- Die strukturierte Synthese liefert zusätzlich langfristige Einschätzung, Preisattraktivität, aktuelles Timing, Anlagehorizont, Confidence, Sofort- und Rücksetzer-Kaufzone, relative Tranchierung, Handlungen für jetzt/Rücksetzer/weitere Stärke, Widerlegungsbedingung und Gültigkeit.
- Bedingte Einstiege nennen eine Kaufzone als Bereich, einen alternativen Bestätigungsweg und eine Widerlegungsmarke. Prozentangaben beziehen sich ausschließlich auf die geplante Position beziehungsweise Aufstockung; ohne Risikobudget werden keine Eurobeträge erfunden.

#### Professionelles Research

- Datenqualitätsprüfung mit sichtbaren Warnungen bei fehlenden oder eingeschränkten Quellen.
- Charttechnik- und Momentum-Module.
- Fundamentalanalyse für Aktien, ETFs und Kryptowährungen mit asset-spezifischer Logik.
- Aktienkennzahlen unter anderem zu Wachstum, Margen, Cashflow, Verschuldung, Kapitalrendite und Bewertungsmultiplikatoren, soweit Yahoo Finance Daten liefert.
- ETF-Kontext unter anderem zu Kostenquote, Fondsgröße, Kategorie, Renditezeiträumen, Beta und Diversifikationshinweisen, soweit verfügbar.
- Bewertungsmodul mit mehreren Multiples, Wachstums- und Cashflow-Kontext sowie transparenter Kennzeichnung fehlender historischer oder vergleichbarer Daten.
- Zukunftspotenzial und eingepreiste Erwartungen.
- Innovations-/Hype-Kontext und Blasenrisiko.
- Expected-Value-Betrachtung aus Szenarien, Wahrscheinlichkeiten und erwarteten Renditen.
- Marktregime- und Makro-Wirkungseinordnung.
- Makro-Modul mit Yahoo-Finance-Proxies für Risikoappetit, US-Zinsen, Dollar sowie Inflation/Realzinsen.
- Geopolitischer Kontext auf Basis verfügbarer Yahoo-News-Titel.
- Rohstoff-Kontext für Öl, Gas, Kupfer, Gold und einen Uran-Proxy.
- Krypto-Zyklus mit deterministischer Bitcoin-Halving-Einordnung als Kontextsignal.
- News-Modul mit Quelle, Datum, Relevanz und einfacher Sentiment-Qualität.
- Risiko- und Liquiditätsmodule mit Datenabdeckung und neutralem Verhalten bei Datenlücken.
- Analysten-Konsens, Earnings, Event-Risiko und institutionelle Daten, soweit Yahoo Finance entsprechende Felder liefert.
- Vertrauensscore, Datenquellenwarnungen und Unsicherheitsfaktoren.
- Professionelle, handlungsorientierte Empfehlung mit konkretem Plan ohne automatische Ausführung; fehlende Daten senken die Confidence, führen aber nicht automatisch zu einer negativen Asset-Bewertung.

#### Portfolio-Modus

- Optionaler Portfolio-Schalter.
- Einlesen einer lokalen `portfolio.json` mit Cash und Positionsdaten.
- Bewertung von Cash-Reserve, Positionswert, Portfoliogewicht, Klumpenrisiko und möglichem Nachkauf.
- Verständliche Hinweise bei fehlender oder ungültiger optionaler Portfolio-Datei.
- Strikte Trennung des Depot-Effekts von Asset-Qualität und Kaufsignal.

#### Swing Trade Finder, Risikomodell und Trade Journal

- Eigenständiger automatischer Scannerbereich ohne Sidebar, erreichbar über die Startseite und mit Rückkehr zum Hauptmenü.
- Intern gepflegtes, versioniertes Universum mit 2.520 aktiven gültigen Assets: 2.431 Aktien, 59 ETFs und 30 Kryptowährungen. Es verbindet das vorhandene breite Projektuniversum mit regulären Nasdaq-Global-Select-Aktien; ServiceNow bleibt enthalten.
- Mehrstufiger Pfad: gebündelter Jahresdatenabruf, binärer Grobfilter auf Daten, Mindesthistorie, Preis, Liquidität/Volumen, Volatilität, Aufwärtstrend und Pullback-/Breakout-Struktur, danach vollständige Analyse jedes bestandenen Kandidaten und abschließende harte Freigabe. Es gibt keine feste 60er- oder andere Top-N-Grenze.
- Version 1 ist bewusst auf Long-Swing-Trades über mehrere Tage bis einige Wochen und zwei Setups begrenzt: Rücksetzer im intakten Aufwärtstrend sowie bestätigter Ausbruch.
- Ein Trade wird nur bei erfüllter Datenqualität, EUR-Liquidität, Kaufsignal-, Confidence-, Markt-, Ereignis-, Struktur-, Einstiegs-, CRV- und Expected-Value-Prüfung freigegeben. Die langfristige Asset-Qualität bleibt dokumentiert, ist im kurzfristigen Swing-Kontext aber weder Hard-Gate noch Rangfaktor. Ein relativ bester, aber objektiv schwacher Kandidat wird nicht erzwungen.
- Hauptansicht zeigt Marktlage, Scanzeitpunkt, Universumsgröße, erfolgreich geladene Assets, Vorfilterauswahl, Tiefenprüfungen, Freigaben und Datenfehler sowie ausschließlich freigegebene Trades. Ohne Freigabe erscheint `Aktuell kein hochwertiger Trade vorhanden.` einschließlich Ablehnungszusammenfassung.
- Die sichtbare Kategorie `Beobachten`, eine Watchlist schwacher Kandidaten und Short-/Absicherungs-Setups sind aus dem Scanner-v1-Hauptpfad entfernt. Abgelehnte Kandidaten und exakte Gründe bleiben nur unter `Erweiterte Einblicke` verfügbar.
- Jeder Trade zeigt Asset/Ticker, Richtung, Setup-Typ, EUR-Kurs, konkrete Einstiegszone, messbare Schlusskursbedingung, Stop, ein bis zwei strukturell abgeleitete Ziele, Chance/Risiko in Euro und Prozent, zentral berechnetes CRV, Haltedauer, Gültigkeit, maximalen Einstieg, Gründe, Hauptrisiko und Nichteinstiegsbedingungen.
- Zentrale Standardgrenzen in `SwingTradeThresholds`: mindestens 200 Historienzeilen, Datenqualität 7,0/10, relatives Volumen 0,50, durchschnittlicher Tagesumsatz 1,0 Mio. € für Aktien, 0,5 Mio. € für ETFs und 5,0 Mio. € für Krypto, Kaufsignal 5,8, Confidence 5,8, Marktscore 4,0 und CRV 2,0. Setupzonen werden relativ zur ATR mit konservativen Obergrenzen normalisiert; Asset-Qualität hat kein Swing-Minimum. Harte Ereignissperre: drei Tage; Standardgültigkeit: sieben Tage.
- CRV wird ausschließlich zentral als `(Ziel - Einstieg) / (Einstieg - Stop)` berechnet; für Long muss `0 < Stop < Einstieg < Ziel` gelten. Ziele sind auf maximal 18 % Abstand begrenzt und müssen aus der Setup-Struktur ableitbar sein.
- Trefferwahrscheinlichkeit und Expected Value werden erst ab mindestens 20 ausgewerteten vergleichbaren Fällen als belastbar verwendet. Darunter erscheint exakt `Trefferwahrscheinlichkeit noch nicht belastbar.`; ein belastbar negativer Expected Value lehnt das Setup ab.
- Im Hauptbereich ist nur `Verfügbares Tradingkapital in Euro` einzugeben. Interne, nur lesbare Risikoregel: höchstens 0,50 % Kapitalrisiko je Trade, 2,00 % offenes Gesamtrisiko, 50 % Gesamtbelastung und 20 % je Position. Die feste Drei-Trade-Grenze wurde entfernt; die zulässige Anzahl wird dynamisch aus verbleibendem Risiko und Kapitalbindung berechnet.
- Stop-Loss wird aus Setup-Struktur, Unterstützung und Volatilität abgeleitet, verständlich begründet und liegt bei Long unter dem Einstieg. Unrealistisch große Abstände über 8 % bei Aktien, 7 % bei ETFs oder 12 % bei Krypto verhindern die Freigabe.
- Stückzahl, investierter Betrag, geplanter Verlust sowie mögliche Gewinne an Ziel 1/2 werden automatisch berechnet. Ohne gültiges Kapital gibt es keine Stückzahl; der Gap-Hinweis stellt ausdrücklich klar, dass der geplante Stop-Verlust nicht garantiert maximal ist.
- Jede neue Freigabe besitzt einen versionierten, fingerprinteten und zuerst sichtbaren Orderplan. Er speichert Einstiegsmethode, abgeschlossene Signalkerze, frühesten Folgetag, Limit, Aktivierung, Maximalpreis, initialen Stop, Ziele, Gültigkeit, Löschbedingungen, denselben FX-Snapshot sowie nach Positionsfreigabe Stückzahl, Kapitaleinsatz, geplanten Verlust und mögliche Gewinne. `automatic_order_execution` bleibt fest `false`.
- Besitzt ein Plan zwei Ziele, gilt versioniert ein 50/50-Ausstieg. Die Karte zeigt den geplanten Teilgewinn an Ziel 1 und den kumulierten Gewinn bei Ziel 2; die Paper-Auswertung aggregiert Ziel 1 mit Ziel 2 oder einem späteren Stop und zählt niemals beide Ziele für die volle Position.
- Eine Tageskerze vom aktuellen Scan-Tag gilt erst nach der konservativen regionalen Schlusszeit als abgeschlossen; bei Krypto weiterhin erst am nächsten UTC-Tag. Ausbruchssignale dürfen nie rückwirkend zum bestätigenden Schlusskurs als Einstieg gelten; Lücke über Maximalpreis und Strukturbruch werden bei der späteren Balkenprüfung als verpasst beziehungsweise annulliert behandelt.
- Beim manuellen Öffnen bleibt der initiale Stop mit einer Stop-Vertragsversion unverändert gespeichert. Ein aktiver Long-Stop darf nur angehoben und niemals wieder vom Einstieg weg erweitert werden.
- Vor der ersten Nutzung erscheint einmalig der verbindliche Verlusthinweis. Seine Bestätigung wird atomar und ausschließlich lokal unter `runtime/` gespeichert.
- Alle freigegebenen Scanner-Signale werden automatisch lokal als Paper-Trades in `trade_history.json` dokumentiert. Abgelaufene Setups werden markiert, nicht gelöscht; Statistiken umfassen Trefferquote, Durchschnittsgewinn/-verlust, Expected Value, Profitfaktor, Drawdown, Setup-/Marktphasen-Ergebnisse, Ziel-/Stop-Treffer, Ablauf und Opportunitätskosten, soweit aus abgeschlossenen Fällen ableitbar.
- Defensive Normalisierung älterer und neuerer Trade-Journal-Felder bleibt erhalten.
- Keine Broker-Verbindung und keine Orderausführung.
- Echte manuelle und regionale Hintergrundscans werden zusätzlich unveränderbar in einer getrennten privaten SQLite-Datenbank gespeichert. Null-Trade-Scans bleiben erhalten; Updates und Löschungen an Scans, Signalen und Ereignissen sind auf Datenbankebene gesperrt.
- Die automatische Paper-Auswertung verwendet nur vollständige spätere Kursbalken, konservative versionierte Kosten und behauptet bei unklarer Intraday-Reihenfolge keinen Treffer. Gap über Maximalpreis, Gap unter Stop, Ablauf, Ungültigkeit und nicht verfügbare Daten besitzen eigene Statuswerte.
- Terminale Paper-Ergebnisse speichern zusätzlich maximalen günstigen und ungünstigen Kursausschlag ab der Einstiegskerze. Das Archiv leitet daraus Paper-Einstiegs-/Ausstiegszeit, Haltedauer, Ergebnisstatus sowie maximalen Zwischengewinn/-verlust ab. Bei groben Kursintervallen bleibt die Aussage ausdrücklich eingeschränkt; bestehende append-only Ereignisse werden nicht umgeschrieben.
- Historische Ein- und Ausstiegswechselkurse werden Point-in-Time-sicher als separates append-only Ereignis gespeichert. Bei Teilverkäufen erhält jedes Ausstiegsbein seinen eigenen zeitlich passenden FX-Beleg. Intraday-Kurse nach dem Ereignis sind ausgeschlossen; als Fallback ist nur der vorherige Tagesabschluss zulässig. Fehlende FX-Belege lassen das Originalwährungsergebnis unverändert und können später ohne Überschreiben nachbewertet werden.
- Die 2.520 Assets bleiben regional ohne Überschneidung aufgeteilt: 65 Asien/Australien, 73 Europa, 2.352 Amerika/Global und 30 Krypto. Registriert sind Asien/Australien um 10:30 Uhr, Europa um 18:15 Uhr und die Prognose-Abendkette um 22:30 Uhr. Die Abendkette führt nach den Prognosen Amerika/Global und danach Krypto aus; separate Nachtaufgaben existieren nicht mehr. Alle vier Bereiche wurden am 2026-08-11 mit der Scannerpipeline real ausgeführt: 65/65, 73/73, 2.350/2.352 und 29/30 geladen, null Rate-Limits, jeweils Status `ok`.
- Dieselbe abgeschlossene Signalkerze kann über wiederholte Wochenend- oder Nachholläufe nur ein Forward-Signal je Logikversion erzeugen. Die einzelnen Scans bleiben trotzdem als reale Beobachtungen erhalten; der erste unveränderbare Signalsnapshot wird nicht ersetzt.
- Die erweiterte Ansicht zeigt die append-only Scan-/Signalbasis, eindeutige Paper-Ergebnisse und getrennte Nicht-Ergebniszustände. Trefferquote, durchschnittliches R, Profitfaktor, Drawdown und Segmente werden erst aus eindeutigen Ergebnissen gebildet; unter 20 Fällen bleibt `Trefferwahrscheinlichkeit noch nicht belastbar.` Suche nach Asset/Ticker/ISIN/Signal-ID, Signalzeitraum sowie Filter nach Status, Setup, Einstiegsmethode, Asset-Typ, Gewinn/Verlust/offenem Ergebnis, Datenqualität, Region, historischem FX, Strategieversion, Quellentyp und dokumentiertem Nutzertrade sind kombinierbar. Systemplan, Ereignisverlauf, segmentierte Werte und scanübergreifende technische Asset-Fehler bleiben prüfbar. Fehler führen niemals automatisch zur Löschung eines Tickers.
- `Trade getätigt` dokumentiert ausschließlich eine bereits extern ausgeführte Nutzerhandlung. Persönliche Trades liegen getrennt vom objektiven Paper-Signal; Abweichungen von Zeitpunkt, Maximalpreis oder Stückzahl benötigen eine ausdrückliche Bestätigung und bleiben gespeichert.
- Persönliche Stop-Nachzüge, Teilverkäufe und Abschlüsse sind append-only. Initialer Stop und Systemplan bleiben unverändert; ein Long-Stop kann nur angehoben werden. Die aktive Ansicht prüft zusätzlich abgeschlossene Tagesstruktur, Unterstützung, Trend, Gap und relatives Verkaufsvolumen. Nicht belastbar automatisierte Nachrichten-, Ereignis- und Branchenfaktoren werden sichtbar als fehlend ausgewiesen; die App führt keine Order aus.
- Eine gemeinsame unabhängige Risk Engine versorgt Scanner, autonomen Paper-Bot und Shadow-Live mit demselben versionierten Risiko-, Positionsgrößen- und Orderplan. Zulässig sind ausschließlich die brokerlosen Modi `analysis_only`, `paper_only` und `shadow_only`; kein Strategie- oder Challengerpfad kann die Risikoprüfung umgehen.
- Die Strategie-Freeze-Infrastruktur speichert vollständige Strategie-, Parameter-, Filter-, Risiko-, Order-, Positionsmanagement-, Exit-, Kosten- und Datenverträge zusammen mit Code-, Konfigurations-, Komponenten- und Datenfingerabdrücken. Neun getrennte append-only Freezes existieren für die unveränderte Long-v1-Baseline und acht vorab deklarierte RSI-, EMA20/EMA50-, EMA+RSI- sowie Pullback-/Breakout-Challenger. Keine Version ist performancefreigegeben oder automatisch produktiv.
- Die acht technischen Challenger verwenden ausschließlich damalige Daten, dieselben Kosten-, Purging-, Development-/Validation-/Holdout-Regeln wie die Baseline und getrennte Strategieversionen. Die Auswertung zeigt unter anderem R/Expectancy, Profitfaktor, Drawdown, Trefferquote, Tradeanzahl, Verlustserien, Markt-/Volatilitätsregime, zeitliche Stabilität, geringere Tradezahl und Parameterrobustheit; sie kann keine Produktionsstrategie aktivieren.
- Die historische Kampagne ist seit 2026-08-23 um 01:47 Uhr vollständig: 248/248 Jobs, A 80/80, B 80/80 und C 80/80. Der Frozen-Dataset-Fingerprint blieb unverändert; weder Queue noch Fälle, Regeln oder Produktion wurden durch die Policy-Arbeit verändert.
- Die automatische COT-Forward-Verknüpfung ist aktiv. Der append-only Speicher enthält 61.944 CFTC-Reportversionen; der offizielle Read-only-Abruf am 2026-08-23 ergänzte 1.085 tatsächliche lokale First-Seen-Belege für künftige Signale. Alle 29 bestehenden Forward-Signale besitzen einen Sidecar: 3 (`CRVL`, `COP`, `CVX`) sind mit einem zum Cutoff bereits verfügbaren `tff_futures_only`-US-Breitmarktkontext vom Berichtsstichtag 2026-08-11 verknüpft, 26 tragen `cot_context_unavailable`. Spätere Reports wurden nicht eingesetzt; der Forward-Datenbankhash blieb vor/nach dem Nachzug identisch `455F55F3FB8676BE8C123E22CE559CA6DA2948078D12E317914ED996139E543A`.
- Der getrennte breite Frozen-Research-Pfad ist technisch umgesetzt: outcome-unabhängige Pullback-/Breakout-Grundgesamtheit, bestehende RSI14-/EMA20-/EMA50-/ATR-/Volumen-/Marktphasenlogik, Impuls- und Pullback-Geometrie, objektive Fibonacci-Vergleichszonen, bestätigte Swing-/BOS-Struktur, Daily-/Weekly-/Monthly-/Quarterly-/Yearly-Opens, nur damals abgeschlossene Saisonalitätsperioden sowie Point-in-Time-COT mit 52-Wochen-Normalisierung und Teilnehmer-Spreads. Daily-OHLCV reicht nicht für belastbares POC/VAH/VAL; diese Felder bleiben ausdrücklich nicht verfügbar und werden nicht approximiert.
- Eine spätere technische Research-Reserve mit Stochastic, Williams %R, CCI, zusätzlichen ROC-/MACD-/Moving-Average-Varianten, Ichimoku, Supertrend und begrenzten Candlestick-Pattern-Gruppen ist ausschließlich in `ROADMAP.md` dokumentiert. Sie gehört nicht zum ersten Broad-Research-Pass; keiner dieser Reserve-Indikatoren wurde dafür implementiert, getestet oder optimiert. Eine spätere aktive Wiedervorlage ist an eine konkret belegte Informationslücke und einen neuen Development-zuerst-Freeze-/Validierungspfad gebunden.
- Der getrennte Event-/News-/Makro-/Geopolitik-Layer ist als Research-/Shadow-Sidecar aktiv konfiguriert. Event-Schema `swing-event-pit-2026.08.23-v2`, Code-Fingerprint `627ef8ca6b7be3f7d2e932d89d2f4f1d6f21cfc41e390ed0b98a8607452f20b8`. Unterstützt sind Company, Macro, Geopolitics/Policy und Market Shock; aktuelle Speicherquelle ist ausschließlich der unveränderbare Forward-Signalsnapshot. Der Yahoo-News-Forward-Adapter ist für künftige neue Signale eingebunden, hat aber für den dokumentierten Bestand keine Alt-News abgerufen.
- Features werden vollständig fingerprintet, bevor spätere Forward-Returns, MFE/MAE, nächster handelbarer Einstieg, Gaps, R und konservative Stop-/Exit-Kontrafakten in physisch getrennten append-only Tabellen angehängt werden. Der Runner ist deterministisch, resume-fähig, nutzt bis zu acht Prozesse und schreibt SQLite ausschließlich seriell. Die feste Acht-Hypothesen-Auswertung darf nur Development sehen und zeigt zusätzlich die ungefilterte Development-Basis, verlorene Trades sowie feste RSI-, EMA- und BOS-Parameterplateaus. Validation/Holdout bleiben geschlossen; es gibt keine automatische Challenger- oder Produktionsaktivierung.
- Research-Quality-v1 ist technisch eingebunden. Ein eigener append-only Ledger dedupliziert fachlich identische Hypothesen auch bei Umbenennung, zählt Versuche derselben Familie und speichert Definition, Herkunft, Features/Parameter, Fingerprints sowie getrennte Auswertungs-/Entscheidungsereignisse. Resume zählt denselben Versuch und dieselbe Evaluation nicht doppelt. Broad-v1 und sein read-only Methodik-Audit sind abgeschlossen; keine geprüfte Hypothese erreichte C und es wurde kein Challenger freigegeben.
- Der einheitliche Qualitätsbericht umfasst Roh-/Effektivfälle, Expectancy, Profitfaktor, Trefferquote, Drawdown, Verlustserie, MFE/MAE, Entry-Effizienz, Zeit-/Regimestabilität, Placebo, Plateau, Ablation, Execution-Stress, Komplexität, Survivorship-Grenzen und „Warum könnte dieses Ergebnis falsch positiv sein?“. Effektive Evidenz nutzt konservative Komponenten über Signalstag, Issuer, wirtschaftlich identisches Instrument und vorhandene Abhängigkeits-/Korrelationscluster. Forward, Paper und Shadow können denselben Metrikvertrag nutzen, bleiben aber getrennte Evidenzarten.
- Gute Development-Durchschnittswerte allein erzeugen künftig nur einen vorläufigen B-Hinweis. `quality_review_complete` bleibt bis zur vollständigen manuellen Robustheitsprüfung falsch. Ohne diesen Nachweis kann kein C eingefroren werden. Der Qualitätslayer kann weder Parameter automatisch abstimmen noch Validation/Holdout öffnen, Features entfernen, Regeln kombinieren oder Produktion aktivieren.
- Der zusätzliche Feature-Familienvertrag gruppiert vorhandene Rohmerkmale deterministisch in Trend/Momentum, Volatilität, Struktur, Bestätigung, Marktumfeld, externe Information und Execution/Risk. Rohfeaturezahl, Anzahl je Familie, tatsächlich verschiedene Informationsfamilien, Mehrfachbelegung und semantische Redundanzkandidaten sind sichtbar. EMA-Lage, EMA-Slope und HH/HL werden dadurch nicht als drei unabhängige Bestätigungen ausgegeben. Rohfeatures bleiben unverändert; Ablation bleibt Voraussetzung einer späteren Vereinfachung.
- Der sequenzielle Ledgervertrag sperrt kombinatorische Entry×Stop×Exit-Suchen. Setup/Entry, Stop und Exit/Management sind getrennte Hypothesen und müssen nacheinander manuell eingefroren werden; erst danach darf eine einzelne feste Gesamtversion OOS geprüft werden. Die finale OOS-Stufe akzeptiert keine Variantenliste und wählt keine historisch beste Komposition automatisch.
- Die 20-Fälle-Regel ist nur noch ausdrücklich frühe Diagnose-/Anzeigegrenze. Sie kann deskriptive Trefferquoten und weitere Untersuchung erlauben, aber niemals allein Hard-Filter, C, Strategie- oder Produktionsfreigabe. CRV ≥ 2 bleibt unveränderte Long-v1-Baseline und wird nicht als bewiesenes Optimum bezeichnet; neue Forschung bewertet realisierten Expected R nach Kosten statt frei nachträglich eine CRV-Schwelle zu suchen.
- Fib bleibt Kontrollhypothese mit Kill-Regel gegen kontinuierliche Pullback-Tiefe und gleich breite Nicht-Fibonacci-Zonen. COT, Saisonalität und Opening Levels bleiben sekundär. Event/News/Makro/Geopolitik bleibt `research_only`/`shadow_only`; fehlende Daten sind kein „kein Event“.
- Historical Walk-Forward, Broad Historical, Swing Forward, Autonomous Paper, Shadow Live, User Trades und Legacy JSON sind verbindlich getrennte Evidenzarten. Ein gemeinsamer Bericht zeigt Gruppen einzeln und erzeugt keine still vermischte Gesamtstatistik.
- Alle abgeschlossenen echten Forward-Paper-Trades werden jetzt mit einem festen Pflichtfeldvertrag dokumentiert, nicht nur Verlustklassen. Der aktuelle Bestand umfasst 14 Verluste und 0 Gewinne: durchschnittlich -1,0867 R, Profitfaktor 0, Drawdown 15,2143 R, durchschnittliche MFE 0,6676 R, Median-MFE 0,6187 R und durchschnittliche MAE -1,0444 R. 8/14 erreichten mindestens 0,5 R, 4/14 mindestens 1 R, 1/14 mindestens 1,5 R und 1/14 mindestens 2 R. Zwölf Trades waren zwischenzeitlich positiv, sechs erreichten weniger als 0,5 R, drei besitzen Gap/Slippage und drei sind mögliche Stop-Kalibrierungsfälle. Die Stichprobe ist Ursachenhinweis, kein Beleg für eine Regeländerung.
- Der automatische Folgepfad wurde nach dem vollständig bestandenen 248/248-Gate ausgeführt. Broad-v1 ist über 2.520/2.520 Assets abgeschlossen; Frozen Dataset und Fingerprints blieben unverändert. Der nachgelagerte read-only Methodik-Audit öffnete weder Validation/Holdout noch Produktion.
- Das zusätzliche Gate `External Unseen Asset Universe` ist technisch als outcome-blinder append-only Freeze-Vertrag vorhanden. Es schließt ursprüngliche Ticker, Emittenten und wirtschaftlich identische Instrumente aus und bindet spätere Ergebnisse an exakt eine bereits eingefrorene Strategie-/Universe-Version. Ein reales externes Universum ist noch nicht ausgewählt oder eingefroren; es liegen dort null Ergebnisse vor.
- Der autonome Paper-Bot war in den bedienungsfreien Legacy-Swing-Hintergrundlauf eingebunden. Seine historische Infrastruktur und Evidenz bleiben append-only lesbar; seit dem Freeze erhält er aus Forward v1 keine neuen Strategie-Signale oder Paper-Zyklen. Die kleine gespeicherte Stichprobe ist nicht freigabefähig.
- Die Shadow-Live-Grundlage erzeugte aus damaligen Forward-Signalen brokerlose Orderentwürfe, übertrug sie aber niemals. Drei getrennte Entwürfe und drei append-only Execution-Missingness-Sidecars bleiben gespeichert. Seit dem Freeze entstehen aus Forward v1 keine neuen Entwürfe. Eine belastbare kostenlose automatische Read-only-Quotequelle für die konkreten Listings ist weiterhin nicht vorhanden: 0 echte Bid-/Ask-Quotes, 0 echte Trade-only-Beobachtungen, 0 Fill-/Teilfill-/Slippage-/Orderbuch-/Brokerablehnungs-Evidenzen.
- Abnahme der zeitkritischen Sidecars: 32/32 gezielte COT-/Shadow-/Background-/Architekturtests und 610/610 vollständige Regressionen erfolgreich. Python-Kompilierung, Repository-Sicherheitscheck, Swing-Preflight, Offline-Smoke und Streamlit-Start sind `ok`. Broad Research blieb beim Teststand vor 248/248 korrekt bei 0 Kandidaten gesperrt.
- Walk-Forward-, echtes Forward-, autonomes Paper-, Shadow-Live- und Nutzertrade-Evidenz besitzen getrennte Datenbanken beziehungsweise Evidenzarten und werden weder gelöscht noch rückwirkend umgedeutet.

#### Point-in-Time Event-/News-/Makro-/Geopolitik-Research

Stand 2026-08-23 nach netzwerkfreiem, kausalem Legacy-Nachzug:

| Kennzahl | Aktueller Stand |
|---|---|
| Event-Schema | `swing-event-pit-2026.08.23-v2` |
| Event-Code-Fingerprint | `627ef8ca6b7be3f7d2e932d89d2f4f1d6f21cfc41e390ed0b98a8607452f20b8` |
| Unterstützte Gruppen | Company, Macro, Geopolitics/Policy, Market Shock |
| Aktuell gespeicherte Quelle | ausschließlich unveränderbare echte Forward-Signalsnapshots |
| Gespeicherte Events | 24 generische, damals bekannte Unternehmenstermine für 20 Assets |
| Forward-Signal-Sidecars / Event-Verknüpfungen | 29 / 29 |
| Sidecars ohne belastbare Eventinformation | 5 von 29; ausdrücklich nicht als „kein Event“ interpretiert |
| Historische Eventdaten | 0; historische Coverage unvollständig |
| Expectations / Surprise | 0 / 0; keine Konsenswerte rekonstruiert |
| Marktreaktionslabels | 0; getrennte Tabelle vorbereitet |
| Company-Abdeckung | 24 generische bekannte Termine; 0 belegte Earnings-/Guidance-/Studien-/Zulassungsarten |
| Macro / Geopolitics / Market Shock | jeweils 0 gespeicherte Events; nur Vertrag und Adapter vorbereitet |
| Forward-Sammlung | für Legacy Forward v1 eingefroren; keine neuen Sidecars aus dieser Version |
| Produktionswirkung | keine; kein Score, Gate, Signal, Stop, Ziel, Größe, Short oder Brokerpfad geändert |

Der Nachzug las `runtime/swing_forward.sqlite3` ausschließlich read-only. Für alle 29 vorhandenen Signale wurde ein unveränderbarer Event-Sidecar erzeugt. Nur die bereits im damaligen Signalsnapshot vorhandene Tatsache eines bekannten Unternehmenstermins wurde übernommen; Terminart, Veröffentlichungszeit, Erwartung, Richtung und Wirkung bleiben nicht verfügbar. Es wurden keine heutigen Nachrichten auf alte Signale zurückdatiert.

Unter den 14 abgeschlossenen echten Forward-Paper-Trades besitzen elf einen solchen generischen bekannten Unternehmenstermin und drei keine belastbare Eventinformation. Das ist **keine** Aussage, dass elf Trades rund um Earnings lagen, dass der Termin den Verlust verursachte oder dass ein Filter sinnvoll wäre. In der aktuellen Stichprobe sind 0 belegte negative Company Events, 0 geopolitische Kontexte, 0 Market-Shock-Kontexte und 0 positive Surprises vorhanden.

Der vorhandene Sidecar-Code könnte bei einer später regulär freigegebenen neuen Forward-Generation wieder genutzt werden. Für Legacy Forward v1 ist dieser Weg eingefroren und wird nicht aufgerufen. Die PIT-Regel bleibt unverändert: Yahoo-Ticker-News wären nur als sekundäre Aggregatorquelle und nur mit einem tatsächlichen `first_seen_at` vor dem jeweiligen Event-Cutoff zulässig; später gesehene Artikel dürfen niemals zurückdatiert werden.

#### Future-only Kampagnenhärtung aus der 248/248-Forensik

Stand 2026-08-23: `swing_campaign_forensic_hardening.py` ergänzt ausschließlich Verträge und append-only Speicher für neue Kampagnenversionen. Es wird weder vom unveränderten Legacy-Walk-Forward-Runner noch vom laufenden Broad-Epoch importiert.

- Kampagne v1 bleibt unveränderliche historische Referenz; Frozen-Dataset-Fingerprint `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`, Queue, Cases, Resultate, Strategy-Freezes, historische A/B/C-Ergebnisse und Long-v1 sind unverändert.
- `long_v1_pullback_only` ist wegen des Setup-ID-/Anzeigenamen-Mismatch methodisch ungültig; null Fälle sind keine negative Pullback-Evidenz. Breakout-/Long-v1 bleiben negative historische Evidenz. RSI-/EMA+RSI-Befunde sind nur neutrale Hypothesenhinweise nach dem Broad-Pass.
- Künftige Research-, Scanner-, Campaign-, Freeze- und Reportingverträge selektieren nur exakte kanonische Setup-IDs; Anzeigenamen sind reine Darstellung und Substring-Selektion ist gesperrt.
- Ein outcome-blinder kompakter Candidate-/Reject-Funnel, ein echter Cutoff-basierter `recent_incremental`-Vertrag und eine append-only Retry-/Completion-Provenienz sind vorbereitet. Backfill, initiale Basis, neue Incremental- und echte Forward-Evidenz bleiben getrennt; Retries können Dataset, Sample, Completion oder Resultat nicht still wechseln beziehungsweise doppelt zählen.
- A/B/C-v2.1, seine Effective-N-/Underpowered-Gates und der vollständige Development-/Validation-/Holdout-/External-/Forward-Pfad wurden nicht neu gebaut oder verändert. Der erste Broad-Pass erhielt weder neue Features, Kandidatendefinitionen, Hypothesen noch einen Neustart.

#### Konkreter echter Swing-Forward-Status

Stand: 2026-08-22. Rein lesend aus append-only Forward-Ereignissen und dem unveränderten Frozen-Datensatz abgeleitet. `n/v` bedeutet nicht verfügbar. Die Sitzungszahlen sind Untergrenzen aus tatsächlich gespeicherten Beobachtungstagen, kein erfundener Börsenkalender. Spätere Kursfenster und alternative Stops sind ausschließlich Counterfactuals/Diagnose, keine echten Forward-Ergebnisse; eine Intrabar-Reihenfolge wird nicht erfunden.

| Kennzahl | Wert |
|---|---:|
| Abgeschlossene Trades | 14 |
| Gewinne / Verluste / Null | 0 / 14 / 0 |
| Ø R / Profit Factor / Max Drawdown | -1,09 R / 0,00 / 15,21 R |
| Ø MFE / Median MFE / Ø MAE | 0,67 R / 0,62 R / -1,04 R |
| MFE mindestens 0,5 R / 1 R / 1,5 R / 2 R | 8 (57,14 %) / 4 (28,57 %) / 1 (7,14 %) / 1 (7,14 %) |
| Vor Stop zeitweise positiv / fast ohne Bewegung (<0,5 R) ausgestoppt | 12 / 6 |
| Gap-/Slippage-Fälle / mögliche Stop-Kalibrierung | 3 / 3 |
| Ursachen A–G | A=4, B=4, D=3, F=3; C/E/G=0 |

Deskriptive Gruppen; erst ab 20 Fällen je Gruppe als interpretierbar markiert:

| Dimension | Gruppe | Fälle | Gewinne/Verluste | Ø R | PF | Ø MFE / MAE | belastbar |
|---|---|---:|---:|---:|---:|---:|---|
| Setup | Breakout | 14 | 0/14 | -1,09 | 0,00 | 0,67 / -1,04 | nein |
| Marktphase | Bullenmarkt | 14 | 0/14 | -1,09 | 0,00 | 0,67 / -1,04 | nein |
| Volatilität | unbekannt | 9 | 0/9 | -1,08 | 0,00 | 0,72 / -1,03 | nein |
| Volatilität | ruhig | 4 | 0/4 | -1,11 | 0,00 | 0,72 / -1,07 | nein |
| Volatilität | normal | 1 | 0/1 | -1,06 | 0,00 | 0,00 / -1,10 | nein |

Trade-Kerndaten:

| Ticker | Setup | Entry | Stop | Stop % / ATR | Ergebnis R | MFE R / % | MAE R / % | Max. Gewinn R | ≥0,5/1/1,5/2 R | Sitzungen MFE / Exit | Gap | schlechter als Stop; Abweichung R/% | Klasse |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|---|
| EWL | Breakout | 64,39 | 63,67 | 1,12 % / 0,93 | -1,09 | 0,33 / 0,36 % | -1,02 / -1,14 % | 0,33 | nein/nein/nein/nein | 3 / 3 | ja | ja; -0,02 R/-0,03 % | D |
| BANR | Breakout | 72,83 | 71,90 | 1,27 % / 0,60 | -1,07 | 2,17 / 2,77 % | -1,01 / -1,28 % | 2,17 | ja/ja/ja/ja | 5 / 7 | nein | nein; 0,00 R/0,00 % | B |
| ASB | Breakout | 32,16 | 31,68 | 1,49 % / 0,84 | -1,06 | 0,63 / 0,94 % | -1,07 / -1,60 % | 0,63 | ja/nein/nein/nein | 2 / 5 | nein | nein; 0,00 R/0,00 % | F |
| UMBF | Breakout | 150,89 | 148,35 | 1,68 % / 0,77 | -1,05 | 0,96 / 1,61 % | -1,04 / -1,75 % | 0,96 | ja/nein/nein/nein | 3 / 5 | nein | nein; 0,00 R/0,00 % | F |
| HOPE | Breakout | 14,46 | 14,34 | 0,88 % / 0,47 | -1,10 | 1,02 / 0,91 % | -1,00 / -0,89 % | 1,02 | ja/ja/nein/nein | 1 / 3 | nein | nein; 0,00 R/0,00 % | B |
| BATRK | Breakout | 53,21 | 52,44 | 1,44 % / 0,58 | -1,06 | 1,04 / 1,49 % | -1,03 / -1,48 % | 1,04 | ja/ja/nein/nein | 1 / 3 | nein | nein; 0,00 R/0,00 % | B |
| IJH | Breakout | 78,60 | 77,72 | 1,13 % / 1,03 | -1,06 | 0,04 / 0,05 % | -1,02 / -1,15 % | 0,04 | nein/nein/nein/nein | 1 / 2 | nein | nein; 0,00 R/0,00 % | A |
| LLYVA | Breakout | 104,25 | 103,05 | 1,15 % / 0,40 | -1,11 | 0,00 / 0,00 % | -1,03 / -1,18 % | 0,00 | nein/nein/nein/nein | 1 / 1 | ja | ja; -0,03 R/-0,03 % | D |
| LYV | Breakout | 186,93 | 185,58 | 0,72 % / 0,27 | -1,12 | 0,26 / 0,19 % | -1,00 / -0,72 % | 0,26 | nein/nein/nein/nein | 1 / 1 | nein | nein; 0,00 R/0,00 % | A |
| LT.NS | Breakout | 4061,45 | 4039,20 | 0,55 % / 0,35 | -1,16 | 1,06 / 0,58 % | -1,19 / -0,65 % | 1,06 | ja/ja/nein/nein | 1 / 2 | nein | nein; 0,00 R/0,00 % | B |
| LLYVK | Breakout | 108,51 | 106,94 | 1,44 % / 0,52 | -1,06 | 0,00 / 0,00 % | -1,10 / -1,58 % | 0,00 | nein/nein/nein/nein | 1 / 1 | nein | nein; 0,00 R/0,00 % | A |
| EWBC | Breakout | 136,25 | 134,99 | 0,93 % / 0,61 | -1,14 | 0,96 / 0,89 % | -1,04 / -0,97 % | 0,96 | ja/nein/nein/nein | 1 / 2 | ja | ja; -0,04 R/-0,04 % | D |
| SREN.SW | Breakout | 140,58 | 138,40 | 1,55 % / 0,85 | -1,06 | 0,61 / 0,94 % | -1,05 / -1,62 % | 0,61 | ja/nein/nein/nein | 2 / 3 | nein | nein; 0,00 R/0,00 % | F |
| BBT | Breakout | 32,61 | 32,19 | 1,27 % / n/v | -1,07 | 0,27 / 0,34 % | -1,01 / -1,29 % | 0,27 | nein/nein/nein/nein | 2 / 2 | nein | nein; 0,00 R/0,00 % | A |

Signalkontext und maschinell erzeugte sachliche Ursache:

| Ticker | RSI14 | EMA20/EMA50 | Kurs zu EMA20/50 | Käufer | BOS/Struktur | Marktphase | Volatilität | Klasse und Begründung |
|---|---:|---|---|---|---|---|---|---|
| EWL | 61,39 | EMA20 über EMA50 | über/über | ja | BOS ja; HH/LL | Bullenmarkt | unbekannt | D: Gap-Stop; Ausführung -0,02 R/-0,03 % schlechter als Stop, Ergebnis -1,09 R. |
| BANR | 66,77 | EMA20 über EMA50 | über/über | ja | BOS ja; HH/HL | Bullenmarkt | unbekannt | B: 2,17 R MFE, danach -1,07 R in sieben beobachteten Sitzungen; Intrabar-Reihenfolge offen. |
| ASB | 64,47 | EMA20 über EMA50 | über/über | ja | BOS ja; HH/HL | Bullenmarkt | unbekannt | F: Stop 0,84 ATR; 0,63 R MFE; Pullback-Low-, Puffer- und ATR-Stop hielten bis zum Originalende. |
| UMBF | 64,22 | EMA20 über EMA50 | über/über | ja | BOS ja; HH/LL | Bullenmarkt | unbekannt | F: Stop 0,77 ATR; 0,96 R MFE; Pullback-Low-, Puffer- und ATR-Stop hielten bis zum Originalende. |
| HOPE | 69,69 | EMA20 über EMA50 | über/über | ja | BOS ja; HH/HL | Bullenmarkt | unbekannt | B: 1,02 R MFE, danach -1,10 R in drei beobachteten Sitzungen; Intrabar-Reihenfolge offen. |
| BATRK | 61,89 | EMA20 über EMA50 | über/über | ja | BOS ja; HH/LL | Bullenmarkt | unbekannt | B: 1,04 R MFE, danach -1,06 R in drei beobachteten Sitzungen; Intrabar-Reihenfolge offen. |
| IJH | 66,62 | EMA20 über EMA50 | über/über | ja | BOS ja; HH/LL | Bullenmarkt | unbekannt | A: Nur 0,04 R MFE; danach -1,06 R in zwei beobachteten Sitzungen. |
| LLYVA | 62,96 | EMA20 über EMA50 | über/über | ja | BOS ja; HH/HL | Bullenmarkt | unbekannt | D: Gap-Stop; Ausführung -0,03 R/-0,03 % schlechter als Stop, Ergebnis -1,11 R. |
| LYV | 61,84 | EMA20 über EMA50 | über/über | ja | BOS ja; LH/HL | Bullenmarkt | unbekannt | A: Nur 0,26 R MFE; danach -1,12 R in einer beobachteten Sitzung. |
| LT.NS | 61,37 | EMA20 über EMA50 | über/über | ja | BOS ja; HH/LL | Bullenmarkt | ruhig | B: 1,06 R MFE, danach -1,16 R in zwei beobachteten Sitzungen; Intrabar-Reihenfolge offen. |
| LLYVK | 63,43 | EMA20 über EMA50 | über/über | ja | BOS ja; HH/HL | Bullenmarkt | normal | A: 0,00 R MFE; danach -1,06 R in einer beobachteten Sitzung. |
| EWBC | 67,44 | EMA20 über EMA50 | über/über | ja | BOS ja; HH/HL | Bullenmarkt | ruhig | D: Gap-Stop; Ausführung -0,04 R/-0,04 % schlechter als Stop, Ergebnis -1,14 R. |
| SREN.SW | 66,72 | EMA20 über EMA50 | über/über | ja | BOS ja; HH/HL | Bullenmarkt | ruhig | F: Stop 0,85 ATR; 0,61 R MFE; ATR-Puffer- und ATR-Stop hielten bis zum Originalende. |
| BBT | n/v | n/v | n/v/n/v | n/v | n/v | Bullenmarkt | ruhig | A: Nur 0,27 R MFE; danach -1,07 R in zwei beobachteten Sitzungen. |

5-/20-Sitzungs-Diagnose nach dem Stop, ausschließlich Counterfactual:

| Ticker | 5 Sitzungen: Erholung/Ziele/alternative Stops/Ergebnis | 20 Sitzungen: Erholung/Ziele/alternative Stops/Ergebnis |
|---|---|---|
| EWL | n/v | n/v |
| BANR | n/v | n/v |
| ASB | n/v | n/v |
| UMBF | n/v | n/v |
| HOPE | n/v | n/v |
| BATRK | n/v | n/v |
| IJH | n/v | n/v |
| LLYVA | n/v | n/v |
| LYV | n/v | n/v |
| LT.NS | n/v | n/v |
| LLYVK | n/v | n/v |
| EWBC | n/v | n/v |
| SREN.SW | n/v | n/v |
| BBT | n/v | n/v |

Der Diagnose-Runner füllt diese beiden Spalten automatisch, sobald jeweils fünf beziehungsweise zwanzig abgeschlossene Sitzungen aus einem append-only Kontrollereignis oder dem unveränderten Frozen-Datensatz vollständig verfügbar sind. Dann werden maximale Erholung in Prozent und relativ zum ursprünglichen Risiko, Ziel-1-/Ziel-2-Berührung, Haltbarkeit von Pullback-Low-, Pullback-Low-plus-ATR-Puffer- und ATR-Stop sowie ein konservativer Ergebnisstatus je Variante ausgegeben. Bei gleichzeitiger Stop-/Zielberührung bleibt das Ergebnis ausdrücklich unbestimmt.

Bei jedem relevanten künftigen Swing-Update ist dieser Block mit `scripts/run_swing_edge_diagnostics.py --markdown` neu aus dem Read-only-Bericht zu erzeugen. Aggregierte Klassen allein gelten nicht mehr als ausreichender PLDatei-/Work-Status.

#### Tracking, Backtesting und Lernlogik

- Eigenständiger täglicher Hintergrundprozess ohne geöffnete Streamlit-Sitzung; er verwendet die vorhandene Analyse-, Score-, Szenario- und Confidence-Pipeline.
- Kuratiertes, nicht als vollständig bezeichnetes Prognoseuniversum mit 325 Assets: 236 Aktien, 59 ETFs und 30 Kryptowährungen aus USA, Europa, Asien und weiteren Regionen; ServiceNow ist enthalten.
- Erster vollständiger planmäßiger Windows-Lauf am 2026-08-02: Start 22:30 Uhr, alle 325 Positionen verarbeitet, 322 Prognosen gespeichert, drei Assets (`SO`, `BK`, `ROG.SW`) wegen fehlender belastbarer Kursdaten isoliert fehlgeschlagen, keine Rate-Limit-Fehler, 0,92 % Fehlerquote, 1.416,73 Sekunden Laufzeit, SQLite-Integrität `ok` und reguläres Wrapper-/Task-Ende mit Rückgabecode 0.
- Zweiter vollständiger planmäßiger Windows-Lauf am 2026-08-03: alle 325 Positionen verarbeitet, 323 Prognosen gespeichert, zwei isolierte Yahoo-Symbolfehler (`BK`, `ROG.SW`), keine Rate-Limits, 0,62 % Fehlerquote, 887,17 Sekunden Laufzeit, 21,98 Assets pro Minute, Datenbankstatus/Integrität `ok` und reguläres Wrapper-Ende mit Rückgabecode 0. `SO` war diesmal erfolgreich.
- Dritter vollständiger planmäßiger Windows-Lauf am 2026-08-04: alle 325 Positionen verarbeitet und alle 325 Prognosen erfolgreich gespeichert, keine Fehler, keine Rate-Limits, 0,00 % Fehlerquote, 803,26 Sekunden Laufzeit, 24,28 Assets pro Minute, Datenbankstatus/Integrität `ok` und reguläres Wrapper-Ende mit Rückgabecode 0.
- Vierter vollständiger planmäßiger Windows-Lauf am 2026-08-05: alle 325 Positionen verarbeitet und alle 325 Prognosen erfolgreich gespeichert, keine Fehler, keine Rate-Limits, 887,47 Sekunden Laufzeit und reguläres Wrapper-Ende mit Rückgabecode 0.
- Planmäßige Läufe am 2026-08-07 und 2026-08-08: jeweils alle 325 Assets erfolgreich gespeichert, keine Fehler und keine Rate-Limits. Der Lauf vom 2026-08-08 endete nach 822,88 Sekunden regulär mit 325/325; Windows meldet Rückgabecode 0.
- Der Termin vom 2026-08-06 wurde verpasst, weil der Laptop vom 2026-08-05 um 23:58 Uhr bis 2026-08-07 um 21:26 Uhr im Modern Standby blieb. Die aktivierte Windows-Aufgabe blieb `Ready`, meldete einen verpassten Lauf und behielt den nächsten regulären Termin bei; der fehlende Forward-Snapshot wurde nicht nachträglich erfunden.
- Die zwei wiederkehrenden Yahoo-Symbolfehler sind für künftige Läufe korrigiert: Bank of New York Mellon verwendet jetzt `BNY`, Roche Zürich `ROP.SW`. Beide Ersatzsymbole lieferten beim isolierten Nachweis ungefähr 250 aktuelle Tageszeilen. Historische Läufe und Fehlereinträge bleiben unverändert erhalten.
- Der vollständige Lauf vom 2026-08-04 bestätigt beide Korrekturen im realen Batch: `BNY` und `ROP.SW` wurden jeweils beim ersten Versuch erfolgreich gespeichert.
- Die 322 erfolgreichen Prognosen besitzen je fünf spätere Horizonte und erzeugen deshalb 1.610 offene Auswertungen. Das sind keine 1.610 Assets und kein noch laufender Rechenprozess; die ersten 322 Ein-Wochen-Auswertungen werden ab 2026-08-09 fällig.
- Zum geprüften Stand am 2026-08-09 vor dem 22:30-Lauf liegen 1.945 echte Prognosen mit 9.725 Prognosezeiträumen vor. 322 Ein-Wochen-Ergebnisse sind an diesem Tag erstmals fällig; vor dem planmäßigen Lauf existiert noch keine Auswertung.
- Ein separates versioniertes Forecast-Wochenuniversum enthält 1.726 gültige, eindeutige Assets. Der feste 325er Referenzkern läuft montags; 1.401 Erweiterungen sind deterministisch auf Dienstag bis Freitag verteilt (362/354/340/345). Der Wochenbetrieb startet am 2026-08-10, während die Fälligkeitsprüfung weiterhin täglich um 22:30 Uhr läuft.
- Neue Prognosen speichern ab Schema 9 einen L0-Point-in-Time-Messvertrag mit Beobachtungs-Cutoff, Feature-, Label-, Benchmark-, Kosten- und Qualitätsregeln, Leakage-Schutz und SHA-256-Fingerabdruck. Vor jedem Tageslauf wird jeder neue Vertrag vollständig nachgerechnet; beschädigte oder unvollständige Verträge stoppen den Prozess vor Auswertung und Marktabruf. Die 1.945 älteren Datensätze wurden nicht rückwirkend ergänzt und bleiben als Legacy ohne Messvertrag sichtbar.
- Neue Prognosezeiträume speichern eine versionierte, ausdrücklich unkalibrierte Rohwahrscheinlichkeit für `tatsächliche Rendite > 0`. Sie stammt ausschließlich aus der unverändert gespeicherten Bull-/Base-/Bear-Verteilung und den zugehörigen numerischen Szenariozielen; Confidence wird nicht künstlich als Wahrscheinlichkeit interpretiert. Bis eigene Horizontmodelle existieren, gilt dieselbe Szenarioverteilung transparent für alle fünf Zeiträume.
- Für den verpassten Termin wurden getrennt 116.517 historische OHLCV-Balken für 324 Assets gerettet: 85.336 Tagesbalken bis 2026-08-05 und 31.181 Fünf-Minuten-Balken vom 2026-08-06, deren Ende nie nach 22:30 Uhr Europe/Berlin liegt. Die Recovery-Datenbank ist intakt, fingerprintet und technisch von Forward-Prognosen beziehungsweise Trefferquoten ausgeschlossen. `MATIC-USD` bleibt als einzige nicht rekonstruierbare Lücke sichtbar.
- Lokale SQLite-Datenbank für Läufe, Assets je Lauf, Prognose-Snapshots, fünf Prognosezeiträume, spätere Auswertungen und den letzten fehlgeschlagenen Auswertungsversuch je Prognosezeitraum. Gespeichert werden nur technischer Status, Fehlerart und eine begrenzte Fehlermeldung, keine Nutzerdaten.
- Snapshots enthalten unter anderem EUR-Kurs, Asset-Qualität, Kaufsignal, Marktphase, Richtung, Bull-/Base-/Bear-Szenarien, Confidence, Datenqualität, Unsicherheiten und Logikversion.
- Unterstützte automatische Auswertungszeiträume: 1 Woche, 1 Monat, 3 Monate, 6 Monate und 12 Monate.
- Neue Horizonte starten unabhängig: 1W jede Woche, 1M alle zwei Wochen, 3M monatlich, 6M alle drei Monate und 12M alle sechs Monate. 6M/12M werden nur bei ausreichender Historie, Datenqualität, Assetqualität und gültigem EUR-Preis erzeugt; bestehende Horizonte bleiben unverändert offen oder auswertbar.
- Fällige Auswertungen laden Kursdaten in begrenzten Batches und teilen historische FX-Abfragen je Währung und Bewertungstag. Gespeichert werden tatsächlicher Kurs und Bewertungstag, Rendite, beste/schlechteste Bewegung, Richtungs- und Kursbereichstreffer, Abweichung, Ziel-/Risikomarken, Datenqualität sowie Referenztreffer für `immer steigend`, `keine Änderung`, einen festen 20-Tage-Trend und einen assettyp-/regionsabhängigen Marktbenchmark; nicht fällige Zeiträume bleiben offen.
- Zentrale Erfolgsdefinition bleibt die Richtungstrefferquote. Die Qualitätsansicht zeigt zusätzlich Ergebnisabdeckung, Wilson-Unsicherheitsbereich, Precision, Recall, Balanced Accuracy, Rendite, Drawdown, Überschussrendite und den Abstand zu den Referenzen sowie getrennte Segmente nach Region, Marktphase, Datenqualität und Logikversion. Für gereifte neue Wahrscheinlichkeitsfälle werden zusätzlich Brier Score, Log Loss, Kalibrierungsfehler und Bias ausgewiesen. Fehlende oder nicht wertbare Daten zählen weder als Treffer noch als Fehler; die Rohwahrscheinlichkeit wird ausdrücklich nicht als bereits kalibrierte Erfolgszusage dargestellt.
- Prognosequalität unter `Einstellungen → Erweiterte Einblicke` mit Gesamtkennzahlen, Aufschlüsselungen nach Zeitraum, Asset-Typ und Analyseart, durchschnittlicher Abweichung, Filtern und seitenweiser Tabelle.
- Verständlicher Betriebsstatus unter `Prognosequalität` mit letztem Lauf, verarbeitetem Anteil, Fehlerzahl und nächstem Termin. Fehlende erwartete, unterbrochene und seit mehr als neun Stunden nicht fortgeschriebene Läufe werden sichtbar gewarnt.
- Beginnt ein neuer Tageslauf, werden ältere noch als `running` markierte Läufe ohne Datenlöschung automatisch als `interrupted` dokumentiert. Dadurch bleibt ein hart beendeter Prozess nicht dauerhaft fälschlich als aktiv stehen.
- Integritätsgeprüfte SQLite-Sicherung unter `runtime/backups/` ohne automatische Aufbewahrungs- oder Löschregel. Eine Wiederherstellung wird aus Sicherheitsgründen nur in eine neue Datei geschrieben und überschreibt niemals die produktive Datenbank.
- Verständlicher Prognosestatus unterscheidet: noch keine Prognosen vorhanden, Hintergrundlauf noch nicht dokumentiert, Prognosen vorhanden aber noch nicht fällig, Prognosen ausgewertet sowie fällige Auswertungen, die nach einem dokumentierten Versuch wegen fehlender verwertbarer Marktdaten nicht möglich waren. Das früheste nächste Fälligkeitsdatum wird angezeigt.
- Fortsetzbare Läufe, Tages-Deduplizierung, begrenzte Wiederholungen, kontrollierte Pausen und Fehlerisolierung pro Asset.
- Abgeschlossene Tagesläufe werden auch mit `--force` niemals überschrieben. Eine abweichende Logikversion für denselben Tag wird ausdrücklich abgelehnt, damit Versionen und erfolgreiche Assets nicht still vermischt werden.
- Betriebsmetriken je Hintergrundlauf: Gesamtdauer, Assets pro Minute, Fehlerquote, erkannte Rate-Limit-Fehler, Datenbankwachstum, Schema-Version und Integritätsstatus werden ausgegeben und im rotierenden Log festgehalten.
- Das rotierende Laufprotokoll beginnt vor dem Laden des Universums mit einer Startvorprüfung. Vor jedem Asset-Versuch werden Lauf-ID, Ticker, Position und Versuchszahl geschrieben, damit ein harter Prozessabbruch dem letzten begonnenen Asset oder der Startphase zugeordnet werden kann.
- Der äußere Windows-Wrapper führt ein zweites lokales Diagnoseprotokoll unter `runtime/logs/forecast_task_wrapper.log`. Es hält Start, reguläres Ende und den unveränderten Python-Rückgabecode fest; fehlt der Endmarker, wurde wahrscheinlich der gesamte Prozesskontext hart beendet.
- `scripts/run_forecasts.py --preflight` prüft Konfiguration, Laufparameter, Universum, Schreibpfade, SQLite-Integrität und sämtliche vorhandenen neuen Messverträge ohne Marktdatenabruf und ohne Prognosezeile. Unterstützte Schema-Migrationen können dabei nicht löschend nachgezogen werden.
- Eine exklusive Betriebssystem-Sperre auf Basis der Prognosedatenbank verhindert parallele Runner auch dann, wenn einer davon manuell und nicht über die Windows-Aufgabe gestartet wird. Sie wird beim Prozessende automatisch freigegeben und benötigt keine Löschung alter Sperrdateien.
- Sind vor einer neuen Wochenkohorte sämtliche gemeinsam geladenen Marktbenchmarks gleichzeitig nicht verfügbar, stoppt der Runner die Neuprognose vor dem ersten Asset. Es entsteht keine fälschlich abgeschlossene Kohorte; Windows-Wiederholung oder das normale Nachholen können später erneut versuchen. Einzelne Datenlücken bleiben weiterhin isoliert.
- Betriebsmetriken werden seit Datenbankschema 3 zusätzlich am Laufdatensatz gespeichert und in der Prognosequalitätsansicht angezeigt. Sie bleiben damit nach Neustarts und Logrotation verfügbar.
- Datenbankschema 4 speichert je Prognose die explizite Analyseart. Bestandsdaten werden verlustfrei als `Einstiegsanalyse` gekennzeichnet; die Qualitätsansicht fasst Analysearten getrennt zusammen und kann nach ihnen filtern. Der aktuelle Runner erzeugt ausschließlich Einstiegsanalysen, Long-Term- und Swing-Prognosemodelle sind noch nicht implementiert.
- Sobald ausgewertete Fälle mehrerer Analysearten vorliegen, wird keine gemeinsame Richtungstrefferquote angezeigt. Startseite und Qualitätsansicht verweisen dann auf die getrennten Modellwerte.
- Asset-spezifische News- und Earnings-Massenabfragen sind im täglichen Lauf bewusst deaktiviert; diese eingeschränkte Abdeckung wird im Snapshot gespeichert und nicht als positives Signal gewertet.
- Performance-Reviews von Trade-Setups nach 1 Woche, 1 Monat, 3 Monaten, 6 Monaten und 12 Monaten.
- Erfassung von Rendite, maximaler positiver/negativer Bewegung, Ziel-/Stop-Berührung, bester Alternative und Opportunitätskosten aus späteren echten Kursdaten.
- Lokale Prognosequalitätsprüfung gespeicherter Analysen mit Szenarien, Modul-Scores, Signal-Snapshots und späterer Auswertung; die technische Legacy-Bezeichnung `Forward-Test` bleibt nur in historischen Datenmodellen und erweiterten Methodikansichten erhalten.
- Optionales Decision-Tracking mit Nutzerentscheidung, Kommentar, App-Alignment, bester Alternative und Opportunitätskosten.
- Prognose-Tracking für Szenarien und spätere Treffer-/Fehlursachenanalyse.
- Historische Backtesting-Basis für Kombinationen aus Kaufsignal, RSI, MACD und CRV über 1, 3, 6 und 12 Monate.
- Lokale Speicherung ausgewählter Backtest-Ergebnisse.
- Confidence-Kontext aus ähnlichen ausgewerteten Historienfällen.
- Segmentierte Trefferquoten nach Asset-Typ, Marktphase, Zeitraum, Szenario-Lesart und Signalgruppen.
- Fehlmuster- und Kalibrierungshinweise mit Mindestdatenregeln.
- Lernlogik-Guardrails: unter 20 Fällen nur sammeln, zwischen 20 und 50 Fällen vorsichtige Hinweise, über 50 Fällen manuell prüfbare Kalibrierungsvorschläge.
- Keine automatische Änderung von Score-Gewichtungen.
- Qualitätsprüfung lokaler Lernhistorien mit Reparaturhinweisen; die Anwendung verändert oder löscht Historien nicht automatisch.
- Automatisch nach jedem Hintergrundlauf erzeugtes Kalibrierungsprofil aus echten SQLite-Auswertungen. Es segmentiert nach Analyseart, Logikversion, Asset-Typ und Zeitraum, zeigt nur manuelle Prüfhinweise und verändert weder Produktionsregeln noch Score-Gewichte.
- Das Kalibrierungsprofil enthält das Lern-Gate mit reproduzierbarem Datensatzfingerabdruck. Nur verifizierte gereifte Point-in-Time-Fälle sind berechtigt; ein erster Shadow-Forschungsbestand benötigt mindestens 1.000 Fälle, zwölf Beobachtungswochen, je 200 positive/negative Fälle und 90 % Wahrscheinlichkeitsabdeckung. Diese konservativen technischen Grenzen ersetzen keine spätere Power-Analyse und erlauben niemals automatisch eine Produktionsaktivierung.
- Zeitliche Walk-Forward-Fenster mit wachsendem Training, späterer Validierung und unangetastetem Test sind vorbereitet. Labels, die am Beginn der nächsten Stufe noch nicht bekannt waren, werden durch Purging ausgeschlossen; zufälliges Zeilenmischen ist verboten.
- Rollierende beobachtende Prognoseüberwachung mit 28-Tage-Aktuellfenster und 84-Tage-Referenzfenster. Sie vergleicht je Analyseart und Horizont Richtungstreffer, Trendregel-Vorsprung, Überschussrendite, Brier Score, Log Loss und Wahrscheinlichkeitsabdeckung und prüft zusätzlich Eingabe-/Segmentverschiebungen, Scoremittelwerte, Auswertungsrückstand, technische Fehler, Asset-Erfolgsquote, Enthaltungsquote und Rate-Limits.
- Drift wird erst ab mindestens 50 Ergebnis-/Wahrscheinlichkeitsfällen beziehungsweise 100 Eingabefällen behauptet. Kalendarisch fällige Ergebnisse besitzen drei Tage Puffer, damit Wochenenden und Feiertage keine falsche Überfälligkeitswarnung erzeugen. Das Monitoring erscheint im atomaren Kalibrierungsprofil und in der Prognosequalität, bleibt aber strikt rein beobachtend.

#### Stabilität, Datenschutz und Betrieb

- Defensive Lader für fehlende, leere, ungültige und ältere JSON-Strukturen.
- Atomare Speicherung lokaler JSON-Historien über temporäre Dateien und sicheren Dateiaustausch; bei einem Austauschfehler bleibt der alte Stand erhalten.
- Verständliche Meldungen bei Ausfällen externer Datenquellen und eingeschränkte Weiterverarbeitung verfügbarer Bereiche.
- Lokaler yfinance-Cache mit temporärem Fallback bei Schreibproblemen.
- Repository-Sicherheitscheck gegen Secrets und versehentlich versionierte private Laufzeitdateien.
- Pytest-Stabilitätstests, Streamlit-AppTest und eigenständiger Smoke-Test.
- Performance-Pfad mit parallelen unabhängigen Research-Abrufen, Wiederverwendung der langfristigen Tageshistorie für tägliche Charts sowie 30-minütigem Cache des historischen Signal-Backtests; die Bewertungslogik bleibt unverändert.
- Automatische Prognosedatenbank, WAL-Dateien, Logs und UI-Testdaten liegen unter `runtime/` und sind durch `.gitignore` ausgeschlossen.
- Optional umleitbare private Historien- und Datenbankpfade ermöglichen isolierte UI-Tests ohne Veränderung echter Nutzerhistorien.
- Rotierende lokale Hintergrundlogs ohne bewusst gespeicherte sensible Nutzerdaten.
- Benutzerbezogene Windows-Aufgabe `InvestmentAssistantDailyForecasts`, täglich 22:30 Uhr lokale Zeit, Status `Ready`, Ausführung mit eingeschränkten Rechten, Projekt-Python und korrektem Arbeitsordner.
- GitHub-Actions-Smoke-Workflow.
- Vorbereitung für Streamlit Community Cloud ohne Windows-spezifische Pfade in `app.py`.

### Aktueller Arbeitsstand nach der Konsolidierung

Der belegte Funktionsumfang umfasst weiterhin das 1.726-Asset-Prognosewochenuniversum, den entkoppelten Horizontkalender, die automatische Prognoseauswertung sowie die vorhandene 2.520-Asset-Swing-Infrastruktur mit Assetklassen-Funnel, Strategy-Freezes, Risk Engine und getrennten Forward-/Paper-/Shadow-Speichern. Die Long-v1-Baseline, ihre Scores, Gewichte und historische Evidenz wurden nicht umgedeutet. Ihr alter automatischer Strategy-Forward ist jedoch eingefroren und erzeugt keine neuen Signale oder Trades.

Verbindliche nächste Reihenfolge seit 2026-08-28:

1. **Konsolidierung vollständig abnehmen.** Git, Dokumentation, Buyer-Terminalstatus, Legacy-Freeze und Schutz der historischen Artefakte müssen nachweislich stimmen.
2. **Multi-Asset Opportunity Discovery separat freigeben.** Erst nach `READY_FOR_MULTI_ASSET_DISCOVERY`; noch kein Forward und keine Vorwegnahme einer Strategie.
3. **Bestehende Prognosedaten weiter erhalten.** Fälligkeitsauswertung und Wochenbetrieb dürfen weiterlaufen, verändern aber keine Swing-Strategie.

Prioritätsblock 1 – nächste Validierungs- und Ausbauschritte:

- Broad-v1 als unveränderliche Research-Referenz bewahren. Neue Fragestellungen nur als getrennte, versionierte Experimente bearbeiten; keine Freigabe oder Öffnung von Validation/Holdout, solange kein belastbarer vorab eingefrorener C-Kandidat existiert.
- Paper-/Shadow-Infrastruktur und vorhandene Evidenz erhalten, aber nicht mehr mit Legacy Forward v1 füttern. Neue Evidenz darf erst zu einer später regulär bestandenen festen Strategieversion gehören.
- **Trade-Republic-Ausrichtung technisch umgesetzt:** Der normale Swing-Bereich enthält nur dauerhaft listing-spezifisch als `TR handelbar` markierte Instrumente. `TR nicht handelbar` und `unbekannt` bleiben unverändert im Paper-/Forward-Bestand und werden getrennt angezeigt. Scannerqualität gesamt, TR-handelbare Listings und aktuell vollständig ausführbare TR-Pläne besitzen getrennte Zähler und Ergebnisgruppen.
- **TR-Kurssicherheit technisch umgesetzt, manuelle Pflege erforderlich:** Analyse- und TR-Listing werden über Ticker, Börsenplatz, Währung und gleiche ISIN verknüpft. Eine append-only lokale Markierung erlaubt die dauerhafte manuelle Ergänzung fehlender ISIN-Daten. `Aktueller Preis`, Limit, Maximalpreis, Stop, Ziele, Stückzahl und EUR-Beträge werden nur für dieses TR-Listing gezeigt, wenn ein höchstens 15 Minuten alter manuell erfasster TR-Preis und ein zeitgleich erfasster Vergleichskurs des analysierten Listings vorhanden sind; sonst steht `TR-Preis nicht verfügbar` beziehungsweise kein ausführbarer Plan. Der Quotient bildet nur die Listing-Basis und verankert alte technische Marken nicht neu. Yahoo bleibt Chart-/Analyse-/Forward-Quelle und wird nie als TR-Preis ausgegeben.
- **Weiter real zu validieren:** Den Listing-Bestand schrittweise verifizieren und anschließend Scannerqualität gesamt gegen echte Ergebnisse der tatsächlich TR-ausführbaren Teilmenge vergleichen. Es gibt keine automatische TR-Erkennung, Broker-Verbindung, Quote oder Orderausführung.
- Bereits gespeicherte EWL-/LT.NS- und weitere Long-v1-Fälle bleiben append-only lesbar und dürfen anhand ihrer bereits vorgesehenen späteren Ereignisse ausgewertet werden; daraus entsteht keine neue Signalerzeugung.
- Die neutralisierte v3-Pipeline nicht weiter automatisch scannen lassen. Ihre bisherigen Kennzahlen bleiben historische Legacy-Evidenz und dürfen keiner künftigen Strategie zugerechnet werden.
- Den ab 2026-08-10 konfigurierten Wochenbetrieb real über mehrere vollständige Wochen validieren: 325er Montagskern und vier Erweiterungskohorten des 1.726-Asset-Universums, Nachholen innerhalb derselben Woche, Laufzeit, Soll-/Ist-Abdeckung, dauerhaft fehlerhafte Ticker und Rate-Limits beobachten.
- Wiederanlauf, verpasste Termine, Datenbankwachstum, Auswertungsrückstand und Yahoo-Finance-Schonung über mehrere Wochen messen. Ein fehlender Forward-Snapshot bleibt eine sichtbare Lücke.
- Die technische Lernbasis aus Point-in-Time-Datenvertrag, fachlich getrennten Ergebnislabels, Referenzmetriken, purged Walk-Forward-Aufteilung, Rohwahrscheinlichkeiten, Shadow-Modellregister, manuellen Freigabegates, Canary, Rollback und rollierender Driftüberwachung mit echten gereiften Fällen füllen.
- Analyse- und Vorhersagequalität getrennt nach Analyseart, Horizont, Asset-Typ, Region, Marktphase, Datenqualität und Modellversion bewerten. Trefferquote allein reicht nicht; Kalibrierung, Brier Score oder Log Loss, Abdeckung/Enthaltung, Rendite, Drawdown, Benchmarkvorsprung und Opportunitätskosten gehören dazu.
- Kalibrierte produktive Wahrscheinlichkeiten, echte Challenger-Modelle und belastbare Driftvergleiche erst nach mehrwöchigen bis mehrmonatigen ungesehenen Daten prüfen. Bis dahin bleiben alle Lernhinweise rein beobachtend und verändern keine Produktionsregel automatisch.

Prioritätsblock 2 – direkt anschließend:

- Den entkoppelten Horizontkalender im realen Wochenbetrieb abnehmen und die tatsächliche Zahl neu gestarteter 1W-/1M-/3M-/6M-/12M-Zeiträume dokumentieren.
- Den 1.726-Asset-Wochenbetrieb, fällige Ergebnisse, Datenbankwachstum, Fehler und Rate-Limits über mehrere vollständige Wochen messen.
- Bestehende Prognosen niemals löschen oder rückwirkend umdeuten; keine Broker-Anbindung und keine automatische Orderausführung.

Erst danach:

- Professionelle Research- und Long-Term-Module mit weiteren belastbaren Quellen verbinden.
- Die umgesetzte Drei-Bereichs-Navigation und die ersten Design-Tokens app-weit weiter konsolidieren.
- `Investment Opportunities`, Tracking-/Backtesting-Komfort sowie allgemeine Architektur-, Modularisierungs-, Performance- und Dokumentationsarbeit weiterführen.
- Den ersten GitHub-Actions-Lauf des vorhandenen Smoke-Workflows nach ausdrücklich erlaubtem Commit und Push auswerten; bis dahin bleibt diese Aufgabe nachgeordnet blockiert.

### Noch nicht umgesetzt

- Freigabe eines technischen Challengers aus Broad-v1. Der Broad-v1-Datensatz und der read-only Methodik-Audit sind vollständig, aber keine Hypothese erreichte C; Validation und Holdout blieben geschlossen. Daher wurde kein Challenger erzeugt oder aktiviert.
- Reales `External Unseen Asset Universe`. Auswahl-/Freeze-/Ergebnisvertrag sind vorhanden, aber noch kein zusätzliches Universum wurde vor Ergebnissichtung zusammengestellt, eingefroren oder getestet.
- Gereifte autonome Paper-Bot- und Shadow-Live-Evidenz über ausreichend viele aktuelle Trades, Marktphasen, Spreads, Slippage, Gaps und reale Ausführbarkeit. Fehlende echte Mikrostrukturdaten werden nicht geschätzt.
- Echtgeld-Gate, Brokeradapter, reale Orderübermittlung, Live-Bot und kontrollierte Echtgeldskalierung. Diese Stufen bleiben technisch und fachlich gesperrt.
- Automatisch verlässliche, offizielle listing-spezifische TR-Handelbarkeits- und Preiserkennung ohne Broker-/Orderanbindung. Bis eine belastbare Quelle fachlich und rechtlich geprüft ist, bleibt der sichere Standard `unbekannt` und der TR-Preis eine kurzlebige manuelle Eingabe; Yahoo darf diese Lücke nicht füllen.
- Vollständige fachliche und optische Ausgestaltung der neuen Drei-Bereichs-Navigation; die sichere Navigationsbasis und UI-Umbenennung in `Swing Trade Finder` sind umgesetzt, die sichtbare Desktop-/Mobilprüfung dieses Stands ist noch offen.
- Vollständige eigenständige quellenbasierte Long-Term-Analyse für drei bis sieben Jahre. Quellenvertrag, Cache, isolierte Bewertungs-/Szenariorechnung, inaktive SEC-Filing-Discovery und eine streng begrenzte XBRL-Finanzfakten-Evidenz sind vorhanden; automatische sichere Beschaffung, weitere Geschäftsmodell-/Risiko-Ableitung, unabhängige Markt-/Wettbewerbsquellen, vollständige Faktorableitung, Ergebnistext, separater Einstiegsplan und UI-Auswahl fehlen noch.
- Eigener Bereich `Investment Opportunities` mit getrennten Scores, hochwertigem Feed, Investment-Watchlist und sicheren Übergaben in die beiden Analysearten.
- Mehrtägiger Realnachweis aller vier regionalen Swing-Hintergrundaufgaben über mehrere Marktphasen. Mindestens eine reale Ausführung aller vier Bereiche ist belegt; eine ausreichend lange Betriebs- und Ergebnisserie steht noch aus.
- Short-/Absicherungs-, Mean-Reversion- und weitere Setup-Typen; Version 1 ist bewusst auf Long-Pullbacks und bestätigte Long-Ausbrüche begrenzt.
- Mehrwöchiger Realnachweis der umgesetzten 1.726-Asset-Wochenrotation. Die technische Zuordnung und Konfiguration sind vorhanden; vor mehreren tatsächlich abgeschlossenen Wochen ist die betriebliche Zuverlässigkeit noch nicht belegt.
- Umfassende externe Krypto-Spezialdaten wie Fear & Greed, ETF-Flows, On-Chain-Daten, Orderbuch, Spread, Börsentiefe und Stablecoin-Liquidität. Ohne belastbare Quelle zeigt die Anwendung diese Daten bewusst als nicht verfügbar.
- Direkte belastbare Liquiditäts-, Flow- und vollständige institutionelle Datenquellen außerhalb der über Yahoo Finance verfügbaren Felder und Proxies.
- Vollständige historische Peer- und Bewertungsdaten, wenn Yahoo Finance sie nicht bereitstellt.
- Echtes trainierendes Prognose- und Empfehlungssystem mit eigenen Horizontmodellen, Trainingspipeline, tatsächlich laufenden Shadow-Challengern, Out-of-Sample-Nachweis, Wahrscheinlichkeitskalibrierung und hartem Out-of-Distribution-Enthaltungsgate. Point-in-Time-Datensatz, Referenzmodelle, purged Walk-Forward-Aufteilung, Modellregister, Canary-/Rollback-Gates und die rein beobachtende Driftbasis sind technisch vorbereitet; automatische Score- oder Modelländerungen bleiben in Version 1 bewusst ausgeschlossen.
- Persistente Cloud-Datenhaltung für private Such-, Trade-, Entscheidungs-, Prognose- und Backtest-Historien.
- Modularisierung der monolithischen `app.py` in getrennte fachliche und technische Komponenten.
- Multi-Factor Opportunity Ranking, integrierte Swing-Thesis-Engine, vollständiger Entry-/Tranchenplaner, fortlaufende Kontextüberwachung und validierte dynamische Swing-Exit-Engine des langfristigen Produktziels.
- Broker-Anbindung, Orderausführung und automatische Käufe oder Verkäufe sind aktuell strikt gesperrt. Eine separate Live-Bot-Phase wäre erst nach vollständiger Validierung und ausdrücklich bestandenem Echtgeld-Gate zulässig.

## 4. Daten und Architektur

### Datenquellen

Die zentrale derzeit produktiv genutzte externe Schnittstelle ist `yfinance` beziehungsweise Yahoo Finance. Genutzt werden:

- Asset-Suche.
- Historische und aktuelle Kursdaten.
- Ticker-Stammdaten und verfügbare Fundamentalfelder.
- Wechselkursdaten.
- Yahoo-News.
- Earnings-Termine.
- Verfügbare Analysten- und institutionelle Felder.
- Markt-, Makro- und Rohstoff-Proxies über Yahoo-Finance-Ticker.

Für die geplante Long-Term-Analyse sind zusätzlich noch nicht aktivierte SEC-EDGAR-Adapter vorhanden. Sie können offizielle US-Jahres-/Quartalsberichte anhand Ticker/CIK entdecken und sechs aktuelle US-GAAP-Jahreswerte aus der öffentlichen Company-Facts-API strukturiert lesen. Nur ein Wert mit exakt passender offizieller Filing-Accession darf Evidenz werden. Im normalen App- oder Hintergrundpfad finden noch keine automatischen SEC-Netzabrufe statt; Geschäftsmodell-, Wettbewerbs- oder Risikoaussagen werden nicht aus Dokumenttext erfunden.

Es existieren keine Broker-, Order- oder Depot-APIs. Zusätzliche belastbare Quellen für On-Chain-Daten, ETF-Flows, Fear & Greed, Orderbuch oder vollständige Liquiditätsdaten sind derzeit nicht eingebunden.

### Gespeicherte Daten

Manuelle Nutzerhistorien bleiben in den vorhandenen lokalen JSON-Dateien. Die automatische tägliche Prognoseerfassung verwendet getrennt davon SQLite; das kuratierte Universum liegt versioniert als CSV vor. Vorhandene JSON-Historien wurden nicht migriert, verändert oder gelöscht.

| Datei | Inhalt und Status |
| --- | --- |
| `portfolio.json` | Optionale, versionierbare Portfolio-Minimalstruktur mit `cash`, `ticker`, `asset_type`, `shares` und `buy_price`. Keine Zugangsdaten oder persönlichen Identifikationsdaten. |
| `search_history.json` | Lokale erfolgreiche Suchen; durch `.gitignore` ausgeschlossen. |
| `trade_history.json` | Lokale Scanner-/Trading-Setups und spätere Performance-Reviews; durch `.gitignore` ausgeschlossen. |
| `forward_tests.json` | Lokal gespeicherte Analysen und spätere Forward-Auswertungen; durch `.gitignore` ausgeschlossen. |
| `decision_history.json` | Lokale Nutzerentscheidungen und spätere Ergebnisvergleiche; durch `.gitignore` ausgeschlossen. |
| `prediction_history.json` | Lokale Szenarien, Prognosen und spätere Reviews; durch `.gitignore` ausgeschlossen. |
| `backtest_history.json` | Lokal gespeicherte Backtest-Zusammenfassungen; durch `.gitignore` ausgeschlossen. |
| `.yfinance-cache/` | Lokaler yfinance-Cache; durch `.gitignore` ausgeschlossen. |
| `config/forecast_universe.csv` | Versionierte kuratierte Auswahl mit 325 Assets und strukturierten Feldern für Ticker, Asset-Typ, Name, Region, Kategorie und Versionsstand. |
| `runtime/forecasts.sqlite3` | Private automatische Prognosen, Prognosezeiträume, Auswertungen und Laufstatus; samt WAL-/SHM-Dateien durch `runtime/` in `.gitignore` geschützt. |
| `runtime/swing_walk_forward.sqlite3` | Strikt getrennte append-only historische Swing-Forschung mit Läufen, Fällen, Ergebnisrevisionen, Identitätskonflikten und beobachtenden Merkmalen; nicht als echter Forward-Test oder Produktionsfreigabe verwendbar. |
| `runtime/swing_strategy_freezes.sqlite3` und `runtime/strategy_freezes/` | Append-only Register und unveränderbare JSON-Artefakte der Baseline-/Challenger-Freezes; lokale Laufzeitdaten, durch `.gitignore` geschützt. |
| `runtime/swing_paper_bot.sqlite3` | Eigene append-only autonome Paper-Bot-Zyklen, Signale und Ereignisse; strikt getrennt von Walk-Forward, echtem Forward, Shadow und Nutzertrades. |
| `runtime/swing_shadow_live.sqlite3` | Eigene append-only Shadow-Orderentwürfe und ausschließlich echte Beobachtungen ohne Brokerorder oder geschätzte Mikrostrukturdaten. |
| `runtime/logs/forecast_runner.log` | Rotierendes lokales Lauf- und Fehlerprotokoll des Hintergrundprozesses; durch `.gitignore` ausgeschlossen. |

Die konkreten Inhalte lokaler Nutzer- und Historiendateien sind nicht Bestandteil dieser Projektdokumentation.

### Bewertungslogik

Die zentrale Architekturregel ist die Trennung von drei Bewertungen:

1. **Asset-Qualität:** langfristige Qualität, asset-spezifische Fundamentaldaten und Stabilität.
2. **Kaufsignal:** aktueller Einstiegszeitpunkt aus Technik, CRV, Marktphase und begrenzten Signal-Anpassungen.
3. **Depot-Effekt:** ausschließlich Portfoliowirkung, Cash-Reserve und Konzentrationsrisiko.

Die nutzerseitige Empfehlung trennt davon drei verständliche Entscheidungsebenen:

1. **Langfristige Attraktivität:** Qualität, Wachstum beziehungsweise Adoption, Zukunftspotenzial und langfristige Risiken.
2. **Preisattraktivität:** heutiger Preis im Verhältnis zu Bewertung, erwarteter Rendite, maximal verfügbarer Kurshistorie und aktueller Plausibilität der These.
3. **Kurzfristiges Timing:** Trend, Bodenbildung, Unterstützungen, Widerstände, Momentum und CRV.

Erst die Synthese dieser drei Ebenen erzeugt die Handlungskategorie und den gemeinsamen Kaufplan. Der separate Depot-Effekt kann die Positionsentscheidung begrenzen, verändert aber weder Asset-Qualität noch Kaufsignal.

Das Kaufsignal verwendet den Technik-Score mit 70 Prozent, den CRV-Score mit 20 Prozent und anschließend begrenzte Zu- oder Abschläge für Marktphase, RSI, MACD und asset-typische Volatilität. Asset-Qualität und Depot-Effekt fließen nicht in dieses Timing-Signal ein.

Der Research-Kontext nutzt je Asset-Typ unterschiedliche Gewichte:

- Aktie: Technik 30 %, Fundamentaldaten 30 %, Makro 20 %, News 10 %, CRV 10 %.
- ETF: Technik 25 %, Fundamentaldaten 25 %, Makro 25 %, News 10 %, CRV 15 %.
- Krypto: Technik 40 %, Fundamentaldaten/Krypto-Adoption 5 %, Makro 25 %, News 15 %, CRV 15 %.
- Unbekannt: Technik 45 %, Fundamentaldaten 5 %, Makro 25 %, News 10 %, CRV 15 %.

Fehlende Daten werden neutral oder als `Daten nicht verfügbar` behandelt. Sie dürfen nicht erfunden oder als sichere Fakten dargestellt werden. Historische Trefferquoten und Kalibrierungskontexte verändern Scores nicht automatisch.

### Analyse-Struktur

Der aktuelle Ablauf ist:

1. Asset zentral suchen und einen Vorschlag auswählen; letzte erfolgreiche Assets werden in derselben Vorschlagsliste priorisiert.
2. Langfristige Tageshistorie laden und für tägliche Chartintervalle passend zuschneiden; nur andere Intervalle benötigen einen separaten Chartabruf.
3. Asset identifizieren und Asset-Typ automatisch bestimmen; nur bei Unsicherheit oder unter erweiterten Einstellungen manuell korrigieren.
4. Unabhängige Stamm-, Makro-, News-, Rohstoff- und Earnings-Daten parallel laden.
5. Indikatoren, Marktphase, Unterstützungen, Widerstände und CRV berechnen.
6. Asset-Qualität, Kaufsignal und optionalen Depot-Effekt getrennt berechnen.
7. Research-, Datenqualitäts-, Szenario-, Risiko- und Confidence-Module aufbauen und daraus zentral eine Handlungsempfehlung mit getrennten Langfrist-, Preis- und Timing-Sichten sowie einem gemeinsamen Mehrpfad-Plan synthetisieren, ohne Einzel-Scores zu verändern.
8. Als Ebene 1 ausschließlich den kompakten Ergebniskopf, die drei Bewertungen, maximal drei Gründe, maximal zwei Risiken sowie relative Tranchen für jetzt, Rücksetzer und weitere Stärke mit Kaufzonen, Widerlegung und Gültigkeit anzeigen.
9. Als Ebene 2 erst nach Klick verständliche Facetten nach Nutzerfragen anzeigen; leere oder irrelevante Module und der ausgeschaltete Portfolio-Bereich bleiben verborgen.
10. Als Ebene 3 technische Kennzahlen, Fundamentaldetails, Datenqualität, Methodik, Prognosequalität und Rohdaten in einem standardmäßig geschlossenen Bereich bündeln.
11. Nutzerentscheidungen und Backtests bei Bedarf lokal speichern; automatische Prognosen werden nicht mehr manuell aus der Analyseoberfläche ausgelöst.

Der automatische Ablauf ist:

1. Die Windows-Aufgabenplanung startet `scripts/run_forecasts.cmd` täglich zur konfigurierten lokalen Uhrzeit.
2. Der Wrapper setzt den Projekt-Arbeitsordner und startet `scripts/run_forecasts.py` mit `.venv/Scripts/python.exe`.
3. `forecast_runner.py` lädt Konfiguration und Universum, setzt einen täglichen Lauf auf oder nimmt einen unterbrochenen Lauf wieder auf.
4. Für jedes noch nicht erfolgreich verarbeitete Asset ruft der Runner `app.build_background_forecast_snapshot` und damit die vorhandene zentrale Analysepipeline auf.
5. `forecast_store.py` speichert Snapshots und Horizonte transaktional in SQLite; Fehler eines Assets werden protokolliert und stoppen den Rest nicht.
6. Danach werden fällige offene Prognosezeiträume mit echten späteren Kursdaten ausgewertet.
7. Die Streamlit-App liest nur kompakte Kennzahlen auf der Startseite und lädt die vollständige Tabelle erst bei aktivierter Prognosequalitätsansicht.

### Relevante Schnittstellen

- **Streamlit:** Benutzeroberfläche, Session State, Eingaben und Ergebnisdarstellung.
- **yfinance/Yahoo Finance:** einzige zentrale externe Markt- und Research-Datenschnittstelle.
- **Lokale JSON-Dateien:** Portfolio, Historien, Tracking und Backtest-Kontext.
- **SQLite:** skalierbare lokale Speicherung automatischer Prognosen, Auswertungen und Laufstatus.
- **CSV/JSON-Konfiguration:** kuratiertes Asset-Universum und einfach änderbare Laufparameter.
- **Windows-Aufgabenplanung:** täglicher benutzerbezogener Start des Hintergrundprozesses ohne sichtbare Streamlit-Oberfläche.
- **Plotly:** interaktive Diagramme innerhalb der Streamlit-Oberfläche.
- **GitHub Actions:** automatisierter Repository-Sicherheitscheck und Offline-Smoke-Test.
- **Streamlit Community Cloud:** dokumentierte Deployment-Möglichkeit; lokale Laufzeitdateien sind dort keine dauerhafte Datensicherung.

## 5. Bekannte Probleme und technische Schulden

- Die technische Challenger-Kampagne ist mit 248/248 vollständig. Daraus folgt weiterhin weder ein automatischer Sieger noch eine Produktionsänderung; Broad, vollständige Qualitätsprüfung und alle ungesehenen Gates bleiben erforderlich.
- Der autonome Paper-Bot besitzt erst drei gespeicherte Signale; die Stichprobe ist für Trefferquote, Rendite, Drawdown oder Strategieverbesserung nicht belastbar. Shadow-Live besitzt drei Orderentwürfe und drei ehrliche Missingness-Sidecars, aber weiterhin 0 echte Bid-/Ask-/Fill-Beobachtungen. Ohne belastbare Quelle werden diese Daten bewusst nicht geschätzt.
- Die vollständige historische Challenger-Detailaggregation über derzeit 392.273 Fälle ist rechenintensiv. Die normale Streamlit-Seite lädt sie deshalb nur nach ausdrücklicher Nutzeranforderung; ein späterer inkrementeller, voraggregierter read-only Bericht würde die Bedienbarkeit weiter verbessern, ohne Evidenz umzuschreiben.
- `app.py` bündelt weiterhin den Großteil der Anwendung in einer Datei mit rund 9.533 Zeilen. Das erschwert Modularisierung, isolierte Tests, Wartung und parallele Weiterentwicklung; Datenmodelle, Asset-Suche, JSON-Speicherung, technische Analyse, Datenqualität, Score-Zusammensetzung, Portfolio-Bewertung, Währungsumrechnung, Aktien-/ETF-Fundamentalanalyse, Bewertung, Zukunftspotenzial/eingepreiste Erwartungen, Szenarien/Expected Value, Empfehlungssynthese, Entry-Plan, Preisattraktivität, Long-Term-Quellenbasis/-Scoring, Long-Swing-Logik, Prognosehaltung, Kalibrierung, Driftmonitoring und Runner sind bereits getrennt.
- Die Teststruktur konzentriert sich weiterhin stark auf `tests/test_stability.py`; mit `tests/test_forecast_system.py`, `tests/test_recommendation_synthesis.py`, `tests/test_analysis_performance.py`, `tests/test_information_hierarchy.py` und `tests/test_trading_assistant.py` bestehen fachlich getrennte Module.
- Der GitHub-Actions-Workflow führt den Repository-Sicherheitscheck, den vollständigen Pytest-Lauf und den Offline-Smoke-Test aus. Der erste Remote-Lauf dieses erweiterten Workflows ist noch nicht dokumentiert.
- `pytest` ist als Entwicklungsabhängigkeit in `requirements-dev.txt` dokumentiert und wird im GitHub-Actions-Workflow installiert.
- Der erste vollständige 325-Asset-Lauf ist inzwischen erfolgreich belegt. Die Roadmap priorisiert nun den wiederkehrenden Wochenbetrieb, einen erweiterten qualitätsgeprüften Assetbestand und den Point-in-Time-Messvertrag als Grundlage für echtes kontrolliertes Lernen. Der erste GitHub-Actions-Remote-Lauf bleibt bis zu einem ausdrücklich erlaubten Commit und Push nachgeordnet blockiert.
- Yahoo Finance ist die zentrale externe Quelle. Ausfälle, Schemaänderungen oder fehlende Felder begrenzen dadurch mehrere Analysebereiche gleichzeitig.
- Die Long-Term-Quellenprüfung definiert strikte Provenienz-, Mindestabdeckungs- und quellentypische Altersregeln. Ein alter Bericht kann nicht durch einen neuen Abrufzeitpunkt verjüngt werden. Die lokale Evidenzablage besitzt Schema-/Modellversion, atomaren Austausch und Stale-Sperre; das getrennte Scoring erzwingt sieben belegte Faktoren und geordnete Drei-Szenario-Rechnungen. Die SEC-Teilkollektion verbindet offizielle US-Filings, öffentliche gecachte JSON-Daten, sechs nur bei passender Accession belegte XBRL-Jahreswerte und sachliche Zwei-Jahres-Vergleiche zu einem weiterhin geschlossenen Bereitschaftsbericht. Transportfehler besitzen begrenztes Retry/Backoff; dauerhafte Fehler enden sofort. Die CLI-Vorprüfung bestätigt aktuell ohne Netzwerk oder Schreibvorgang, dass die erforderliche Fair-Access-Kontaktkennung nicht konfiguriert ist; ein Live-Abruf bleibt daher korrekt gesperrt. Prozessübergreifende Begrenzung und unabhängige Gegenquellen fehlen ebenfalls. Deshalb ist der Modus nicht freigeschaltet und erzeugt keine Langfrist-Empfehlung.
- Die Prozent-Tranchen der langfristigen Einzelanalyse bleiben eine relative Reihenfolge innerhalb der geplanten Position oder Aufstockung. Der Swing-Scanner besitzt getrennt davon eine risikobasierte Stückzahl aus Kapital, Risikolimit, Einstieg und Stop; ohne hinterlegtes Trading-Kapital wird auch dort keine Stückzahl ausgegeben.
- Yahoo Finance liefert im aktuellen Projekt keine vollständigen historischen Umsatz-, Gewinn-, Cashflow-, Erwartungs- und Bewertungsstände exakt zum früheren Kurshoch. Die App prüft deshalb aktuelle Fundamentaltrends und kennzeichnet den exakten Seit-dem-Hoch-Vergleich als nicht belastbar, statt ihn zu schätzen.
- Rücksetzer-, Bestätigungs- und Widerlegungsmarken sind technische Planungsmarken und keine garantierten Ausführungskurse.
- Kaufzonen werden derzeit deterministisch um die nächste belastbare technische Referenz gebildet (ETF enger, Aktie mittel, Krypto breiter). Diese Breite ist transparent und asset-spezifisch, aber noch nicht historisch kalibriert oder volatilitätsadaptiv validiert.
- `Erweiterte Analyse` ist visuell geschlossen, wird von Streamlit im selben Seitenlauf jedoch bereits berechnet. Die Hierarchie reduziert die sichtbare Informationslast, ist aber noch kein vollständig lazy geladener Backend-Bereich.
- Makro-, Rohstoff-, Geopolitik-, Liquiditäts-, Krypto- und institutionelle Module arbeiten teilweise mit Proxies oder unvollständigen Yahoo-Finance-Daten. Die Anwendung kennzeichnet diese Einschränkungen, die fachliche Abdeckung bleibt dennoch begrenzt.
- Der Swing Finder hängt für den großen Marktabruf weiterhin von Yahoo Finance ab. Der reale 2.352-Asset-Amerika/Global-Lauf lud 2.350 Assets in 327,36 Sekunden ohne Rate-Limit; `CWEN-A` und `SVA` blieben als technische Fehler sichtbar. Diese sehr gute Einzelmessung ersetzt noch keinen mehrwöchigen Dauerbetrieb.
- Automatische Prognosen verwenden SQLite; manuelle Legacy-Historien verbleiben aus Kompatibilitätsgründen in JSON. Einzelne Schreibvorgänge sind jetzt atomar, konkurrierende Schreibzugriffe mehrerer Prozesse werden aber weiterhin nicht zusammengeführt.
- Der Prognosestatus speichert nur den letzten fehlgeschlagenen automatischen Auswertungsversuch je Asset und Zeitraum. Er unterscheidet fehlende Marktdaten von sonstigen technischen Fehlern, bildet aber noch keine vollständige Versuchshistorie oder Fehlermetrik ab.
- Das SQLite-Schema besitzt nun die formale Version 9 und schrittweise idempotente Migrationen. Version 5 ergänzt den L0-Messvertrag, Version 6 Wochenkohorten-Metadaten, Version 7 reichere Ergebnisfelder, Version 8 Trend-/Marktbenchmark-Ergebnisse und Version 9 die explizite Rohwahrscheinlichkeit je Prognosezeitraum. Vor den produktiven Migrationen wurden geprüfte SQLite-Sicherungen erstellt; ältere Prognosen blieben unverändert.
- Das 325-Asset-Universum ist kuratiert und erweiterbar, nicht vollständig. Dauerhaft ungültige Ticker werden protokolliert, aber bewusst nicht automatisch entfernt.
- Der Runner besitzt nun eine feste 1.726-Asset-Wochenrotation und speichert Version, Kohorte und Zuordnungsfingerabdruck. Noch offen sind der mehrwöchige Realnachweis, eine vollständige historische Universumsmitgliedschaft über Versionswechsel, Delisting-Pflege und Kapazitätssteuerung anhand echter Fehlerraten und Laufzeiten.
- Der erste vollständige planmäßige Lauf ist beobachtet und erfolgreich beendet. Ein einzelner Lauf belegt jedoch weder mehrwöchige Zuverlässigkeit noch Prognosequalität; Wiederanlauf, Nachholen, erste Fälligkeiten und Drift müssen weiter real beobachtet werden.
- Die gespeicherten Daten ermöglichen Gedächtnis, Ergebnisprüfung und manuelle Kalibrierungshinweise, aber noch kein echtes Modelltraining. Neue Snapshots besitzen einen vor jedem Lauf erneut geprüften L0-Vertrag, feste Trend- und Marktbenchmarks sowie eine messbare unkalibrierte Rohwahrscheinlichkeit; ältere Snapshots bleiben Legacy. Brier/Log-Loss, Kalibrierungsfehler, strenges Datensatz-Gate, purged Walk-Forward-Aufteilung, append-only Modellregister und rein beobachtendes Driftmonitoring sind technisch vorbereitet, besitzen aber noch keine gereiften realen Wahrscheinlichkeitsfälle oder echten Vergleichsperioden. Reife Benchmark-Ergebnisse, eigene Horizontmodelle, Wahrscheinlichkeitskalibrierung, tatsächlich laufende Shadow-Challenger und ein produktives OOD-Enthaltungsgate fehlen weiterhin.
- Die neue Start-/Asset-Diagnose verbessert die Ursachenlokalisierung bei einem erneuten harten Abbruch, verhindert aber keinen externen Abbruch durch Windows, Abmeldung, Energiezustand oder Prozessbeendigung.
- Eine lesende Prüfung der Windows-Systemereignisse zum alten Lauf zeigte Modern-Standby-Wechsel kurz vor 22:30 Uhr, aber keinen eindeutigen Absturz- oder Beendigungsnachweis zum Lauf. Die Ursache von `0xC000013A` bleibt daher bis zur nächsten Beobachtung offen.
- Der reale Lauf vom 2026-08-01 blieb bei 0 von 325 verarbeiteten Assets stehen und wurde beim nächsten Tageslauf als unterbrochen dokumentiert. Der erfolgreiche Lauf vom 2026-08-02 ersetzt diesen historischen Fehler nicht, belegt aber den funktionsfähigen aktuellen Start- und Verarbeitungsweg.
- Die Windows-Aufgabe verwendet einen interaktiven Benutzer-Logon mit eingeschränkten Rechten. Sie startet bei verpasster Uhrzeit nach Verfügbarkeit, läuft jedoch nicht unabhängig von einem angemeldeten Benutzerkonto.
- Im Hintergrundlauf werden massenhafte asset-spezifische News- und Earnings-Abfragen bewusst ausgelassen. Das schont Yahoo Finance, begrenzt aber die Research-Abdeckung der täglichen Snapshots.
- Die numerischen erwarteten Kursbereiche aller fünf Horizonte basieren aktuell auf derselben vorhandenen Unterstützungs-/Widerstandsstruktur. Die zentrale Erfolgskennzahl ist deshalb bewusst die Richtungstrefferquote; eine belastbar horizon-spezifische Zielmodellierung bleibt offen.
- Mehrere Historienformate besitzen Legacy-Felder. Defensive Normalisierung ist umgesetzt, die dauerhafte Schema-Konsolidierung bleibt technische Schuld.
- Die Wiederherstellungsfunktion erzeugt bewusst nur eine geprüfte neue SQLite-Datei. Der Austausch der produktiven Datenbank bleibt ein manueller Wartungsschritt bei sicher gestopptem Hintergrundprozess; dadurch wird kein laufender Datenbestand versehentlich überschrieben.
- Die sehr umfangreiche `ROADMAP.md` kombiniert Planung, Status, Arbeitsregeln und einen langen, teilweise nicht chronologisch angeordneten Änderungsverlauf. Eine spätere Konsolidierung würde die Wartbarkeit verbessern.
- Der aktuelle lokale Testlauf deckt Pytest, Streamlit-AppTest, Headless-Start, Live-Datenpfade, SQLite und sichtbare Browserprüfung ab. CI deckt Pytest, Repository-Sicherheit und Offline-Start ab; Live-Daten- und sichtbare Browserprüfungen bleiben bewusst lokal.
- Es sind keine aktuell bekannten aktiven Tracebacks oder absichtlich verdeckten Laufzeitfehler dokumentiert. Externe Datenverfügbarkeit bleibt jedoch eine betriebliche Unsicherheit.

## 6. Änderungsverlauf

### 2026-08-23

Änderungen:

- Methodischen Research-Policy-Vertrag ergänzt. Bereits vorhandene Features werden deterministisch sieben primären Informationsfamilien zugeordnet; Rohfeatures, Familienzählung, semantische Redundanz und tatsächlich verschiedene Informationsfamilien werden getrennt gezeigt. Korrelierte Trendmerkmale zählen nicht als mehrere unabhängige Bestätigungen. Keine Rohfeature- oder Broad-Erweiterung.
- Sequenzielle Research-Sperre umgesetzt: Setup/Entry, Stop, Exit/Management und vollständiger Challenger OOS sind getrennte Ledger-Versuche. Jede Folgestufe benötigt den manuellen Freeze aller Vorgänger. Kombinatorische Entry×Stop×Exit-Suche und Variantenlisten im finalen OOS werden abgelehnt.
- 20 Fälle als reine frühe Diagnose-/Anzeigegrenze festgeschrieben. CRV ≥ 2 bleibt unveränderte Long-v1-Baseline und kein behauptetes Optimum. Fib-Kontroll- und Kill-Regel, sekundärer Status für COT/Saisonalität/Opening Levels sowie unveränderte Event-Research-/Shadow-Sperre dokumentiert und maschinenlesbar gemacht.
- Evidenzartenvertrag hält Historical Walk-Forward, Broad Historical, Swing Forward, Autonomous Paper, Shadow Live, User Trades und Legacy JSON getrennt. Kombinierte Berichte enthalten keine vermischte Gesamtkennzahl.
- Datierter `Current Truth`-Block ergänzt. Die spätere Trennung in ROADMAP, PROJECT_STATUS, CHANGELOG und RESEARCH_POLICY ist geplant, wird aber nicht vor dem ersten Broad-Pass als große Migration ausgeführt.
- 12/12 gezielte Research-Policy-Tests und vollständige Regression 622/622 erfolgreich. Python-Kompilierung und Git-Diff-Prüfung bestanden. Broad-Code- und Feature-Vertragsfingerprint sowie Frozen-Dataset blieben vor/nach identisch; Long-v1 blieb unverändert.
- Research-Quality-v1 umgesetzt und an den zukünftigen Broad-Development-Abschluss angebunden. Der getrennte append-only Ledger speichert Hypothesen und Ereignisse, dedupliziert semantisch identische Umbenennungen, zählt Familienversuche und verhindert doppelte Resume-Evaluationen. Der reale Ledger steht bis zum Broad-Start bei 0 registrierten Hypothesen.
- Deterministische regimegematchte Placebos, optionale kausal vorbereitete Zeit-/Random-Entry-Kontrollen, feste Parameterplateaus, exakte Ein-Feature-Ablation, konservative Zusammenhangscluster, Kalender-/Rolling-/Regime-Stabilität, Entry-Effizienz A–D, getrennte Execution-Stressszenarien, Komplexitätsbericht und Survivorship-Audit ergänzt.
- Development-C verschärft: vorläufig gute Durchschnittswerte bleiben B, solange die vollständige Qualitätsprüfung nicht dokumentiert ist. Ein C-Freeze verlangt zusätzlich `quality_review_complete = true`. Keine automatische Auswahl, kein Tuning, keine Validation-/Holdout-Öffnung, keine Featureentfernung, keine Regelkombination und keine Produktion.
- Historische, Forward-, Paper- und Shadow-Evidenz bleiben getrennt. Long-v1, Stops, Ziele, Kosten, 248er Queue und bestehende Daten wurden nicht verändert. Lesender Kampagnenstand 246/248 beziehungsweise 99,19 %, A/B je 80/80 und C 78/80; Broad weiterhin gesperrt und 0 reale Kandidaten.
- Strikt getrennten Point-in-Time Event-/News-/Makro-/Geopolitik-Research-Layer umgesetzt. Der versionierte append-only Vertrag umfasst Company, Macro, Geopolitics/Policy und Market Shock, Quellenqualität/Provenienz, Eventrevisionen, Expectation/Actual/Surprise, klinische Missingness, politische Umsetzungsstände, hierarchische Relevanz und eine erklärbare Übertragungsmatrix ohne Kausalitätsbehauptung.
- Eventfeatures, Signal-Sidecars und spätere Market-Reaction-Labels physisch getrennt. Reaktionshorizonte können später 1h/Close/1D/3D/5D/10D/20D, MFE/MAE, Volumen, Gap sowie Sektor-/Marktrelativwerte speichern, aber nur nach Eventverfügbarkeit und nur in tatsächlich vorhandener Datengranularität.
- Forward-Sammlung nach erfolgreicher Signalablage in den Hintergrundrunner eingebunden. Eventfehler sind fail-open ausschließlich für Research: Scan, unveränderbarer Forward-Snapshot, Paper, Shadow, Prognosen und Broad Research bleiben unangetastet. `research_only`, keine Strategie-/Score-/Stop-/Größenänderung, kein Short und keine Brokerorder sind in Konfiguration und Ergebnisvertrag festgeschrieben.
- Netzwerkfreien Legacy-Nachzug ausgeführt: 29 unveränderbare Sidecars, 24 bereits damals im Signalsnapshot bekannte generische Unternehmenstermine für 20 Assets und 29 Verknüpfungen; fünf Sidecars ohne belastbare Eventinformation. Historische News, Terminarten, Expectations und Ursachen wurden nicht rückwirkend ergänzt. Event-Store-Integrität `ok`, null ungültige Fingerprints.
- Forward-Event-Diagnose ergänzt. Von 14 abgeschlossenen Trades besitzen elf nur einen generischen bekannten Unternehmenstermin, drei keine belastbare Eventinformation; 0 belegte Earnings, negative Company Events, Geopolitik-/Market-Shock-Kontexte oder positive Surprises. Kleine Stichprobe und fehlende Eventart verbieten jede Regelableitung.
- Append-only Event-Hypothesen-Ledger vorbereitet: einzelne begründete Hypothese, Development, Freeze, Validation, Holdout und erst danach External/True Forward. Freie Keywordoptimierung, automatische Eventcluster-Regeln und Holdout-Selektion bleiben gesperrt. Der technische Broad-Pass wartet nicht auf historische Event-Coverage.
- Kostenlosen historischen SEC-SIC-Pfad umgesetzt. Aus den offiziellen Financial Statement Data Sets werden ausschließlich unterstützte 10-K-/10-Q-/20-F-/40-F-Einreichungen mit CIK, Accession, Annahmezeitpunkt, damaligem SIC und deterministischer SIC-Division gelesen. Fehlender SIC bleibt fehlend.
- Append-only SQLite-Speicher, reproduzierbare Snapshot-Fingerprints, konfliktfreie Wiederaufnahme und streng kausale As-of-Abfrage ergänzt. Eine Abfrage darf niemals ein erst später angenommenes Filing verwenden.
- Sicherer optionaler Download einzelner SEC-Quartalsarchive ergänzt: Laufzeitkontakt ist Pflicht, maximal 200 MiB, temporärer Download, ZIP-/SUB-Prüfung vor atomarem Austausch und kein erneuter Netzwerkzugriff bei bereits gültigem Archiv. Ohne Kontaktkennung wurde kein Live-Abruf durchgeführt.
- Grenzen bleiben technisch und dokumentarisch sichtbar: keine historische Indexmitgliedschaft, keine bestätigte Handelbarkeit, keine delisteten Kurse und damit keine vollständige survivorship-bias-freie OHLCV- oder Sektor-Breadth-Basis. Der Pfad verändert weder den eingefrorenen ersten Broad-Pass noch Long-v1, Regeln, Stops, Ziele, Kampagne oder Produktion.

Tests:

- 42/42 gezielte Research-Quality-, Broad-, Kontext-, Übergangs- und Diagnose-Tests erfolgreich; Python-Kompilierung der geänderten Module und des Broad-Runners bestanden. Eine erneute Vollregression wurde bei zwei noch offenen historischen Kampagnenjobs bewusst nicht gestartet.
- Abschließende vollständige Regression in der lockfreien Lücke zwischen zwei historischen Shards: 589/589 Tests in 60,82 Sekunden erfolgreich; der nächste Kampagnenstart und seine Forschungsdaten wurden nicht verändert.
- 24/24 gezielte Event-Research- und Hintergrundrunner-Regressionen erfolgreich: Kausalität, Revisionen, Surprise, Relevanz, Quellen/Provenienz, Missingness, getrennte Labels, Append-only/Resume, deterministische Fingerprints, Forward-Read-only-Nachzug, nicht blockierender Providerfehler, Broad-Unabhängigkeit, Long-v1-Neutralität, kein Short und keine Brokerorder. Python-Kompilierung der Eventmodule und CLI erfolgreich.
- 568/568 vollständige Tests vor der abschließenden reinen CLI-Ergänzung sowie danach 11/11 gezielte Parser-, Missingness-, SIC-, Kausalitäts-, Resume-, Append-only-, Download- und Preflighttests erfolgreich. Python-Kompilierung und SQLite-Statusprüfung bestanden. Eine erneute Vollregression wurde während des laufenden historischen Kampagnenjobs bewusst nicht gestartet.

Git:

- Kein Commit und kein Push durch diese Arbeitseinheit.

### 2026-08-22

Änderungen:

- Featureumfang für den ersten Broad-Research-Vollpass vor seinem realen Start erweitert und eingefroren. Verfügbar sind jetzt kausale Relative Stärke gegen lokale Markt-/Regionalbenchmarks, Trendqualität, Volatilitätskompression/-expansion, kontinuierliche Kerzen-/Price-Action-Werte, historische 20/50/100/252-Hochs und -Tiefs, deterministische Konsolidierung sowie Gap-/Overnight-Risiko. Dieselben gemeinsamen Berechnungen werden je Asset/Tag nur einmal erzeugt und sind richtungsneutral.
- Historische Marktbreite aus dem finalisierten Frozen-Projektuniversum vorbereitet: Gesamtanteile über EMA20/50/200, positives 20/60-Momentum, Nähe zu 20/50-Hochs/-Tiefs, Änderungen über 5/10/20 Sitzungen und Beschleunigung. Region und Assettyp werden erst ab mindestens fünf Assets je Merkmal ausgegeben. Der Layer ist ausdrücklich nicht survivorship-bias-frei. Historische Sektor-/Peer-Mitgliedschaft, Sektor-Breadth und Vergleichsgruppen-Perzentile bleiben mangels belastbarer Point-in-Time-Zuordnung sichtbar nicht verfügbar.
- Der Breadth-Kontext wird ausschließlich nach bestandenem 248/248-Gate aus lokalen Frozen-Daten erzeugt, komprimiert append-only gespeichert und bei Resume fingerprintgeprüft geladen. Keine Yahoo-/Providerdownloads, keine Featureoptimierung, keine neue Confluence, kein Holdout-Zugriff, keine Short-Aktivierung und keine Änderung von Long-v1, Stops, Zielen, Kosten oder Produktion.
- Broad-Speicher Schema 4; Feature-Schema `swing-broad-pit-features-frozen-first-pass-2026.08.22-v3`; ML-Adapter `swing-ml-broad-research-frozen-first-pass-2026.08.22-v3`; Label-Schema unverändert `swing-broad-direction-neutral-labels-2026.08.22-v2`. Code-Fingerprint `7e763c3d786d3d79431f5b635d5e637e7b4f6add85d6ffa2596c7b8507e21b62`, Feature-Vertragsfingerprint `649bc9b45ad73c0d97aa95c0472c04cc8a01d30bff0c321972dd50d15e249e0b`, Frozen-Dataset unverändert `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`.
- 559/559 Tests, Python-Kompilierung, Repository-Sicherheitscheck, Streamlit-Start und Git-Diff-Prüfung erfolgreich. Der Live-Smoke konnte für `BTC-EUR` wegen nicht verfügbarer externer Yahoo-Kursdaten keine Chartdaten laden; es wurden keine Ersatzdaten erfunden. Kampagne lesend unverändert bei 243/248 beziehungsweise 97,98 Prozent: A 80/80, B 80/80, C 75/80. Der Broad-Pass bleibt gesperrt und enthält weiterhin 0 Kandidaten. In dieser Arbeitseinheit wurde kein Commit und kein Push ausgelöst; der Branch-HEAD wurde währenddessen durch einen anderen Projektprozess auf `17f4f911f8f8afba4ed371ea26b12b65030adfef` fortgeschrieben, die abschließenden Änderungen bleiben lokal offen.
- Rein vorbereitenden Short-Readiness-Layer vor dem ersten realen Broad-Vollpass umgesetzt. Der gemeinsame historische Pass berechnet jetzt zusätzlich kausalen Abwärtsimpuls und Rally-Retracement, Stärke/Dauer, bullische Kerzenserien, bearish `Close < Low[t-1]`, Lower High/Lower Low, bearish BOS/Breakdown, High-/Low- und Close-Break, ATR-Überschreitung, gespiegelte Fibonacci-Lage sowie bearishen EMA-Kontext. Vorhandene RSI-/EMA-/ATR-/Volumen-/Volatilitäts-/Marktphasen-, Opening-, Saisonalitäts- und COT-Werte werden wiederverwendet.
- Spätere Labels für 5/10/20/25 Sitzungen richtungsneutral erweitert: Forward Return, zukünftiges Hoch/Tief, maximale Auf-/Abwärtsbewegung in Prozent und ATR sowie Sitzungen bis Hoch/Tief. Features und Labels bleiben getrennt; keine Zukunftsinformation fließt in Kandidat oder Feature. Borrow-Verfügbarkeit, Leih-/Finanzierungs-/Brokerkosten und reale Short-Spreads bleiben ausdrücklich unbekannt und werden nicht angenähert.
- Broad-Speichervertrag nicht löschend auf Schema 3 mit expliziter Richtung `long | short` erweitert; der reale Pass speichert derzeit ausschließlich `long`. Feature-Schema `swing-broad-pit-features-short-readiness-2026.08.22-v2`, Label-Schema `swing-broad-direction-neutral-labels-2026.08.22-v2`, Code-Fingerprint `b7020db164445369b39cbbef619f965d71b8012b325439dc2fab79bc2e6f8811`, Feature-Vertragsfingerprint `46acb6e82b0feaaf0809b4b665944e1171189025e97d842cbcf846fa31de2e5e`. Frozen-Dataset unverändert `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`.
- Eine reine richtungsneutrale Preisordnungsprüfung ist vorbereitet. Aktive Risk-, Paper- und Shadow-Pfade blockieren explizite Short-Kandidaten fail-closed; es wurden keine Short-Strategie, kein Short-Challenger, kein Short-Signal und keine Short-Ausführung ergänzt. Long-v1 und die 248er Kampagne blieben unverändert; letzter relevanter lesender Stand 243/248, Broad weiterhin 0 reale Kandidaten.
- Forward-Statusbericht auf alle abgeschlossenen echten Paper-Trades einschließlich künftiger Gewinner erweitert. Ein getesteter Pflichtfeldvertrag hält pro Trade Ticker, Setup, Entry/Stop/Ausstieg, Stopweite, Ergebnis-R, MFE/MAE in R und Prozent, MFE-Schwellen, Zeit bis MFE/Exit, Gap/Slippage, Signalzustände, A–G und eine konkrete sachliche Begründung im JSON-Bericht sowie im reproduzierbaren Markdown-Status fest.
- Aktueller rein lesender Befund mit vollständiger Einzeltabelle dokumentiert: 0 Gewinne/14 Verluste, durchschnittlich -1,0867 R, Profitfaktor 0, 15,2143 R Drawdown, Ø MFE 0,6676 R, Median-MFE 0,6187 R und Ø MAE -1,0444 R. 8/4/1/1 Trades erreichten mindestens 0,5/1/1,5/2 R; 12 waren zeitweise positiv, sechs fast ohne Bewegung, drei Gap/Slippage und drei mögliche Stop-Kalibrierungsfälle. Für noch keinen Fall ist ein vollständiges 5- oder 20-Sitzungsfenster vorhanden; alles bleibt `n/v` statt geschätzt. Der Befund ändert Long-v1, Stops, Ziele, Filter und Produktion ausdrücklich nicht.
- Fail-closed Übergang der bestehenden 248-Job-Kampagne zum Broad-Research ergänzt. Erst exakt 248/248, ein vollständiger gültiger Walk-Forward-Audit, identischer finalisierter Frozen-Datensatz sowie Code-/Feature-Fingerprints erzeugen einen einmaligen append-only Übergangsnachweis. Der vorhandene Windows-Wrapper startet danach höchstens 16 Assets je Block und prüft Schutzfenster sowie Produktionslocks erneut; keine neue Marktdatenerfassung.
- Development-Bericht um ungefilterte Basis, Expectancy, Trade-Retention/-Verlust sowie kleine feste RSI-, EMA- und BOS-Parameter-Nachbarschaften ergänzt. Validation/Holdout bleiben technisch geschlossen.
- Manuellen C-Challenger-Handoff vervollständigt: Nur ein bestätigter C-Bericht kann eine vollständig fingerprintete feste Regel erzeugen. Ground-up-Rescans aus Frozen-OHLCV laufen strikt Validation → manuelle Prüfung → Holdout → External → True Forward; Development wird nicht zur nachträglichen Filterung geöffnet, Parameter bleiben unveränderlich und Produktion kann nie automatisch aktiviert werden.
- External-Ergebnisspeicherung zusätzlich hart an das manuell bestandene Holdout-Gate derselben festen Challenger-Version gebunden. Ohne diesen Nachweis bleibt nur die outcome-blinde Auswahl-/Freeze-Infrastruktur nutzbar; aktuell existieren weiterhin 0 External-Manifeste und 0 Ergebnisse.
- Ein C-Freeze muss nun zusätzlich auf das vollständige append-only Broad-Manifest und den dort unverändert gespeicherten C-Hinweis verweisen; vorgelegte Berichte können das Gate nicht umgehen. Aktuelle Fingerprints: Code `a1fb7490b377500d55a10ae08b9b5056fffc4493fb6adaa183b91ba603198b67`, Featurevertrag `b2705b847881f5c70e16539fb1de51065d35e7c250bf6c0c79313cf2b2f3496f`, Frozen-Dataset unverändert `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`.
- Laufende Kampagne unverändert bei 243/248 beziehungsweise 97,98 % geprüft: A 80/80, B 80/80, C 75/80, fünf offen. Broad-Speicher Schema 2 und Integrität `ok`, weiterhin 0 Assetabschlüsse, 0 Kandidaten, 0 Hypothesen, 0 Challenger und 0 Challenger-Trades.
- Priorisierte Verlust-/Edge-Diagnose als getrenntes read-only Modul ergänzt. Vorhandene Fälle werden nach Ergebnis, MFE/MAE, Gap-/Ausführungsrisiko, Verlustserie, Setup, Marktphase, Volatilität, Assettyp, Region und Issuer-Cluster ausgewertet. Hinweise auf Entry-/Setup- oder Stop-/Exit-Probleme sind ausdrücklich keine Regelentscheidung; bei täglichen Kerzen wird keine unbeweisbare Reihenfolge innerhalb der Stop-Kerze behauptet. Nicht gespeicherte ATR-Abstände, Sitzungsdauern und Sektoren werden nicht rekonstruiert.
- ML-tauglichen Shadow-Datenvertrag ergänzt. Er trennt Fall-/Asset-/Listing-/Strategieidentität, Point-in-Time-Features und erst spätere Zielvariablen, lehnt zukünftige Quellen und Label-Leakage ab, speichert Missingness sichtbar und erzeugt reproduzierbare Fingerabdrücke. Er trainiert kein Modell, verändert keine Regel und erlaubt nur zeitbasierte purged Walk-Forward-Splits.
- Strategie-Freeze-Infrastruktur mit neun getrennten append-only Baseline-/Challenger-Artefakten, vollständigen Fachverträgen sowie Code-, Konfigurations-, Komponenten- und Datenfingerabdrücken umgesetzt. Die Long-v1-Baseline bleibt unverändert; keine Performancefreigabe oder automatische Produktionsaktivierung.
- Acht technische Research-Challenger für RSI, EMA20/EMA50, EMA+RSI sowie Pullback-/Breakout-Trennung hinzugefügt. Alle laufen mit kausalen Indikatoren, denselben Kosten-/Purging-/Development-/Validation-/Holdout-Regeln und getrennten Strategieversionen; ein robuster Vorteil muss auf ungesehenen Daten und über vorab festgelegte Parametervarianten bestehen.
- Gemeinsame unabhängige Risk Engine sowie autonomer brokerloser Paper-Bot und brokerlose Shadow-Live-Grundlage umgesetzt. Vollständiger virtueller Positionszyklus, Restart/Idempotenz, fail-closed Datenfehler, append-only Audit und strikte Evidenztrennung sind vorhanden; reale Orders sind technisch ausgeschlossen.
- Historische Forschung unverändert fortgesetzt und geprüft: 226/248 Kampagnenjobs abgeschlossen, 5.507 Läufe, 392.273 Fälle, SQLite-Quick-Check `ok`, null ungültige Einträge. Kein bestehender Fall, keine Forward-Historie und keine Baseline wurden gelöscht, überschrieben oder zurückgesetzt.
- Gemeldeten Streamlit-Importfehler für `refresh_swing_walk_forward_forward_links` behoben beziehungsweise gegen den vollständigen Modulstand verifiziert. Die normale Seite lädt die große historische Detailaggregation nur noch auf Wunsch.
- Breiten Frozen-Research-Pfad und External-Universe-Gate umgesetzt. Die neue Pipeline erzeugt Kandidaten ohne Ergebniswissen, berechnet alle verfügbaren G2.1-/G2.2-/G2.3-Merkmale in einem kausalen Assetpass, hängt Labels und Stop-/Exit-Kontrafakten erst danach getrennt an und wertet die acht festen Hypothesen speicherschonend ausschließlich auf Development aus. Dataset-Fingerprint `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`, Code-Fingerprint `1c70ed5458a8554ca81bbeebfd5d9fc57afc611de55b85fca2b7b6fed8d52774`, Feature-Vertragsfingerprint `a14cfda4b1c6669e4af51b3699859f780573266e10005b4de306d24449f9aa67`. Volume Profile bleibt wegen Daily-OHLCV ausdrücklich nicht verfügbar; kein ML wurde trainiert.
- Bestehende Kampagne erneut unverändert geprüft: 238/248 Jobs, 10 offen, A 80/80, B 80/80, C 70/80, 5.792 Läufe, 397.764 Fälle, 0 ungültige Fingerabdrücke, SQLite `ok`, Dataset-Fingerprint `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`. Der neue Runner verweigert deshalb den echten Vollstart; sein separater Speicher meldet Integrität `ok`, 0 Assetabschlüsse und 0 Kandidaten. External-Universe-Infrastruktur ist bereit, aber noch ohne Manifest und Ergebnisse.

Tests:

- Abschließende gezielte Prüfung des verbindlichen Forward-Statusrenderers: 9/9 Diagnose- und Dokumentationsregressionen erfolgreich; die konkrete Ursachenzeile ist ausdrücklich als maschinell erzeugte sachliche Begründung gekennzeichnet.
- 28 gezielte Broad-/Short-Readiness-/Transition-/Bot-/ML-Vertragstests und 556/556 vollständige Regression erfolgreich. Python-Kompilierung der geänderten Module bestanden. Repository-Sicherheitscheck, Offline-Smoke-Test einschließlich Streamlit-Start und Git-Diff-Prüfung wurden anschließend erfolgreich ausgeführt.
- Erweiterter Forward-Statusvertrag und statische PLDatei-Abdeckung geprüft: 45/45 gezielte Diagnose-/Forward-Tests und 556/556 vollständige Regression in 53,17 Sekunden erfolgreich. `compileall`, Repository-Sicherheitscheck und Git-Diff-Prüfung bestanden. Die produktive Forward-Datenbank hatte vor und nach beiden Read-only-Berichtsformaten denselben SHA-256 `455F55F3FB8676BE8C123E22CE559CA6DA2948078D12E317914ED996139E543A`.
- Abschließende vollständige Regression 547/547 in 82,24 Sekunden erfolgreich. Zusätzlich 24 gezielte Stopout-/Broad-/Transition-/Challenger-/External-Gate-Tests, Python-`compileall`, direkter App-Import und realer headless Streamlit-Start auf Port 8517 erfolgreich; Testserver anschließend beendet.
- Sieben gezielte Diagnose-/ML-Vertragstests sowie vollständige Regression 526/526 erfolgreich. Python-Kompilierung, Repository-Sicherheitscheck, Offline-Smoke-Test einschließlich Streamlit-Start und Git-Diff-Prüfung bestanden.
- Vollständige Regression: 519/519 Tests erfolgreich in 84,39 Sekunden. Zusätzlich Python-Kompilierung der relevanten App-/Swing-Module, Repository-Sicherheitscheck und Offline-Smoke-Test einschließlich Streamlit-Start erfolgreich. Der direkte App-Import und der zuvor fehlende `refresh_swing_walk_forward_forward_links`-Import sind bestätigt.
- Aktueller vollständiger Regressionslauf: 538/538 Tests in 50,46 Sekunden erfolgreich. Zusätzlich 26 gezielte Broad-Research-, External-Universe-, ML-Vertrags- und COT-Tests, Python-Kompilierung sowie direkter Import von `refresh_swing_walk_forward_forward_links` erfolgreich.

Git:

- Branch `codex/swing-forward-diagnostics-status`; Ausgangscommit `b6698c0bdcfa0565f10df1be16fc1b53927022e7`. Der dokumentierte zusammenhängende Arbeitsstand ist auf diesem Branch versioniert; Commit und GitHub-Abgleich werden beim Abschluss des Work-Stands extern ausgewiesen.

### 2026-08-19

- Historische Kampagne bei 16/248 abgeschlossenen Jobs beziehungsweise 6,45 % gegen wiederholte Legacy-Shard-Abbrüche stabilisiert. Ursache war kein Datenfehler: Dieselben 1.480/1.488 OHLCV-Zeilen in Manifest, Frozen-Parquet und Cache erhielten nach dem Parquet-Roundtrip wegen `datetime64[s]` gegenüber `datetime64[ms]` unterschiedliche Fingerprints.
- Automatische, streng begrenzte Kompatibilitätsreparatur umgesetzt: Neue Research-Historienfingerprints kanonisieren den DatetimeIndex; bestehende V1-Manifeste akzeptieren beim Lesen ausschließlich inhaltlich identische `s/ms/us/ns`-Repräsentationen. Weder Manifest noch Frozen-Datei, Dataset-Fingerprint `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed` oder gespeicherte Fälle werden umgeschrieben. Abweichende OHLCV-Werte bleiben gesperrt.
- Reale automatische Wiederaufnahme ohne manuellen Neustart belegt: Nach dem letzten Altprozess-Fehler um 11:50 Uhr nahm der reguläre Fünf-Minuten-Trigger um 11:55 Uhr denselben offenen Legacy-Vertrag wieder auf; sechs aktive Analyseworker bestätigten, dass die Dataset-Prüfung passiert wurde. Queue bleibt 248 Jobs, Fortschritt und Attempts bleiben atomar nachvollziehbar.
- Zusätzliche automatische Recovery für echte Frozen-Dateifehler umgesetzt: ausschließlich ein lokaler Cacheverlauf mit exakt manifestkompatiblem vollständigem OHLCV-Fingerprint darf eine fehlende, unlesbare oder abweichende Parquet-Datei atomar ersetzen. Das defekte Original bleibt vorher deterministisch unter `.recovery` erhalten; es gibt keinen Providerabruf, keine Manifest-/Epochänderung und keine Annäherungs- oder Teildatenreparatur. Ein abweichender oder fehlender Cache hält den Job sicher offen für den nächsten Retry.
- Tests: 46/46 gezielte Dataset-, Walk-Forward-, Campaign-, Fingerprint-, Resume- und Append-only-Prüfungen sowie 519/519 vollständige Regression bestanden. Ein reiner Datetime-Auflösungswechsel wird akzeptiert, eine Teständerung des Schlusskurses um +0,01 weiterhin fail-closed abgelehnt. Keine Strategie-, Profil-, Fallauswahl-, Ergebnis-, Forward- oder Produktionsänderung.

### 2026-08-18

- Neuer COT-/Positionierungs-Shadow-Layer für den Swing Trader umgesetzt und in der Roadmap als priorisierte Phase G1 verankert.
- Offizielle CFTC-Public-Reporting-Datensätze `TFF - Futures Only` und `Disaggregated - Futures Only` werden über feste HTTPS-Endpunkte paginiert gelesen. Die Zertifikatsprüfung bleibt aktiv und nutzt das lokale CA-Bundle.
- CFTC-Klassen bleiben fachlich unverändert benannt. `Non-Reportables = Retail` und pauschale `Commercials/Dealer/Asset Manager = Smart Money` sind technisch und dokumentarisch ausgeschlossen.
- Normalisierte Beobachtungen enthalten Berichtstag, echten Erstabruf beziehungsweise verifizierten Veröffentlichungszeitpunkt, Markt-/Commodity-Code, Reporttyp, Open Interest, Long/Short/Net je Klasse, Quelle und Fingerabdrücke.
- Point-in-Time-Gate arbeitet fail-closed: historische Rückfüllungen ohne verifizierten Veröffentlichungszeitpunkt dürfen alte Signale nicht sehen. Später verfügbare Reports werden vor einem früheren Entscheidungszeitpunkt ausgeschlossen.
- Kausale Shadow-Merkmale berechnen 1W-/4W-Veränderung, historische Perzentile und Z-Scores nur aus damals verfügbaren Berichten; unterschiedliche Märkte und Reporttypen können nicht vermischt werden.
- Versioniertes Markt-Mapping und breite Asset-Kontextrouten ergänzt. US-/Europa-Aktien erhalten höchstens Index-Marktkontext; unbekannte Regionen/Instrumente bleiben `unmapped`. Die Auswahl mehrerer geeigneter Terminmärkte erfolgt outcome-blind nach aktuellem Open Interest.
- Append-only SQLite-Speicher mit Update-/Delete-Sperren, Inhaltsrevisionen, getrennten Shadow-Links und Integritätsprüfung umgesetzt.
- Vergleichsauswertung hält Champion und den rein simulierten Overlay-Fall getrennt und misst Fallzahl, Trefferquote, Durchschnitts-R, Profitfaktor, Drawdown, MFE und MAE. Das Overlay kann keine Swing-Regel, keinen Score, kein Gewicht und keine Freigabe verändern.
- Erster offizieller Rohbestand ab 2023: 60.859 CFTC-Beobachtungen, Integrität `ok`, keine Fehler, keine produktiven Verknüpfungen und keine rückwirkende historische Verfügbarkeitsbehauptung.
- Zehn gezielte Regressionstests und Python-Kompilierung erfolgreich. Kein Commit und kein Push.
- Offen bleiben: belastbarer historischer CFTC-Veröffentlichungskalender, automatische rein beobachtende Verknüpfung künftiger Swing-/Walk-Forward-Fälle, gereifte echte Forward-Vergleiche und eine spätere ausdrücklich manuelle Entscheidung über irgendeine Produktionsnutzung.
- Ursache des dokumentierten Walk-Forward-Abbruchs abschließend eingegrenzt: Der V4-Pilot und die später erweiterte Fallstruktur verwendeten für denselben logischen Kursfall dieselbe `case_id`, obwohl sich der vollständige Fall-Fingerabdruck durch neue Forschungsmetadaten geändert hatte. Der bestehende Append-only-Schutz erkannte dies korrekt, konnte den Shard aber nur vollständig zurückrollen und dadurch bei jedem Retry erneut blockieren.
- Walk-Forward-Schema 3 ergänzt eine allgemeine deterministische Konfliktrevision. Ein valider neuer Inhalt unter bereits belegter `case_id` erhält eine reproduzierbare neue Revisions-ID; alter und neuer Fall bleiben unverändert append-only erhalten. Ursache, alter/neuer Fingerabdruck und Auflösung werden in einer eigenen update-/delete-gesperrten Konflikttabelle protokolliert. Identischer Resume erzeugt weder eine zweite Fallrevision noch einen zweiten Konfliktdatensatz.
- Neue Forschungsfälle speichern getrennte `listing_id`, `issuer_id`/`company_id`, Identitätsquelle, ISIN-/Instrumentbezug, Anteilsklasse und Depositary-Receipt-Hinweis. Explizite IDs haben Vorrang; andernfalls wird ohne Ticker-Sonderregel konservativ aus Unternehmens-/Instrumentname und Listingmerkmalen abgeleitet. Legacy-Fälle bleiben bytegleich und erhalten die Information nur bei Auswertung aus dem Universum abgeleitet.
- Robustheitsauswertung clustert überlappende Ergebnisfenster derselben Strategie bei gemeinsamem Emittenten oder wirtschaftlich identischem Instrument. Share Classes, ADR/Stammaktie und Mehrfachlistings bleiben als einzelne Trades und Rohfälle sichtbar; zusätzlich werden rohe und effektiv unabhängige Fallzahl, Issuerzahl, abhängige Listingcluster und clusterrobuste Wilson-Trefferquote ausgewiesen. Mindestfall-, Segment-, Validation-/Holdout- und Pareto-Reifegates verwenden die effektive Evidenzzahl. Historische Trefferquote, R, Profitfaktor und Drawdown bleiben unveränderte Rohmetriken.
- Der ursprünglich fehlgeschlagene reale V2-Shard bleibt unverändert in der atomaren Kampagnenqueue, während ein anderer Shard aktiv war. Der exakte Konflikt-/Resume-Pfad wurde deshalb ohne Konkurrenz zur Forschungssperre in einer isolierten SQLite-Datenbank zweimal reproduziert: erste Wiederholung speichert genau eine Revision und einen Konfliktdatensatz, zweite Wiederholung null neue Datensätze; Audit `ok`, kein Überschreiben oder Löschen.
- Keine Strategieparameter, Entry-/Exit-Regeln, Stops, Targets, RSI-/EMA-Filter, Produktionsfreigaben, Broker- oder Echtgeldfunktionen geändert.
- Fünf neue Datenqualitäts-Regressionstests sowie alle bestehenden Walk-Forward-, Forward-, Resume-, Fingerprint-, Append-only- und Strategie-Freeze-Tests erfolgreich. Vollständige Testsuite: 497/497 erfolgreich; Python-Kompilierung der geänderten Module erfolgreich.
- Ausschließlich den Laufzeit-/Datenbereitstellungspfad der historischen Swing-Forschung optimiert. Development-/Validation-/Holdout-Fenster, A→B→C-Abhängigkeiten, Profile und eingefrorene Profilversionen, Shards, Fallauswahl, Purging, Kosten, Entry-/Exit-Regeln, Stops, Targets, Fallobergrenzen, Produktionssperren und Brokerlosigkeit blieben unverändert.
- Die bisher vier CPU-lastigen Threads wurden nach einem Ergebnisidentitäts-Benchmark durch sechs kontrollierte Prozesse ersetzt. Pro Kampagnenjob wird genau ein zentraler Pool über alle Batches wiederverwendet; der Hauptprozess bereitet Daten und Jobs vor, Worker analysieren nur disjunkte Assetgruppen und ausschließlich der Hauptprozess schreibt die zurückgegebenen Läufe seriell und in ursprünglicher Jobreihenfolge nach SQLite.
- Worker-Abschlussreihenfolge kann die Persistenzreihenfolge nicht mehr ändern. Ein Workerfehler wird mit Jobindex, betroffenen Tickern und `resume_required` sichtbar ausgegeben, löst keinen versteckten synchronen Fallback aus und lässt den Kampagnenjob unvollendet für einen späteren unveränderten Resume-Lauf.
- Finalisierten lokalen Parquet-/OHLCV-Datensatz pro Research-Epoch ergänzt. Ein Manifest umfasst das vollständige aktive Universum und alle Zeitfenster derselben festen beziehungsweise wöchentlichen Epochengruppe. Manifest, Einzelhistorien und vollständiger Dataset-Fingerprint werden validiert; nach Finalisierung greifen Jobs weder bei Cachemiss noch bei beschädigter Datei auf Yahoo zu, sondern brechen sichtbar fail-closed ab. Providerzugriff ist nur während einer neuen/noch nicht finalisierten Revision und nur für echte Cachelücken erlaubt.
- Jeder historische Lauf speichert Epoch-, Revisions-, Scope- und vollständigen Dataset-Fingerprint als eigenen Forschungsdatenvertrag, ohne Fallauswahl oder Fallfingerprints zu verändern. Die neue Kampagnenversion `swing-walk-forward-campaign-2026.08.18-v3` beginnt deshalb geschlossen auf einem gemeinsamen Freeze; bereits append-only gespeicherte V1/V2-Läufe und Fälle bleiben erhalten und werden nicht überschrieben oder gelöscht.
- Repräsentativer datenbankfreier Vergleich auf zwölf real gecachten Assets aus Kampagnenshard 4/8 mit allen vier unveränderten Basisprofilen und 270 resultierenden Fällen: vier Threads benötigten 167,712 s Wandzeit, 188,406 s gemessene aggregierte CPU-Zeit und 186,02 MiB Spitzen-RAM; sechs Prozesse benötigten 35,166 s, 178,234 s CPU-Zeit und 840,23 MiB Spitzen-RAM. Das entspricht 4,77-facher Beschleunigung beziehungsweise 79,0 % weniger Wandzeit bei identischem Gesamtfingerabdruck `22fb1ca1071628465425a5f282b17ce1e24dc210ef18231ff0612bb7a8725734`, identischen 270 Fällen und null Datenbankschreibvorgängen. Der deutlich höhere, aber auf dem 12-Logical-CPU-Rechner vertretbare RAM-Bedarf ist der dokumentierte Trade-off.
- Windows-Kampagnentask real auf eine tägliche `P1D`-Abdeckung mit `PT5M`-Wiederholung ab 00:00 Uhr erweitert. Registriert und lesend bestätigt sind `IgnoreNew`, globaler Forschungs-Lock, `WakeToRun`, `StartWhenAvailable` und `PT0S` ohne hartes Task-Laufzeitende. Verpasste Trigger können dadurch keinen parallelen Shard erzeugen; nach Freigabe des Locks nimmt der nächste zulässige Fünf-Minuten-Termin die Queue wieder auf.
- Asien/Australien um 10:30 Uhr besitzt nun ein zusätzliches Schutzfenster 10:30–11:30 Uhr und denselben konservativen 90-Minuten-Startpuffer; ab 09:00 Uhr startet daher kein neuer historischer Job. Die vorhandenen Fenster 17:15–18:45 und 21:30–23:59 blieben unverändert und sperren neue Starts weiterhin ab 15:45 beziehungsweise 20:00 Uhr. Ein laufender Forschungsjob wird an einer Fenstergrenze nicht beendet.
- Vor jedem Start prüft die Kampagne zusätzlich die echten Prozesslocks `swing_forward.scan.lock` und `forecasts.sqlite3.run.lock`, vor und nach Erwerb des globalen Research-Locks. Bei gleichzeitigem Aufwachen erhalten die Produktionsprozesse vor der ersten Lockprüfung fünf Sekunden Startvorrang. Ein aktiver Asien-/Europa-/Amerika-/Krypto-Scan oder Prognoselauf führt zu einem fail-closed Skip ohne Queue-/Versuchsmutation. Die produktiven Windows-Aufgaben wurden danach lesend unverändert auf 10:30, 18:15 und 22:30 Uhr mit `IgnoreNew`, `WakeToRun` und `StartWhenAvailable` bestätigt.
- Nachtstart, exakte 90-Minuten-Grenzen vor allen drei Produktionsketten, aktive Produktionslocks, nächster Queuejob, globaler Doppellaufschutz, Resume, Dataset-/Ergebnisidentität sowie alle bestehenden Campaign-/Append-only-/Walk-Forward-Pfade erfolgreich geprüft. Gezielte Suite: 38/38; abschließende vollständige Regression: 512/512 in 39,47 s. Strategie, Profile/Challenger, Assets, Fälle, Runden A/B/C, Purging, Kosten, Dataset-Fingerprint, Worker-Pool, serielle SQLite-Persistenz, echte Forward-Läufe und Brokerlosigkeit blieben unverändert.
- Beobachtenden RSI-/EMA-Layer für ausschließlich neu eingefügte historische Fälle umgesetzt. Die Featureversion `swing-observational-rsi-ema-2026.08.18-v1` speichert RSI14, EMA20/EMA50, drei relative Quotienten, normalisierte Abstände, Kurs-/EMA-Lage und den vollständigen Kurs-über-EMA20-über-EMA50-Zustand. Quelle ist der vorhandene einmalige Indikatorpass bis einschließlich der abgeschlossenen Signalkerze; Zukunftsbalken, zusätzliche Downloads und ein zweiter Datenlauf sind ausgeschlossen.
- Neue Werte liegen in einer eigenen update-/delete-gesperrten Sidecartabelle und sind ausdrücklich nicht Bestandteil des bestehenden Fallpayloads oder seiner Identität. Fall-ID, Fall-Fingerprint, Baseline-Snapshot, Ergebnis, Entry/Stop/Targets/Kosten, Auswahl und Freigabe bleiben daher unverändert. Nur der serielle Hauptprozess schreibt Features atomar zusammen mit einem tatsächlich neuen Fall; ein Retry/Resume oder ein bereits gespeicherter beziehungsweise beim Rollout laufender Fall wird nicht nachträglich aufgefüllt und bleibt als `legacy_feature_not_recorded` lesbar.
- Rollout ohne Unterbrechung der aktiven Kampagne real belegt: Shard 1/248 war vor dem Feature-Rollout bereits beendet und bleibt unverändert Legacy; Shard 2/248 lief ohne Neustart weiter und hatte nach seinem ersten 100er-Batch 2.031 neue Feature-Sidecars seriell gespeichert. Der eingefrorene Dataset-Fingerprint blieb `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`; Queue und Shardfortschritt wurden nicht zurückgesetzt oder erweitert.
- Rein beschreibende Segmentauswertung einschließlich fester RSI-Bereiche, EMA-/Kursrelationen, Pullback/Breakout-Kreuzungen, Marktphase und Volatilität ergänzt. Fallzahl, Durchschnitts-R, Profitfaktor, Trefferquote und maximaler Drawdown werden je Segment insgesamt sowie getrennt nach Development, Validation und Holdout gezeigt; unter 50 effektiv unabhängigen Ergebnissen erscheint immer der Kleinstichprobenhinweis. Automatische Schwellenwertsuche, Regeländerung, Holdout-Selektion und Produktionsfreigabe sind fest `false`.
- Vertrag für einen möglichen späteren Challenger nur als gesperrte Vorlage dokumentiert: manuelle Hypothese, vorab eingefrorene Regel, eigener Strategie-Fingerprint, neue hypothetische Trades, getrennte Speicherung und neue Research-Epoch beziehungsweise frischer Walk-Forward-Lauf sind verpflichtend; die jetzige Beobachtung ist keine Bestätigungsevidenz. Kampagnenkonfiguration, Profile, bestehende Challenger, Queue mit 248 Jobs, Assets, Fälle, Runden A/B/C, Dataset-Fingerprint und Produktionsstrategie blieben unverändert. Gezielte Feature-/Walk-Forward-/Campaign-Prüfung: 47/47 erfolgreich; vollständige Regression: 516/516 in 86,22 s.

### 2026-08-17

Änderungen:

- Historische Forschungsplanung auf drei vorab gelockte, voneinander abhängige Testrunden A/B/C erweitert. Jede Runde enthält pro Asset und Strategie höchstens sechs nicht überlappende Signale aus 2010–2015 und sechs aus 2016 bis heute, also höchstens zwölf neue Fälle und nach allen drei Runden höchstens 36. Runde B bleibt bis zum vollständigen Abschluss von A blockiert, C bis zum vollständigen Abschluss von B. Die Auswahl rekonstruiert und reserviert frühere Rundensignale ohne Verwendung späterer Ergebnisse; identische oder überlappende 25-Sitzungs-Fälle können nicht erneut in eine Folgerunde gelangen.
- Profilversionen der drei Runden vorab eingefroren. Eine spätere Änderung an Schwellen oder Engine bricht den betroffenen Kampagnenjob sichtbar ab, statt verschiedene Strategiestände in einer Testreihe zu vermischen. Kampagnenstatus, Zusammenfassung, Archiv und Oberfläche weisen A/B/C getrennt aus; aktuelle wöchentliche Ergänzungen bleiben eigenes Monitoring.
- Vollständigen V3-Basislauf beendet: 2.518/2.520 Assets geladen, 21.179 neue historische Fälle, zwei isolierte Providerfehler (`CWEN-A`, `SVA`). 21.299 eindeutige V3-Fälle enthalten 11.158 R-Ergebnisse mit 18,63 % positiven Abschlüssen, +0,027 R im Durchschnitt und Profitfaktor 1,029. Negative Validation und großer sequenzieller Forschungs-Drawdown verhindern ausdrücklich jede Freigabe.
- Rotierende V5-Forschungskampagne ergänzt: zwölf feste Forschungsvarianten werden als drei gemeinsame Datenverträge mit jeweils vier Strategieschwellen ausgeführt. Die getrennten Epochen 2010–2015 und 2016 bis heute sowie wöchentlich die jüngsten gereiften Fälle bleiben enthalten. Acht diversifizierte Shards, der vorhandene Cache und die gemeinsame Indikatorberechnung verkürzen die Startwarteschlange von 96 auf 24 Jobs; ein atomarer Status setzt nach Unterbrechung fort.
- Evidenzidentität gegen künstliche Datenvermehrung gehärtet: Abrufstichtag und Samplingmodus können denselben fachlichen Fall nicht mehrfach in Kennzahlen einbringen. Echte Datenkorrekturen bleiben als append-only Revision nachvollziehbar.
- Windows-Kampagnenaufgabe mit 15-Minuten-Startraster zwischen 11:05 und 22:05 Uhr, `IgnoreNew`, gemeinsamer Forschungssperre, Aufwecken und Nachholen registriert. Schutzfenster 17:15–18:45 sowie 21:30–23:59 schützen reale Scans/Abendprognosen; zusätzlich startet in den jeweils 90 Minuten davor kein neuer Forschungsjob. Der erste V1-Pilotshard wurde von 15:32 bis 15:52 Uhr erfolgreich abgeschlossen: 313 Historien geladen, zwei Providerfehler isoliert und 2.540 neue V4-Fälle append-only gespeichert. Danach wurde die gleichwertige Warteschlange auf 24 gebündelte V2-Jobs verkürzt; die stabile Evidenz-ID verhindert Doppelzählung des Pilotbestands.
- Der globale Summary- und Integritätsscan wird zur Laufzeitersparnis nicht mehr nach jedem Shard, sondern gebündelt nach dem letzten der acht Shards eines Vertrags ausgeführt. Die Datenbankprüfung bleibt damit verbindlich, ohne jeden Teiljob mit einem immer größeren Gesamtscan zu belasten.
- Gebündelten Vier-Profil-Pfad mit zwei echten Cache-Historien separat geprüft: 2/2 Assets geladen, null Fehler, 16 Fälle gespeichert und SQLite-Quick-Check `ok`. Der erste große V2-Job über 315 Assets deckte danach einen Versionskonflikt zwischen älteren V4-Pilotfällen und der erweiterten Fallstruktur auf; der append-only Schutz brach vor jeder produktiven Datenänderung ab. Engine/Forschungsvertrag wurden auf V5/V4 angehoben und mit derselben Alt-/Neu-Testdatenbank erfolgreich nachgewiesen. Produktive Datenbank unverändert integer mit 128 Läufen und 24.135 Fällen.
- Append-only Cross-Store-Verknüpfung zwischen historischen und echten Forward-Fällen ergänzt. Exakte Gleichheit verlangt kompatibles Listing/Ticker, denselben Signalkerzentag, Setup, Richtung und normalisierten Originalwährungs-Ausführungsplan. Dann erhält der echte Forward-Fall Vorrang und der historische `recent_incremental`-Fall zählt nicht ein zweites Mal im aktuellen Monitoring. Abweichende Strategien oder Pläne bleiben als verwandte eigenständige Experimente erhalten.
- Verknüpfung automatisch nach historischen Kampagnen-Shards sowie regionalen und manuellen echten Forward-Scans aktiviert. Die UI zeigt exakte, verwandte und ausgeschlossene Doppelzählungen. Beide Quellen bleiben unverändert und getrennt; historische Evidenz wird nie als echter Forward-Fall umgedeutet.
- Walk-Forward-Datenbank vor der Erweiterung online gesichert und nicht löschend auf Schema 2 migriert. 128 Läufe und 24.135 Fallrevisionen besitzen vor und nach der Migration dieselben Identitäts-Fingerabdrucksummen; Quick-Check `ok`, null ungültige Datensätze. 24.039 eindeutige historische Fälle und 19 echte Forward-Signale besitzen derzeit noch keinen gemeinsamen Signalkerzentag, daher korrekt null Verknüpfungen.
- Historischen Swing-Walk-Forward-Test zu einem breiten, wiederaufnehmbaren V3-Forschungsbetrieb ausgebaut. Die CLI verwendet ohne Tickerauswahl alle 2.520 aktiven Swing-Assets, parallele 100er-Batches, split-/dividendenbereinigte Tagesdaten, lokalen Parquet-Cache, isolierte Providerfehler und einmalig je Asset berechnete kausale Indikatoren.
- Rechenintensive Assetanalyse innerhalb jedes 100er-Batches auf vier getrennte Worker verteilt. Die Windows-Aufgabe verwendet dafür stabile Threads; ein manueller Prozessmodus ist optional. Alle Worker bearbeiten disjunkte Assetgruppen ohne Datenbankzugriff, ausschließlich der Hauptpfad speichert die Ergebnisse nacheinander in SQLite.
- Forschungsdesign gegen Scheinergebnisse gehärtet: feste Development-/Validation-/Holdout-Zeitfenster, kalenderjahr- und splitbalancierte Fallauswahl je Asset, technisch erzwungenes letztes Signaldatum, Purging an Fenstergrenzen, keine überlappenden 25-Sitzungs-Labels desselben Assets, vollständige OHLCV-Fingerabdrücke, deterministisch balancierte Fallbegrenzung und versionierte Schwellenprofile.
- Revisionssichere Fallidentität ergänzt: Eine logische ID beschreibt den Forschungsfall, eine zweite append-only ID bindet ihn an exakt die bis zu seinem Ergebnis verwendeten Kursdaten. Nachträgliche Providerkorrekturen bleiben erhalten; Zusammenfassungen zählen nur die neueste Revision und vermeiden Doppelgewichtung.
- OHLCV-Fingerabdruck auf ein einheitliches Datums- und Float64-Format normalisiert, damit identische Cache-/Netzwerkdaten trotz unterschiedlicher Speicherdatentypen dieselbe Identität behalten. Ein paralleler Zehn-Asset-Test speicherte im ersten Durchlauf 120 und im identischen zweiten Durchlauf null neue Fälle.
- Kennzahlen und UI erweitert: Wilson-Intervall, Trefferquote, Durchschnitt/Median in R, Profitfaktor, Drawdown, Asset-/Signaltagsabdeckung, Marktphasen, Strategievergleich und die neuesten 500 Einzelfälle sind getrennt sichtbar. Abgeleitete `balanced`-, `precision`- und `payoff`-Hypothesen müssen vor jeder fachlichen Prüfung als eigene Version erneut gelockt werden.
- Technisches Research-Gate verlangt 1.000 eindeutige Ergebnisse, 200 Assets, je 200 Validation-/Holdout-Fälle, ausreichende Marktphasensegmente, überlappungsfreie Labels und verifizierte angepasste Kurse. Es erlaubt höchstens die manuelle Prüfung eines technischen Shadow-Challengers; vollständige Swing- oder Produktionsänderung bleibt gesperrt.
- Reale V2-Probe mit zehn Assets: 10/10 Historien geladen, 120 neue Fälle, 64 eindeutige R-Ergebnisse, 18,75 % positive Quote, +0,010 R im Durchschnitt, Profitfaktor 1,011 und Drawdown 26,52 R. Dieser kleine Stand ist nicht freigabereif. Walk-Forward-Datenbank danach zwei Läufe und insgesamt 200 unveränderte Fälle, Integrität/Fingerabdrücke `ok`.
- Reale V3-Probe mit zehn Assets: 10/10 Historien geladen, null Providerfehler, 120 aktuelle Fälle und 61 eindeutige R-Ergebnisse über alle drei Zeitfenster. 16,39 % positive Quote, +0,074 R im Durchschnitt, Profitfaktor 1,080 und Drawdown 15,79 R sind weiterhin keine belastbare Freigabegrundlage.
- Windows-Aufgabe `InvestmentAssistantSwingWalkForward` wöchentlich Samstag 11:00 Uhr registriert und lesend bestätigt: `Ready`, aktiviert, nächster Lauf 2026-08-22 um 11:00 Uhr, Aufwecken und verspäteter Start aktiv. Sie führt keine Order und keine automatische Regeländerung aus.
- Erster vollständiger V3-Lauf über 2.520 Assets am 2026-08-17 um 13:09 Uhr im Windows-sicheren Vier-Thread-Modus gestartet und nach Überschreiten des zuvor instabilen Prozesspool-Startpunkts weiter aktiv. Der planmäßige Wochenstart bleibt Samstag 11:00 Uhr.
- Feste Drei-Trade-Grenze durch dynamische Portfoliokapazität ersetzt: 0,50 % Risiko je Trade, 2,00 % offenes Gesamtrisiko, 50 % Kapitalbindung und 20 % je Position. Der aktuelle nachgezogene Stop bestimmt das noch belegte Risiko; alle fachlich geeigneten Signale bleiben unabhängig davon als Paper-/Forward-Evidenz erhalten.
- Bestehende Paper-, Forward- und historische Legacy-Daten blieben unverändert erhalten. Kein Commit und kein Push.

Tests:

- Neue Rundentests bestätigen unveränderte Runde-A-Auswahl, exakt getrennte A/B/C-Fälle, mindestens 25 Sitzungen Abstand, Abhängigkeitsreihenfolge, Zwölferkapazität je Gesamtrunde und eingefrorene Profilversionen. Vollständige Testsuite: 472/472 erfolgreich; Kompilierung, Repository-Sicherheitscheck und Offline-Smoke-Test ebenfalls erfolgreich.
- Gezielte Walk-Forward-, Scanner-, Positionsgrößen- und Trade-Republic-Tests erfolgreich.
- Reale Netzwerk-/Cache-/SQLite-Probe erfolgreich; Walk-Forward-Audit Schema 2, Quick-Check `ok`, null ungültige Fingerabdrücke.
- Vollständige Testsuite nach V5-Kampagnenausbau, Profilbündelung, Versionskorrektur und Cross-Store-Verknüpfung: 469/469 erfolgreich. Repository-Sicherheitscheck `OK`; Kompilierung und Offline-Smoke-Test erfolgreich. Forschungsdatenbank: 128 Läufe, 24.135 append-only Fallrevisionen, Quick-Check `ok`, null ungültige Fingerabdrücke.

Git:

- Branch `main`, Commit unverändert `b6698c0bdcfa0565f10df1be16fc1b53927022e7`.
- Lokale Änderungen nicht committet und nicht gepusht.

### 2026-08-16

Änderungen:

- Swing-Forward-Datenbestand aktuell geprüft: 41 append-only Scans, 14 Signale, nach der erweiterten Aktivmessung 37 Ereignisse, Datenbankintegrität `ok` und null ungültige Datensätze.
- Aktueller Paper-Stand: sechs ausgelöste Einstiege, davon fünf aktiv und einer eindeutig mit Verlust beendet; außerdem drei verpasste Einstiege, ein vor Einstieg ungültiges Signal und vier noch nicht aktivierte gespeicherte Signale. Ein abgeschlossener Fall reicht nicht für eine belastbare Trefferquote.
- Der eigenständige Forward-Runner richtet den yfinance-Cache jetzt selbst auf den lokalen Projektcache aus und verwendet bei einem Schreibproblem einen temporären Fallback. Er ist damit nicht mehr davon abhängig, dass zuvor die Streamlit-App gestartet wurde.
- Wiederholbare Providerfehler bleiben als technische Ereignisse erhalten, überschreiben aber nicht mehr den fachlichen Signalstatus. Aktive Trades bleiben aktiv und noch nicht ausgelöste Signale gespeichert; echte nicht auswertbare Marktverläufe behalten weiterhin `not_evaluable`.
- Unterschiedliche Providerfehler am selben Tag werden über einen Fingerabdruck im Ereignisschlüssel konfliktfrei gespeichert; identische Wiederholungen bleiben idempotent.
- Der Europa-Hintergrundscan vom 2026-08-16 um 18:15 Uhr war mit 73/73 Assets, null Fehlern, null Rate-Limits und Status `ok` erfolgreich. Der reale Forward-Nachlauf enthielt keine neue abgeschlossene Marktsitzung und erzeugte daher korrekt kein neues Ergebnis.
- Neun retry-fähige Hinweise aus einem isolierten Netzwerk-/Cache-Fehlversuch bleiben transparent append-only gespeichert. Eine anschließende erfolgreiche Wiederholung lieferte null Daten- und Auswertungsfehler; bestehende Scans, Signale und Ergebnisse wurden weder gelöscht noch rückwirkend verändert.
- Alle fachlich qualifizierten Setups werden ab künftigen Scans objektiv weiterverfolgt. Tatsächlich für das Nutzerportfolio freigegebene Signale und nur wegen Höchstzahl/Positionsberechnung zurückgehaltene Shadow-Signale besitzen getrennte unveränderbare Evidenzarten, Archive und Ergebnisgruppen; dadurch werden weder Nutzertrades erzwungen noch Statistiken vermischt.
- Verpasste, vor Einstieg ungültige und abgelaufene Signale erhalten nach 5 und 20 weiteren abgeschlossenen Sitzungen eine separate Kontrollrendite mit MFE/MAE. Sie bleibt `kein Trade-Ergebnis`; die vier vorhandenen Kontrollfälle sind noch nicht gereift und verändern die aktuelle Trefferquote nicht.
- Die fünf aktiven Papertrades besitzen nun laufende kostenbereinigte Zwischenwerte in Prozent und R, MFE/MAE sowie Stop-/Zielabstände. Der reale Nachlauf erzeugte fünf neue append-only Aktivmessungen ohne Fehler oder Datenlöschung.
- Marktphase, Volatilitätsregime, Evidenzart und Portfoliofreigabe sind im Archiv filterbar und segmentiert. Ein neuer rein beobachtender Cluster-Audit misst Branchen-/Regionshäufung und 60-Sitzungs-Korrelation qualifizierter Kandidaten, ohne automatische Ablehnung oder Gewichtung.
- Getrennten historischen technischen Walk-Forward-Test mit wachsendem Vergangenheitsfenster, Leakage-Schutz, Fingerabdrücken und eigener append-only Datenbank `runtime/swing_walk_forward.sqlite3` umgesetzt. Er besitzt keine historischen Fundamental-, News-, Makro- oder TR-Ausführungsdaten und ist deshalb ausdrücklich nicht produktionsvergleichbar.
- Erste reale Fünfjahres-Stichprobe für zehn liquide Aktien gespeichert: 80 historische technische Shadow-Fälle, 47 eindeutige R-Ergebnisse, davon 10 positiv und 37 nicht positiv; positive Quote 21,28 %, Durchschnitt +0,378 R. Diese begrenzte technische Kontrollmessung darf weder als echte Forward-Trefferquote noch als Freigabe zur Regeländerung verwendet werden. Datenbankintegrität `ok`.
- Manuelles Swing-Lern-Gate ergänzt: mindestens 100 eindeutige echte Forward-Ergebnisse, zwölf Beobachtungswochen und mindestens 20 Ergebnisse je vorhandener Asset-, Marktphasen-, Volatilitäts- und Versionsgruppe. Aktuell 1/100 und sechs Beobachtungstage; historische Walk-Forward-Fälle zählen nie dazu. Automatische Regel- und Gewichtsänderungen bleiben gesperrt.
- Reproduzierbare Kontrollgruppe für bereits in der Tiefenanalyse abgelehnte Kandidaten ergänzt. Je Scan werden maximal fünf Fälle über einen stabilen SHA-256-Samplingschlüssel ausgewählt und mit Ausgangskurs, Marktphase, Volatilität, Datenqualität sowie Ablehnungsfiltern append-only gespeichert. Nach 5 und 20 Sitzungen folgen Rendite und MFE/MAE als reine Kontrollwerte; es entstehen weder Orderplan noch Signal oder Trade-Ergebnis.
- Swing-Forward-Datenbank nicht löschend von Schema 1 auf Schema 2 erweitert. Bestehende 41 Scans, 14 Signale und 37 Ereignisse blieben unverändert und gültig; neue Tabellen für Ablehnungsproben und ihre Ereignisse sind leer, bis der nächste reale Scan sie automatisch füllt. Quick-Check `ok`, null ungültige Fingerabdrücke.

Tests:

- 12 gezielte Tests für Forward-Runner und -Statistik bestanden, einschließlich Cache-unabhängigem Betrieb, idempotenter gleicher Fehler, konfliktfreier unterschiedlicher Fehler und stabiler Lebenszyklusstatus.
- Vollständige Testsuite 439/439 bestanden. Repository-Sicherheitscheck und Offline-Smoke-Test mit Kompilierung, Streamlit-Start und lesbarer lokaler Lernhistorie ebenfalls erfolgreich.
- Abschluss nach Shadow-, Kontroll-, Aktivmessungs-, Cluster-, Ablehnungsstichproben- und Walk-Forward-Ausbau: 453/453 Tests bestanden. Repository-Sicherheitscheck sowie Offline-Smoke-Test mit Kompilierung, Historienqualität und Streamlit-Start erfolgreich. Produktive Swing-Forward-Datenbank und getrennte Walk-Forward-Datenbank jeweils Integrität `ok`.

Git:

- Aktiver Branch `main`; bestehende umfangreiche lokale Änderungen wurden bewahrt.
- Kein Commit und kein Push.

### 2026-08-11

Änderungen:

- Windows-Zeitplanung auf ein tägliches Ausschaltfenster von 00:00 bis 10:00 Uhr umgestellt. Asien/Australien bleibt 10:30 Uhr, Europa 18:15 Uhr und Prognosen 22:30 Uhr.
- Neue feste Abendkette `scripts/run_evening_pipeline.cmd` registriert: Prognosen laufen zuerst, danach Amerika/Global, danach Krypto. Jede Stufe wird getrennt protokolliert; auch bei einem Fehler einer Stufe werden die folgenden Stufen versucht und der erste Fehlercode bleibt sichtbar.
- Separate Aufgaben `InvestmentAssistantSwingScan-america_global` und `InvestmentAssistantSwingScan-crypto` entfernt. Die 22:30-Aufgabe zeigt `Ready`, verwendet die Abendkette und behält `StartWhenAvailable`; Asien- und Europa-Aufgabe bleiben ebenfalls `Ready`. Es wurden keine Prognose-, Paper- oder Forward-Daten verändert.
- Trade Republic als verbindliche Ausführungs-/Referenzebene des Swing-Nutzerbereichs umgesetzt. Normal angezeigt werden nur listing-spezifisch verifizierte TR-Instrumente; unbekannte oder nicht handelbare Listings bleiben vollständig unter `Nur Paper / nicht bei Trade Republic handelbar` sowie im unveränderten Forward-/Lernbestand.
- Append-only SQLite-Referenz `runtime/trade_republic_reference.sqlite3` ergänzt. Statuswerte sind exakt `TR handelbar`, `TR nicht handelbar` und `unbekannt`; Ticker, Börsenplatz, Währung und ISIN bilden die konkrete Listingidentität. Manuelle dauerhafte ISIN-/TR-Zuordnung ist möglich, abweichende ADR-/GDR-/Instrument-ISINs werden hart abgelehnt.
- Strikte Preis- und Plantrennung umgesetzt: `Aktueller Preis` ist ausschließlich ein höchstens 15 Minuten alter, manuell für das verknüpfte TR-Listing erfasster EUR-Preis. Ein zeitgleich erfasster Analyse-Vergleichskurs bildet nur die Listing-Basis; ältere technische Marken werden nicht am aktuellen Preis neu verankert. Fehlt eine Seite, zeigt die Anwendung `TR-Preis nicht verfügbar` beziehungsweise keinen ausführbaren Plan; Yahoo wird weder still verwendet noch als TR-Preis beschriftet. Limit, Maximalpreis, Stop, Ziele, Stückzahl und EUR-Beträge werden gemeinsam auf dasselbe per ISIN verifizierte TR-Listing übertragen und mit getrennten Analyse-/Ausführungsquellen dokumentiert.
- Persönliche Nutzertrades verlangen jetzt zwingend einen ausführbaren TR-Plan mit gleicher ISIN, konkretem Handelsplatz, EUR-Preis und Nicht-Yahoo-Quelle. Auch die laufende Nutzertrade-Bewertung nutzt für aktuellen Preis und Gewinn/Verlust keinen Yahoo-Ersatz; Yahoo bleibt ausschließlich technischer Markt-/Chartkontext.
- Forward-Snapshots speichern den zum Signalzeitpunkt bekannten TR-Status und eine gegebenenfalls vorhandene getrennte Ausführungsreferenz, ohne ältere Signale umzuschreiben. Archiv und Oberfläche trennen Scannerqualität gesamt, TR-handelbare Listings, tatsächlich vollständige TR-Ausführungspläne und Paper-only-Ergebnisse.
- Arbeitsreihenfolge auf ausdrücklichen Nutzerwunsch aktualisiert: zuerst Swing Trade Finder, danach effizientere Prognosehorizonte; andere Roadmap-Punkte bleiben nachgeordnet, außer kritischen Stabilitäts-, Datenintegritäts- oder Falschergebnisfehlern.
- Feste 60er-Grenze aus `SwingPrefilterThresholds` und der Scannerpipeline entfernt. Jeder bestandene Grobfilterkandidat wird tief analysiert; Last wird nicht mehr durch stilles Top-N-Abschneiden reduziert.
- Versionierten Assetklassen-Funnel ergänzt: Universum, geladen, Grobfilter bestanden, tief geprüft, Setup bestanden und Portfoliofreigabe werden je Aktie, ETF und Krypto gespeichert und in den erweiterten Einblicken gezeigt.
- Neutralen ETF-/Aktien-Bias-Audit ergänzt. Der große Echtlauf ergab 58,0 % Grobfilterquote bei ETFs und 14,48 % bei Aktien, Verhältnis 4,006. Dies ist ausdrücklich nur ein Messhinweis ohne Kausalbehauptung und ohne automatische Gewichtsänderung.
- ETF-Bias exakt zerlegt: Im Baseline-Reallauf erklärten Setup-Struktur und Aufwärtstrend praktisch die gesamte Grobfilterdifferenz; das Rohvolumen lehnte ETFs anteilig sogar etwas häufiger ab. Im Finalfilter scheiterten 50 Aktien, aber nur ein ETF zusätzlich am nicht vergleichbaren Asset-Qualitäts-Hard-Gate; 20 von 29 tief geprüften ETFs scheiterten erst an der präzisen Setup-Struktur.
- Filterneutralität umgesetzt: Grobfilter-Setupzonen sind ATR-normalisiert, absolute Stückzahlgrenzen durch eine reine Volumenabdeckungsprüfung ersetzt und der finale EUR-Umsatzcheck beibehalten. Langfristige Asset-Qualität ist kein Swing-Hard-Gate und kein Rangfaktor mehr. Es gibt keine Klassenquote und keine automatische Gewichtung.
- Nicht speichernder Nachher-Reallauf über Amerika/Global: 2.350/2.352 Assets geladen, Aktien-Grobfilter 319/2.300 beziehungsweise 13,87 %, ETF-Grobfilter 7/50 beziehungsweise 14,00 %, Differenz 0,13 Prozentpunkte. Alle 326 Treffer wurden tief geprüft; zwei Aktien und kein ETF bestanden final. Die Verringerung von 29 auf 7 ETF-Tiefenanalysen beseitigte die gemessenen ETF-False-Positives, ohne Aktien zu bevorzugen.
- Strategie auf `swing-long-pullback-breakout-2026.08.11-v3` und Orderplan zuletzt auf `swing-order-plan-2026.08.11-v3` versioniert. Der Orderplan speichert nun zusätzlich eine ausdrücklich nicht als TR-Kurs geltende Analysepreisreferenz für die getrennte TR-Übertragung. Der Forward-Vergleich zeigt Trefferquote, R, Profitfaktor und Drawdown erst ab mindestens 20 eindeutigen v3-Ergebnissen je Aktie und ETF; aktuell sind beide Klassen noch bei null gereiften v3-Fällen.
- Abschlussaudit der privaten Swing-Datenbank: Schema 1, Quick-Check `ok`, 21 echte gespeicherte Scans, vier v1/v2-Signale (EWL, LT.NS, BANR und JBL), drei Ereignisse und null ungültige Fingerabdrücke. Der um 22:21 Uhr separat gespeicherte `manual_full`-v2-Lauf mit BANR/JBL bleibt von den drei nicht gespeicherten Bias-Kontrollläufen und der neuen v3-Auswertung getrennt.
- Swing-Universum reproduzierbar auf 2.520 eindeutige Assets erweitert: 2.431 Aktien, 59 ETFs und 30 Kryptowährungen. Zusatzquelle sind ausschließlich reguläre Titel des offiziellen Nasdaq Global Select Market; ServiceNow bleibt enthalten.
- Alle vier Regionalbereiche real mit der neuen Pipeline ausgeführt: Amerika/Global 2.350/2.352 in 327,36 Sekunden, Asien/Australien 65/65, Europa 73/73, Krypto 29/30; alle Status `ok`, null Rate-Limits, SQLite-Integrität `ok`, Orders deaktiviert.
- Alle 362 Amerika/Global-Grobfiltertreffer vollständig tief geprüft. Kein Setup wurde erzwungen. Im Asien-Lauf wurde LT.NS als zweites echtes append-only Forward-Signal neben EWL gespeichert.
- Sichtbaren Regionalrandfall korrigiert: Neue Orderpläne können keinen frühesten Einstieg vor dem tatsächlichen Scanzeitpunkt mehr nennen. Der bereits gespeicherte LT.NS-Snapshot wurde nicht verändert; die Forward-Auswertung schloss schon vorher alle Balken bis einschließlich Signalzeitpunkt aus.
- Kritische Zeitreise-Lücke bei persönlichen Nutzertrades geschlossen: Ein bestätigter Einstieg muss jetzt strikt nach dem unveränderbar gespeicherten Signalzeitpunkt liegen und kann diese Grenze auch mit einer Abweichungsbestätigung nicht umgehen. Bestehende Signale und Nutzertrade-Daten wurden nicht verändert.
- Kritischen LT.NS-/GDR-Kursbasisfehler untersucht und zentral abgesichert: `LT.NS` ist das analysierte indische INR-Listing, während `USY5217N1183` ein anderes GDR-Instrument bezeichnet. Veraltete regionale Tageskerzen und widersprüchliche OHLC-Daten werden nun vor Setup- und CRV-Freigabe als `nicht handelbar bestätigt` abgelehnt. Bekannte Tickersuffixe wie `.NS`, `.HK`, `.T` und `.AX` verwenden konservative listingnahe Börsenzeiten.
- Swing-Karten zeigen jetzt `Signalkurs (Schluss)` statt eines irreführenden aktuellen Kurses sowie analysiertes Listing, Börsenplatz, Originalwährung, Quelle und Signaltag. Fremdwährungsumrechnungen werden ausdrücklich nicht als Trade-Republic-/LS-Exchange-Livekurs dargestellt.
- Die lokale Bestätigung eines extern ausgeführten Trades verlangt einen zum analysierten Listing passenden Ticker oder eine passende ISIN. Andere Listings sowie ein tatsächlicher Einstieg auf oder unter dem unveränderbaren System-Stop können nicht durch eine allgemeine Abweichungsbestätigung freigegeben werden.
- Swing-Strategieversion auf `swing-long-pullback-breakout-2026.08.11-v2` angehoben und die Reihenfolge gleichzeitiger Terminal-/FX-Ereignisse semantisch stabilisiert.
- Neue Prognosehorizonte mit `forecast-horizon-calendar-2026.08.11-v1` entkoppelt: 1W wöchentlich, 1M alle zwei Wochen, 3M monatlich, 6M alle drei Monate und 12M alle sechs Monate.
- 6M/12M werden nur bei versioniert dokumentierter Langfristeignung gestartet. Das Evidenzgate prüft Historienlänge, Datenqualität, Assetqualität, gültigen EUR-Preis und bei Krypto zusätzlich Stablecoin-Eignung. Fehlende Eignung ist kein negatives Investmenturteil.
- Messvertrag auf v4 erweitert und gleichzeitig die gültigen v3-Verträge rückwärtskompatibel erhalten. Produktionsdatenbank rein lesend bestätigt: 2.270 Prognosen, 523 Auswertungen, 325 gültige Messverträge, 1.945 Legacy-Datensätze, null ungültige Verträge, Schema 9, Integrität `ok`.
- `ROADMAP.md` und PLDatei auf tatsächlichen Umsetzungsstand, reale Messwerte und weiterhin offene Forward-Reifung aktualisiert.

Tests:

- 38 Forecast- und Swing-Hintergrundtests bestanden. Registrierte Aufgaben anschließend real geprüft: nächste Läufe 10:30, 18:15 und 22:30; keine separate Aufgabe um 00:30 oder 02:15.
- Vollständige Suite nach der TR-Ausrichtung: 437/437 Tests bestanden.
- 28 gezielte TR-Referenz-, Nutzertrade- und Forward-Statistiktests bestanden; darunter sicherer `unbekannt`-Standard, gleiche/abweichende ISIN, mehrere Listings, manuelle ISIN-Ergänzung, Preisverfall ohne Yahoo-Fallback, einheitlicher TR-Plan, append-only Schutz und getrennte Gesamt-/TR-/Paper-Statistik.
- Repository-Sicherheitscheck und Offline-Smoke-Test einschließlich Kompilierung und Headless-Streamlit-Start erfolgreich.
- 71 zusammenhängende Scanner-, Hintergrundlauf-, Kursbasis-, Listing-, Swing-Trade- und Nutzertrade-Prüfungen bestanden; darunter der reproduzierte LT.NS-Stale-Bar-Fall vom 2026-08-11, widersprüchliche Tageshoch/-tief-Werte, US-/EU-Einzelnotierungen, eine fremde GDR-ISIN und ein Einstieg auf der falschen Seite des Stops. Kompilierung von `trading_assistant.py`, `swing_user_store.py` und `app.py` erfolgreich. Parallel entstandene Scanner-Änderungen wurden kompatibel zusammengeführt.
- Kompilierung der Anwendung, geänderten Module, Skripte und Tests erfolgreich.
- Repository-Sicherheitscheck erfolgreich.
- `git diff --check` ohne Inhaltsfehler; nur vorhandene Windows-Zeilenendehinweise.
- Marktfreie Swing-Vorprüfung: 2.520/2.520 Assets genau einem Bereich zugeordnet, keine Überschneidung, Datenbank-Quick-Check `ok`.
- Marktfreie Prognose-Vorprüfung: Wochenuniversum 1.726, Datenbank- und Messvertragsstatus `ok`, keine Marktdaten angefordert, keine Prognosen geschrieben, keine Daten gelöscht.

Git:

- Aktiver Branch `main`; bestehende umfangreiche lokale Änderungen wurden bewahrt.
- Kein Commit und kein Push.

### 2026-08-09

Änderungen:

- PL-Priorität auf ausdrücklichen Nutzerwunsch mit `ROADMAP.md` synchronisiert: zuerst realer Wochen-Scan, Forward-Auswertung und messbare Prognosepräzision; direkt danach der Swing Trade Finder als wichtigste Nutzerfunktion; Design, Long-Term-Ausbau, `Investment Opportunities` und Komfortarbeit folgen später. Kritische Stabilitäts-, Datenschutz-, Datenintegritäts- oder Falschergebnisfehler bleiben die einzige blockübergreifende Ausnahme.
- Produktionsstand geprüft: Windows-Aufgabe bereit, letzter Lauf 2026-08-08 mit 325/325, null Fehlern, null Rate-Limits und Rückgabecode 0; nächster Termin 2026-08-09 um 22:30 Uhr. SQLite integer mit 1.945 Prognosen, 9.725 Zeiträumen und vor dem Termin null Auswertungen.
- Fällige Kursdatenabfrage auf begrenzte Batches umgestellt; historischer FX-Kurs wird je Währung und Bewertungstag geteilt. Auswertungs-Rate-Limits fließen in die Laufmetriken ein.
- L0-Point-in-Time-Vertrag für neue Snapshots umgesetzt: Beobachtungszeitpunkt, Feature-/Label-/Benchmark-/Kosten-/Qualitätsvertrag, Leakage-Schutz und SHA-256-Fingerabdruck. Legacy-Daten werden nicht rückwirkend angereichert.
- Separates versioniertes Wochenuniversum mit 1.726 gültigen Assets erstellt. Der 325er Referenzkern ist Montag zugeordnet, die Erweiterung Dienstag bis Freitag. Tägliche Fälligkeitsprüfung und wöchentliche Neuprognose sind getrennt; Start ist 2026-08-10.
- Nicht löschende SQLite-Migrationen nach fünf geprüften Sicherungen bis Schema 9 durchgeführt. Neue Ergebnisfelder erfassen tatsächlichen Bewertungstag, Rendite, beste/schlechteste Bewegung, 20-Tage-Trendtreffer, Marktbenchmark, Überschussrendite und die versionierte Rohwahrscheinlichkeit je Prognosezeitraum. Die letzte Sicherung vor Schema 9 liegt integer unter `runtime/backups/forecasts-20260809-154956-548472.sqlite3`.
- L2-Referenzen für neue Snapshots umgesetzt und live für US-, Europa-, Asien-, ETF- und Krypto-Pfade geprüft. Automatische Wochenberichte dokumentieren Kohorten, Nachholen, Fehler, Rate-Limits, Laufzeit, Datenbankwachstum und Fälligkeitsstand.
- Qualitätsansicht um Ergebnisabdeckung, Wilson-Unsicherheitsbereich, Precision, Recall, Balanced Accuracy, Referenzvorsprung, Rendite, Drawdown, Überschussrendite und getrennte Qualitätssegmente erweitert.
- Vollständige Messvertragsprüfung ergänzt. Der Tageslauf prüft alle neuen Point-in-Time-Verträge vor jeder Auswertung und jedem Marktabruf und bricht bei Fingerabdruck-, Schema-, JSON- oder Cutoff-Fehlern sicher ab. Produktive Vorprüfung: 1.945 Legacy-Zeilen, null neue Verträge, null ungültige Verträge und Gesamtstatus `ok`.
- Versionierte unkalibrierte Rohwahrscheinlichkeit `Rendite > 0` aus gespeicherter Bull-/Base-/Bear-Verteilung und numerischen Zielen ergänzt. Brier Score, Log Loss, Kalibrierungsfehler und Bias werden nach Reifung neuer Fälle insgesamt sowie nach Modell und Zeitraum berechnet und in das weiterhin rein manuelle Kalibrierungsprofil übernommen.
- Strenges L2-Lern-Gate und purged Walk-Forward-Aufteilung ergänzt. Der aktuelle produktive Bericht zählt 9.725 Legacy-Zeiträume, null lernberechtigte Fälle, null ungültige Verträge und bleibt im Status `collect_only`; Produktionsaktivierung ist technisch gesperrt.
- Reale nicht speichernde Yahoo-Probe für NVDA war am 2026-08-09 um 15:59 Uhr vollständig leer. Deshalb schützt nun ein globales Provider-Gate die breite Neuprognose: Sind alle Marktbenchmarks leer, startet kein einzelner Asset-Versuch und keine Kohorte gilt als abgeschlossen. Fällige Ergebnisse bleiben bei Datenmangel offen und werden später erneut geprüft.
- Drei datumsabhängige Long-Term-Tests mit festem Prüfzeitpunkt reproduzierbar gemacht; fachliche Quellenalter-Regeln blieben unverändert.
- Swing-Phase-A-Kern ergänzt: versionierter fingerprinteter Orderplan, ausschließlich abgeschlossene Signalkerze, Folgesitzungsregel, finaler Positions-/Risiko-/Gewinnvertrag und ein initialer Stop, der bei aktivem Long-Trade nur enger werden darf.
- Getrennte append-only Swing-Forward-Datenbank, konservative spätere Kursbalkenauswertung und ehrliches Archiv mit Ergebnis in R, Profitfaktor, Drawdown und Segmenten ergänzt. Bestehende JSON-Historien wurden nicht überschrieben oder gelöscht.
- Regionaler Swing-Hintergrundbetrieb vorbereitet und in vier Windows-Aufgaben registriert. Exakt 65/73/956/30 Assets decken Asien/Australien, Europa, Amerika/Global und Krypto ohne Überschneidung ab; alle Aufgaben sind `Ready`, Wake-to-run und StartWhenAvailable sind aktiv.
- Sichtbare In-App-Browserprüfung bei 1.440 und 390 Pixel ohne horizontalen Überlauf und ohne zusätzliche Normaleingaben bestanden. Die echte Signal-/Orderkarte bleibt bis zur ersten realen Freigabe zu prüfen.
- Point-in-Time-sichere historische Swing-FX-Bewertung append-only ergänzt. Ein- und Ausstieg verwenden getrennte belegte Kurse; ein fehlender Beleg bleibt nachholbar und verändert das ursprüngliche Terminalereignis nicht.
- Laufende Nutzertrade-Begleitung um abgeschlossene 20-Tage-Struktur, Trend, Gaps und relatives Verkaufsvolumen erweitert. Ungeprüfte Nachrichten-, Ereignis- und Branchenfaktoren werden nicht erfunden, sondern ausdrücklich als nicht belastbar angezeigt.
- Stabile versionierte interne IDs für alle 1.124 Swing-Assets ergänzt. Börsen- und ISIN-Metadaten werden nur aus tatsächlich gelieferten vorhandenen Metadaten übernommen.
- Filter- und Detailansicht des Swing-Archivs ergänzt: Status, Setup, Region, Asset-Typ, Datenqualität und historische FX-Bewertung sind kombinierbar; Systemplan, append-only Ereignisverlauf und Segmentwerte bleiben prüfbar.
- Swing-Archivfilter vervollständigt: freie Suche über Assetname, Ticker, ISIN und Signal-ID sowie kombinierbare Einschränkung nach Signalzeitraum, Status, Setup, Einstiegsmethode, Asset-Typ, Paper-Gewinn/-Verlust/offenem Ergebnis, Datenqualität, Region, historischem FX, Strategieversion, Quellentyp und dokumentiertem Nutzertrade. Persönliche Nutzerhandlungen bleiben dabei strikt von objektiven Paper-Ergebnissen getrennt.
- Reale EWL-Daten read-only mit Suche und Zeitfilter geprüft: genau ein Archivtreffer, vollständige neue Felder und korrekt `Nutzertrade = Nein`. 68 gezielte Swing-/UI-/Stabilitätstests und anschließend die vollständige Suite mit 404/404 Tests bestanden.
- Begonnene Archiv-Detailmetriken abgeschlossen: Paper-Einstiegs-/Ausstiegszeit, Haltedauer, Ergebnisstatus sowie maximaler günstiger/ungünstiger Ausschlag sind in künftigen terminalen Ereignissen und Archivzeilen verfügbar. Gap-Stop berücksichtigt den ersten beobachteten handelbaren Kurs; Ereignisversion und stabile Quellschlüssel blieben zur append-only Kompatibilität unverändert.
- 16 gezielte Swing-Auswertungs-, Archiv- und Runner-Tests bestanden.
- Scanübergreifende technische Asset-Fehler ergänzt. Wiederkehrende Datenlücken werden sichtbar gezählt und niemals automatisch als Delisting interpretiert oder aus dem Universum gelöscht.
- Wochenend-Deduplizierung ergänzt: Setup-ID basiert auf abgeschlossener Signalkerze und Logikversion. Wiederholte Scans derselben Freitagskerze erzeugen kein zweites Forward-Signal.
- Hintergrundmetriken um Laufdauer, Abdeckung, Fehler und Rate-Limit-Zahl erweitert; sie werden im unveränderbaren Scan-Snapshot gespeichert.
- Append-only Modellregister für spätere Prognose-Challenger ergänzt. Kandidaten bleiben `shadow_only`; Dataset, Walk-Forward, Trainingscode und Artefakt sind fingerprintet. Ungesehene Qualitäts-, manuelle Review-, Canary- und Rollback-Gates werden dokumentiert, können aber niemals automatisch eine Produktionsversion aktivieren.
- Zwei-Ziel-Papervertrag korrigiert: Ziel 1 realisiert fest 50 %, Ziel 2 oder ein späterer Stop bewertet die verbleibenden 50 %. Teil- und Gesamtergebnis in Originalwährung, R und Euro werden nicht doppelt gezählt; historische FX-Kurse werden je Ausstiegsbein belegt.
- Ersten planmäßigen regionalen Swing-Lauf real validiert: Die Europa-Aufgabe startete am 2026-08-09 um 18:15 Uhr, endete mit Windows-Rückgabecode 0 und verarbeitete 72 von 73 Assets in 22,921 Sekunden ohne Rate-Limit. Das einzige freigegebene Setup ist ein unveränderbares EWL-Ausbruchssignal mit frühestem Paper-Einstieg am 2026-08-10; keine Order wurde ausgeführt.
- Den einzelnen Roche-Fehler anhand echter Anbieterantworten auf den falschen Swing-Ticker `ROG.SW` zurückgeführt und für künftige Läufe auf `ROP.SW` korrigiert. Zwei append-only Nachläufe luden danach jeweils alle 73 Europa-Assets ohne Fehler oder Rate-Limit. Die Datenbank enthält bewusst drei reale Scanbeobachtungen, aber dank der Wochenend-Deduplizierung weiterhin nur ein EWL-Signal und null doppelte Ereignisse; der ursprüngliche Fehler bleibt unverändert nachvollziehbar.
- Frische Swing-Seite an den automatischen Betrieb angebunden: Der letzte Regional-Scan und offene beziehungsweise aktive Hintergrundsignale sind ohne erneuten manuellen Vollscan sichtbar. EWL zeigt den unveränderbaren Orderplan und erlaubt ausschließlich die lokale Dokumentation eines bereits extern ausgeführten Nutzertrades; weder die Anzeige noch diese Dokumentation sendet eine Order.
- Rein beobachtende rollierende Prognoseüberwachung in `forecast_monitoring.py` ergänzt. Je Analyseart/Horizont werden 28 jüngste Tage mit den vorherigen 84 Tagen auf Richtungstreffer, feste Trendregel, Überschussrendite, Brier Score, Log Loss und Wahrscheinlichkeitsabdeckung verglichen; Eingabe-/Segmentverteilungen, Scoremittelwerte, Auswertungsrückstand, technische Fehler, Asset-Erfolgsquote, Enthaltungsquote und Rate-Limits werden zusätzlich beobachtet.
- Feste Fehlalarmschutzregeln ergänzt: Driftvergleich erst ab 50 Ergebnis-/Wahrscheinlichkeitsfällen beziehungsweise 100 Eingabefällen; drei Tage Puffer für nur kalendarisch fällige Ergebnisse. Der Monitoring-Bericht ist Bestandteil des atomaren Kalibrierungsprofils v3, erscheint in der Prognosequalität und kann weder Training noch Regel-, Score- oder Produktionsänderungen auslösen.
- Produktives Profil ohne Markt- oder Prognoseabruf aktualisiert: Status `collect_only`, 322 kalendarisch fällige und null mehr als drei Tage überfällige Fälle, 99,7 % Asset-Erfolgsabdeckung im aktuellen Fenster, null Rate-Limits und keine behauptete Drift ohne Referenzperiode.

Tests:

- Vollständige Suite: 401 Pytest-Tests bestanden.
- Kompilierung, Repository-Sicherheitscheck und Offline-Smoke-Test einschließlich Headless-Streamlit-Start bestanden.
- Produktive marktfreie Vorprüfung: Schema 9, Quick-Check `ok`, 1.726 Wochenassets, 1.945 unveränderte Legacy-Prognosen, null ungültige Messverträge, keine Marktdatenabfrage, keine neue Prognose, keine Auswertung und keine Datenlöschung. Kalibrierungsprofil v2 enthält korrekt null gereifte Wahrscheinlichkeitsfälle und verändert keine Produktionsregel.
- Regression nach Roche-Korrektur: 12 gezielte Swing-Universums-, Hintergrund- und Forward-Store-Tests bestanden; Preflight weiterhin `ok` mit 1.124 vollständig und eindeutig abgedeckten Assets. Produktive Swing-Forward-Datenbank: Schema 1, Quick-Check `ok`, drei Scans, ein Signal, null Ereignisse und null ungültige Datensätze.
- Reale EWL-Oberfläche im In-App-Browser bei 1.280 und 390 Pixel ohne horizontalen Überlauf und ohne Konsolenfehler geprüft. Anschließend vollständige Suite erneut mit 401/401 bestandenen Tests; datumsabhängige Long-Term-Testquellen sind reproduzierbar fixiert, ohne produktive Frischegrenzen zu verändern.
- Aktueller vollständiger Stand nach der Monitoring-Einheit: 404/404 Pytest-Tests bestanden; Kompilierung, Repository-Sicherheitscheck und Offline-Smoke-Test einschließlich Headless-Streamlit-Start erfolgreich. `git diff --check` meldete keine Fehler, nur vorhandene Zeilenende-Hinweise.

Git:

- Bestehende lokale Änderungen vollständig bewahrt. Kein Commit und kein Push; GitHub wurde nicht verändert. Keine Broker-Verbindung und keine Order.
- Erster realer Prognose-Fälligkeitsnachweis um 22:30 Uhr, die übrigen drei regionalen Swing-Erstläufe und der mehrwöchige Kohorten-/Paper-Betrieb stehen noch aus; das aktive Goal bleibt deshalb offen.

### 2026-08-07

Änderungen:

- Einmalig verpassten Datenlauf vom 2026-08-06 als Warnung statt als rote Fehlermeldung eingeordnet; echte Datenbank-, Abbruch- und Stale-Fehler bleiben rot. Die Oberfläche bezeichnet die 6.475 offenen Einheiten korrekt als Prognosezeiträume statt als eigenständige Prognosen.
- Separate historische Recovery-Datenbank und CLI ergänzt. Sie speichern nur OHLCV-Daten bis zum expliziten Cutoff, niemals heutige Fundamentaldaten, Nachrichten oder rückwirkend erzeugte Empfehlungen.
- Reale Recovery für den 2026-08-06 um 22:30 Uhr durchgeführt: 116.517 Balken, 324 vollständige Assets, eine sichtbare Lücke (`MATIC-USD`), keine Daten nach dem Cutoff, Integrität `ok` und reproduzierbarer SHA-256-Fingerabdruck.
- Produktive Prognosedaten unverändert erhalten: 1.295 echte Prognosen und 6.475 Prognosezeiträume; Recovery-Daten besitzen `forward_test_eligible = 0` und werden niemals in Trefferquoten eingerechnet.

Tests:

- 29 gezielte Tests aus `tests/test_forecast_recovery.py` und `tests/test_forecast_system.py`, Kompilierung, marktfreie Vorprüfung und Repository-Sicherheitscheck bestanden; `git diff --check` meldete keine Fehler.

Git:

- Bestehende lokale Änderungen vollständig bewahrt. Kein Commit und kein Push; GitHub wurde nicht verändert.

### 2026-08-04

Änderungen:

- Planmäßigen Prognoselauf vom 2026-08-04 sicher bis zum regulären Ende überwacht, ohne den aktiven Prozess zu verändern: 325 verarbeitet, 325 erfolgreich, null fehlgeschlagen, null Rate-Limits, 803,26 Sekunden und Wrapper-Exit 0.
- Beide zuvor korrigierten Yahoo-Symbole im vollständigen Batch bestätigt: `BNY` und `ROP.SW` wurden jeweils beim ersten Versuch erfolgreich gespeichert.
- SQLite nach Abschluss read-only geprüft: Integrität `ok`, 970 gespeicherte Prognosen, 4.850 Horizontzeilen, null fällige Auswertungen und 3.510.272 Byte Wachstum im Tageslauf.
- Kalibrierungsprofil automatisch aktualisiert: null ausgewertete Fälle, `collect_only`, keine manuellen Vorschläge, keine Änderung von Produktionsgewichten oder Regeln.
- Direkter Windows-Aufgabenplanerabruf war erneut wegen Windows-Pfadfehler `0x80070003` nicht verfügbar. Planmäßiger Start und Abschluss sind durch Wrapper-Start/Ende, Runner-Log und SQLite vollständig belegt.

Tests:

- Marktfreie Vorprüfung erfolgreich: 325 eindeutige Assets, Schema 4, Datenbankstatus `ok`, 970 Prognosen, null Auswertungen, kein Marktabruf, keine neue Prognose und keine Datenlöschung.
- Alle 25 Tests in `tests/test_forecast_system.py` sowie der Repository-Sicherheitscheck bestanden; `git diff --check` meldete keine Fehler.

Git:

- Bestehende lokale Änderungen vollständig bewahrt. Kein Commit und kein Push; GitHub wurde nicht verändert.

### 2026-08-03

Änderungen:

- Planmäßigen Prognoselauf vom 2026-08-03 ab 22:35 Uhr sicher bis zum regulären Ende überwacht, ohne den aktiven Prozess zu verändern: 325 verarbeitet, 323 erfolgreich, zwei fehlgeschlagen, null Rate-Limits, 887,17 Sekunden und Wrapper-Exit 0.
- SQLite nach Abschluss read-only geprüft: Schema 4, Integrität/Quick-Check `ok`, 645 gespeicherte Prognosen, 3.225 Horizontzeilen, null fällige Auswertungen und keine Datenlöschung.
- Kalibrierungsprofil automatisch aktualisiert: null ausgewertete Fälle, `collect_only`, keine manuellen Vorschläge, keine Änderung von Produktionsgewichten oder Regeln.
- Wiederkehrende Symbolfehler sicher diagnostiziert: Öffentliche Yahoo-Suche ordnet Bank of New York Mellon `BNY` und Roche Zürich `ROP.SW` zu; beide Symbole besitzen aktuelle belastbare Tageshistorien.
- `config/forecast_universe.csv` für künftige Läufe versioniert von `BK` auf `BNY` und von `ROG.SW` auf `ROP.SW` korrigiert. Das Universum behält exakt 325 eindeutige Assets; historische SQLite-Daten wurden nicht umgeschrieben.
- Regressionstest ergänzt, der die neuen Symbole verlangt und die alten ablehnt.
- Direkter Windows-Aufgabenplanerabruf war wegen Windows-Pfadfehler `0x80070003` nicht verfügbar. Der planmäßige Start und Abschluss sind dennoch durch Wrapper-Start/Ende, Runner-Log, Prozessfortschritt und SQLite vollständig belegt.

Tests:

- Marktfreie Vorprüfung erfolgreich: 325 eindeutige Assets, 236 Aktien, 59 ETFs, 30 Kryptowährungen, Schema 4, Datenbankstatus `ok`, kein Marktabruf, keine neue Prognose und keine Datenlöschung.
- Alle 25 Tests in `tests/test_forecast_system.py` bestanden.
- Beide Ersatzsymbole isoliert mit Yahoo-Daten geprüft: `BNY` 251 Tageszeilen, `ROP.SW` 250 Tageszeilen, jeweils bis 2026-08-03.

Git:

- Bestehende lokale Änderungen vollständig bewahrt. Kein Commit und kein Push; GitHub wurde nicht verändert.

### 2026-08-02

Änderungen:

- Swing Trade Finder von einer manuellen Tickerliste auf ein intern gepflegtes, versioniertes Universum mit 1.124 aktiven gültigen Assets umgestellt. Enthalten sind 1.035 Aktien, 59 ETFs und 30 Kryptowährungen aus mehreren Regionen; ServiceNow ist enthalten.
- Strikte Universumsprüfung ergänzt: Pflichtfelder, Eindeutigkeit, Aktivstatus, Liquiditätsklasse und Tickerformat werden validiert; ungültige Zeilen werden protokolliert, bekannte Hebel-/Inverse-Produkte abgelehnt und nicht still als gültig übernommen.
- Mehrstufigen Scan umgesetzt: gebündelter Kursabruf, schneller Filter für Datenlage, Historie, Preis, Liquidität, Volumen, Volatilität, Trend und Setup-Struktur, vollständige Analyse von höchstens 60 Kandidaten sowie harte abschließende Freigabe ohne erzwungenen Trade.
- Finder-Hauptansicht auf Tradingkapital und Scan-Aktion reduziert. Manuelle Ticker-/Watchlist-, Risiko-, Stop-, CRV-, Volatilitäts-, Asset-Typ- und Positionsgrenzen-Eingaben entfernt; Universum und interne Regeln bleiben unter erweiterten Einstellungen nur lesbar.
- Historischer Stand: Zentrale konservative Risikopolitik zunächst mit 0,50 % Risiko je Trade, höchstens drei offenen Trades, 50 % Gesamtbelastung und 20 % je Position ergänzt. Die feste Drei-Trade-Grenze wurde am 2026-08-17 durch ein dynamisches 2,00-%-Gesamtrisikobudget ersetzt. Stop-Distanz bleibt zusätzlich auf 8 % bei Aktien, 7 % bei ETFs und 12 % bei Krypto begrenzt.
- Stop-Berechnung verbindet Setup-Struktur und aktuelle Volatilität und erklärt die verwendete Marke. Positionsberechnung zeigt Stückzahl, Investitionsbetrag, geplanten Verlust sowie mögliche Gewinne an Ziel 1/2; der Gap-Hinweis vermeidet eine falsche Verlustgarantie.
- Einmaligen Risikohinweis vor der ersten Finder-Nutzung ergänzt. Die Quittierung wird atomar ausschließlich lokal unter `runtime/` gespeichert und nicht auf jeder Karte wiederholt.
- Trade-Karten und Scan-Statistik vereinfacht: Universum, geladene Assets, Vorfilterauswahl, Tiefenprüfungen, Freigaben und Datenfehler sind kompakt sichtbar; abgelehnte Kandidaten und Datenqualität erscheinen ausschließlich erweitert.
- Wartungsskript und Quellenmetadaten für das Scanneruniversum sowie isolierte Universums-, Vorfilter-, Risiko-, App-Integrations- und UI-Regressionstests ergänzt.
- Ersten vollständigen planmäßigen Prognoselauf als aktuelle Betriebsbasis dokumentiert: Start um 22:30 Uhr ohne geöffnete App, 325 Positionen verarbeitet, 322 Prognosen gespeichert, drei Assets (`SO`, `BK`, `ROG.SW`) wegen fehlender belastbarer Kursdaten isoliert fehlgeschlagen, keine Rate-Limit-Fehler, 0,92 % Fehlerquote, 1.416,73 Sekunden Laufzeit, SQLite-Integrität `ok` und Windows-/Wrapper-Rückgabecode 0.
- Bedeutung der 1.610 offenen Prognoseauswertungen klargestellt: 322 erfolgreiche Assets mal fünf getrennte Horizonte; kein laufender Rechenprozess und keine 1.610 unterschiedlichen Assets. Die ersten 322 Ein-Wochen-Auswertungen werden ab 2026-08-09 fällig.
- ROADMAP um das vollständige Zielbild eines echten kontrollierten Lernsystems erweitert. Der 325-Asset-Bestand bleibt wiederkehrender Referenzkern; ungefähr 1.500 bis 2.500 qualitätsgeprüfte Assets sollen in fünf festen Wochengruppen jede Woche erneut prognostiziert werden, während fällige alte Prognosen weiterhin täglich geprüft werden.
- Verbindliche Lernarchitektur ergänzt: unveränderbarer Point-in-Time-Datenvertrag, horizon- und modellspezifische Ergebnislabels, Referenzmodelle, Kosten, Bias-/Leakage-Schutz, zeitliche Walk-Forward-Prüfung, Wahrscheinlichkeitskalibrierung, statistische Unsicherheit, Enthaltung, Champion-Challenger-/Shadow-Betrieb, Modellregister, manuelle Freigabe, Canary, Rollback, Drift-Überwachung und kontrolliertes Nachtraining.
- 20/50-Fallgrenzen ausdrücklich auf frühe Hinweise begrenzt. Ein produktives lernendes Modell benötigt deutlich strengere Reife-, Zeit-, Segment- und Out-of-Sample-Nachweise; `hohe Wahrscheinlichkeit` darf nur mit ausreichend großer belegter Kalibrierung erscheinen.
- Keine Anwendung, Bewertungsregel, Gewichtung, Windows-Aufgabe oder Produktionskonfiguration wurde für diese Roadmap-Erweiterung verändert.
- Quellen- und Bereitschaftsgrundlage für die geplante Long-Term-Analyse in `long_term_analysis.py` ergänzt. Das eigenständige Modell prüft zehn Pflichtbereiche, Quellenherkunft, URL, Herausgeber, Abrufzeitpunkt und Verwendungszweck, bevor eine spätere Synthese überhaupt freigegeben werden darf.
- Offizielle Primärquellen und unabhängige belastbare Quellen werden je Bereich ausdrücklich verlangt. Yahoo Finance, allgemeine News und sonstige Kontextquellen reichen allein nicht; fehlende, doppelte, ungültige oder nicht auflösbare Quellen bleiben sichtbare Datenlücken.
- Technische Einstiegsevidenz wird vom Long-Term-Gate ignoriert und kann die langfristige Quellenabdeckung nicht erhöhen. Noch kein UI-Modus, kein Long-Term-Score und keine Empfehlung wurden freigeschaltet.
- Atomare lokale Long-Term-Quellenablage in `long_term_research_cache.py` ergänzt. Öffentliches Quellenmaterial und Evidenz werden mit festem Schema, Modellversion, Ticker sowie Sammel-/Ablaufzeitpunkt gespeichert; unsichere Ticker können keinen Pfad außerhalb des Cache-Verzeichnisses erzeugen.
- Veraltete Cache-Stände bleiben unverändert lesbar, sind aber für eine Analyse technisch gesperrt. Beschädigte Dateien, Zukunftsschemata, falsche Modellversionen, ungültige Quellen und unbekannte Referenzen werden ausdrücklich abgelehnt statt still normalisiert.
- Atomarer Austauschschutz erhält bei einem Schreibfehler den vorherigen Cache und entfernt die temporäre Datei. Es wurden keine produktiven Quellen gesammelt und keine Long-Term-Empfehlung erzeugt.
- Preisattraktivität und Fundamentalvergleich seit dem historischen Hoch nach `price_attractiveness.py` extrahiert. Die bestehenden App-Funktionsnamen werden direkt reexportiert; Scoregewichtung, Schwellen, Hochabstandsbonus und sichtbare Texte blieben unverändert.
- Der Hochabstand bleibt reiner Kontext. Der Bonus wird nur bei nicht erkennbar verschlechterten aktuellen Fundamentalsignalen zugelassen; historische Umsatz-, Gewinn- oder Cashflow-Werte exakt zum früheren Hoch werden weiterhin nicht erfunden.
- Vorhandenen Bewertungs-Research-Pfad nach `valuation_analysis.py` extrahiert. App-Schnittstelle, Multiple-Beiträge, Schwellen, neutrale Leerzustände und sichtbare Hinweise zu fehlenden historischen, Peer-, ETF-Index- und Krypto-On-Chain-Daten blieben unverändert.
- Zukunftspotenzial und eingepreiste Erwartungen nach `future_potential_analysis.py` extrahiert. Vorhandene Qualitäts-, Wachstums-, Margen-, Bewertungs-, Momentum- und News-Beiträge sowie ehrliche Lücken für Produkt-, Adoptions-, Flow- und Spezial-Sentimentdaten blieben unverändert.
- Szenario-Wahrscheinlichkeiten und Expected Value nach `scenario_analysis.py` extrahiert. Sämtliche bisherigen Signal-, Markt-, Trend-, Marken- und Volatilitätsbeiträge, die 100-Prozent-Normalisierung, der Mindest-Basisfall und konservative Fallback-Renditen blieben unverändert.
- Zentrale numerische Kursbereiche und sichtbare Szenariozeilen in dieselbe Szenario-Domain übernommen. Sichtbare Analyse und Hintergrundprognose greifen weiterhin auf identische Zielmarken zu; App-Schnittstellen bleiben kompatibel.
- Einstiegsplan-Hilfen nach `entry_plan.py` extrahiert. Kaufzonen, technische Aktion, Confidence-Bezeichnung, Horizont und Gültigkeit verwenden weiterhin dieselben Regeln; App-Funktionsnamen werden direkt reexportiert.
- Quellengebundene Long-Term-Bewertung in `long_term_scoring.py` ergänzt. Erst ein vollständiger und versionskompatibler Quellenstatus erlaubt sieben explizite Faktoren und Bear-/Basis-/Bull-Rechnungen über drei bis sieben Jahre; technische Einstiegssignale sind als Langfristfaktor verboten.
- Bestehende zentrale Empfehlungssynthese und die kompatible ältere professionelle Entscheidungsfunktion unverändert nach `recommendation_synthesis.py` verschoben. `app.py` reexportiert beide Schnittstellen; Kategorien, Schwellen, Texte und Ergebnisstruktur bleiben erhalten.
- Long-Term-Evidenzmodell auf Version 2 angehoben und um quellentypische Höchstalter sowie Zukunfts-/Zeitzonenprüfung ergänzt. Der Veröffentlichungszeitpunkt ist gegenüber einem späteren Abruf maßgeblich; der Cache verweigert bereits bei Sammlung veraltete Quellen.
- Ersten offiziellen Quellenadapter `sec_filing_sources.py` vorbereitet. Er nutzt ausschließlich öffentliche SEC-Ticker-/CIK- und Submissionsdaten, entdeckt aktuelle unterstützte Jahres-/Quartalsfilings, baut sichere EDGAR-Dokumentadressen und behält Fair-Access-Kontaktdaten außerhalb jedes Ergebnisses.
- Prozesslokalen SEC-Fair-Access-Client ergänzt: serialisiert Requests, hält mindestens 0,12 Sekunden zwischen Starts ein, verwendet dieselbe Kontaktkennung und lädt die Ticker-/CIK-Datei nur einmal je Prozess. Fehlgeschlagene Abrufe werden nicht als gültiger Cache behandelt.
- Atomaren persistenten SEC-JSON-Cache in `sec_json_cache.py` ergänzt. Er akzeptiert nur die feste Ticker-/CIK-Adresse und korrekt formatierte Submissions-Adressen, verwendet 24 beziehungsweise sechs Stunden TTL und bewahrt die Kontaktkennung ausschließlich im Arbeitsspeicher des Clients.
- Strukturierte SEC-Company-Facts-Auswertung in `sec_financial_facts.py` ergänzt. Sechs aktuelle US-GAAP-Jahreswerte werden nach festen Konzeptprioritäten ausgewählt; Evidenz entsteht ausschließlich bei identischer Accession Number einer bereits entdeckten offiziellen Jahresberichtquelle.
- Nicht schreibende SEC-Teilkollektion in `sec_long_term_collection.py` ergänzt. Sie verbindet Discovery, Company Facts und Evidenz mit dem vorhandenen Long-Term-Gate; Teilausfälle bleiben sichtbar und können weder Quellen noch Aussagen erfinden.
- SEC-Finanzfakten um belegte Zwei-Jahres-Vergleiche erweitert. Prozentänderungen werden rein mathematisch und nur bei positivem Vorjahreswert gezeigt; ohne beide exakt passenden Jahresberichtquellen entsteht keine Vergleichsevidenz und kein Qualitätsurteil.
- Sichere manuelle SEC-Teilquellen-CLI ergänzt. `--preflight` prüft Kontaktkonfiguration und privaten Cachepfad ohne Netzwerk/Schreiben; Live-Nutzung bleibt ohne gültigen nur zur Laufzeit gesetzten Fair-Access-Kontakt gesperrt und gibt dessen Wert nie aus.
- Bestehende Datenqualitäts-Domain nach `data_quality_analysis.py` extrahiert. Externe Quellenwarnungen, Ampelstatus und Historien-/Identitätsprüfung bleiben unverändert über `app.py` erreichbar; vollständig fehlende `Close`-Spalten werden nun nach der Warnung nicht mehr versehentlich erneut abgefragt.
- Bestehende Score-Zusammensetzung nach `score_composition.py` extrahiert. Gewichtstabellen, Standardgesamtwert und optionale Mittelwerte behalten dieselben Regeln und werden von `app.py` direkt reexportiert.
- SEC-Transport um höchstens drei Versuche mit begrenztem Backoff für 429/temporäre Server- und Verbindungsfehler ergänzt. Dauerhafte HTTP-Fehler sowie ungültiges UTF-8-JSON werden nicht wiederholt; Kontaktkennung bleibt aus Fehlermeldungen ausgeschlossen.
- Hintergrunddiagnose vor dem nächsten Produktionslauf erweitert: Startvorprüfung sowie jeder begonnene Asset-Versuch werden mit Ticker, Position und Versuchszahl protokolliert.
- Prognoseuniversen ohne einen verwendbaren Ticker werden ausdrücklich abgelehnt; auch ein Fehler beim Laden des Universums landet vor dem Prozessende im rotierenden Laufprotokoll.
- Windows-Wrapper um ein getrenntes lokales Prozessprotokoll mit Start, Ende und Rückgabecode erweitert. Eine reale nicht löschende Wartungsprüfung endete mit Code 0 und bestätigte `data_deleted: false`.
- Windows-Systemereignisse zum alten Abbruch geprüft: Standby-Aktivität kurz vor dem Termin war sichtbar, ein eindeutiger Kausalnachweis für den Prozessabbruch jedoch nicht.
- Marktfreie Vorprüfung ergänzt und real über den Windows-Wrapper ausgeführt: 325 eindeutige Assets, Schema 4, Integrität `ok`, keine Marktabfrage, keine Prognosen geschrieben, keine Daten gelöscht, Rückgabecode 0.
- Prozessweiten Doppellaufschutz ergänzt: Ein zweiter Runner wird vor Datenbank- und Yahoo-Arbeit abgelehnt; Task-Scheduler- und manuelle Starts können dadurch nicht mehr gleichzeitig dasselbe Tagesuniversum bearbeiten.
- Portfolio-Domäne als kleine PRIO-C-Architekturpflege aus `app.py` nach `portfolio_analysis.py` getrennt: optionales JSON wird nur gelesen, Positions- und Depotbewertung sind ohne Streamlit oder Yahoo isoliert testbar, während Live-Kursfallback und bestehende App-Schnittstellen unverändert bleiben.
- Keine Portfolio-, Score- oder UI-Regel geändert und keine private Portfolio-Datei verändert. Fünf neue Regressionstests sichern die bisherigen Ergebnisse und Fehlerfälle ab.
- Währungs- und Anzeigeumrechnung als weitere kleine PRIO-C-Einheit nach `currency_utils.py` getrennt. Geldformate, EUR-Umrechnung und Kursreihenkopien sind jetzt ohne Streamlit isoliert testbar; sichtbare Texte und App-Schnittstellen blieben unverändert.
- Aktien- und ETF-Fundamentallogik als Phase-3-/PRIO-C-Vorarbeit nach `fundamental_analysis.py` getrennt. Snapshots, Datenlücken, Bewertungsgrenzen und Scores sind jetzt ohne Streamlit oder Yahoo-Netzwerkzugriff isoliert prüfbar; die bisherigen App-Schnittstellen und Scorebeiträge blieben erhalten.
- Zentrale Zahlen-Normalisierung gehärtet: Nicht endliche Werte (`NaN`, positive oder negative Unendlichkeit) gelten als nicht verfügbar und können keine künstlichen Extrem-Scores mehr erzeugen.
- Verständlichen Betriebsstatus für den automatischen Prognoselauf ergänzt: letzter Lauf, verarbeitete Assets, nächster Termin, Fehler und klare Zustände für erfolgreich, laufend, verspätet, unterbrochen oder veraltet.
- Schutz gegen dauerhaft falsche `running`-Zustände ergänzt: Ein neuer Tageslauf markiert ältere nicht abgeschlossene Läufe als unterbrochen, ohne Prognosen oder Historien zu löschen.
- Reale Betriebsdiagnose dokumentiert: Der Lauf vom 2026-08-01 startete um 22:30 Uhr, verarbeitete aber 0 von 325 Assets und wurde danach nicht fortgeschrieben; die Oberfläche meldet diesen Zustand nun als Fehler.
- Verbindliche Roadmap-Architektur in der PLDatei nachgezogen: `Asset-Analyse`, `Investment Opportunities` und `Swing Trade Finder` sind getrennte Zielbereiche; aktuelle Implementierung und offene Teile sind klar markiert.
- Nicht löschende Sicherungs- und Wiederherstellungsbasis für die Prognosedatenbank ergänzt: zeitgestempelte SQLite-Online-Sicherung, Integritäts-/Schemacheck, Überschreibschutz und Wiederherstellung ausschließlich in eine neue Datei.
- Erste reale Sicherung der aktuellen Datenbank erfolgreich unter `runtime/backups/` erstellt; Schema 2 und Integrität `ok`, keine Daten gelöscht.
- Prognosedatenbank auf Schema 3 erweitert: Laufzeit, Assets pro Minute, Fehlerquote, Rate-Limit-Fehler, Datenbankgröße/-wachstum und Integritätsstatus werden nach jedem nicht übersprungenen Lauf dauerhaft gespeichert und sichtbar angezeigt.
- Startseite auf drei fachlich getrennte Hauptbereiche erweitert: `Asset-Analyse`, `Investment Opportunities` und `Swing Trade Finder`.
- Bisherigen Opportunity Scanner ohne Änderung seiner Long-Swing-Logik oder privaten Historien sichtbar in `Swing Trade Finder` umbenannt; ältere Session-Zustände bleiben kompatibel.
- Sicheren `Investment Opportunities`-Leerzustand mit den geplanten Modi `Aktuell attraktiv` und `Zukunftschancen 3+ Jahre` ergänzt. Es werden noch keine Scores oder scheinbaren Kandidaten erzeugt.
- Erste gemeinsame Design-Tokens für Radien, Rahmen, Oberflächen, Schatten und Schaltflächen ergänzt.
- Prognosedatenbank auf Schema 4 erweitert: Jede Prognose trägt eine explizite Analyseart; Bestandsdaten werden als `Einstiegsanalyse` erhalten, und die Qualitätsansicht bietet getrennte Zusammenfassung und Filterung nach Analyseart.
- Reale Datenbank erfolgreich auf Schema 4 migriert und mit Integritätsstatus `ok` geprüft; zusätzliche lokale Sicherung unter `runtime/backups/` erstellt, keine Daten gelöscht.
- Bedienungsfreies Kalibrierungsprofil ergänzt: Nach jedem Hintergrundlauf werden echte abgeschlossene Prognoseauswertungen nach Analyseart, Logikversion, Asset-Typ und Zeitraum zusammengefasst und atomar unter `runtime/calibration_profile.json` gespeichert.
- Reproduzierbaren Datenfingerabdruck, Profilversion, Mindestdatenstufen und strikte Guardrails ergänzt. Das Profil erzeugt ausschließlich manuelle Prüfhinweise und verändert niemals selbstständig Produktionsregeln oder Score-Gewichte.
- Prognosequalitätsansicht um Reifegrad, Fallzahl und manuelle Prüfhinweise aus dem Kalibrierungsprofil erweitert; `--calibration-only` aktualisiert das Profil ohne Marktabruf.
- Opportunity Scanner zu einem selektiven manuellen Long-Swing-Assistenten umgebaut; keine sichtbare `Beobachten`-Kategorie und keine erzwungenen schwachen Kandidaten.
- Zwei messbare Setup-Arten umgesetzt: Rücksetzer in intaktem Aufwärtstrend und bestätigter Ausbruch über relevanten Widerstand.
- Zentrale Mindestgrenzen, exakte Einstiegssignale, Struktur-Stop/-Ziele, konsistente CRV- und Expected-Value-Berechnung sowie Schutz vor verpassten Einstiegen, Strukturbruch, Daten-/Liquiditätsmangel und Ereignisrisiko in `trading_assistant.py` gebündelt.
- Scanner-Hauptansicht auf Marktlage, Scanzeit, geprüfte Assets, hochwertige Setups und ausschließlich freigegebene Trade-Karten reduziert. Ablehnungen, Methodik, Grenzwerte und Paper-Statistiken liegen unter `Erweiterte Einblicke`.
- Risikobasierte Positionsgröße mit Kapital-, Einzelrisiko-, Gesamtbelastungs-, Maximaltrade- und Asset-Typ-Einstellungen ergänzt; ohne Kapital keine Stückzahl.
- Manuellen Trade-Lebenszyklus ergänzt: tatsächlichen Einstieg erfassen, aktive Trades mit Gewinn/Verlust und Handlung begleiten, Stop manuell anpassen und Ausstieg manuell bestätigen.
- Alle freigegebenen Scanner-Signale werden als lokale Paper-Trades dokumentiert; abgelaufene Setups werden markiert und Auswertungen ändern keine Score-Gewichte automatisch.
- Ergebnisdarstellung konsequent in drei Ebenen getrennt: kompakte Entscheidung, verständliche Detailanalyse auf Klick und standardmäßig geschlossene erweiterte Analyse.
- Hauptansicht auf Asset-Identität, EUR-Kurs, Anlagehorizont, Confidence, Asset-Typ, Empfehlung, getrennte Langfrist-, Preis- und Timing-Sicht, maximal drei Gründe, maximal zwei Risiken sowie einen konkreten Mehrpfad-Plan reduziert.
- Empfehlungssynthese um strukturierte Felder für Empfehlungskategorie, langfristige Einschätzung, Preisattraktivität, aktuelles Timing, Sofort- und Rücksetzer-Zone, relative Tranchierung, Handlung jetzt, Handlung bei Rücksetzer, Handlung bei weiterer Stärke, Widerlegungsbedingung und Gültigkeit erweitert.
- Kursabstand zum höchsten Kurs der maximal verfügbaren Historie als Kontext ergänzt; er erzeugt nie allein ein Kaufsignal. Bei Aktien verhindern mehrere aktuelle Umsatz-, Gewinn- oder Cashflow-Schwächesignale eine falsche `günstig`-Einordnung.
- Asset-spezifische Erläuterungen für Aktien, ETFs und Kryptowährungen ergänzt; fehlende historische Fundamentaldaten beziehungsweise On-Chain-, Flow- und Liquiditätsdaten bleiben sichtbar.
- Empfehlungen `Jetzt kaufen`, `Erste Tranche kaufen`, `Bei Bestätigung kaufen`, `Auf konkrete Kaufzone warten`, `Halten`, `Teilweise reduzieren` und `Verkaufen oder vermeiden` liefern jetzt eine relative Prozent-Reihenfolge der geplanten Position. Ohne Risikobudget werden weiterhin keine Eurobeträge erfunden.
- Rücksetzer-Einstieg von einer einzelnen Marke zu einer asset-spezifischen technischen Kaufzone als Bereich erweitert; der bisherige Referenzkurs bleibt als technischer Mittelpunkt nachvollziehbar.
- Verständliche Detailfacetten `Investmentthese`, `Preis & Bewertung`, `Einstieg & Vorgehen`, `Chancen`, `Risiken`, `Szenarien` und `Markt & Umfeld` umgesetzt.
- Zentrale Risiken um Relevanz und beobachtbare Eintrittshinweise ergänzt; Szenarien auf notwendige Entwicklung, Wahrscheinlichkeit, mögliche Folge und wichtigsten Auslöser verdichtet.
- Leere beziehungsweise nicht verfügbare Module werden aus der normalen Detailansicht gefiltert; Rohstoff-/Zykluskontext erscheint dort nur bei erkennbarer Asset-Relevanz.
- `Portfolio-Effekt` wird ausschließlich bei aktivem Portfolio-Modus als Detailfacette erzeugt.
- Jede normale Detailfacette beginnt mit einem Kurzfazit; längere Szenarien werden nicht mehr in einer kompakten Datentabelle abgeschnitten, sondern vollständig als umbrochene Texte angezeigt.
- Ergebnis-CSS um flexible Textkarten, Wortumbruch, umbrochene Metric-Texte und Stapelung der Spalten unter 700 Pixel erweitert; es bestehen keine `text-overflow: ellipsis`- oder `white-space: nowrap`-Regeln für wichtige Ergebnisinhalte.
- Technische Kennzahlen, Fundamentaldetails, Datenqualität, Methodik, Score-Komponenten, Logikversion, Prognosequalität, ähnliche Fälle, Opportunitätskosten, Backtesting und Rohdaten in `Erweiterte Analyse` gebündelt.
- Prognosestatus unterscheidet leeren Bestand, noch nicht fällige Prognosen, ausgewertete Prognosen, nicht dokumentierten Hintergrundbetrieb sowie fällige Auswertungen mit fehlenden Marktdaten. Fehlgeschlagene Auswertungsversuche werden in SQLite ohne Nutzerdaten protokolliert.
- Veraltete Earnings-Termine aus Yahoo werden nicht als zukünftige Gültigkeitsgrenze verwendet.
- Bestehende Analyse-, Score-, Portfolio-, Tracking-, Backtesting- und Scannerfunktionen erhalten; keine Score-Gewichte verändert.
- Betroffene Dateien dieser Überarbeitung: `app.py`, `forecast_store.py`, `forecast_runner.py`, `tests/test_recommendation_synthesis.py`, `tests/test_information_hierarchy.py`, `tests/test_forecast_system.py` und `PROJECT_STATUS.md`.
- GitHub-Actions-Workflow erweitert: `requirements-dev.txt` wird installiert und der vollständige Pytest-Lauf vor dem Offline-Smoke-Test ausgeführt.
- Roadmap und Projektstatus abgeglichen: bereits umgesetzte Module klarer markiert und der erste echte Remote-Lauf weiterhin als blockierter nächster Schritt dokumentiert.
- Prognose-Datenbank um Schema-Version 2, schrittweise Migrationen, Schutz vor neueren unbekannten Schemata sowie nicht löschende Integritäts-, Größen-, WAL- und Optimierungswartung ergänzt.
- `scripts/run_forecasts.py` um `--maintenance-only` und das ausdrücklich manuelle `--compact` erweitert; beide Wege löschen keine Prognosen oder Auswertungen.
- Hintergrundlauf um Betriebsmetriken ergänzt: Dauer, Verarbeitungstempo, Fehlerquote, erkannte Rate-Limits, Datenbankwachstum, Schema-Version und Integritätsstatus werden in Ergebnis und Log ausgegeben.
- Erste weitere Modularisierung umgesetzt: Asset-Suche, bekannte Ticker, Normalisierung und Tippfehler-Vorschläge aus `app.py` nach `asset_search.py` verschoben; App-Aufrufe bleiben kompatibel.
- JSON-Historienzugriff nach `json_history_store.py` extrahiert und alle lokalen History-Schreibpfade auf atomaren Austausch umgestellt; bestehende Dateien und private Daten wurden nicht automatisch verändert oder gelöscht.
- Zehn gemeinsame Analyse-Datenklassen nach `analysis_models.py` extrahiert und über `app.py` kompatibel reexportiert.
- Technische Indikatoren, Unterstützungen/Widerstände, CRV, Marktphasenerkennung und gemeinsame numerische Hilfsfunktionen nach `technical_analysis.py` extrahiert; die bisherigen App-Schnittstellen und Bewertungsregeln bleiben unverändert.
- Fünf isolierte technische Regressionstests in `tests/test_technical_analysis.py` ergänzt.

Tests:

- Reine Dokumentationsprüfung für das Lernsystem bestanden: alle vorgesehenen ROADMAP-Bausteine und PLDatei-Verweise vorhanden, UTF-8-Inhalt ohne Mojibake und `git diff --check` ohne Fehler. Keine Code-Tests ausgeführt, da diese Einheit keine Anwendung, Konfiguration oder Bewertungslogik verändert hat.
- Neun neue isolierte Long-Term-Tests bestanden: Leerzustand, Yahoo-only-Ablehnung, vollständige Primär-/Unabhängigen-Abdeckung, Wettbewerbsanforderung, fehlende Referenzen, Quellenmetadaten, doppelte Quellen-IDs, Techniktrennung, Provenienz und Nicht-Mutation.
- Vollständiger aktueller Stand nach der Long-Term-Quellengrundlage: 186 Pytest-Tests bestanden; Kompilierung, Repository-Sicherheitscheck, Offline-Smoke-Test einschließlich Headless-Streamlit-Start und Git-Diff-Prüfung ebenfalls erfolgreich.
- Acht zusätzliche Cache-Tests bestanden: Pfadsicherheit, frischer Roundtrip, Provenienz, Stale-Sperre, fehlende/beschädigte Datei, Zukunftsschema, Quellen-/Referenzvalidierung, atomarer Austauschschutz und Zeitregeln. Vollständiger Pytest-Stand danach: 194 Tests bestanden.
- Fünf direkte Preisattraktivitäts-Tests sowie alle 19 Empfehlungssynthese-Tests bestanden. Vollständiger Pytest-Stand nach der Extraktion: 199 Tests bestanden; Kompilierung von App und neuem Modul erfolgreich.
- Fünf direkte Bewertungstests und die vorhandenen Bewertungs-Regressionsfälle bestanden. Vollständiger Pytest-Stand nach der Extraktion: 204 Tests bestanden.
- Fünf direkte Tests für Zukunftspotenzial und eingepreiste Erwartungen sowie alle Empfehlungssynthese-Tests bestanden. Vollständiger Pytest-Stand nach der Extraktion: 209 Tests bestanden.
- Fünf direkte Szenario-/Expected-Value-Tests sowie alle Empfehlungssynthese-Tests bestanden. Vollständiger Pytest-Stand nach der Extraktion: 214 Tests bestanden.
- Zwei weitere Szenariotests für numerische und sichtbare Zielkonsistenz bestanden. Vollständiger Pytest-Stand danach: 216 Tests bestanden.
- Elf direkte Entry-Plan-Tests und alle Empfehlungssynthese-Tests bestanden. Vollständiger Pytest-Stand nach der Extraktion: 227 Tests bestanden.
- Vierzehn neue Long-Term-Scoring-Fälle bestanden; zusammen mit Quellen- und Cache-Tests sind es 31 gezielte Long-Term-Tests. Vollständiger Pytest-Stand nach dieser Einheit: 241 Tests bestanden.
- Zwei Schnittstellen-/Kompatibilitätsfälle für das extrahierte Empfehlungsmodul ergänzt. Alle 21 Empfehlungssynthese-Tests und der vollständige lokale Stand mit 243 Pytest-Tests bestanden.
- Drei neue Quellenaktualitätsfälle und ein Cache-Fall bestanden. Zusammen bestehen 35 gezielte Long-Term-Tests; vollständiger Pytest-Stand nach Evidenzversion 2: 247 Tests bestanden.
- Zehn SEC-Adapterfälle bestanden; vollständiger lokaler Pytest-Stand danach: 257 Tests bestanden. Es wurde kein SEC-Live-Abruf und keine automatische Aktivierung vorgenommen, weil dafür eine echte nur zur Laufzeit bereitgestellte Kontaktkennung sowie kontrolliertes Request-Limit/Caching nötig sind.
- Vier zusätzliche Fair-Access-Client-Fälle bestanden; alle 14 SEC-Tests und vollständiger Pytest-Stand mit 261 Tests grün. Der User-Agent bleibt ausschließlich im Arbeitsspeicher und die gecachte Tickerdatei wird an Aufrufer nur als Kopie herausgegeben.
- Sieben persistente SEC-Cache-Tests bestanden; zusammen 21 gezielte SEC-Fälle und vollständiger lokaler Pytest-Stand mit 268 Tests. Beschädigte, alte, zukünftige und unbekannte Schemaeinträge werden neu geladen statt verwendet; gescheiterter atomarer Austausch erhält die alte Datei.
- Sechs Finanzfaktenfälle bestanden; zusammen 27 gezielte SEC-Tests und vollständiger lokaler Pytest-Stand mit 274 Tests. Quartals-/Zukunfts-/Nichtendlichkeitswerte, ungültige Accession Numbers und unverbundene Quellen erzeugen keine Evidenz.
- Vier SEC-Integrationsfälle bestanden; zusammen 31 gezielte SEC-Tests und vollständiger lokaler Pytest-Stand mit 278 Tests. Selbst bei einer korrekt belegten Finanzangabe bleibt das Gesamtgate wegen der übrigen fehlenden Long-Term-Bereiche geschlossen.
- Drei Jahresvergleichsfälle bestanden; zusammen 34 gezielte SEC-Tests und vollständiger lokaler Pytest-Stand mit 281 Tests. Fehlende Vorjahresquelle oder nicht positiver Basiswert führen nicht zu einer scheinbar präzisen Prozentinterpretation.
- Vier CLI-Sicherheitsfälle bestanden; zusammen 38 gezielte SEC-Tests und vollständiger lokaler Pytest-Stand mit 285 Tests. Reale Offline-Vorprüfung: `configuration_required`, kein Netzwerk, kein Schreibvorgang, Cachepfad innerhalb `runtime/`, Kontaktwert nicht ausgegeben.
- Sechs direkte Datenqualitätstests sowie alle Informationshierarchie-/Empfehlungsfälle bestanden. Vollständiger Pytest-Stand nach Extraktion und Leerzustandsfix: 291 Tests; `app.py` umfasst 8.238 Zeilen und 214 eigene Top-Level-Funktionen.
- Fünf direkte Score-Kompositionsfälle sowie die vollständige Stabilitätsteilmenge bestanden. Vollständiger Pytest-Stand nach der Extraktion: 296 Tests; `app.py` umfasst 8.195 Zeilen und 211 eigene Top-Level-Funktionen.
- Drei direkte SEC-Transportfälle bestanden; zusammen 41 gezielte SEC-Tests und vollständiger lokaler Pytest-Stand mit 299 Tests.
- Drei neue Regressionstests für ein leeres Universum, protokollierte Startfehler und das Fortschrittsprotokoll vor einem simulierten harten Abbruch bestanden; alle 22 Prognosesystemtests erfolgreich.
- Zusätzlicher Vertragstest für Wrapper-Protokoll, Argumentweitergabe und Erhalt des Python-Rückgabecodes bestanden; alle 23 Prognosesystemtests erfolgreich.
- Zwei Vorprüfungstests für gültige Laufzeitpfade und strikt abgelehnte defekte JSON-Konfiguration bestanden; alle 25 Prognosesystemtests erfolgreich.
- Zwei neue Sperrtests bestanden: echter zweiter Python-Prozess wird abgelehnt, nach Freigabe ist die Sperre erneut nutzbar, und der tägliche Runner beginnt bei Konflikt weder Datenbank- noch Marktarbeit. Zusammen mit den Prognosesystemtests: 27 Tests bestanden.
- Vollständiger aktueller Stand nach Runner-, Wrapper-, Vorprüfungs- und Doppellaufschutz-Ausbau: 150 Pytest-Tests bestanden; Kompilierung, Repository-Sicherheitscheck, Offline-Smoke-Test einschließlich Headless-Streamlit-Start und Git-Diff-Prüfung ebenfalls erfolgreich.
- Vollständiger aktueller Stand nach der Portfolio-Extraktion: 155 Pytest-Tests bestanden; Kompilierung, Repository-Sicherheitscheck, Offline-Smoke-Test einschließlich Headless-Streamlit-Start und Git-Diff-Prüfung ebenfalls erfolgreich.
- Vollständiger aktueller Stand nach der Währungs-Extraktion: 159 Pytest-Tests bestanden; Kompilierung, Repository-Sicherheitscheck, Offline-Smoke-Test einschließlich Headless-Streamlit-Start und Git-Diff-Prüfung ebenfalls erfolgreich.
- Vollständiger aktueller Stand nach Fundamental-Extraktion und Nicht-Endlichkeits-Schutz: 177 Pytest-Tests bestanden; Kompilierung, Repository-Sicherheitscheck, Offline-Smoke-Test einschließlich Headless-Streamlit-Start und Git-Diff-Prüfung ebenfalls erfolgreich.
- Produktionsnaher Windows-Startweg nach sämtlichen Moduländerungen erneut mit `--preflight` geprüft: Wrapper-Exit 0, 325 eindeutige Assets, Schema 4, Datenbankintegrität `ok`, keine Marktabfrage, keine Prognosen oder Auswertungen geschrieben und keine Daten gelöscht. Die geplante Aufgabe blieb `Ready` für 22:30 Uhr mit aktivem Aufwecken und Wiederanlauf.
- Vollständiger Hintergrund-Snapshot nach der Fundamental-Extraktion einmalig mit echten NVDA-Daten im Speicher erzeugt, ohne ihn in SQLite zu speichern: korrekter Aktien-/Einstiegsanalyse-Typ, fünf Horizonte, 17 Modulwerte, verfügbarer Kurs und grüne Datenqualität. Der zunächst eingeschränkte Netzwerkmodus lieferte erwartbar keine Yahoo-Daten; mit freigegebenem Zugriff war der Produktionspfad erfolgreich.
- Äußere Betriebsbedingungen vor dem planmäßigen Lauf rein lesend bestätigt: Wrapper, lokale Python-Umgebung, Konfiguration, Universum und Laufzeitpfad vorhanden, ausreichend freier Speicher, Netzbetrieb aktiv, automatischer Standby für Netz-/Akkubetrieb deaktiviert und Aufwecktimer in beiden Betriebsarten aktiviert. Die Windows-Aufgabe besitzt zusätzlich weiterhin `WakeToRun`.
- Drei neue Prognose-Betriebstests für einen veralteten Lauf, automatische Kennzeichnung eines älteren laufenden Tages und einen gesunden abgeschlossenen Lauf bestanden.
- Gezielter Prognose-/Stabilitätslauf nach dem Betriebsstatus-Ausbau: 71 Tests bestanden.
- Zwei isolierte Sicherungstests sowie die 15 Prognosesystemtests gemeinsam bestanden; Kompilierung des Sicherungsmoduls und der CLI erfolgreich.
- Neuer Persistenztest für Betriebsmetriken bestanden; Sicherungs- und Prognosesystemteilmenge danach mit 18 Tests erfolgreich.
- Früherer vollständiger Pytest-Zwischenstand: 130 Tests bestanden.
- Aktueller vollständiger Pytest-Lauf nach Betriebs-, Sicherungs-, Metrik- und Navigationsausbau: 136 Tests bestanden.
- Aktuelle Kompilierung, Repository-Sicherheitscheck und Offline-Smoke-Test einschließlich Headless-Streamlit-Start: erfolgreich.
- Sichtbare Browserprüfung der neuen Navigation begonnen, aber durch die Sicherheitsrichtlinie für die lokale URL blockiert; es wurde kein alternativer Zugriff erzwungen. Desktop- und 390-Pixel-Sichtprüfung bleiben offen.
- Neuer Schema-4-Migrationstest sowie gezielter Prognose-/Stabilitätslauf: 73 Tests bestanden.
- Zwei Kalibrierungsprofiltests sowie Prognose- und Stabilitätstests gemeinsam: 75 Tests bestanden. Reales Profil erfolgreich mit 0 ausgewerteten Fällen, 0 Prüfhinweisen und unveränderten Produktionsregeln erzeugt.
- Isolierter Tagesprozess ohne Marktabruf bestätigt die automatische Profilerzeugung. Dabei gefundenen Windows-Logdatei-Handle behoben; alle 20 Prognose-/Kalibrierungstests anschließend bestanden.
- Schutz gegen Versionsvermischung ergänzt: abgeschlossene Tagesläufe bleiben unverändert, und eine abweichende Logikversion am selben Tag wird abgelehnt. Alle 21 Prognose-/Kalibrierungstests bestanden.
- Gemeinsame Trefferquote bei gemischten Analysearten unterdrückt; Einstiegs- und Swing-Auswertungen bleiben getrennt sichtbar. Prognose-, Kalibrierungs- und Stabilitätsteilmenge: 78 Tests bestanden.
- Prognose-Zusammenfassung, Qualitätsfilter und letzter Lauf migrieren ältere unterstützte Schemata vor dem Lesen idempotent, statt nach einem Update einen scheinbaren Leerstand zu zeigen. Alle 22 Prognose-/Kalibrierungstests bestanden.
- Vollständiger aktueller Pytest-Lauf: 142 Tests bestanden. Kompilierung, Repository-Sicherheitscheck und Offline-Smoke-Test einschließlich Headless-Streamlit-Start ebenfalls erfolgreich.
- Reale Betriebsprüfung um 17:28 Uhr: Datenbank Schema 4/Integrität `ok`, 0 Prognosen und 0 Auswertungen; Kalibrierungsprofil im korrekten Sammelstatus. Windows-Aufgabe `Ready`, aktiviert, nächster Lauf am 2026-08-02 um 22:30 Uhr, Aufwecken/verspäteter Start/drei Neustarts/Doppellaufschutz aktiv.
- 21 isolierte Trading-Assistent-Tests für Pullback, Breakout, Kein-Trade-Fall, CRV, verpassten Einstieg, gebrochene Unterstützung, Schlusskursbedingung, Datenqualität, Ereignisrisiko, Positionsgröße, manuellen/aktiven/geschlossenen Trade, Ziel, Stop, Ablauf und Paper-Statistiken bestanden.
- Reales manuelles Scanner-Sample mit fünf Assets: fünf geprüft, kein fachlich ausreichendes Setup freigegeben, keine Ladefehler; die objektive Kein-Trade-Regel funktionierte damit auch mit Live-Daten.
- `python -m compileall` für Anwendung, Prognosemodule, Skripte und Tests: erfolgreich.
- Vollständiger Pytest-Lauf: 90 Tests bestanden.
- Repository-Sicherheitscheck: erfolgreich.
- Offline-Smoke-Test einschließlich lokalem Headless-Streamlit-Start und Historienqualität: erfolgreich.
- Erweiterten lokalen CI-Ablauf nach Datenbank-Stabilisierung, Betriebsmetriken, Suchmodul, atomaren JSON-Historien und Datenmodell-Extraktion erneut geprüft: 103 Tests, Sicherheitscheck, Offline-Smoke-Test und Kompilierung erfolgreich.
- Aktueller vollständiger Lauf nach der technischen Analyse-Extraktion: 108 Tests bestanden.
- Live-Smoke-Test mit echten Yahoo-Daten: `BTC-EUR`, `NVDA` und `1810.HK` erfolgreich.
- Reale ServiceNow-Prüfung: Synthese erfolgreich mit `Auf konkrete Kaufzone warten`, langfristig `Gemischt`, Preisattraktivität `Fair`, Timing `Ungünstig`, Handlung `0 % jetzt`, Kaufzone `89,78 € bis 93,44 €` und gültiger 30-Tage-Grenze. Ein von Yahoo gelieferter vergangener Earnings-Termin wurde erkannt, behoben und erneut live geprüft.
- Szenario-Matrix geprüft für Bitcoin, ServiceNow-ähnliche Qualität, große Qualitätsaktie, deutlich gefallene Aktie mit intakten beziehungsweise schwächeren aktuellen Fundamentaldaten, überbewertetes Wachstum, breiten ETF, Themen-ETF, fehlende Bewertungsdaten, bestehende Position und Portfolio-Konflikt.
- Sichtbare Browserprüfung mit isolierten ServiceNow-Daten: Ebene 1 zeigte Empfehlung, drei getrennte Bewertungen, drei Gründe, zwei Risiken, vollständige Prozent-Tranchen, konsistente Zonen, Widerlegung und Gültigkeit. Nach Klick erschienen die sieben verständlichen Facetten ohne Portfolio-Tab; der Kursabstand von 51,0 % wurde ausdrücklich nicht als automatisches Kaufsignal erklärt. `Erweiterte Analyse` war zunächst geschlossen und zeigte nach Öffnen exakt die fünf vorgesehenen Unterkategorien einschließlich verständlichem Prognosestatus.
- Sichtbare Scanner-Prüfung mit isolierten Daten: freigegebener NVDA-Ausbruch mit Einstieg, Stop, zwei Zielen, CRV 2,30, belastbar zurückgehaltener Trefferwahrscheinlichkeit und Positionsgröße; abgelehnter schwacher Kandidat mit konkreten Gründen; aktiver Trade und Paper-Statistiken sichtbar. Desktop mit 1.280 Pixel und Mobilansicht mit 390 × 844 Pixel ohne horizontalen Überlauf, ohne abgeschnittene wichtige Texte, ohne sichtbare Beobachtungskategorie und ohne Browserfehler.

Git:

- Ausgangsbasis und aktueller Commit: Branch `main`, Commit `b6698c0bdcfa0565f10df1be16fc1b53927022e7`.
- Kein Commit und kein Push; GitHub wurde nicht verändert.

### 2026-08-01

Änderungen:

- Zentrale Projektdokumentation `PROJECT_STATUS.md` angelegt.
- Vorhandenen Funktions-, Architektur-, Daten-, Test- und Roadmap-Stand aus `app.py`, `README.md`, `ROADMAP.md`, Tests, Skripten und Konfigurationen zusammengeführt.
- Neue native Startseite mit den Bereichen `Aktien Analyse` und `Opportunity Scanner` umgesetzt.
- Session-State-Navigation mit `home`, `analysis` und `scanner` sowie sichtbaren Zurück-Buttons ergänzt.
- Aktien-Analyse grundlegend neu gegliedert: zentrale Suche, integrierte Vorschläge, Euro-Standard, Einstellungen oben rechts, automatische Asset-Erkennung und sieben Ergebnisbereiche.
- Zentrale Empfehlungssynthese ergänzt: Qualität, Timing, CRV, Marktphase, Bewertung, Risiken, Datenlage und optionaler Depot-Effekt werden in sieben eindeutige Handlungskategorien übersetzt, ohne vorhandene Einzel-Scores oder Gewichtungen zu verändern.
- Analyse-Ergebnis neu strukturiert: kompakter Ergebniskopf und sieben Bereiche für Übersicht, Unternehmen/Asset und Bewertung, Kurs und Einstieg, Chancen und Risiken, Markt und Umfeld, Portfolio sowie Methodik und Daten.
- Bedingte Empfehlungen um einen konkreten Rücksetzerweg, einen alternativen Bestätigungsweg und eine Widerlegungsmarke ergänzt; ohne Risikobudget wird keine exakte Positionsgröße erfunden.
- Offenen Roadmap-Punkt zur Analyse-Laufzeit umgesetzt: tägliche Chartdaten verwenden die bereits geladene Langfristhistorie, unabhängige externe Research-Quellen werden parallel abgerufen und historische Signal-Backtests 30 Minuten zwischengespeichert.
- Separate Reihe und Schnellwahl für letzte Suchen sowie sichtbare manuelle Forward-/Prognose-Schaltflächen aus dem normalen Analyseablauf entfernt.
- Kleine Richtungstrefferquote auf der Startseite und gefilterte, paginierte Prognosequalitätsansicht unter den erweiterten Einstellungen ergänzt.
- Gemeinsame Hintergrund-Snapshot-Funktion auf Basis der vorhandenen Analyse-, Score-, Szenario- und Confidence-Logik ergänzt; keine Score-Gewichte verändert.
- SQLite-Schema für Läufe, Assets, Snapshots, Horizonte und Auswertungen in `forecast_store.py` umgesetzt.
- Fortsetzbaren täglichen Runner mit Deduplizierung, Wiederholungen, Batches, Pausen, Fehlerisolierung, rotierendem Log und automatischer Fälligkeitsprüfung in `forecast_runner.py` umgesetzt.
- Versioniertes Prognoseuniversum mit 325 eindeutigen Assets angelegt; enthält 236 Aktien, 59 ETFs und 30 Kryptowährungen sowie ausdrücklich ServiceNow.
- Windows-Wrapper, idempotentes Installationsskript und Konfiguration angelegt; Aufgabe `InvestmentAssistantDailyForecasts` benutzerbezogen für 22:30 Uhr registriert.
- Private automatische Laufzeitdaten und Logs über `runtime/` in `.gitignore` geschützt; vorhandene JSON-Historien blieben unverändert.
- Testpfade für private Historien und Prognosedatenbank umleitbar gemacht, damit UI-Tests keine echten Nutzerdaten verändern.
- Beim sichtbaren vollständigen Analysefluss einen zuvor verdeckten Fehler im Aufruf von `negative_case_cause_rows` gefunden und behoben.
- Blockierenden Analyse-Engpass behoben: Die bestehende Unterstützungs-/Widerstandssuche wurde bei unveränderter Bewertungslogik vektorbasiert umgesetzt. Dadurch läuft der automatisch erzeugte historische Signal-Backtest nicht mehr minutenlang in Python-Schleifen.
- Streamlit-Stabilitätstest an neue Navigation, Suche, Einstellungen, Euro-Standard und Prognosequalität-Leerzustand angepasst; neues isoliertes Prognosetestmodul ergänzt.
- `requirements-dev.txt` mit reproduzierbarer Pytest-Abhängigkeit angelegt.
- Betroffene Dateien: `.gitignore`, `app.py`, `forecast_store.py`, `forecast_runner.py`, `config/forecast_settings.json`, `config/forecast_universe.csv`, `scripts/run_forecasts.py`, `scripts/run_forecasts.cmd`, `scripts/install_forecast_task.ps1`, `requirements-dev.txt`, `tests/test_stability.py`, `tests/test_forecast_system.py`, `tests/test_recommendation_synthesis.py`, `tests/test_analysis_performance.py`, `ROADMAP.md` und `PROJECT_STATUS.md`.
- Zu den jüngsten bereits vorhandenen Repository-Änderungen gehören der Repository-Sicherheitscheck, der GitHub-Smoke-Workflow und die transparente Qualitätsprüfung lokaler Lernhistorien.

Tests:

- `python -m compileall` für Anwendung, Prognosemodule, Skripte und Tests: erfolgreich.
- Repository-Sicherheitscheck: erfolgreich.
- Offline-Smoke-Test mit Headless-Streamlit-Start und Historienqualitätsprüfung: erfolgreich.
- Vollständiger Smoke-Test mit Live-Marktdaten: erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`; der erste Versuch war nur durch den eingeschränkten Netzwerkzugriff blockiert und wurde mit freigegebenem Zugriff erfolgreich wiederholt.
- Vollständiger Pytest-Lauf: 71 Tests bestanden.
- Neun isolierte Empfehlungstests für hochwertige und schwache Aktien, Rücksetzer, ETF, Krypto, fehlende Fundamentaldaten, bestehende Position und Portfolio-Konflikt bestanden.
- Zwei Performance-Regressionstests für wiederverwendete Tageshistorie und tatsächlich parallele unabhängige Research-Abrufe bestanden.
- Regressionstest für identische Fenster-, Filter- und Relevanzsemantik der optimierten Unterstützungs-/Widerstandssuche ergänzt; zusätzlich 800 Vergleichsfälle gegen die bisherige Logik erfolgreich geprüft.
- Frühere reale NVDA-Gegenmessung: historischer Signal-Backtest von 101,6 auf 1,24 Sekunden reduziert; vollständiger Analyse-Klick von 128,91 auf 15,08 Sekunden reduziert.
- Neue reale ServiceNow-Gegenmessung nach der Roadmap-Optimierung: erster vollständiger Analyse-Klick 9,31 Sekunden, erneuter Abruf 2,51 Sekunden, keine Exception. Damit ist der Zielbereich von 5–10 Sekunden für den kalten Abruf erreicht.
- Neue Prognose-Kerntests: Universum, SQLite-Leerzustand, Wiederaufnahme nach Teilabbruch, Tages-Deduplizierung, Fehlerisolierung, künstlich fällige Auswertung, Trefferquote und Tabellenfilter bestanden.
- Echter isolierter Hintergrundlauf mit NVDA: 1 von 1 Asset erfolgreich, SQLite-Snapshot gespeichert; temporäre Testdaten danach entfernt.
- Direkter Streamlit-AppTest: Startseite, Analyse öffnen, leere Prognosequalität, Analyse zurück, Scanner öffnen, Scanner zurück und neue Sitzung ohne Exception.
- Installationsskript im `-WhatIf`-Modus validiert; registrierte Aufgabe anschließend lesend geprüft: `Ready`, 22:30 Uhr, Benutzer `maxwi`, `RunLevel Limited`, korrekter Runner und Projekt-Arbeitsordner.
- Sichtbare Browserprüfung mit isolierten Testdaten: ServiceNow-Suche, kompakter Ergebniskopf, Empfehlung `Erste Tranche kaufen`, Rücksetzer- und Bestätigungsweg, Widerlegungsmarke sowie alle sieben Ergebnisbereiche erfolgreich.
- Desktop-Prüfung bei 1.280 Pixel ohne horizontalen Seitenüberlauf; Mobilprüfung bei 390 Pixel ohne horizontalen Seitenüberlauf, Suche und Einstellungen auf volle Inhaltsbreite gestapelt.
- Opportunity Scanner und Rücknavigation sichtbar regressionsgeprüft; keine Browserfehler. Temporärer UI-Harness, Testdaten und lokale Server wurden anschließend entfernt.

Git:

- Ausgangsbasis: `main` auf Commit `b6698c0bdcfa0565f10df1be16fc1b53927022e7`.
- Lokales `main` und `origin/main` waren vor der Dokumentationsänderung identisch.
- Aktueller Commit bleibt `b6698c0bdcfa0565f10df1be16fc1b53927022e7`, da kein Commit erstellt wurde.
- Lokale Änderungen und neue Dateien entsprechen der oben aufgeführten Umsetzung; private Laufzeitdaten werden nicht von Git erfasst.
- Kein Commit und kein Push im Rahmen dieser Änderung; `origin/main` wurde nicht verändert.

Bei zukünftigen Änderungen dieses Format fortführen:

```text
### JJJJ-MM-TT

Änderungen:

- ...

Tests:

- ...

Git:

- ...
```

## 7. Roadmap

### Verbindliche Ausführungsreihenfolge

1. Zuerst den realen wöchentlichen Markt- und Forward-Betrieb mit 1.726 Assets stabil belegen und aus echten fälligen Ergebnissen die Analyse- und Prognosequalität messen.
2. Direkt danach den Swing Trade Finder als wichtigste Nutzerfunktion weiter validieren und vervollständigen.
3. Erst danach allgemeines Design, Navigation, Long-Term-Ausbau, `Investment Opportunities` und Komfortfunktionen fortsetzen.

Die folgenden historischen Phasennummern beschreiben fachliche Bereiche und Abhängigkeiten. Sie ersetzen diese aktuelle Arbeitsreihenfolge nicht. Kritische Stabilitäts-, Datenschutz-, Datenintegritäts- oder Falschergebnisfehler behalten jederzeit Vorrang.

### Phase 1 – Stabilität und Datenqualität

- Tests, Start, Datenbankintegrität, Historien und Sicherheitscheck stabil halten.
- Der erste vollständige 325-Asset-Lauf ist belegt: 322 von 325 Prognosen gespeichert, drei isolierte Datenfehler, keine Rate-Limit-Fehler, rund 23 Minuten Laufzeit, Datenbankintegrität `ok` und Windows-Rückgabecode 0.
- Der dritte vollständige Lauf am 2026-08-04 bestätigte 325 von 325 erfolgreiche Assets einschließlich `BNY` und `ROP.SW`, null Rate-Limits, Integrität `ok` und Windows-Rückgabecode 0.
- Den Hintergrundbetrieb nun über mehrere Wochen beobachten; erste fällige Auswertungen, Laufzeit, Fehler, Rate-Limits, Wiederanlauf, Nachholen und Datenbankwachstum bewerten.
- Startphase und jeder begonnene Asset-Versuch werden inzwischen protokolliert, damit ein erneuter Abbruch wesentlich genauer eingegrenzt werden kann.
- Der Windows-Wrapper protokolliert zusätzlich die äußere Prozessgrenze und den Rückgabecode; der sichere Wartungsweg wurde damit real mit Code 0 validiert.
- Eine marktfreie Vorprüfung bestätigt vor dem nächsten Termin alle 325 eindeutigen Ticker, beschreibbare Laufpfade und die intakte Schema-4-Datenbank, ohne Prognosen zu erzeugen.
- Eine zusätzliche betriebssystemweite Prozesssperre verhindert Doppelläufe auch außerhalb der Windows-Aufgabenplanung und gibt sich nach Prozessende automatisch frei.
- Der sichtbare Betriebsstatus und die Erkennung veralteter Läufe sind umgesetzt. Der fehlerhafte Lauf vom 2026-08-01 und der erfolgreiche vollständige Lauf vom 2026-08-02 bleiben getrennt nachvollziehbar.
- Keine privaten Daten oder Lernhistorien löschen; Bewertungslogik nachvollziehbar und versionierbar halten.

### Phase 2 – Gemeinsames Designsystem und Navigation

- Hauptmenü mit `Asset-Analyse`, `Investment Opportunities` und `Swing Trade Finder` ist umgesetzt und funktional regressionsgeprüft.
- Der bisherige Opportunity Scanner ist ohne Änderung von Paper-Trades oder Historien sichtbar in `Swing Trade Finder` umbenannt.
- Erste gemeinsame Regeln für Radien, Rahmen, Oberflächen, Schatten und Schaltflächen sind umgesetzt; Typografie, Abstände, Statusflächen und responsive Komponenten bleiben app-weit weiter zu vereinheitlichen.
- Startseite, Analyse, Prognosequalität, Einstellungen und Swing Trade Finder bei 1.280 sowie 390 Pixel sichtbar prüfen; der aktuelle Browserlauf war durch die lokale URL-Sicherheitsrichtlinie blockiert.

### Phase 3 – Asset-Analyse

- Die bestehende Einstiegsanalyse als expliziten Modus erhalten und stabilisieren.
- Eine eigenständige Long-Term-Analyse für drei bis sieben Jahre aufbauen. Der isoliert getestete Quellen- und Bereitschaftsvertrag sowie die atomare Cache-Grundlage mit Stale-Sperre sind umgesetzt; Quellenadapter, Aktualisierungsplanung, Synthese, Bewertung, Szenarien und UI fehlen.
- Geschäftsmodell, Markt, Wettbewerb und Management nur aus ausgewiesenen offiziellen oder belastbaren Quellen ableiten; Yahoo Finance allein reicht dafür nicht.
- Langfristige Qualität, Preis, Timing und optionalen Depot-Effekt getrennt halten.

### Phase 4 – Investment Opportunities

- Getrennte Modi und Scores `Aktuell attraktiv` und `Zukunftschancen 3+ Jahre` entwickeln.
- Nur ausreichend hochwertige Kandidaten anzeigen; keine schwachen Ideen zum Auffüllen erzwingen.
- Investment-Watchlist, lokale rückgängig machbare Ausblendungen und sichere Übergaben in die passende Analyseart umsetzen.
- Ein größeres, kontrolliert belastbares Marktuniversum erst nach geklärter Datenabdeckung und Last anbinden.

### Phase 5 – Swing Trade Finder

- Die Long-v1-Basis mit Rücksetzer, Ausbruch, Kein-Trade-Regel und absoluter harter Freigabe ist erhalten.
- Freeze-Infrastruktur, acht getrennte technische Challenger, gemeinsame unabhängige Risk Engine, autonomer `paper_only`-Bot und brokerlose Shadow-Live-Grundlage sind technisch umgesetzt. Keine dieser Stufen ist wegen Performance produktiv freigegeben.
- Historische Kampagne vom zuletzt geprüften Stand 243/248 sicher bis zum vollständigen Validation-/Holdout-/Robustheitsbericht fortführen. Danach startet ausschließlich der gesicherte Broad-Research-Pfad; Challenger dürfen höchstens nach einem Development-C manuell eingefroren, niemals automatisch aktiviert werden.
- Autonome Paper- und echte Shadow-Beobachtungen über ausreichend viele aktuelle Signale, Marktphasen und Betriebszustände sammeln. Fehlende Ausführungsdaten nicht schätzen.
- Versioniertes 2.520-Asset-Universum, gebündelter Yahoo-Abruf, binärer Grobfilter und vollständige Tiefenanalyse aller bestandenen Kandidaten sind umgesetzt. ServiceNow ist enthalten; Hebel-/Inverse-Produkte sind ausgeschlossen.
- Hauptoberfläche ist auf Tradingkapital und Scan reduziert. Einmalige Risikoquittierung, zentrale konservative Regeln, automatische Struktur-/Volatilitäts-Stops, Positionsgröße und vollständige Scan-Zähler sind umgesetzt.
- Erster Europa-Betriebsnachweis ist vorhanden: 73 Assets wurden nach korrigiertem Roche-Symbol vollständig geladen, ohne Rate-Limit; drei append-only Beobachtungen derselben Freitagslage erzeugten korrekt nur ein EWL-Forward-Signal. Der erste zulässige Paper-Einstieg liegt am 2026-08-10.
- Automatisch gespeicherte offene und aktive Signale erscheinen direkt beim Öffnen des Swing-Bereichs; ein erneuter manueller Gesamtmarkt-Scan ist nicht erforderlich. Die reale EWL-Karte ist desktop- und mobil geprüft.
- Reale Scan-Abdeckung, Laufzeit, Datenabrufquote, Assetklassen-Funnel und Paper-Ergebnisse über mehrere Marktphasen weiter messen. Der erste große Lauf erreichte 2.350/2.352 ohne Rate-Limit.
- Weitere Long-Setups sowie Short-/Absicherung erst nach ausreichender realer Validierung untersuchen.
- Keine Hebelprodukte, kein Scalping, keine Broker-Anbindung und keine reale Order. Das nächste fachliche Gate ist Evidenzreife, nicht Echtgeldentwicklung.

### Phase 6 – Automatische Prognosequalität

- Hintergrundbetrieb, Fälligkeitsauswertung und kompakte Prognosequalität zuverlässig betreiben.
- Bis 2026-08-08 wurden 1.945 echte Prognosen und 9.725 Prognosezeiträume gespeichert. Die ersten 322 Ein-Wochen-Zeiträume werden ab 2026-08-09 fällig, bleiben am marktfreien Sonntag jedoch korrekt offen, solange noch kein abgeschlossener Kurs nach dem Zielzeitpunkt vorliegt; der erste reguläre Bewertungstag ist voraussichtlich 2026-08-10.
- Tägliche Fälligkeitsprüfung ist technisch von der Neuprognose getrennt und läuft zuerst. Ab 2026-08-10 erzeugt jeder Termin höchstens eine feste Wochenkohorte; Wochenenden ohne Rückstand bleiben reine Auswertungsläufe.
- Seit 2026-08-11 sind auch die Startfrequenzen der Horizonte entkoppelt: 1W wöchentlich, 1M zweiwöchentlich, 3M monatlich, 6M quartalsweise und 12M halbjährlich. 6M/12M verlangen ein versioniertes Langfrist-Evidenzgate; Altdaten bleiben unverändert.
- Das versionierte Gesamtuniversum umfasst 1.726 liquide, eindeutig identifizierte Assets. Der 325er Referenzkern bleibt montags vollständig erhalten; vier deterministische Erweiterungskohorten decken die übrigen 1.401 Assets ab.
- Neue Snapshots besitzen den L0-Point-in-Time-Vertrag; ältere Daten und die getrennte Recovery-Datenbank werden nicht rückwirkend zu Forward-Fällen umgedeutet.
- Technische Trennung nach Analyseart ist mit Schema 9, Modellfilter, separater Richtungstrefferquote und getrennten Wahrscheinlichkeitsmetriken vorbereitet; aktuell existieren nur automatische Einstiegsanalysen.
- Versioniertes Kalibrierungsprofil wird bedienungsfrei aus echten Auswertungen erzeugt und darf nur manuelle Prüfhinweise liefern; automatische Regel- oder Gewichtsänderungen sind technisch und dokumentarisch ausgeschlossen.
- Long-Term-, Einstiegs- und Swing-Modelle künftig nach Version, Horizont und passendem Vergleichsmaßstab vollständig getrennt auswerten.
- Keine rückwirkenden Prognosen erfinden und fehlende Marktdaten nicht als Fehlergebnis zählen.

### Phase 7 – Validierung und kontrollierte Verbesserung

- Empfehlungen, Opportunity-Scores und Swing-Setups über ausreichend viele echte Fälle getrennt messen.
- Trefferquote, Rendite, Profitfaktor, Drawdown und Opportunitätskosten nach Modell, Asset-Typ, Marktphase und Datenqualität vergleichen.
- Point-in-Time-Merkmale und fachlich getrennte Labels ohne Zukunftswissen speichern; alte Wochenprognosen und ihre fünf Horizonte niemals überschreiben.
- Gegen bestehende Regeln, einfache Richtungs-/Trendmodelle und passende Benchmarks vergleichen; Trefferquote allein reicht nicht.
- Modelle zeitbasiert mit Walk-Forward-, Purging- und unangetasteter Testperiode prüfen; Wahrscheinlichkeiten auf getrennten Daten kalibrieren.
- Bestehende Regelbasis als Champion behalten, Kandidaten zunächst im Shadow-Modus sammeln und nur nach dokumentiertem ungesehenem Vorteil freigeben.
- Modellregister, manuelle Freigabe, Canary, rollierende Drift-Überwachung und getesteten Rollback vor jeder lernenden Produktionsversion verlangen. Modellregister, Freigabe-/Canary-/Rollback-Gates und die rein beobachtende Driftbasis sind technisch vorhanden; ihr realer Qualitätsnachweis benötigt gereifte Daten und tatsächliche Shadow-Kandidaten.
- Bei unzureichender Datenlage oder unbekannter Verteilung `keine belastbare Empfehlung` ausgeben; keine hohe Wahrscheinlichkeit ohne sichtbare Kalibrierung und Unsicherheit.
- Regeln oder Gewichte nur versioniert, dokumentiert, getestet und mit Rückfallmöglichkeit ändern; keine heimliche automatische Kalibrierung.

### Langfristige Vision

Das Projekt soll sich zu einem stabilen, nachvollziehbaren und datenbasierten Research-System entwickeln, das gezielte Asset-Analysen und eine systematische Chancensuche verbindet. Es soll Markt-, Fundamental-, Makro-, Risiko-, Portfolio- und historische Qualitätsinformationen verständlich zusammenführen, eigene Prognosen und Entscheidungen messbar machen und Verbesserungsbedarf transparent ableiten.

Die langfristige Lernfähigkeit bleibt regelgebunden: Ein fester Referenzkern und ein größeres rotierendes Wochenuniversum werden wiederholt prognostiziert, alte Snapshots mit echten späteren Kursdaten geprüft und Verbesserungen zeitbasiert gegen einfache Referenzen getestet. Die Long-v1-Baseline sowie technische Challenger sind versioniert und getrennt; Kandidaten dürfen erst nach vollständiger ungesehener Walk-Forward-, echter Forward-, autonomer Paper- und Shadow-Evidenz manuell geprüft werden. Hohe Wahrscheinlichkeiten benötigen belegte Kalibrierung, und unsichere Fälle führen zur Enthaltung. Produktionsänderungen benötigen Versionierung, manuelle Freigabe, Canary und Rollback. Der Investment Assistant bleibt in der aktuellen Stufe eine technische Entscheidungshilfe ohne Broker-Anbindung und ohne reale Orderausführung.
