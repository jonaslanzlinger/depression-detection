import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

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

rows = []
indicator_order = []
for metric, indicators in metric_categories.items():
    for ind in indicators:
        rows.append((metric, ind))
        if ind not in indicator_order:
            indicator_order.append(ind)
indicator_order.append("(7) Feelings of Worthlessness & Guilt")

df = pd.DataFrame(rows, columns=["Metric", "Indicator"])
df = pd.concat(
    [
        df,
        pd.DataFrame(
            [("__dummy__", "(7) Feelings of Worthlessness & Guilt")],
            columns=["Metric", "Indicator"],
        ),
    ]
)

heatmap_df = df.pivot_table(
    index="Metric", columns="Indicator", aggfunc=lambda x: 1, fill_value=0
)

heatmap_df = heatmap_df.drop(index="__dummy__")

heatmap_df = heatmap_df.reindex(index=metric_categories.keys())
heatmap_df = heatmap_df.reindex(columns=sorted(heatmap_df.columns))

plt.figure(figsize=(14, 12))
sns.heatmap(
    heatmap_df, cmap="Greys", cbar=False, linewidths=0.5, linecolor="gray", square=True
)
plt.title("Voice Metrics Mapping to DSM-5 Indicators", fontsize=16)
plt.xlabel("DSM-5 Indicators")
plt.ylabel("Voice Metrics")
plt.xticks(rotation=45, ha="right")
plt.yticks(rotation=0)
plt.tight_layout(rect=[0, 0.05, 1, 1])
plt.show()
