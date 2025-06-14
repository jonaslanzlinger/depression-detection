import pandas as pd

df = pd.read_csv("phq_metadata.csv")

numeric_df = df.select_dtypes(include="number")

feature_start_index = numeric_df.columns.get_loc("articulation_rate")
features_df = numeric_df.iloc[:, feature_start_index:]

means = features_df.mean()
stds = features_df.std()

summary_stats = pd.DataFrame({"Mean": means, "Standard Deviation": stds})

formatted_stats = summary_stats.applymap(
    lambda x: f"{x:.3f}" if abs(x) >= 0.001 else f"{x:.2e}"
)

print(formatted_stats)
