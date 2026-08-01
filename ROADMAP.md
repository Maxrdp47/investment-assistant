# Investment-Assistent Master-Roadmap

## Projektziel

Der Investment-Assistent ist eine lokale Python-Streamlit-App, die Aktien, ETFs und Kryptowährungen analysiert und verständliche Einschätzungen liefert. Die App soll langfristig wie ein professionelles Research-Werkzeug funktionieren: technisch sauber, transparent, nachvollziehbar und auch für Anfänger verständlich.

Die App darf niemals automatisch handeln. Es darf keine Broker-Anbindung, keine Kaufautomatisierung und keine Verkaufsautomatisierung geben. Jede Ausgabe ist nur Analyse- und Entscheidungshilfe. Die finale Entscheidung trifft immer der Nutzer.

Zentrale Bewertungsregel:

- Asset-Qualität bewertet nur das Asset selbst.
- Kaufsignal bewertet nur Marktdaten und den aktuellen Einstiegszeitpunkt.
- Depot-Effekt bewertet nur Portfolio-Daten.
- Portfolio-Daten dürfen Asset-Qualität und Kaufsignal niemals beeinflussen.

Langfristige Qualitätsorientierung:

- Equity-Research-Analyst
- Hedgefonds-Analyst
- Portfoliomanager
- Makro-Research
- Krypto-Research

Die App soll transparent, nachvollziehbar, datenbasiert und anfängerfreundlich sein.

Schutz vor erfundenen Daten:

- Keine Daten erfinden.
- Fehlende Daten immer als `Daten nicht verfügbar` anzeigen.
- Schätzwerte niemals als Fakten darstellen.
- Analystenziele niemals erfinden.
- ETF-Flows niemals erfinden.
- Makrodaten niemals erfinden.

## PRIO 0 – Stabilisierung

Neue ROADMAP-Funktionen bleiben pausiert, bis die bestehende Anwendung die Stabilitätskriterien erfüllt.

- Anwendung startet fehlerfrei: am 2026-07-31 mit `compileall`, Pytest, Streamlit-AppTest und headless Streamlit-Start geprüft.
- Bestehende Funktionen reparieren: History-Lader und Auswertungsdaten tolerieren fehlende, leere und ältere lokale Datenformate.
- Signaturen und Datenmodelle vereinheitlichen: `evaluated_history_cases()` erhält Trade-History, Forward-Tests und Predictions konsistent als getrennte Eingaben; alle Kompatibilitätsaufrufe verwenden dieselbe Reihenfolge.
- Smoke-Tests ergänzen: Startseite, Hauptbedienelemente, leere Histories und unvollständige ältere JSON-Daten werden automatisiert geprüft.
- Logo entfernen: eigenes Browser-Tab-Symbol entfernt; im Repository bestehen keine weiteren Logo-Einbindungen.
- Keine neuen Funktionen entwickeln, bis Start, Hauptanalyse, Portfolio, Trading/Scanner und lokale Historien bei den verfügbaren Tests stabil bleiben.

Stabilitätskriterien:

- Streamlit startet ohne Traceback und zeigt die Startseite.
- Analyse wird erst nach bewusster Betätigung von `Analysieren` gestartet; externe Datenquellen blockieren nicht mehr den initialen Seitenaufbau.
- Fehlende oder ungültige optionale History-Dateien führen zu leeren Ansichten statt zu einem App-Absturz.
- Regressionstests für History-Signaturen und ältere `review_after`-Formate laufen erfolgreich.
- Keine Portfolio-, Analyse-, Trade-History- oder Konfigurationsdaten werden für die Stabilisierung gelöscht.

## Aktueller Projektstand

Analysierter Stand am 2026-06-14:

Vorhandene Dateien:

- `app.py`: Hauptanwendung mit Streamlit-Oberfläche, Kursdaten, Analyse, Research-Modul, Portfolio-Modus und Charts.
- `README.md`: Startanleitung und Erklärung der wichtigsten Funktionen.
- `requirements.txt`: Python-Abhängigkeiten.
- `portfolio.example.json`: anonymisierte Beispiel-Datei für den optionalen Portfolio-Modus.
- `search_history.example.json`: anonymisierte Beispiel-Datei für den Suchverlauf.
- `portfolio.json`: portable Depot-Datei im GitHub-kompatiblen Minimalformat; nur Cash, Ticker, Asset-Typ, Positionsgröße und Kaufkurs.
- `search_history.json`: lokale private Suchhistorie, nicht versionieren.
- `start_investment_assistent.bat`: lokales Startskript für die Desktop-Verknüpfung.
- `.streamlit/`: Streamlit-Konfiguration.
- `.yfinance-cache/`: lokaler yfinance-Cache.
- `.venv/`: lokale Python-Umgebung.
- `.git/`: lokales Git-Repository.

Die App ist funktional und startet lokal über Streamlit. Sie nutzt Yahoo Finance über `yfinance`, arbeitet ohne Broker-Anbindung und enthält bereits viele Research-Bausteine.

## Aktuelle Funktionen

- Eingabe von Asset-Name oder Yahoo-Finance-Ticker.
- Automatische Yahoo-Finance-Suche mit auswählbaren Treffern.
- Fallback-Ticker für bekannte Beispiele wie Xiaomi, Nvidia, Palantir, Bitcoin und MSCI World.
- Speicherung erfolgreicher Suchanfragen in `search_history.json`.
- Anzeige von Firmenname, Ticker, Börse und Währung.
- Automatische Asset-Typ-Erkennung für Aktie, ETF, Krypto und unbekannt.
- Manuelle Asset-Typ-Auswahl, falls die automatische Erkennung unsicher ist.
- Historische Kursdaten über `yfinance`.
- Auswahl von Zeitraum und Intervall.
- Währungsmanagement mit EUR-Anzeige plus Originalwährung.
- Wechselkursanzeige, wenn das Asset nicht in EUR gehandelt wird.
- Technische Indikatoren: RSI 14, MACD, Signal-Linie, 50er Durchschnitt, 200er Durchschnitt, Volumenentwicklung, Volatilität.
- Unterstützungen und Widerstände aus lokalen Tiefs und Hochs.
- CRV, Risiko bis Unterstützung und Potenzial bis Widerstand.
- Marktphasen-Erkennung: Bullenmarkt, Bärenmarkt, Korrektur innerhalb eines Aufwärtstrends, Bodenbildungsphase, Seitwärtsmarkt.
- Wahrscheinlichkeiten für verschiedene Szenarien.
- Getrennte Scores für Asset-Qualität, Kaufsignal und Depot-Effekt.
- Portfolio-Modus per Toggle.
- Depot-Effekt mit Cash, Positionsgröße, Portfolioanteil, Klumpenrisiko, geplantem Nachkauf und Cash-Reserve.
- Anfänger-Modus mit einfachen Erklärungen.
- Research-Modul mit Datenqualitäts-Check.
- Research-Modul-Scores: Charttechnik, Momentum, Bewertung oder Zyklus/On-Chain, Fundamentaldaten oder Krypto-Adoption, Makro, News, Risiko, Liquidität.
- Institutionelle Research-Module: Analysten-Konsens, Earnings, Event-Risiko und institutionelle Daten, sofern Daten verfügbar sind.
- Vertrauensscore zur Belastbarkeit der Analyse.
- Unsicherheitsfaktoren: Was könnte diese Analyse widerlegen?
- Bull/Base/Bear-Szenarien.
- Nachkaufzonen.
- Research-Fazit mit Pro/Kontra, entscheidender Marke und konkretem Plan.
- News-Modul über Yahoo-Finance-News mit einfachem Sentiment.
- Makro-Modul mit Nasdaq, US-Zinsen, Dollar-Index und TIP-Proxy.
- Keine automatische Kauf- oder Verkaufsfunktion.

## Offene Aufgaben

### Priorität 1: Klarheit und Stabilität

- Haupt-Dashboard und Research-Modul vereinheitlichen, damit Empfehlungen nicht doppelt oder widersprüchlich wirken. Status: umgesetzt am 2026-06-15.
- Sichtbare Empfehlung klar trennen in Asset-Qualität, Kaufsignal, Research-Handlungsempfehlung und Depot-Effekt. Status: umgesetzt am 2026-06-15.
- Fehlerbehandlung bei Yahoo-Finance-Ausfällen verbessern. Status: umgesetzt am 2026-06-15.
- Datenqualitäts-Check kompakter und sichtbarer machen. Status: umgesetzt am 2026-06-15.
- Analyse-Daten vollständig von Chart-Daten entkoppeln. Status: umgesetzt am 2026-06-15; Chart-Zeitraum steuert nur Visualisierung, Analyse nutzt maximal verfügbare Tageshistorie.
- Suchhistorie in der Sidebar als auswählbare Schnellwahl nutzbar machen. Status: umgesetzt am 2026-06-15.
- Umlaute und sichtbare deutsche Texte prüfen. Status: umgesetzt am 2026-06-15.
- App-Start und Analysefluss regelmäßig testen. Status: umgesetzt am 2026-06-15.

### Priorität 2: Score-Qualität

- Gewichtungen der Scores transparent dokumentieren. Status: umgesetzt am 2026-06-15.
- Score-Logik kalibrieren. Status: Basis umgesetzt am 2026-06-15; echte Gewichtungsänderungen erst mit ausreichender Historie.
- Asset-Qualität je Asset-Typ verbessern. Status: umgesetzt am 2026-06-15.
- Kaufsignal weiter von Asset-Qualität abgrenzen. Status: umgesetzt am 2026-06-15.
- Research-Scores stärker erklären: Was bedeutet hoch, mittel oder niedrig? Status: umgesetzt am 2026-06-15.
- Nachkaufzonen robuster machen, wenn keine klaren Kurszonen erkannt werden. Status: umgesetzt am 2026-06-15.
- Bull/Base/Bear-Szenarien stärker aus Trend, Volatilität, Unterstützungen und Widerständen ableiten. Status: umgesetzt am 2026-06-15.

### Priorität 3: Profi-Research

- Fundamentaldaten für Aktien erweitern: Umsatzwachstum, Gewinnwachstum, Margen, Verschuldung, Free Cashflow, Cashbestand, Bewertung. Status: erweitert am 2026-07-01; zusätzliche strukturierte Kennzahlen und transparente Detailausgabe eingebaut.
- ETF-Daten erweitern: TER, Fondsvolumen, Region, Sektor, Diversifikation, langfristige Performance. Status: erweitert am 2026-07-01; strukturierter ETF-Snapshot, YTD/1J/3J/5J, Beta und transparente Detailausgabe eingebaut.
- Bewertungsmodelle ausbauen: historische Bewertung, relative Bewertung und Peer-Vergleich, falls Daten verfügbar sind. Status: erweitert am 2026-07-31; zusätzliche Multiples, Forward-KGV-Abstand, Sektor-/Branchenkontext und klare Nichtverfügbarkeit für Historien-/Peer-Daten eingebaut.
- Analysten-, Earnings-, Event- und institutionelle Module weiter validieren und auf zusätzliche Datenquellen erweitern. Status: validiert am 2026-07-31; Datenabdeckung und Score-Neutralität je Modul ergänzt, fehlende Daten bleiben `Daten nicht verfügbar`.
- News-Modul verbessern: Quelle, Datum, Relevanz, Sentiment-Qualität. Status: erweitert am 2026-07-31; Yahoo-News werden normalisiert und Quelle, Datum, Relevanz sowie Sentiment-Qualität transparent angezeigt.
- Makro-Modul erweitern: Inflation, Realzinsen, Liquidität, Risikoappetit. Status: erweitert am 2026-07-31; Datenabdeckung, Score-Neutralität, Risikoappetit/Nasdaq, Zinsdruck, Dollar-/Liquiditätsdruck und TIP als Inflations-/Realzinsproxy werden transparent ausgewiesen. Direkte Liquiditätsdaten bleiben ohne Quelle `Daten nicht verfügbar`.
- Geopolitik-Modul prüfen, ohne Daten zu erfinden. Status: umgesetzt am 2026-07-31; nutzt nur verfügbare Yahoo-News-Titel als Hinweisquelle, zeigt Datenabdeckung und Score-Neutralität und kennzeichnet fehlende geopolitische Daten klar.
- Risiko- und Liquiditätsmodul verfeinern. Status: erweitert am 2026-07-31; Datenabdeckung, Score-Neutralität, Asset-Typ-Volatilität, CRV-Einordnung, Volumenqualität und fehlende Spread-/Orderbuchdaten werden transparent angezeigt.

### PRIO A: Marktregime-, Innovations-, Blasen- und Makro-Wirkungsmodul

Ziel: Die App soll nicht nur Daten anzeigen, sondern nachvollziehbar erklären, in welchem Marktumfeld ein Asset analysiert wird und wie Makrofaktoren verschiedene Asset-Klassen beeinflussen. Dieses Modul ist PRIO A, weil es zur Grundfähigkeit der Analyse gehört.

Marktregime-Modul:

- Liquiditätsboom
- Liquiditätsentzug
- Risk-On
- Risk-Off
- Rezessionsangst
- Wachstumsphase
- Defensivphase
- Technologie-Hype
- KI-Hype
- Spekulationsphase

Für jedes erkannte Marktregime anzeigen:

- erkannte Hinweise aus verfügbaren Daten
- Gegenargumente und Unsicherheiten
- betroffene Asset-Klassen
- praktische Bedeutung für Aktien, ETFs, Krypto und Rohstoffe
- Vertrauensgrad der Einordnung

Innovations-Modul:

- echte Innovationsführer erkennen, wenn belastbare Hinweise auf Marktführerschaft, Wachstum, Margen, Produktvorsprung oder strukturelle Nachfrage vorhanden sind
- indirekte Profiteure erkennen, wenn Unternehmen über Infrastruktur, Zulieferung, Plattformen, Energie, Rechenzentren, Halbleiter, Software oder Finanzierung vom Trend profitieren
- reine Hype-Aktien erkennen, wenn Kurs, Medieninteresse oder Story stark sind, aber Fundamentaldaten, Cashflows oder Wettbewerbsvorteile nicht belastbar belegt sind
- fehlende Belege immer als `Daten nicht verfügbar` kennzeichnen

Blasenrisiko-Modul:

- Bewertung
- Medienaufmerksamkeit
- Zuflüsse
- Momentum
- Sentiment

Ausgabe:

- Blasenrisiko 0-10
- kurze Begründung je Teilfaktor
- Datenqualität je Teilfaktor
- Warnhinweis, wenn der Score wegen fehlender Daten nur eingeschränkt belastbar ist

Makro-Wirkungsmodul:

- Zinsen erklären
- Inflation erklären
- Realzinsen erklären
- Dollar erklären
- Liquidität erklären

Auswirkungen erklären auf:

- Aktien
- ETFs
- Krypto
- Rohstoffe

Rohstoff-Modul:

- Öl
- Gas
- Kupfer
- Gold
- Uran

Für Rohstoffe berücksichtigen:

- Angebots- und Nachfragesignale, sofern Daten verfügbar sind
- Konjunkturabhängigkeit
- geopolitische Risiken
- Dollar- und Realzinswirkung
- Inflations- und Liquiditätsumfeld
- asset-spezifische Besonderheiten, z. B. Kupfer als Wachstumsindikator, Gold als Realzins- und Sicherheitsasset, Öl und Gas als Energie- und Geopolitik-Sensitivität, Uran als struktureller Energie- und Angebotsmarkt

Transparenzregeln:

- Keine Daten erfinden.
- Zusammenhänge erklären.
- Korrelationen nicht als sichere Kausalitäten darstellen.
- Makro-Wirkungen als Wahrscheinlichkeiten, Belastungen oder Rückenwind formulieren, nicht als Garantien.
- Bei fehlenden Makro-, Flow-, Sentiment- oder Rohstoffdaten sichtbar `Daten nicht verfügbar` anzeigen.
- Datenquellen, Proxies und Unsicherheiten offenlegen.

### Priorität 4: Krypto-Modul

