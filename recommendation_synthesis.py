from __future__ import annotations

import pandas as pd

from analysis_models import (
    AssetProfile,
    MarketPhase,
    ModuleScore,
    PortfolioResult,
    ResearchModule,
    RiskReward,
)
from currency_utils import format_display_money
from entry_plan import (
    recommendation_confidence_label,
    recommendation_horizon,
    recommendation_validity,
)
from price_attractiveness import price_attractiveness_context
from technical_analysis import value_or_none

def synthesize_investment_recommendation(
    asset_profile: AssetProfile,
    asset_quality: ModuleScore,
    future_potential: ResearchModule,
    valuation: ResearchModule,
    priced_expectations: ResearchModule,
    bubble_risk: ResearchModule,
    buy_signal: ModuleScore,
    expected_value: ResearchModule,
    macro: ModuleScore,
    market_phase: MarketPhase,
    risk_reward: RiskReward,
    confidence: ResearchModule,
    data_quality: ResearchModule,
    supports: list[float],
    resistances: list[float],
    df: pd.DataFrame,
    latest: pd.Series,
    original_currency: str,
    fx_rate: float | None,
    currency_mode: str,
    uncertainty_factors: list[str] | None = None,
    portfolio_result: PortfolioResult | None = None,
    has_position: bool = False,
    ticker_info: dict | None = None,
) -> dict[str, object]:
    """Synthesize one actionable decision without changing any component score."""
    quality = asset_quality.score
    future = future_potential.score if future_potential.score is not None else 5.0
    valuation_score = valuation.score if valuation.score is not None else 5.0
    expectations = priced_expectations.score if priced_expectations.score is not None else 5.0
    bubble = bubble_risk.score if bubble_risk.score is not None else 5.0
    entry = buy_signal.score
    ev = expected_value.score if expected_value.score is not None else 5.0
    confidence_score = confidence.score if confidence.score is not None else 4.0
    data_quality_score = data_quality.score if data_quality.score is not None else 4.0
    close = float(latest.get("Close"))
    sma_50 = value_or_none(latest.get("SMA_50"))
    sma_200 = value_or_none(latest.get("SMA_200"))
    macd = value_or_none(latest.get("MACD"))
    macd_signal = value_or_none(latest.get("MACD_Signal"))
    volatility = value_or_none(latest.get("Volatility"))
    volume = value_or_none(latest.get("Volume"))
    volume_average = value_or_none(latest.get("Volume_SMA_20"))
    macd_positive = macd is not None and macd_signal is not None and macd > macd_signal
    above_sma_50 = sma_50 is not None and close >= sma_50
    above_sma_200 = sma_200 is None or close >= sma_200
    volume_confirmed = volume is not None and volume_average is not None and volume >= volume_average * 1.05

    valid_supports = [float(level) for level in supports if level < close]
    valid_resistances = [float(level) for level in resistances if level > close]
    recent_low = value_or_none(df["Low"].dropna().tail(20).min()) if "Low" in df else None
    recent_high = value_or_none(df["High"].dropna().tail(20).max()) if "High" in df else None
    pullback_level = valid_supports[0] if valid_supports else sma_50 if sma_50 is not None and sma_50 < close else recent_low
    confirmation_level = valid_resistances[0] if valid_resistances else recent_high
    zone_width = {"Aktie": 0.02, "ETF": 0.015, "Krypto": 0.04}.get(asset_profile.asset_type, 0.025)
    current_zone_width = zone_width / 2
    current_lower = close * (1 - current_zone_width)
    current_upper = close * (1 + current_zone_width)
    pullback_lower = pullback_level * (1 - zone_width) if pullback_level is not None else None
    pullback_upper = pullback_level * (1 + zone_width) if pullback_level is not None else None
    invalidation_level = pullback_lower * 0.98 if pullback_lower is not None else None

    pullback_label = (
        format_display_money(pullback_level, original_currency, fx_rate, currency_mode)
        if pullback_level is not None
        else "keine belastbare Kaufzone"
    )
    pullback_zone_label = (
        f"{format_display_money(pullback_lower, original_currency, fx_rate, currency_mode)} bis "
        f"{format_display_money(pullback_upper, original_currency, fx_rate, currency_mode)}"
        if pullback_lower is not None and pullback_upper is not None
        else "keine belastbare Kaufzone"
    )
    current_zone_label = (
        f"{format_display_money(current_lower, original_currency, fx_rate, currency_mode)} bis "
        f"{format_display_money(current_upper, original_currency, fx_rate, currency_mode)}"
    )
    confirmation_label = (
        format_display_money(confirmation_level, original_currency, fx_rate, currency_mode)
        if confirmation_level is not None
        else "keine belastbare Ausbruchsmarke"
    )
    invalidation_label = (
        format_display_money(invalidation_level, original_currency, fx_rate, currency_mode)
        if invalidation_level is not None
        else "keine belastbare Widerlegungsmarke"
    )
    pullback_path = (
        f"Rücksetzer-Einstieg in der Zone {pullback_zone_label} mit technischem Mittelpunkt {pullback_label}; "
        "erst zugreifen, wenn die Zone hält und der Kurs nicht dynamisch darunter schließt."
        if pullback_level is not None
        else "Rücksetzer-Einstieg erst nach Ausbildung einer neuen, belastbaren Unterstützung; aktuell wird keine Kaufzone erfunden."
    )
    confirmation_path = (
        f"Bestätigungs-Einstieg nach Tagesschluss über {confirmation_label} und Bestätigung durch einen stabilen Trend, stärkeres Momentum oder erhöhtes Volumen. "
        "Dieser Weg ist teurer, aber technisch besser bestätigt."
        if confirmation_level is not None
        else "Bestätigungs-Einstieg erst nach neuem 20-Tage-Hoch sowie positivem MACD- oder Volumensignal; aktuell fehlt eine belastbare Kursmarke."
    )
    invalidation = (
        f"Die technische Idee ist bei einem Tagesschluss unter {invalidation_label} widerlegt; anschließend vollständig neu bewerten."
        if invalidation_level is not None
        else "Die Einschätzung ist ungültig, wenn Trend und MACD weiter kippen oder neue Fundamentaldaten die Asset-Qualität deutlich senken."
    )

    quality_threshold = {"Aktie": 6.5, "ETF": 6.0, "Krypto": 5.5}.get(asset_profile.asset_type, 6.0)
    quality_good = quality >= quality_threshold and future >= 5.5
    quality_weak = quality < 4.5
    price_context = price_attractiveness_context(
        asset_profile.asset_type,
        future,
        valuation,
        expected_value,
        df,
        latest,
        ticker_info,
    )
    price_assessment = str(price_context["assessment"])
    price_attractive = price_assessment in {"Günstig", "Fair"}
    fundamentals_deteriorated = price_context.get("fundamentals_deteriorated") is True
    valuation_extreme = (
        (valuation.score is not None and valuation_score < 3.0)
        or (bubble_risk.score is not None and bubble >= 8.5)
        or (priced_expectations.score is not None and expectations >= 8.5)
    )
    valuation_stretched = (
        (valuation.score is not None and valuation_score < 4.5)
        or (bubble_risk.score is not None and bubble >= 7.5)
        or (priced_expectations.score is not None and expectations >= 7.5)
    )
    trend_supportive = market_phase.phase in {"Bullenmarkt", "Korrektur innerhalb eines Aufwärtstrends"} or (
        above_sma_50 and above_sma_200 and macd_positive
    )
    timing_strong = entry >= 7.0 and ev >= 5.8 and trend_supportive
    timing_acceptable = entry >= 4.8 and ev >= 4.8
    severe_avoid = quality <= 3.5 or (quality_weak and future < 4.5) or (entry <= 3.2 and ev <= 3.8) or (
        valuation_extreme and quality < 5.5
    )
    portfolio_result = portfolio_result or PortfolioResult(False, False, None, "Portfolio-Modus ist aus.", [])
    portfolio_blocks_entry = bool(
        portfolio_result.enabled
        and portfolio_result.available
        and portfolio_result.score is not None
        and portfolio_result.score < 4.5
    )

    if quality >= 8.0 and future >= 7.0:
        long_term_assessment = "Sehr attraktiv"
    elif quality_good:
        long_term_assessment = "Attraktiv"
    elif quality >= 4.5 and future >= 4.5:
        long_term_assessment = "Gemischt"
    else:
        long_term_assessment = "Schwach"

    if timing_strong:
        timing_assessment = "Gut"
    elif timing_acceptable:
        timing_assessment = "Vertretbar"
    elif entry >= 4.0:
        timing_assessment = "Nur bei Bestätigung"
    else:
        timing_assessment = "Ungünstig"

    if valuation.score is None:
        valuation_assessment = "Nicht belastbar verfügbar"
    elif valuation_score >= 7.0:
        valuation_assessment = "Günstig bis angemessen"
    elif valuation_score >= 5.0:
        valuation_assessment = "Angemessen"
    elif valuation_score >= 3.5:
        valuation_assessment = "Erhöht"
    else:
        valuation_assessment = "Extrem beziehungsweise sehr anspruchsvoll"

    if has_position:
        if severe_avoid:
            title = "Verkaufen oder vermeiden"
        elif portfolio_blocks_entry or quality_weak or valuation_extreme or (
            entry < 3.8 and market_phase.phase == "Bärenmarkt"
        ):
            title = "Teilweise reduzieren"
        else:
            title = "Halten"
    elif severe_avoid or quality_weak or portfolio_blocks_entry:
        title = "Verkaufen oder vermeiden"
    elif timing_strong and quality_good and price_attractive and not valuation_stretched and confidence_score >= 5.5:
        title = "Jetzt kaufen"
    elif quality_good and price_attractive and entry >= 3.5 and not valuation_extreme and confidence_score >= 4.5:
        title = "Erste Tranche kaufen"
    elif quality_good and timing_acceptable and not valuation_extreme and confidence_score >= 4.5:
        title = "Erste Tranche kaufen"
    elif entry >= 5.8 and ev >= 4.8 and confidence_score >= 4.5:
        title = "Bei Bestätigung kaufen"
    elif pullback_level is not None:
        title = "Auf konkrete Kaufzone warten"
    else:
        title = "Bei Bestätigung kaufen"

    if title == "Jetzt kaufen":
        next_action = f"Jetzt 40 % der geplanten Position in der Zone {current_zone_label} aufbauen."
        pullback_action = f"Weitere 35 % nach Stabilisierung in der Rücksetzer-Zone {pullback_zone_label} kaufen."
        strength_action = f"Kommt kein Rücksetzer, die restlichen 25 % erst nach Tagesschluss über {confirmation_label} und bestätigter Stärke ergänzen."
        tranche_plan = "40 % jetzt, 35 % beim bestätigten Rücksetzer, 25 % beim bestätigten Ausbruch."
    elif title == "Erste Tranche kaufen":
        next_action = f"Jetzt 25 % der geplanten Position in der Zone {current_zone_label} als erste Tranche kaufen."
        pullback_action = f"Weitere 35 % nur kaufen, wenn die Rücksetzer-Zone {pullback_zone_label} sichtbar hält."
        strength_action = f"Kommt kein Rücksetzer, weitere 25 % erst nach Tagesschluss über {confirmation_label} und Bestätigung der Stärke kaufen; die letzten 15 % erst nach anschließend stabilem Verlauf."
        tranche_plan = "25 % jetzt, 35 % beim bestätigten Rücksetzer, 25 % beim bestätigten Ausbruch, 15 % nach stabilem Folgeverlauf."
    elif title == "Bei Bestätigung kaufen":
        next_action = "Jetzt noch keine Tranche kaufen; eine der beiden konkreten Bestätigungen abwarten."
        pullback_action = f"35 % der geplanten Position kaufen, wenn die Zone {pullback_zone_label} hält; weitere 30 % erst nach anschließender Stabilisierung."
        strength_action = f"Alternativ 35 % nach Tagesschluss über {confirmation_label} und bestätigter Stärke kaufen; die restlichen 30 % erst nach stabilem Folgeverlauf."
        tranche_plan = "0 % jetzt; 35 % bei erster Bestätigung, 30 % nach Stabilisierung und 35 % über den zweiten bestätigten Einstiegspfad."
    elif title == "Auf konkrete Kaufzone warten":
        next_action = f"Jetzt 0 % kaufen und nur die konkrete Rücksetzer-Zone {pullback_zone_label} beobachten."
        pullback_action = f"40 % der geplanten Position erst kaufen, wenn die Zone {pullback_zone_label} hält; weitere 30 % nach anschließender Stabilisierung."
        strength_action = f"Kommt kein Rücksetzer, 30 % erst nach Tagesschluss über {confirmation_label} und bestätigter Stärke kaufen; vorher nicht hinterherlaufen."
        tranche_plan = "0 % jetzt, 40 % in der bestätigten Kaufzone, 30 % nach Stabilisierung, 30 % nur über den bestätigten Ausbruchsweg."
    elif title == "Halten":
        next_action = "Bestehende Position halten; kein Handlungsdruck, solange die Widerlegungsmarke intakt bleibt."
        pullback_action = f"Eine geplante Aufstockung zu 50 % erst bei gehaltenem Rücksetzer in die Zone {pullback_zone_label} umsetzen."
        strength_action = f"Die übrigen 50 % einer geplanten Aufstockung nur nach bestätigtem Ausbruch über {confirmation_label} ergänzen."
        tranche_plan = "Bestehende Position unverändert halten; eine mögliche Aufstockung 50 % in der bestätigten Rücksetzer-Zone und 50 % nach bestätigtem Ausbruch staffeln."
    elif title == "Teilweise reduzieren":
        next_action = "Als erste Risikoreduktion 25 % der bestehenden Position kontrolliert abbauen."
        pullback_action = f"Bei weiterer Schwäche in Richtung {pullback_zone_label} nicht automatisch nachkaufen, sondern die Restposition neu prüfen."
        strength_action = f"Die übrige Position halten, solange die Widerlegung nicht eintritt; eine bestätigte Rückkehr über {confirmation_label} erlaubt eine neue Bewertung."
        tranche_plan = "25 % der bestehenden Position zuerst reduzieren; weitere Schritte nur bei Widerlegung oder nach erneuter Gesamtanalyse."
    else:
        next_action = "Keine neue Position eröffnen; eine bestehende Position zunächst um 50 % reduzieren und die Restposition neu bewerten."
        pullback_action = "Ein fallender Kurs allein macht das Asset nicht attraktiv; vor einem Einstieg müssen Qualität und Investmentthese neu überzeugen."
        strength_action = f"Erst nach neuer fundamentaler Prüfung und bestätigter Rückkehr über {confirmation_label} erneut bewerten."
        tranche_plan = "0 % Neukauf; bei bestehender Position 50 % erste Risikoreduktion, Rest nur nach vollständiger Neubewertung halten oder abbauen."

    alternative_action = f"Rücksetzer: {pullback_action} Weitere Stärke: {strength_action}"

    price_reason = (
        f"Die Preisattraktivität ist {price_assessment.lower()}, aber Bewertung nicht verfügbar; die Datenlücke senkt die Sicherheit."
        if valuation.score is None
        else f"Die Preisattraktivität ist {price_assessment.lower()}; der Abstand zum früheren Hoch wird nicht als automatisches Kaufsignal verwendet."
    )
    timing_sentence = {
        "Gut": "gut",
        "Vertretbar": "vertretbar",
        "Nur bei Bestätigung": "nur bei Bestätigung",
        "Ungünstig": "ungünstig",
    }.get(timing_assessment, timing_assessment)
    main_reasons = [
        f"Die langfristige Einschätzung ist {long_term_assessment.lower()}.",
        price_reason,
        f"Das kurzfristige Timing ist {timing_sentence} und die Marktphase lautet „{market_phase.phase}“.",
    ]
    risk_candidates: list[str] = []
    if valuation_stretched:
        risk_candidates.append("Bewertung oder eingepreiste Erwartungen sind erhöht; ein gutes Asset kann dadurch kurzfristig enttäuschen.")
    if fundamentals_deteriorated:
        risk_candidates.append("Aktuelle Umsatz-, Gewinn- oder Cashflow-Daten zeigen Schwäche; der Kursabstand zum Hoch kann dadurch gerechtfertigt sein.")
    if entry < 4.5 or market_phase.phase == "Bärenmarkt":
        risk_candidates.append("Trend beziehungsweise Marktphase bestätigt den Einstieg derzeit nicht ausreichend.")
    if risk_reward.ratio is not None and risk_reward.ratio < 1.0:
        risk_candidates.append(f"Das aktuelle Chancen-Risiko-Verhältnis von {risk_reward.ratio:.2f} ist ungünstig.")
    if confidence_score < 5.0 or data_quality_score < 6.0:
        risk_candidates.append("Datenlage oder Signalstabilität ist eingeschränkt; fehlende Daten werden als Unsicherheit behandelt.")
    if portfolio_blocks_entry:
        risk_candidates.append("Der separate Depot-Effekt spricht wegen Cash- oder Konzentrationsrisiko gegen zusätzliches Kapital.")
    risk_candidates.extend(uncertainty_factors or [])
    central_risks = list(dict.fromkeys(risk_candidates))[:2]
    if not central_risks:
        central_risks = ["Markt-, Unternehmens- oder Ereignisdaten können die Einschätzung trotz aktuell stabiler Signale verändern."]

    volatility_limit = {"Aktie": 0.65, "ETF": 0.35, "Krypto": 1.10}.get(asset_profile.asset_type, 0.75)
    if risk_reward.score < 4.0 or (volatility is not None and volatility > volatility_limit):
        risk_label = "hoch"
    elif risk_reward.score < 6.0 or not above_sma_200:
        risk_label = "mittel"
    else:
        risk_label = "kontrollierbar"

    signal_confirmation: list[str] = []
    if macd_positive:
        signal_confirmation.append("MACD positiv")
    if above_sma_50:
        signal_confirmation.append("über 50-Tage-Linie")
    if volume_confirmed:
        signal_confirmation.append("Volumen bestätigt")
    signal_text = ", ".join(signal_confirmation) if signal_confirmation else "noch keine klare Momentum-/Volumenbestätigung"
    summary = f"{title}: {main_reasons[0]} {main_reasons[1]}"
    if title in {"Bei Bestätigung kaufen", "Auf konkrete Kaufzone warten"}:
        summary += " Die Wartebedingung ist an einen konkreten Kurs- und Bestätigungspfad gebunden."

    sizing_note = (
        "Die Prozentangaben beziehen sich auf die geplante Positionsgröße. Ohne definiertes Risikobudget und Maximalverlust wird kein Eurobetrag berechnet."
        if portfolio_result.enabled and portfolio_result.available
        else "Die Prozentangaben beziehen sich auf die geplante Position. Ohne vollständige Portfolio- und Risikodaten wird bewusst kein Eurobetrag erfunden."
    )
    risk_details: list[dict[str, str]] = []
    for index, risk in enumerate(central_risks):
        lowered_risk = risk.lower()
        if "bewertung" in lowered_risk or "erwart" in lowered_risk:
            observation = "An nachlassendem Wachstum, schwächeren Margen, gesenkten Prognosen oder einer negativen Kursreaktion auf Quartalszahlen."
        elif "trend" in lowered_risk or "marktphase" in lowered_risk or "chancen-risiko" in lowered_risk:
            observation = f"An einem bestätigten Bruch der technischen Widerlegungsmarke {invalidation_label} oder weiter schwächerem Momentum."
        elif "daten" in lowered_risk or "signalstabilität" in lowered_risk:
            observation = "An fehlenden, veralteten oder widersprüchlichen Stamm-, Markt- oder Ereignisdaten."
        elif "depot" in lowered_risk or "konzentration" in lowered_risk:
            observation = "An steigender Positionsgewichtung, sinkender Cash-Reserve oder zunehmendem Klumpenrisiko."
        else:
            observation = "An neuen Unternehmens-, Markt- oder Ereignisdaten, die die zentrale Investmentannahme widerlegen."
        risk_details.append(
            {
                "Risiko": risk,
                "Relevanz": "hoch" if index == 0 else "mittel bis hoch",
                "Erkennbar an": observation,
            }
        )

    central_assumption = {
        "Aktie": "Wachstum, Profitabilität und Wettbewerbsvorteile müssen die heutige Bewertung langfristig rechtfertigen.",
        "ETF": "Die zugrunde liegenden Märkte und die Diversifikation müssen den langfristigen Vermögensaufbau weiterhin tragen.",
        "Krypto": "Adoption, Liquidität und Marktstruktur müssen den langfristigen Anwendungs- und Nachfragefall weiter stützen.",
    }.get(
        asset_profile.asset_type,
        "Die langfristige Qualität und die erwarteten Treiber müssen sich in belastbaren Daten bestätigen.",
    )
    thesis_damage = f"Die These muss neu bewertet werden, wenn sich die langfristige Qualität verschlechtert. Zusätzlich gilt: {invalidation}"
    disappointment_risk = (
        "Erhöht: Der aktuelle Preis setzt bereits einen Teil der positiven Entwicklung voraus. Bleiben Wachstum oder Adoption hinter den Erwartungen, kann der Kurs deutlich fallen."
        if valuation_stretched
        else "Normal bis erhöht: Auch ein fairer Preis schützt nicht vor schwächeren Unternehmens-, Markt- oder Asset-Daten."
    )
    scenario_return_context = (
        f"Bis zur nächsten technischen Zielzone liegt das Potenzial bei etwa {risk_reward.reward_pct * 100:.1f} %, "
        f"das Risiko bis zur nächsten Unterstützung bei etwa {abs(risk_reward.risk_pct) * 100:.1f} %. "
        "Das sind Szenariobandbreiten, keine garantierten Renditen."
        if risk_reward.reward_pct is not None and risk_reward.risk_pct is not None
        else "Erwartete Rendite und Risiko lassen sich aus den vorhandenen Zonen derzeit nicht belastbar beziffern."
    )
    validity = recommendation_validity(asset_profile.asset_type, ticker_info)
    return {
        "Titel": title,
        "Empfehlungskategorie": title,
        "Langfristige Einschätzung": long_term_assessment,
        "Preisattraktivität": price_assessment,
        "Aktuelles Timing": timing_assessment,
        "Asset-Qualität": f"{quality:.1f}/10",
        "Zukunftspotenzial": f"{future:.1f}/10",
        "Bewertung": "Daten nicht verfügbar" if valuation.score is None else f"{valuation_score:.1f}/10",
        "Eingepreiste Erwartungen": "Daten nicht verfügbar" if priced_expectations.score is None else f"{expectations:.1f}/10",
        "Blasenrisiko": "Daten nicht verfügbar" if bubble_risk.score is None else f"{bubble:.1f}/10",
        "Technischer Einstieg": f"{entry:.1f}/10",
        "Expected Value": "Daten nicht verfügbar" if expected_value.score is None else f"{ev:.1f}/10",
        "Gesamtfazit": summary,
        "Kurzbegründung": " ".join(main_reasons),
        "Hauptgründe": main_reasons[:3],
        "Zentrale Risiken": central_risks,
        "Confidence": recommendation_confidence_label(confidence.score),
        "Confidence-Score": "Daten nicht verfügbar" if confidence.score is None else f"{confidence.score:.1f}/10",
        "Anlagehorizont": recommendation_horizon(asset_profile.asset_type),
        "Risiko": risk_label,
        "Nächste Handlung": next_action,
        "Alternative Handlung": alternative_action,
        "Handlung jetzt": next_action,
        "Handlung bei Rücksetzer": pullback_action,
        "Handlung bei weiterer Stärke": strength_action,
        "Sofort-Kaufzone": current_zone_label,
        "Kaufzone": pullback_zone_label,
        "Rücksetzer-Einstieg": pullback_path,
        "Bestätigungs-Einstieg": confirmation_path,
        "Tranchierung": tranche_plan,
        "Widerlegungsbedingung": invalidation,
        "Gültigkeit": validity,
        "Zentrale Annahme": central_assumption,
        "These beschädigt wenn": thesis_damage,
        "Bewertungseinordnung": valuation_assessment,
        "Allzeithoch-Kontext": price_context["high_context"],
        "Fundamentaldaten seit Hoch": price_context["fundamental_context"],
        "Grund für Kursrückgang": price_context["decline_reason"],
        "Szenario-Rendite": scenario_return_context,
        "Bewertung und Wachstum": (
            f"Der aktuelle Preis ist {price_assessment.lower()}. Er ist nur tragfähig, wenn sich die zentralen "
            "Wachstums-, Qualitäts- oder Adoptionstreiber über den angegebenen Anlagehorizont bestätigen. "
            "Bleibt die Entwicklung hinter den Erwartungen zurück, kann der Kurs deutlich fallen."
        ),
        "Enttäuschungsanfälligkeit": disappointment_risk,
        "Risiko-Details": risk_details,
        "Positionsgröße": sizing_note,
        "Signalbestätigung": signal_text,
        "Hauptgrund der Ablehnung": central_risks[0] if title in {"Teilweise reduzieren", "Verkaufen oder vermeiden"} else "Kein pauschaler Ablehnungsgrund.",
        "Nicht der Hauptgrund": "Fehlende Daten werden als Unsicherheit behandelt und nicht automatisch negativ gewertet.",
    }


