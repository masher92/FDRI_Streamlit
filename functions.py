import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def load_station_data(station_id: str) -> pd.DataFrame:
    url = f"https://catalogue.ceh.ac.uk/datastore/eidchub/211710ac-f01b-4b52-807f-373babb1c368/1_RiverFlowStations/{station_id}.csv"
    return pd.read_csv(url, parse_dates=["datetime"], index_col="datetime")

def explore_qc_flags(
    df: pd.DataFrame,
    station_id: str,
    print_summary_table : bool = False,
    qc_columns: list = [0, 1, 2],
    qc_flags: list = ["1", "2", "3", "4", "5", "6", "7", "8", "9"],):
    """
    Explore how many timesteps would be flagged for each combination of
    qc_column and qc_flag value, to inform selection before running interpolation.
    Flag value 0 is excluded as it indicates no quality issue.

    Parameters
    ----------
    df : pd.DataFrame
        The dataframe with datetime index and 'flag' column.
    station_id : str
        Station ID, used in plot title.
    qc_columns : list
        Which QC digit positions to explore (0=X, 1=Y, 2=Z). Default is all three.
    qc_flags : list
        Which digit values to explore. Default is 1-9 (0 excluded as it means no issue).
    """

    # start = time.time()

    flag_padded = normalize_flag_to_3char(df["flag"])
    col_names = {0: "X", 1: "Y", 2: "Z"}
    total = len(df)

    # Extract all digit positions in one pass
    digits = pd.DataFrame({
        "X": flag_padded.str[0],
        "Y": flag_padded.str[1],
        "Z": flag_padded.str[2],
    })

    rows = []
    for col_idx, col_name in col_names.items():
        if col_idx not in qc_columns:
            continue
        counts = digits[col_name].value_counts()
        for flag in qc_flags:
            n_flagged = counts.get(flag, 0)
            rows.append({
                "qc_column": f"{col_idx} ({col_name})",
                "qc_flag": flag,
                "n_flagged": n_flagged,
                "pct_flagged": round(100 * n_flagged / total, 2),
            })

    summary = pd.DataFrame(rows)
    non_zero = summary[summary["n_flagged"] > 0]

    # elapsed = time.time() - start
    # print(f"Summary built in {elapsed:.3f}s")

    # Print summary table
    if print_summary_table ==True:
        print(f"\nStation {station_id} — Flagged timesteps by QC column and flag value")
        print(f"Total timesteps: {total}\n")
        if non_zero.empty:
            print("No flagged timesteps found for any combination.")
            return summary
        else:
            print(non_zero.to_string(index=False))

    # Only plot flag values that actually appear in the data
    active_flags = non_zero["qc_flag"].unique()
    pivot = summary[summary["qc_flag"].isin(active_flags)].pivot(
        index="qc_flag", columns="qc_column", values="n_flagged")

    fig, ax = plt.subplots(figsize=(6, 3))

    im = ax.imshow(pivot.values, aspect="auto", cmap="Reds")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title(f"Station {station_id} — Flagged timesteps by QC column and flag value")
    ax.set_xlabel("QC column")
    ax.set_ylabel("Flag value")
    plt.colorbar(im, ax=ax)

    for r in range(pivot.shape[0]):
        for c in range(pivot.shape[1]):
            val = pivot.values[r, c]
            if val > 0:
                ax.text(c, r, str(int(val)), ha="center", va="center",
                        color="black" if val < pivot.values.max() * 0.7 else "white",
                        fontsize=8)

    plt.tight_layout()
    plt.show()

    return summary