- Bitcoin-Halving-Zyklus integrieren. Status: Basis umgesetzt am 2026-06-15; erweitert am 2026-08-01 um deterministische Zyklusphase, Zyklusfortschritt, praktische Anlegerbedeutung und klare Unsicherheitsregel.
- Fear & Greed Index prüfen und integrieren, falls zuverlässig verfügbar. Status: geprüft am 2026-07-31; keine belastbare Quelle eingebunden, daher weiterhin `Daten nicht verfügbar`.
- ETF-Flows integrieren, falls eine belastbare Datenquelle verfügbar ist. Status: geprüft am 2026-07-31; keine belastbare Quelle eingebunden, daher weiterhin `Daten nicht verfügbar`.
- On-Chain-Daten integrieren, falls verfügbar. Status: geprüft am 2026-07-31; keine belastbare Quelle eingebunden, daher weiterhin `Daten nicht verfügbar`.
- Krypto-Liquidität und Marktstruktur besser erklären. Status: erweitert am 2026-07-31; Volumenvergleich, Volatilität, 50er/200er-Struktur sowie fehlende Orderbuch-, Spread-, Börsentiefe- und Stablecoin-Liquiditätsdaten werden transparent angezeigt.
- Bei fehlenden Krypto-Daten immer `Daten nicht verfügbar` anzeigen. Status: umgesetzt am 2026-07-31; Krypto-Spezialdaten zeigen Datenabdeckung und Score-Neutralität.

### Priorität 5: Backtesting

- Backtesting-Modul planen. Status: Basis umgesetzt am 2026-07-20.
- Historische Signale speichern. Status: erste In-App-Auswertung historischer Kaufsignal-Buckets umgesetzt am 2026-07-20; lokale Speicherung in `backtest_history.json` umgesetzt am 2026-07-20.
- Trefferquoten berechnen. Status: Basis umgesetzt am 2026-07-20 für Kaufsignal-Buckets über 1, 3, 6 und 12 Monate.
- Renditeanalyse durchführen. Status: Basis umgesetzt am 2026-07-20 über Durchschnittsrendite und Kompaktansicht.
- Drawdown-Analyse ergänzen. Status: Basis umgesetzt am 2026-07-20 als maximaler Drawdown je Backtest-Gruppe.
- Verschiedene Signal-Kombinationen vergleichen. Status: Basis umgesetzt am 2026-07-20 für Kaufsignal, RSI, MACD und CRV.
- Backtesting-Tabelle verdichten und interpretieren. Status: umgesetzt am 2026-07-20 mit Kompaktansicht für beste Trefferquote, schwächste Rendite, größten Drawdown und größte Datenbasis.
- Backtesting-Ausgabe gegen Lern-/Confidence-Kontext prüfen. Status: umgesetzt am 2026-08-01; Backtest-Gruppen zeigen jetzt Historienstatus und Lernhinweis nach Mindestdatenregeln, gespeicherte Backtests zeigen zusätzlich einen Confidence-Kontext.

### Priorität 6: Prognose-Tracking

- Prognosen speichern. Status: umgesetzt am 2026-06-15; neue Prognosen speichern zusätzlich Modul-Scores seit 2026-07-31.
- Szenarien und Kursziele später mit echten Ergebnissen vergleichen. Status: umgesetzt am 2026-07-20 für 1 Woche, 1 Monat, 3 Monate, 6 Monate und 12 Monate.
- Trefferquote je Asset und Modul ausweisen. Status: erweitert am 2026-07-31; Prognose-Tracking zeigt Asset-Typ- und Modul-/Signalgruppen aus ausgewerteten Prognosen, mit Mindestdatenlogik.
- Szenario-Lesart und Fehlursachen ausweisen. Status: erweitert am 2026-08-01; Prognoseauswertungen speichern `scenario_read` und `miss_reason`, Trefferquoten gruppieren zusätzlich nach Szenario-Lesart und Fehlursache.
- Grundlage für ein späteres Lernsystem vorbereiten. Status: umgesetzt; Prognosen fließen in Confidence, Signalanalyse, Segmentanalyse, Fehlmuster und Kalibrierungsvorschläge ein.

### PRIO B: Forward-Testing-Modul

- Jede neue Analyse optional als Forward-Test speichern.
  - Status: Basis umgesetzt am 2026-06-15 (`forward_tests.json`, lokal und nicht versioniert).
- Startzeitpunkt, Asset, Ticker, Asset-Typ, Marktphase, Kaufsignal, Asset-Qualität, Depot-Effekt, Vertrauensscore und relevante Modul-Scores erfassen.
  - Status: konsolidiert am 2026-08-01; neue Forward-Tests speichern Modul-Scores, Signal-Snapshot, Szenarien, Kaufzonen und Review-Plan.
- Bull/Base/Bear-Szenarien, Kursziele, Wahrscheinlichkeiten und entscheidende Marken speichern.
  - Status: konsolidiert am 2026-08-01; gespeicherte Szenarien bleiben im Forward-Test-Datensatz erhalten.
- Nach festgelegten Zeiträumen prüfen: 1 Woche, 1 Monat, 3 Monate, 6 Monate und 12 Monate.
  - Status: Basis umgesetzt am 2026-06-15 für 1 Woche, 1 Monat und 3 Monate.
  - Status: Erweiterte Zeiträume umgesetzt am 2026-07-20 für 6 Monate und 12 Monate; alte Historien bleiben kompatibel.
- Tatsächliche Kursentwicklung, maximalen Drawdown, maximale positive Bewegung und Treffer der Szenarien auswerten.
  - Status: erweitert am 2026-08-01; Forward-Test-Auswertungen speichern Rendite, maximale positive/negative Bewegung und Szenario-Lesart.
- Keine Performance-Werte erfinden, wenn Kursdaten fehlen.
- Ergebnisse getrennt nach Asset-Typ, Marktphase und Signalart ausweisen.
  - Status: erweitert am 2026-08-01; Signalanalyse zählt Forward-Test-Ergebnisse zusätzlich nach Asset-Typ, Szenario-Lesart und Modulgruppen.

### PRIO B: Decision-Tracking-Modul

- Nutzerentscheidungen optional protokollieren: gekauft, nicht gekauft, gehalten, verkauft, beobachtet.
  - Status: Basis umgesetzt am 2026-06-15 (`decision_history.json`, lokal und nicht versioniert).
- Zeitpunkt, Entscheidungsgrund, angezeigte Empfehlung und relevante Scores speichern.
  - Status: konsolidiert am 2026-08-01; Decision-Tracking speichert App-Aktion, Professional-Decision-Kontext, Asset-Qualität, Kaufsignal, Confidence, Marktphase, Signal-Snapshot und Modul-Scores.
- Optionalen Nutzerkommentar ermöglichen.
  - Status: umgesetzt; `user_note` bleibt im lokalen Decision-Datensatz erhalten.
- Später vergleichen, ob die Entscheidung gegen oder mit der App-Einschätzung getroffen wurde.
  - Status: erweitert am 2026-08-01; Auswertungen speichern Entscheidungsexposure, App-Exposure und Alignment `mit/gegen App-Einschätzung`.
- Keine Broker-Anbindung und keine automatische Ausführung.
- Daten lokal und transparent speichern.

### PRIO B: Prognose-Tracking-Modul

- Prognosen aus Bull/Base/Bear-Szenarien dauerhaft speichern.
  - Status: Basis umgesetzt am 2026-06-15 (`prediction_history.json`, lokal und nicht versioniert).
- Kursziele, Wahrscheinlichkeiten, Zeithorizont und entscheidende Widerlegungsmarken erfassen.
- Später prüfen, welches Szenario am besten getroffen hat.
  - Status: Basis umgesetzt am 2026-06-15 für 1 Woche, 1 Monat und 3 Monate.
  - Status: Erweiterte Zeiträume umgesetzt am 2026-07-20 für 6 Monate und 12 Monate; alte Prognosehistorien werden beim Auswerten ergänzt.
- Trefferquote je Modul, Signalart, Asset-Typ und Marktphase berechnen.
- Fehlprognosen sichtbar machen und Ursachen kategorisieren.
  - Status: Basis umgesetzt am 2026-07-20: verfehlte Historienfälle werden nach Asset-Typ, Marktphase, Kaufsignal, RSI, MACD, Volatilität, CRV, News und Makro gruppiert.
  - Status: erweitert am 2026-08-01; einzelne Prognose-Reviews speichern eine einfache Fehlursache aus Marktphase, Signal-Snapshot, Modul-Scores oder Kursentwicklung.
- Nur echte nachträgliche Kursdaten verwenden; fehlende Daten als `Daten nicht verfügbar` kennzeichnen.

### PRIO B: Kalibrierungs- und Lernmodul

- Aus Forward-Testing, Decision-Tracking und Prognose-Tracking lernen, welche Signale zuverlässig sind.
- Score-Gewichtungen nicht automatisch ändern, sondern Anpassungsvorschläge erzeugen.
- Häufige Fehlerquellen erkennen, z. B. schwache Marktphasen-Erkennung, schlechte Krypto-Bewertung, unbrauchbare News-Signale oder übergewichtete technische Signale.
- Kalibrierungsbericht anzeigen: Was funktioniert gut? Was funktioniert schlecht? Welche Module brauchen Verbesserung?
  - Status: Basis umgesetzt am 2026-06-15: lokaler Kalibrierungsstatus zählt Forward-Tests, Entscheidungen, Prognosen und ausgewertete Zeiträume.
  - Status: Signalbasierte Kalibrierung umgesetzt am 2026-07-19: ähnliche Setups werden nach RSI, MACD, Marktphase, Volatilität, News, Makro und CRV aufgeschlüsselt; Hinweise bleiben ab Mindestfallzahlen transparent und verändern keine Gewichtungen automatisch.
  - Status: Backtest-Historie integriert am 2026-07-20: gespeicherte Backtest-Gruppen werden als separater Lernkontext mit Fallzahl, Trefferquote, Rendite und Drawdown angezeigt.
  - Status: Kalibrierungsvorschläge aus Fehlmustern umgesetzt am 2026-07-31: häufige Fehlmuster erzeugen manuelle Prüfhinweise mit Datenbasis, Fehlquote und Begründung; Gewichtungen werden nicht automatisch geändert.
  - Status: konsolidiert am 2026-08-01; Lern- und Kalibrierungsansichten nutzen zusätzlich Szenario-Lesart, Fehlursache und Decision-Alignment aus den neuen Review-Feldern.
- Lernlogik transparent machen und keine Blackbox-Entscheidungen treffen. Status: konsolidiert am 2026-07-31; `Lernlogik-Guardrails` zeigen dokumentierte Fälle, ausgewertete Fälle, Mindestdatenlogik und das Verbot automatischer Gewichtungsänderungen.
- Änderungen an Bewertungslogik erst nach Dokumentation und Tests übernehmen.

### PRIO B: Opportunity Scanner

Ziel: Die App soll langfristig nicht nur einzelne Assets analysieren, sondern regelmäßig verfügbare Aktien, ETFs und Kryptowährungen durchsuchen und die attraktivsten Chancen identifizieren.
Status: erweitert am 2026-08-01; Scanner-Ergebnisse zeigen zusätzlich ähnliche historische Setups, Trefferquote ähnlicher Setups und Historienstatus als Transparenzfeld ohne automatische Score-Änderung.

Der Scanner bewertet:

- Trend
- Momentum
- Marktphase
- Risiko
- Volatilität
- News
- Makro
- Liquidität
- Bewertung
- institutionelle Faktoren, falls verfügbar

Ausgabe:

- Top Long Chancen
- Top Short Chancen

Für jedes Asset anzeigen:

- Asset
- Richtung: Long oder Short
- Opportunity Score
- Vertrauensscore
- Zeithorizont
- wichtigste Begründungen

Regeln:

- Der Scanner macht nur Vorschläge.
- Keine automatische Kauf- oder Verkaufsfunktion.
- Keine Broker-Anbindung.
- Fehlende Daten werden als `Daten nicht verfügbar` gekennzeichnet.
- Status: Basis umgesetzt am 2026-06-15. Eine Sidebar-Watchlist scannt bis zu 20 Yahoo-Finance-Ticker mit vorhandener Analyse-, Kaufsignal-, Asset-Qualitäts-, CRV- und Vertrauenslogik und zeigt Long-, Short-/Absicherungs- sowie Beobachtungskandidaten tabellarisch.
- Status: Faktorabdeckung erweitert am 2026-07-31. Scanner-Ausgabe zeigt News, Makro, Liquidität, Bewertung und institutionelle Faktoren als verfügbare Scores/Proxies oder klar `Daten nicht verfügbar`.

### PRIO B: Trading-Modus

Der Trading-Modus analysiert ausschließlich Kandidaten, die vom Opportunity Scanner ausgewählt wurden. Er soll keine beliebigen Assets handeln oder automatisch ausführen.

Für jedes Setup erzeugen:

- Long oder Short
- Chance in %
- Confidence Score
- Zielzone
- Stop-Zone
- Zeithorizont
- CRV
- wichtigste Risiken
- wichtigste Chancen

Beispielausgabe:

- Asset: Bitcoin
- Richtung: Long
- Chance: 72 %
- Confidence: 8/10
- Zeithorizont: 2-6 Wochen
- CRV: 3,1
- Status: Basis umgesetzt am 2026-06-15. Aus Scanner-Kandidaten werden Trading-Setups mit Richtung, Chance, Confidence, Zielzone, Stop-Zone, Zeithorizont, CRV, Risiken und Chancen erzeugt. Speichern ins lokale Trade Journal ist optional und löst keine Order aus.
- Status: konsolidiert am 2026-08-01. Trading-Setups speichern und zeigen zusätzlich ähnliche Setups, Treffer ähnlicher Setups, Trefferquote, Historienstatus und Historienhinweis; Yahoo-Stammdaten werden für Asset-Qualität wiederverwendet.

### PRIO B: Trade Journal

Jeder vorgeschlagene Trade wird automatisch dokumentiert, aber niemals automatisch ausgeführt.
Status: umgesetzt am 2026-07-31. Trading-Setups aus dem Scanner werden automatisch lokal in `trade_history.json` dokumentiert und nach Ticker, Richtung und Tag dedupliziert. Es gibt keine Orderfunktion und keine Broker-Anbindung.
Status: konsolidiert am 2026-08-01. Neue und ältere Trade-Journal-Feldnamen werden beim Speichern defensiv normalisiert, inklusive Review-Plan, Einstieg, Ziel, Stop, Historienstatus und ähnlichen Setups.

Datei:

- `trade_history.json`

Speichern:

- Datum
- Asset
- Richtung
- Einstiegskurs
- Ziel
- Stop
- Chance
- Confidence
- Asset-Typ
- Marktphase
- verwendete Scores
- Begründung

### PRIO B: Performance Tracking

Für jeden vorgeschlagenen Trade prüfen:

- nach 1 Woche
- nach 1 Monat
- nach 3 Monaten
- nach 6 Monaten
- nach 12 Monaten

Bewerten:

- Treffer oder Fehlschlag
- maximale positive Entwicklung
- maximale negative Entwicklung
- Ziel erreicht?
- Stop erreicht?
- beste Alternative?
- Status: Basis umgesetzt am 2026-06-15. Gespeicherte Trading-Setups werden nach 1 Woche, 1 Monat und 3 Monaten mit echten Kursdaten ausgewertet; Ziel/Stop, Rendite sowie maximale positive und negative Entwicklung werden gespeichert.
- Status: Erweiterte Zeiträume umgesetzt am 2026-07-20. Trade-Journal, Forward-Tests, Prognosen und Entscheidungen unterstützen 6- und 12-Monats-Reviews kompatibel zu alten Historien.
- Status: Beste Alternative umgesetzt am 2026-08-01. Trade-Journal-Auswertungen speichern zusätzlich gewählte Aktion, beste Alternative und Opportunitätskosten.
- Status: Historienkontext umgesetzt am 2026-08-01. Trade-Journal-Auswertungen normalisieren ältere Setup-Felder vor der Auswertung und speichern ähnliche Setups, Treffer, Trefferquote, Historienstatus und Historienhinweis im Review-Ergebnis.

