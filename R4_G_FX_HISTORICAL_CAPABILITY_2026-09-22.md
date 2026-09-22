# R4-G – FX-v2-Historienfähigkeit und Gap-Ursache

Stand: 2026-09-22. Outcome-freier, schreibgeschützter Audit des vorhandenen v6/v7-r2-Eingabevertrags. Keine Frozen-, v6-, v7-r2- oder FX-Quelldaten wurden verändert; keine Regel wurde gelockert.

## Konkreter Befund

Der eingefrorene v6-Input-Precheck `runtime/research_exports/multi_asset_development_v6_input_precheck_2026-09-05-v1-r7.json` meldet für die drei FX-Paare 4.508 aktive gültige Balken, 93 ausgeschlossene ungültige Source-Sitzungen, 165 Grenzen wegen fehlender Ziel-Paar-Balken an **beobachteten** Peer-Sitzungen, zusammen 258 Gap-Boundaries und **0** nach Warmup zulässige Signalpositionen. Die gesicherte FX-Dataset-Projektion hat Fingerprint `a3c41cddd06d7b24596bac5f1e375868a86784ea5a6feeacd9b44f49598c5c91`. `quick_check=ok`, 0 aktive OHLC-Hüllenverletzungen, 0 doppelte aktive Sitzungen, 0 Überlappungen mit archivierten ungültigen Sitzungen und 0 Availability-Verstöße stehen im Precheck.

Der read-only Segment-Loader aus [`multi_asset_development_v6_inputs.py`](multi_asset_development_v6_inputs.py) bestätigt:

| Paar | Aktive Balken | Kontinuitätssegmente | Längstes Segment | Peer-Missing-Grenzen | Invalid-Source-Grenzen | Zulässige Signale |
|---|---:|---:|---:|---:|---:|---:|
| EUR/USD | 1.523 | 39 | 194 | 38 | 24 | 0 |
| GBP/USD | 1.525 | 38 | 148 | 37 | 19 | 0 |
| USD/JPY | 1.460 | 91 | 75 | 90 | 50 | 0 |

Die 93 Invalid-Source- und 165 Peer-Missing-Grenzen können an derselben Segmentkante zusammentreffen; die Tabelle listet **Grenzereignisse**, nicht 258 unterschiedliche Schnittpunkte. Der unveränderte Gap-Vertrag verlangt 220 Beobachtungen **innerhalb desselben Segments** und einen ebenfalls dort liegenden nächsten Einstiegsbalken. Schon das längste Segment mit 194 Balken unterschreitet diese Mindestlänge. `NO_GAP_SAFE_220_OBSERVATION_HISTORY` ist daher anhand der Quellprojektion belegt; v7-r2 hatte folgerichtig 0 vollständige FX-Outcomes.

## Kalender-/Session-Prüfung

Die konservative Session-Gruppe ist die eingefrorene Vereinigung aktiv beobachteter Tage aller drei Paare, **kein** behaupteter offizieller FX-Kalender. Sie enthält 1.562 Beobachtungstage in der Development-Projektion, ausschließlich Montag bis Freitag (Montag 312, Dienstag 312, Mittwoch 312, Donnerstag 312, Freitag 314). Leere Wochenenden werden nicht künstlich als Lücken gezählt. Feiertage ohne irgendeinen Paar-Balken werden ebenfalls nicht als Sitzungen erfunden. Eine Grenze entsteht nur, wenn ein anderes Paar an diesem Tag tatsächlich beobachtet wurde und das Zielpaar fehlt, oder wenn ein belegter ungültiger Balken archiviert ist. Der vorliegende Befund zeigt **keinen nachgewiesenen Wochenend-/Kalenderbug**. Ob ein einzelnes Paar an einem Peer-Tag aus einem provider- oder sessionspezifischen Grund legitim fehlte, ist aus der erhaltenen Quelle nicht sicher auflösbar; diese Unsicherheit rechtfertigt kein automatisches Zusammenkleben der Segmente.

## Gate-Entscheidung

Historischer FX-v2-Discovery-Track: `FX_HISTORICAL_DISCOVERY_NOT_TESTABLE`. Kein FX-Challenger, kein Null-Edge-Urteil. Die archivierten ungültigen Balken werden weder geclippt noch imputiert; die 220er-Historien- und Entry-/Outcome-Grenzen bleiben unverändert. Eine spätere Teilnahme erfordert einen neuen, eigenständig versionierten und PIT-geprüften FX-Datensatz oder eine vor Ergebnissichtung fachlich belegte Session-Korrektur. Die bestehende Forward-PIT-Sammlung wird nicht angetastet; sie ersetzt keine historische Evidenz.

Nächster Programmblock ist R4-H Crypto; R5- und Outcome-Gates bleiben geschlossen.
