# Oberstes Produktziel – SwingTrader

Der Investment-Assistent soll langfristig ein autonomes, regelbasiertes **Multi-Factor Swing-/Position-Trading-System** werden: ein großes handelbares, listinggenaues Universum überwachen, hochwertige Opportunities erkennen, eine belegte These und einen bedingten Kaufplan bilden, strukturelles Risiko unabhängig begrenzen, Positionen halten und dynamisch schützen beziehungsweise verkaufen.

Sieben Informationsschichten tragen das Zielbild:

| Schicht | Zweck |
|---|---|
| A | Unternehmensqualität / Fundamentals |
| B | Erwartungen / Surprises / Catalysts |
| C | Markt / Sektor / Relative Strength |
| D | Makro / Rates / Liquidität |
| E | Unternehmens-, regulatorische und geopolitische Events |
| F | Technische Preisstruktur und Timing |
| G | Volatilität / Liquidität / Ausführbarkeit |

Der technische Chart allein muss keinen eigenständigen Edge besitzen. Technik unterstützt Timing, Entry, strukturelle Invalidation, Protective Zones, Position Management und Exit. Die Kombination dieser Schichten ist eine **zu prüfende Hypothese**, kein nachgewiesener Vorteil.

Ziel-Zustandsautomat (kein bereits implementierter Lauf):

`UNIVERSE → WATCH → ENTRY_READY → BUY_SIGNAL → POSITION_OPEN → HOLD → PROTECT → SELL_SIGNAL → CLOSED`

`NO_TRADE`, `WAIT` und `DATA_INSUFFICIENT` sind vollwertige Ergebnisse. HOLD und PROTECT können wiederholt neu beurteilt werden; SELL setzt eine eigene Exit-Regel voraus, nicht das bloße Durchlaufen dieser Darstellung.

## Planungsgrenze und Dokumentrollen

Plan freigegeben, Umsetzung **noch nicht gestartet**. Abschlussstatus dieses Dokumentationsauftrags: `SWINGTRADER_MASTER_ROADMAP_REBUILT_AWAITING_START`. Es besteht keine neue Ausführungsfreigabe für Collector, Research, Strategie, Validation, Holdout, Forward, Paper, Shadow, Broker oder Orders. Bereits gesondert genehmigte signalunabhängige Datensammler bleiben unberührt.

- [PROJECT_STATUS.md](PROJECT_STATUS.md): belegter Ist-Stand, aktive Collector, Datenblocker und konkrete Forward-Zahlen.
- [RESEARCH_POLICY.md](RESEARCH_POLICY.md): dauerhafte PIT-, Evidence-, Freeze- und Freigaberegeln.
- [Produktarchitektur](SWINGTRADER_PRODUCT_ARCHITECTURE.md): langfristige Modulgrenzen, keine Laufstatuszahlen.
- [CHANGELOG.md](CHANGELOG.md), [Archivnachweis](docs/archive/ROADMAP_ARCHIVE_2026-09-26.md) und Research Reports / Knowledge Base: unveränderte historische Entscheidungen und Evidenz, **keine aktive Arbeitsqueue**.

## Signal zuerst, Orders erst nach eigenem Gate

**Stufe A – Signal-System:** Opportunities, Entry-Signale, Größenvorschläge, Invalidation sowie HOLD/PROTECT/SELL ausgeben. Der Nutzer führt reale Orders selbst aus. Nutzerausführungen, unveränderte Modell-Signale und hypothetische Ergebnisse bleiben getrennt.

**Stufe B – autonome Execution:** BUY_SIGNAL/SELL_SIGNAL erst nach Development → Validation → Holdout → External Unseen Universe → True Forward → Autonomous Paper → Shadow Live → manuellem Echtgeld-Gate separat in Broker-Orders überführen. Technische Fähigkeit oder ein einzelnes PASS ist keine Handelsfreigabe.

**Kein Fixed-Time-Trader:** Positionen dürfen wenige Tage, mehrere Wochen oder Monate laufen. HOLD ist zulässig, solange These, Invalidation und Protective Structure halten, das verbleibende Chance/Risiko attraktiv bleibt und kein zwingender negativer Event vorliegt. Zeit allein löst keinen Exit aus. 20 / 60 / 120 / 252 sind ausschließlich Research-, Mess-, Vergleichs- und Censoring-Fenster, keine automatische Produktions-Exit-Regel. Weder blindes Next-Open noch ein fixer 2R-Exit wird zum Produktstandard.