### PRIO B: Erweitertes Decision Tracking

Nicht nur prüfen: `Hatte der Bot recht?`

Sondern zusätzlich prüfen: `War dies die beste Entscheidung?`

Vergleichen:

- Long
- Short
- Halten
- Beobachten

Berechnen:

- Rendite der Empfehlung
- Rendite der besten Alternative
- Opportunitätskosten
- Status: Basis umgesetzt am 2026-06-15. Gespeicherte Nutzerentscheidungen werden gegen Long, Short und Halten/Beobachten ausgewertet; beste Alternative und Opportunitätskosten werden gespeichert.

### PRIO B: Confidence-System

Status: ähnliche historische Setups und Trefferquoten aus `trade_history.json`, `forward_tests.json` und `prediction_history.json` umgesetzt am 2026-07-01. Unter 20 ähnlichen Fällen zeigt die App `Datenbasis zu klein`; Gewichtungen werden nicht automatisch geändert.

Status: konsolidiert am 2026-08-01; ähnliche Setup-Auswertungen zeigen zusätzlich häufigste Szenario-Lesart, Fehlursache, Decision-Alignment und Historienstatus aus Review-Daten, sofern vorhanden. Diese Felder dienen nur als Transparenzkontext und verändern keine Scores automatisch.

Zusätzlich zur Chance immer einen Confidence Score anzeigen.

Beispiel:

- Chance: 72 %
- Confidence: 9/10
- Ähnliche Setups: 183
- Historische Trefferquote: 71 %

Der Confidence Score soll berücksichtigen:

- Datenqualität
- Anzahl ähnlicher historischer Fälle
- Trefferquote ähnlicher Setups
- Stabilität der Signale
- Klarheit der Marktphase
- Liquidität und Volatilität
- Status: Basis umgesetzt am 2026-06-15. Die App zählt ähnliche lokale Historienfälle nach Asset-Typ oder Marktphase und zeigt Trefferquote erst ab ausreichender Datenbasis.

### PRIO B: Signalanalyse

Auswerten, welche Signale historisch nützlich waren:

- RSI
- MACD
- Marktphase
- Volatilität
- Trend
- News
- Makro
- Asset-Typ
- CRV
- Opportunity Score
- Confidence Score
  - Status: Basis umgesetzt am 2026-06-15: Signalanalyse zählt ausgewertete Forward-Tests und Prognosen und zeigt Trefferquoten nach Asset-Typ erst ab ausreichender Datenbasis.
  - Status: Signal-Snapshots umgesetzt am 2026-07-19: neue Historieneinträge speichern RSI-, MACD-, Volatilitäts-, News-, Makro- und CRV-Buckets; fehlende alte Signalwerte bleiben `Daten nicht verfügbar`.
  - Status: Segment-Auswertung umgesetzt am 2026-07-19: Trefferquote, Durchschnittsrendite und Fallzahl werden nach Asset-Typ, Marktphase und Zeithorizont gruppiert; unter 20 Fällen bleibt die Aussage `Datenbasis zu klein`.

### PRIO B: Kalibrierungsvorschläge

Der Bot darf Vorschläge machen, aber Gewichtungen in Version 1 nicht automatisch ändern.

- Backtest-Historie in Kalibrierungsvorschläge einbeziehen. Status: umgesetzt am 2026-08-01; schwache gespeicherte Backtest-Gruppen mit ausreichender Datenbasis werden als `Backtest-Signal` in manuellen Kalibrierungshinweisen angezeigt.

Beispiele:

- RSI bei Krypto stärker gewichten
- Marktphase stärker gewichten
- News schwächer gewichten

Für jeden Vorschlag anzeigen:

- Datenbasis
- Anzahl Fälle
- Trefferquote
- Begründung

Mindestdatenmenge:

- Unter 20 Fällen: `Datenbasis zu klein`
- 20-50 Fälle: vorsichtige Hinweise
- Über 50 Fälle: Kalibrierungsvorschläge erlaubt
  - Status: Basis umgesetzt am 2026-07-19: ähnliche Setups zeigen Signal-Buckets, Fallzahl, Trefferquote, Durchschnittsrendite und ob nur gezählt, vorsichtig hingewiesen oder ein manueller Vorschlag erlaubt ist.

Langfristig soll der Bot erkennen:

- welche Signale funktionieren
- welche Signale nicht funktionieren
- bei welchen Asset-Typen er besonders gut ist
- bei welchen Asset-Typen er schwächer ist
- wann er zu optimistisch ist
- wann er zu vorsichtig ist

Ziel ist nicht eine Blackbox-KI. Ziel ist ein transparentes, nachvollziehbares System, das seine eigene historische Leistung misst und daraus begründete Verbesserungen ableitet.

## Prioritäten

Aktuelle höchste offene Priorität:

1. Lokale Historienqualität in CI-/GitHub-Check vorbereiten.

Warum diese Aufgabe zuerst:

- `scripts/smoke_test.py` zeigt jetzt lokale Historienqualität im Smoke-Test an.
- Der nächste größte Nutzen liegt darin, diesen Check CI-tauglich zu machen oder für GitHub Actions vorzubereiten, ohne private Laufzeitdateien zu benötigen.
- Dadurch kann das Repository später automatisch prüfen, dass die App startet und Historienlogik auch ohne lokale Nutzerdaten stabil bleibt.

Nächste konkrete Umsetzung:

1. Bestehende Confidence- und ähnliche-Setup-Auswertungen gegen neue Review-Felder prüfen.
2. Fehlende Gruppierungen oder Hinweise zu Historienstatus, Decision-Alignment und Fehlursachen ergänzen, falls sinnvoll.
3. Keine automatische Kauf-/Verkaufsfunktion einbauen.
4. Tests ausführen und README/ROADMAP aktualisieren.

## Akzeptanzkriterien

Allgemeine Akzeptanzkriterien:

- Die App startet lokal ohne Python-Syntaxfehler.
- Streamlit kann die App laden.
- Keine automatische Kauf- oder Verkaufsfunktion wird eingebaut.
- Keine Broker-Anbindung wird eingebaut.
- Fehlende Daten werden nicht geschätzt oder erfunden.
- Bei fehlenden Daten wird sichtbar `Daten nicht verfügbar` oder ein klarer Hinweis angezeigt.
- Asset-Qualität, Kaufsignal und Depot-Effekt bleiben getrennt.
- Portfolio-Daten beeinflussen niemals Asset-Qualität oder Kaufsignal.
- README wird aktualisiert, wenn sich Bedienung, Struktur oder wichtige Funktionen ändern.
- ROADMAP wird nach jeder Arbeitseinheit aktualisiert.

Akzeptanzkriterien für Priorität 1:

- Oben im Dashboard gibt es keine widersprüchlichen Empfehlungen.
- Der Nutzer sieht klar:
  - Was ist das Asset?
  - Wie gut ist die Asset-Qualität?
  - Wie stark ist das aktuelle Kaufsignal?
  - Was sagt das Research-Modul?
  - Was sagt der Depot-Effekt, falls Portfolio-Modus aktiv ist?
- Anfänger-Erklärung beschreibt die praktische Bedeutung der Einschätzung.
- Fehler bei Yahoo Finance führen nicht zu App-Abstürzen.
- Suchhistorie ist einfacher nutzbar.

Akzeptanzkriterien für Research-Module:

- Jeder Score zeigt eine kurze Begründung.
- Jeder Score zeigt bei fehlenden Daten ehrlich `Daten nicht verfügbar`.
- Bull/Base/Bear-Wahrscheinlichkeiten ergeben zusammen 100 %.
- Nachkaufzonen zeigen keine erfundenen Marken.
- Wenn keine Marke berechenbar ist, wird `Daten nicht verfügbar` angezeigt.

Akzeptanzkriterien für Marktregime-, Innovations-, Blasen- und Makro-Wirkungsmodule:

- Marktregime werden nur aus vorhandenen Daten, Proxies oder klar gekennzeichneten qualitativen Hinweisen abgeleitet.
- Jede Marktregime-Einordnung nennt Hinweise, Gegenargumente, Unsicherheiten und einen Vertrauensgrad.
- Innovationsführer, indirekte Profiteure und Hype-Aktien werden getrennt ausgewiesen.
- Das Blasenrisiko wird als Score 0-10 angezeigt und nach Bewertung, Medienaufmerksamkeit, Zuflüssen, Momentum und Sentiment begründet.
- Fehlende Bewertungs-, Flow-, Medien- oder Sentimentdaten senken die Belastbarkeit und werden nicht geschätzt.
- Das Makro-Wirkungsmodul erklärt Zinsen, Inflation, Realzinsen, Dollar und Liquidität verständlich.
- Auswirkungen auf Aktien, ETFs, Krypto und Rohstoffe werden getrennt erklärt.
- Öl, Gas, Kupfer, Gold und Uran werden als eigene Rohstoffgruppen berücksichtigt, sofern Daten verfügbar sind.
- Korrelationen werden nicht als sichere Kausalitäten dargestellt.
- Jede Makro-Aussage enthält einen Hinweis auf Unsicherheit, Datenlage oder mögliche Gegenbewegungen.

Akzeptanzkriterien für Portfolio-Modus:

- Portfolio-Modus AUS: keine Depotdaten, keine Klumpenrisiko-Warnung, keine Cash-Bewertung.
- Portfolio-Modus AN: Depot-Effekt wird zusätzlich angezeigt.
- Depot-Effekt verändert Asset-Qualität und Kaufsignal nicht.

Akzeptanzkriterien für Forward-Testing, Decision-Tracking und Prognose-Tracking:

- Tracking ist optional und transparent.
- Keine Broker-Anbindung und keine automatische Kauf- oder Verkaufsfunktion.
- Gespeichert werden nur Analysezeitpunkt, Scores, Szenarien, Wahrscheinlichkeiten, Marken, Nutzerentscheidung und spätere echte Ergebnisdaten.
- Trefferquoten werden nur aus vorhandenen echten Daten berechnet.
- Fehlende Ergebnisdaten werden als `Daten nicht verfügbar` angezeigt.
- Ergebnisse sind nach Asset-Typ, Marktphase, Signalart und Modul auswertbar.

Akzeptanzkriterien für Kalibrierungs- und Lernmodul:

- Das Modul zeigt Verbesserungsvorschläge, ändert Score-Gewichtungen aber nicht heimlich automatisch.
- Jede vorgeschlagene Gewichtungs- oder Logikänderung nennt Auslöser, Datenbasis und erwartete Wirkung.
- Häufige Fehlprognosen erhöhen nachvollziehbar die Priorität des betroffenen Moduls.
- Prioritätsänderungen werden mit ursprünglicher Priorität, neuer Priorität und Begründung im Änderungsprotokoll dokumentiert.

Akzeptanzkriterien für Opportunity Scanner und Trading-Modus:

- Der Scanner durchsucht nur definierte, nachvollziehbare Asset-Universen.
- Top Long und Top Short Chancen zeigen Opportunity Score, Vertrauensscore, Zeithorizont und Begründungen.
- Trading-Setups entstehen nur aus Scanner-Kandidaten.
- Jedes Setup zeigt Richtung, Chance, Confidence, Zielzone, Stop-Zone, Zeithorizont, CRV, Risiken und Chancen.
- Kein Setup löst automatisch Kauf, Verkauf, Short oder Order aus.
- Bei fehlenden News-, Makro-, Bewertungs- oder institutionellen Daten wird `Daten nicht verfügbar` angezeigt.

Akzeptanzkriterien für Trade Journal und Performance Tracking:

- Vorgeschlagene Trades werden in `trade_history.json` gespeichert.
- Gespeichert werden nur Analyse- und Setupdaten, keine Broker-Zugangsdaten.
- Performance wird nach 1 Woche, 1 Monat und 3 Monaten geprüft, später optional nach 6 und 12 Monaten.
- Treffer, Fehlschlag, Ziel erreicht, Stop erreicht, maximale positive und negative Entwicklung werden aus echten Kursdaten berechnet.
- Fehlende Kursdaten erzeugen keinen geschätzten Treffer, sondern einen klaren Datenhinweis.

Akzeptanzkriterien für Confidence-System, Signalanalyse und Lernsystem:

- Jede Chance wird zusammen mit einem Confidence Score angezeigt.
- Wenn historische Daten vorhanden sind, zeigt die App Anzahl ähnlicher Setups und Trefferquote ähnlicher Setups.
- Unter 20 Fällen erscheint `Datenbasis zu klein`.
- Zwischen 20 und 50 Fällen werden nur vorsichtige Hinweise angezeigt.
- Über 50 Fällen sind Kalibrierungsvorschläge erlaubt.
- Kalibrierungsvorschläge nennen Datenbasis, Anzahl Fälle, Trefferquote und Begründung.
- Das Lernsystem analysiert, ändert aber in Version 1 keine Gewichtungen automatisch.

## Arbeitsmodus

Wenn der Nutzer später schreibt:

- `Arbeite weiter`
- `Weiter`
- `Setze die Entwicklung fort`
- `Arbeite bis zum Limit`

dann soll automatisch folgender Arbeitsmodus gelten:

1. `ROADMAP.md` lesen.
2. Alle offenen Aufgaben anhand der dynamischen Priorisierung bewerten.
3. Nutzen für Analysequalität, Stabilität und Lernfähigkeit einschätzen.
4. Die höchste tatsächliche Priorität auswählen, nicht automatisch die erste Aufgabe der Liste.
5. Die ausgewählte Aufgabe implementieren.
6. Die App testen.
7. Fehler beheben.
8. `README.md` aktualisieren, wenn sich Bedienung, Funktionen oder Struktur ändern.
9. `ROADMAP.md` aktualisieren.
10. Prioritätsänderungen im Änderungsprotokoll dokumentieren.
11. `git status` prüfen und geänderte Dateien identifizieren.
12. Einen Commit mit automatisch erzeugter, kurzer Commit-Nachricht erstellen.
13. `git push` ausführen.
14. Wenn Push fehlschlägt: Fehler dokumentieren, Nutzer informieren und Änderungen lokal behalten.
15. Danach die nächste offene Aufgabe bearbeiten.
16. Wiederholen, bis keine offene Aufgabe mehr sinnvoll bearbeitbar ist oder kein Arbeitsbudget mehr vorhanden ist.

Während dieses Arbeitsmodus gilt:

- Bestehende App nicht unnötig neu bauen.
- Keine vorhandenen Funktionen entfernen.
- Änderungen klein, nachvollziehbar und testbar halten.
- Keine automatische Kauf- oder Verkaufsfunktion einbauen.
- Keine Broker-Anbindung einbauen.
- Keine Daten erfinden.
- Bei fehlenden Daten ehrlich bleiben.
- Portfolio-Daten nur im Depot-Effekt verwenden.
- Wenn für eine offene Aufgabe kein genauer Implementierungs-Prompt vorhanden ist, wird die Aufgabe selbstständig analysiert, ein Umsetzungsplan erstellt, die Lösung implementiert, getestet und dokumentiert.
- Wenn eine spätere Aufgabe durch eine frühere Architekturänderung besser, sauberer oder risikoärmer umgesetzt werden kann, darf die ROADMAP-Reihenfolge angepasst werden.
- Änderungen an der ROADMAP-Reihenfolge müssen im Änderungsprotokoll dokumentiert werden.
- Ziel ist nicht starres Abarbeiten, sondern die beste technische Lösung für die bestehende App.

Langzeit-Ziel des Arbeitsmodus:

- Der Nutzer soll langfristig meist nur noch `Arbeite weiter` schreiben müssen.
- Danach werden Planung, Umsetzung, Tests, Dokumentation, Commit und Push autonom ausgeführt, soweit technisch möglich.

## Dynamische Priorisierung

