# Buyer Confirmation v1 – Validation-Provenienz und Errata

Stand: 2026-08-28

Challenger: `buyer-confirmation-objective-pullback-v1`

Regel: `Close[t] > High[t-1]`

Scope: `objective_pullback`

## Kanonisches Ergebnis

Die ursprüngliche, vor Ergebnissichtung eingefrorene Validation ist technisch intakt und mit dem eindeutig zugeordneten Ausführungscode vollständig reproduzierbar. Ihr unveränderter Endstatus lautet:

`Development C_RECOMMENDATION -> Freeze -> VALIDATION_FAIL -> REJECTED_AT_VALIDATION`

Holdout wurde nicht geöffnet. External, Forward, Paper, Produktion und Brokerfunktionen waren nicht Teil dieser Evaluation. Es gab keine Retunes und keine Parameteränderung.

## A. Ausgangslage und Git-Zuordnung

- Kanonischer Audit-Worktree: `C:\Users\maxwi\AppData\Local\Temp\investment-assistant-buyer-validation-c6ca582`
- Kanonischer Branch: `codex/buyer-confirmation-validation`
- Start-HEAD und damaliger Origin-Stand: `3b73eb391340387c19ba2ebb624fd7dfc6579125`
- Der Hauptworktree `C:\investment-assistent` blieb auf `codex/swing-forward-diagnostics-status` mit HEAD `31ff30eeefd46c7f42993802864687eda0c6e47b` unangetastet. Seine fremden modifizierten und unversionierten Dateien wurden weder bereinigt noch überschrieben.
- Relevante erhaltene Branches: `codex/buyer-confirmation-robustness`, `codex/buyer-confirmation-validation`, `codex/swing-forward-diagnostics-status`, `main` und `backup-before-main-sync-2026-08-01`.

## B. Rekonstruierte Provenienz-Kette

| Stufe | Belegter Stand |
|---|---|
| Development | Commit `31ff30eeefd46c7f42993802864687eda0c6e47b`; autoritativer Report `buyer_confirmation_development_robustness_2026-08-26-v3-authoritative.json`; Ergebnis `C_RECOMMENDATION` |
| Broad-Konsolidierung | Commit `bfd4a97`; unveränderliche Broad-v1-Quelle konsolidiert |
| Freeze | 2026-08-26 20:12:20 Europe/Berlin; Freeze-Fingerprint `6c41572e2619e9123c8219d2d51fa61f542c5666fe8304519797caa6a06b9293` |
| Validation-Vertrag | Commit `a2eec82`; Integritäts- und Stage-Vertrag versioniert |
| KB-Verknüpfung | Commit `227a034`; bestehender Work Request und Experiment verknüpft |
| Ausführungscode | Commit `a2bc13b`; exakt der Codezustand der 100-Asset-/6-Worker-Ausführung |
| Validation Opening | 2026-08-27 00:01:27 Europe/Berlin; Opening-Fingerprint `27212a73d6c9c86219247950c255f883f7bf218ceb51eaf9af34ad5336847aea` |
| Stage Cases | 181.473 append-only Validation-Fälle |
| Asset Completions | 2.520/2.520 eindeutige Assets |
| Stage Review | 2026-08-27 03:51:53.005314+02:00; Review-Fingerprint `64c4b78dbda9fb0d5cc9e828df3338b9cebc24e05bdb22f7578f8073f6833d12` |
| Dokumentierter Endstand | Commit `3b73eb391340387c19ba2ebb624fd7dfc6579125`; `VALIDATION_FAIL`, `REJECTED_AT_VALIDATION` |

Die Ausführungsdateien sind zwischen `a2bc13b` und `3b73eb3` unverändert; der Git-Unterschied betrifft ausschließlich `PROJECT_STATUS.md` und `ROADMAP.md`. Der ursprüngliche Ausführungscode ist damit eindeutig gefunden. Result Integrity und Software Provenance sind `VERIFIED`.

### Identitäten und Fingerprints

