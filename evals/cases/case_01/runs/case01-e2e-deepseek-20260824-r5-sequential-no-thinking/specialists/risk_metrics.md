# Risk Metrics Review

## Review Metadata

- **Report ID:** RISK
- **Domain:** risk_metrics
- **Review Period:** 2025-07-01 to 2026-06-30
- **Generated At:** 2026-08-24T12:25:12.557005+00:00

## Scope

Risk Metrics review of 2 source(s) (risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv, risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet) for the period 2025-07-01 to 2026-06-30.

## Sources Reviewed

- SRC-012
- SRC-013

## Analysis Performed

- risk_metrics_input_contract
- risk_metrics_data_integrity
- risk_limit_consumption
- risk_metric_dynamics
- risk_excess_workflow
- risk_cross_source_consistency

## Data Overview

### Limit utilization — MOCK_PTF_ATLAS VAR

**Overview ID:** `risk-metrics.limit-utilization`
**Status:** available

Directional utilization for MOCK_PTF_ATLAS / MOCK_RISK_METRIC_VAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 43.1% (2026-06-30 effective directional limit)
- **Worst utilization:** 107.9% (maximum on 2026-03-26)
- **P95 utilization:** 61.2% (95th percentile of reviewed observations)
- **Breach observations:** 3 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.553127 | 0.430561 | 0.409578 | 1.07857 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=1:12481`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_ATLAS SVAR

**Overview ID:** `risk-metrics.limit-utilization-263efcd203`
**Status:** available

Directional utilization for MOCK_PTF_ATLAS / MOCK_RISK_METRIC_SVAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 50.9% (2026-06-30 effective directional limit)
- **Worst utilization:** 58.3% (maximum on 2025-11-13)
- **P95 utilization:** 57.3% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.508459 | 0.50855 | 0.499471 | 0.582516 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=2:12482`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_ATLAS STRESS TEST

**Overview ID:** `risk-metrics.limit-utilization-ddb3332f54`
**Status:** available

Directional utilization for MOCK_PTF_ATLAS / MOCK_RISK_METRIC_STRESS against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 58.2% (2026-06-30 effective directional limit)
- **Worst utilization:** 64.3% (maximum on 2026-05-28)
- **P95 utilization:** 63.7% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.562009 | 0.582147 | 0.558801 | 0.642604 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=3:12483`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_ATLAS EXPOSURE

**Overview ID:** `risk-metrics.limit-utilization-44437f4254`
**Status:** available

Directional utilization for MOCK_PTF_ATLAS / MOCK_RISK_METRIC_EXPOSURE against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 70.5% (2026-06-30 effective directional limit)
- **Worst utilization:** 78.5% (maximum on 2025-09-05)
- **P95 utilization:** 77.3% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.676188 | 0.704797 | 0.669501 | 0.78495 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=4:12484`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_BOREAL VAR

**Overview ID:** `risk-metrics.limit-utilization-783135ed12`
**Status:** available

Directional utilization for MOCK_PTF_BOREAL / MOCK_RISK_METRIC_VAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 57.7% (2026-06-30 effective directional limit)
- **Worst utilization:** 62.5% (maximum on 2026-02-05)
- **P95 utilization:** 61.3% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.577335 | 0.577022 | 0.527587 | 0.62498 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=5:12485`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_BOREAL SVAR

**Overview ID:** `risk-metrics.limit-utilization-05d3d3a90d`
**Status:** available

Directional utilization for MOCK_PTF_BOREAL / MOCK_RISK_METRIC_SVAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 46.1% (2026-06-30 effective directional limit)
- **Worst utilization:** 58.3% (maximum on 2025-12-29)
- **P95 utilization:** 57.2% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.542115 | 0.460916 | 0.415344 | 0.582657 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=6:12486`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_BOREAL STRESS TEST

**Overview ID:** `risk-metrics.limit-utilization-b4b5ca6779`
**Status:** available

Directional utilization for MOCK_PTF_BOREAL / MOCK_RISK_METRIC_STRESS against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 61.9% (2026-06-30 effective directional limit)
- **Worst utilization:** 64.2% (maximum on 2025-12-29)
- **P95 utilization:** 63.8% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.598712 | 0.619305 | 0.558905 | 0.642268 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=7:12487`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_BOREAL EXPOSURE

**Overview ID:** `risk-metrics.limit-utilization-c9681f34f7`
**Status:** available

Directional utilization for MOCK_PTF_BOREAL / MOCK_RISK_METRIC_EXPOSURE against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 74.0% (2026-06-30 effective directional limit)
- **Worst utilization:** 78.5% (maximum on 2025-12-09)
- **P95 utilization:** 77.3% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.71337 | 0.740274 | 0.668706 | 0.784644 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=8:12488`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_CEDAR VAR

**Overview ID:** `risk-metrics.limit-utilization-447e4264c2`
**Status:** available

Directional utilization for MOCK_PTF_CEDAR / MOCK_RISK_METRIC_VAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 53.3% (2026-06-30 effective directional limit)
- **Worst utilization:** 62.5% (maximum on 2026-02-02)
- **P95 utilization:** 61.4% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.60929 | 0.532528 | 0.526615 | 0.625089 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9:12489`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_CEDAR SVAR

**Overview ID:** `risk-metrics.limit-utilization-57f5b43b26`
**Status:** available

Directional utilization for MOCK_PTF_CEDAR / MOCK_RISK_METRIC_SVAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 51.6% (2026-06-30 effective directional limit)
- **Worst utilization:** 58.3% (maximum on 2025-10-16)
- **P95 utilization:** 57.3% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.565855 | 0.516498 | 0.498533 | 0.583155 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=10:12490`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_CEDAR STRESS TEST

**Overview ID:** `risk-metrics.limit-utilization-b56487fff3`
**Status:** available

Directional utilization for MOCK_PTF_CEDAR / MOCK_RISK_METRIC_STRESS against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 57.0% (2026-06-30 effective directional limit)
- **Worst utilization:** 64.2% (maximum on 2025-12-15)
- **P95 utilization:** 63.6% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.640621 | 0.569535 | 0.558819 | 0.64214 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=11:12491`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_CEDAR EXPOSURE

**Overview ID:** `risk-metrics.limit-utilization-f4585bc339`
**Status:** available

Directional utilization for MOCK_PTF_CEDAR / MOCK_RISK_METRIC_EXPOSURE against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 70.2% (2026-06-30 effective directional limit)
- **Worst utilization:** 78.4% (maximum on 2026-03-03)
- **P95 utilization:** 77.5% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.774838 | 0.701528 | 0.66917 | 0.783701 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=12:12492`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_DUNE VAR

**Overview ID:** `risk-metrics.limit-utilization-3b773136ee`
**Status:** available

Directional utilization for MOCK_PTF_DUNE / MOCK_RISK_METRIC_VAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 58.6% (2026-06-30 effective directional limit)
- **Worst utilization:** 62.5% (maximum on 2026-02-17)
- **P95 utilization:** 61.6% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.555785 | 0.586193 | 0.526572 | 0.624521 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=13:12493`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_DUNE SVAR

**Overview ID:** `risk-metrics.limit-utilization-d8ee63a009`
**Status:** available

Directional utilization for MOCK_PTF_DUNE / MOCK_RISK_METRIC_SVAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 53.7% (2026-06-30 effective directional limit)
- **Worst utilization:** 58.3% (maximum on 2026-03-09)
- **P95 utilization:** 57.3% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.538206 | 0.537379 | 0.499588 | 0.58303 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=14:12494`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_DUNE STRESS TEST