Die bisherigen numerischen Prioritäten sind nur eine Ausgangsbasis. Der Arbeitsmodus soll nicht automatisch die erste Aufgabe der Liste wählen, sondern die tatsächliche Wirkung auf die Analysequalität, Stabilität und Lernfähigkeit bewerten.

### PRIO A: Grundfähigkeit der Analyse

Immer höchste Priorität:

- Datenqualität
- Fehlerbehandlung
- Stabilität
- Asset-Erkennung
- Bewertungslogik
- Marktphasen-Erkennung
- Wahrscheinlichkeiten
- Vertrauensscore
- Fundamentaldaten
- Krypto-Analyse
- Makro
- Marktregime
- Makro-Wirkungsanalyse
- Innovationsanalyse
- Blasenrisiko
- Rohstoffe
- News
- Geopolitik
- Risikoanalyse

Diese Aufgaben dürfen immer vorgezogen werden, wenn sie die Analyse belastbarer, ehrlicher oder stabiler machen.

### PRIO B: Messung der Analysequalität

- Forward-Testing
- Decision-Tracking
- Prognose-Tracking
- Opportunity Scanner
- Trading-Modus
- Trade Journal
- Performance Tracking
- Confidence-System
- Signalanalyse
- Trefferquote
- Kalibrierung
- Lernmodul

Diese Aufgaben dürfen vorgezogen werden, wenn sie die Analysequalität messbar verbessern oder sichtbar machen, welche Module falsche Signale liefern. Wenn genügend historische Daten vorhanden sind, dürfen Lernsystem und Kalibrierung vor neuen Komfortfunktionen bearbeitet werden.

### PRIO C: Architektur und Wartbarkeit

- Refactoring
- Modularisierung
- Performance
- Dokumentation
- Testbarkeit

Diese Aufgaben dürfen vorgezogen werden, wenn sie mehrere spätere Aufgaben erleichtern, Risiken senken oder Tests zuverlässiger machen.

### PRIO D: Komfortfunktionen

Niedrigste Priorität:

- Suchkomfort
- Favoriten
- Watchlists
- Exporte
- UI-Verschönerungen
- sonstige Komfortfunktionen

Diese Aufgaben dürfen niemals vor Analysequalität bearbeitet werden.

### Selbstständige Prioritätsentscheidung

Wenn der Nutzer `Arbeite weiter`, `Weiter`, `Setze die Entwicklung fort` oder `Arbeite bis zum Limit` schreibt:

1. `ROADMAP.md` lesen.
2. Alle offenen Aufgaben analysieren.
3. Geschätzten Nutzen für die Analysequalität bewerten.
4. Geschätzten Nutzen für Stabilität bewerten.
5. Geschätzten Nutzen für Lernfähigkeit bewerten.
6. Daraus eine aktuelle Priorität ableiten.
7. Die höchste tatsächliche Priorität bearbeiten.

Nicht automatisch die erste Aufgabe der Liste wählen.

### Lernmodul und Prioritäten

Wenn Forward-Testing oder Prognose-Tracking zeigt, dass bestimmte Signalarten schlecht funktionieren, bestimmte Module wenig Nutzen liefern oder bestimmte Fehler häufig auftreten, dürfen passende Verbesserungen höher priorisiert werden.

Beispiele:

- Häufige Fehlprognosen durch schlechte Marktphasen-Erkennung -> Marktphasen-Modul priorisieren.
- Häufige Fehlprognosen durch schlechte Krypto-Bewertung -> Krypto-Modul priorisieren.
- Häufig falsche News-Impulse -> News-Modul und Sentiment-Qualität priorisieren.
- Niedriger Vertrauensscore wegen Datenlücken -> Datenqualität und Fehlerbehandlung priorisieren.

### Keine Blackbox

Wenn Prioritäten angepasst werden, muss im Änderungsprotokoll dokumentiert werden:

- ursprüngliche Priorität
- neue Priorität
- Begründung

Damit jederzeit nachvollziehbar bleibt, warum eine Aufgabe vorgezogen wurde.

Ziel ist nicht, möglichst viele Features zu bauen. Ziel ist, die tatsächliche Qualität der Investment-Analysen langfristig zu maximieren. Die Verbesserung der Grundfähigkeit des Bots hat immer Vorrang vor Komfortfunktionen.

Wenn eine Aufgabe unklar ist:

1. `ROADMAP.md` analysieren.
2. Teilaufgaben erzeugen.
3. Teilaufgaben priorisieren.
4. Schrittweise umsetzen.
5. Nicht auf weitere Anweisungen warten, sofern keine riskante Produktentscheidung nötig ist.

## GitHub-Synchronisation

Nach jeder erfolgreichen Arbeitseinheit:

1. `git status` prüfen.
2. Geänderte Dateien identifizieren.
3. Nur sinnvolle Projektänderungen committen.
4. Commit-Nachricht automatisch erzeugen.
5. `git push` ausführen.

Beispiel:

```powershell
git add .
git commit -m "Improve dashboard recommendation logic"
git push
```

Wenn `git push` fehlschlägt:

- Fehler im Abschlussbericht dokumentieren.
- Nutzer informieren.
- Änderungen lokal behalten.
- Keine funktionierenden lokalen Änderungen verwerfen.

Vor dem Commit prüfen:

- Keine geheimen Schlüssel oder Zugangsdaten committen.
- `portfolio.json` darf nur im erlaubten Minimalformat committed werden: Cash, Ticker, Asset-Typ, Positionsgröße und Kaufkurs.
- Keine Kontonummern, Depotnummern, Broker-Zugangsdaten, API-Keys, Passwörter, Namen, Adressen oder persönlichen Identifikationsdaten committen.
- Keine Suchhistorien-Daten committen.
- Keine bewusst kaputten Zwischenstände committen.
- Keine automatisch generierten Dateien committen, wenn sie nicht sinnvoll zum Projekt gehören.

## Rollback-System

Vor größeren Änderungen:

1. `git status` prüfen.
2. Wenn der aktuelle Stand stabil ist, einen Sicherheits-Commit erstellen.
3. Danach erst größere Refactorings oder Modulumbauten beginnen.

Beispiel:

```powershell
git add .
git commit -m "Checkpoint before macro module refactor"
```

Bei schwerem Fehler:

- Ursache dokumentieren.
- Wenn möglich, den Fehler vorwärts beheben.
- Nur wenn der Stand nicht sinnvoll reparierbar ist, auf den letzten funktionierenden Stand zurückgehen.
- Nie absichtlich funktionierenden Code zerstören.
- Nie fremde oder nutzerseitige Änderungen verwerfen, ohne dass der Nutzer es ausdrücklich verlangt.

## Autonome Architekturpflege

Wenn während der Arbeit sichtbar wird, dass eine kleine strukturelle Vorarbeit mehrere spätere Aufgaben sicherer oder einfacher macht, darf diese Vorarbeit vorgezogen werden.

Erlaubt sind:

- kleine Extraktionen von Hilfsfunktionen,
- bessere Trennung von UI, Datenbeschaffung und Bewertung,
- klarere Datenstrukturen für Research-Module,
- robustere Fehlerbehandlung,
- bessere Dokumentation,
- Aufräumen doppelter oder widersprüchlicher Anzeige-Logik.

Nicht erlaubt sind:

- vollständiger Neubau der App ohne ausdrückliche Anweisung,
- Entfernen vorhandener Funktionen ohne Ersatz,
- automatische Kauf- oder Verkaufsfunktionen,
- Broker-Anbindung,
- erfundene Daten oder versteckte Annahmen.

## Wachsende ROADMAP

Wenn während der Entwicklung neue sinnvolle Aufgaben entdeckt werden, dürfen und sollen sie in die ROADMAP aufgenommen werden.

Für jede neu entdeckte Aufgabe dokumentieren:

- kurze Beschreibung
- vermuteter Nutzen
- Zuordnung zu PRIO A, PRIO B, PRIO C oder PRIO D
- Begründung der Priorität
- mögliche Abhängigkeiten zu bestehenden Aufgaben

Neue Aufgaben dürfen die ROADMAP erweitern. Sie dürfen aber nicht automatisch Komfortfunktionen vor Analysequalität schieben. Wenn eine neu entdeckte Aufgabe wichtiger ist als die bisherige Reihenfolge, muss die Prioritätsänderung im Änderungsprotokoll begründet werden.

## Teststrategie

Nach relevanten Änderungen mindestens:

- `python -m py_compile app.py`
- Streamlit-Starttest, wenn möglich
- Analyse-Test mit `BTC-EUR`
- Analyse-Test mit `NVDA`
- Analyse-Test mit `Xiaomi`

Wenn externe Daten wegen Netzwerk oder Yahoo Finance nicht verfügbar sind:

- Fehler sauber anzeigen.
- Keine falschen Daten erzeugen.
- ROADMAP oder Abschlussbericht entsprechend notieren.

Wenn ein Test wegen Netzwerk, Yahoo Finance, GitHub-Authentifizierung oder Nutzungslimit nicht möglich ist:

- Test als nicht ausgeführt dokumentieren.
- Grund nennen.
- Keine Testergebnisse behaupten.

## Änderungsprotokoll

### 2026-06-15

