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
- `portfolio.json`: Beispiel- und Nutzportfolio für den optionalen Portfolio-Modus.
- `search_history.json`: lokal gespeicherte erfolgreiche Suchanfragen.
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

- Haupt-Dashboard und Research-Modul vereinheitlichen, damit Empfehlungen nicht doppelt oder widersprüchlich wirken.
- Sichtbare Empfehlung klar trennen in Asset-Qualität, Kaufsignal, Research-Handlungsempfehlung und Depot-Effekt.
- Fehlerbehandlung bei Yahoo-Finance-Ausfällen verbessern.
- Datenqualitäts-Check kompakter und sichtbarer machen.
- Suchhistorie in der Sidebar als auswählbare Schnellwahl nutzbar machen.
- Umlaute und sichtbare deutsche Texte prüfen.
- App-Start und Analysefluss regelmäßig testen.

### Priorität 2: Score-Qualität

- Gewichtungen der Scores transparent dokumentieren.
- Score-Logik kalibrieren.
- Asset-Qualität je Asset-Typ verbessern.
- Kaufsignal weiter von Asset-Qualität abgrenzen.
- Research-Scores stärker erklären: Was bedeutet hoch, mittel oder niedrig?
- Nachkaufzonen robuster machen, wenn keine klaren Kurszonen erkannt werden.
- Bull/Base/Bear-Szenarien stärker aus Trend, Volatilität, Unterstützungen und Widerständen ableiten.

### Priorität 3: Profi-Research

- Fundamentaldaten für Aktien erweitern: Umsatzwachstum, Gewinnwachstum, Margen, Verschuldung, Free Cashflow, Cashbestand, Bewertung.
- ETF-Daten erweitern: TER, Fondsvolumen, Region, Sektor, Diversifikation, langfristige Performance.
- Bewertungsmodelle ausbauen: historische Bewertung, relative Bewertung und Peer-Vergleich, falls Daten verfügbar sind.
- Analysten-, Earnings-, Event- und institutionelle Module weiter validieren und auf zusätzliche Datenquellen erweitern.
- News-Modul verbessern: Quelle, Datum, Relevanz, Sentiment-Qualität.
- Makro-Modul erweitern: Inflation, Realzinsen, Liquidität, Risikoappetit.
- Geopolitik-Modul prüfen, ohne Daten zu erfinden.
- Risiko- und Liquiditätsmodul verfeinern.

### Priorität 4: Krypto-Modul

- Bitcoin-Halving-Zyklus integrieren.
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

## Prioritäten

Aktuelle höchste offene Priorität:

1. Dashboard und Research-Empfehlung vereinheitlichen.

Warum diese Aufgabe zuerst:

- Die App hat bereits viele Analysebausteine.
- Der größte Nutzwert entsteht jetzt durch eine klarere, weniger widersprüchliche Darstellung.
- Anfänger sollen sofort verstehen, was langfristige Qualität, aktuelles Kaufsignal und Depot-Effekt bedeuten.

Nächste konkrete Umsetzung:

1. `app.py` lesen und alle sichtbaren Empfehlungsbereiche identifizieren.
2. Prüfen, ob `final_recommendation_v2`, `research_pack.action`, `buy_signal` und `portfolio_result` doppelte oder widersprüchliche Aussagen erzeugen.
3. Eine zentrale Anzeige bauen:
   - Primäre Entscheidung: Kaufsignal / Research-Handlungsempfehlung.
   - Langfristiger Kontext: Asset-Qualität.
   - Separater Kontext: Depot-Effekt nur bei aktivem Portfolio-Modus.
4. Anfänger-Erklärung entsprechend anpassen.
5. README aktualisieren, wenn sich die Bedienung ändert.
6. App testen.
7. ROADMAP aktualisieren.

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

Akzeptanzkriterien für Portfolio-Modus:

- Portfolio-Modus AUS: keine Depotdaten, keine Klumpenrisiko-Warnung, keine Cash-Bewertung.
- Portfolio-Modus AN: Depot-Effekt wird zusätzlich angezeigt.
- Depot-Effekt verändert Asset-Qualität und Kaufsignal nicht.

## Arbeitsmodus

Wenn der Nutzer später schreibt:

- `Arbeite weiter`
- `Weiter`
- `Setze die Entwicklung fort`
- `Arbeite bis zum Limit`

dann soll automatisch folgender Arbeitsmodus gelten:

1. `ROADMAP.md` lesen.
2. Die höchste offene Priorität auswählen.
3. Die ausgewählte Aufgabe implementieren.
4. Die App testen.
5. Fehler beheben.
6. `README.md` aktualisieren, wenn sich Bedienung, Funktionen oder Struktur ändern.
7. `ROADMAP.md` aktualisieren.
8. `git status` prüfen und geänderte Dateien identifizieren.
9. Einen Commit mit automatisch erzeugter, kurzer Commit-Nachricht erstellen.
10. `git push` ausführen.
11. Wenn Push fehlschlägt: Fehler dokumentieren, Nutzer informieren und Änderungen lokal behalten.
12. Danach die nächste offene Aufgabe bearbeiten.
13. Wiederholen, bis keine offene Aufgabe mehr sinnvoll bearbeitbar ist oder kein Arbeitsbudget mehr vorhanden ist.

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

## Intelligente Priorisierung

Wenn mehrere Aufgaben offen sind, gilt diese Priorität:

1. Fehler und Abstürze
2. Datenqualität
3. Analysequalität
4. Stabilität
5. Performance
6. Komfortfunktionen

Komfortfunktionen dürfen nicht vor Analysequalität bearbeitet werden, außer sie sind notwendig, um Analysefehler sichtbar oder testbar zu machen.

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

### 2026-06-14

- Master-ROADMAP erstellt und aktuellen Projektstand analysiert.
- Projektziel, aktuelle Funktionen, offene Aufgaben, Prioritäten, Akzeptanzkriterien und Arbeitsmodus dokumentiert.
- Regel ergänzt: Bei `Arbeite weiter` wird ROADMAP gelesen, die höchste offene Priorität bearbeitet, getestet und ROADMAP aktualisiert.
- Sicherheitsregel festgehalten: keine automatische Kauf- oder Verkaufsfunktion.
- Institutionelles Research-Modul umgesetzt: Analysten-Konsens, Earnings-Modul, Event-Risiko, institutionelle Daten, Vertrauensscore und Unsicherheitsfaktoren.
- Arbeitsmodus erweitert: Wenn kein Implementierungs-Prompt vorhanden ist, wird selbstständig geplant, umgesetzt, getestet und dokumentiert.
- Autonome Architekturpflege ergänzt: ROADMAP-Reihenfolge darf angepasst werden, wenn eine frühere strukturelle Änderung spätere Aufgaben besser lösbar macht.
- Projekt auf autonomen Langzeitbetrieb vorbereitet: GitHub-Synchronisation, Sicherheits-Commits, Rollback-Regeln, intelligente Priorisierung, Testmatrix und Schutz vor erfundenen Daten dokumentiert.