## Reihenfolge und Prioritäten

Keine Phase überspringt ein früheres Gate. Phase 0 bleibt querschnittlich bestehen; Phase 1 ist die höchste fachliche Entwicklungspriorität. Fehlende PIT-Evidenz ist kein Beweis gegen den Multi-Factor-Ansatz, rechtfertigt aber auch keine neue Suche ohne Daten-Gate.

| Phase | Verbindlicher Arbeitsschritt |
|---|---|
| 0 | Datenbetrieb und Infrastruktur stabil halten |
| 1 | Point-in-Time Data Engine fertigstellen |
| 2 | Opportunity / Asset Selection Engine erforschen |
| 3 | Thesis Engine entwickeln |
| 4 | Entry Planner erforschen und validieren |
| 5 | Independent Risk / Portfolio Risk vervollständigen |
| 6 | Position Monitor entwickeln |
| 7 | Dynamic Exit Engine erforschen |
| 8 | Komplettes Swing-System als Fixed Challenger einfrieren |
| 9 | Vollständiges Development / Walk-Forward |
| 10 | Validation |
| 11 | Holdout |
| 12 | External Unseen Universe |
| 13 | True Forward Signals |
| 14 | Autonomous Paper |
| 15 | Shadow Live |
| 16 | Manuelles Echtgeld-Gate |
| 17 | Begrenzter Live-Bot |
| 18 | Kontrollierte Skalierung |

Priorität innerhalb zulässiger Aufgaben: **0** Integrität / kritische Fehler / Sicherheit; **1** PIT Data Engine; **2** Opportunity / Thesis; **3** Entry; **4** Risk / Portfolio Risk; **5** Monitor / Exit; **6** integrierte Strategievalidierung; **7** Forward / Paper / Shadow; **8** Live Execution; **9** sonstiger Produktkomfort. Priorität ersetzt niemals eine Phasenfreigabe.

## Phase 0 – Betrieb zuerst absichern

Nach einem späteren Start zuerst Repository, Prozesse, Scheduler, Locks, unveränderliche Stores und aktuelle Source Health read-only prüfen. Die erste Umsetzung darf nur belegte Betriebs-/Integritätslücken im freigegebenen Umfang schließen; keine historischen Ergebnisse korrigieren.

Das zentrale Data-Health-Gate muss für **jede** Quelle ausweisen: Zuständigkeit/Scheduler, letzter tatsächlicher Erfolg, expected cadence, Staleness, Source Health, `first_seen_at`, `published_at`, Revision Support, Missingness, Retry-Grenzen, Append-only und Duplicate Protection. Ein erfolgreicher Prozess ist nicht automatisch frische oder vollständige Evidenz. Betriebszustände bleiben `HEALTHY`, `STALE`, `PARTIAL`, `FAILED`, `NOT_CONFIGURED`, `NOT_APPLICABLE`.

| Quellenbereich | Geplante Betriebsprüfung, keine Aktivierungsbehauptung |
|---|---|
| FX PIT / COT | Bestehenden genehmigten Observer, tatsächliche Quellenfrische und Availability prüfen; keine Kurs-/COT-Rückdatierung. |
| Allgemeiner Forecast-/Market Collector | Bestehende Abendkette, einzelne Assetfehler, Rate Limits und Beobachtungszeit prüfen; Prognosen sind keine validierte Swing-Strategie. |
| Unternehmens-/Filing-, Macro-/Expectation- und Event-/Policy-/Geopolitics-Collector | Je Quelle erst Genehmigung, Implementierung und Konfiguration nachweisen. Fehlender Collector ist `NOT_CONFIGURED`, nicht aktiv. |
| Crypto-Regime, Identity-/Listing- und Market-/Sector-Daten | Vorhandene Quellen inventarisieren; eingefrorene Historie nicht mit prospektiver Sammlung gleichsetzen. |

Abnahme: reproduzierbarer Health-Bericht mit Source-/Task-Belegen, korrekter Missingness, getesteter Idempotenz und sichtbaren Datenlücken. Integritätsfehler, ungeklärter Writer oder verbotene Datenmutation ⇒ fail-closed stoppen. Produktionspriorität, reale Konflikt-/Research-Locks und serieller SQLite-Writer bleiben erhalten; hier wird keine Schedulerlogik geändert.