- ROADMAP um PRIO-A-Paket für Marktregime-, Innovations-, Blasenrisiko-, Makro-Wirkungs- und Rohstoffanalyse erweitert.
- Neue Analyseziele dokumentiert: Marktregime wie Liquiditätsboom, Liquiditätsentzug, Risk-On, Risk-Off, Rezessionsangst, Wachstumsphase, Defensivphase, Technologie-Hype, KI-Hype und Spekulationsphase sollen nachvollziehbar erklärt werden.
- Innovations-Modul geplant: Trennung zwischen echten Innovationsführern, indirekten Profiteuren und reinen Hype-Aktien.
- Blasenrisiko-Modul geplant: Score 0-10 auf Basis von Bewertung, Medienaufmerksamkeit, Zuflüssen, Momentum und Sentiment, ohne fehlende Daten zu schätzen.
- Makro-Wirkungsmodul geplant: Erklärung von Zinsen, Inflation, Realzinsen, Dollar und Liquidität sowie deren Auswirkungen auf Aktien, ETFs, Krypto und Rohstoffe.
- Rohstoff-Modul geplant: Öl, Gas, Kupfer, Gold und Uran mit Konjunktur-, Dollar-, Realzins-, Liquiditäts- und geopolitischer Sensitivität.
- Prioritätsentscheidung nach dynamischer Logik: PRIO A vorgezogen, weil widersprüchliche Empfehlungen direkt Analysequalität und Verständlichkeit beeinträchtigen.
- Haupt-Dashboard und Research-Modul vereinheitlicht: zentrale Empfehlungsbox zeigt Kaufsignal, Research-Einordnung, Asset-Qualität, Depot-Effekt, Vertrauensscore, Marktphase, CRV und Wahrscheinlichkeiten.
- Separate obere `Research-Handlungsempfehlung` entfernt, damit keine zweite Empfehlung neben der zentralen Entscheidung konkurriert.
- Analyse-Details verbessert: `Konkreter Plan` zeigt jetzt den Research-Plan statt nur den Empfehlungstitel.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Analysepfade mit `BTC-EUR`, `NVDA` und `1810.HK` erfolgreich; Streamlit-Start gab einen lokalen URL-Hinweis, Browser-/HTTP-Sichtprüfung war durch die Sandbox blockiert.
- Yahoo-Finance-Fehlerbehandlung verbessert: eingeschränkte Stammdaten, FX-Umrechnung, News und Makro-Proxies werden oben im Dashboard und im Research-Modul als externe Datenquellen-Warnungen gebündelt.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Warnungsfunktion mit simulierten Ausfällen und Normalfall erfolgreich; Live-Analysepfade mit `BTC-EUR`, `NVDA` und `1810.HK` erfolgreich.
- Datenqualitäts-Check kompakter und sichtbarer gemacht: Dashboard zeigt jetzt eine Datenqualitäts-Ampel mit Score, kurzer Statuszeile, wichtigsten Datenhinweisen und Details im Expander.
- Anfänger-Modus um einfache Datenqualitäts-Erklärung ergänzt.
- Umlaute und sichtbare deutsche Texte geprüft: `app.py` und `README.md` enthalten keine Mojibake-Treffer; ROADMAP-Treffer sind nur absichtlich dokumentierte Beispiele.
- Suchhistorie in der Sidebar als auswählbare Schnellwahl umgesetzt.
- Wiederholbaren Smoke-Test ergänzt: `scripts/smoke_test.py` kompiliert `app.py`, startet Streamlit kurz auf einem freien Port und prüft den Analysefluss mit `BTC-EUR`, `NVDA` und `1810.HK`.
- Smoke-Test erfolgreich ausgeführt: py_compile OK, Streamlit-Start OK, Live-Analysepfade OK.
- Score-Gewichtungen transparent gemacht: Analyse-Details zeigen jetzt Gewichtungen nach Asset-Typ und die separate Kaufsignal-Gewichtung; README dokumentiert die Gewichtungen.
- Kalibrierungsstatus ergänzt: Die App zeigt Anzahl dokumentierter Fälle, Mindestdatenmenge und ob Hinweise oder Kalibrierungsvorschläge erlaubt sind; Gewichtungen werden nicht automatisch geändert.
- `trade_history.json` als lokale, nicht versionierte Datei für spätere Trade-/Prognosehistorie vorbereitet.
- Nächste tatsächliche Priorität gesetzt: Asset-Qualität je Asset-Typ verbessern.
- Asset-Qualität je Asset-Typ verbessert: Aktien bewerten zusätzlich Margen, Kapitalrendite und Kurs-Umsatz-Verhältnis; ETFs bewerten langfristige Stabilität aus berechneter Volatilität; fehlende Daten bleiben sichtbar als `Daten nicht verfügbar`.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; erster Smoke-Test ohne Netzwerk scheiterte erwartbar am Yahoo-Datenabruf für `BTC-EUR`; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Aufgabe ist die weitere Abgrenzung und Präzisierung des Kaufsignals, weil die langfristige Asset-Qualität nun besser getrennt abgebildet ist.
- Kaufsignal weiter von Asset-Qualität abgegrenzt: MACD-Bestätigung, Bodenbildungs-Hinweis und asset-typische Volatilitätsschwellen ergänzt; App zeigt ausdrücklich, dass Asset-Qualität und Depot-Effekt nicht in das Kaufsignal einfließen.
- Smoke-Test aktualisiert und erfolgreich ausgeführt: `score_buy_signal` nutzt jetzt den Asset-Typ; `BTC-EUR`, `NVDA` und `1810.HK` liefen mit Netzwerkfreigabe erfolgreich durch.
- Priorität angepasst: Nächste PRIO-A-Aufgabe ist die stärkere Erklärung der Research-Scores, weil die Score-Bedeutung unmittelbar die Nutzbarkeit der Analyse verbessert.
- Research-Scores stärker erklärt: Modul- und institutionelle Tabellen zeigen jetzt Score-Bänder (`stark`, `konstruktiv`, `gemischt`, `schwach`, `kritisch`, `Daten nicht verfügbar`) plus praktische Bedeutung; Anfänger-Modus nutzt dieselbe Interpretation.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Aufgabe sind robustere Nachkaufzonen, damit fehlende Kurszonen nicht als präzise Kaufmarken missverstanden werden.
- Nachkaufzonen robuster gemacht: faire Kaufzone nutzt nur Unterstützungen unter dem Kurs, Sicherheits-Kaufzone nur Widerstand oder SMA50 oberhalb des Kurses; fehlende Marken erhalten Statushinweise statt erfundener Kursziele.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Aufgabe sind stärkere Bull/Base/Bear-Szenarien aus Trend, Volatilität, Unterstützungen, Widerständen und CRV.
- Bull/Base/Bear-Szenarien verbessert: Wahrscheinlichkeiten berücksichtigen jetzt zusätzlich SMA-Trendstruktur, Abstand zu Unterstützung/Widerstand, Volatilität und CRV; Kursziele bleiben bei fehlenden Marken `Daten nicht verfügbar`.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Aufgabe ist der Einstieg in das Marktregime-, Innovations-, Blasen- und Makro-Wirkungsmodul.
- Erstes Marktregime-Modul umgesetzt: nutzt vorhandene Nasdaq-, US-Zins-, Dollar-, TIP-, Trend- und Volatilitätsdaten; zeigt Hinweise, Gegenargumente, Unsicherheiten, betroffene Asset-Klassen und Vertrauensgrad.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Teilaufgabe ist das Makro-Wirkungsmodul mit getrennten Auswirkungen auf Aktien, ETFs, Krypto und Rohstoffe.
- Makro-Wirkungsmodul ergänzt: erklärt Zinsen, Dollar, Risikoappetit und Inflations-/Realzinsproxy mit praktischer Wirkung auf Aktien, ETFs, Krypto und Rohstoffe; Aussagen bleiben als Wahrscheinlichkeitszusammenhänge gekennzeichnet.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Teilaufgabe ist ein erstes Blasenrisiko-Modul aus verfügbaren Bewertungs-, Momentum-, Sentiment- und Volatilitätsdaten.
- Blasenrisiko-Modul umgesetzt: nutzt vorhandene Bewertungsdaten, RSI, 3M-Kursanstieg, Volatilität und News-Sentiment; Medienaufmerksamkeit und Zuflüsse werden als `Daten nicht verfügbar` gekennzeichnet; hoher Score wird als Warnsignal interpretiert.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Teilaufgabe ist das Innovations-Modul zur Trennung von Innovationsführern, indirekten Profiteuren und Hype-Aktien.
- Innovations-/Hype-Modul umgesetzt: nutzt vorhandene Wachstums-, Margen-, Free-Cashflow-, Marktstellungs-, Beschreibungs- und News-Daten; Produktvorsprung, Patente, Entwickleraktivität und Marktanteile bleiben `Daten nicht verfügbar`, wenn sie nicht vorliegen.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Teilaufgabe ist ein Rohstoff-Kontextmodul mit Öl, Gas, Kupfer, Gold und Uran als Makro-/Rohstoff-Wirkungskategorien.
- Rohstoff-Kontextmodul umgesetzt: nutzt Yahoo-Proxies für Öl, Gas, Kupfer, Gold und Uran/URA, sofern verfügbar; zeigt 3M-Trends, Asset-Typ-Kontext und Unsicherheit statt sichere Kausalitäten zu behaupten.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Teilaufgabe ist die Erweiterung des Krypto-Moduls mit Bitcoin-Halving-Zyklus und transparenter Krypto-Marktstruktur.
- Krypto-Zyklusmodul umgesetzt: bei Krypto-Assets werden Bitcoin-Halving-Zyklus, geschätzte Zyklusphase, Krypto-Volatilität und Volumen/Liquidität angezeigt; ETF-Flows, Fear & Greed und On-Chain-Daten bleiben ohne Quelle `Daten nicht verfügbar`.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste Aufgabe ist PRIO B Forward-Testing, weil Messung der Analysequalität jetzt mehr Nutzen bringt als weitere unbelegte Datenquellen.
- Forward-Test-Basisspeicherung umgesetzt: Nutzer können die aktuell angezeigte Analyse optional lokal in `forward_tests.json` speichern; gespeichert werden Analysezeitpunkt, Symbol, Asset-Typ, Einstiegskurs, Scores, Szenarien, Kaufzonen, Modul-Scores und Review-Felder; keine Orderfunktion.
- `forward_tests.json` in `.gitignore` und README-Datenschutzliste aufgenommen.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist die Auswertung gespeicherter Forward-Tests mit echten Kursdaten.
- Forward-Test-Auswertung umgesetzt: Sidebar kann fällige gespeicherte Analysen nach 1 Woche, 1 Monat und 3 Monaten mit echten Kursdaten auswerten; gespeichert werden aktuelle Rendite, maximale positive Entwicklung und maximale negative Entwicklung.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist Decision Tracking, damit Nutzerentscheidungen später mit App-Einschätzungen verglichen werden können.
- Decision-Tracking-Basis umgesetzt: Nutzer können Kaufen, Nicht kaufen, Halten, Verkaufen oder Beobachten mit optionalem Kommentar lokal in `decision_history.json` speichern; App-Einschätzung und Modul-Scores werden mitgespeichert; keine Orderfunktion.
- `decision_history.json` in `.gitignore` und README-Datenschutzliste aufgenommen.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist Prognose-Tracking für Bull/Base/Bear-Szenarien.
- Prognose-Tracking-Basisspeicherung umgesetzt: Bull/Base/Bear-Szenarien, Wahrscheinlichkeiten, Kursziele, entscheidende Marke und Kaufzonen können lokal in `prediction_history.json` gespeichert werden; keine Orderfunktion.
- `prediction_history.json` in `.gitignore` und README-Datenschutzliste aufgenommen.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist die Prognose-Auswertung mit echten Kursdaten.
- Prognose-Auswertung umgesetzt: Sidebar kann fällige gespeicherte Prognosen nach 1 Woche, 1 Monat und 3 Monaten mit echten Kursdaten auswerten; gespeichert werden Rendite, maximale positive/negative Entwicklung und eine einfache Szenario-Lesart.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist ein Kalibrierungs- und Lernmodul, das lokale Historien zusammenfasst und Datenbasis/Mindestfallzahl transparent macht.
- Kalibrierungs- und Lernstatus erweitert: Analyse-Details zählen jetzt Trade-Historie, Forward-Tests, Nutzerentscheidungen, Prognosen und ausgewertete Zeiträume gemeinsam; Gewichtungen werden weiterhin nicht automatisch geändert.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist eine erste Signalanalyse aus lokalen Historien, sobald ausreichend Fälle vorliegen.
- Signalanalyse-Basis umgesetzt: Analyse-Details zeigen ausgewertete Fälle, positive/negative Ausgänge und ab ausreichender Datenbasis Trefferquoten nach Asset-Typ; Gewichtungen bleiben unverändert.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist ein erster Opportunity Scanner auf Basis der bestehenden Analysefunktionen.
- Opportunity-Scanner-Basis umgesetzt: Sidebar-Watchlist mit Standardwerten `BTC-EUR`, `NVDA`, `PLTR`, `1810.HK` und `EUNL.DE`; Scan nutzt bestehende Kurs-, Asset-Typ-, Kaufsignal-, Asset-Qualitäts-, CRV- und Vertrauenslogik; einzelne Tickerfehler werden abgefangen und fehlende Daten nicht erfunden.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`; Scanner-Direkttest mit `BTC-EUR` und `NVDA` erfolgreich.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist der Trading-Modus auf Basis der Scanner-Kandidaten.
- Streamlit-Community-Cloud-Vorbereitung umgesetzt: `app.py` nutzt keine Windows-Pfade, yfinance-Cache fällt bei Schreibproblemen auf ein temporäres Verzeichnis zurück, `.streamlit/config.toml` ist vorhanden, `portfolio.json` enthält nur GitHub-kompatible Minimaldaten und README erklärt das Cloud-Deployment.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich.
- Trading-Modus-Basis umgesetzt: Aus Opportunity-Scanner-Kandidaten werden Setups mit Richtung, Chance, Confidence, Zielzone, Stop-Zone, CRV, Zeithorizont, Risiken und Chancen erzeugt; Setups können lokal in `trade_history.json` gespeichert werden und lösen keine Order aus.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Trading-Setup-Direkttest mit `NVDA` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist Performance-Tracking für gespeicherte Trade-Journal-Setups.
- Neue PRIO-A-Aufgabe vorgezogen: Analyse-Daten vollständig von Chart-Daten entkoppeln, weil der gewählte Chart-Zeitraum die Analysequalität nicht verschlechtern darf.
- Entkopplung umgesetzt: Einzelanalyse lädt Chart-Daten separat für die Visualisierung und Analyse-Daten separat mit maximal verfügbarer Tageshistorie; Datenqualitätsbereich zeigt Chart-Historie und Analyse-Historie; langfristige und kurzfristige Unterstützungen/Widerstände werden getrennt angezeigt.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; aktualisierter Smoke-Test prüft getrennte Chart- und Analyse-Daten und lief mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Streamlit-Community-Cloud-Check erneut durchgeführt: keine lokalen Windows-Pfade in `app.py`, Requirements vollständig, `portfolio.json` im erlaubten Minimalformat, keine Secrets/Brokerdaten gefunden, `.streamlit/config.toml` vorhanden und README um Mobile-Hinweise erweitert.
- Performance-Tracking für Trade-Journal umgesetzt: Fällige Setups in `trade_history.json` können über die Sidebar mit echten Kursdaten ausgewertet werden; gespeichert werden Rendite, maximale positive/negative Entwicklung, Ziel erreicht, Stop erreicht und Ergebnis.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Trade-History-Auswertung mit gemockten Kursdaten erfolgreich. Live-Test mit Yahoo-Finance-Daten bleibt optional.
- Erweitertes Decision Tracking umgesetzt: Fällige Entscheidungen in `decision_history.json` können über die Sidebar gegen Long, Short und Halten/Beobachten ausgewertet werden; gespeichert werden Entscheidungsrendite, beste Alternative und Opportunitätskosten.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Decision-Tracking-Auswertung mit gemockten Kursdaten erfolgreich.
- Confidence-System erweitert: Im Research-Modul zeigt die App ähnliche lokale Historienfälle nach Asset-Typ oder Marktphase, historische Trefferquote erst ab ausreichender Datenbasis und die Regel, dass keine automatische Gewichtungsänderung erfolgt.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Confidence-Historienauswertung mit gemockten Fällen erfolgreich.

### 2026-08-01

- Historienqualität in Smoke-Test sichtbar gemacht: `scripts/smoke_test.py` ruft jetzt `local_history_quality_rows()` auf und gibt Status sowie eingeschränkte Historien aus.
- README aktualisiert: Smoke-Test-Beschreibung nennt lokale Historienqualität.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich inklusive Historienqualitätsausgabe.
- Priorität angepasst: ursprüngliche Priorität `Historienqualität in Smoke-Test oder Testskript sichtbar machen` ist umgesetzt; neue Priorität ist `Lokale Historienqualität in CI-/GitHub-Check vorbereiten`, weil der Smoke-Test jetzt ohne private Historien laufen kann.

- Lernhistorien-Dateien mit Datenschutz-/Cloud-Hinweisen in README präzisiert: `backtest_history.json` ergänzt und Rollen der Historien erklärt.
- Datenschutz klargestellt: Lernhistorien dürfen keine Broker-Zugangsdaten, API-Keys, Passwörter, Kontonummern oder persönlichen Identifikationsdaten enthalten.
- Streamlit-Cloud-Einschränkung präzisiert: Laufzeitdateien sind keine dauerhafte Datensicherung; lokale Sicherung oder bewusster Export bleibt Nutzerentscheidung.
- Tests dokumentiert: reine README/ROADMAP-Änderung; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erneut vorgesehen vor Commit.
- Priorität angepasst: ursprüngliche Priorität `Lernhistorien-Dateien mit Datenschutz-/Cloud-Hinweisen in README präzisieren` ist umgesetzt; neue Priorität ist `Historienqualität in Smoke-Test oder Testskript sichtbar machen`, weil Qualität lokaler JSON-Historien nun zentraler Analysekontext ist.

- Defekte lokale Historien in Lernansicht mit Reparaturhinweisen ergänzt: `local_history_quality_rows()` zeigt jetzt eine Spalte `Reparaturhinweis`.
- Sicherheitsregel beibehalten: Die App löscht oder verändert lokale Historien nicht automatisch; defekte Einträge werden nur erklärt und ignoriert.
- README aktualisiert: lokale Lernhistorienqualität beschreibt jetzt manuelle Reparaturhinweise.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; direkte Mock-Tests für defekte und gültige Historien erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Defekte lokale Historien in Lernansicht mit Reparaturhinweisen ergänzen` ist umgesetzt; neue Priorität ist `Lernhistorien-Dateien mit Datenschutz-/Cloud-Hinweisen in README präzisieren`, weil die App inzwischen mehrere lokale Historien nutzt.

- Lernhistorien-Datenqualität in Confidence-/Kalibrierungsstatus eingebunden: `calibration_status_rows()` und `similar_setup_rows()` zeigen jetzt den Qualitätsstatus lokaler Historien als Kontext.
- Eingeschränkte Historien relativieren Lernhinweise: Bei eingeschränkter lokaler Historienqualität ergänzt der Kalibrierungsstatus einen Warnhinweis; Confidence-Tabellen zeigen die Qualitätszeile separat.
- README aktualisiert: lokale Historienqualität als Transparenzhinweis für Kalibrierung und Confidence dokumentiert.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter History-Quality-Status-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Lernhistorien-Datenqualität in Confidence-/Kalibrierungsstatus einfließen lassen` ist umgesetzt; neue Priorität ist `Defekte lokale Historien in Lernansicht mit Reparaturhinweisen ergänzen`, weil die App jetzt Einschränkungen erkennt, aber noch keine praktischen nächsten Schritte anbietet.

- Datenqualitäts-Check für Lern-/Backtest-Historien ausgebaut: neue `local_history_quality_rows()` prüft Review-Strukturen, abgeschlossene Auswertungen und belastbare Backtest-Zeilen.
- Analyse-Details erweitert: Die App zeigt `Datenqualität lokaler Lernhistorien` vor den Lernlogik-Guardrails.
- README aktualisiert: lokale Lernhistorienqualität und Teststrategie ergänzt.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Local-History-Quality-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Datenqualitäts-Check für Lern-/Backtest-Historien ausbauen` ist umgesetzt; neue Priorität ist `Lernhistorien-Datenqualität in Confidence-/Kalibrierungsstatus einfließen lassen`, weil eingeschränkte Historien die Belastbarkeit von Lernhinweisen reduzieren sollten.

- Testbarkeit der neuen Lern-/Confidence-Kontextfunktionen gebündelt: `tests/test_stability.py` nutzt jetzt gemeinsame Konstanten und `reviewed_case()` für Kalibrierungskontext-Mocks.
- Wartbarkeit verbessert: Mehrere Tests für Kalibrierungsvorschläge, Fehlmuster, Kalibrierungskontext-Zusammenfassung und ähnliche Setups verwenden dieselbe Mock-Historie.
- README aktualisiert: Teststrategie für Lern-/Confidence-Kontexte ergänzt.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Testbarkeit der neuen Lern-/Confidence-Kontextfunktionen bündeln` ist umgesetzt; neue Priorität ist `Datenqualitäts-Check für Lern-/Backtest-Historien ausbauen`, weil belastbare Historien die Grundlage der Lernmodule sind.

- Lernsystem-Ausgabe für Kalibrierungskontext verständlicher zusammengefasst: neue `calibration_context_summary_rows()` erzeugt eine kompakte Tabelle mit Fallzahl, Fehlquote, Durchschnittsrendite und praktischer Bedeutung.
- Analyse-Details erweitert: Direkt nach den Lernlogik-Guardrails zeigt die App `Kalibrierungskontext kurz erklärt`.
- README aktualisiert: Lernlogik-Guardrails beschreiben die neue Kalibrierungskontext-Zusammenfassung.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Kalibrierungskontext-Zusammenfassungs-Mock-Test erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Lernsystem-Ausgabe für Kalibrierungskontext verständlicher zusammenfassen` ist umgesetzt; neue Priorität ist `Testbarkeit der neuen Lern-/Confidence-Kontextfunktionen bündeln`, weil mehrere neue Kontextfunktionen ähnliche Mock-Daten nutzen.

