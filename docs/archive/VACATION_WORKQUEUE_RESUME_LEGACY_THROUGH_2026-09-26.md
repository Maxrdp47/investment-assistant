# Urlaubs-Workqueue – Resume-Stand

Stand: 2026-09-06T03:59:37+02:00

Dieser kompakte Stand dient nur der idempotenten Fortsetzung der in `ROADMAP.md` begrenzten Queue. Er erweitert keine Freigabe.

## Queue

- `queue_id`: `vacation-workqueue-2026-09-06-v1`
- `queue_status`: `PREPARED_NOT_STARTED`
- `explicit_start_received`: `false`
- `current_task`: `NONE`
- `current_phase`: `WAITING_FOR_EXPLICIT_START`
- `last_successful_step`: Roadmap, Current Truth, Forschungsregeln, Historie und Queue-Struktur vorbereitet
- `code_branch`: `codex/multi-asset-development-v6`
- `project_head_before_documentation_commit`: `b1e3802b807649bc2cf871fa31ccf09fd8781cac`
- `development_v6_run_code_commit`: `e3ecdb6a1242c5922213ab489eb337342de0b17e`
- `documentation_commit`: der Commit, der diese Datei enthält
- `model_resume_automation_id`: `NONE`
- `model_resume_status`: `MANUAL_MODEL_RESUME_REQUIRED`
- `next_quota_check`: `NOT_SCHEDULED_BEFORE_START_SIGNAL`

## Vorhandener Development-v6-Stand

- `run_id`: `mad1-development-v6-f6432d72f806e9b97ea8ac46`
- `run_status`: `PAUSED_REQUIRES_REVIEW`
- `phase`: `RUN`
- `checkpoint_progress_pct`: 36.232315
- `last_successful_work_unit`: `madv6-unit-97a99277c5720e31d3810ea571c54d85`
- `last_checkpoint_at`: `2026-09-06T00:36:58.387179+00:00`
- `blocker`: `EQUITIES:FLG:OperationalError:attempt to write a readonly database`
- `process_observation`: kein laufender Python-Prozess der v6-Kette beim Dokumentations-Preflight
- `lock_observation`: Lock-Datei vorhanden; kein aktiver Prozess allein daraus ableitbar
- `scheduler_task`: `InvestmentAssistant-MultiAssetDiscoveryV1-Development-v6-Chain`
- `scheduler_state`: aktiviert / bereit; bestehende Aufgabe wurde nicht verändert
- `next_allowed_action_now`: auf ausdrückliches Startsignal warten
- `next_allowed_action_after_start`: Blocker read-only prüfen; nur bei rein technischer, contract-sicherer Ursache denselben Run idempotent fortsetzen

## Schutzstatus

- Validation geöffnet: `false`
- Holdout geöffnet: `false`
- External geöffnet: `false`
- Forward geöffnet: `false`
- Paper geöffnet: `false`
- Shadow geöffnet: `false`
- Broker geöffnet: `false`
- automatische Orders erlaubt: `false`
- neuer Multi-Asset-Run erlaubt: `false`; nur bestehende v6-Run-ID verwenden

## Vorhandene unabhängige Datensammler

- `InvestmentAssistant-FX-PIT-Observer`: aktiviert; letzter belegter Lauf 2026-09-05 21:45, Ergebnis 0
- `InvestmentAssistantDailyForecasts`: aktiviert; letzter belegter Lauf 2026-09-05 22:30, Ergebnis 0
- Diese vorhandenen Aufgaben wurden nicht gestoppt oder verändert.

## Fortsetzungsregeln

1. Nur ein ausdrückliches neues Startsignal darf `explicit_start_received` auf wahr setzen.
2. Vor jeder Fortsetzung Git, Prozesse, Scheduler, Locks, Chain-State und Run-ID prüfen.
3. Nie einen zweiten Development-v6-Run erzeugen.
4. Keine gesperrte Forschungsstufe öffnen.
5. Nach jedem wesentlichen Teilabschnitt diese Datei und die belegten Referenzen aktualisieren.
6. Bei Kontingentstopp Pausegrund und Zeitpunkt speichern.
7. Erst nach Startsignal prüfen, ob eine offizielle lokale Codex-Automation Modellarbeit alle fünf Stunden fortsetzen kann.
8. Nur bei belegter Registrierung und Funktionstest von automatischer Modell-Wiederaufnahme sprechen; sonst `MANUAL_MODEL_RESUME_REQUIRED` beibehalten.
9. Bei Nutzerstopp, abgeschlossener Queue oder ausschließlich nicht freigegebenen Blockern keine weitere Agenten-Wiederaufnahme planen.

## Vorhandene lokale Befehle

Diese Befehle sind dokumentiert, aber **vor dem Startsignal nicht zur Ausführung freigegeben**, soweit sie Runtime-Zustand verändern.

Status nur lesen:

```powershell
.\.venv\Scripts\python.exe scripts\run_multi_asset_development_v6_chain.py --status
```

Nach Startsignal und erfolgreichem Blocker-Review denselben Run freigeben:

```powershell
.\.venv\Scripts\python.exe scripts\run_multi_asset_development_v6_chain.py --resume
```

Kooperativ pausieren:

```powershell
.\.venv\Scripts\python.exe scripts\run_multi_asset_development_v6_chain.py --pause
```

Kontrolliert stoppen:

```powershell
.\.venv\Scripts\python.exe scripts\run_multi_asset_development_v6_chain.py --stop
```

Queue stoppen: Nutzer schreibt ausdrücklich `Stoppe die Urlaubs-Workqueue`. Danach keine neue Agenten-Wiederaufnahme erzeugen; separat freigegebene Datensammler bleiben unverändert, sofern der Nutzer sie nicht ebenfalls nennt.

## Erwartetes Startsignal

`Starte jetzt die freigegebene Urlaubs-Arbeitsliste`

Bis dahin endet jede Bearbeitung nach Dokumentation und sicheren read-only Prüfungen.