## Phase 1 – PIT Data Engine (Arbeitspakete A–I)

Ziel ist ausreichende, ehrliche Information **vor** neuer Multi-Factor-Strategiesuche. Neue Quellen benötigen einen konkreten Quellen-/Lizenz-/Kosten-/Sammlungsauftrag; diese Roadmap allein startet keinen Collector. Nach Betriebsprüfung zuerst 1A und die Quellenverträge für 1B/1C klären, damit Abhängigkeiten und nicht rekonstruierbare Erwartungen prospektiv erfasst werden können.

Für jedes Paket liefern: versioniertes Schema + Herkunft/Verfügbarkeitszeiten, inkrementellen append-only Import, deterministische Fixtures, No-lookahead-/Revisions-/Resume-/Deduplizierungstests und Coverage nach Assetklasse, Markt, Zeitraum und unabhängigen Clustern. Fehlende Felder bleiben unbekannt. Historische Verfügbarkeit aus Originalbelegen und heutiges `first_seen_at` getrennt halten; keine erfundene damalige Beobachtung.

| Paket | Inhalt / Datenanforderung | Abnahme / harte Grenze |
|---|---|---|
| 1A – Identity / Historical Dependencies | `asset_id`, `listing_id`, `issuer_id`, CIK, ISIN, FIGI, LEI, ADR/ADS-Beziehungen, `valid_from`/`valid_to`, Mergers, Spin-offs, Ticker-/Listingwechsel; verifizierte Quellenintervalle. | Historische Cluster und Unsicherheit belegbar. Heutige Identity nicht rückdatieren; unbekannte Abhängigkeiten erzeugen kein künstliches Effective N. |
| 1B – Fundamentals | Offizielle SEC Filings, FSDS, XBRL / Unternehmens-Filings; `accepted_at`, `filed_at`, `first_seen_at`, Quelle, Revision. Revenue/Growth, Earnings/EPS, Gross-/Operating-Margin, Cash, Debt/Net Debt, FCF/OCF, Shares Outstanding, Dilution, Bilanzqualität, Cash Runway. | As-of-Join nur auf damals verfügbare Versionen; Berechnungsgrundlagen nachvollziehbar. Kein heutiger Snapshot als Historie. |
| 1C – Expectations / Surprise | EPS-/Revenue-Erwartung vs. Actual, Makrokonsens vs. Veröffentlichung, Zentralbankerwartung vs. Entscheidung; prospektive Sammlung besonders priorisieren. | `expected_known_at < release_at`; Erwartung fehlt ⇒ `UNKNOWN`, keine künstliche Surprise. Revisionen und Zeitpunkt der tatsächlichen Zahlen erhalten. |
| 1D – Events / Catalysts | Earnings, Guidance, M&A, Kapitalmaßnahmen, Produkt, Clinical, Regulatory, Legal, Management, Supply Chain, damals bekannte zukünftige Termine; `published_at`, `first_seen_at`, `effective_at`, Quelle, Revision, Asset-/Issuer-Zuordnung, Qualität. | Ereignisdefinition ohne spätere Kursreaktion; Kalendertermin nicht als Überraschung oder Ereignisinhalt ausgeben. |
| 1E – Makro | Policy Rates, Yield Curves, Inflation, Labour Market, GDP, PMI, Liquidity, Dollar, relevante Rohstoffe, Risk Regime. | Vintages/Revisions und Veröffentlichungslags korrekt; revidierte Endwerte ersetzen keine damalige Sicht. |
| 1F – Politik / Geopolitik | Belegte Sanctions, Tariffs, Export Controls, Regulierung, offizielle Regierungsentscheidungen, Interventionen, bestätigte geopolitische Ereignisse. | Keine subjektive Newsbewertung; Asset-Relevanz mit Quelle belegen. Historisch fehlend ⇒ `SHADOW` / `UNAVAILABLE`, erst prospektiv sammeln. |
| 1G – Relative Strength / Market / Sector | Asset vs. Market, Asset vs. Sector, Sector vs. Market; 20/60/120-Renditen, Breadth, Rotation, Trend/Regime, Volatilität. | Historische Sector Membership, Benchmark-/Listingkontinuität und damaliges Universum prüfen; heutige Sektorzuordnung nicht rückdatieren. |
| 1H – Crypto | BTC-Regime, RS zu BTC, Dominance, Breadth, Liquidität, Volumen, Volatilität; On-Chain optional nur bei echter PIT-Historie. | Unabhängige Quellen-/Zeitbelege, Survivorship sichtbar; kein komplexes Crypto-ML als Rettung fehlender Daten. |
| 1I – FX | Canonical Sessions, Rates, Zinsdifferenzen, Expectations, Carry, COT, Volatilität, Interventionen, Kostenproxies / echte Quotes soweit vorhanden. | Veröffentlichung, Handelszeit und Ausführbarkeit getrennt belegen; fehlende Expectations prospektiv sammeln, keine fingierte Carry-/Kostenhistorie. |