**Overview ID:** `risk-metrics.limit-utilization-f280453700`
**Status:** available

Directional utilization for MOCK_PTF_DUNE / MOCK_RISK_METRIC_STRESS against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 60.4% (2026-06-30 effective directional limit)
- **Worst utilization:** 64.2% (maximum on 2025-09-23)
- **P95 utilization:** 63.7% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.582423 | 0.60395 | 0.558739 | 0.641752 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=15:12495`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_DUNE EXPOSURE

**Overview ID:** `risk-metrics.limit-utilization-9d140e0744`
**Status:** available

Directional utilization for MOCK_PTF_DUNE / MOCK_RISK_METRIC_EXPOSURE against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 73.4% (2026-06-30 effective directional limit)
- **Worst utilization:** 78.5% (maximum on 2026-02-26)
- **P95 utilization:** 77.1% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.727292 | 0.733882 | 0.668986 | 0.784574 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=16:12496`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_ECHO VAR

**Overview ID:** `risk-metrics.limit-utilization-badd2d60ad`
**Status:** available

Directional utilization for MOCK_PTF_ECHO / MOCK_RISK_METRIC_VAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 62.3% (2026-06-30 effective directional limit)
- **Worst utilization:** 62.3% (maximum on 2026-06-30)
- **P95 utilization:** 61.1% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.588052 | 0.623051 | 0.525836 | 0.623051 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=17:12497`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_ECHO SVAR

**Overview ID:** `risk-metrics.limit-utilization-5cd135f5b3`
**Status:** available

Directional utilization for MOCK_PTF_ECHO / MOCK_RISK_METRIC_SVAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 56.3% (2026-06-30 effective directional limit)
- **Worst utilization:** 58.2% (maximum on 2026-03-24)
- **P95 utilization:** 57.5% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.550206 | 0.563006 | 0.50027 | 0.582492 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=18:12498`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_ECHO STRESS TEST

**Overview ID:** `risk-metrics.limit-utilization-3c8b40c2e1`
**Status:** available

Directional utilization for MOCK_PTF_ECHO / MOCK_RISK_METRIC_STRESS against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 63.0% (2026-06-30 effective directional limit)
- **Worst utilization:** 64.2% (maximum on 2025-07-02)
- **P95 utilization:** 63.8% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.617069 | 0.630167 | 0.558921 | 0.642269 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=19:12499`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_ECHO EXPOSURE

**Overview ID:** `risk-metrics.limit-utilization-f3f2bc1c56`
**Status:** available

Directional utilization for MOCK_PTF_ECHO / MOCK_RISK_METRIC_EXPOSURE against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 77.8% (2026-06-30 effective directional limit)
- **Worst utilization:** 78.5% (maximum on 2026-06-10)
- **P95 utilization:** 77.4% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.764729 | 0.777655 | 0.669579 | 0.785134 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=20:12500`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_FJORD VAR

**Overview ID:** `risk-metrics.limit-utilization-48abc20b6c`
**Status:** available

Directional utilization for MOCK_PTF_FJORD / MOCK_RISK_METRIC_VAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 55.4% (2026-06-30 effective directional limit)
- **Worst utilization:** 62.5% (maximum on 2026-02-09)
- **P95 utilization:** 61.3% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.569948 | 0.55382 | 0.526735 | 0.625012 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=21:12501`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_FJORD SVAR

**Overview ID:** `risk-metrics.limit-utilization-55416bd235`
**Status:** available

Directional utilization for MOCK_PTF_FJORD / MOCK_RISK_METRIC_SVAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 52.3% (2026-06-30 effective directional limit)
- **Worst utilization:** 58.3% (maximum on 2026-02-27)
- **P95 utilization:** 57.5% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.531702 | 0.523386 | 0.498071 | 0.58302 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=22:12502`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_FJORD STRESS TEST

**Overview ID:** `risk-metrics.limit-utilization-037e9375de`
**Status:** available

Directional utilization for MOCK_PTF_FJORD / MOCK_RISK_METRIC_STRESS against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 58.7% (2026-06-30 effective directional limit)
- **Worst utilization:** 64.3% (maximum on 2025-09-24)
- **P95 utilization:** 63.7% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.570504 | 0.587166 | 0.558845 | 0.642615 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=23:12503`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_FJORD EXPOSURE

**Overview ID:** `risk-metrics.limit-utilization-da51eaac72`
**Status:** available

Directional utilization for MOCK_PTF_FJORD / MOCK_RISK_METRIC_EXPOSURE against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 72.1% (2026-06-30 effective directional limit)
- **Worst utilization:** 78.3% (maximum on 2026-02-27)
- **P95 utilization:** 76.9% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.683731 | 0.720916 | 0.669109 | 0.782819 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=24:12504`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_GARNET VAR

**Overview ID:** `risk-metrics.limit-utilization-18f3278a0d`
**Status:** available

Directional utilization for MOCK_PTF_GARNET / MOCK_RISK_METRIC_VAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 60.4% (2026-06-30 effective directional limit)
- **Worst utilization:** 62.5% (maximum on 2025-11-18)
- **P95 utilization:** 61.0% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.599488 | 0.60441 | 0.526543 | 0.624926 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=25:12505`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_GARNET SVAR

**Overview ID:** `risk-metrics.limit-utilization-62bd7360d4`
**Status:** available

Directional utilization for MOCK_PTF_GARNET / MOCK_RISK_METRIC_SVAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 55.4% (2026-06-30 effective directional limit)
- **Worst utilization:** 58.2% (maximum on 2026-05-22)
- **P95 utilization:** 57.6% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.554706 | 0.553714 | 0.498099 | 0.582416 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=26:12506`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_GARNET STRESS TEST

**Overview ID:** `risk-metrics.limit-utilization-baa955a40b`
**Status:** available

Directional utilization for MOCK_PTF_GARNET / MOCK_RISK_METRIC_STRESS against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 62.7% (2026-06-30 effective directional limit)
- **Worst utilization:** 64.2% (maximum on 2026-05-22)
- **P95 utilization:** 63.6% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.618137 | 0.626821 | 0.55877 | 0.642494 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=27:12507`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_GARNET EXPOSURE

**Overview ID:** `risk-metrics.limit-utilization-ffb5790eb9`
**Status:** available

Directional utilization for MOCK_PTF_GARNET / MOCK_RISK_METRIC_EXPOSURE against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 74.3% (2026-06-30 effective directional limit)
- **Worst utilization:** 78.4% (maximum on 2025-08-12)
- **P95 utilization:** 77.2% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.746588 | 0.742621 | 0.669214 | 0.784433 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=28:12508`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_HARBOR VAR

**Overview ID:** `risk-metrics.limit-utilization-e3330d3443`
**Status:** available

