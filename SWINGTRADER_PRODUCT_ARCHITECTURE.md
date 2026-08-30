# SwingTrader – kanonische Produktarchitektur

Stand: 2026-08-30

Dieses Dokument ist das verbindliche langfristige Zielbild für den SwingTrader des Investment-Assistenten. Es beschreibt keine neue aktive Handelslogik und erteilt keine Produktions-, Broker- oder Echtgeldfreigabe. Der belegte Ist-Stand bleibt in `PROJECT_STATUS.md`; Prioritäten und offene Arbeit stehen in `ROADMAP.md`.

## Kernsatz

**Research Baseline != Production Strategy.**

Next-Open-Entry, fixer Stop, fixer 2R-Exit, 5/10/20/25-Sitzungs-Labels und feste maximale Forschungshorizonte sind kontrollierte wissenschaftliche Baselines oder Counterfactuals. Sie machen einzelne Merkmale vergleichbar. Sie sind nicht automatisch das spätere Produktverhalten.

Der SwingTrader ist langfristig **kein klassischer Daily-Trading-Bot**. Das Ziel ist ein transparenter, regelbasierter Multi-Factor Swing-/Investment-Assistent. Ein Trade kann Tage, Wochen oder länger laufen, solange These, Invalidation und verbleibendes Chance-Risiko-Verhältnis intakt bleiben. Zeit allein ist kein primärer Exit-Grund.

## Langfristiges Produktziel

Das vollständig validierte spätere System soll:

1. ein großes, tatsächlich handelbares und listinggenaues Asset-Universum prüfen,
2. attraktive Chancen aus mehreren fachlich getrennten Informationsschichten priorisieren,
3. eine belegte Aufwärts- beziehungsweise Investmentthese mit Gegenargumenten bilden,
4. einen konkreten bedingten Entry-Plan statt eines blinden Sofortkaufs erstellen,
5. Risiko, Positionsgröße und Portfolio-Open-Risk unabhängig von der Strategie begrenzen,
6. offene Positionen mit Preis-, Markt-, Sektor-, Event- und Unternehmenskontext überwachen,
7. `HOLD`, Stop-Nachzug, Teilgewinn oder vollständigen Exit regelbasiert neu beurteilen,
8. jede Entscheidung mit Datenstand, Gründen, Unsicherheit und Version nachvollziehbar speichern.

`No Trade`, `Warten`, `Watchlist` und `Daten nicht ausreichend` sind vollwertige Ergebnisse. Das System muss keine Position erzwingen.

## Statusbegriffe

- **Aktuell vorhanden:** technisch umgesetzt und im Projekt nachweisbar; das bedeutet nicht automatisch performancevalidiert oder produktionsfreigegeben.
- **Research/Shadow:** vorhanden oder geplant, aber ohne aktive Signal-, Score-, Risiko- oder Orderwirkung.
- **Langfristiges Ziel:** noch nicht als vollständiges Produktmodul umgesetzt oder validiert.

## Zielarchitektur

### A. Data Quality / Point-in-Time Layer

Aufgaben:

- Identität von Emittent, Listing, Instrumenttyp, Börse und Währung sichern.
- Datenzeitpunkt, Quelle, Revision, Veröffentlichungszeit, Lag, Coverage und Missingness speichern.
- Zukunftswissen, rückdatierte heutige Daten und still vermischte Listings verhindern.
- Unsicherheit und nicht verfügbare Daten sichtbar halten.

Aktueller Stand: Der future-only Research-Identity-Vertrag v3 trennt Asset, Listing und nur über belastbare LEI-/CIK-/FIGI-/ISIN-/Börsen-/ADR-Anker bekannte Issuer; unbekannte Beziehungen werden nicht als unabhängige Evidenz gezählt. Ein zentraler Listing-Bundle-Guard sperrt gemischte OHLCV-, Kurs-, Währungs-, Handelszeit-, Entry-, Stop- und Zieldaten. Für das aktuelle Universum sind wegen eines realen HTTP-403-Fehlers der kostenlosen SEC-Quelle alle 2.520 Issuer-Zuordnungen weiterhin sichtbar unbekannt; der Multi-Asset-Precheck bleibt deshalb gesperrt. Die FX-PIT-Grundpipeline modelliert Paarinversion, Session, Verfügbarkeit und Revisionen und hält inzwischen 12.779 tägliche Kursbeobachtungen für EUR/USD, USD/JPY und GBP/USD von 2010 bis 2026. Ein getrennter append-only FX-PIT-Observer sammelt täglich um 21:45 Uhr Kurs-, COT-, Missingness- und Source-Health-Evidenz ohne Strategie- oder Tradepfad. Fehlende historische Erwartungen, Makro-Vintages, Policy Rates und Bid/Ask bleiben ehrlich nicht verfügbar. Die vollständige historische Coverage für Fundamentals, Erwartungen, Events, Branchen, Handelbarkeit und Mikrostruktur ist weiterhin nicht vorhanden.