- Confidence-System gegen Kalibrierungskontext aus Performance-Reviews geprüft: `similar_setup_rows()` zeigt jetzt häufigsten `Kalibrierungskontext` und `Kalibrierungshinweis` aus ähnlichen lokalen Fällen.
- Score-Trennung beibehalten: Die neuen Confidence-Kontexte sind reine Transparenzhinweise und verändern keine Gewichtungen.
- README aktualisiert: Confidence-System nennt Kalibrierungskontext als zusätzlichen Review-Kontext.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Confidence-Kalibrierungskontext-Mock-Test erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Confidence-System gegen Kalibrierungskontext aus Performance-Reviews prüfen` ist umgesetzt; neue Priorität ist `Lernsystem-Ausgabe für Kalibrierungskontext verständlicher zusammenfassen`, weil die neuen Kontexte jetzt über mehrere Tabellen verteilt sind.

- Lern-/Signalanalyse gegen Performance-Kalibrierungskontext geprüft: `evaluated_history_cases()` übernimmt jetzt `calibration_context` und `calibration_hint` aus Review oder Setup.
- Fehlmuster und Kalibrierung erweitert: `negative_case_cause_rows()` und `calibration_suggestion_rows()` können Kalibrierungskontext und Kalibrierungshinweis gruppieren.
- README aktualisiert: Signalanalyse nennt Kalibrierungskontext als Fehlmuster-Dimension.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Lern-Kalibrierungskontext-Mock-Test erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Lern-/Signalanalyse gegen Performance-Kalibrierungskontext prüfen` ist umgesetzt; neue Priorität ist `Confidence-System gegen Kalibrierungskontext aus Performance-Reviews prüfen`, weil ähnliche Setup-Ausgaben diese Warnkontexte ebenfalls anzeigen sollten.

- Performance-Tracking-Auswertung gegen Kalibrierungskontext-Felder geprüft: Trade-Journal-Reviews speichern jetzt `calibration_context` und `calibration_hint` aus dem ursprünglichen Setup.
- Setup-Kontext bleibt erhalten: Performance Reviews überschreiben die ursprünglichen Kalibrierungshinweise nicht, sondern führen sie als Auswertungskontext mit.
- README aktualisiert: Performance Tracking beschreibt jetzt den ursprünglichen Kalibrierungskontext.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Performance-Kalibrierungskontext-Mock-Test erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Performance-Tracking-Auswertung gegen Kalibrierungskontext-Felder prüfen` ist umgesetzt; neue Priorität ist `Lern-/Signalanalyse gegen Performance-Kalibrierungskontext prüfen`, weil diese Review-Felder für spätere Signalqualität relevant sind.

- Trade-Journal-Speicherung gegen neue Kalibrierungskontext-Felder geprüft: `normalize_trade_record()` übernimmt `calibration_context` und `calibration_hint` in `Kalibrierungskontext` und `Kalibrierungshinweis`.
- Default-Verhalten ergänzt: Fehlen die Felder, zeigt das Trade Journal `Daten nicht verfügbar` und verändert keine Einschätzung.
- README aktualisiert: Trade Journal beschreibt jetzt den erhaltenen Kalibrierungskontext.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Trade-Journal-Kalibrierungsfeld-Mock-Test erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Trade-Journal-Speicherung gegen neue Kalibrierungskontext-Felder prüfen` ist umgesetzt; neue Priorität ist `Performance-Tracking-Auswertung gegen Kalibrierungskontext-Felder prüfen`, weil Review-Auswertungen diese Setup-Kontexte erhalten müssen.

- Scanner- und Trading-Ausgaben mit Backtest-/Kalibrierungskontext verbunden: Opportunity Scanner und Trading-Setups zeigen jetzt `Kalibrierungskontext` und `Kalibrierungshinweis` aus schwachen gespeicherten Backtest-Mustern.
- Score-Trennung beibehalten: Opportunity Score, Chance, Confidence und Kaufsignal werden dadurch nicht automatisch verändert.
- README aktualisiert: Opportunity Scanner und Trading-Modus beschreiben die neuen Kalibrierungskontext-Felder.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Scanner-/Trading-Kalibrierungskontext-Mock-Test erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Scanner- und Trading-Ausgaben mit Backtest-/Kalibrierungskontext verbinden` ist umgesetzt; neue Priorität ist `Trade-Journal-Speicherung gegen neue Kalibrierungskontext-Felder prüfen`, weil diese Felder in späteren Performance-Auswertungen erhalten bleiben sollten.

- Kalibrierungsvorschläge mit Backtest-Historie verbunden: schwache gespeicherte Backtest-Gruppen mit ausreichender Datenbasis erscheinen jetzt als Bereich `Backtest-Signal`.
- Keine automatische Kalibrierung: Backtest-Hinweise bleiben manuelle Vorschläge mit Datenbasis, Fehlquote, Begründung und Umsetzungshinweis.
- README aktualisiert: Signalanalyse beschreibt Backtest-basierte manuelle Kalibrierungshinweise.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Backtest-Kalibrierungs-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Kalibrierungsvorschläge mit Backtest-Historie verbinden` ist umgesetzt; neue Priorität ist `Scanner- und Trading-Ausgaben mit Backtest-/Kalibrierungskontext verbinden`, weil Lernhinweise bei neuen Chancen sichtbar sein sollten.

- Backtesting-Ausgabe gegen Lern-/Confidence-Kontext konsolidiert: Backtest-Gruppen zeigen jetzt `Historienstatus` und `Lernhinweis`; gespeicherte Backtest-Historie zeigt zusätzlich einen `Confidence-Kontext`.
- Mindestdatenregel vereinheitlicht: Unter 20 Fällen bleibt der Kontext `Datenbasis zu klein`, 20 bis 50 Fälle sind vorsichtige Lernhinweise, über 50 Fälle sind nur manuell prüfbare Kalibrierungshinweise.
- README aktualisiert: Backtesting-Basis beschreibt Historienstatus, Confidence-Kontext und Lernhinweis.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Backtest-Confidence-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Backtesting-Ausgabe gegen Lern-/Confidence-Kontext prüfen` ist umgesetzt; neue Priorität ist `Kalibrierungsvorschläge mit Backtest-Historie verbinden`, weil die Backtest-Ergebnisse nun als Lernkontext strukturiert vorliegen.

- Confidence-System gegen erweiterten Historienkontext konsolidiert: `similar_setup_rows()` zeigt jetzt häufigste Szenario-Lesart, Fehlursache, Decision-Alignment und Historienstatus aus ähnlichen lokalen Review-Fällen.
- Keine Blackbox-Änderung: Die neuen Context-Felder erklären ähnliche Setups, verändern aber keine Score-Gewichtungen automatisch.
- README aktualisiert: Confidence-System beschreibt die zusätzlichen Review-Kontexte.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Confidence-Kontext-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Confidence-System gegen erweiterten Trade-/Decision-/Prediction-Historienkontext prüfen` ist umgesetzt; neue Priorität ist `Backtesting-Ausgabe gegen Lern-/Confidence-Kontext prüfen`, weil Backtesting die nächste Messschicht für die Analysequalität ist.

- Performance-Tracking gegen normalisierte Journal-Felder konsolidiert: `evaluate_due_trade_history()` normalisiert Trade-Records vor der Auswertung und hält Legacy-Felder kompatibel.
- Historienkontext im Review ergänzt: Trade-Journal-Auswertungen speichern jetzt ähnliche Setups, Treffer ähnlicher Setups, Trefferquote, Historienstatus und Historienhinweis im jeweiligen Review-Ergebnis.
- Ergebnislogik unverändert: Ziel/Stop, Rendite, maximale positive/negative Bewegung, beste Alternative und Opportunitätskosten bleiben reine Nachauswertung mit echten Kursdaten.
- README aktualisiert: Performance Tracking beschreibt jetzt Historienkontext aus ähnlichen Setups.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Performance-Tracking-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Performance-Tracking-Ausgabe gegen normalisierte Journal-Felder und Historienkontext prüfen` ist umgesetzt; neue Priorität ist `Confidence-System gegen erweiterten Trade-/Decision-/Prediction-Historienkontext prüfen`, weil Confidence-Ausgaben die erweiterten Review-Felder transparent nutzen sollten.

- Trade-Journal-Datenmodell konsolidiert: `append_trade_records()` normalisiert neue und ältere Feldnamen beim Speichern in `trade_history.json`.
- Legacy-Kompatibilität verbessert: Alias-Felder wie `created_at`, `symbol`, `entry_price`, `target`, `stop`, `similar_setups` und `history_status` werden in die deutschen Journal-Felder übernommen.
- Performance-Tracking vorbereitet: Neue Journal-Einträge erhalten defensiv `review_after`, Historienstatus, ähnliche Setups und Sicherheits-Hinweis, ohne bestehende Werte zu überschreiben.
- README aktualisiert: Trade Journal beschreibt jetzt defensive Feldnormalisierung.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Trade-Journal-Normalisierungscheck erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Trade-Journal-Datenmodell gegen neue Trading-/Performance-Felder konsolidieren` ist umgesetzt; neue Priorität ist `Performance-Tracking-Ausgabe gegen normalisierte Journal-Felder und Historienkontext prüfen`, weil die Auswertung auf den normalisierten Journal-Daten aufsetzt.

- Trading-Modus gegen Lern-/Confidence-Kontext konsolidiert: Trading-Setups zeigen und speichern jetzt Treffer ähnlicher Setups, Trefferquote, Historienstatus und Historienhinweis.
- Performance verbessert: `build_trading_setup()` verwendet bereits geladene Yahoo-Stammdaten für die Asset-Qualität und vermeidet eine doppelte Stammdatenabfrage pro Setup.
- Trade-Journal-Kontext erweitert: Die neuen Felder werden beim automatischen lokalen Dokumentieren mitgespeichert; keine Order, keine Broker-Anbindung.
- README aktualisiert: Trading-Modus beschreibt jetzt Historienstatus und ähnliche Setups.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Trading-Setup-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Trading-Modus-Ergebnisliste gegen Lern-/Confidence-Kontext und Journal-Felder prüfen` ist umgesetzt; neue Priorität ist `Trade-Journal-Datenmodell gegen neue Trading-/Performance-Felder konsolidieren`, weil gespeicherte Setups die Basis für spätere Performance-Auswertungen sind.

- Opportunity Scanner mit Lern-/Confidence-Kontext erweitert: Scanner-Ergebnisse zeigen jetzt ähnliche historische Setups, Trefferquote ähnlicher Setups und Historienstatus.
- Score-Trennung beibehalten: Der Historienkontext verändert den Opportunity Score nicht automatisch, sondern wird als Transparenzfeld und Begründung angezeigt.
- Testbarkeit ergänzt: Scanner-Mock-Test prüft weiter einmalige Yahoo-Stammdatennutzung und zusätzlich die neuen Historienfelder.
- README aktualisiert: Opportunity Scanner beschreibt jetzt historische Setup-Anzahl und Trefferquote.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Scanner-Historien-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Opportunity-Scanner-Ergebnisliste gegen Lern-/Confidence-Kontext prüfen` ist umgesetzt; neue Priorität ist `Trading-Modus-Ergebnisliste gegen Lern-/Confidence-Kontext und Journal-Felder prüfen`, weil Trading-Setups direkt aus Scanner-Kandidaten entstehen und ins Journal fließen.

- Kalibrierungs- und Lernmodul konsolidiert: `evaluated_history_cases()` normalisiert jetzt zusätzlich Szenario-Lesart, Fehlursache und Decision-Alignment aus Review-Daten.
- Fehlfall- und Kalibrierungstabellen erweitert: negative Fälle und Kalibrierungsvorschläge können nun nach Szenario-Lesart, Fehlursache und Decision-Alignment gruppiert werden.
- Signalanalyse erweitert: negative Prognosefälle können Fehlursachen als Lernhinweis anzeigen, ohne Gewichtungen automatisch zu ändern.
- README aktualisiert: Kalibrierungsbereich beschreibt die neuen Lernfelder.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkte Lern-/Kalibrierungs-Mock-Tests erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Kalibrierungs- und Lernmodul gegen Prognose-/Decision-/Forward-Erweiterungen konsolidieren` ist umgesetzt; neue Priorität ist `Opportunity-Scanner-Ergebnisliste gegen Lern-/Confidence-Kontext prüfen`, weil Scanner-Vorschläge die vorhandene Historie transparent berücksichtigen sollten.

- Prognose-Tracking konsolidiert: Prognose-Auswertungen speichern jetzt neben `scenario_read` auch eine einfache `miss_reason` aus vorhandener Marktphase, Signal-Snapshot, Modul-Scores oder Kursentwicklung.
- Trefferquoten erweitert: `prediction_hit_rate_rows()` gruppiert ausgewertete Prognosen zusätzlich nach Szenario-Lesart und Fehlursache.
- Keine Daten erfunden: Fehlursachen werden nur aus bereits gespeicherten Signalen/Modul-Scores oder echter Kursentwicklung abgeleitet; fehlende Felder bleiben kompatibel.
- README aktualisiert: Prognose-Tracking beschreibt jetzt Szenario-Lesart und mögliche Fehlursachen.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Prognose-Tracking-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Prognose-Tracking-Hauptliste gegen Szenario-Treffer, Modulgruppen und Fehlursachen konsolidieren` ist umgesetzt; neue Priorität ist `Kalibrierungs- und Lernmodul gegen Prognose-/Decision-/Forward-Erweiterungen konsolidieren`, weil die neuen Review-Felder nun in der Lernlogik nutzbar gemacht werden sollten.

- Decision-Tracking konsolidiert: Decision-Reviews speichern jetzt zusätzlich App-Exposure, Entscheidungsexposure und ob die Nutzerentscheidung mit oder gegen die App-Einschätzung getroffen wurde.
- Nutzerkontext bleibt erhalten: `user_note`, App-Aktion, Professional-Decision-Kontext, Asset-Qualität, Kaufsignal, Confidence, Marktphase, Signal-Snapshot und Modul-Scores bleiben im lokalen Decision-Datensatz.
- Ergebnisvergleich bleibt getrennt von Empfehlungen: Beste Alternative und Opportunitätskosten werden nur nachträglich aus echten Kursdaten berechnet und verändern keine Live-Scores.
- README aktualisiert: Decision-Tracking beschreibt jetzt Kommentar, App-Alignment, beste Alternative und Opportunitätskosten.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Decision-Tracking-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Decision-Tracking-Hauptliste gegen gespeicherte Scores, Nutzerkommentar und Ergebnisvergleich konsolidieren` ist umgesetzt; neue Priorität ist `Prognose-Tracking-Hauptliste gegen Szenario-Treffer, Modulgruppen und Fehlursachen konsolidieren`, weil Prognosen die nächste wichtige Quelle für messbare Analysequalität sind.

- Forward-Testing konsolidiert: Fällige Forward-Test-Auswertungen speichern jetzt zusätzlich eine einfache Szenario-Lesart aus echter Kursentwicklung.
- Lernfähigkeit verbessert: Signalanalyse zählt ausgewertete Forward-Tests nun zusätzlich nach Szenario-Lesart und gespeicherten Modul-Score-Gruppen.
- Kompatibilität beibehalten: Alte Forward-Test-Historien ohne Modul-Scores oder Szenario-Lesart bleiben lesbar; fehlende Felder werden nicht erfunden.
- README aktualisiert: Forward-Testing beschreibt jetzt Szenario-Lesart, Modul-Scores und die Regel, dass Gewichtungen nicht automatisch geändert werden.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Forward-Test-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Forward-Testing-Hauptliste gegen gespeicherte Modul-Scores, Szenarien und Ergebnisgruppen konsolidieren` ist umgesetzt; neue Priorität ist `Decision-Tracking-Hauptliste gegen gespeicherte Scores, Nutzerkommentar und Ergebnisvergleich konsolidieren`, weil Nutzerentscheidungen die nächste wichtige Messschicht für Analysequalität sind.

