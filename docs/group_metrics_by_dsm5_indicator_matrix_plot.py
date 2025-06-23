import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

metric_categories = {
    "F1 / F2 formants": ["(1) Depressed mood"],
    "SNR": ["(1) Depressed mood"],
    "F0 average": [
        "(1) Depressed mood",
        "(3) Significant weight changes",
        "(5) Psychomotor retardation / agitation",
    ],
    "F0 std": [
        "(1) Depressed mood",
        "(2) Loss of interest",
        "(5) Psychomotor retardation / agitation",
        "(8) Diminished ability to think / concentrate",
    ],
    "F0 range": [
        "(2) Loss of interest",
        "(8) Diminished ability to think / concentrate",
    ],
    "SF": [
        "(1) Depressed mood",
        "(5) Psychomotor retardation / agitation",
    ],
    "Speech rate": ["(1) Depressed mood", "(5) Psychomotor retardation / agitation"],
    "Articulation rate": [
        "(1) Depressed mood",
        "(5) Psychomotor retardation / agitation",
    ],
    "Pause duration": [
        "(1) Depressed mood",
        "(5) Psychomotor retardation / agitation",
        "(8) Diminished ability to think / concentrate",
    ],
    "Pause frequency": [
        "(1) Depressed mood",
        "(5) Psychomotor retardation / agitation",
        "(8) Diminished ability to think / concentrate",
    ],
    "VSA": [
        "(1) Depressed mood",
        "(5) Psychomotor retardation / agitation",
    ],
    "F2 formant transition speed": [
        "(1) Depressed mood",
        "(5) Psychomotor retardation / agitation",
    ],
    "Jitter": [
        "(1) Depressed mood",
        "(2) Loss of interest",
        "(3) Significant weight changes",
        "(5) Psychomotor retardation / agitation",
        "(8) Diminished ability to think / concentrate",
    ],
    "Shimmer": [
        "(1) Depressed mood",
        "(2) Loss of interest",
        "(3) Significant weight changes",
        "(5) Psychomotor retardation / agitation",
        "(8) Diminished ability to think / concentrate",
    ],
    "Volume intensity range": [
        "(2) Loss of interest",
        "(8) Diminished ability to think / concentrate",
    ],
    "Volume intensity std": [
        "(2) Loss of interest",
        "(8) Diminished ability to think / concentrate",
    ],
    "HNR": ["(3) Significant weight changes"],
    "Temporal modulations at 2-8 Hz": [
        "(4) Insomnia / hypersomnia",
        "(6) Fatigue / loss of energy",
    ],
    "Spectral modulations at 2 cyc/oct": [
        "(4) Insomnia / hypersomnia",
        "(6) Fatigue / loss of energy",
    ],
    "VOT": ["(5) Psychomotor retardation / agitation"],
    "Pulse (glottal pulses)": ["(8) Diminished ability to think / concentrate"],
    "PSD_4": ["(9) Suicidality"],
    "PSD_5": ["(9) Suicidality"],
    "PSD_7": ["(9) Suicidality"],
    "Voiced-to-silence (t_13) transition": ["(9) Suicidality"],
    "Voiced16:20 interval length PDF": ["(9) Suicidality"],
}

rows = []
indicator_order = []
for metric, indicators in metric_categories.items():
    for ind in indicators:
        rows.append((metric, ind))
        if ind not in indicator_order:
            indicator_order.append(ind)
indicator_order.append("(7) Worthlessness / guilt")

df = pd.DataFrame(rows, columns=["Metric", "Indicator"])
df = pd.concat(
    [
        df,
        pd.DataFrame(
            [("__dummy__", "(7) Worthlessness / guilt")],
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

heatmap_df = heatmap_df.T

plt.figure(figsize=(14, 12))

sns.set_context("talk", font_scale=1.7)

sns.heatmap(
    heatmap_df, cmap="Greys", cbar=False, linewidths=0.5, linecolor="gray", square=True
)

plt.xlabel("")
plt.ylabel("")

plt.xticks(rotation=45, ha="right", fontsize=16)
plt.yticks(rotation=0, fontsize=16)

plt.tight_layout(rect=[0, 0.05, 1, 1])
plt.show()
