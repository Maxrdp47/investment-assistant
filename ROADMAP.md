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

- Fundamentaldaten für Aktien erweitern: Umsatzwachstum, Gewinnwachstum, Margen, Verschuldung, Free Cashflow, Cashbestand, Bewertung.
- ETF-Daten erweitern: TER, Fondsvolumen, Region, Sektor, Diversifikation, langfristige Performance.
- Bewertungsmodelle ausbauen: historische Bewertung, relative Bewertung und Peer-Vergleich, falls Daten verfügbar sind.
- Analysten-, Earnings-, Event- und institutionelle Module weiter validieren und auf zusätzliche Datenquellen erweitern.
- News-Modul verbessern: Quelle, Datum, Relevanz, Sentiment-Qualität.
- Makro-Modul erweitern: Inflation, Realzinsen, Liquidität, Risikoappetit.
- Geopolitik-Modul prüfen, ohne Daten zu erfinden.
- Risiko- und Liquiditätsmodul verfeinern.

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

- Bitcoin-Halving-Zyklus integrieren. Status: Basis umgesetzt am 2026-06-15.
- Fear & Greed Index prüfen und integrieren, falls zuverlässig verfügbar.
- ETF-Flows integrieren, falls eine belastbare Datenquelle verfügbar ist.
- On-Chain-Daten integrieren, falls verfügbar.
- Krypto-Liquidität und Marktstruktur besser erklären.
- Bei fehlenden Krypto-Daten immer `Daten nicht verfügbar` anzeigen.

### Priorität 5: Backtesting

- Backtesting-Modul planen.
- Historische Signale speichern.
- Trefferquoten berechnen.
- Renditeanalyse durchführen.
- Drawdown-Analyse ergänzen.
- Verschiedene Signal-Kombinationen vergleichen.

### Priorität 6: Prognose-Tracking

- Prognosen speichern.
- Szenarien und Kursziele später mit echten Ergebnissen vergleichen.
- Trefferquote je Asset und Modul ausweisen.
- Grundlage für ein späteres Lernsystem vorbereiten.

### PRIO B: Forward-Testing-Modul

- Jede neue Analyse optional als Forward-Test speichern.
  - Status: Basis umgesetzt am 2026-06-15 (`forward_tests.json`, lokal und nicht versioniert).
- Startzeitpunkt, Asset, Ticker, Asset-Typ, Marktphase, Kaufsignal, Asset-Qualität, Depot-Effekt, Vertrauensscore und relevante Modul-Scores erfassen.
- Bull/Base/Bear-Szenarien, Kursziele, Wahrscheinlichkeiten und entscheidende Marken speichern.
- Nach festgelegten Zeiträumen prüfen: 1 Woche, 1 Monat, 3 Monate, 6 Monate und 12 Monate.
  - Status: Basis umgesetzt am 2026-06-15 für 1 Woche, 1 Monat und 3 Monate.
- Tatsächliche Kursentwicklung, maximalen Drawdown, maximale positive Bewegung und Treffer der Szenarien auswerten.
- Keine Performance-Werte erfinden, wenn Kursdaten fehlen.
- Ergebnisse getrennt nach Asset-Typ, Marktphase und Signalart ausweisen.

### PRIO B: Decision-Tracking-Modul

- Nutzerentscheidungen optional protokollieren: gekauft, nicht gekauft, gehalten, verkauft, beobachtet.
  - Status: Basis umgesetzt am 2026-06-15 (`decision_history.json`, lokal und nicht versioniert).
- Zeitpunkt, Entscheidungsgrund, angezeigte Empfehlung und relevante Scores speichern.
- Optionalen Nutzerkommentar ermöglichen.
- Später vergleichen, ob die Entscheidung gegen oder mit der App-Einschätzung getroffen wurde.
- Keine Broker-Anbindung und keine automatische Ausführung.
- Daten lokal und transparent speichern.

### PRIO B: Prognose-Tracking-Modul

