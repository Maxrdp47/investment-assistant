from __future__ import annotations

import pandas as pd

from analysis_models import AssetProfile, ModuleScore, ResearchModule
from technical_analysis import clamp, value_or_none

def build_data_source_warnings(
    ticker_info: dict,
    original_currency: str,
    fx_rate: float | None,
    fx_ticker: str,
    news: ModuleScore,
    macro: ModuleScore,
) -> list[str]:
    warnings: list[str] = []
    if not ticker_info:
        warnings.append("Yahoo-Finance-Stammdaten sind nicht verfügbar; Asset-Name, Börse, Fundamentaldaten und institutionelle Daten können eingeschränkt sein.")
    if original_currency != "EUR" and fx_rate is None:
        warnings.append(f"EUR-Umrechnung für {original_currency} ist nicht verfügbar ({fx_ticker}); Anzeige erfolgt teilweise in Originalwährung.")
    if any("Keine News verfügbar" in detail or "Keine aktuellen Nachrichten" in detail for detail in [news.summary, *news.details]):
        warnings.append("Yahoo-Finance-News sind nicht verfügbar oder leer; News-Score wird neutral behandelt.")
    if any("Keine Makrodaten verfügbar" in detail or "Makrodaten konnten nicht geladen" in detail for detail in [macro.summary, *macro.details]):
        warnings.append("Makro-Proxies konnten nicht geladen werden; Makro-Score wird neutral behandelt.")
    return warnings


def data_quality_status(data_quality: ResearchModule, external_warnings: list[str]) -> tuple[str, str, list[str]]:
    score = data_quality.score if data_quality.score is not None else 0.0
    if score >= 8 and not external_warnings:
        label = "Grün"
        summary = "Datenqualität gut. Die Analyse ist aus Datensicht solide nutzbar."
    elif score >= 6:
        label = "Gelb"
        summary = "Datenqualität eingeschränkt. Die Analyse ist nutzbar, aber einzelne Datenlücken sollten beachtet werden."
    else:
        label = "Rot"
        summary = "Datenqualität schwach. Die Analyse ist nur vorsichtig nutzbar."

    issues = [detail for detail in data_quality.details if "nicht" in detail.lower() or "fehlt" in detail.lower() or "weniger" in detail.lower()]
    highlights = [*issues[:2], *external_warnings[:2]]
    if not highlights:
        highlights = ["Keine wesentlichen Datenlücken erkannt."]
    return label, summary, highlights[:3]

def data_quality_check(
    symbol: str,
    asset_profile: AssetProfile,
    asset_identity: dict,
    df: pd.DataFrame,
    chart_history_label: str | None = None,
    analysis_history_label: str | None = None,
    chart_rows: int | None = None,
) -> ResearchModule:
    issues: list[str] = []
    positives: list[str] = []

    if symbol:
        positives.append("Ticker gefunden.")
    else:
        issues.append("Ticker nicht gefunden.")
    if asset_profile.asset_type and asset_profile.asset_type != "Derivat / unbekannt":
        positives.append(f"Asset-Typ erkannt: {asset_profile.asset_type}.")
    else:
        issues.append("Asset-Typ unsicher oder unbekannt.")
    if asset_identity.get("exchange") and asset_identity.get("exchange") != "Daten nicht verfügbar":
        positives.append(f"Börse erkannt: {asset_identity.get('exchange')}.")
    else:
        issues.append("Börse nicht erkannt.")
    if asset_identity.get("currency"):
        positives.append(f"Währung erkannt: {asset_identity.get('currency')}.")
    else:
        issues.append("Währung nicht erkannt.")
    if df.empty or "Close" not in df:
        issues.append("Kursdaten fehlen.")
    else:
        positives.append(f"Kursdaten vorhanden: {len(df)} Zeilen.")
    if chart_history_label:
        positives.append(f"Chart-Historie: {chart_history_label}" + (f" ({chart_rows} Zeilen)." if chart_rows is not None else "."))
    if analysis_history_label:
        positives.append(f"Analyse-Historie: {analysis_history_label} ({len(df)} Zeilen).")
    if "Volume" in df and df["Volume"].dropna().sum() > 0:
        positives.append("Volumen verfügbar.")
    else:
        issues.append("Volumen nicht verfügbar.")
    if "Close" in df and len(df.dropna(subset=["Close"])) >= 200:
        positives.append("Mindestens 200 Handelstage vorhanden.")
    else:
        issues.append("Weniger als 200 Handelstage vorhanden.")
    latest = df.iloc[-1] if not df.empty else pd.Series(dtype=float)
    if value_or_none(latest.get("SMA_50")) is not None:
        positives.append("50er-Durchschnitt berechenbar.")
    else:
        issues.append("50er-Durchschnitt nicht berechenbar.")
    if value_or_none(latest.get("SMA_200")) is not None:
        positives.append("200er-Durchschnitt berechenbar.")
    else:
        issues.append("200er-Durchschnitt nicht berechenbar.")

    score = round(clamp(10 - len(issues) * 1.2), 1)
    summary = "Datenqualität gut." if not issues else "Datenqualität eingeschränkt: " + "; ".join(issues)
    beginner = "Je mehr Daten fehlen, desto vorsichtiger solltest du die Analyse lesen. Fehlende Daten werden nicht erfunden."
    return ResearchModule("Datenqualität", score, summary, positives + issues, beginner)
