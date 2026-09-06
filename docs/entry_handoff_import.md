# ENTRY-Handoff-Import

`scripts/import_entry_handoff.py` übernimmt bereits in ENTRY analysierte Claims in die bestehende Research-Knowledge-Base. Die Schnittstelle speichert ausschließlich Research-Objekte. Sie startet keine Backtests, erzeugt keine Paper- oder Nutzertrades, führt keine Orders aus und ändert weder Strategiecode noch Strategieparameter.

## Aufruf

```powershell
python scripts/import_entry_handoff.py --input C:\pfad\handoff.json --json-output
```

Sicherer Probelauf ohne persistente Datei-, Schema- oder Datenänderung:

```powershell
python scripts/import_entry_handoff.py --input C:\pfad\handoff.json --dry-run --json-output
```

Für Tests kann eine abweichende Datenbank angegeben werden:

```powershell
python scripts/import_entry_handoff.py --input C:\pfad\handoff.json --database C:\temp\research-test.sqlite3 --json-output
```

Ohne `--database` gilt `INVESTMENT_ASSISTANT_RESEARCH_KB_DB`; andernfalls wird `runtime/research_knowledge.sqlite3` verwendet. `--json-output` schreibt genau ein JSON-Objekt nach stdout und benötigt keine Bestätigung. Dadurch kann ENTRY den Import automatisiert aufrufen.

## Schema `trading_handoff_v1`

Pflichtfelder sind in diesem vollständigen Beispiel gezeigt. `creator`, `url` und `published_date` dürfen `null` sein, wenn ENTRY sie nicht kennt. Unbekannte Werte werden nicht ergänzt. `source_hash` ist ein SHA-256 mit 64 Hex-Zeichen.

```json
{
  "schema_version": "trading_handoff_v1",
  "handoff_id": "handoff-techfeed5-001",
  "entry_source_id": "entry-source-techfeed5-001",
  "source_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "title": "Techfeed5: Pullback-Filter",
  "platform": "youtube",
  "creator": "techfeed5",
  "url": "https://youtu.be/AbCdEf12345",
  "published_date": "2026-08-31",
  "neutral_summary": "Neutrale Zusammenfassung ohne Handelsempfehlung.",
  "claims": [
    {
      "origin_claim_id": "entry-claim-001",
      "claim_text": "Ein erhöhtes relatives Volumen verbessert Pullback-Fortsetzungen.",
      "video_timestamps": [{"start": "00:01:12", "end": "00:01:38"}],
      "claim_type": "strategy_feature",
      "trading_relevance": "TRADING_RELEVANT",
      "market_scope": "US-Aktien, Daily Swing",
      "verification_status": "MOSTLY_SUPPORTED",
      "evidence_strength": "medium",
      "confidence": 72,
      "rationale": "Begründung der allgemeinen Quellenprüfung.",
      "evidence": [
        {
          "title": "Verifizierende Quelle",
          "url": "https://example.test/evidence",
          "publisher": "Publisher",
          "published_date": "2025-03-01",
          "notes": "Relevanz und Einschränkung."
        }
      ],
      "counter_evidence": [],
      "limitations": ["Keine Prüfung der konkreten Schwelle."],
      "risks": ["Overfitting", "Regimewechsel"],
      "valid_as_of": "2026-09-01",
      "tags": ["Pullback", "Volume"],
      "suggested_hypothesis": "Relatives Volumen als Pullback-Filter untersuchen.",
      "suggested_test": "Inkrementeller Point-in-Time-Test gegen die unveränderte Baseline."
    }
  ]
}
```

`video_timestamps` akzeptiert Textwerte oder Objekte. `evidence`, `counter_evidence`, `limitations` und `risks` müssen als Listen vorhanden sein; leere Listen sind zulässig. `tags` ist optional. `verification_status` akzeptiert die vorhandenen KB-Werte `UNVERIFIED`, `SUPPORTED`, `PARTIALLY_SUPPORTED`, `CONFLICTING_EVIDENCE`, `INSUFFICIENT_EVIDENCE`, `REFUTED`, `OUTDATED` sowie ENTRYs Alias `MOSTLY_SUPPORTED`. Dieser Alias wird in der bestehenden Tabelle als `PARTIALLY_SUPPORTED` gespeichert und im Herkunftsdatensatz unverändert erhalten.

Nur Claims mit `trading_relevance = "TRADING_RELEVANT"` werden übernommen. Andere im Paket enthaltene Claims erscheinen unter `ignored_claim_ids` und gelangen in keine Trading-Research-Tabelle. Mindestens ein Claim muss tradingrelevant sein.

### Strukturierte Vorschläge

Ein Text unter `suggested_hypothesis` oder `suggested_test` bleibt vollständig im Herkunftsdatensatz und in den Extraktionsnotizen erhalten. Ein Standardobjekt wird nur angelegt, wenn ENTRY alle benötigten Angaben liefert; der Importer erfindet keine Defaults.

Eine strukturierte Hypothese benötigt `title`, `area`, `category`, `claim`, `mechanism`, `external_evidence`, `rating` und `risks_limitations`. Zulässige `area`-Werte sind `swing_trader`, `opportunity_scanner`, `investment`, `cross_cutting`; Evidenzstärke ist `weak`, `medium` oder `strong`, Rating `A`, `B` oder `C`. `strategy` und `asset_class` sind optional. Der Status wird sicher auf `HYPOTHESIS` begrenzt.