Directional utilization for MOCK_PTF_HARBOR / MOCK_RISK_METRIC_VAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 57.0% (2026-06-30 effective directional limit)
- **Worst utilization:** 62.5% (maximum on 2026-03-20)
- **P95 utilization:** 61.3% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.559567 | 0.569975 | 0.525962 | 0.62458 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=29:12509`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_HARBOR SVAR

**Overview ID:** `risk-metrics.limit-utilization-6543531fa8`
**Status:** available

Directional utilization for MOCK_PTF_HARBOR / MOCK_RISK_METRIC_SVAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 52.7% (2026-06-30 effective directional limit)
- **Worst utilization:** 58.2% (maximum on 2026-02-10)
- **P95 utilization:** 57.4% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.511656 | 0.526785 | 0.498078 | 0.582106 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=30:12510`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_HARBOR STRESS TEST

**Overview ID:** `risk-metrics.limit-utilization-a5f6832620`
**Status:** available

Directional utilization for MOCK_PTF_HARBOR / MOCK_RISK_METRIC_STRESS against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 57.5% (2026-06-30 effective directional limit)
- **Worst utilization:** 64.3% (maximum on 2026-02-10)
- **P95 utilization:** 63.7% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.561289 | 0.575475 | 0.55919 | 0.642512 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=31:12511`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_HARBOR EXPOSURE

**Overview ID:** `risk-metrics.limit-utilization-24238520fc`
**Status:** available

Directional utilization for MOCK_PTF_HARBOR / MOCK_RISK_METRIC_EXPOSURE against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 68.6% (2026-06-30 effective directional limit)
- **Worst utilization:** 78.5% (maximum on 2026-06-17)
- **P95 utilization:** 77.1% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.682527 | 0.685747 | 0.668783 | 0.784556 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=32:12512`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_IVORY VAR

**Overview ID:** `risk-metrics.limit-utilization-ad629b352f`
**Status:** available

Directional utilization for MOCK_PTF_IVORY / MOCK_RISK_METRIC_VAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 58.8% (2026-06-30 effective directional limit)
- **Worst utilization:** 62.4% (maximum on 2026-03-17)
- **P95 utilization:** 61.3% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.583378 | 0.588491 | 0.527503 | 0.624023 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=33:12513`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_IVORY SVAR

**Overview ID:** `risk-metrics.limit-utilization-695b92e8b1`
**Status:** available

Directional utilization for MOCK_PTF_IVORY / MOCK_RISK_METRIC_SVAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 55.8% (2026-06-30 effective directional limit)
- **Worst utilization:** 58.3% (maximum on 2025-12-18)
- **P95 utilization:** 57.6% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.546606 | 0.557705 | 0.498163 | 0.582616 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=34:12514`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_IVORY STRESS TEST

**Overview ID:** `risk-metrics.limit-utilization-479881580c`
**Status:** available

Directional utilization for MOCK_PTF_IVORY / MOCK_RISK_METRIC_STRESS against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 61.4% (2026-06-30 effective directional limit)
- **Worst utilization:** 64.3% (maximum on 2026-01-27)
- **P95 utilization:** 63.8% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.59607 | 0.614147 | 0.55907 | 0.642549 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=35:12515`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_IVORY EXPOSURE

**Overview ID:** `risk-metrics.limit-utilization-18503a95ab`
**Status:** available

Directional utilization for MOCK_PTF_IVORY / MOCK_RISK_METRIC_EXPOSURE against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 73.9% (2026-06-30 effective directional limit)
- **Worst utilization:** 78.4% (maximum on 2026-02-05)
- **P95 utilization:** 77.5% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.721093 | 0.739103 | 0.670069 | 0.78445 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=36:12516`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_JADE VAR

**Overview ID:** `risk-metrics.limit-utilization-13059537fa`
**Status:** available

Directional utilization for MOCK_PTF_JADE / MOCK_RISK_METRIC_VAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 54.2% (2026-06-30 effective directional limit)
- **Worst utilization:** 62.4% (maximum on 2026-06-09)
- **P95 utilization:** 61.4% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.592527 | 0.541652 | 0.525898 | 0.62424 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=37:12517`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_JADE SVAR

**Overview ID:** `risk-metrics.limit-utilization-4a02a0bb45`
**Status:** available

Directional utilization for MOCK_PTF_JADE / MOCK_RISK_METRIC_SVAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 50.8% (2026-06-30 effective directional limit)
- **Worst utilization:** 58.3% (maximum on 2025-08-28)
- **P95 utilization:** 57.7% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.563675 | 0.507852 | 0.498087 | 0.583063 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=38:12518`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_JADE STRESS TEST

**Overview ID:** `risk-metrics.limit-utilization-299221633d`
**Status:** available

Directional utilization for MOCK_PTF_JADE / MOCK_RISK_METRIC_STRESS against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 55.9% (2026-06-30 effective directional limit)
- **Worst utilization:** 64.2% (maximum on 2026-05-11)
- **P95 utilization:** 63.7% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.627258 | 0.559418 | 0.559054 | 0.642291 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=39:12519`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_JADE EXPOSURE

**Overview ID:** `risk-metrics.limit-utilization-73f443ddd7`
**Status:** available

Directional utilization for MOCK_PTF_JADE / MOCK_RISK_METRIC_EXPOSURE against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 68.9% (2026-06-30 effective directional limit)
- **Worst utilization:** 78.5% (maximum on 2026-01-22)
- **P95 utilization:** 77.3% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.784665 | 0.689191 | 0.668923 | 0.784986 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=40:12520`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_KITE VAR

**Overview ID:** `risk-metrics.limit-utilization-2da437dc8b`
**Status:** available

Directional utilization for MOCK_PTF_KITE / MOCK_RISK_METRIC_VAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 56.1% (2026-06-30 effective directional limit)
- **Worst utilization:** 62.5% (maximum on 2025-10-13)
- **P95 utilization:** 61.3% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.566671 | 0.560833 | 0.526004 | 0.624812 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=41:12521`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_KITE SVAR

**Overview ID:** `risk-metrics.limit-utilization-929ffab3cd`
**Status:** available

Directional utilization for MOCK_PTF_KITE / MOCK_RISK_METRIC_SVAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 53.9% (2026-06-30 effective directional limit)
- **Worst utilization:** 58.2% (maximum on 2025-12-30)
- **P95 utilization:** 57.7% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.536817 | 0.538879 | 0.499377 | 0.581585 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=42:12522`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_KITE STRESS TEST

**Overview ID:** `risk-metrics.limit-utilization-ce02c460c1`
**Status:** available

Directional utilization for MOCK_PTF_KITE / MOCK_RISK_METRIC_STRESS against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 60.0% (2026-06-30 effective directional limit)
- **Worst utilization:** 64.2% (maximum on 2026-02-17)
- **P95 utilization:** 63.8% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.590161 | 0.599681 | 0.558751 | 0.641895 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=43:12523`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_KITE EXPOSURE

**Overview ID:** `risk-metrics.limit-utilization-e9c801ebc5`
**Status:** available

Directional utilization for MOCK_PTF_KITE / MOCK_RISK_METRIC_EXPOSURE against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 72.8% (2026-06-30 effective directional limit)
- **Worst utilization:** 78.4% (maximum on 2026-04-27)
- **P95 utilization:** 77.1% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.709267 | 0.727889 | 0.669524 | 0.783946 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=44:12524`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_LUMEN VAR