def plot_qc_flag_distribution(
    df: pd.DataFrame,
    station_id: str,
    qc_columns: list = [0, 1, 2],
    qc_flags: list = ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
):
    """
    Plot the distribution of flagged timestamps across the full record,
    with a separate row for each QC column so it is easy to see whether
    the three checks flag the same periods or different ones.

    Parameters
    ----------
    df : pd.DataFrame
        The dataframe with datetime index and 'flag' column.
    station_id : str
        Station ID, used in plot title.
    qc_columns : list
        Which QC digit positions to plot (0=X, 1=Y, 2=Z). Default is all three.
    qc_flags : list
        Which digit values to treat as flagged. Default is 1-9.
    """

    flag_padded = normalize_flag_to_3char(df["flag"])
    col_names = {0: "X", 1: "Y", 2: "Z"}
    colours = {0: "steelblue", 1: "firebrick", 2: "seagreen"}

    # Extract all digit positions in one pass
    digits = pd.DataFrame({
        "X": flag_padded.str[0],
        "Y": flag_padded.str[1],
        "Z": flag_padded.str[2],
    })

    fig, axes = plt.subplots(
        len(qc_columns), 1,
        figsize=(14, len(qc_columns) * 1.5),
        sharex=True
    )

    # Handle case where only one column is requested
    if len(qc_columns) == 1:
        axes = [axes]

    for ax, col_idx in zip(axes, qc_columns):
        col_name = col_names[col_idx]

        # Find timestamps where this column has a flagged value
        flagged_mask = digits[col_name].isin(qc_flags)
        flagged_timestamps = df.index[flagged_mask]

        ax.axhspan(0, 1, color="lightgrey", alpha=0.3)
        ax.vlines(
            flagged_timestamps,
            ymin=0, ymax=1,
            color=colours[col_idx],
            linewidth=0.5, alpha=0.7
        )

        ax.set_yticks([])
        ax.set_ylabel(f"{col_idx} ({col_name})", rotation=0, labelpad=40, va="center")
        ax.set_title(f"{flagged_mask.sum()} flagged timesteps", fontsize=9, loc="right")

    axes[-1].set_xlabel("Datetime")
    fig.suptitle(f"Station {station_id} — Distribution of flagged timestamps by QC column", y=1.02)
    plt.tight_layout()
    plt.show()


def plot_flagged_clusters(
    df: pd.DataFrame,
    clusters: list,
    station_id: str,
    interp_log: pd.DataFrame = None,
    show_interpolated: bool = False,
    n_context: int = 10,
):
    """
    Plot a zoomed window around each contiguous cluster of flagged values.

    Parameters
    ----------
    df : pd.DataFrame
        The dataframe with datetime index and 'value' column.
    clusters : list
        List of arrays of integer positions, one per contiguous cluster.
    station_id : str
        Station ID, used in plot titles.
    interp_log : pd.DataFrame, optional
        Interpolation log with columns ['station', 'datetime', 'old_value', 'new_value'].
        Required if show_interpolated=True.
    show_interpolated : bool
        If True, overlay interpolated values in green. Requires interp_log. Default False.
    n_context : int
        Number of real (non-NaN) values to show either side of each cluster. Default 10.
    """

    if show_interpolated and interp_log is None:
        raise ValueError("interp_log must be provided when show_interpolated=True.")

    print(f"{len(clusters)} cluster(s) of flagged points found.")

    log_indexed = interp_log.set_index("datetime") if interp_log is not None else None

    for i, cluster in enumerate(clusters):

        window_start, window_end = get_window_with_real_values(df, cluster, n=n_context)
        df_window = df.iloc[window_start:window_end + 1].copy()
        cluster_datetimes = df.index[cluster]

        # Get old values — from df directly if no log provided, otherwise from log
        if log_indexed is not None:
            old_values_cluster = log_indexed.loc[cluster_datetimes, "old_value"]
        else:
            old_values_cluster = df.loc[cluster_datetimes, "value"]

        # Restore original values as the base line
        df_window.loc[cluster_datetimes, "value"] = old_values_cluster.values

        # Scale scatter point size based on number of points in the window
        n_points = len(df_window)
        point_size = max(10, min(80, 800 / n_points))

        fig, ax = plt.subplots(figsize=(10, 4))

        ax.plot(df_window.index, df_window["value"],
                color="black", linewidth=0.8)
        ax.scatter(df_window.index, df_window["value"],
                   color="black", s=point_size, label="Time series")

        # Always show flagged values in red
        ax.scatter(cluster_datetimes, old_values_cluster,
                   color="red", zorder=5, s=point_size * 1.5,
                   label=f"Flagged values ({len(cluster)} points)")

        if show_interpolated:
            new_values = log_indexed.loc[cluster_datetimes, "new_value"]
            ax.scatter(cluster_datetimes, new_values,
                       color="green", zorder=6, s=point_size * 1.5, marker="x",
                       label=f"Interpolated values ({len(cluster)} points)")

            still_nan = new_values[new_values.isna()]
            if not still_nan.empty:
                ax.scatter(still_nan.index, old_values_cluster.loc[still_nan.index],
                           color="orange", zorder=6, s=point_size * 1.5, marker="x",
                           label=f"Could not interpolate ({len(still_nan)} points)")

        # Format x axis based on time range of the window
        time_range = df_window.index[-1] - df_window.index[0]
        if time_range <= pd.Timedelta(days=2):
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M"))
        elif time_range <= pd.Timedelta(days=30):
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%Y"))
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

        plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha="center")

        ax.set_title(f"Station {station_id} — Cluster {i + 1} of {len(clusters)} "
                     f"({'interpolated' if show_interpolated else 'original'})")
        ax.set_xlabel("Datetime")
        ax.set_ylabel("Flow value")
        ax.legend()
        fig.tight_layout()
        plt.show()

