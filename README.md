# Investment-Assistent

Lokale Streamlit-App zur Analyse von Aktien, ETFs und Kryptowährungen über Yahoo Finance.

Die App handelt nicht automatisch, hat keine Broker-Anbindung und gibt keine Finanzberatung. Sie ist eine technische Analysehilfe; die letzte Entscheidung trifft immer der Nutzer.

## Funktionen

- Asset-Name oder Yahoo-Finance-Ticker eingeben
- automatische Yahoo-Finance-Suche mit auswählbaren Treffern für Firmennamen, ETFs und Kryptowährungen
- Speicherung der zuletzt erfolgreichen Suchanfragen in `search_history.json`
- Schnellwahl der letzten erfolgreichen Suchen in der Sidebar
- Währungsmanagement: Anzeige standardmäßig in EUR plus Originalwährung
- automatische Asset-Typ-Erkennung: Aktie, ETF, Krypto oder unbekannt
- manuelle Asset-Typ-Auswahl, falls die automatische Erkennung unsicher ist
- getrennte Bewertung von Asset-Qualität, Kaufsignal und Depot-Effekt
- zentrale Empfehlungsbox mit Kaufsignal, Research-Einordnung, Asset-Qualität, Depot-Effekt und Vertrauensscore
- klare Warnungen bei eingeschränkten Yahoo-Finance-Datenquellen wie Stammdaten, Wechselkursen, News oder Makro-Proxies
- technische Analyse mit RSI, MACD, Trend, Volumen, Volatilität, Unterstützungen, Widerständen und CRV
- professionelle Research-Ansicht mit Datenqualitäts-Ampel, Modul-Scores, Szenarien, Nachkaufzonen und Fazit
- Marktphase und Szenario-Wahrscheinlichkeiten
- Anfänger-Modus mit einfachen Erklärungen
- optionaler Portfolio-Modus mit `portfolio.json`

## Start

Per Desktop-Symbol **Investment-Assistent** oder manuell:

```powershell
cd C:\investment-assistent
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Smoke-Test

Für eine schnelle technische Prüfung:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

Der Test kompiliert `app.py`, startet Streamlit kurz auf einem freien lokalen Port und prüft den Analysefluss mit `BTC-EUR`, `NVDA` und `1810.HK`. Ohne Live-Daten:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py --skip-live-data
```

## Asset-Suche

Du kannst entweder einen Namen oder direkt einen Yahoo-Finance-Ticker eingeben.

Beispiele für Namen:

- Xiaomi
- Nvidia
- Palantir
- Bitcoin
- MSCI World

Beispiele für Ticker:

- `NVDA`
- `PLTR`
- `BTC-EUR`
- `1810.HK`
- `EUNL.DE`

Die App sucht passende Yahoo-Finance-Treffer und zeigt Name, Ticker und Börse an. Wenn kein Treffer gefunden wird, kannst du weiterhin manuell einen Ticker eintragen. Erfolgreiche Suchen werden lokal in `search_history.json` gespeichert.

## Währungsanzeige

Die Analyse rechnet intern weiter mit den Originalkursen von Yahoo Finance. Dadurch bleiben RSI, MACD, Unterstützungen, Widerstände und CRV unverzerrt.

Für die Anzeige werden Kurse, Unterstützungen, Widerstände und der Hauptchart standardmäßig in EUR angezeigt. Wenn ein Asset in USD, HKD oder einer anderen Währung gehandelt wird, zeigt die App zusätzlich die Originalwährung und den verwendeten Wechselkurs.

In der Sidebar kannst du wählen:

- `EUR + Originalwährung`
- `Nur EUR`

Wenn kein Wechselkurs geladen werden kann, zeigt die App ehrlich an, dass die EUR-Umrechnung nicht verfügbar ist.

## Research-Modul

Das Research-Modul ist wie eine kompakte Equity-Research-Ansicht aufgebaut. Es verändert nicht automatisch Depotdaten, Asset-Qualität oder Kaufsignal, sondern zeigt zusätzliche Analyseblöcke.

Enthalten sind:

- Datenqualitäts-Check: Ticker, Asset-Typ, Börse, Währung, Kursdaten, Volumen, 200 Handelstage sowie 50er/200er-Durchschnitt
- Charttechnik-Score
- Momentum-Score
- Bewertungsscore oder bei Krypto Zyklus-/On-Chain-Score
- Fundamentaldaten-Score oder bei Krypto Netzwerk-/Adoptionsscore
- Innovation / Hype: Hinweise auf Wachstum, Margen, Cashflow, Marktstellung, Technologiebezug und Hype-Risiko
- Blasenrisiko: Bewertung, Momentum, 3M-Kursanstieg, Volatilität und News-Sentiment; hoher Wert ist ein Warnsignal
- Makro-Score
- Marktregime mit Hinweisen, Gegenargumenten, Unsicherheiten, betroffenen Asset-Klassen und Vertrauensgrad
- Makro-Wirkung: Zinsen, Dollar, Risikoappetit und Inflations-/Realzinsproxy mit praktischer Wirkung auf Aktien, ETFs, Krypto und Rohstoffe
- Rohstoff-Kontext: Öl, Gas, Kupfer, Gold und Uran-Proxy als Konjunktur-, Inflations-, Sicherheits- und Energiesignale, sofern Yahoo-Daten verfügbar sind
- Krypto-Zyklus: nur bei Krypto-Assets, mit Bitcoin-Halving-Einordnung, Krypto-Volatilität und Liquidität; ETF-Flows, Fear & Greed und On-Chain-Daten bleiben `Daten nicht verfügbar`, wenn keine belastbare Quelle eingebunden ist
- News-Score
- Risiko-Score
- Liquiditäts-Score
- Bull-/Base-/Bear-Szenarien mit Wahrscheinlichkeiten, die zusammen 100 % ergeben; Trend, Volatilität, Unterstützungen, Widerstände und CRV werden als Treiber ausgewiesen
- Nachkaufzonen: aggressiv, fair, sicher und ungültig bei Bruch der Unterstützung; fehlende Unterstützungen oder Widerstände werden als nicht berechenbar angezeigt
- Research-Fazit: was für Kauf spricht, was dagegen spricht, was die Analyse verbessern würde, welche Marke entscheidend ist und ein konkreter Plan
- Analysten-Konsens, sofern Yahoo-Finance-Daten verfügbar sind
- Earnings-Modul für Aktien, sofern Quartalsdaten verfügbar sind
- Event-Risiko-Modul für bekannte oder verfügbare Ereignisdaten
- Institutionelle Daten wie Beteiligungen und Short Interest, sofern verfügbar
- Vertrauensscore zur Einschätzung, wie belastbar die Analyse aktuell ist
- Unsicherheitsfaktoren: Was könnte diese Analyse widerlegen?

Wenn Daten fehlen, zeigt die App **Daten nicht verfügbar** oder **Datenqualität eingeschränkt**. Fehlende Kennzahlen werden nicht erfunden.

## Geplante Qualitätsmessung

Die ROADMAP sieht zusätzliche Module vor, die nicht nur neue Features liefern sollen, sondern die Analysequalität messbar machen:

- Opportunity Scanner: Die App soll regelmäßig Aktien, ETFs und Kryptowährungen durchsuchen und die besten Long- und Short-Chancen mit Opportunity Score, Vertrauensscore und Begründung anzeigen.
- Trading-Modus: Es werden nur Kandidaten aus dem Opportunity Scanner analysiert. Für jedes Setup werden Richtung, Chance, Confidence, Zielzone, Stop-Zone, Zeithorizont, CRV, Risiken und Chancen angezeigt.
- Trade Journal: Vorgeschlagene Trades sollen in `trade_history.json` dokumentiert werden, ohne eine Order auszuführen.
- Performance Tracking: Vorgeschlagene Trades sollen nach 1 Woche, 1 Monat und 3 Monaten mit echten Kursdaten überprüft werden.
- Forward-Testing: Eine angezeigte Analyse kann optional lokal in `forward_tests.json` gespeichert werden. Fällige Tests können in der Sidebar ausgewertet werden; gespeichert werden Rendite, maximale positive und negative Entwicklung. Die Datei wird nicht versioniert und löst niemals eine Order aus.
- Decision-Tracking: Nutzerentscheidungen wie gekauft, gehalten, verkauft oder beobachtet können optional protokolliert werden.
- Prognose-Tracking: Bull/Base/Bear-Szenarien, Kursziele und Wahrscheinlichkeiten werden später mit realen Ergebnissen verglichen.
- Confidence-System: Chancen sollen zusätzlich mit ähnlichen historischen Fällen und Trefferquoten eingeordnet werden.
- Kalibrierungs- und Lernmodul: Häufige Fehlprognosen sollen zeigen, welche Module verbessert werden müssen.

Diese Module dürfen keine Käufe oder Verkäufe ausführen. Sie dienen nur dazu, Chancen zu finden, Vorschläge zu dokumentieren, Trefferquoten zu messen, Fehlerquellen zu erkennen und Verbesserungsbedarf transparent zu machen.

Für das Lernsystem gilt:

- Unter 20 Fällen wird die Datenbasis als zu klein angezeigt.
- Zwischen 20 und 50 Fällen sind nur vorsichtige Hinweise erlaubt.
- Ab über 50 Fällen dürfen Kalibrierungsvorschläge angezeigt werden.
- Gewichtungen werden in Version 1 nicht automatisch geändert.
- Jeder Vorschlag muss Datenbasis, Anzahl Fälle, Trefferquote und Begründung nennen.

## Dynamische Entwicklungsprioritäten

Wenn später `Arbeite weiter` geschrieben wird, soll nicht starr die erste Aufgabe aus der ROADMAP bearbeitet werden. Stattdessen wird bewertet, welche offene Aufgabe den größten Nutzen für Analysequalität, Stabilität und Lernfähigkeit hat.

Priorität haben:

- PRIO A: Grundfähigkeit der Analyse, z. B. Datenqualität, Fehlerbehandlung, Bewertungslogik, Marktphasen, Wahrscheinlichkeiten, Fundamentaldaten, Krypto, Makro, News und Risikoanalyse
- PRIO B: Messung der Analysequalität, z. B. Opportunity Scanner, Trading-Modus, Trade Journal, Performance Tracking, Forward-Testing, Decision-Tracking, Prognose-Tracking, Confidence-System, Trefferquote, Kalibrierung und Lernmodul
- PRIO C: Architektur und Wartbarkeit, z. B. Refactoring, Modularisierung, Performance, Dokumentation und Testbarkeit
- PRIO D: Komfortfunktionen, z. B. Favoriten, Watchlists, Exporte oder reine UI-Verschönerungen

Komfortfunktionen dürfen nicht vor Analysequalität bearbeitet werden. Wenn Prioritäten geändert werden, muss die Begründung in `ROADMAP.md` dokumentiert werden.

## Die drei Scores

### Asset-Qualität

Bewertet nur die langfristige Qualität des Assets.

- Bei Aktien: Umsatz, Gewinn, Free Cashflow, Verschuldung, Margen, Kapitalrendite, Bewertung, Kurs-Umsatz-Verhältnis und Marktstellung, soweit verfügbar
- Bei ETFs: Diversifikation, TER/Kostenquote, Fondsvolumen, Region/Sektor, Performance und langfristige Stabilität aus realer Volatilität, soweit verfügbar
- Bei Krypto: Marktstellung, Liquidität, Volatilität und verfügbare Langfristdaten

Wenn Daten fehlen, zeigt die App **Daten nicht verfügbar** und erfindet keine Werte.

### Kaufsignal

Bewertet nur, ob **jetzt** ein guter Einstiegszeitpunkt sein könnte.

Einflussfaktoren:

- Marktphase
- Trend
- RSI
- MACD
- Volumen
- Unterstützungen
- Widerstände
- Chancen-Risiko-Verhältnis
- Volatilität

Portfolio-Daten verändern das Kaufsignal nicht. Asset-Qualität verändert das Kaufsignal ebenfalls nicht. Das Kaufsignal bewertet nur den aktuellen Einstiegszeitpunkt; MACD und Volatilität werden dabei je nach Asset-Typ eingeordnet, weil ein ETF, eine Aktie und Krypto unterschiedliche Schwankungsprofile haben.

### Gewichtungen

Die App zeigt die Gewichtungen im Bereich **Analyse-Details anzeigen**. Je nach Asset-Typ werden die Research-Bausteine unterschiedlich gewichtet:

- Aktie: Technik 30 %, Fundamentaldaten 30 %, Makro 20 %, News 10 %, CRV 10 %
- ETF: Technik 25 %, Fundamentaldaten 25 %, Makro 25 %, News 10 %, CRV 15 %
- Krypto: Technik 40 %, Fundamentaldaten/Krypto-Adoption 5 %, Makro 25 %, News 15 %, CRV 15 %
- Unbekannt: Technik 45 %, Fundamentaldaten 5 %, Makro 25 %, News 10 %, CRV 15 %

Das **Kaufsignal** bleibt separat: Es nutzt vor allem den Technik-Score, das CRV und begrenzte Zu- oder Abschläge für Marktphase, RSI und Volatilität.

### Research-Score-Einordnung

Die Research-Tabellen übersetzen jeden Score zusätzlich in einfache Bänder:

- `stark`: Der Baustein unterstützt die Analyse klar.
- `konstruktiv`: Der Baustein spricht eher für das Investment, braucht aber Bestätigung.
- `gemischt`: Der Baustein ist uneindeutig und sollte nicht allein entscheidend sein.
- `schwach`: Der Baustein bremst die Analyse und spricht für Vorsicht.
- `kritisch`: Der Baustein erhöht das Risiko deutlich.
- `Daten nicht verfügbar`: Es fehlen belastbare Daten; die App erfindet keine Werte.