- Krypto-Zyklus-Kontext erweitert: Das Krypto-Zyklusmodul nutzt jetzt eine testbare Halving-Kontextfunktion mit Zyklusphase, Zyklusfortschritt, Score und praktischer Anlegerbedeutung.
- Anfänger-Transparenz verbessert: Der Halving-Zyklus wird ausdrücklich als Kontextsignal und nicht als Kaufsignal erklärt; Trend, Liquidität, Volatilität, Makro und Risikomarken bleiben wichtiger.
- Keine Krypto-Daten erfunden: ETF-Flows, Fear & Greed, On-Chain, Orderbuch, Spread, Börsentiefe und Stablecoin-Liquidität bleiben ohne belastbare Quelle `Daten nicht verfügbar`.
- README aktualisiert: Krypto-Zyklus beschreibt jetzt Zyklusfortschritt, Anlegerbedeutung und Unsicherheitsregel.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Krypto-Zyklus-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Krypto-Zyklus-Kontext prüfen und verständlicher in Krypto-Analyse integrieren` ist umgesetzt; neue Priorität ist `Forward-Testing-Hauptliste gegen gespeicherte Modul-Scores, Szenarien und Ergebnisgruppen konsolidieren`, weil messbare Analysequalität und Lernfähigkeit Vorrang vor Komfortfunktionen haben.

- Performance-Tracking für Trade Journal erweitert: Fällige Trade-Auswertungen speichern jetzt zusätzlich gewählte Aktion, beste Alternative, Rendite der besten Alternative und Opportunitätskosten.
- Ziel-/Stop-Auswertung bleibt unverändert erhalten: Ziel erreicht, Stop erreicht, Rendite sowie maximale positive und negative Entwicklung werden weiterhin aus echten Kursdaten berechnet.
- Testbarkeit ergänzt: Neuer Mock-Test prüft einen Long-Trade mit Stop-Berührung, negativer Rendite und Short/Absicherung als beste Alternative.
- README aktualisiert: Performance Tracking beschreibt jetzt beste Alternative und Opportunitätskosten.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkte Funktionschecks für beste Alternative und Trade-Performance-Auswertung erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Performance-Tracking für Trade Journal um beste Alternative und Ziel-/Stop-Auswertung gegen Roadmap prüfen` ist umgesetzt; neue Priorität ist `Krypto-Zyklus-Kontext prüfen und verständlicher in Krypto-Analyse integrieren`, weil Krypto-Analysequalität wichtiger ist als Komfortfunktionen und fehlende Spezialdaten transparent kompensiert werden müssen.

### 2026-07-31