def professional_decision(
    asset_quality: ModuleScore,
    future_potential: ResearchModule,
    valuation: ResearchModule,
    priced_expectations: ResearchModule,
    bubble_risk: ResearchModule,
    buy_signal: ModuleScore,
    expected_value: ResearchModule,
    macro: ModuleScore,
    market_phase: MarketPhase,
    confidence: ResearchModule | None = None,
) -> dict[str, str]:
    quality = asset_quality.score
    future = future_potential.score if future_potential.score is not None else 5.0
    valuation_score = valuation.score if valuation.score is not None else 5.0
    expectations = priced_expectations.score if priced_expectations.score is not None else 5.0
    bubble = bubble_risk.score if bubble_risk.score is not None else 5.0
    entry = buy_signal.score
    ev = expected_value.score if expected_value.score is not None else 5.0
    confidence_score = confidence.score if confidence and confidence.score is not None else 5.0

    positive_quality = quality >= 7.0 and future >= 6.0
    valuation_ok = valuation_score >= 5.2 and bubble < 7.8 and expectations < 7.8
    chance_positive = ev >= 5.8
    entry_acceptable = entry >= 4.8

    if quality <= 3.5 and entry <= 3.8:
        title = "Verkaufen / Risiko reduzieren"
    elif valuation_score <= 3.2 or bubble >= 8.2 or expectations >= 8.4:
        title = "Nicht kaufen"
    elif positive_quality and valuation_ok and chance_positive and entry >= 7.4:
        title = "Kaufen"
    elif positive_quality and valuation_ok and chance_positive and entry_acceptable:
        title = "Gestaffelt kaufen"
    elif positive_quality and valuation_ok and ev >= 5.2:
        title = "Kleine Tranche"
    elif ev >= 5.2 and entry >= 5.0 and valuation_score >= 4.5:
        title = "Beobachten"
    else:
        title = "Abwarten"

    if title == "Kaufen" and all([quality >= 8.0, valuation_score >= 6.5, entry >= 7.5, ev >= 7.0, bubble <= 5.5]):
        title = "Stark kaufen"

    reasons = {
        "Unternehmensqualität schwach": quality < 4.5,
        "Bewertung zu hoch": valuation_score < 4.2,
        "Blasenrisiko zu hoch": bubble >= 7.5 or expectations >= 7.5,
        "Makro schlecht": macro.score < 4.0 or market_phase.phase == "Bärenmarkt",
        "Trend klar negativ": entry < 4.0,
        "Einstieg technisch unattraktiv": entry < 5.0,
        "CRV schlecht": ev < 4.8,
        "Datenlage zu schwach": confidence_score < 4.5,
    }
    main_reason = "Kein klarer Ablehnungsgrund; Chance und Risiko werden abgewogen."
    if title in {"Nicht kaufen", "Abwarten", "Beobachten", "Verkaufen / Risiko reduzieren"}:
        main_reason = next((reason for reason, active in reasons.items() if active), "Signal noch nicht eindeutig genug.")

    not_main = []
    if quality >= 7.0 and main_reason != "Unternehmensqualität schwach":
        not_main.append("nicht wegen Unternehmensqualität")
    if valuation_score >= 5.2 and main_reason != "Bewertung zu hoch":
        not_main.append("nicht wegen Bewertung")
    if entry >= 5.0 and main_reason != "Einstieg technisch unattraktiv":
        not_main.append("nicht wegen Timing")
    not_main_reason = ", sondern wegen " + main_reason.lower() + "." if not_main else "Daten nicht eindeutig genug."
    if not_main:
        not_main_reason = f"{', '.join(not_main).capitalize()}{not_main_reason}"

    if title == "Stark kaufen":
        summary = "Außergewöhnlich attraktive Chance: Qualität, Bewertung, Einstieg und Expected Value passen selten gut zusammen."
    elif title == "Gestaffelt kaufen":
        summary = "Starkes Asset und positives CRV; der Einstieg muss nicht perfekt sein, daher eher in Tranchen statt alles sofort."
    elif title == "Kleine Tranche":
        summary = "Langfristig interessant, aber kurzfristige Unsicherheit ist erhöht; kleine Startposition statt voller Kauf."
    elif title == "Nicht kaufen":
        summary = "Gutes Unternehmen kann trotzdem ein schlechtes Investment sein, wenn Bewertung, Hype oder CRV dagegen sprechen."
    else:
        summary = "Die Entscheidung trennt Qualität, Bewertung, Timing und Expected Value statt pauschal vorsichtig oder bullisch zu sein."

    return {
        "Titel": title,
        "Asset-Qualität": f"{quality:.1f}/10",
        "Zukunftspotenzial": f"{future:.1f}/10",
        "Bewertung": "Daten nicht verfügbar" if valuation.score is None else f"{valuation_score:.1f}/10",
        "Eingepreiste Erwartungen": "Daten nicht verfügbar" if priced_expectations.score is None else f"{expectations:.1f}/10",
        "Blasenrisiko": "Daten nicht verfügbar" if bubble_risk.score is None else f"{bubble:.1f}/10",
        "Technischer Einstieg": f"{entry:.1f}/10",
        "Expected Value": "Daten nicht verfügbar" if expected_value.score is None else f"{ev:.1f}/10",
        "Gesamtfazit": summary,
        "Hauptgrund der Ablehnung": main_reason,
        "Nicht der Hauptgrund": not_main_reason,
    }