Ein strukturierter Test benötigt zusätzlich eine strukturierte Hypothese sowie `title`, `test_definition`, `data_universe`, `point_in_time_rules` und `baseline`. Optional sind `period_start`, `period_end`, `features` und `parameters`. Er wird ausschließlich als `DRAFT` gespeichert. Es entsteht weder ein Work Request noch ein Testergebnis, und es wird kein Runner aufgerufen.

## Mapping

| ENTRY-Feld | Vorhandene Trading-/Research-Struktur |
|---|---|
| Titel, Plattform, Creator, URL, Datum, Zusammenfassung | `research_sources`, `source_provenance`, `source_identity_keys` |
| Claim, Scope, Zeitstempel, Typ, Risiken, Vorschläge | `source_claims`; strukturierte Zusatzdaten in `extraction_notes` |
| Trading-Relevanz und Claim-Typ | `claim_domain_assessments` (`TRADING_INVESTMENT`) |
| Verifikationsstatus, Begründung, Einschränkungen, `valid_as_of` | `claim_verification_assessments` |
| Evidenz und Gegenbelege | `claim_verification_references` |
| optionale Tags | `source_claim_tags` |
| vollständige strukturierte Hypothese | `hypotheses`, `hypothesis_sources`, `source_claim_resolutions`, `hypothesis_evidence_assessments`, `evidence_ledger` |
| vollständiger strukturierter Testvorschlag | `experiments` mit Status `DRAFT`, `experiment_features`, Statushistorie und Ledger |
| Herkunft, Revision und Dublettenschutz | `entry_handoff_imports`, `entry_claim_imports` |
| konkurrierende lokale Änderung | `entry_handoff_conflicts` |

Die Herkunftszuordnung hält `origin_system = ENTRY`, `origin_source_id`, `origin_claim_id`, `handoff_id`, `handoff_fingerprint`, `imported_at` und `source_hash` sowie das kanonische vollständige Payload-JSON. Die allgemeine Quellenprüfung bleibt von einem empirischen Test getrennt: `source_verification_status` enthält den ENTRY-Stand, `empirical_test_status` startet immer als `NOT_TESTED`, `research_status` als `CANDIDATE`.

## Idempotenz und Konflikte

- Der Import läuft in einer SQLite-Transaktion mit aktivierten Fremdschlüsseln und abschließender Fremdschlüsselprüfung.
- Derselbe `handoff_id` plus derselbe kanonische `handoff_fingerprint` liefert `NO_CHANGE` und erzeugt keine Zeile.
- Eine geänderte Revision derselben Handoff-ID wird append-only als `UPDATED` gespeichert. Unveränderte Quellen, Claims, Evidenzbewertungen, Hypothesen, DRAFT-Tests und Tags werden wiederverwendet.
- Eine geänderte Claim-Fassung wird als neuer Source-Claim gespeichert und über `SUPERSEDES` mit der vorherigen Fassung verbunden; die alte Fassung bleibt erhalten.
- Exakte URL-/Plattform-Identitäten und ENTRY-Herkunft verhindern doppelte Sources. Claim-Fingerprint, Referenz-Fingerprint und normalisierte Tags verhindern Dubletten in ihren Beziehungen.
- Lokale Ergänzungen, die der Importer nicht verwaltet, bleiben unangetastet. Wenn sich jedoch der vom vorigen Import verwaltete Zustand lokal geändert hat und ENTRY denselben Claim ebenfalls geändert liefert, wird nichts davon überschrieben. Der Import liefert `CONFLICT` und speichert den Konflikt samt eingehendem Payload in `entry_handoff_conflicts`.
- Eine Handoff-ID, die plötzlich auf eine andere `entry_source_id` zeigt, oder widersprüchliche exakte Quellenidentitäten erzeugen ebenfalls `CONFLICT`.
- Bei Validierungsfehlern wird nichts geschrieben. Bei Datenbank-/Dateifehlern oder verletzter Integrität wird die gesamte Transaktion zurückgerollt.

## Rückgabewerte und Exit-Codes

| Status | Exit-Code | Bedeutung |
|---|---:|---|
| `IMPORTED` | 0 | Neues Handoff wurde importiert. |
| `UPDATED` | 0 | Neue append-only Revision wurde übernommen. |
| `NO_CHANGE` | 0 | Identisches Paket war bereits vorhanden. |
| `CONFLICT` | 3 | Überschneidende lokale Änderung oder Identitätskonflikt; kein Import. |
| `REJECTED_INVALID` | 2 | JSON, Schema-Version oder Pflichtfeld ist ungültig. |
| `FAILED_RETRYABLE` | 75 | Temporärer Datei-/Datenbankfehler oder vollständiger Rollback nach Integritätsfehler. |

Eine erfolgreiche Antwort enthält mindestens `status`, `reason`, `handoff_id`, `source_id` und `claim_ids`; je nach Mapping zusätzlich Handoff-, Hypothesen-, Experiment-, Assessment- oder Konflikt-IDs. Beispiel:

```json
{"claim_ids":["..."],"conflict_ids":[],"database_path":"C:\\investment-assistent\\runtime\\research_knowledge.sqlite3","dry_run":true,"handoff_id":"handoff-techfeed5-001","reason":"Dry-Run erfolgreich: ... Es wurde nichts gespeichert.","source_id":"...","status":"IMPORTED"}
```