**Overview ID:** `risk-metrics.limit-utilization-2ffc4042f5`
**Status:** available

Directional utilization for MOCK_PTF_LUMEN / MOCK_RISK_METRIC_VAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 59.9% (2026-06-30 effective directional limit)
- **Worst utilization:** 62.5% (maximum on 2025-11-26)
- **P95 utilization:** 61.4% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.591892 | 0.598836 | 0.527441 | 0.624835 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=45:12525`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_LUMEN SVAR

**Overview ID:** `risk-metrics.limit-utilization-67b482f6ed`
**Status:** available

Directional utilization for MOCK_PTF_LUMEN / MOCK_RISK_METRIC_SVAR against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 56.4% (2026-06-30 effective directional limit)
- **Worst utilization:** 58.3% (maximum on 2025-07-22)
- **P95 utilization:** 57.4% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.571403 | 0.563559 | 0.498422 | 0.582887 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=46:12526`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_LUMEN STRESS TEST

**Overview ID:** `risk-metrics.limit-utilization-cd322a74b0`
**Status:** available

Directional utilization for MOCK_PTF_LUMEN / MOCK_RISK_METRIC_STRESS against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 63.7% (2026-06-30 effective directional limit)
- **Worst utilization:** 64.3% (maximum on 2026-01-05)
- **P95 utilization:** 63.7% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.626251 | 0.636657 | 0.558719 | 0.642649 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=47:12527`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

### Limit utilization — MOCK_PTF_LUMEN EXPOSURE

**Overview ID:** `risk-metrics.limit-utilization-939cf63710`
**Status:** available

Directional utilization for MOCK_PTF_LUMEN / MOCK_RISK_METRIC_EXPOSURE against the effective limit at each observation.

#### Key Metrics

- **Current utilization:** 77.7% (2026-06-30 effective directional limit)
- **Worst utilization:** 78.5% (maximum on 2025-11-06)
- **P95 utilization:** 76.9% (95th percentile of reviewed observations)
- **Breach observations:** 0 (utilization above 100%)

#### Visual Data Summary

| Series | Observations | Start | End | Minimum | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Utilization | 261 | 0.745078 | 0.776775 | 0.670659 | 0.784707 |
| Warning threshold | 261 | 0.9 | 0.9 | 0.9 | 0.9 |
| Limit | 261 | 1 | 1 | 1 | 1 |

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=48:12528`

#### Limitations

- Unlike risk metrics and units are not added or ranked by raw value.
- Utilization uses the recorded directional bound and does not establish position direction.

## Findings

### RISK-F1 — VaR limit breach on MOCK_PTF_ATLAS MOCK_PC_FLOW with 3 consecutive days above hard bound

**Severity:** high
**Confidence:** 0.95
**Period:** 2026-03-25 to 2026-03-27
**Verification:** passed

#### Observation

MOCK_LIMIT_01_01 (VaR, MEUR, upper bound 7.0) was breached on 2026-03-25, 2026-03-26, and 2026-03-27, with worst value 7.55 on 2026-03-26 (utilization 107.86%). This is a hard-bound breach population of 3 observations, confirmed by deterministic analysis.

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9169:9169`
- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9217:9217`
- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9265:9265`

#### Analysis

- Identified breach observations via deterministic limit consumption analysis.
- Calculated utilization as consoValue/limMaxValue for each date.

#### Alternative Explanations

- Market move or new activity could explain the spike.
- Limit may have been temporarily increased but not reflected in the series.

#### Counter Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9409:9409`

#### Verifier Questions

- **Can every cited row be reopened, and does it contain the stated date, hierarchy, metric, unit, limit, value, event, or workflow state?** — Yes. The three breach rows (9169, 9217, 9265) and the counter-evidence row (9409) were reopened and contain the expected fields: limId=MOCK_LIMIT_01_01, rmRiskIndicator=VAR, limUnit=MEUR, consoValueDate and consoValue as claimed, and limMaxValue=7.0 for breach rows and 9.0 for the later row.
- **Was utilization reproduced against the correct directional bound and unit?** — Yes. For each breach row, utilization = consoValue / limMaxValue. Row 9169: 7.35/7.0 = 1.05; row 9217: 7.55/7.0 = 1.0786; row 9265: 7.25/7.0 = 1.0357. The worst utilization 107.86% matches the finding.
- **Was the limit effective on the value date?** — Yes. For the breach rows, limStartDate=2025-07-01 and limEndDate=2026-03-31, covering 2026-03-25 to 2026-03-27. The counter-evidence row shows a new limit period starting 2026-04-01 with limMaxValue=9.0, so the breach period used the 7.0 bound.
- **Is the finding based solely on an outlier or statistical signal without business context?** — No. The finding is based on a hard limit breach (utilization > 1.0) for three consecutive days, which is a deterministic limit-consumption event, not merely a statistical outlier. The outlier flag (z-score 8.8) is additional context.
- **Is there contrary evidence that materially undermines the breach claim?** — The counter-evidence shows a limit increase to 9.0 effective 2026-04-01, after the breach dates. This does not negate the breach; it raises a governance question about the timing of the increase relative to the breach, which the finding appropriately flags as needing review.
- **Does the finding avoid unsupported causal or misconduct language?** — Yes. The finding states the breach factually and recommends reviewing cause and approval timing. It does not assert that the limit increase was retrospective or that misconduct occurred.
- **Is the severity calibrated to the evidence?** — Yes. A three-day hard breach with worst utilization 107.86% on a VaR limit is a material risk event, and high severity is appropriate. The finding also notes the need to confirm approval timing, which could elevate or mitigate severity.
- **Are the alternative explanations considered and appropriately qualified?** — Yes. The finding lists market move/new activity and possible temporary limit increase as alternatives, and the recommendation explicitly asks to confirm whether the limit increase was approved before the breach dates.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **pass**
Checks: Reopened all cited locators and verified fields.; Reproduced utilization calculations for all three breach rows.; Confirmed limit effective dates cover the breach period.; Verified that the counter-evidence row shows a later limit change, not a contradiction of the breach.; Checked that the finding does not overstate causation or misconduct.; Assessed severity as high, consistent with a multi-day hard breach.; evidence reopen: 3 locator(s)
Feedback: The finding is well-supported by the reopened evidence. The breach is deterministic and reproducible. The counter-evidence of a later limit increase is correctly treated as a governance question rather than a negation of the breach. Severity high is appropriate. No revision needed.

#### Recommendation

Review the cause of the breach and confirm whether the limit increase was approved before the breach dates.

### RISK-F2 — Limit increase effective before workflow approval after VaR breach on MOCK_PC_FLOW

**Severity:** high
**Confidence:** 0.80
**Period:** 2026-03-25 to 2026-04-15
**Verification:** passed

#### Observation

MOCK_LIMIT_01_01 upper bound changed from 7.0 to 9.0 effective 2026-04-01, but the associated Colibris workflow (excess 880001) has request date 2026-04-02, trader approval 2026-04-12, and risk approval 2026-04-15. The effective date precedes the recorded approvals, and the change follows a 3-day breach in late March 2026. This is a material governance candidate.

#### Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9409:9409`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=42:42`