**Coverage-Gate:** Vor Outcome-Einsicht je benötigter Informationsfamilie Mindest-Coverage, unabhängige Cluster, Zeitbreite, Quellenalter, Missingness und zulässige Asset-Scope-Grenzen präregistrieren. Nicht 100 % Coverage verlangen, aber keinen Grenzwert nach Ergebnis wählen. Familienstatus: `ACTIVE_PIT`, `LIMITED_SCOPE`, `SHADOW`, `UNAVAILABLE` – getrennt vom operativen Health-Status. Fehlende Pflichtfamilie, ungesicherte Dependencies oder unbestimmtes Gate ⇒ `DATA_INSUFFICIENT`, keine neue Suche. Ein transparenter begrenzter Scope ist nur mit vorab begründetem Vertrag zulässig, nicht als Performance-Selektion.

## Gemeinsamer Vertrag für alle Research-Phasen

Die folgenden Limits sind **geplante Obergrenzen für einen später ausdrücklich freizugebenden neuen Zyklus**, keine Freigabe und kein Reset abgeschlossener Attempt-Budgets. Jeder Test benötigt vor Outcomes einen versionierten Vertrag mit:

- konkreter Hypothese, Scope/Datenanforderung, As-of-/Dependency-/Coverage-Gate und unverändertem Dataset-Fingerprint;
- Baseline, genau benannten Varianten/Interaktionen, Kostenmodell, numerischem Attempt Limit und kumulativem Attempt-Register;
- vorab fixierten Akzeptanzschwellen für Netto-Zusatznutzen, Effective N, Unsicherheit, Drawdown, zeitliche/Markt-Stabilität und Komplexität;
- Development-internen, zeitlich getrennten Walk-Forward-Folds mit Purging/Embargo; globales Validation/Holdout bleibt dabei geschlossen;
- explizitem PASS/FAIL/UNDERPOWERED/INVALID, Kill Rule, Stop-Bedingung, erlaubter Folgestufe und verantwortlicher Freigabe.

Fehlt ein Pflichtwert, startet kein Test. Daten-/Integritätsbruch ⇒ `INVALID`; kleine unabhängige Stichprobe ⇒ `UNDERPOWERED`, keine Verbesserung behaupten; fehlender/instabiler Netto-Mehrwert ⇒ `FAIL`. Nach Limit, Fail oder ausgeschöpfter Evidenz endet die jeweilige Hypothese ohne Retune. Nur eine **bereits vertraglich genehmigte**, fachlich eigenständige nächste Schicht darf geprüft werden; kein Testen bis irgendetwas positiv wird. Kein Cartesian Product, Parameter-Mining oder nachträgliches Stapeln korrelierter Bestätigungen. Negative Ergebnisse ebenfalls speichern.

## Phasen 2–7 – getrennte Bausteine, keine aktive Strategie

Kanonische Opportunity-Hypothese: Hochwertige Swing-Chancen treten häufiger auf, wenn Unternehmensqualität/Bilanz, Erwartungen oder Surprise/Catalyst, Markt/Sektor, Relative Strength, Regime und technische Struktur bei realistischem strukturellem Risiko gemeinsam günstig sind. Erst Einzelmehrwert messen, dann wenige begründete Kombinationen; diese Annahme ist noch kein Kaufkriterium.

