import pandas as pd
import matplotlib.pyplot as plt

data_ingestion_df = pd.read_csv("docs/performance_log_DATA_INGESTION_LAYER_save.csv")
metrics_df = pd.read_csv(
    "docs/performance_log_METRICS_COMPUTATION_save.csv", header=None
)
profiling_df = pd.read_csv("docs/performance_log_USER_PROFILING_save.csv", header=None)

metrics_df.columns = ["timestamp", "audio_duration", "computation_duration"]
profiling_df.columns = ["timestamp", "audio_duration", "profiling_duration"]

data_ingestion_df["timestamp"] = pd.to_datetime(data_ingestion_df["timestamp"])
metrics_df["timestamp"] = pd.to_datetime(metrics_df["timestamp"])
profiling_df["timestamp"] = pd.to_datetime(profiling_df["timestamp"])

if len(data_ingestion_df) == len(metrics_df) == len(profiling_df):
    combined_df = pd.concat(
        [
            data_ingestion_df.reset_index(drop=True),
            metrics_df[["computation_duration"]].reset_index(drop=True),
            profiling_df[["profiling_duration"]].reset_index(drop=True),
        ],
        axis=1,
    )

    # cumulate total processing duration of tightly coupled services
    combined_df["tightly_coupled_processing_duration"] = (
        combined_df["computation_duration"] + combined_df["profiling_duration"]
    )

    plt.figure(figsize=(14, 8))
    plt.plot(
        combined_df["timestamp"],
        combined_df["original_audio_duration"],
        label="original_audio_duration",
        marker="o",
    )
    plt.plot(
        combined_df["timestamp"],
        combined_df["step_collect_duration"],
        label="step_collect_duration",
        marker="v",
    )
    plt.plot(
        combined_df["timestamp"],
        combined_df["filtered_audio_duration"],
        label="filtered_audio_duration",
        marker="d",
    )
    plt.plot(
        combined_df["timestamp"],
        combined_df["step_filter_duration"],
        label="step_filter_duration",
        marker="x",
    )
    plt.plot(
        combined_df["timestamp"],
        combined_df["step_transport_duration"],
        label="step_transport_duration",
        marker="1",
    )
    plt.plot(
        combined_df["timestamp"],
        combined_df["computation_duration"],
        label="computation_duration",
        marker="^",
    )
    plt.plot(
        combined_df["timestamp"],
        combined_df["profiling_duration"],
        label="profiling_duration",
        marker="s",
    )
    plt.plot(
        combined_df["timestamp"],
        combined_df["tightly_coupled_processing_duration"],
        label="tightly_coupled_processing_duration",
        linestyle="--",
        linewidth=2,
    )

    plt.xlabel("Timestamp")
    plt.ylabel("Duration (seconds)")
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

else:
    print("Row count mismatch – cannot directly concatenate the DataFrames.")