### B. Asset Discovery / Opportunity Engine

Aufgaben:

- großes handelbares Universum stufenweise scannen,
- Multi-Factor-Chancen erkennen und priorisieren,
- unabhängige Informationsfamilien statt bloßer Rohfeaturezahl bewerten,
- Redundanz, Korrelation, Datenqualität und Marktregime berücksichtigen,
- bewusst keine Idee anzeigen, wenn kein Kandidat ausreichend gut ist.

Aktueller Stand: Das technische Swing-Universum, regionale Scans, Grobfilter und die vollständige Prüfung vorhandener Long-v1-Setups sind vorhanden. Ein validiertes Multi-Factor-Opportunity-Ranking aus Fundamental-, Markt-, Makro-, Event- und Technikschichten existiert noch nicht.

### C. Thesis Engine

Aufgaben:

- verständlich beantworten, warum ein Asset steigen könnte,
- bullische Treiber, erwartete Katalysatoren und bereits eingepreiste Erwartungen trennen,
- Risiken, Gegenargumente und widerlegende Bedingungen aktiv suchen,
- Confidence und Unsicherheit aus Quellenlage und Evidenz ableiten,
- These versioniert neu bewerten, ohne alte Stände umzuschreiben.

Aktueller Stand: Asset-Analyse, Quellen-/Research-Bausteine, Event-Research und eine getrennte langfristige Investment-Verkaufsprüfung liefern Teilgrundlagen. Eine integrierte, validierte Swing-Thesis-Engine ist noch nicht umgesetzt.

### D. Entry Planner

Aufgaben:

- primäre Kaufzone,
- alternative tiefere Kaufzone,
- Breakout-Level und Bestätigungsbedingungen,
- Tranchengröße und Reihenfolge,
- Nachkaufbedingungen,
- Invalidation,
- Vorgehen, wenn der erwartete Rücksetzer nicht kommt.

Ein attraktives Asset darf auf der Watchlist bleiben, bis Preis und Bedingungen passen. Ein blindes Next-Open-Kaufen ist kein Produktstandard.

Aktueller Stand: Der Swing Trade Finder erzeugt für vorhandene Setups einen versionierten Orderplan mit Einstieg, Aktivierung/Limit, Maximalpreis, Stop, Zielen, Gültigkeit und Nichteinstiegsbedingungen. Next-Bar-/Next-Open-Annahmen bleiben in historischen Tests kontrollierte Ausführungsbaselines. Ein vollständiger Multi-Factor- und Thesen-gesteuerter Entry-/Tranchenplaner ist noch nicht umgesetzt.

### E. Independent Risk Engine

Aufgaben:

- Positionsgröße aus Entry, Invalidation und maximal zulässigem Risiko bestimmen,
- Risiko je Position, offenes Gesamtrisiko und Kapitalbelastung begrenzen,
- Korrelationen und Cluster im Portfolio berücksichtigen,
- bei widersprüchlichen Daten fail-closed handeln,
- von Strategy Engine, KI und Research nicht überschreibbar sein.

Aktueller Stand: Eine gemeinsame unabhängige Risk Engine für Analyse, Paper und Shadow ist technisch vorhanden und ausschließlich brokerlos. Ihre heutigen Regeln bleiben durch dieses Zielbild unverändert.

### F. Position Monitor

Aufgaben:

- ursprüngliche These und Invalidation fortlaufend prüfen,
- Preisstruktur, Markt, Sektor, Events und Unternehmensentwicklung neu bewerten,
- Datenalter, fehlende Quellen und Unsicherheit melden,
- Handlungszustände wie `HOLD`, `AUFMERKSAMKEIT`, `RISIKO REDUZIEREN` oder `EXIT PRÜFEN` nachvollziehbar ableiten.

