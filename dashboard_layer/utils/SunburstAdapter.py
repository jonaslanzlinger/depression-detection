import json
import pandas as pd

# Import theme colors if available, fallback to defaults
try:
    from utils.theme import COLORS, INDICATOR_COLORS
except ImportError:
    COLORS = {
        "danger": "#E74C3C",
        "warning": "#F39C12",
        "success": "#27AE60",
        "inactive": "#BDC3C7",
        "text_secondary": "#7F8C8D",
    }
    INDICATOR_COLORS = {}


class SunburstAdapter:
    def __init__(self, config_path="core/mapping/config.json"):
        """
        Initialize with the mapping config to understand the hierarchy.
        """
        with open(config_path, "r") as f:
            self.mapping_config = json.load(f)

    def process(self, indicator_record: dict, metric_records: list) -> dict:
        """
        Transform flat records into Plotly Sunburst format.

        Args:
            indicator_record: Dict containing the final DSM-5 scores (e.g., {'1_depressed_mood': 1.5})
            metric_records: List of dicts or objects containing 'metric_name' and 'analyzed_value' (Z-scores)

        Returns:
            Dict containing 'ids', 'labels', 'parents', 'values', 'colors', 'customdata' for Plotly.
        """

        # --- 1. Pre-process Inputs ---
        # Convert list of metrics to a quick lookup dict: { 'jitter': 2.3, ... }
        metric_lookup = {
            m['metric_name'] if isinstance(m, dict) else m.metric_name:
            m['analyzed_value'] if isinstance(m, dict) else m.analyzed_value
            for m in metric_records
        }

        # Clean indicator keys (remove "1_", "2_" prefixes for display)
        indicators = indicator_record.get('indicator_scores', {})

        # --- 2. Calculate Center (MDD Support Status) ---
        # Logic: >= 5 symptoms active, AND (Ind 1 OR Ind 2 is active)
        active_count = 0
        core_symptom_active = False

        for key, score in indicators.items():
            # Treat None as 0
            if score is None: score = 0

            # Use specific threshold from config or default to 0.5
            # Skip metadata keys whose values are not dicts (e.g. _comment, _version)
            cfg_entry = self.mapping_config.get(key, {})
            threshold = cfg_entry.get('severity_threshold', 0.5) if isinstance(cfg_entry, dict) else 0.5

            if score >= threshold:
                active_count += 1
                if key.startswith("1_") or key.startswith("2_"):
                    core_symptom_active = True

        if active_count >= 5 and core_symptom_active:
            center_label = "<b>ELEVATED<br>PATTERNS</b>"
            center_color = COLORS["danger"]
        elif active_count > 0:
            center_label = "<b>SOME ELEVATED<br>SIGNALS</b>"
            center_color = COLORS["warning"]
        else:
            center_label = "<b>WITHIN TYPICAL<br>RANGE</b>"
            center_color = COLORS["success"]

        # --- 3. Build Plotly Lists ---
        ids = ["root"]
        labels = [center_label]
        parents = [""]
        values = [0.0] # Placeholder for root value
        colors = [center_color]
        customdata = [0.0] # Custom data for root

        total_root_value = 0.0

        # Iterate through DSM-5 Indicators (Inner Ring)
        # Skip metadata keys (string values or underscore-prefixed keys like _comment, _version)
        for ind_key, ind_details in self.mapping_config.items():
            if not isinstance(ind_details, dict) or ind_key.startswith('_'):
                continue

            # Prepare Label
            parts = ind_key.split('_', 1)
            clean_name = parts[1].replace('_', ' ').title() if len(parts) > 1 else ind_key

            # Shorten long names for UI readability
            if "Psychomotor" in clean_name: clean_name = "Psychomotor"
            if "Diminished" in clean_name: clean_name = "Concentration"
            if "Recurrent" in clean_name: clean_name = "Suicidal Ideation"
            if "Significant Weight" in clean_name: clean_name = "Weight Change"

            ind_score = indicators.get(ind_key, 0)
            if ind_score is None: ind_score = 0

            # Determine Parent Value (Indicator Size)
            # Ensure it has some size even if 0 so it appears in the chart
            parent_value = max(ind_score, 0.5)
            total_root_value += parent_value

            # ID Strategy: root -> indicator
            node_id = f"root - {ind_key}"

            ids.append(node_id)
            labels.append(f"{clean_name}<br>({ind_score:.1f})")
            parents.append("root")
            values.append(parent_value)
            customdata.append(ind_score) # Real score for hover

            # Determine threshold
            threshold = ind_details.get('severity_threshold', 0.5)

            # Color logic: Use indicator-specific color if active, inactive grey otherwise
            ind_color = INDICATOR_COLORS.get(ind_key, COLORS["danger"])
            colors.append(ind_color if ind_score >= threshold else COLORS["inactive"])

            # Collect Children (Metrics)
            children_data = []
            metrics = ind_details.get('metrics', {})

            for metric_name, props in metrics.items():
                weight = props['weight']
                if weight == 0: continue

                z_score = metric_lookup.get(metric_name, 0)
                if z_score is None: z_score = 0

                # Calculate raw size (absolute z-score)
                raw_size = abs(z_score) if abs(z_score) > 0.1 else 0.1

                # Color logic: Danger for high contribution, secondary for normal
                child_color = COLORS["danger"] if abs(z_score) > 2.0 else COLORS["text_secondary"]

                children_data.append({
                    'id': f"{node_id} - {metric_name}",
                    'label': f"{metric_name}", # Simplified label, value in hover
                    'raw_size': raw_size,
                    'z_score': z_score,
                    'color': child_color
                })

            # Normalize children values to sum exactly to parent_value
            children_sum = sum(c['raw_size'] for c in children_data)

            if children_sum > 0:
                factor = parent_value / children_sum
            else:
                # If no children or all zero (shouldn't happen with 0.1 min),
                # we just don't append children or factor is 0
                factor = 0

            for child in children_data:
                ids.append(child['id'])
                labels.append(child['label'])
                parents.append(node_id)
                values.append(child['raw_size'] * factor) # Normalized value
                colors.append(child['color'])
                customdata.append(child['z_score']) # Real z-score for hover

        # Update Root Value
        values[0] = total_root_value if total_root_value > 0 else 1.0

        return {
            "ids": ids,
            "labels": labels,
            "parents": parents,
            "values": values,
            "colors": colors,
            "customdata": customdata
        }