- Prognosen aus Bull/Base/Bear-Szenarien dauerhaft speichern.
  - Status: Basis umgesetzt am 2026-06-15 (`prediction_history.json`, lokal und nicht versioniert).
- Kursziele, Wahrscheinlichkeiten, Zeithorizont und entscheidende Widerlegungsmarken erfassen.
- Später prüfen, welches Szenario am besten getroffen hat.
  - Status: Basis umgesetzt am 2026-06-15 für 1 Woche, 1 Monat und 3 Monate.
- Trefferquote je Modul, Signalart, Asset-Typ und Marktphase berechnen.
- Fehlprognosen sichtbar machen und Ursachen kategorisieren.
- Nur echte nachträgliche Kursdaten verwenden; fehlende Daten als `Daten nicht verfügbar` kennzeichnen.

### PRIO B: Kalibrierungs- und Lernmodul

- Aus Forward-Testing, Decision-Tracking und Prognose-Tracking lernen, welche Signale zuverlässig sind.
- Score-Gewichtungen nicht automatisch ändern, sondern Anpassungsvorschläge erzeugen.
- Häufige Fehlerquellen erkennen, z. B. schwache Marktphasen-Erkennung, schlechte Krypto-Bewertung, unbrauchbare News-Signale oder übergewichtete technische Signale.
- Kalibrierungsbericht anzeigen: Was funktioniert gut? Was funktioniert schlecht? Welche Module brauchen Verbesserung?
  - Status: Basis umgesetzt am 2026-06-15: lokaler Kalibrierungsstatus zählt Forward-Tests, Entscheidungen, Prognosen und ausgewertete Zeiträume.
- Lernlogik transparent machen und keine Blackbox-Entscheidungen treffen.
- Änderungen an Bewertungslogik erst nach Dokumentation und Tests übernehmen.

### PRIO B: Opportunity Scanner

Ziel: Die App soll langfristig nicht nur einzelne Assets analysieren, sondern regelmäßig verfügbare Aktien, ETFs und Kryptowährungen durchsuchen und die attraktivsten Chancen identifizieren.

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

### PRIO B: Trade Journal

Jeder vorgeschlagene Trade wird automatisch dokumentiert, aber niemals automatisch ausgeführt.

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

Optional später:

- nach 6 Monaten
- nach 12 Monaten

Bewerten:

- Treffer oder Fehlschlag
- maximale positive Entwicklung
- maximale negative Entwicklung
- Ziel erreicht?
- Stop erreicht?
- beste Alternative?

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

### PRIO B: Confidence-System

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

### PRIO B: Kalibrierungsvorschläge

Der Bot darf Vorschläge machen, aber Gewichtungen in Version 1 nicht automatisch ändern.

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

1. Trading-Modus beginnen: aus Scanner-Kandidaten ein konkretes Setup mit Zielzone, Stop-Zone, CRV, Chance, Confidence und Risiken ableiten.

Warum diese Aufgabe zuerst:

- Die zentralen PRIO-A-Aufgaben aus Score-Qualität und Szenarien sind umgesetzt.
- Signalanalyse und Opportunity Scanner sind als Basis umgesetzt.
- Der nächste größte Nutzen liegt im Trading-Modus, weil Scanner-Kandidaten dadurch in prüfbare Setups mit Ziel, Stop und Zeithorizont überführt werden können.
- Diese Aufgabe ist PRIO B, weil sie spätere Performance-Messung, Trade Journal und Lernsystem vorbereitet.

Nächste konkrete Umsetzung:

1. Scanner-Ergebnisse in ein Setup-Format überführen.
2. Zielzone und Stop-Zone aus Widerständen, Unterstützungen und Volatilität ableiten.
3. Chance, Confidence, CRV, wichtigste Risiken und wichtigste Chancen anzeigen.
4. Keine automatische Orderfunktion einbauen.
5. Tests ausführen und ROADMAP aktualisieren.

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
