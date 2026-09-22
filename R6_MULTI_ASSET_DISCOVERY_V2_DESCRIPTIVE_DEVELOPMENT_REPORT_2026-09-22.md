# R6 Multi-Asset Discovery v2 – Descriptive Development Report

- Status: `R6_DESCRIPTIVE_COMPLETE_NO_ROBUST_CANDIDATE`
- Run: `mad2-development-v2-20260922-v1`
- Fälle: 2,356,553
- Vorab benannte Einzelfeatures: 31
- Robuste Kandidaten: 0
- Report-Fingerprint: `4ee1cdb2193a0103618ffa6887d8da03f65030addaf93fb1231a1db639d46024`

Die Tabelle enthält alle vorab festgelegten Einzelassoziationen, keine nach Rendite ausgewählte Rangliste. Pearson-r ist ausschließlich deskriptiv auf bereits gesehenen Development-Daten. `n/v` bedeutet nicht verfügbar.

| Feature | Familie | Horizont | N Return | r Return | N MFE | r MFE | N MAE | r MAE |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `core.return_20` | PRICE_RETURNS | 20 | 2,305,861 | -0.014938 | 2,305,861 | 0.001847 | 2,305,861 | 0.000970 |
| `core.return_20` | PRICE_RETURNS | 60 | 2,201,941 | 0.004188 | 2,201,941 | 0.005068 | 2,201,941 | -0.003567 |
| `core.return_20` | PRICE_RETURNS | 120 | 2,052,852 | 0.011466 | 2,052,852 | 0.015405 | 2,052,852 | -0.009332 |
| `core.return_20` | PRICE_RETURNS | 252 | 1,749,125 | 0.001574 | 1,749,125 | 0.004501 | 1,749,125 | 0.012797 |
| `core.return_60` | MOMENTUM_TREND_VOLATILITY | 20 | 2,305,861 | 0.001465 | 2,305,861 | 0.022321 | 2,305,861 | -0.017909 |
| `core.return_60` | MOMENTUM_TREND_VOLATILITY | 60 | 2,201,941 | 0.001643 | 2,201,941 | 0.009028 | 2,201,941 | -0.023893 |
| `core.return_60` | MOMENTUM_TREND_VOLATILITY | 120 | 2,052,852 | 0.015322 | 2,052,852 | 0.017561 | 2,052,852 | -0.015869 |
| `core.return_60` | MOMENTUM_TREND_VOLATILITY | 252 | 1,749,125 | 0.000405 | 1,749,125 | 0.003564 | 1,749,125 | -0.003566 |
| `core.rsi_14` | MOMENTUM_TREND_VOLATILITY | 20 | 2,305,861 | -0.026993 | 2,305,861 | -0.063901 | 2,305,861 | 0.098641 |
| `core.rsi_14` | MOMENTUM_TREND_VOLATILITY | 60 | 2,201,941 | -0.025759 | 2,201,941 | -0.019944 | 2,201,941 | 0.065393 |
| `core.rsi_14` | MOMENTUM_TREND_VOLATILITY | 120 | 2,052,852 | -0.021418 | 2,052,852 | -0.017886 | 2,052,852 | 0.046976 |
| `core.rsi_14` | MOMENTUM_TREND_VOLATILITY | 252 | 1,749,125 | -0.013709 | 1,749,125 | -0.013527 | 1,749,125 | 0.057615 |
| `core.atr_pct` | MOMENTUM_TREND_VOLATILITY | 20 | 2,305,861 | 0.286958 | 2,305,861 | 0.471164 | 2,305,861 | -0.315167 |
| `core.atr_pct` | MOMENTUM_TREND_VOLATILITY | 60 | 2,201,941 | 0.371704 | 2,201,941 | 0.382072 | 2,201,941 | -0.221959 |
| `core.atr_pct` | MOMENTUM_TREND_VOLATILITY | 120 | 2,052,852 | 0.345471 | 2,052,852 | 0.381048 | 2,052,852 | -0.171139 |
| `core.atr_pct` | MOMENTUM_TREND_VOLATILITY | 252 | 1,749,125 | 0.359643 | 1,749,125 | 0.359488 | 1,749,125 | -0.090137 |
| `core.volatility_20` | MOMENTUM_TREND_VOLATILITY | 20 | 2,305,861 | 0.061498 | 2,305,861 | 0.156080 | 2,305,861 | -0.153094 |
| `core.volatility_20` | MOMENTUM_TREND_VOLATILITY | 60 | 2,201,941 | 0.107682 | 2,201,941 | 0.081840 | 2,201,941 | -0.105371 |
| `core.volatility_20` | MOMENTUM_TREND_VOLATILITY | 120 | 2,052,852 | 0.093972 | 2,052,852 | 0.088851 | 2,052,852 | -0.077484 |
| `core.volatility_20` | MOMENTUM_TREND_VOLATILITY | 252 | 1,749,125 | 0.058743 | 1,749,125 | 0.062221 | 1,749,125 | -0.035949 |
| `core.volatility_60` | MOMENTUM_TREND_VOLATILITY | 20 | 2,305,861 | 0.106106 | 2,305,861 | 0.259630 | 2,305,861 | -0.147460 |
| `core.volatility_60` | MOMENTUM_TREND_VOLATILITY | 60 | 2,201,941 | 0.116864 | 2,201,941 | 0.096644 | 2,201,941 | -0.107448 |
| `core.volatility_60` | MOMENTUM_TREND_VOLATILITY | 120 | 2,052,852 | 0.098458 | 2,052,852 | 0.097757 | 2,052,852 | -0.083797 |
| `core.volatility_60` | MOMENTUM_TREND_VOLATILITY | 252 | 1,749,125 | 0.068341 | 1,749,125 | 0.070751 | 1,749,125 | -0.037053 |
| `core.volume_ratio_20` | REPORTED_VOLUME_RELATIVE | 20 | 2,304,541 | -0.006589 | 2,304,541 | 0.011890 | 2,304,541 | -0.046704 |
| `core.volume_ratio_20` | REPORTED_VOLUME_RELATIVE | 60 | 2,200,629 | 0.000710 | 2,200,629 | 0.001383 | 2,200,629 | -0.028286 |
| `core.volume_ratio_20` | REPORTED_VOLUME_RELATIVE | 120 | 2,051,540 | 0.003737 | 2,051,540 | 0.002313 | 2,051,540 | -0.020309 |
| `core.volume_ratio_20` | REPORTED_VOLUME_RELATIVE | 252 | 1,747,833 | -0.000550 | 1,747,833 | -0.000231 | 1,747,833 | -0.019160 |
| `core.close_vs_ema20_pct` | MOMENTUM_TREND_VOLATILITY | 20 | 2,305,861 | -0.047203 | 2,305,861 | -0.060293 | 2,305,861 | 0.061528 |
| `core.close_vs_ema20_pct` | MOMENTUM_TREND_VOLATILITY | 60 | 2,201,941 | -0.050782 | 2,201,941 | -0.037528 | 2,201,941 | 0.034063 |
| `core.close_vs_ema20_pct` | MOMENTUM_TREND_VOLATILITY | 120 | 2,052,852 | -0.026434 | 2,052,852 | -0.025544 | 2,052,852 | 0.020724 |
| `core.close_vs_ema20_pct` | MOMENTUM_TREND_VOLATILITY | 252 | 1,749,125 | -0.036655 | 1,749,125 | -0.033101 | 1,749,125 | 0.032435 |
| `core.ema20_vs_ema50_pct` | MOMENTUM_TREND_VOLATILITY | 20 | 2,305,861 | -0.054524 | 2,305,861 | -0.086951 | 2,305,861 | 0.059916 |
| `core.ema20_vs_ema50_pct` | MOMENTUM_TREND_VOLATILITY | 60 | 2,201,941 | -0.040364 | 2,201,941 | -0.024714 | 2,201,941 | 0.030483 |
| `core.ema20_vs_ema50_pct` | MOMENTUM_TREND_VOLATILITY | 120 | 2,052,852 | -0.016722 | 2,052,852 | -0.012783 | 2,052,852 | 0.026040 |
| `core.ema20_vs_ema50_pct` | MOMENTUM_TREND_VOLATILITY | 252 | 1,749,125 | -0.020765 | 1,749,125 | -0.017407 | 1,749,125 | 0.026792 |
| `core.safe_zone_a_distance_pct` | SUPPORT_RESISTANCE_GEOMETRY | 20 | 2,305,861 | 0.011471 | 2,305,861 | 0.028846 | 2,305,861 | -0.014760 |
| `core.safe_zone_a_distance_pct` | SUPPORT_RESISTANCE_GEOMETRY | 60 | 2,201,941 | 0.014137 | 2,201,941 | 0.011854 | 2,201,941 | -0.013950 |
| `core.safe_zone_a_distance_pct` | SUPPORT_RESISTANCE_GEOMETRY | 120 | 2,052,852 | 0.007633 | 2,052,852 | 0.010663 | 2,052,852 | -0.013162 |
| `core.safe_zone_a_distance_pct` | SUPPORT_RESISTANCE_GEOMETRY | 252 | 1,749,125 | 0.009264 | 1,749,125 | 0.009336 | 1,749,125 | -0.006934 |
| `core.safe_zone_b_distance_pct` | SUPPORT_RESISTANCE_GEOMETRY | 20 | 2,305,861 | 0.005154 | 2,305,861 | 0.014683 | 2,305,861 | -0.006150 |
| `core.safe_zone_b_distance_pct` | SUPPORT_RESISTANCE_GEOMETRY | 60 | 2,201,941 | 0.004915 | 2,201,941 | 0.005361 | 2,201,941 | -0.008664 |
| `core.safe_zone_b_distance_pct` | SUPPORT_RESISTANCE_GEOMETRY | 120 | 2,052,852 | 0.002337 | 2,052,852 | 0.005112 | 2,052,852 | -0.012734 |
| `core.safe_zone_b_distance_pct` | SUPPORT_RESISTANCE_GEOMETRY | 252 | 1,749,125 | 0.003886 | 1,749,125 | 0.004185 | 1,749,125 | -0.008009 |
| `core.safe_zone_c_distance_pct` | SUPPORT_RESISTANCE_GEOMETRY | 20 | 2,305,785 | 0.003897 | 2,305,785 | 0.009980 | 2,305,785 | -0.002844 |
| `core.safe_zone_c_distance_pct` | SUPPORT_RESISTANCE_GEOMETRY | 60 | 2,201,865 | 0.016120 | 2,201,865 | 0.013497 | 2,201,865 | -0.001881 |
| `core.safe_zone_c_distance_pct` | SUPPORT_RESISTANCE_GEOMETRY | 120 | 2,052,776 | 0.007217 | 2,052,776 | 0.010047 | 2,052,776 | -0.001205 |
| `core.safe_zone_c_distance_pct` | SUPPORT_RESISTANCE_GEOMETRY | 252 | 1,749,078 | 0.009774 | 1,749,078 | 0.010077 | 1,749,078 | 0.000577 |
| `r4b.relative_momentum_20` | RELATIVE_STRENGTH_GLOBAL_ACWI | 20 | 2,175,100 | -0.012659 | 2,175,100 | -0.002101 | 2,175,100 | -0.007154 |
| `r4b.relative_momentum_20` | RELATIVE_STRENGTH_GLOBAL_ACWI | 60 | 2,073,241 | 0.007342 | 2,073,241 | 0.002333 | 2,073,241 | -0.001199 |
| `r4b.relative_momentum_20` | RELATIVE_STRENGTH_GLOBAL_ACWI | 120 | 1,927,264 | -0.000359 | 1,927,264 | 0.005660 | 1,927,264 | -0.002226 |
| `r4b.relative_momentum_20` | RELATIVE_STRENGTH_GLOBAL_ACWI | 252 | 1,629,446 | 0.000174 | 1,629,446 | 0.001433 | 1,629,446 | 0.010325 |
| `r4b.relative_momentum_60` | RELATIVE_STRENGTH_GLOBAL_ACWI | 20 | 1,965,874 | 0.004029 | 1,965,874 | 0.016636 | 1,965,874 | -0.005923 |
| `r4b.relative_momentum_60` | RELATIVE_STRENGTH_GLOBAL_ACWI | 60 | 1,866,267 | -0.003133 | 1,866,267 | 0.002227 | 1,866,267 | -0.002703 |
| `r4b.relative_momentum_60` | RELATIVE_STRENGTH_GLOBAL_ACWI | 120 | 1,722,694 | -0.000657 | 1,722,694 | 0.003406 | 1,722,694 | -0.001827 |
| `r4b.relative_momentum_60` | RELATIVE_STRENGTH_GLOBAL_ACWI | 252 | 1,429,519 | -0.002458 | 1,429,519 | -0.000904 | 1,429,519 | 0.008094 |
| `r4b.relative_momentum_120` | RELATIVE_STRENGTH_GLOBAL_ACWI | 20 | 1,656,266 | 0.003366 | 1,656,266 | 0.006303 | 1,656,266 | -0.002164 |
| `r4b.relative_momentum_120` | RELATIVE_STRENGTH_GLOBAL_ACWI | 60 | 1,559,147 | 0.003210 | 1,559,147 | 0.001491 | 1,559,147 | 0.000989 |
| `r4b.relative_momentum_120` | RELATIVE_STRENGTH_GLOBAL_ACWI | 120 | 1,418,835 | 0.003292 | 1,418,835 | 0.001010 | 1,418,835 | 0.004271 |
| `r4b.relative_momentum_120` | RELATIVE_STRENGTH_GLOBAL_ACWI | 252 | 1,132,879 | -0.010462 | 1,132,879 | -0.010013 | 1,132,879 | 0.057343 |
| `r4b.resistance_distance_prior20_pct` | SUPPORT_RESISTANCE_GEOMETRY | 20 | 2,279,115 | 0.379991 | 2,279,115 | 0.472958 | 2,279,115 | -0.165740 |
| `r4b.resistance_distance_prior20_pct` | SUPPORT_RESISTANCE_GEOMETRY | 60 | 2,176,295 | 0.518551 | 2,176,295 | 0.555644 | 2,176,295 | -0.111668 |
| `r4b.resistance_distance_prior20_pct` | SUPPORT_RESISTANCE_GEOMETRY | 120 | 2,028,826 | 0.492643 | 2,028,826 | 0.548243 | 2,028,826 | -0.084847 |
| `r4b.resistance_distance_prior20_pct` | SUPPORT_RESISTANCE_GEOMETRY | 252 | 1,728,614 | 0.561672 | 1,728,614 | 0.563575 | 1,728,614 | -0.052810 |
| `r4b.support_distance_prior20_pct` | SUPPORT_RESISTANCE_GEOMETRY | 20 | 2,279,115 | 0.002350 | 2,279,115 | 0.007515 | 2,279,115 | -0.014386 |
| `r4b.support_distance_prior20_pct` | SUPPORT_RESISTANCE_GEOMETRY | 60 | 2,176,295 | 0.004696 | 2,176,295 | 0.004336 | 2,176,295 | -0.013558 |
| `r4b.support_distance_prior20_pct` | SUPPORT_RESISTANCE_GEOMETRY | 120 | 2,028,826 | 0.002722 | 2,028,826 | 0.004540 | 2,028,826 | -0.016073 |
| `r4b.support_distance_prior20_pct` | SUPPORT_RESISTANCE_GEOMETRY | 252 | 1,728,614 | 0.002731 | 1,728,614 | 0.003192 | 1,728,614 | -0.010151 |
| `r4b.pullback_from_prior20_high_pct` | CONFIRMED_STRUCTURE_CONTEXT | 20 | 2,279,115 | -0.102125 | 2,279,115 | -0.235931 | 2,279,115 | 0.241308 |
| `r4b.pullback_from_prior20_high_pct` | CONFIRMED_STRUCTURE_CONTEXT | 60 | 2,176,295 | -0.112132 | 2,176,295 | -0.085606 | 2,176,295 | 0.168974 |
| `r4b.pullback_from_prior20_high_pct` | CONFIRMED_STRUCTURE_CONTEXT | 120 | 2,028,826 | -0.115304 | 2,028,826 | -0.090026 | 2,028,826 | 0.127940 |
| `r4b.pullback_from_prior20_high_pct` | CONFIRMED_STRUCTURE_CONTEXT | 252 | 1,728,614 | -0.053733 | 1,728,614 | -0.055292 | 1,728,614 | 0.088905 |
| `r4b.consolidation_width_ratio_20_60` | CONFIRMED_STRUCTURE_CONTEXT | 20 | 2,278,667 | -0.020306 | 2,278,667 | -0.013154 | 2,278,667 | -0.044075 |
| `r4b.consolidation_width_ratio_20_60` | CONFIRMED_STRUCTURE_CONTEXT | 60 | 2,175,847 | 0.012651 | 2,175,847 | 0.001505 | 2,175,847 | -0.008191 |
| `r4b.consolidation_width_ratio_20_60` | CONFIRMED_STRUCTURE_CONTEXT | 120 | 2,028,378 | 0.002627 | 2,028,378 | 0.001149 | 2,028,378 | -0.004696 |
| `r4b.consolidation_width_ratio_20_60` | CONFIRMED_STRUCTURE_CONTEXT | 252 | 1,728,187 | 0.000173 | 1,728,187 | -0.000210 | 1,728,187 | -0.012227 |
| `r4b.trend_efficiency_20` | CONFIRMED_STRUCTURE_CONTEXT | 20 | 2,278,018 | 0.000211 | 2,278,018 | 0.007422 | 2,278,018 | -0.027766 |
| `r4b.trend_efficiency_20` | CONFIRMED_STRUCTURE_CONTEXT | 60 | 2,175,206 | 0.010118 | 2,175,206 | 0.007871 | 2,175,206 | -0.030240 |
| `r4b.trend_efficiency_20` | CONFIRMED_STRUCTURE_CONTEXT | 120 | 2,027,752 | 0.001397 | 2,027,752 | 0.006308 | 2,027,752 | -0.027980 |
| `r4b.trend_efficiency_20` | CONFIRMED_STRUCTURE_CONTEXT | 252 | 1,727,584 | 0.004867 | 1,727,584 | 0.005101 | 1,727,584 | -0.015004 |
| `r4b.trend_efficiency_60` | CONFIRMED_STRUCTURE_CONTEXT | 20 | 2,278,675 | 0.026284 | 2,278,675 | 0.042619 | 2,278,675 | -0.029849 |
| `r4b.trend_efficiency_60` | CONFIRMED_STRUCTURE_CONTEXT | 60 | 2,175,855 | 0.015616 | 2,175,855 | 0.015579 | 2,175,855 | -0.037169 |
| `r4b.trend_efficiency_60` | CONFIRMED_STRUCTURE_CONTEXT | 120 | 2,028,386 | 0.006628 | 2,028,386 | 0.009684 | 2,028,386 | -0.013450 |
| `r4b.trend_efficiency_60` | CONFIRMED_STRUCTURE_CONTEXT | 252 | 1,728,194 | 0.008009 | 1,728,194 | 0.007330 | 1,728,194 | -0.006082 |
| `r4b.breakout_above_prior20_high` | CONFIRMED_STRUCTURE_CONTEXT | 20 | 2,279,115 | -0.015725 | 2,279,115 | -0.023756 | 2,279,115 | 0.013130 |
| `r4b.breakout_above_prior20_high` | CONFIRMED_STRUCTURE_CONTEXT | 60 | 2,176,295 | -0.009054 | 2,176,295 | -0.006319 | 2,176,295 | 0.008437 |
| `r4b.breakout_above_prior20_high` | CONFIRMED_STRUCTURE_CONTEXT | 120 | 2,028,826 | -0.009088 | 2,028,826 | -0.006528 | 2,028,826 | 0.009474 |
| `r4b.breakout_above_prior20_high` | CONFIRMED_STRUCTURE_CONTEXT | 252 | 1,728,614 | -0.002885 | 1,728,614 | -0.003227 | 1,728,614 | 0.010980 |
| `r4b.confirmed_higher_high` | CONFIRMED_STRUCTURE_CONTEXT | 20 | 2,271,621 | -0.021934 | 2,271,621 | -0.034298 | 2,271,621 | 0.024530 |
| `r4b.confirmed_higher_high` | CONFIRMED_STRUCTURE_CONTEXT | 60 | 2,168,948 | -0.011620 | 2,168,948 | -0.009368 | 2,168,948 | 0.019873 |
| `r4b.confirmed_higher_high` | CONFIRMED_STRUCTURE_CONTEXT | 120 | 2,021,777 | -0.014636 | 2,021,777 | -0.010180 | 2,021,777 | 0.014944 |
| `r4b.confirmed_higher_high` | CONFIRMED_STRUCTURE_CONTEXT | 252 | 1,722,002 | -0.006303 | 1,722,002 | -0.006090 | 1,722,002 | 0.013868 |
| `r4b.confirmed_higher_low` | CONFIRMED_STRUCTURE_CONTEXT | 20 | 2,271,439 | -0.012485 | 2,271,439 | -0.021092 | 2,271,439 | 0.026678 |
| `r4b.confirmed_higher_low` | CONFIRMED_STRUCTURE_CONTEXT | 60 | 2,168,896 | -0.004994 | 2,168,896 | -0.002747 | 2,168,896 | 0.021718 |
| `r4b.confirmed_higher_low` | CONFIRMED_STRUCTURE_CONTEXT | 120 | 2,021,822 | -0.006066 | 2,021,822 | -0.002128 | 2,021,822 | 0.011387 |
| `r4b.confirmed_higher_low` | CONFIRMED_STRUCTURE_CONTEXT | 252 | 1,722,186 | 0.000419 | 1,722,186 | 0.000372 | 1,722,186 | 0.021487 |
| `r4h.relative_to_btc_20` | CRYPTO_BTC_RELATIVE | 20 | 26,746 | 0.048370 | 26,746 | 0.118546 | 26,746 | -0.175699 |
| `r4h.relative_to_btc_20` | CRYPTO_BTC_RELATIVE | 60 | 25,646 | -0.010182 | 25,646 | 0.029820 | 25,646 | -0.171672 |
| `r4h.relative_to_btc_20` | CRYPTO_BTC_RELATIVE | 120 | 24,026 | -0.005936 | 24,026 | 0.029295 | 24,026 | -0.142582 |
| `r4h.relative_to_btc_20` | CRYPTO_BTC_RELATIVE | 252 | 20,511 | -0.023470 | 20,511 | -0.029852 | 20,511 | -0.080843 |
| `r4h.relative_to_btc_60` | CRYPTO_BTC_RELATIVE | 20 | 26,746 | 0.001658 | 26,746 | 0.074501 | 26,746 | -0.197648 |
| `r4h.relative_to_btc_60` | CRYPTO_BTC_RELATIVE | 60 | 25,646 | 0.029199 | 25,646 | 0.066930 | 25,646 | -0.171319 |
| `r4h.relative_to_btc_60` | CRYPTO_BTC_RELATIVE | 120 | 24,026 | -0.038509 | 24,026 | 0.017638 | 24,026 | -0.140428 |
| `r4h.relative_to_btc_60` | CRYPTO_BTC_RELATIVE | 252 | 20,511 | -0.019593 | 20,511 | -0.031598 | 20,511 | -0.039603 |
| `r4h.asset_volatility_20` | MOMENTUM_TREND_VOLATILITY | 20 | 26,746 | 0.049309 | 26,746 | 0.180108 | 26,746 | -0.351653 |
| `r4h.asset_volatility_20` | MOMENTUM_TREND_VOLATILITY | 60 | 25,646 | 0.086671 | 25,646 | 0.129251 | 25,646 | -0.303974 |
| `r4h.asset_volatility_20` | MOMENTUM_TREND_VOLATILITY | 120 | 24,026 | 0.104593 | 24,026 | 0.132846 | 24,026 | -0.266633 |
| `r4h.asset_volatility_20` | MOMENTUM_TREND_VOLATILITY | 252 | 20,511 | 0.026741 | 20,511 | 0.037481 | 20,511 | -0.154884 |
| `r4h.btc_lagged_volatility_20` | CRYPTO_BTC_RELATIVE | 20 | 26,746 | 0.035218 | 26,746 | 0.040246 | 26,746 | -0.069686 |
| `r4h.btc_lagged_volatility_20` | CRYPTO_BTC_RELATIVE | 60 | 25,646 | 0.057255 | 25,646 | 0.032421 | 25,646 | 0.006612 |
| `r4h.btc_lagged_volatility_20` | CRYPTO_BTC_RELATIVE | 120 | 24,026 | 0.031273 | 24,026 | 0.040864 | 24,026 | 0.052362 |
| `r4h.btc_lagged_volatility_20` | CRYPTO_BTC_RELATIVE | 252 | 20,511 | -0.055523 | 20,511 | -0.045626 | 20,511 | 0.076680 |
| `r4h.reported_volume_ratio_20` | REPORTED_VOLUME_RELATIVE | 20 | 26,746 | 0.032795 | 26,746 | 0.039069 | 26,746 | -0.036266 |
| `r4h.reported_volume_ratio_20` | REPORTED_VOLUME_RELATIVE | 60 | 25,646 | 0.016979 | 25,646 | 0.024691 | 25,646 | -0.023603 |
| `r4h.reported_volume_ratio_20` | REPORTED_VOLUME_RELATIVE | 120 | 24,026 | 0.032390 | 24,026 | 0.035646 | 24,026 | -0.012528 |
| `r4h.reported_volume_ratio_20` | REPORTED_VOLUME_RELATIVE | 252 | 20,511 | 0.005132 | 20,511 | 0.009512 | 20,511 | -0.006768 |
| `r4h.close_vs_prior20_high_pct` | CONFIRMED_STRUCTURE_CONTEXT | 20 | 26,746 | 0.042857 | 26,746 | -0.018913 | 26,746 | 0.218875 |
| `r4h.close_vs_prior20_high_pct` | CONFIRMED_STRUCTURE_CONTEXT | 60 | 25,646 | -0.008355 | 25,646 | -0.017101 | 25,646 | 0.151916 |
| `r4h.close_vs_prior20_high_pct` | CONFIRMED_STRUCTURE_CONTEXT | 120 | 24,026 | -0.010550 | 24,026 | -0.021491 | 24,026 | 0.175970 |
| `r4h.close_vs_prior20_high_pct` | CONFIRMED_STRUCTURE_CONTEXT | 252 | 20,511 | -0.010224 | 20,511 | -0.015345 | 20,511 | 0.148538 |
| `r4h.trend_efficiency_20` | CONFIRMED_STRUCTURE_CONTEXT | 20 | 26,746 | 0.042092 | 26,746 | 0.067173 | 26,746 | -0.069789 |
| `r4h.trend_efficiency_20` | CONFIRMED_STRUCTURE_CONTEXT | 60 | 25,646 | 0.000687 | 25,646 | 0.016434 | 25,646 | -0.096166 |
| `r4h.trend_efficiency_20` | CONFIRMED_STRUCTURE_CONTEXT | 120 | 24,026 | 0.008394 | 24,026 | 0.012987 | 24,026 | -0.100299 |
| `r4h.trend_efficiency_20` | CONFIRMED_STRUCTURE_CONTEXT | 252 | 20,511 | 0.000043 | 20,511 | -0.007061 | 20,511 | -0.120466 |

## Quality-C-Entscheidung

- Gate: `MANDATORY_DEPENDENCIES_DIMENSION_FAILED_EFFECTIVE_N_ZERO`
- Dependencies: `FAIL_HISTORICAL_VERIFIED_ISSUER_EFFECTIVE_N_ZERO`
- Historisch verifizierte Issuer-Dependencies besitzen im eingefrorenen 2016–2021-Scope Effective N = 0. Da alle Quality-C-Dimensionen bestehen müssen, ist kein R7-Kandidat zulässig.
- Jahres-, Assetklassen- und Regime-Slices sowie alle Mittelwerte und Fallzahlen stehen vollständig im fingerprint-geschützten JSON-Artefakt.

Es wurden keine Schwellen, Quantile, Parameter, Featurekombinationen oder Profit-Ranglisten gesucht. Validation und Holdout blieben geschlossen.