#### Analysis

- Compared effective date from SGMR with workflow dates from Colibris.
- Identified that effective date precedes request and approval dates.

#### Alternative Explanations

- Effective date may be backdated for legitimate reasons.
- Workflow dates may be system processing dates, not approval dates.

#### Counter Evidence

- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=9169:9169`

#### Verifier Questions

- **Does the cited evidence support the claim that the limit effective date precedes the workflow request and approval dates?** — Yes. SGMR row 9409 shows limStartDate=2026-04-01 with limMaxValue=9.0. Colibris row 42 shows increaseCreationDate=2026-04-02, increaseValidationTrdDirCreationDate=2026-04-12, increaseValidationRisqCreationDate=2026-04-15. The effective date is before all three workflow milestones.
- **Is the prior breach supported by the evidence?** — Yes. The deterministic support shows a breach population with 3 observations from 2026-03-25 to 2026-03-27, worst value 7.55 against limit 7.0. The counter evidence locator row 9169 shows consoValue=7.35 on 2026-03-25 with limMaxValue=7.0.
- **Is the severity of 'high' calibrated given the evidence?** — Yes. The finding is a governance candidate: a limit increase effective before request/approval after a hard breach. Policy states such timing is normally a material governance candidate (medium or high depending on linkage and impact). The linkage is direct (same limit ID, same perimeter, same metric) and the impact is a limit increase that would have covered the breach. High severity is appropriate.
- **Are there any contrary evidence or benign explanations that would lower severity?** — The finding lists alternative explanations (backdating for legitimate reasons, system processing dates). However, no evidence in the reopened rows supports these alternatives. The workflow status is APPROVED, but the approval dates are after the effective date. The finding appropriately notes that timing alone does not prove retrospective action, but the governance candidate remains material.
- **Is the confidence of 0.8 appropriate?** — Yes. The factual comparison of dates is deterministic and reproducible. The uncertainty is about the business reason for the timing, which is not required for the governance candidate. 0.8 reflects high confidence in the observed discrepancy.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **pass**
Checks: Reopened SGMR row 9409: limStartDate=2026-04-01, limMaxValue=9.0, limInitialMaxValue=7.0.; Reopened Colibris row 42: increaseCreationDate=2026-04-02, increaseValidationTrdDirCreationDate=2026-04-12, increaseValidationRisqCreationDate=2026-04-15.; Deterministic support confirms limit_effective_before_workflow_approval candidate with same dates and prior breach observations.; Counter evidence row 9169 shows breach on 2026-03-25 with value 7.35 > limit 7.0.; Severity high is consistent with policy for effective-before-approval after breach.; Confidence 0.8 is reasonable given deterministic date comparison and unresolved business rationale.; evidence reopen: 2 locator(s)
Feedback: The finding is well-supported by the cited evidence and deterministic analysis. The effective date precedes the request and approval dates, and the prior breach is confirmed. The severity and confidence are calibrated. No revision needed.

#### Recommendation

Obtain the limit change approval and effective-date history to confirm whether the change was retrospective.

### RISK-F3 — Recurring excess events on MOCK_PC_FLOW VaR with 9 events and 2 still open

**Severity:** medium
**Confidence:** 0.90
**Period:** 2025-07-01 to 2026-04-07
**Verification:** passed

#### Observation

MOCK_PC_FLOW VaR (limit 7.0 MEUR) had 9 excess events between 2025-07-01 and 2026-04-07, with 2 still open as of 2026-06-30. Max recorded usage reached 116% (excessMaxUsage=1.16). This indicates a recurring pattern of limit breaches on this perimeter.

#### Evidence

- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=44:44`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=2:2`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=6:6`

#### Analysis

- Counted excess events per PC/indicator from Colibris.
- Used deterministic max_last_usage value.

#### Alternative Explanations

- Recurrence may reflect normal market-making activity in a volatile period.
- Some events may be duplicates or system artifacts.

#### Counter Evidence

- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=2:2`

#### Verifier Questions

- **Does the cited evidence support the claim of 9 excess events on MOCK_PC_FLOW VaR with 2 open?** — Yes. The deterministic support shows 9 events for MOCK_PC_FLOW/VAR/MEUR/limit 7.0, with 2 open events. The reopened rows include one open event (row 2) and two closed events (rows 6 and 44), consistent with the aggregate.
- **Is the maximum usage of 116% reproducible from the cited rows?** — Yes. Row 6 shows excessMaxUsage=120.28 and usage=116%, while the deterministic support reports max_last_usage=1.16. The claim states max recorded usage reached 116%, which matches the usage field and is consistent with the deterministic calculation.
- **Is the period 2025-07-01 to 2026-04-07 supported by the evidence?** — Yes. The first event (row 2) has excessCreationDate=2025-07-01 and the last event (row 44) has excessCreationDate=2026-04-07. The deterministic support lists first_created and last_created matching these dates.
- **Does the finding appropriately treat Colibris as a selected excess population rather than all risk days?** — Yes. The finding states '9 excess events' and does not claim an excess rate over all observations. The deterministic support explicitly notes 'selected excess population; denominator is not all risk days'.
- **Is the severity of medium calibrated given recurrence and open events?** — Yes. Recurring excesses (9 events) with 2 open and max usage 116% on a VaR limit is a moderate control concern. The finding does not overstate impact; it recommends investigation. Medium severity is appropriate.
- **Are there any contrary evidence or benign explanations that would undermine the finding?** — The counter evidence notes a limit type difference (RELATIVE_THRESHOLD vs ABSOLUTE_THRESHOLD) but this does not negate the recurrence. The finding includes alternative explanations such as normal market-making activity and duplicates, but the recurrence pattern remains a valid observation.
- **Is the confidence of 0.9 justified?** — Yes. The aggregate counts and usage are directly supported by deterministic analysis and reopened rows. The only uncertainty is the root cause, which is appropriately left as a recommendation.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **pass**
Checks: Reopened rows 2, 6, and 44 confirm the perimeter, metric, unit, and limit.; Deterministic support shows 9 events, 2 open, max_last_usage=1.16.; Period matches first and last creation dates.; Severity medium is consistent with recurrence and open state.; No unsupported causal claims; recommendation is investigative.; evidence reopen: 3 locator(s)

#### Recommendation

Investigate the root cause of repeated breaches and consider whether the limit level is appropriate.

### RISK-F5 — Limit increase status APPROVED without increase ID on multiple excess records

**Severity:** low
**Confidence:** 0.90
**Period:** 2025-07-01 to 2026-06-30
**Verification:** passed

#### Observation

At least 10 excess records have increaseWorkflowStatus 'APPROVED' but increaseId equals 0 (e.g., excess 590000, 590005, 590010). This is an internal consistency issue in the Colibris data.

#### Evidence

- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=2:2`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=7:7`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=12:12`

#### Analysis

- Filtered records with increaseWorkflowStatus APPROVED and increaseId=0.
- Counted occurrences from deterministic analysis.

#### Alternative Explanations

- Increase ID may be populated in a separate system not included.
- Status may be inherited from a parent limit.

#### Counter Evidence

- none

#### Verifier Questions