| Phase | Hypothese / Voraussetzung und geplantes Ergebnis | Attempt Limit, Abnahme und Stop |
|---|---|---|
| 2 – Opportunity / Asset Selection | Nach Coverage-PASS prüfen, ob unabhängige Informationsfamilien das zukünftige Upside-vs-Structural-Risk-Profil verbessern. **Alle geeigneten handelbaren Assets** analysieren, kein prognostischer Candidate-Vorfilter. Erst Einzelmehrwert: Fundamental Quality/Downside → Expectations/Surprise → Market/Sector/RS → Event/Catalyst → Technical Structure → Macro Regime. Ergebnis `WATCH`, `NO_TRADE`, `DATA_INSUFFICIENT` mit Gründen, noch kein `BUY_SIGNAL`. | Maximal **1** präregistrierte Hypothese je dieser **6** Familien, danach höchstens **2** begründete Interaktionen insgesamt. Netto-Zusatznutzen und Robustheit gegenüber der einfacheren Baseline auf Development-internen ungesehenen Folds belegen. Kein brauchbarer Einzelmehrwert ⇒ keine Interaktionsrettung; kein robuster Opportunity-Baustein ⇒ Phase 4 gesperrt. |
| 3 – Thesis Engine | Aus belegten Opportunities eine versionierte These: mögliche Aufwärtstreiber, Catalysts, eingepreiste Erwartungen, Gegenargumente, Risiken, Widerlegung, Datenqualität und Confidence. Jede qualitative Aussage auf Daten/Quellen zurückführen. | **0** neue Performance-Suchversuche; ein Daten-/Begründungsvertrag. Abnahme mit As-of-, Quellen-, Widerspruchs- und Versionstests. Nicht belegte Aussage ⇒ unbekannt/keine These; keine LLM-Fantasie. |
| 4 – Entry Planner | Erst nach robustem Opportunity-Nachweis und prüfbarer These; immediate entry, Pullback, Support Retest, Breakout oder Confirmation fachlich vergleichen. Plan: Entry Zone, Alternative Zone, Breakout Level, Confirmation, maximal akzeptabler Preis, Invalidation, Gültigkeitsbedingungen. Ausgabe `ENTRY_READY`, `WAIT`, `ENTRY_INVALID`. | Höchstens **2** vorab ausgewählte Varianten gegen **1** eingefrorene Vergleichsbaseline, keine Kombinationen aller Entry-Arten. Ausführbare kausale Signale und Netto-Mehrwert auf Development-Walk-Forward nötig. Kein Vorteil ⇒ Variante verwerfen; keine neue technische Confluence als Rettung. |
| 5 – Independent Risk / Portfolio Risk | Vorhandene unabhängige Engine prüfen/ergänzen: Positionsrisiko, Größe, maximaler Verlust, Portfolio Open Risk, korrelierte/Branchen-Exposures, Liquiditätsgrenzen, Cash Usage. Strukturelle Invalidation ist Risikoreferenz; breitere Safe Zone bedeutet kleinere Position, nicht automatisch schlechter Trade. | **0** Performance-Optimierungen; ein vorab definierter Risikovertrag mit Grenz-/Gap-/Stress-/Invarianztests. Strategie und KI dürfen Risk Engine nie überschreiben. Fehlende Quote, Währung, Kapital- oder Risiko-Basis ⇒ keine Freigabe. Neue Safe-Zone-Produktregel nur nach eigener Validierung. |
| 6 – Position Monitor | Preisstruktur, ursprüngliche These, neue Catalysts/Earnings/Fundamentals, Sektor, Markt, RS, Makro, Events und Datenqualität laufend prüfen. Zustände `HOLD`, `ATTENTION`, `PROTECT`, `EXIT_REVIEW`. | **0** zusätzliche Performance-Suchen; ein versionierter Zustandsvertrag, Replay-/Deduplizierungs-/Recovery-/Missingness-Tests. Bestätigte höhere Böden dürfen Long-Schutz **nur nach oben** ratcheten; niemals nach unten erweitern, um Verluste weiterzuhalten. Datenlücke ⇒ sichtbare Unsicherheit, kein erfundener Zustandswechsel. |
| 7 – Dynamic Exit Engine | Bei eingefrorenem Entry-/Risk-/Monitor-Kontext prüfen: Protective Structure Break, Thesis Deterioration, RS Deterioration, Markt-/Sektorverschlechterung, negative Fundamental-/Eventänderung, Overextension + Rejection, Profit Giveback, Opportunity Cost. Ziel: robusten Trendanteil erfassen, nicht lokales Hoch perfekt treffen. | Höchstens **2** fachlich vorab ausgewählte Exit-Varianten gegen **1** feste Baseline; keine Grid Search. `HOLD`, `PROTECT`, `PARTIAL_EXIT`, `FULL_EXIT` benötigen getrennt belegte Regeln und Netto-/Drawdown-/Stabilitätsgates. Zeit allein kein Exit; fehlender Mehrwert ⇒ verwerfen, kein fixer 2R-Produktzwang. |