- Dataset: `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`
- Feature-/Contract-Fingerprint: `c09d43e3c297b1685796db568b63c23c5878b2f246e69508c409fdbaa77f01dd`
- Code-Fingerprint: `77ab6ed29d8d08e32fabb8c2aee01c0a94953ded4b69092227f074273b12d946`
- Manifest-Fingerprint: `7531b0b8411436b3bbaf31d1db4bab94e35ecb0360f094cdbb96baf0d6297bf5`
- Broad-Hypothesen-Fingerprint: `c27747c508b1fcad46bdce7b3440b6b3e537ca64c618d3e08a264d62917a17d3`
- Freeze-Fingerprint: `6c41572e2619e9123c8219d2d51fa61f542c5666fe8304519797caa6a06b9293`
- Pre-Validation-Receipt-Fingerprint: `9b1c32caa47c0aad5085abce4902f1191550f13be1f77f7fd61434b500d74a59`
- Opening-Fingerprint: `27212a73d6c9c86219247950c255f883f7bf218ceb51eaf9af34ad5336847aea`
- Review-Fingerprint: `64c4b78dbda9fb0d5cc9e828df3338b9cebc24e05bdb22f7578f8073f6833d12`
- Validation-DB SHA-256: `008adc339f5f9a9abdfe26db12e02712df6957cc89c7f0bc7927357c6e8767ca`
- Decision-JSON SHA-256: `18952c3d561135a58c35bd382001da15f62f74bd2c8518aac4bec416da876bb1`
- Development-Report SHA-256: `7493c58c549d0b60f1bbdba09170bd14d0fb09be86559c30676dd0fe061f0c6f`
- Dataset-Manifest-Datei SHA-256: `7eb27d92bd3995ace9ca80e6a77eaeee0e492575363a9cc29f6638c0d1de725f`
- Freeze-JSON SHA-256: `84bffc897ba68d22f32ebe830d9247102c446a8ad6a6b3690842dc97972f82fd`
- Pre-Validation-Receipt-JSON SHA-256: `0998e1888e01848979653528eddddb5b7e76fc9c1af55c77fe2c43859220cc49`
- Validation-Modul SHA-256 / Git-Blob: `122f57775e85802399a28fbaf09ba10d4df6bc4c8fc749bf40e3c76ab126515d` / `12ae7620158d02c008237c5105c60563f2c02169`
- Validation-Runner SHA-256 / Git-Blob: `9d0b571ccb2b94f468316978454603edc1de22af88e8b764e9e78d4b89655d48` / `ae825c89cf34a986c5bc927393684440928690db`

Der maschinelle Audit prüft zusätzlich jeden einzelnen Payload-Fingerprint aller 181.473 Fälle und 2.520 Completions.

## C. Isolierte Reproduzierbarkeit

Die Validation wurde ground-up in einem separaten Scratch-Store reproduziert:

`C:\Users\maxwi\AppData\Local\Temp\buyer-confirmation-repro-a2bc13b-20260827\buyer_confirmation_validation.sqlite3`

Verwendet wurden ausschließlich der eingefrorene Dataset-/Challenger-Stand, identische Splits, Entry-/Stop-/Exit-/Kostenlogik, 100-Asset-Blöcke, sechs Worker, der globale Research-Lock und die bestehenden Produktionsschutzfenster. Die Original-Validation-DB wurde nur gelesen.

Ergebnis des read-only Vergleichs:

- 2.520/2.520 Asset-Completions identisch
- 181.473 Fälle und sämtliche Treatment-/Control-Gruppenzahlen identisch
- Case-Identitätsdigest: `59c5ef691d134b3d9ee2a8dfbcf43cfa9111436a18346f3226369462b765a36b` auf beiden Stores
- Completion-Identitätsdigest: `34c1aa4a306e14e2b4a86b145ee5847a84918ff9edd9538397299399e33d34b6` auf beiden Stores
- Freeze-, Receipt-, Opening- und Review-Fingerprint identisch
- Stage-Entscheidung und fehlgeschlagene Gates identisch
- alle geprüften logischen Records identisch
- das reproduzierte Decision-JSON ist byte-identisch zum Original
- die SQLite-Dateien sind wegen physischer Seiten-/Einfügereihenfolge nicht byte-identisch; Original SHA-256 `008adc339f5f9a9abdfe26db12e02712df6957cc89c7f0bc7927357c6e8767ca`, Reproduktion SHA-256 `b82d9acc707681425b0d240ce763b077236e031a9ac98083b272fca22481847c`

Diese physische SQLite-Abweichung betrifft keine logischen Datensätze, Metriken, Fingerprints oder Entscheidungen.

## D. Validation-Endstatus

- Treatment: 30.352 roh, 30.294 ausgewertet, effective N 23.595; Expectancy +0,009384 R; Profitfaktor 1,017033; Trefferquote 42,1866 %
- Control: 151.121 roh, 146.659 ausgewertet, effective N 51.954; Expectancy -0,189245 R; Profitfaktor 0,762872; Trefferquote 33,8377 %
- Direkter Expectancy-Abstand: +0,198630 R
- Vorab festgelegter gematchter Abstand: +0,208940 R
- Konservative Treatment-Ausführung: -0,043919 R; Profitfaktor 0,923839
- Positive Jahre: 2/4
- Kandidatenreihenfolge-Drawdown: 2.515,744 R; kein Portfolio-Drawdown

Fehlgeschlagene Gates:

- `conservative_execution_treatment_pf_above_one`
- `conservative_execution_treatment_positive`
- `positive_in_at_least_60pct_of_years`

