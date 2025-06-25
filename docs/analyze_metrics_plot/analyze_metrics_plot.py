import json
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime

with open("docs/analyze_metrics_plot/daily_metrics.json", "r") as f:
    json_data = json.load(f)

baseline = json_data["baseline"]
std_dev = json_data["standard_deviation"]
records = json_data["data"]

df = pd.DataFrame(records)
df["date"] = pd.to_datetime(df["date"])
df["baseline"] = baseline
df["std_dev_upper"] = baseline + std_dev
df["std_dev_lower"] = baseline - std_dev
df["z_score"] = (df["observed"] - baseline) / std_dev

plt.figure(figsize=(12, 6))

plt.fill_between(
    df["date"],
    df["std_dev_lower"],
    df["std_dev_upper"],
    color="gray",
    alpha=0.2,
    label="±1 Std Dev",
)

plt.plot(df["date"], df["baseline"], label="Baseline", linestyle="--", linewidth=2)
plt.plot(df["date"], df["observed"], label="Observed Value", linewidth=2)
plt.plot(df["date"], df["z_score"], label="Z-Score", linewidth=2)

plt.title("Daily Observed Values, Baseline, and Z-Scores", fontsize=14)
plt.xlabel("Date")

plt.ylabel("Value / Z-Score")
plt.xticks(rotation=45)
plt.grid(True, linestyle=":")
plt.legend()
plt.tight_layout()
plt.show()