Eine komplexere Regel braucht robusten inkrementellen OOS-/Walk-Forward-Mehrwert gegenüber der einfacheren Variante. Isolierte Bausteinergebnisse sind noch keine Strategiekennzahlen und keine globale Validation. Langfristige Investment-Verkäufe bleiben ein anderes Modul: These, Fundamentals, Bewertung, Bilanz/Risiko, Konzentration und Kapitalallokation prüfen – weder kurzfristige Angst als automatisches Sell noch „niemals verkaufen“.

## Phasen 8–18 – Gesamtstrategie und stufenweise Freigabe

| Phase | Voraussetzung / prüfbare Lieferung | Limit / Gate / Stop |
|---|---|---|
| 8 – Integrated Fixed Challenger | Genügende Evidenz für Opportunity, Thesis, Entry, Risk, Monitor und Exit; **genau eine** vollständige Version inklusive Universum, Datenvertrag, Zustandslogik, Kosten, Portfolio- und Evidenzregeln einfrieren. Eigener Strategy-Fingerprint, separater append-only Store, alle Bausteinreferenzen. | **1** integrierter Kandidat; kein nachträgliches Kombinieren nach Ergebnisbetrachtung. Integrity-/Reproduzierbarkeits-PASS und explizite Phase-9-Freigabe erforderlich. Fehlender Bausteinnachweis ⇒ kein Freeze als „validiert“ und kein Lauf. |
| 9 – Development / Walk-Forward | Eingefrorene **Gesamtstrategie**, nicht bloß Fallstatistik, simulieren. Kapital, offene/überlappende Trades, Portfolio-Cash, Sizing, Korrelation, Sektorcluster, gesamtes offenes Risiko, Kosten/Slippage/Gaps, relevante Finanzierungs-/Haltekosten, realisierte/unrealisierte P&L, Kapitalbindung und Drawdown modellieren. | **1** registrierter Lauf mit vorab fixierten Folds; exakter technischer Resume kein neuer Versuch. Expected R, PF, Win/Loss, Ø Gewinner/Verlierer, Max Drawdown, risikoadjustierte Rendite, Turnover, Kapitalnutzung, Stabilität/Regime und Komplexitätsmehrwert gegen feste Baseline prüfen. Kein Portfolio-/Kostenmodell oder Gate-Fail ⇒ Stop vor OOS. |
| 10 – Validation | Phase-9-PASS, unveränderte Version, getrennte nach Seen-Register wirklich ungesehene Daten; gleiche vollständige Simulation. | **1** Auswertung. FAIL/UNDERPOWERED/INVALID ⇒ Version terminal verwerfen, kein Holdout. PASS erlaubt nur bei gesondert ausdrücklich freigegebenem Stage-Vertrag Phase 11, keine Regeländerung. |
| 11 – Holdout | Validation-PASS und gesonderte Freigabe; einmaliger ungesehener Test mit identischen Regeln. | **1** Auswertung, kein Rescue/Retune. FAIL/UNDERPOWERED/INVALID ⇒ terminal Stop. PASS = starker Kandidat, **keine Produktionsfreigabe**. |
| 12 – External Unseen Universe | Holdout-PASS; vorab festgelegte neue Assets/Marktbereiche, nicht in Entwicklung gesehen, Scope-/Dependency-/Coverage-PASS und Freigabe. | **1** externer Test; keine nachträgliche Auswahl positiver Märkte. Fehlende Generalisierung oder unzureichende unabhängige Evidenz ⇒ Stop, kein True Forward. |
| 13 – True Forward Signals | External-PASS und eigener prospektiver Vertrag; zunächst **nur Signalbot**: WATCH, BUY_SIGNAL, HOLD, PROTECT, SELL_SIGNAL mit Version/Zeit/Daten/Gründen append-only. Nutzer führt reale Orders selbst aus. | **1** vorregistrierte Beobachtungsepoche mit Mindest-Effective-N, Zeitraum und Endtermin vor Start; kein optionales Stoppen bei gutem Ergebnis. Signalresultate, Nutzertrades und Research getrennt. Gate-Fail oder zu wenig Evidenz am Endtermin ⇒ Stop/UNDERPOWERED, kein Paper-Aufstieg. |
| 14 – Autonomous Paper | Forward-PASS und ausdrücklicher Paper-Vertrag: vollständiger Scan→Entry→Size→Hold→Exit-Zyklus ohne Nutzerentscheidung; separates simuliertes Kapital. | **1** vorab begrenzte Epoche; Kosten-, Kapital-, Audit- und Betriebsgates. Keine echten Orders; Fail/Unterpowerung ⇒ keine Shadow-Freigabe. |
| 15 – Shadow Live | Paper-PASS und eigener Shadow-Vertrag: auf aktuellen Bedingungen hypothetische Orders erstellen, **niemals senden**. Reale Spreads/Quotes, Slippage, Delays, Rejections und Liquidität prüfen. | **1** begrenzte Epoche mit Ausführungs-/Latenz-/Fehlergrenzen; kein Broker-Sendepfad freigegeben. Unzureichende Ausführbarkeit ⇒ Stop vor Echtgeld. |
| 16 – Echtgeld-Gate | Manuelle Gesamtprüfung: historische Evidenz, Validation, Holdout, External, Forward, Paper, Shadow, unabhängiges Risiko, Execution Safety, Rollback und Kill Switches gemeinsam. | **1** dokumentierte Gesamtentscheidung, **kein automatischer PASS**. Fehlende Evidenz oder Nutzerfreigabe ⇒ Orders geschlossen. |
| 17 – Begrenzter Live-Bot | Erst nach Phase 16 und **neuer ausdrücklicher Nutzerfreigabe** autonome Execution separat entwickeln/prüfen/aktivieren. Separates kleines Bot-Kapital, harte Verlust-/Exposures-/Liquiditäts-/Orderlimits, manueller Kill Switch, Rollback, Positionsabgleich. | **1** explizit budgetierter Pilot; anfangs kein Hebel, außer separat validiert und genehmigt. Integritäts-, Risiko- oder Ausführungsgrenze verletzt ⇒ neue Orders stoppen und sicheren vorab vereinbarten Betriebszustand herstellen, keine improvisierte Notliquidation. |
| 18 – Kontrollierte Skalierung | Erst nach belegtem Live-Pilot-PASS jede Kapitalstufe einzeln auf Netto-Evidenz, Kapazität, Drawdown, Betrieb und Risiko prüfen und freigeben. | **1** vorab begrenzte Stufe je neuer Entscheidung; kein automatisches exponentielles Scaling. Gate-Fail ⇒ keine Erhöhung, Rücknahme/Stop nach vorher festgelegtem Risikovertrag. |

