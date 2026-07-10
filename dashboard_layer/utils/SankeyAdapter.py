import pandas as pd
import json
import plotly.graph_objects as go

# Import theme colors if available, fallback to defaults
try:
    from utils.theme import COLORS
except ImportError:
    COLORS = {
        "danger": "#E74C3C",
        "warning": "#F39C12",
        "success": "#27AE60",
        "border": "#DEE2E6",
    }


class SankeyAdapter:
    def __init__(self, config_path="core/mapping/config.json"):
        with open(config_path, "r") as f:
            self.mapping_config = json.load(f)

    def _get_pretty_name(self, key):
        if key == "mdd_support": return "Elevated Patterns"
        if key == "no_support": return "Monitoring" # Or "Healthy"

        parts = key.split('_', 1)
        clean_name = parts[1].replace('_', ' ').title() if len(parts) > 1 else key

        # Shorten specific ones
        if "Psychomotor" in clean_name: clean_name = "Psychomotor Retardation"
        if "Diminished" in clean_name: clean_name = "Concentration Loss"
        if "Recurrent" in clean_name: clean_name = "Suicidal Ideation"
        if "Significant Weight" in clean_name: clean_name = "Weight Change"
        if "Insomnia" in clean_name: clean_name = "Sleep Disturbance"

        return clean_name

    def process(self, indicator_records_df: pd.DataFrame):
        """
        Process indicator records into a Sankey diagram structure.
        Groups data by week and determines the dominant state.
        """
        if indicator_records_df.empty:
            return None

        # 1. Prepare Data
        df = indicator_records_df.copy()
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Handle missing mdd_signal (backward compatibility)
        if 'mdd_signal' not in df.columns:
            df['mdd_signal'] = False

        # Flatten indicator_scores
        indicators_df = pd.concat(
            [
                df[['timestamp', 'mdd_signal']],
                df['indicator_scores'].apply(pd.Series)
            ],
            axis=1
        )

        # 2. Resample by Week (W-MON)
        # We aggregate: mean of scores, mode/mean of mdd_signal
        weekly = indicators_df.resample('W-MON', on='timestamp').mean()

        # Note: mdd_signal is boolean, mean gives proportion of days active
        # If > 0.5, we consider it Active for the week
        weekly_mdd = indicators_df[['timestamp', 'mdd_signal']].resample('W-MON', on='timestamp').mean()

        # 3. Determine State for each Week
        states = []
        severities = [] # This will be the link width
        dates = []

        indicator_cols = [c for c in indicators_df.columns if c not in ['timestamp', 'mdd_signal']]

        for date, row in weekly.iterrows():
            mdd_prop = weekly_mdd.loc[date, 'mdd_signal'] if date in weekly_mdd.index else 0

            # Calculate Total Severity (Sum of all indicator scores)
            # This represents the "Width" of the band
            total_severity = sum([row[c] for c in indicator_cols if pd.notnull(row[c])])

            # Determine Label
            label = "no_support"

            if mdd_prop >= 0.5:
                label = "mdd_support"
            else:
                # Find max indicator
                max_ind = None
                max_val = -1
                for col in indicator_cols:
                    val = row[col]
                    if pd.notnull(val) and val > max_val:
                        max_val = val
                        max_ind = col

                # Threshold for "Dominant Symptom" - let's say 0.5 (from config default)
                if max_ind and max_val >= 0.5:
                    label = max_ind
                else:
                    label = "no_support"

            states.append(label)
            severities.append(max(total_severity, 0.5)) # Ensure min width
            dates.append(date)

        # 4. Build Sankey Data
        # Nodes: We need unique (Step, Label) nodes to show progression
        # Actually, Plotly Sankey takes a list of labels for all nodes.
        # We'll create nodes like "Week 1: Label", "Week 2: Label"

        node_labels = []
        node_colors = []
        source = []
        target = []
        value = []

        # Helper to get/create node index
        # We want nodes to be distinct per week to allow "A" -> "A" flow
        # So Node ID = (WeekIndex, Label)

        # Let's flatten this.
        # Node indices will be sequential.

        for i in range(len(states)):
            week_label = f"Week {i+1}"
            pretty_name = self._get_pretty_name(states[i])
            full_label = f"{week_label}<br>{pretty_name}"

            node_labels.append(full_label)

            # Color based on state
            if states[i] == "mdd_support":
                node_colors.append(COLORS["danger"])
            elif states[i] == "no_support":
                node_colors.append(COLORS["success"])
            else:
                node_colors.append(COLORS["warning"])  # Symptom

            if i > 0:
                # Link from prev to current
                source.append(i - 1)
                target.append(i)
                # Value is the severity of the *source* (or average of transition?)
                # Let's use the current severity to show "arriving" magnitude
                value.append(severities[i])

        return {
            "node": {
                "pad": 15,
                "thickness": 20,
                "line": {"color": "black", "width": 0.5},
                "label": node_labels,
                "color": node_colors
            },
            "link": {
                "source": source,
                "target": target,
                "value": value,
                # Gradient color? Or semi-transparent grey
                "color": ["rgba(100, 100, 100, 0.4)"] * len(source)
            }
        }