- **Does the cited evidence support the claim that at least 10 excess records have increaseWorkflowStatus 'APPROVED' but increaseId equals 0?** — Yes. The reopened rows 2, 7, and 12 each show increaseWorkflowStatus=APPROVED and increaseId=0. The deterministic support includes a 'limit_increase_status_without_increase_id' candidate for each of these rows, and the analysis summary indicates the condition was found across the population. The claim of at least 10 records is consistent with the deterministic screening, though the exact count is not directly shown in the provided support.
- **Is the finding's severity of 'low' appropriate for a data consistency issue?** — Yes. The finding is explicitly categorized as 'Data consistency' and does not assert a risk loss or control failure. The inconsistency is internal to Colibris and may be due to system design or missing linkage. Low severity is calibrated.
- **Are there any contrary evidence or benign explanations that would undermine the finding?** — The finding itself lists alternative explanations: increase ID may be populated in a separate system, or status may be inherited from a parent limit. These are plausible and do not contradict the observed inconsistency. No counter-evidence was found in the reopened rows.
- **Is the finding based on a reproducible deterministic calculation?** — Yes. The deterministic support includes a specific flag kind 'limit_increase_status_without_increase_id' with exact locators and values. The condition is simple and reproducible from the source.
- **Does the finding avoid unsupported causal or misconduct language?** — Yes. The finding states it is an internal consistency issue and recommends verification and correction. It does not infer intent or impact.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **pass**
Checks: Reopened evidence rows 2, 7, 12 confirm increaseWorkflowStatus=APPROVED and increaseId=0.; Deterministic support includes matching flag candidates for each cited row.; Severity is low and consistent with a data consistency observation.; Alternative explanations are acknowledged and do not negate the observed inconsistency.; No material counter-evidence found.; evidence reopen: 3 locator(s)

#### Recommendation

Verify the increase workflow data completeness and correct the mapping.

### RISK-F6 — Workflow date order mismatch on excess 880001 and 880002

**Severity:** low
**Confidence:** 0.95
**Period:** 2025-07-01 to 2026-06-30
**Verification:** passed

#### Observation

Excess records 880001 and 880002 have explanation and validation timestamps before the excess creation date, indicating a date order mismatch in the workflow data.

#### Evidence

- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=32:32`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=42:42`

#### Analysis

- Compared creation date with explanation and validation timestamps.
- Identified timestamps preceding creation date.

#### Alternative Explanations

- Creation date may be a system processing date, not the event date.
- Timestamps may be in different timezones.

#### Counter Evidence

- none

#### Verifier Questions

- **Can every cited row be reopened, and does it contain the stated date, hierarchy, metric, unit, limit, value, event, or workflow state?** — Yes. Both cited rows (32 and 42) were reopened and contain the relevant fields: excessCreationDate, lastExcessExplanationCreationDate, lastExcessValidationCreationDate, and lastExcessValidationLod2CreationDate.
- **Is the date order mismatch reproducible from the cited evidence?** — Yes. For row 32 (excessId 880002), excessCreationDate=2026-01-20T10:01:02.786, while lastExcessExplanationCreationDate=2025-07-02T18:01:02.786 and lastExcessValidationCreationDate=2025-07-02T15:01:02.786. For row 42 (excessId 880001), excessCreationDate=2026-03-27T10:01:02.786, while lastExcessExplanationCreationDate=2025-07-02T18:01:02.786 and lastExcessValidationCreationDate=2025-07-02T15:01:02.786. In both cases, explanation and validation timestamps precede the excess creation date.
- **Is the finding based solely on a single observation or outlier without population context?** — No. The finding identifies two specific records with the same date order mismatch pattern. The deterministic support also flags both rows as 'colibris_workflow_date_order_mismatch' with issues 'explanation_before_event_creation' and 'validation_before_event_creation'.
- **Is there contrary evidence that the timestamps are actually in the correct order or that the mismatch is expected?** — No contrary evidence was found in the reopened rows. The alternative explanations provided (creation date as system processing date, timezone differences) are plausible but not supported by the data. The finding appropriately lists them as alternatives.
- **Could the mismatch be explained by a benign data model or workflow design?** — Possibly, but the finding does not assert causation or misconduct. It correctly labels the issue as a data quality observation and recommends investigation. The alternative explanations are acknowledged.
- **Is the severity calibrated to the evidence and impact?** — Yes. The finding is classified as 'low' severity, which is appropriate for a data quality issue with no direct risk impact. The confidence of 0.95 is reasonable given the clear timestamp discrepancy.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **pass**
Checks: Reopened both cited locators and confirmed the presence of the relevant date fields.; Reproduced the date order mismatch: explanation and validation timestamps are before excessCreationDate in both records.; Verified that the deterministic support flags both rows with the same issue kind.; Assessed alternative explanations and found them plausible but unsupported by the data.; Confirmed severity is low and confidence is high, consistent with a data quality observation.; evidence reopen: 2 locator(s)
Feedback: The finding is well-supported by the cited evidence. The date order mismatch is clearly reproducible, and the severity and confidence are appropriate. The alternative explanations are noted but do not undermine the observation.

#### Recommendation

Investigate the timestamp semantics and correct the data.

### RISK-F7 — Cross-source limit type mismatch between Colibris and SGMR for VaR limits

**Severity:** medium
**Confidence:** 0.80
**Period:** 2025-07-01 to 2026-06-30
**Verification:** passed

#### Observation

Colibris records for MOCK_PC_FLOW and MOCK_PC_HEDGE VaR excesses show limitType 'RELATIVE_THRESHOLD', while the matched SGMR limit definitions are 'ABSOLUTE_THRESHOLD'. This discrepancy affects the interpretation of the limit type and requires confirmation.

#### Evidence

- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=2:2`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=10:10`
- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=1:1`

#### Analysis

- Matched Colibris limit definitions to SGMR by PC and indicator.
- Compared limitType fields across sources.

#### Alternative Explanations

- Colibris may describe the event trigger type, not the limit type.
- Different systems may use different terminology.

#### Counter Evidence

- none

#### Verifier Questions

- **Can every cited row be reopened, and does it contain the stated date, hierarchy, metric, unit, limit, value, event, or workflow state?** — Yes. The three cited locators were reopened and contain the relevant fields: Colibris rows 2 and 10 show limitType=RELATIVE_THRESHOLD for MOCK_PC_FLOW and MOCK_PC_HEDGE respectively, and SGMR row 1 shows limType=ABSOLUTE_THRESHOLD for MOCK_PC_FLOW. The SGMR row for MOCK_PC_HEDGE is not directly cited but the deterministic support references SGMR row 9 with the same limType.
- **Does the population cover the claimed period and every relevant portfolio, limit, risk metric, version, event state, and source family?** — The finding is a cross-source consistency observation for two specific portfolios (MOCK_PC_FLOW and MOCK_PC_HEDGE) and VaR limits. The cited evidence covers those portfolios and the relevant limit type fields. The period is not central to the claim; the mismatch is structural.
- **Is a Colibris observation being misrepresented as the population of all daily risk? State the denominator before reporting event rates.** — No. The finding does not report event rates or treat Colibris as the full daily risk population. It compares limit type definitions between two systems for specific excess events.
- **Are derived LLM_Explanation_* tags being used as independent evidence?** — No. The finding relies on the limitType field in Colibris and limType in SGMR, not on LLM-generated tags.
- **Is the metric definition known: horizon, confidence level, methodology, stress scenario and sign, exposure type, sensitivity shock, currency, and scale?** — The finding does not require full metric definition; it concerns the limit type classification. The metric is VaR, unit MEUR, and the limit type mismatch is the focus.
- **Is the analysis at a stable desk hierarchy and metric grain? Check mapping changes and do not merge unlike portfolios or metric definitions.** — Yes. The comparison is done per PC (MOCK_PC_FLOW and MOCK_PC_HEDGE) and risk indicator VAR. No merging of unlike portfolios or metrics is performed.
- **Are raw VaR, SVaR, stress, exposure, or sensitivity values being added or compared as though they were interchangeable?** — No. The finding compares limit type labels, not raw risk values.
- **Does a factor or portfolio concentration calculation use an additive measure and a complete population?** — Not applicable; no concentration calculation is performed.
- **Does the result explain what risk it represents for this desk, rather than repeat a high value without portfolio, factor, scenario, or limit context?** — The finding explains that the limit type mismatch affects interpretation of the limit for VaR on two portfolios. It does not discuss risk magnitude but the governance/definitional aspect.
- **Was utilization reproduced against the correct directional bound and unit?** — Not applicable; the finding does not compute utilization.
- **Was the limit effective on the value date?** — The SGMR row shows limStartDate=2025-07-01 and limEndDate=2026-03-31, which covers the Colibris event dates (2025-07-01 and 2025-08-26). The limit type is a static attribute, so effectiveness is not central.
- **Was a warning threshold confused with a hard limit, or a temporary/initial bound used without valid precedence and effective dates?** — No. The finding is about limit type classification, not threshold values.
- **Is a current-versus-initial difference presented only as a change candidate?** — Not applicable; no limit change is claimed.
- **For breach or proximity claims, are the count, worst and current utilization, first and last dates, longest streak, and affected series reproducible?** — Not applicable; no breach or proximity claim is made.
- **Does a repeated streak survive duplicate removal, missing dates, limit changes, and observations that are consecutive only because of an extract gap?** — Not applicable.
- **Is the outlier, jump, trend, level shift, or volatility change calculated within one comparable portfolio/metric/unit/version series with an adequate population?** — Not applicable; no statistical behavior analysis is performed.
- **Is a single observation being called systemic?** — No. The finding notes a discrepancy for two portfolios, but does not generalize to all limits.
- **Could the pattern reflect a market move, new or closed business, model/version change, hierarchy remap, hedging, expiry, rebalancing, data delay, or scenario update?** — The limit type mismatch is a static definitional difference, not a market-driven pattern. The alternative explanations provided (different terminology, event trigger vs limit type) are plausible and acknowledged.
- **Are VaR/SVaR or stress/VaR comparisons aligned by date and portfolio, and are their methodology differences clearly qualified?** — Not applicable.
- **Is a statistical threshold being confused with desk materiality?** — No. The finding is not based on a statistical threshold.
- **Does the record itself support that it is open, closed, validated, satisfactory, or manually closed?** — Not applicable; the finding does not rely on workflow state.
- **Is usage reproduced from value and limit within stated rounding, and is excessMaxUsage at least as severe as the recorded last consumption?** — Not applicable; the finding does not discuss usage.
- **Are creation, explanation, validation, LoD2, deadline, and closure timestamps ordered logically?** — Not applicable.
- **Is a timeliness conclusion based on a documented SLA, business calendar, timezone, and event class?** — Not applicable.
- **For an apparently overdue open item, is the extract's as-of state current, and is there later closure, accepted risk, waiver, or superseding event evidence?** — Not applicable.
- **Are repeated events genuinely comparable by perimeter, metric, limit, underlying, cause, and time, or are unrelated excesses being collapsed into one pattern?** — The finding compares two events from different portfolios but the same metric and limit type. The comparison is appropriate for a cross-source consistency check.
- **Are explanation, action, owner, deadline, validation, and LoD2 fields required for this workflow state and classification?** — Not applicable.
- **For a limit increase, do the ID, requested bound, effective date, trader/risk approval, and relationship to the excess all exist?** — Not applicable; no limit increase is claimed.
- **Do limit definitions agree on PC/perimeter, risk indicator, metric name, unit, bound, type, owner, and relevant date?** — The finding specifically identifies a disagreement on limit type: Colibris says RELATIVE_THRESHOLD, SGMR says ABSOLUTE_THRESHOLD. Other fields (PC, indicator, unit, bound) appear consistent.
- **Does the claimed event-to-SGMR match use a documented unique key?** — The finding does not claim a row-level event-to-SGMR match; it compares limit definitions at the PC/indicator level. The deterministic support notes that event-to-row reconciliation is UNRESOLVED, but that does not undermine the limit type comparison.
- **Is a missing daily match explained by weekend/holiday dates, review-period boundaries, source cadence, or an actual in-period business-date gap?** — Not applicable; no daily match is required for this finding.
- **Does another source contradict the conclusion or provide a benign explanation such as approved business, a temporary limit, hedge, market event, or resolved action?** — No contradicting source is provided. The alternative explanations (different terminology, event trigger vs limit type) are plausible and are included in the finding.
- **Is severity proportionate to utilization, duration, recurrence, scope, regulatory or capital consequence, open control state, and evidence strength?** — The severity is medium. The mismatch affects interpretation of limit type for two portfolios and could have governance implications, but it is not a breach or loss. Medium seems proportionate given the need for clarification.
- **Is causation or intent inferred from timing, co-movement, machine-generated text, or missing evidence?** — No. The finding does not infer causation or intent; it reports a factual discrepancy and recommends clarification.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **pass**
Checks: Reopened all cited locators and confirmed the limit type values.; Verified that the finding is an observation of a definitional mismatch, not a statistical or causal claim.; Confirmed that the alternative explanations are appropriately included and do not undermine the observation.; Checked that severity is calibrated to medium, consistent with a governance/definitional issue without direct risk impact.; Ensured no unsupported causal language or inflated severity.; evidence reopen: 3 locator(s)
Feedback: The finding is well-supported by the cited evidence. The limit type mismatch is clearly documented and the recommendation to clarify terminology is appropriate. The severity of medium is reasonable given the potential governance impact but lack of direct risk loss. No revision needed.

#### Recommendation

Clarify the meaning of limitType in each system and align definitions.

### RISK-F8 — Event-to-SGMR row reconciliation unresolved due to missing unique bridge

**Severity:** info
**Confidence:** 0.90
**Period:** 2025-07-01 to 2026-06-30
**Verification:** passed

#### Observation

Only 25 of 50 Colibris events have semantic date matches with SGMR rows, and no unique direct ID matches exist. The event-to-observation reconciliation is UNRESOLVED because a unique source-backed sgmrId bridge is required.

#### Evidence

- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=2:2`
- `source://risk_metrics/SGMR_consumption_combined_2025-07-01-2026-06-30.parquet#rows=1:1`

#### Analysis

- Attempted to match Colibris events to SGMR rows using semantic dates.
- Checked for unique ID matches; none found.

#### Alternative Explanations