Bestanden haben unter anderem Vollständigkeit, Validity/Power, Treatment-vs.-Control, Matching über vorab definierte Seeds, Scope-/Integritätsprüfung und exakte Baseline-Ausführungsrekonstruktion. Weil drei verbindliche Robustheitsgates scheiterten, ist `next_stage_allowed=false`. Holdout bleibt bei 0 Assets und 0 Fällen ungeöffnet.

## E. Knowledge Base

- Hypothese `9f8b5cc4...` bleibt absichtlich `RAW/B`, weil sie die breitere Hypothese „Pullback-Tiefe und Buyer Confirmation als inkrementelle Merkmale“ repräsentiert und nicht mit dem engeren Challenger gleichgesetzt werden darf.
- Experiment `fa61d54f-6649-4e8a-a521-15eb02e1bd90`: `COMPLETED`
- Work Request `e8fc4673-485c-48d8-a948-c44d5ecb2d49`: `COMPLETED`
- Resultat `a5060b1a-0323-40ac-94f2-24f6be6f686b`: negative Schlussfolgerung, terminal `REJECTED_AT_VALIDATION`
- Negative Validation-Bewertung `b0167cd2-e0ae-40c7-8d12-d337b083fea2`: append-only verknüpft; OOS, Walk-Forward sowie Kosten/Slippage `FAILED`; External, Forward und Paper `NOT_RUN`
- Keine unterstützende Hypothesis-Validation-Evidence und kein Integration Candidate wurden erzeugt. Das entspricht dem Schema: negative Evidenz wird als Result Assessment und im Ledger erhalten, nicht als positive Supporting Evidence.
- Wiederholte Synchronisierung ist idempotent und erzeugt weder ein doppeltes Resultat noch eine doppelte Bewertung.

## F. Erratum zum Dateinamen

Das unveränderliche Entscheidungsartefakt heißt `buyer_confirmation_validation_decision_2026-08-26-v1.json`, obwohl der gespeicherte Review am 2026-08-27 um 03:51:53 Europe/Berlin erfolgte. Der Dateiname wurde im vorab festgelegten Vertrag am Build-/Freeze-Tag 2026-08-26 hart codiert; der kontrollierte Lauf überschritt Mitternacht. Das Artefakt wird nicht umbenannt oder überschrieben, damit Hash und historische Referenz erhalten bleiben.

## G. Schutzbilanz

- Broad-v1, Frozen Dataset, Development-Artefakt und ursprüngliche Validation-DB unverändert
- Walk-Forward-v1 blieb unverändert bei SHA-256 `ad4a211e54f5a24f9866fd92c62aa1272a0c7697f678593163fcca0b297c58e0`.
- Shadow und External blieben unverändert bei SHA-256 `d343d034b88c39db1e964e4cfe5367377c4886018eeaa48a15c7282c8a1d81da` und `885cd83d64aa4dcb76dd716398bc961237dbadfe8e3657d6e43c4af9286b7026`.
- Forward- und Paper-Store änderten sich unabhängig durch die geschützte Produktionskette am 2026-08-27 um 23:07 Europe/Berlin. Die Reproduktion war zu diesem Zeitpunkt gesperrt und wurde erst nach 00:14 fortgesetzt; diese produktionsseitigen Änderungen stammen nicht aus dem Audit. Aktuelle SHA-256-Werte: Forward `d01b1e08281a7873a7e6a4e74a4537c9e6e83cfa5bcf70fead0b2bc11e70bd56`, Paper `0f5d98a57e628576566cc5b7e7f9757b3573bb16df48fdf7624006253df51c41`.
- durch diesen Audit keine Holdout-, External-, Forward-, Paper- oder Produktionsöffnung
- keine Retunes, neuen Regeln, Strategieparameter oder Brokerfunktionen
- keine Änderungen an fremden Dateien im Hauptworktree
- ausschließlich zulässige append-only KB-Bewertung ergänzt

## H. Engineering-Nachweis

- `python -m compileall .`: erfolgreich; lediglich das fremd besitzte Cache-Verzeichnis `.pytest_cache` konnte nicht aufgelistet werden und enthält keinen Projektquellcode.
- Gezielte Provenienz-/KB-/Lifecycle-/Validation-Tests: 36 bestanden.
- Vollständige Testsuite: 772 bestanden in 69,69 Sekunden.
- Repository Safety Check: `OK`.
- Offline-Smoke-Test: `OK`, einschließlich eingebautem Streamlit-Start.
- Separater lokaler Streamlit-Start auf Test-Port 8517: erfolgreich; anschließend kontrolliert beendet.
- `git diff --check`: ohne Fehler.
- Kanonischer Branch: `codex/buyer-confirmation-validation`.
- Commit, Push und GitHub-Actions-Status werden im abschließenden Git-Nachweis berichtet.