**Seen bleibt seen:** Validation/Holdout/External werden nicht durch neue Run-ID, Epoch oder Store wieder ungesehen. Vor jeder Stufe Überschneidungen, Issuer-/Listingabhängigkeiten und bereits betrachtete Zeiträume prüfen. Originale, Frozen Dataset, Broad-v1, Buyer, Failed-Seller-Rohmetriken und abgeschlossene Kampagnen bleiben immutable. Technische Replays liefern Reproduzierbarkeit, keine zusätzliche unabhängige Evidenz.

## Geschlossene Pfade und eng begrenzte Reserve

Buyer Confirmation v1, Fibonacci, Failed Seller, Overnight Bias, Wasser R1 und Discovery v1/v2 Technical-only bleiben negativ/inconclusive abgeschlossen, keine offene Wiederholungsqueue. Auch FX Carry PIT wird nicht still wieder geöffnet. Nur wirklich neue Daten oder ein klar anderer Mechanismus **plus neuer ausdrücklicher Auftrag** dürfen eine eigenständige Hypothese begründen; keine Retunes, Umbenennungen oder Holdout-Rettung. Einzelresultate bleiben in [Status](PROJECT_STATUS.md), Reports und KB.

Research-Reserve: Stochastic, Williams %R, CCI, gezielte zusätzliche ROC-Varianten, weitere MACD-Parametersets, Moving-Average-Kombinationen, Ichimoku, Supertrend und begrenzte Candlestick-Pattern-Gruppen. Weitere vergleichbare Indikatoren nur bei klar begründetem Zusatznutzen. Nicht implementieren oder pauschal testen, nur weil populär. Nach abgeschlossener Auswertung aktiv wieder vorschlagen, **wenn** Gewinner-/Verlierer-Trennung eine relevante Erklärungslücke hat, Development wiederkehrende fachliche Struktur zeigt, Forward-Fehlerdiagnosen dasselbe ungemessene Muster zeigen oder ein Baustein eine konkret belegte Messlücke besitzt. Fehlende PIT-Provenienz wird nicht durch weitere Indikatoren geheilt.