- Semantic matching may be ambiguous because one PC maps to multiple portfolios.
- Weekend/holiday dates may legitimately lack SGMR rows.

#### Counter Evidence

- none

#### Verifier Questions

- **Does the cited evidence support the claim that only 25 of 50 Colibris events have semantic date matches with SGMR rows and no unique direct ID matches exist?** — Yes. The reopened Colibris row shows sgmrId=MOCK_SGMR_1001, but the SGMR row does not contain a matching sgmrId field; the SGMR row has limId, consoId, id, etc. The deterministic support summary states 'Matched 10/10 Colibris limit-definition variant(s) to SGMR and found 25/50 semantic date match(es); event-to-row reconciliation is UNRESOLVED.' This supports the claim.
- **Is the reconciliation genuinely unresolved due to missing unique bridge, or could it be resolved with available fields?** — The SGMR row does not include a sgmrId column, so a direct unique ID match is impossible. Semantic matching by date yields only 25/50 matches, leaving the rest unmatched. The finding correctly states that a unique source-backed sgmrId bridge is required.
- **Are the alternative explanations (semantic ambiguity, weekend/holiday dates) adequately considered?** — Yes, the finding lists both as alternative explanations. The deterministic support also notes 'selected excess population; denominator is not all risk days' and 'confirm extract freshness and later closure before escalation', indicating awareness of limitations.
- **Is the severity 'info' appropriate for a reconciliation gap?** — Yes. The finding is an observation about data linkage limitations, not a risk or control failure. 'info' severity is calibrated.
- **Is the confidence 0.9 justified?** — Yes. The claim is based on deterministic matching results and the absence of a unique ID field in the SGMR schema. Confidence is high.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **pass**
Checks: Reopened both cited locators and confirmed the Colibris row contains sgmrId while the SGMR row does not.; Verified the deterministic support summary matches the claim: 25/50 semantic date matches, no unique ID matches.; Confirmed the finding does not overstate the impact; it is an observation about reconciliation limitations.; Checked that the finding does not infer causation or misconduct from the missing bridge.; Severity and confidence are appropriate for an informational reconciliation gap.; evidence reopen: 2 locator(s)

#### Recommendation

Obtain a documented unique ID bridge between Colibris and SGMR to enable event-level reconciliation.

### RISK-F4 — Open excess events past recorded deadlines on multiple perimeters

**Severity:** medium
**Confidence:** 0.85
**Period:** 2025-07-01 to 2026-06-30
**Verification:** unresolved

#### Observation

At least three excess events remain open as of 2026-06-30 with both explanation action deadlines and technical deadlines in the past (e.g., excess 590000 created 2025-07-01 with deadlines 2025-07-08 and 2025-07-15). This suggests unresolved or stale control items.

#### Evidence

- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=2:2`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=9:9`
- `source://risk_metrics/Filtered_Colibris_All_Maket_Excesses_with_llm_tags.csv#rows=16:16`

#### Analysis

- Identified open excess events with past deadlines from deterministic analysis.
- Confirmed as-of date 2026-06-30 from analysis context.

#### Alternative Explanations

- Extract may be stale; events may have been closed after the as-of date.
- Deadlines may be system-generated and not contractual SLAs.

#### Counter Evidence

- none

#### Verifier Questions

- **Can every cited row be reopened, and does it contain the stated date, hierarchy, metric, unit, limit, value, event, or workflow state?** — Yes, all three cited rows were reopened and contain the relevant fields: excessId, creation date, open status, deadlines, and workflow state.
- **Does the record itself support that it is open, closed, validated, satisfactory, or manually closed? Reconcile boolean, status, close dates, and validation fields.** — Yes, each row has excessStillOpen=True and excessWorkflowStatus=OPEN, with empty excessCloseDate, supporting the open state as of the extract.
- **Are creation, explanation, validation, LoD2, deadline, and closure timestamps ordered logically? Distinguish data inconsistency from policy breach.** — The timestamps are logically ordered: creation before explanation/validation, and deadlines after those dates. No inconsistency in ordering.
- **Is a timeliness conclusion based on a documented SLA, business calendar, timezone, and event class? Otherwise report the measured lag without calling it late.** — The finding does not assert a policy breach; it reports that deadlines are in the past relative to the as-of date. It appropriately frames this as a candidate for stale/unresolved control items, not a definitive SLA violation.
- **For an apparently overdue open item, is the extract's as-of state current, and is there later closure, accepted risk, waiver, or superseding event evidence?** — The finding acknowledges the extract may be stale and recommends confirming freshness and obtaining closure evidence. The as-of date is 2026-06-30, but no later closure evidence is provided.
- **Is severity proportionate to utilization, duration, recurrence, scope, regulatory or capital consequence, open control state, and evidence strength?** — Severity is medium, which is reasonable given multiple open events across different perimeters and metrics, but the lack of confirmed extract freshness and absence of SLA context tempers the severity. Medium is acceptable but could be revised if extract is stale.
- **Is causation or intent inferred from timing, co-movement, machine-generated text, or missing evidence?** — No, the finding does not infer causation or intent; it only notes the open state and past deadlines.

#### Analyst Response

n/a

#### Verifier Conclusion

Decision: **unresolved**
Checks: Reopened all three cited locators and confirmed they contain the stated open status and past deadlines.; Verified that the deterministic support includes matching open_excess_past_recorded_deadline candidates for rows 2, 9, and 16.; Confirmed that the finding's claim of at least three open events with past deadlines is supported by the evidence.; Noted that the finding appropriately includes alternative explanations (stale extract, non-contractual deadlines) and recommends confirmation.; Checked that the severity is medium, which is calibrated given the uncertainty about extract freshness and lack of SLA definition.; evidence reopen: 3 locator(s)
Feedback: Verifier rounds exhausted; marked UNRESOLVED. The finding is well-supported by the cited evidence and deterministic analysis. However, to strengthen it, consider adding the exact as-of date of the extract and any available metadata about its freshness. Also, clarify whether the deadlines are contractual SLAs or system-generated targets, as this affects the governance implication. The severity is appropriate as medium, but if the extract is confirmed current and the deadlines are contractual, severity could be raised to high.

#### Recommendation

Confirm extract freshness and obtain closure evidence for these open events.

## Unresolved Items

- RISK-F4 — Open excess events past recorded deadlines on multiple perimeters: Verifier rounds exhausted; marked UNRESOLVED. The finding is well-supported by the cited evidence and deterministic analysis. However, to strengthen it, consider adding the exact as-of date of the extract and any available metadata about its freshness. Also, clarify whether the deadlines are contractual SLAs or system-generated targets, as this affects the governance implication. The severity is appropriate as medium, but if the extract is confirmed current and the deadlines are contractual, severity could be raised to high.

## Overall Conclusion

Risk Metrics review completed: 7 finding(s) verified, 0 rejected, 1 unresolved. Top findings: RISK-F1 (high): VaR limit breach on MOCK_PTF_ATLAS MOCK_PC_FLOW with 3 consecutive days above hard bound; RISK-F2 (high): Limit increase effective before workflow approval after VaR breach on MOCK_PC_FLOW; RISK-F3 (medium): Recurring excess events on MOCK_PC_FLOW VaR with 9 events and 2 still open.