### Kalibrierung

Die App zeigt im Bereich **Analyse-Details anzeigen** einen Kalibrierungsstatus. In Version 1 werden Gewichtungen nicht automatisch geändert.

- Unter 20 dokumentierten Fällen: `Datenbasis zu klein`
- 20 bis 50 Fälle: nur vorsichtige Hinweise
- Über 50 Fälle: Kalibrierungsvorschläge erlaubt

Künftige Trade- und Prognosehistorien werden lokal in `trade_history.json` ausgewertet. Diese Datei kann persönliche Entscheidungen enthalten und wird nicht versioniert.

### Depot-Effekt

Wird nur berechnet, wenn **Portfolio in Bewertung einbeziehen** aktiv ist.

Der Depot-Effekt bewertet:

- Cash-Reserve
- bestehende Positionsgröße
- Anteil am Gesamtportfolio
- Klumpenrisiko
- Auswirkung eines möglichen Nachkaufs

Der Depot-Effekt ist nur eine Ergänzung. Er verbessert oder verschlechtert nicht das Kaufsignal, sondern zeigt, ob ein Kauf für dein Depot verkraftbar wäre.

## Portfolio-Modus

Wenn der Schalter aus ist:

- nur Asset-Qualität und Kaufsignal
- keine Depotdaten
- keine Klumpenrisiko-Warnung
- keine Cash-Reserve-Bewertung

Wenn der Schalter an ist:

- zusätzlich Depot-Effekt
- Asset-Qualität und Kaufsignal bleiben unverändert

## portfolio.json

Die `portfolio.json` ist bewusst GitHub-kompatibel gehalten, damit der Depot-Modus auch auf anderen Geräten funktioniert. Sie darf nur einfache Depot-Strukturdaten enthalten:

- Cash-Bestand
- Ticker
- Asset-Typ
- Positionsgröße
- Kaufkurs

Nicht erlaubt sind:

- Name, Adresse oder persönliche Identifikationsdaten
- Kontonummern, Depotnummern oder Broker-IDs
- API-Keys, Passwörter oder Zugangsdaten
- geheime Konfigurationswerte

Zum Einrichten:

1. `portfolio.example.json` kopieren.
2. Die Kopie in `portfolio.json` umbenennen.
3. Nur die erlaubten Felder eintragen.

Beispiel:

```json
{
  "cash": 7000,
  "positions": [
    {
      "ticker": "BTC-EUR",
      "asset_type": "crypto",
      "shares": 0.014829,
      "buy_price": 100000
    },
    {
      "ticker": "EUNL.DE",
      "asset_type": "etf",
      "shares": 19.389571,
      "buy_price": 105.18
    }
  ]
}
```

Die App berechnet aktuelle Positionswerte im Depot-Modus über Yahoo Finance. Falls Kursdaten nicht verfügbar sind, wird das sauber angezeigt statt Werte zu erfinden.

- `cash`: freies Geld im Depot
- `ticker`: Yahoo-Finance-Ticker, z. B. `BTC-EUR`, `NVDA`, `EUNL.DE`
- `asset_type`: `stock`, `etf`, `crypto` oder `unknown`
- `shares`: Stückzahl oder Coin-Menge
- `buy_price`: durchschnittlicher Kaufkurs

Wichtig: Die Portfolio-Daten werden ausschließlich für den separaten Depot-Effekt verwendet. Sie verändern niemals Asset-Qualität oder Kaufsignal. Die App handelt niemals automatisch.

## Datenschutz und GitHub

Diese Dateien sind lokal/private Daten und werden nicht versioniert:

- `search_history.json`
- `trade_history.json`
- `forward_tests.json`
- `.streamlit/secrets.toml`
- `.env`
- `.venv/`
- `.yfinance-cache/`
- `__pycache__/`

Für GitHub gibt es anonymisierte Beispiele:

- `portfolio.example.json`
- `search_history.example.json`

`portfolio.json` darf versioniert werden, solange sie nur die erlaubten Felder enthält. Wenn `portfolio.json` fehlt, stürzt die App nicht ab. Im Portfolio-Modus zeigt sie dann den Hinweis: **Keine Portfolio-Datei gefunden.**

## Beispiele für Ticker

- Xiaomi: `3CP.DE` oder `1810.HK`
- Bitcoin: `BTC-EUR`
- Palantir: `PLTR`
- Nvidia: `NVDA`
- MSCI World ETF: `EUNL.DE`

## Hinweis

Dies ist keine Finanzberatung, sondern eine technische Analysehilfe. Die App enthält keine Broker-Anbindung und keine Kauf- oder Verkaufsautomatisierung.