def plot_flagged_distribution(
    df: pd.DataFrame,
    flagged_rows: pd.Series,
    station_id: str,
):
    """
    Plot the distribution of flagged timestamps across the full record.

    Parameters
    ----------
    df : pd.DataFrame
        The dataframe with datetime index.
    flagged_rows : pd.Series
        Boolean mask indicating which rows are flagged.
    station_id : str
        Station ID, used in plot title.
    """

    fig, ax = plt.subplots(figsize=(14, 2))

    ax.axhspan(0, 1, color="lightgrey", alpha=0.3)
    ax.vlines(
        df.loc[flagged_rows].index,
        ymin=0, ymax=1,
        color="red", linewidth=0.5, alpha=0.7
    )

    ax.set_title(f"Station {station_id} — Distribution of flagged timestamps across the full record "
                 f"({flagged_rows.sum()} flagged out of {len(df)} total)")
    ax.set_xlabel("Datetime")
    ax.set_yticks([])
    plt.tight_layout()
    plt.show()        
        
        
def get_window_with_real_values(df, cluster, n=10):
    # Work backwards from the cluster start until we have n real values
    pre_cluster = df.iloc[:cluster[0]]["value"].dropna()
    if len(pre_cluster) >= n:
        window_start = df.index.get_loc(pre_cluster.iloc[-n:].index[0])
    else:
        window_start = df.index.get_loc(pre_cluster.index[0]) if len(pre_cluster) > 0 else cluster[0]
    
    # Work forwards from the cluster end until we have n real values
    post_cluster = df.iloc[cluster[-1]+1:]["value"].dropna()
    if len(post_cluster) >= n:
        window_end = df.index.get_loc(post_cluster.iloc[:n].index[-1])
    else:
        window_end = df.index.get_loc(post_cluster.index[-1]) if len(post_cluster) > 0 else cluster[-1]
    
    return window_start, window_end        

def remove_empty(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove rows where the 'value' column equals the literal string 'NA' (case-insensitive).
    Does not drop numeric NaNs or other blanks.
    """
    if "value" not in df.columns:
        raise KeyError("Column 'value' not found in input data.")
    is_na_string = df["value"].astype(str).str.strip().str.upper() == "NA"
    return df.loc[~is_na_string].copy()

def normalize_flag_to_3char(flag_series: pd.Series) -> pd.Series:
    """
    Normalize flag values to zero-padded 3-character strings:
      0   -> '000'
      60  -> '060'
      137 -> '137'
    Non-numeric or missing -> 0 -> '000'
    """
    nums = pd.to_numeric(flag_series, errors="coerce").fillna(0).astype(int)
    return nums.astype(str).str.zfill(3)


def build_qc_mask(flag_str_series: pd.Series, qc_column: int, qc_flags: str) -> pd.Series:
    """
    Return a boolean mask where the character at qc_column is in qc_flags.
      - qc_column: 0, 1, or 2 (X, Y, Z)
      - qc_flags:  string of digits, e.g. '238', '7', or '0123456789'
    """
    if qc_column not in (0, 1, 2):
        raise ValueError("qc_column must be 0, 1, or 2 for a 3-character QC flag.")
    if not qc_flags or any(ch not in "0123456789" for ch in qc_flags):
        raise ValueError("qc_flags must be a non-empty string of digits 0–9, e.g. '7' or '238'.")

    s = flag_str_series.astype(str)
    ok_len = s.str.len() == 3
    s_ok = s.where(ok_len, None)
    return ok_len & s_ok.str[qc_column].isin(list(qc_flags))

def infer_time_step(index: pd.DatetimeIndex) -> pd.Timedelta:
    """
    Infer the most common time step from a DateTimeIndex.
    Falls back to 15 minutes if inference fails.
    """
    if len(index) < 2:
        return pd.Timedelta(minutes=15)
    diffs = pd.Series(index.sort_values()).diff().dropna()
    if diffs.empty:
        return pd.Timedelta(minutes=15)
    return diffs.value_counts().idxmax()


def group_consecutive_times(times: pd.DatetimeIndex, expected_delta: pd.Timedelta):
    """
    Group sorted times into consecutive runs separated by expected_delta.
    Returns a list of (start, end) tuples.
    """
    times = pd.DatetimeIndex(times).sort_values()
    if len(times) == 0:
        return []

    runs = []
    run_start = times[0]
    prev = times[0]

    for t in times[1:]:
        if t - prev == expected_delta:
            prev = t
        else:
            runs.append((run_start, prev))
            run_start = t
            prev = t
    runs.append((run_start, prev))
    return runs

