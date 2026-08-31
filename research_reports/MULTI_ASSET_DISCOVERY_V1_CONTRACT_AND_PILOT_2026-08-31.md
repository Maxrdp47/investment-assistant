# Multi-Asset Opportunity Discovery v1 – Contract Freeze und technischer Pilot

Stand: 2026-08-31

## Verbindlicher Endstatus

`NOT_READY_TO_START_MULTI_ASSET_DISCOVERY_V1_DEVELOPMENT`

Der große Development-Scan wurde nicht gestartet. Ebenso blieben Validation, Holdout, External, True Forward, Paper, Shadow, Broker, automatische Orders und Produktion geschlossen. Der Pilot enthält keine Performance-Aussage.

## Eingefrorener Vertrag

Der kanonische semantische Vertrag steht in `config/multi_asset_discovery_v1.json` und trägt den Contract-Fingerprint `68994e462f90e2a4f1ad4adbdc858cc43fb0ddb85b0c2662d0f647e1dfa6c05a`.

Eingefroren sind insbesondere:

- getrennte Daily-Analysen für `EQUITIES`, `ETF`, `FX` und `CRYPTO`,
- rein technische Pilot-Eignung ohne prädiktiven Vorfilter und ohne Opportunity-Gesamtscore,
- Point-in-Time-Snapshots nach abgeschlossener Tageskerze,
- Referenzeinstieg ausschließlich zum nächsten verfügbaren Open,
- 252 Tagesbeobachtungen mit Checkpoints 20/60/120/252 und harter Stage-Zensierung,
- exakt drei Safe-Zone-Modelle A/B/C, eine unveränderliche Originalzone und ein nur anhebbarer bestätigter Ratchet,
- drei rein beobachtende Sell-Zonen A/B/C,
- getrennte MFE-/MAE-Messung in Prozent, ATR14 und strukturellem R,
- getrennte Intraday- und Schlusskursverletzungen,
- getrennte Deterioration-Familien,
- explizite Missingness ohne Imputation,
- rohe Fallzahl ungleich unabhängige Fallzahl; unbekannte Dependencies tragen null zum effective N bei,
- physisch getrennte append-only Feature- und Outcome-Stores,
- keine automatische Regel-, Strategie- oder Produktionsableitung.

Der authoritative Implementierungs-Freeze ist `runtime/research_exports/multi_asset_discovery_v1_contract_freeze_2026-08-31-v1-implementation-r4.json`, Freeze-Fingerprint `0d5a0cb5634398ccdc8e9fe55a702ea1b4c713cbf85415bf710d6d503d333aef`, Code-Fingerprint `c76268ca3d274324996bc9bf9e68a26b2bc257edf384aa39b8820f26e60154ac`.

## Technischer Pilot

Der Pilot verwendete genau elf feste Integritätsfälle:

- Aktien: AAPL, MSFT,
- ETFs: SPY, QQQ,
- FX: EUR/USD, GBP/USD, USD/JPY,
- Krypto: BTC-USD, ETH-USD, SOL-USD,
- zusätzlicher AAPL-Fall nahe der Development-Grenze zur Prüfung der Zensierung.

Alle Assetklassen blieben getrennt. Features wurden vor Outcomes erzeugt. Der AAPL-Grenzfall wurde korrekt am 2021-12-31 als `CENSORED_AT_STAGE_BOUNDARY` beendet. Deterministische Wiederholung, Next-Open, Safe-/Sell-Zonen, Ratchet, Breach-Messung, Checkpoints, MFE/MAE/R, Dependency-Fail-Closed, Store-Trennung, Append-only-Resume und SQLite-Integrität bestanden.

Authoritative Ergebnisdatei: `runtime/research_exports/multi_asset_discovery_v1_integrity_pilot_2026-08-31-v1-authoritative-r4.json`

- Pilot-Fingerprint: `3ef0864fd0e4c94e1d20e069fcbd14516d5b8c9c5924dd819469b862949374a7`
- Case-Digest: `f97bbff722535635d03dd41f3848c4a47b1ee6482180dd1765946aae3b64af16`
- 18 von 19 Readiness-Gates bestanden.
- Feature-Store: 11 Zeilen, Integrität `ok`.
- Outcome-Store: 11 Zeilen, Integrität `ok`.
- Wiederholung erzeugte 0 neue Features und 0 neue Outcomes; die authoritative Dateien und Stores blieben hash-identisch.

## Blocker

Der Gate `no_ohlc_envelope_anomalies` ist fehlgeschlagen. Die vorhandenen historischen FX-Providerbalken enthalten Fälle, in denen Open oder Close außerhalb der gemeldeten High-/Low-Hülle liegen:

| Paar | Anomalien bis zum Pilot-Signal | Anomalien im 252er Outcome |
|---|---:|---:|
| EUR/USD | 50 | 3 |
| GBP/USD | 26 | 6 |
| USD/JPY | 88 | 2 |

Über den gesamten vorhandenen FX-Preisbestand sind 68 EUR/USD-, 42 GBP/USD- und 121 USD/JPY-Balken betroffen, insgesamt 231. Kein Wert wurde korrigiert, geclippt, ersetzt oder imputiert. Die Originalwerte sind im Pilot nur zur Diagnose lesbar; der Fehler blockiert den großen Development-Start fail-closed.

Zusätzlich bleiben alle elf Pilot-Dependencies zum historischen Entscheidungszeitpunkt unbekannt und tragen daher null zum issuer-adjustierten effective N bei. Das ist keine Stichprobenbehauptung und keine Performance-Evidenz. Vor einem späteren Development-Start muss der Anwendungsmodus des bereits heute verifizierten Identity-Registry auf historische Dependency-Gruppierung explizit und ohne Feature-Leakage geklärt werden.

## Transparente Laufprovenienz

- Der erste Freeze `...contract_freeze_2026-08-31-v1.json` entstand vor dem ersten Pilotversuch. Dieser Versuch stoppte vor jedem Feature-/Outcome-Write an der OHLC-Hüllenprüfung.
- `implementation-r2` führte die Anomalien erstmals explizit als Fail-closed-Fakt und erzeugte die elf unveränderten Fälle.
- `authoritative-r3` korrigierte ausschließlich einen fehlerhaft manuell gesetzten zukünftigen Provenienzzeitpunkt; die Fall-Digests blieben identisch.
- `authoritative-r4` ergänzt den reproduzierbaren SQLite-WAL-Checkpoint und den idempotenten Resume-Pfad. Dies ist der maßgebliche technische Abschluss.

Keine ältere Datei wurde überschrieben. Die geschützten Precheck-, Identity-, Failed-Seller-, Frozen-Dataset-, Broad-v1-, Buyer-, Forward- oder Nutzerdaten blieben unverändert.

## Erforderliche nächste Arbeit vor Development

1. Einen neuen, vorab eingefrorenen FX-Datenqualitätsvertrag definieren, der die 231 Hüllenverletzungen ohne erfundene Kurse behandelt.
2. Danach einen neuen kleinen technischen FX-Integritätspilot ausführen.
3. Die historische Anwendbarkeit der Identity-/Dependency-Registry ausschließlich für Clusterung, nicht als Marktfeature, explizit festlegen und testen.
4. Erst wenn alle Readiness-Gates grün sind, darf der Status auf `READY_TO_START_MULTI_ASSET_DISCOVERY_V1_DEVELOPMENT` wechseln. Auch dann darf der große Scan nur durch einen neuen ausdrücklichen Auftrag gestartet werden.