- Scanner-Performance verbessert: `scan_opportunities()` verwendet bereits geladene Yahoo-Stammdaten nun direkt für die Asset-Qualität und vermeidet dadurch eine doppelte Stammdatenabfrage pro Ticker.
- Testbarkeit ergänzt: Ein neuer Mock-Test prüft, dass der Opportunity Scanner pro Symbol nur einmal `load_ticker_info()` aufruft und die Faktor-Spalten weiter ausgibt.
- README aktualisiert: Opportunity Scanner dokumentiert jetzt die Wiederverwendung geladener Stammdaten.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Scanner-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Scanner-Performance und Testbarkeit nach Faktorabdeckung prüfen` ist umgesetzt; neue Priorität ist `Performance-Tracking für Trade Journal um beste Alternative und Ziel-/Stop-Auswertung gegen Roadmap prüfen`, weil die Lernfähigkeit von vollständigen Ergebnisdaten abhängt.

- News-Modul erweitert: Yahoo-News werden defensiv normalisiert und je Nachricht mit Quelle, Datum, Relevanz und Sentiment-Qualität angezeigt.
- Keine News erfunden: Fehlende, unklare oder leere News-Daten bleiben neutral und werden als `Daten nicht verfügbar` ausgewiesen.
- README aktualisiert: Research-Modul beschreibt die neue News-Transparenz.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; direkte Funktionschecks für fehlende News und News mit Quelle/Datum/Relevanz erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich.
- Nächste Priorität angepasst: Makro-Modul erweitern, Inflation, Realzinsen, Liquidität und Risikoappetit transparenter machen.
- Institutionelle Research-Module validiert: Analysten-Konsens, Earnings, Event-Risiko und institutionelle Daten zeigen jetzt Datenabdeckung und Score-Neutralität.
- Keine institutionellen Daten erfunden: Fehlende Analysten-, Earnings-, Event-, Insider-, Short-Interest- oder ETF-Flow-Daten bleiben ausdrücklich `Daten nicht verfügbar`.
- README aktualisiert: Research-Modul beschreibt Datenabdeckung und Score-Neutralität für institutionelle Module.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; direkte Funktionschecks für fehlende und verfügbare institutionelle Daten erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich.
- Nächste Priorität angepasst: News-Modul verbessern, Quelle, Datum, Relevanz und Sentiment-Qualität transparenter machen.
- Bewertungsmodell erweitert: Aktienbewertung zeigt jetzt Forward-KGV-Abstand, EV/Umsatz, Sektor-/Branchenkontext sowie klar getrennte Hinweise zu historischer Bewertungszeitreihe und Peer-Vergleich.
- Keine Daten erfunden: Wenn Yahoo Finance keine historische Multiple-Zeitreihe oder Peer-Multiples liefert, zeigt die App ausdrücklich `Daten nicht verfügbar`.
- README aktualisiert: Research-Modul beschreibt die erweiterten Bewertungskennzahlen und die Transparenzregel für fehlende Historien-/Peer-Daten.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; direkte Funktionschecks für verfügbare Bewertungsdaten und fehlende Peer-/Historienwerte erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich.
- Nächste Priorität angepasst: Analysten-, Earnings-, Event- und institutionelle Module validieren und auf zusätzliche Datenquellen prüfen.

### 2026-07-20

- Kalibrierungsvorschläge aus Fehlmustern umgesetzt: Die App erzeugt im Analyse-Detailbereich manuelle Prüfhinweise mit Datenbasis, Fehlquote, Begründung und Umsetzungsregel.
- Mindestdatenlogik beibehalten: Unter 20 Fällen wird nur gezählt; 20 bis 50 Fälle liefern vorsichtige Hinweise; über 50 Fälle erlauben manuelle Kalibrierungsvorschläge.
- README aktualisiert: Signalanalyse beschreibt nun auch konkrete Kalibrierungsvorschläge aus Fehlmustern.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; direkte Funktionschecks für leere Historie, keine Fehlmuster und große Fehlerbasis erfolgreich; `pytest` konnte nicht laufen, weil das Modul in der lokalen venv fehlt.
- Nächste Priorität angepasst: Bewertungsmodelle ausbauen, historische Bewertung, relative Bewertung und Peer-Vergleich prüfen, falls Daten verfügbar sind.
- Fehlfall-Ursachenanalyse umgesetzt: Verfehlte Historienfälle werden im Analyse-Detailbereich nach Asset-Typ, Marktphase, Kaufsignal, RSI, MACD, Volatilität, CRV, News und Makro gruppiert.
- Mindestdatenlogik beibehalten: Unter 20 Fehlfällen wird nur gezählt; ab 20 Fällen gibt es vorsichtige Hinweise; Gewichtungen werden nie automatisch geändert.
- README aktualisiert: Signalanalyse beschreibt nun auch die gruppierte Fehlfall-Ursachenanalyse.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Tests für leere Historie, keine Fehlfälle und Fehlfall-Gruppen erfolgreich.
- Nächste Priorität angepasst: Lernmodul mit konkreten Kalibrierungsvorschlägen aus häufigen Fehlerursachen erweitern.
- Backtest-Historie in Lern- und Kalibrierungsübersicht integriert: Gespeicherte Backtests aus `backtest_history.json` werden als separater Lernkontext mit Fallzahl, Trefferquote, Durchschnittsrendite und Drawdown angezeigt.
- Transparenzregel beibehalten: Backtest-Historie verändert keine Scores und keine Gewichtungen automatisch.
- README aktualisiert: Kalibrierungsbereich erklärt den neuen Backtest-Lernkontext.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Tests für leere, dünne und belastbare Backtest-Historie erfolgreich.
- Nächste Priorität angepasst: Fehlprognosen und negative Historienfälle nach Ursache kategorisieren.
- Backtesting-Kompaktansicht umgesetzt: Der Analyse-Detailbereich zeigt jetzt beste Trefferquote, schwächste Rendite, größten Drawdown und größte Datenbasis oberhalb der vollständigen Backtest-Tabelle.
- Backtest-Verdichtung bleibt konservativ: Gruppen unter 20 Fällen werden nicht als belastbar interpretiert.
- README aktualisiert: Backtesting-Basis beschreibt nun die Kompaktansicht.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Tests für Backtesting-Kompaktansicht und kleine Datenbasis erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich.
- Nächste Priorität angepasst: Backtest-Historie in Lern- und Kalibrierungsübersicht integrieren.
- Backtesting-Signal-Kombinationen umgesetzt: Die Backtest-Tabelle vergleicht jetzt Kaufsignal-Bucket, RSI-Bucket, MACD-Bucket und CRV-Bucket gemeinsam.
- Die Backtest-Ausgabe zeigt weiterhin Asset-Typ, damalige Marktphase, Zeithorizont, Trefferquote, Durchschnittsrendite und maximalen Drawdown; unter 20 Fällen bleibt `Datenbasis zu klein`.
- README und UI-Überschrift aktualisiert: Backtesting wird nun als historische Signal-Kombinationsauswertung beschrieben.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Tests für Signal-Kombinationen und kurze Historie erfolgreich.
- Nächste Priorität angepasst: Backtesting-Tabelle besser verdichten und interpretieren.
- Backtest-Ergebnisse dauerhaft nutzbar gemacht: Die aktuelle Backtest-Tabelle kann lokal in `backtest_history.json` gespeichert werden.
- Datenschutz umgesetzt: `backtest_history.json` ist in `.gitignore` aufgenommen und enthält nur Analyse-/Backtestdaten, keine Depot-, Broker- oder Zugangsdaten.
- README aktualisiert: lokale Backtest-Historie und Datenschutzliste ergänzt.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Test für Speichern und Laden von Backtest-Ergebnissen erfolgreich.
- Nächste Priorität angepasst: Backtesting-Signal-Kombinationen vergleichen.
- Backtesting verfeinert: Die Backtest-Tabelle gruppiert historische Kaufsignal-Buckets jetzt zusätzlich nach Asset-Typ und damaliger Marktphase.
- Drawdown-Basis ergänzt: Je Backtest-Gruppe wird der maximale Drawdown im späteren Kursfenster angezeigt, sobald mindestens 20 Fälle vorhanden sind.
- README aktualisiert: Backtesting-Basis beschreibt nun Asset-Typ, Marktphase und Drawdown.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Tests für segmentiertes Backtesting und kurze Historie erfolgreich.
- Nächste Priorität angepasst: Backtest-Ergebnisse dauerhaft nutzbar machen.
- Backtesting-Basis umgesetzt: Im Analyse-Detailbereich werden historische Kaufsignal-Buckets gegen spätere Kursentwicklungen über 1, 3, 6 und 12 Monate getestet.
- Backtest-Regeln dokumentiert: Es handelt sich um einen Signaltest, keine Strategieoptimierung, keine automatische Gewichtungsänderung und keine Kauf-/Verkaufsautomatisierung.
- README aktualisiert: Backtesting-Basis beschrieben.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; Mock-Tests für Backtest mit ausreichender und zu kurzer Historie erfolgreich.
- Nächste Priorität angepasst: Backtesting nach Asset-Typ und Marktphase verfeinern.
- Tracking-Zeiträume erweitert: Trade-Journal, Forward-Tests, Prognosen und Decision-Tracking nutzen jetzt zentral `1w`, `1m`, `3m`, `6m` und `12m`.
- Alte Historien bleiben kompatibel: fehlende `6m`- und `12m`-Felder werden beim Auswerten ergänzt, ohne bestehende Review-Ergebnisse zu überschreiben.
- Neue gespeicherte Analysen, Entscheidungen, Prognosen und Trading-Setups erhalten direkt den vollständigen Review-Plan.
- README aktualisiert: Performance-Tracking und Prognose-Tracking nennen jetzt 6- und 12-Monats-Auswertungen.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Test mit alten Historien für Trade, Decision, Prognose und Forward erfolgreich.
- Nächste Priorität angepasst: Backtesting-Basis vorbereiten.

### 2026-07-31

- Opportunity-Scanner-Faktorabdeckung erweitert: Scanner-Ergebnisse zeigen jetzt News, Makro, Liquidität, Bewertung und institutionelle Faktoren separat.
- Fehlende Scanner-Daten bleiben transparent: Institutionelle Faktoren, Bewertung oder Liquidität werden als `Daten nicht verfügbar` angezeigt, wenn Yahoo/Marktdaten keine belastbare Quelle liefern.
- Keine Handelsfunktion ergänzt: Scanner bleibt Vorschlags- und Vergleichswerkzeug; keine Käufe, Verkäufe oder Broker-Anbindung.
- README aktualisiert: Opportunity Scanner beschreibt jetzt zusätzliche Faktorgruppen und fehlende Datenquellen.
- Tests dokumentiert: direkte Scanner-Faktor-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Opportunity-Scanner-Modulabdeckung transparenter machen` ist umgesetzt; neue Priorität ist `Scanner-Performance und Testbarkeit nach Faktorabdeckung prüfen`, weil zusätzliche News-/Yahoo-Faktorabfragen bei großen Watchlists Laufzeit erzeugen können.
- Trade-Journal-Automatik umgesetzt: Trading-Setups aus Scanner-Kandidaten werden beim Scannerlauf automatisch lokal in `trade_history.json` dokumentiert.
- Deduplizierung ergänzt: Setups werden nach Ticker, Richtung und Tag dedupliziert, damit Streamlit-Reruns nicht mehrere gleiche Journal-Einträge erzeugen.
- Sicherheitsgrenzen beibehalten: Trade-Journal speichert nur lokale Analyse-/Trackingdaten; keine Order, keine Broker-Anbindung, keine Kauf-/Verkaufsautomatisierung.
- README aktualisiert: Trade Journal beschreibt jetzt automatische lokale Dokumentation mit Deduplizierung.
- Tests dokumentiert: direkte Trade-Journal-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Trade-Journal-Automatik gegen Roadmap-Anforderung prüfen` ist umgesetzt; neue Priorität ist `Opportunity-Scanner-Modulabdeckung transparenter machen`, weil die Roadmap zusätzliche Scanner-Faktoren wie News, Makro, Liquidität, Bewertung und institutionelle Faktoren fordert.
- Lernlogik-Guardrails ergänzt: Die Analyse-Details zeigen jetzt dokumentierte Fälle, ausgewertete Fälle, Mindestdatenregeln und die aktuelle Freigabe für Lern-/Kalibrierungshinweise.
- Testbarkeit verbessert: `learning_guardrail_rows()` kapselt die Mindestdatenlogik und macht prüfbar, dass unter 20 Fällen keine Kalibrierung erfolgt und über 50 Fällen nur manuelle Vorschläge erlaubt sind.
- Keine Blackbox-Änderungen: Der Guardrail-Block zeigt explizit, dass Score-Gewichtungen, Kaufsignal-Schwellen und Portfolio-Logik niemals automatisch durch das Lernsystem geändert werden.
- README aktualisiert: Kalibrierungsbereich beschreibt jetzt Lernlogik-Guardrails, ausgewertete Fälle und Datenbasisgrenzen.
- Tests dokumentiert: direkte Lernlogik-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Lernlogik-Dokumentation und Testbarkeit konsolidieren` ist umgesetzt; neue Priorität ist `Trade-Journal-Automatik gegen Roadmap-Anforderung prüfen`, weil die Roadmap automatische lokale Dokumentation vorgeschlagener Trades fordert, aber keine automatische Orderfunktion erlaubt.
- Prognose-Tracking konsolidiert: Neue Prognosen speichern jetzt Research-Modul-Scores zusätzlich zu Szenarien, Kurszielen, Wahrscheinlichkeiten, entscheidender Marke und Signal-Snapshot.
- Trefferquoten je Asset und Modul ergänzt: Die Analyse-Details zeigen ausgewertete Prognosen nach Asset-Typ sowie Modul-/Signalgruppen; alte Prognosen ohne Modul-Scores bleiben über `signal_snapshot` kompatibel.
- Mindestdatenlogik beibehalten: Unter 20 Fällen werden Prognosegruppen nur gezählt; ab 20 Fällen sind vorsichtige Hinweise möglich; Gewichtungen werden nie automatisch geändert.
- README aktualisiert: Prognose-Tracking beschreibt jetzt Modul-Scores, Asset-/Modultrefferquoten und Datenbasisgrenzen.
- Tests dokumentiert: direkte Prognose-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Prognose-Tracking-Hauptliste konsolidieren und Modul-Trefferquoten prüfen` ist umgesetzt; neue Priorität ist `Lernlogik-Dokumentation und Testbarkeit konsolidieren`, weil die nächste Analysequalitätsverbesserung in nachvollziehbarer Kalibrierung und Mindestdatenlogik liegt.
- Krypto-Spezialdaten transparenter gemacht: Krypto-Fundamentals, Krypto-Asset-Qualität und Krypto-Zyklus zeigen jetzt Datenabdeckung und Score-Neutralität für Fear & Greed, ETF-Flows, On-Chain, Orderbuch/Spread, Stablecoin-Liquidität und Volumenvergleich.
- Krypto-Marktstruktur ergänzt: Das Krypto-Zyklusmodul bewertet verfügbare 50er/200er-Trendstruktur zusätzlich zu Halving-Zeitfenster, Volatilität und Volumenvergleich.
- Keine Krypto-Daten erfunden: Fear & Greed, ETF-Flows, On-Chain-Daten, Orderbuch, Spread, Börsentiefe und Stablecoin-Liquidität bleiben ohne belastbare Quelle ausdrücklich `Daten nicht verfügbar`.
- README aktualisiert: Krypto-Zyklus beschreibt jetzt Datenabdeckung, Marktstruktur und fehlende Spezialdatenquellen.
- Tests dokumentiert: direkte Krypto-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Krypto-Modul: externe Krypto-Spezialdaten und Marktstruktur transparenter prüfen` ist umgesetzt; neue Priorität ist `Prognose-Tracking-Hauptliste konsolidieren und Modul-Trefferquoten prüfen`, weil die PRIO-B-Umsetzung bereits weit fortgeschritten ist, aber die ältere Hauptliste noch offene Formulierungen enthält.
- Risiko- und Liquiditätsmodule verfeinert: Risiko-Score zeigt jetzt Datenabdeckung, Score-Neutralität, Asset-Typ-Volatilität, Risiko bis Unterstützung, Potenzial bis Widerstand und CRV-Einordnung.
- Liquiditäts-Score erweitert: relatives Volumen zum 20er-Schnitt, Yahoo-Durchschnittsvolumen, 10T-Durchschnittsvolumen und fehlende Spread-/Orderbuchdaten werden transparent ausgewiesen.
- Keine Markttiefedaten erfunden: Bid-Ask-Spread, Orderbuchtiefe, Börsentiefe und Stablecoin-Liquidität bleiben `Daten nicht verfügbar`, wenn keine belastbare Quelle eingebunden ist.
- README aktualisiert: Risiko-Score und Liquiditäts-Score beschreiben jetzt Datenabdeckung und praktische Grenzen.
- Tests dokumentiert: direkte Risiko-/Liquiditäts-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Risiko- und Liquiditätsmodul verfeinern` ist umgesetzt; neue Priorität ist `Krypto-Modul: externe Krypto-Spezialdaten und Marktstruktur transparenter prüfen`, weil Krypto-Signale stark von Datenquellen wie Fear & Greed, ETF-Flows, On-Chain und Liquiditätsstruktur abhängen.
- Geopolitik-Modul umgesetzt: neuer `Geopolitik-Score` im Research-Pack nutzt ausschließlich verfügbare Yahoo-News-Titel als Hinweisquelle für Sanktionen, Zölle, Krieg, Lieferkettenstress oder Exportkontrollen.
- Keine geopolitischen Daten erfunden: Wenn keine News verfügbar sind, zeigt das Modul `Geopolitische Daten nicht verfügbar`; wenn keine Treffer gefunden werden, wird das ausdrücklich nicht als vollständige Entwarnung formuliert.
- Unsicherheitsfaktoren verbessert: geopolitische Risiken werden jetzt nicht mehr nur pauschal genannt, sondern abhängig von Datenverfügbarkeit und Geopolitik-Score eingeordnet.
- README aktualisiert: Geopolitik-Score und Grenzen der Datenlage dokumentiert.
- Tests dokumentiert: direkte Geopolitik-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Geopolitik-Modul prüfen` ist umgesetzt; neue Priorität ist `Risiko- und Liquiditätsmodul verfeinern`, weil Risiko, Volumenqualität und Handelbarkeit die praktische Belastbarkeit eines Kaufsignals stark beeinflussen.
- Makro-Modul erweitert: Datenabdeckung und Score-Neutralität werden jetzt im Makro-Score ausgewiesen.
- Makro-Proxies transparenter gemacht: Risikoappetit/Nasdaq, Zinsdruck/US-Zinsen, Dollar-/Liquiditätsdruck und TIP als Inflations-/Realzinsproxy werden einzeln erklärt.
- Keine Makro- oder Liquiditätsdaten erfunden: direkte Liquiditätsdaten bleiben ohne belastbare Quelle `Daten nicht verfügbar`, und fehlende Proxies führen zu neutraler Bewertung statt Scheingenauigkeit.
- README aktualisiert: Makro-Score beschreibt jetzt Datenabdeckung, Score-Neutralität und verfügbare Proxy-Daten.
- Tests dokumentiert: direkte Makro-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Makro-Modul erweitern` ist umgesetzt; neue Priorität ist `Geopolitik-Modul prüfen`, weil geopolitische Risiken hohe Analysewirkung haben, aber nur mit belastbarer Datenlage aufgenommen werden dürfen.

### 2026-07-19

- Segmentierte Lernanalyse umgesetzt: Die App zeigt im Analyse-Detailbereich Trefferquote, Durchschnittsrendite und Fallzahl nach Asset-Typ, Marktphase und Zeithorizont.
- Mindestdatenlogik beibehalten: Gruppen unter 20 Fällen bleiben `Datenbasis zu klein`; 20 bis 50 Fälle liefern nur vorsichtige Hinweise; ab über 50 Fällen sind manuelle Kalibrierungsvorschläge erlaubt.
- README aktualisiert: Segment-Trefferquoten nach Asset-Typ, Marktphase und Zeithorizont dokumentiert.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Tests für Segment-Auswertung mit 20+ und kleiner Datenbasis erfolgreich.
- Nächste Priorität angepasst: längere Auswertungszeiträume für Forward-, Prognose-, Decision- und Trade-Tracking vorbereiten.
- Signalbasierte Kalibrierung umgesetzt: neue Historieneinträge speichern eine `signal_snapshot` für RSI, MACD, Volatilität, News, Makro und CRV; ältere Einträge bleiben kompatibel und zeigen fehlende Signalwerte als `Daten nicht verfügbar`.
- Ähnliche historische Setups werden zusätzlich nach Signalbestandteilen aufgeschlüsselt und zeigen je Signal Fallzahl, Trefferquote, Durchschnittsrendite und Kalibrierungsstatus ab den definierten Mindestfallzahlen.
- README aktualisiert: Lernsystem, Signal-Snapshots und Kalibrierungsregeln dokumentiert.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Tests für signalbasierte Kalibrierung mit 20+ und 50+ Fällen erfolgreich.
- Nächste Priorität angepasst: Trefferquoten und Signalwirkung nach Asset-Typ, Marktphase und Zeithorizont feiner auswerten.
- Technische Bereinigung im Confidence-/Lernmodul umgesetzt: doppelte Funktionsnamen für historische Auswertungen getrennt, damit die Ähnliche-Setup-Auswertung und die allgemeine Confidence-Historie jeweils die richtige Datenstruktur verwenden.
- ROADMAP-Bereinigung fortgeführt: Konfliktmarker und doppelte Änderungsprotokoll-Blöcke entfernt.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; Mock-Tests für Ähnliche-Setup-Trefferquote und historische Confidence-Auswertung erfolgreich.

### 2026-06-30

- Confidence-System erweitert: Die App zählt ähnliche historische Setups aus `trade_history.json`, `forward_tests.json`, `decision_history.json` und `prediction_history.json` nach Asset-Typ, Empfehlung/Aktionsfamilie, Marktphase, Kaufsignal-Bucket und Asset-Qualitäts-Bucket.
- Trefferquote und Durchschnittsrendite ähnlicher Setups werden erst ab mindestens 20 ähnlichen ausgewerteten Fällen angezeigt; darunter steht transparent `Datenbasis zu klein`.
- Die Auswertung nutzt nur tatsächlich gespeicherte Review-Ergebnisse und erfindet keine fehlenden Renditen.
- Gewichtungen werden weiterhin nicht automatisch geändert; die Ausgabe dient nur als Confidence- und Kalibrierungshinweis.
- Nächste Priorität angepasst: Kalibrierungsvorschläge aus den ähnlichen Setups feiner nach Signalbestandteilen ableiten.

### 2026-06-24

- Professionellere Kauf-/Nichtkauf-Entscheidung umgesetzt: Die App trennt Asset-Qualität, Zukunftspotenzial, Bewertung, eingepreiste Erwartungen, Blasenrisiko, technischen Einstieg und Expected Value, damit starke Qualitätsaktien nicht nur wegen unperfektem Timing pauschal abgelehnt werden.
- Bewertungsmodul für Aktien erweitert: KGV, Forward-KGV, PEG, KUV, EV/EBIT-Näherung, EV/FCF, Kurs/Buchwert, Free-Cashflow-Rendite, Wachstum, Margen, Verschuldung, historische Bewertung und Branchenvergleich werden berücksichtigt oder explizit als `Daten nicht verfügbar` angezeigt; KGV wird nicht isoliert verwendet.
- Neues Expected-Value-Modul ergänzt: Bull-/Base-/Bear-Case, Wahrscheinlichkeiten, erwartete Rendite, erwarteter Verlustbeitrag und Expected-Value-Score fließen in die Entscheidung ein.
- Ablehnungslogik erweitert: Vorsichtige oder negative Empfehlungen zeigen Hauptgrund und Nicht-Hauptgrund, z. B. ob es nicht an der Unternehmensqualität, sondern an Bewertung, Timing, CRV, Blasenrisiko, Makro oder Datenlage liegt.
- Forward-Testing vorbereitet: Empfehlungen werden lokal automatisch einmal pro Symbol, Empfehlung und Tag für spätere Auswertung gespeichert; es gibt weiterhin keine Broker-Anbindung und keine automatische Orderfunktion.

### 2026-06-14

- Repository für GitHub-Datenschutz vorbereitet: lokale Suchhistorie und Secrets werden ignoriert, Beispiel-Dateien ergänzt, README aktualisiert.
- Portablen Depot-Modus vorbereitet: `portfolio.json` auf GitHub-kompatibles Minimalformat standardisiert, sensible Felder ausgeschlossen und App-Leselogik für `ticker`/`shares`/`buy_price` ergänzt.
- ROADMAP um Forward-Testing, Decision-Tracking, Prognose-Tracking sowie Kalibrierungs- und Lernmodul erweitert.
- Dynamische Priorisierung eingeführt: ursprüngliche numerische Prioritäten bleiben Ausgangsbasis, neue tatsächliche Priorität wird nach Nutzen für Analysequalität, Stabilität und Lernfähigkeit abgeleitet.
- Prioritätslogik dokumentiert: PRIO A für Grundfähigkeit der Analyse, PRIO B für Messung der Analysequalität, PRIO C für Architektur und Wartbarkeit, PRIO D für Komfortfunktionen.
- ROADMAP um Opportunity Scanner, Trading-Modus, Trade Journal, Performance Tracking, Confidence-System, Signalanalyse und erweiterte Kalibrierungsvorschläge ergänzt.
- Priorisierung erweitert: Diese neuen Module gehören zu PRIO B und dürfen vor Komfortfunktionen bearbeitet werden, wenn sie Analysequalität messbar verbessern.
- Regel `Wachsende ROADMAP` ergänzt: Neu entdeckte sinnvolle Aufgaben werden aufgenommen, priorisiert und mit Nutzen, Abhängigkeiten sowie Begründung dokumentiert.
- Master-ROADMAP erstellt und aktuellen Projektstand analysiert.
- Projektziel, aktuelle Funktionen, offene Aufgaben, Prioritäten, Akzeptanzkriterien und Arbeitsmodus dokumentiert.
- Regel ergänzt: Bei `Arbeite weiter` wird ROADMAP gelesen, die höchste tatsächliche Priorität dynamisch bestimmt, bearbeitet, getestet und ROADMAP aktualisiert.
- Sicherheitsregel festgehalten: keine automatische Kauf- oder Verkaufsfunktion.
- Institutionelles Research-Modul umgesetzt: Analysten-Konsens, Earnings-Modul, Event-Risiko, institutionelle Daten, Vertrauensscore und Unsicherheitsfaktoren.
- Arbeitsmodus erweitert: Wenn kein Implementierungs-Prompt vorhanden ist, wird selbstständig geplant, umgesetzt, getestet und dokumentiert.
- Autonome Architekturpflege ergänzt: ROADMAP-Reihenfolge darf angepasst werden, wenn eine frühere strukturelle Änderung spätere Aufgaben besser lösbar macht.
- Projekt auf autonomen Langzeitbetrieb vorbereitet: GitHub-Synchronisation, Sicherheits-Commits, Rollback-Regeln, intelligente Priorisierung, Testmatrix und Schutz vor erfundenen Daten dokumentiert.

## Umsetzungsnotiz 2026-07-01

- Confidence-System erweitert: Die App sammelt ausgewertete lokale Fälle aus Trade Journal, Forward-Tests und Prognose-Tracking, gleicht sie nach Asset-Typ, Marktphase, Richtung und Kaufsignal-Bucket ab und zeigt Anzahl ähnlicher Setups sowie Trefferquote.
- Bei weniger als 20 ähnlichen Fällen wird transparent `Datenbasis zu klein` angezeigt; zwischen 20 und 50 Fällen nur ein vorsichtiger Hinweis; über 50 Fällen nur ein Hinweis auf mögliche manuelle Kalibrierung.
- Trading-Setups zeigen die Historien-Einordnung zusätzlich zur Chance und zum Confidence Score.
- Die Research-Vertrauensanalyse enthält die Historien-Einordnung als Detail, verändert aber keine Gewichtungen automatisch.

## Umsetzungsnotiz 2026-07-01 - Aktien-Fundamentaldaten

- Aktien-Fundamentaldaten erweitert: strukturierter Snapshot für Wachstum, Margen, Renditen, Cash, Verschuldung, Free Cashflow, operativen Cashflow, KGV, Forward-KGV, Kurs-Umsatz-Verhältnis, Kurs-Buchwert-Verhältnis, EV/EBITDA und Marktkapitalisierung.
- Asset-Qualität und Bewertungsscore nutzen die zusätzlichen Kennzahlen nur, wenn Yahoo Finance echte Werte liefert; fehlende Werte bleiben `Daten nicht verfügbar`.
- Nächste höchste offene Priorität ist ETF-Datenqualität und ETF-Strukturtransparenz.

## Umsetzungsnotiz 2026-07-01 - ETF-Daten

- ETF-Daten erweitert: strukturierter Snapshot für Kategorie, Fondsgesellschaft, TER/Kostenquote, Fondsvolumen, Holdings, YTD-, 1J-, 3J- und 5J-Performance sowie 3-Jahres-Beta.
- ETF-Qualität zeigt verfügbare Struktur- und Performance-Daten transparent; fehlende ETF-Spezialdaten bleiben `Daten nicht verfügbar`.
- Nächste höchste offene Priorität sind Bewertungsmodelle, relative Bewertung und Peer-Vergleich ohne erfundene Vergleichsdaten.
