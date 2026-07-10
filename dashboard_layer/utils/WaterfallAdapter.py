import json
import plotly.graph_objects as go

class WaterfallAdapter:
    def __init__(self, config_path="core/mapping/config.json"):
        with open(config_path, "r") as f:
            self.mapping_config = json.load(f)

    def process(self, indicator_key: str, metric_records: list) -> dict:
        """
        Prepare Waterfall chart data for a specific indicator.
        Shows how each metric contributes to the INSTANTANEOUS score.

        Note: The final displayed score in the dashboard is usually smoothed (EMA).
        This waterfall explains the *current day's raw contribution* S_i(t).

        Args:
            indicator_key: The key of the indicator (e.g., "1_depressed_mood")
            metric_records: List of AnalyzedMetricRecord (dicts or objects)
        """

        if indicator_key not in self.mapping_config:
            return None

        details = self.mapping_config[indicator_key]
        metrics_config = details.get("metrics", {})

        # Quick lookup for metric values
        metric_lookup = {
            m['metric_name'] if isinstance(m, dict) else m.metric_name:
            m['analyzed_value'] if isinstance(m, dict) else m.analyzed_value
            for m in metric_records
        }

        measures = ["relative"] * len(metrics_config) + ["total"]
        x_labels = []
        y_values = []
        text_values = []

        total_score = 0.0

        for metric_name, props in metrics_config.items():
            weight = props['weight']
            if weight == 0: continue

            direction = props['direction']
            z_hat = metric_lookup.get(metric_name, 0.0)
            if z_hat is None: z_hat = 0.0

            # Logic from derive_indicator_scores (Eq 3)
            contribution = 0.0
            if direction == "positive":
                contribution = z_hat
            elif direction == "negative":
                contribution = -z_hat
            elif direction == "both" or direction == "anomaly":
                contribution = abs(z_hat)

            weighted_contribution = contribution * weight

            x_labels.append(metric_name)
            y_values.append(weighted_contribution)
            text_values.append(f"{weighted_contribution:+.2f}")

            total_score += weighted_contribution

        # Add Total
        x_labels.append("Total Impact")
        y_values.append(total_score)
        text_values.append(f"{total_score:.2f}")

        # Format for Plotly
        # Waterfall requires:
        # y: [val1, val2, ..., total] (deltas, then final total)
        # But Plotly Waterfall 'y' expects the *delta* for relative, and *value* for total.
        # Yes, we populated y_values correctly above (contributions, then total sum).

        return {
            "name": "Feature Contribution",
            "orientation": "v",
            "measure": measures,
            "x": x_labels,
            "textposition": "outside",
            "text": text_values,
            "y": y_values,
            "connector": {"line": {"color": "rgb(63, 63, 63)"}},
        }