Aktueller Stand: Technische Nutzertrade-Begleitung, Stop-/Zielprüfung und einige Struktur-/Volumenhinweise existieren. Eine vollständige fortlaufende Thesis-, Fundamental-, Sektor-, Makro- und Event-Neubewertung ist noch nicht umgesetzt oder validiert.

### G. Dynamic Exit Engine

Aufgaben:

- `HOLD`, Stop-Nachzug, Teilgewinn und vollständigen Exit getrennt beurteilen,
- eine Position über Seitwärtsphasen halten können, solange These und Invalidation intakt bleiben,
- aussteigen, wenn erwartetes zusätzliches Upside gegenüber Rücksetzungs-/Verlustrisiko nicht mehr attraktiv ist,
- technische Verschlechterung, Strukturbruch, Thesis Deterioration, negative Events und spätere zulässige Kapitalallokation berücksichtigen.

Das Ziel ist nicht, jedes lokale Hoch exakt zu treffen. Ziel ist, einen robusten Anteil eines Trends mitzunehmen und bei schlechter gewordenem verbleibendem Chance-Risiko-Verhältnis kontrolliert zu reagieren.

Aktueller Stand: Die bestehende Swing-Logik besitzt feste Stops, Ziele, Teilgewinn-/Restpositionsregeln und getrennte Paper-Auswertung. `investment_exit_policy.py` hält langfristige Investment-Verkaufsgründe ausdrücklich von Swing-Regeln getrennt. Eine validierte dynamische Swing-Exit-Engine ist noch nicht umgesetzt. Teilgewinn-, Trailing- und Protect-Profit-Varianten bleiben Research-Themen.

### H. Monitoring / Audit

Aufgaben:

- Eingangsdaten, Entscheidung, Gründe, Unsicherheit, Version und Zeitpunkt speichern,
- Research-, Forward-, Paper-, Shadow-, Nutzer- und spätere Live-Evidenz getrennt halten,
- Idempotenz, Restart, Positionsabgleich und nachvollziehbare Fehlerzustände sichern,
- Black-Box-Produktionsentscheidungen verhindern.

Aktueller Stand: Append-only Stores, Fingerprints, Research Knowledge Base, Forward-, Paper-, Shadow- und Nutzertrade-Evidenz schaffen wesentliche Grundlagen. Die vollständige durchgängige Auditkette des langfristigen Produkts bleibt geplant.

## Informationsschichten der späteren Asset-Auswahl

Alle Merkmale müssen kausal und Point-in-Time verfügbar sein. Fehlende Informationen werden nicht erfunden oder aus heutigen Daten rückdatiert.

### Unternehmen / Fundamental

- Umsatz- und Gewinnentwicklung,
- Guidance und damalige Erwartungen,
- Margen, Bewertung und Bilanz,
- Earnings, Auftragslage und Kapitalmaßnahmen,
- wichtige Unternehmensmeldungen,
- belastbare Analystenerwartungen nur mit korrektem damaligem Zeitpunkt.

### Markt / Sektor

- Gesamtmarkt- und Sektortrend,
- Relative Strength und Breadth,
- Volatilität und Marktregime,
- Kapitalrotation, sofern belastbar messbar.

### Makro

- Zinsen, Inflation, Liquidität und Konjunktur,
- Währungen und relevante Rohstoffpreise,
- Veröffentlichungszeitpunkte und Revisionen.

### Events / News

- Unternehmenszahlen und Produkt-/Technologieereignisse,
- Zulassungen und regulatorische Entscheidungen,
- politische Entscheidungen und bestätigte geopolitische Ereignisse,
- Markt- und Sektorschocks.

### Technik

- Trend, Momentum und Marktstruktur,
- Unterstützungen, Widerstände und Konsolidierungen,
- Pullbacks, Breakouts und Volumen,
- Gap-/Overnight-Verhalten.

Mehrere Rohmerkmale sind nicht automatisch mehrere unabhängige Bestätigungen. Semantische Überlappung, empirische Korrelation, Feature-Ablation und inkrementeller Zusatznutzen gegenüber einer einfacheren Baseline sind verpflichtend.

## Invalidation, Stop und Positionsgröße

Die primäre Frage lautet:

> Ab welchem Preis- oder Strukturlevel ist die ursprüngliche These nicht mehr gültig?

