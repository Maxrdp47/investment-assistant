# Investment-Assistent

Lokale Streamlit-App zur Analyse von Aktien, ETFs und Kryptowährungen über Yahoo Finance.

Die App handelt nicht automatisch, hat keine Broker-Anbindung und gibt keine Finanzberatung. Sie ist eine technische Analysehilfe; die letzte Entscheidung trifft immer der Nutzer.

## Funktionen

- Asset-Name oder Yahoo-Finance-Ticker eingeben
- automatische Yahoo-Finance-Suche mit auswählbaren Treffern für Firmennamen, ETFs und Kryptowährungen
- Speicherung der zuletzt erfolgreichen Suchanfragen in `search_history.json`
- Währungsmanagement: Anzeige standardmäßig in EUR plus Originalwährung
- automatische Asset-Typ-Erkennung: Aktie, ETF, Krypto oder unbekannt
- manuelle Asset-Typ-Auswahl, falls die automatische Erkennung unsicher ist
- getrennte Bewertung von Asset-Qualität, Kaufsignal und Depot-Effekt
- technische Analyse mit RSI, MACD, Trend, Volumen, Volatilität, Unterstützungen, Widerständen und CRV
- professionelles Research-Modul mit Datenqualitäts-Check, Modul-Scores, Szenarien, Nachkaufzonen und Fazit
- Marktphase und Szenario-Wahrscheinlichkeiten
- Anfänger-Modus mit einfachen Erklärungen
- optionaler Portfolio-Modus mit `portfolio.json`

## Start

Per Desktop-Symbol **Investment-Assistent** oder manuell:

```powershell
cd C:\investment-assistent
.\.venv\Scripts\python.exe -m streamlit run app.py
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
- Makro-Score
- News-Score
- Risiko-Score
- Liquiditäts-Score
- Bull-/Base-/Bear-Szenarien mit Wahrscheinlichkeiten, die zusammen 100 % ergeben
- Nachkaufzonen: aggressiv, fair, sicher und ungültig bei Bruch der Unterstützung
- Research-Fazit: was für Kauf spricht, was dagegen spricht, was die Analyse verbessern würde, welche Marke entscheidend ist und ein konkreter Plan
- Analysten-Konsens, sofern Yahoo-Finance-Daten verfügbar sind
- Earnings-Modul für Aktien, sofern Quartalsdaten verfügbar sind
- Event-Risiko-Modul für bekannte oder verfügbare Ereignisdaten
- Institutionelle Daten wie Beteiligungen und Short Interest, sofern verfügbar
- Vertrauensscore zur Einschätzung, wie belastbar die Analyse aktuell ist
- Unsicherheitsfaktoren: Was könnte diese Analyse widerlegen?

Wenn Daten fehlen, zeigt die App **Daten nicht verfügbar** oder **Datenqualität eingeschränkt**. Fehlende Kennzahlen werden nicht erfunden.

## Die drei Scores

### Asset-Qualität

Bewertet nur die langfristige Qualität des Assets.

- Bei Aktien: Umsatz, Gewinn, Free Cashflow, Verschuldung, Margen, Bewertung und Marktstellung, soweit verfügbar
- Bei ETFs: Diversifikation, TER/Kostenquote, Fondsvolumen, Region/Sektor und langfristige Stabilität, soweit verfügbar
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

Portfolio-Daten verändern das Kaufsignal nicht.

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
