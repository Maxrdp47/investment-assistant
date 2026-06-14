# Projektstatus

Der Investment-Assistent ist eine lokale Streamlit-App zur Analyse von Aktien, ETFs und Kryptowährungen über Yahoo Finance. Die App lädt Kursdaten, erkennt Asset-Typen, berechnet technische Indikatoren, zeigt Research-Scores, Szenarien, Nachkaufzonen und Anfänger-Erklärungen an. Portfolio-Daten können optional über `portfolio.json` einbezogen werden, bleiben aber als separater Depot-Effekt von Asset-Qualität und Kaufsignal getrennt.

Die App handelt nicht automatisch, hat keine Broker-Anbindung und darf keine Kauf- oder Verkaufsautomatisierung erhalten. Sie ist nur eine Analyse- und Entscheidungshilfe; die finale Entscheidung trifft immer der Nutzer.

Vorhandene Dateien:

- `app.py`: Hauptanwendung mit Streamlit-Oberfläche, Analysefunktionen, Research-Modul und Portfolio-Modus.
- `README.md`: Startanleitung und Erklärung der wichtigsten Funktionen.
- `requirements.txt`: Python-Abhängigkeiten.
- `portfolio.json`: Beispiel- und Nutzportfolio für den optionalen Portfolio-Modus.
- `search_history.json`: lokal gespeicherte erfolgreiche Suchanfragen.
- `start_investment_assistent.bat`: Startskript für Desktop-Verknüpfung.
- `.streamlit/`: Streamlit-Konfiguration.
- `.yfinance-cache/`: lokaler yfinance-Cache.
- `.venv/`: lokale Python-Umgebung.

# Erledigte Aufgaben

- Lokale Streamlit-App erstellt.
- Yahoo-Finance-Kursdaten über `yfinance` integriert.
- Zeitraum- und Intervallauswahl eingebaut.
- Asset-Suche für Namen und Ticker verbessert.
- Bekannte Ticker-Fallbacks für Beispiele wie Xiaomi, Nvidia, Palantir, Bitcoin und MSCI World ergänzt.
- Zuletzt erfolgreiche Suchanfragen werden lokal gespeichert.
- Asset-Typ-Erkennung für Aktie, ETF, Krypto und unbekannt eingebaut.
- Manuelle Asset-Typ-Auswahl eingebaut.
- Währungsmanagement mit EUR-Anzeige und Originalwährung ergänzt.
- Anzeige von Firmenname, Ticker, Börse, Originalwährung und Wechselkurs ergänzt.
- Technische Indikatoren berechnet: RSI 14, MACD, Signal-Linie, 50er/200er Durchschnitt, Volumenentwicklung, Volatilität.
- Unterstützungen und Widerstände über lokale Tiefs/Hochs berechnet.
- CRV, Risiko bis Unterstützung und Potenzial bis Widerstand berechnet.
- Marktphasen-Erkennung eingebaut: Bullenmarkt, Bärenmarkt, Korrektur, Bodenbildung, Seitwärtsmarkt.
- Wahrscheinlichkeiten für Szenarien ergänzt.
- Asset-Qualität, Kaufsignal und Depot-Effekt getrennt.
- Portfolio-Modus per Toggle eingebaut.
- Depot-Effekt berücksichtigt Cash, Positionsgröße, Klumpenrisiko, geplanten Nachkauf und Cash-Reserve.
- Anfänger-Modus mit einfachen Erklärungen eingebaut.
- Research-Modul mit Datenqualitäts-Check, Modul-Scores, Bull/Base/Bear-Szenarien, Nachkaufzonen und Research-Fazit eingebaut.
- News-Modul über Yahoo-Finance-News mit einfachem Sentiment-Score eingebaut.
- Makro-Modul mit Nasdaq, US-Zinsen, Dollar-Index und TIP-Proxy eingebaut.
- README mit Start, Portfolio-Modus, Scores, Suche, Währungsanzeige und Research-Modul aktualisiert.
- Desktop-Start über Batch-Datei vorbereitet.

# Offene Aufgaben

Priorität 1:

- Research-Modul weiter validieren und Duplikate zwischen alter Empfehlung, Kaufsignal und Research-Handlungsempfehlung reduzieren.
- Einheitliche deutsche Umlaute in allen sichtbaren Texten prüfen.
- Fehlerbehandlung bei Yahoo-Finance-Ausfällen verbessern.
- Datenqualitäts-Check sichtbarer und kompakter machen.
- Suchverlauf in der Sidebar besser nutzbar machen, z. B. als klickbare Auswahl statt nur Anzeige.

Priorität 2:

- Score-Logik weiter kalibrieren und Gewichtungen dokumentieren.
- Asset-Qualität pro Asset-Typ verbessern.
- Kaufsignal weiter von langfristiger Asset-Qualität trennen und UI noch klarer machen.
- Research-Scores stärker erklären: Was bedeutet hoch/niedrig konkret?
- Nachkaufzonen robuster machen, wenn keine Unterstützung oder kein Widerstand erkannt wird.
- Bull/Base/Bear-Szenarien besser aus Kurszonen, Volatilität und Trend ableiten.

Priorität 3:

- Fundamentaldaten für Aktien erweitern: Margen, Verschuldungsgrad, Free-Cashflow-Trend, Umsatz-/Gewinnwachstum.
- ETF-Daten verbessern: TER, Fondsvolumen, Index/Region/Sektor, Diversifikation, 1J/3J/5J-Performance.
- Bewertungsmodelle ausbauen: relative Bewertung, historische Bewertung, Peer-Vergleich sofern Daten verfügbar.
- News-Modul robuster machen: Quellen, Datum, Relevanz, Sentiment-Qualität.
- Makro-Modul erweitern: Inflation, Realzinsen, Liquidität, Risikoappetit.
- Geopolitik-Modul prüfen, aber keine Daten erfinden.
- Risiko- und Liquiditätsmodule verfeinern.

Priorität 4:

- Krypto-Modul erweitern.
- Bitcoin-Halving-Zyklus einbauen.
- Fear & Greed Index integrieren, falls ohne API-Hürden verfügbar.
- ETF-Flows integrieren, falls zuverlässige Datenquelle verfügbar ist.
- On-Chain-Daten integrieren, falls verfügbar.
- Krypto-Liquidität und Marktstruktur besser erklären.
- Fehlende Krypto-Spezialdaten weiterhin ausdrücklich als `Daten nicht verfügbar` anzeigen.

Priorität 5:

- Backtesting-Modul planen.
- Historische Signale speichern und auswerten.
- Trefferquoten berechnen.
- Renditeanalyse durchführen.
- Drawdown-Analyse ergänzen.
- Verschiedene Signal-Kombinationen vergleichen.

Priorität 6:

- Prognose-Tracking vorbereiten.
- Ausgegebene Szenarien und Kursziele speichern.
- Spätere Ergebnisse mit Prognosen vergleichen.
- Trefferquote je Asset und Modul ausweisen.
- Grundlage für ein späteres Lernsystem vorbereiten.

# Aktuelle Priorität

Nächste Aufgabe: Research-Modul und Haupt-Dashboard vereinheitlichen.

Ziel: Die App soll oben eine klare, nicht widersprüchliche Empfehlung zeigen. Asset-Qualität, Kaufsignal, Research-Handlungsempfehlung und Depot-Effekt sollen sichtbar getrennt bleiben, aber nicht doppelt oder verwirrend wirken.

Konkrete nächste Schritte:

1. `app.py` lesen und alle sichtbaren Empfehlungsbereiche identifizieren.
2. Prüfen, ob `final_recommendation_v2` und `research_pack.action` widersprüchliche Aussagen erzeugen.
3. Eine einheitliche Anzeige bauen, die Research-Handlungsempfehlung, Kaufsignal und Depot-Effekt klar trennt.
4. Anfänger-Erklärung anpassen.
5. App per Syntaxcheck und Streamlit-Starttest testen.
6. README und ROADMAP aktualisieren.

# Arbeitsmodus

Wenn der Nutzer später schreibt:

- `Arbeite weiter`
- `Weiter`
- `Setze die Entwicklung fort`
- `Arbeite bis zum Limit`

dann soll automatisch folgender Arbeitsmodus gelten:

1. `ROADMAP.md` lesen.
2. Die wichtigste offene Aufgabe auswählen.
3. Diese Aufgabe umsetzen.
4. Die App testen.
5. Fehler beheben.
6. `README.md` aktualisieren, wenn sich Bedienung, Funktionen oder Struktur ändern.
7. `ROADMAP.md` aktualisieren.
8. Danach mit der nächsten offenen Aufgabe weitermachen, bis gestoppt werden muss.

Gestoppt wird nur, wenn:

- keine sinnvollen offenen Aufgaben mehr vorhanden sind,
- ein technischer Blocker auftritt,
- Nutzungs-/Arbeitslimit erreicht wird,
- oder der Nutzer ausdrücklich stoppt oder eine andere Aufgabe stellt.

Während dieses Arbeitsmodus gilt immer:

- Die bestehende App nicht unnötig neu bauen.
- Keine vorhandenen Funktionen entfernen.
- Keine automatische Kauf- oder Verkaufsfunktion einbauen.
- Keine Broker-Anbindung einbauen.
- Keine Daten erfinden.
- Portfolio-Daten dürfen Asset-Qualität und Kaufsignal niemals beeinflussen.
- Depot-Effekt bleibt separat.
- Änderungen nach Möglichkeit testen.

# Abschlussbericht

Nach jeder Arbeitseinheit soll kurz ausgegeben werden:

- Was wurde erledigt?
- Welche Dateien wurden geändert?
- Wurde getestet?
- Was ist die nächste Aufgabe?

# Bekannte Probleme

- Yahoo-Finance-Daten können verzögert, unvollständig oder zeitweise nicht verfügbar sein.
- Manche Fundamentaldaten, ETF-Spezialdaten, Krypto-On-Chain-Daten und News-Daten sind nicht zuverlässig über `yfinance` verfügbar.
- Einige Research-Scores sind heuristisch und müssen weiter kalibriert werden.
- Es gibt mehrere Empfehlungsbereiche, die weiter vereinheitlicht werden sollten.
- Die Sidebar-Suchhistorie ist aktuell nur Anzeige, keine direkte Wiederverwendung.
- Backtesting und Prognose-Tracking fehlen noch.

# Änderungsprotokoll

## 2026-06-14

- `ROADMAP.md` erstellt.
- Projektstand analysiert.
- Erledigte Funktionen und offene Aufgaben dokumentiert.
- Autonomen Arbeitsmodus für zukünftige Befehle wie `Arbeite weiter` dokumentiert.