Aus dieser fachlichen Invalidation entsteht eine Zone beziehungsweise ein Stop-Kandidat. Erst danach berechnet die unabhängige Risk Engine aus Entry, Invalidation und maximalem Portfolio-Risiko die zulässige Positionsgröße.

Ein Stop ist keine Garantie für den Schutz des vollständig investierten Betrags. Gaps, Slippage, Liquidität und Ausführungsfehler können den realen Verlust vergrößern.

## Dynamisches Halten und Verkaufen

Eine Position darf auch mehrere Wochen seitwärts laufen und weiterhin `HOLD` bleiben, wenn:

- sie oberhalb der Invalidation-/Bodenzone liegt,
- die These intakt ist,
- kein zwingender negativer Event vorliegt,
- das verbleibende Risiko vertretbar bleibt,
- eine Sell-Zone oder andere Exit-Bedingung noch nicht erreicht ist.

Eine feste Haltedauer allein darf im späteren Produkt keine automatische Schließung auslösen. Feste Zeitfenster bleiben für Labels, Reviews, Vergleichbarkeit und kontrollierte Baselines zulässig.

## Research-Sequenz und Modulfreigabe

Der verbindliche Forschungsweg bleibt:

`Frozen Historical Data → Development → Fixed Challenger → Validation → Holdout → External Unseen Universe → True Forward → Autonomous Paper → Shadow Live → separates Echtgeld-Gate`

Ein erfolgreiches Entry-Feature ist nur ein Baustein. Folgende Produktmodule benötigen jeweils eigene Evidenz:

- Asset Ranking,
- Thesis / Context,
- Entry,
- Risk,
- Position Management,
- Exit.

Einzeln interessante Bausteine dürfen nicht automatisch zu einer zusammengesetzten Produktionsstrategie verbunden werden. Die Kombination benötigt einen eigenen eingefrorenen Vertrag, inkrementellen Nutzen, OOS-/Walk-Forward-Nachweis sowie die nachgelagerten echten Evidenzstufen.

## Event-, News-, Makro- und Geopolitikstatus

Die vorhandene Architektur bleibt `research_only` beziehungsweise `shadow_only`, solange PIT-Kausalität, Coverage, Relevanz und eigener Zusatznutzen nicht ausreichend validiert sind. Diese Informationen dürfen aktuell keine automatische Score-, Signal-, Risiko- oder Tradewirkung erhalten.

Langfristig dürfen sie Discovery, Thesis und Monitoring unterstützen. Information und Handlung bleiben dabei technisch und fachlich getrennt.

## Broker- und Automationsgrenze

Aktueller Scope:

- keine Brokeranbindung,
- keine automatische Orderausführung,
- keine automatische Echtgeldaktivierung,
- keine produktive Regeländerung aus KI oder Research.

Maschinenlesbare Orderentscheidungen sind nur ein mögliches späteres Ziel. Broker-/Live-Execution bleibt eine separate, ausdrücklich freizugebende Phase nach bestandenem Holdout-, External-, Forward-, Paper-, Shadow- und Echtgeld-Gate. Die Risk Engine und spätere Kill-Switches dürfen von Strategie oder KI niemals überschrieben werden.

## Verbindliche Nicht-Gleichsetzungen

- Daily-Signal ist nicht das vollständige Produkt.
- Next-Open oder Next-Bar ist nicht zwingender Produkt-Entry.
- Fixer 2R-Exit ist nicht das Produktionsziel.
- 25 Sitzungen sind keine maximale Produktionshaltezeit.
- Ein einzelnes technisches Signal ist nicht die vollständige Strategie.
- Mehr Rohfeatures bedeuten nicht mehr unabhängige Evidenz.
- Event-, News-, Makro- oder Geopolitikdaten sind aktuell nicht produktiv aktiv.
- Paper und Shadow sind keine Echtgeldfreigabe.
- Broker- und Auto-Orders sind aktuell nicht aktiv.

## Änderungsgrenze dieses Dokuments

Dieses Zielbild ändert keine Strategy Engine, Signale, Scores, Rankings, Entries, Stops, Ziele, Exits, Scanner, Research-Ergebnisse oder Datenbanken. Historische Research-Artefakte und ihre vereinfachten Verträge bleiben unverändert als wissenschaftliche Referenz erhalten.
