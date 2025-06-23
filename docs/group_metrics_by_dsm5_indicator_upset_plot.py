import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import rcParams
from upsetplot import UpSet, from_memberships

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

membership_list = [frozenset(v) for v in metric_categories.values()]
metric_names = list(metric_categories.keys())

membership_df = pd.DataFrame({"membership": membership_list})
counts = membership_df.value_counts().reset_index()
counts.columns = ["membership", "count"]

data = from_memberships(counts["membership"], data=counts["count"])

all_indicators = sorted(
    {ind for indicators in metric_categories.values() for ind in indicators}
)

rcParams.update(
    {
        "font.size": 14,
        "axes.titlesize": 16,
        "axes.labelsize": 14,
        "xtick.labelsize": 13,
        "ytick.labelsize": 13,
    }
)

plt.figure(figsize=(12, 6))
UpSet(
    data,
    show_counts=True,
    show_percentages=False,
    orientation="horizontal",
    sort_by="-input",
    sort_categories_by=None,
).plot()

# plt.suptitle("Voice Metrics Intersections by DSM-5 Indicators", fontsize=16)

for ax in plt.gcf().get_axes():
    ax.grid(False)
    ax.set_axisbelow(False)

plt.tight_layout()
plt.show()
