import pandas as pd
from upsetplot import UpSet, from_memberships
import matplotlib.pyplot as plt

metric_categories = {
    "Formant F1-F2": ["(1) Depressed Mood"],
    "SNR": ["(1) Depressed Mood"],
    "F0 average": [
        "(1) Depressed Mood",
        "(3) Significant Weight Changes",
        "(5) Psychomotor Retardation & Agitation",
    ],
    "F0 std": [
        "(1) Depressed Mood",
        "(2) Loss of Interest",
        "(5) Psychomotor Retardation & Agitation",
        "(8) Diminished Ability to Think or Concentrate",
    ],
    "F0 range": [
        "(2) Loss of Interest",
        "(8) Diminished Ability to Think or Concentrate",
    ],
    "Spectral flatness (SF)": [
        "(1) Depressed Mood",
        "(5) Psychomotor Retardation & Agitation",
    ],
    "Speech rate": ["(1) Depressed Mood", "(5) Psychomotor Retardation & Agitation"],
    "Articulation rate": [
        "(1) Depressed Mood",
        "(5) Psychomotor Retardation & Agitation",
    ],
    "Pause duration": [
        "(1) Depressed Mood",
        "(5) Psychomotor Retardation & Agitation",
        "(8) Diminished Ability to Think or Concentrate",
    ],
    "Pause frequency": [
        "(1) Depressed Mood",
        "(5) Psychomotor Retardation & Agitation",
        "(8) Diminished Ability to Think or Concentrate",
    ],
    "Vowel space area (VSA)": [
        "(1) Depressed Mood",
        "(5) Psychomotor Retardation & Agitation",
    ],
    "Formant F2 transition speed": [
        "(1) Depressed Mood",
        "(5) Psychomotor Retardation & Agitation",
    ],
    "Jitter": [
        "(1) Depressed Mood",
        "(2) Loss of Interest",
        "(3) Significant Weight Changes",
        "(5) Psychomotor Retardation & Agitation",
        "(8) Diminished Ability to Think or Concentrate",
    ],
    "Shimmer": [
        "(1) Depressed Mood",
        "(2) Loss of Interest",
        "(3) Significant Weight Changes",
        "(5) Psychomotor Retardation & Agitation",
        "(8) Diminished Ability to Think or Concentrate",
    ],
    "Volume intensity range": [
        "(2) Loss of Interest",
        "(8) Diminished Ability to Think or Concentrate",
    ],
    "Volume intensity std": [
        "(2) Loss of Interest",
        "(8) Diminished Ability to Think or Concentrate",
    ],
    "HNR": ["(3) Significant Weight Changes", "(4) Insomnia & Hypersomnia"],
    "Temporal modulations (2-8 Hz)": [
        "(4) Insomnia & Hypersomnia",
        "(6) Fatigue & Loss of Energy",
    ],
    "Spectral modulations (2 cyc/oct)": [
        "(4) Insomnia & Hypersomnia",
        "(6) Fatigue & Loss of Energy",
    ],
    "Voice onset time (VOT)": ["(5) Psychomotor Retardation & Agitation"],
    "Pulse (glottal pulses)": ["(8) Diminished Ability to Think or Concentrate"],
    "PSD_4": ["(9) Recurrent Thoughts of Death or being Suicidal"],
    "PSD_5": ["(9) Recurrent Thoughts of Death or being Suicidal"],
    "PSD_7": ["(9) Recurrent Thoughts of Death or being Suicidal"],
    "Voiced-to-silence transition (t_13)": [
        "(9) Recurrent Thoughts of Death or being Suicidal"
    ],
    "Voiced16:20 interval PDF": ["(9) Recurrent Thoughts of Death or being Suicidal"],
}

membership_list = [frozenset(v) for v in metric_categories.values()]
metric_names = list(metric_categories.keys())

membership_df = pd.DataFrame({"membership": membership_list})
counts = membership_df.value_counts().reset_index()
counts.columns = ["membership", "count"]

data = from_memberships(counts["membership"], data=counts["count"])

all_indicators = sorted(
    {ind for indicators in metric_categories.values() for ind in indicators}
)

plt.figure(figsize=(12, 6))
UpSet(
    data,
    show_counts=True,
    show_percentages=True,
    sort_by="cardinality",
    sort_categories_by=None,
).plot()

plt.suptitle("Voice Metrics Intersections by DSM-5 Indicators", fontsize=16)
plt.tight_layout()
plt.show()