Beispiele: unzureichende Momentumtrennung → eine begrenzte Stochastic/Williams-%R/CCI-Hypothese; unklare Trendqualität trotz EMA/Slope → Supertrend oder Ichimoku; relevante Momentumänderung → eine ROC-Variante; unzureichende Candle-Rohmerkmale → kleine vorab definierte Reversal-Pattern-Gruppe. Pro Vorschlag Hypothese/Lücke, wenige feste Parameter, Redundanz und Attempt-Budget nennen; zuerst nur Development, bei Zusatznutzen einfrieren, dann gesondert freigegebene ungesehene Evidenz. Kein Holdout zur Auswahl, keine großen Grids, nicht mehrere Reserveindikatoren gleichzeitig als neue Confluence. Ohne Zusatznutzen verwerfen/dokumentieren.

`Current Broad Feature Set → Broad Research Results → identify unresolved information gaps → actively reconsider Research Reserve → test only justified reserve hypotheses → freeze → Validation / Holdout`

## Parallele Produktarbeit und spätere Abarbeitung

Während Phase 1 nur direkt unterstützende Arbeit vorziehen: Data Health UI, Signal-/Trade Audit, Watchlist, Thesis Display, Position Monitor UI, Trade Journal, Risk View. Anzeigen geplanter Module dürfen keine vorhandene Evidenz vortäuschen. Allgemeines Redesign, Investment Opportunities Feed, Komfortfunktionen, unnötige Exporte und dekorative UI bleiben hinter dem SwingTrader-Kern.

Wenn der Nutzer später `/goal` oder `Arbeite die Roadmap ab` beauftragt:

1. Current Truth, Policy und aktiven Phasenvertrag lesen; Git/Prozesse/geschützte Daten prüfen.
2. Aktive Phase und Voraussetzungen feststellen; zunächst Phase 0 prüfen, dann die höchste sichere freigegebene Phase-1-Aufgabe.
3. Aufgabe innerhalb ihres Vertrags implementieren und angemessen testen; eigene Änderungen sauber committen/pushen, CI prüfen.
4. Current Truth und verbleibende Roadmap-Arbeit nur nach Belegen aktualisieren; nächste zulässige Aufgabe **derselben Phase** bearbeiten.
5. Bei fehlender Quelle/Freigabe, hartem Gate-Fail oder ausgeschöpftem Attempt-Budget konkret stoppen. Ein allgemeines Startsignal öffnet weder eine neue Research-Stufe noch neue kostenpflichtige Quellen, Broker oder Orders. Jeder Phasenübergang braucht sein belegtes Gate und ausdrücklichen Stage-Vertrag; hier ist noch keiner erteilt.

Vor einem später freigegebenen größeren Lauf kontrollierten Worker-Pool/Benchmark vorschlagen; Parallelität erst nach Gleichheits-, Integritäts- und Ressourcenprüfung wählen. Keine parallelen Shards auf derselben DB, ein Writer, globale Locks und sichere Checkpoints bleiben Pflicht. Effizienz verändert weder Stichprobe noch Forschungsqualität.

Nur bei tatsächlichem Kontingentstopp einen konsistenten Checkpoint mit Branch/Commit, letztem fertigem Abschnitt und nächstem Schritt sichern. Dann ausschließlich eine nachweislich unterstützte Wiederaufnahme nach fünf Stunden verwenden und bei weiter fehlendem Kontingent erneut fünf Stunden später prüfen. Ohne bestätigten Mechanismus `MANUAL_MODEL_RESUME_REQUIRED` dokumentieren; keine Wiederaufnahme versprechen. Dieser Dokumentationsauftrag richtet keine Automation ein.

**Abnahme dieses Plans:** Dokumentations-/Policy- und Linkprüfungen, Archivgleichheit, Repo Safety, `git diff --check`, sauberer Commit/normaler Push und CI-Status. Danach **auf Nutzer-Startsignal warten**; keine Umsetzung der neuen Roadmap beginnen.
