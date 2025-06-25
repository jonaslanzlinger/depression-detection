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

    combined_df["tightly_coupled_processing_duration"] = (
        combined_df["computation_duration"] + combined_df["profiling_duration"]
    )

    combined_df["time_only"] = combined_df["timestamp"].dt.strftime("%H:%M:%S")
    tick_step = 5
    xtick_indices = combined_df.index[::tick_step]
    xtick_labels = combined_df["time_only"].iloc[::tick_step]

    plt.figure(figsize=(14, 8))

    plt.plot(
        combined_df.index,
        combined_df["original_audio_duration"],
        label="(1) original_audio_duration",
        marker="o",
    )
    plt.plot(
        combined_df.index,
        combined_df["step_collect_duration"],
        label="(2) step_collect_duration",
        marker="v",
    )
    plt.plot(
        combined_df.index,
        combined_df["filtered_audio_duration"],
        label="(3) filtered_audio_duration",
        marker="d",
    )
    plt.plot(
        combined_df.index,
        combined_df["step_filter_duration"],
        label="(4) step_filter_duration",
        marker="x",
    )
    plt.plot(
        combined_df.index,
        combined_df["step_transport_duration"],
        label="(5) step_transport_duration",
        marker="1",
    )
    plt.plot(
        combined_df.index,
        combined_df["computation_duration"],
        label="(6) computation_duration",
        marker="^",
    )
    plt.plot(
        combined_df.index,
        combined_df["profiling_duration"],
        label="(7) profiling_duration",
        marker="s",
    )
    plt.plot(
        combined_df.index,
        combined_df["tightly_coupled_processing_duration"],
        label="(8) tightly_coupled_processing_duration",
        linestyle="--",
        linewidth=2,
    )

    plt.rcParams.update({"font.size": 14})
    plt.xlabel("Timestamp", fontsize=16)
    plt.ylabel("Duration (seconds)", fontsize=16)
    plt.legend(fontsize=15)
    plt.grid(True)
    plt.xticks(ticks=xtick_indices, labels=xtick_labels, rotation=45)
    plt.tight_layout()
    plt.show()

else:
    print("Row count mismatch – cannot directly concatenate the DataFrames.")
