import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import sys

# -----------------------------
# 📦 IMPORTS / FUNCTIONS
# -----------------------------
sys.path.insert(1, '../')
from functions import *

# -----------------------------
# 📌 SIDEBAR CONTROLS
# -----------------------------
url = f"https://catalogue.ceh.ac.uk/datastore/eidchub/211710ac-f01b-4b52-807f-373babb1c368/2_metadata/2_1_station_identification_metadata/00_station_id_meta.csv"
station_ids = pd.read_csv(url)
station_ids = station_ids['station_id'].astype(str).str.zfill(6)

station_list = sorted(station_ids)  # <-- you define this

station_id = st.sidebar.selectbox(
    "Station ID",
    options=station_list
)

qc_column = st.sidebar.number_input("QC Column", value=1, step=1)
qc_flags = st.sidebar.text_input("QC Flags", value="7")

go = st.sidebar.button("▶ Go")

# -----------------------------
# 🧠 SESSION STATE SETUP
# -----------------------------
if "active_station" not in st.session_state:
    st.session_state.active_station = None
    st.session_state.active_qc_column = None
    st.session_state.active_qc_flags = None
    st.session_state.i = 0
    st.session_state.results = []

# -----------------------------
# 🚀 RUN ONLY WHEN GO IS PRESSED
# -----------------------------
if go or st.session_state.active_station is None:

    st.session_state.active_station = station_id
    st.session_state.active_qc_column = qc_column
    st.session_state.active_qc_flags = qc_flags

    # reset labelling state
    st.session_state.i = 0
    st.session_state.results = []

# -----------------------------
# 📌 USE ACTIVE SETTINGS
# -----------------------------
station_id = st.session_state.active_station
qc_column = st.session_state.active_qc_column
qc_flags = st.session_state.active_qc_flags
sid = station_id

i = st.session_state.i

# -----------------------------
# 📊 LOAD DATA
# -----------------------------
df = load_station_data(station_id)

df = remove_empty(df)
df["value"] = pd.to_numeric(df["value"], errors="coerce")

# Flags
flag_str = (
    pd.to_numeric(df["flag"], errors="coerce")
    .fillna(0)
    .astype(int)
    .astype(str)
    .str.zfill(3)
)

df["flag_padded"] = normalize_flag_to_3char(df["flag"])

# -----------------------------
# ⏱ TIME PROCESSING
# -----------------------------
expected_delta = infer_time_step(df.index)

mask = build_qc_mask(flag_str, qc_column=qc_column, qc_flags=qc_flags)
times = df.index[mask].sort_values()

if times.empty:
    st.warning(
        f"No QC flags matching column {qc_column} with digits '{qc_flags}' "
        f"for station {station_id}."
    )
    st.stop()

runs = group_consecutive_times(times, expected_delta)

st.write(
    f"👉 Station {station_id}: {len(runs)} event chunk(s) "
    f"(qc_column={qc_column}, qc_flags='{qc_flags}', step={expected_delta})"
)

# (keep your test duplication if needed)
runs_list = runs + runs

# -----------------------------
# 🛑 END CONDITION
# -----------------------------
if i >= len(runs_list):
    st.success("🎉 All events labelled!")

    if st.session_state.results:
        df_out = pd.DataFrame(st.session_state.results)
        st.dataframe(df_out)

        csv = df_out.to_csv(index=False).encode("utf-8")
        st.download_button(
            "💾 Download results",
            data=csv,
            file_name="event_labels.csv",
            mime="text/csv"
        )

    st.stop()

# -----------------------------
# 📊 CURRENT EVENT
# -----------------------------
start, end = runs_list[i]

window = df.loc[
    start - pd.Timedelta(days=1): end + pd.Timedelta(days=1),
    "value"
]

# -----------------------------
# 📈 PLOT
# -----------------------------
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(window.index, window.values, lw=1)
ax.axvspan(start, end, color="red", alpha=0.3)
ax.set_title(f"{sid} ({i+1}/{len(runs_list)})")
ax.set_xlabel("Datetime")
ax.set_ylabel("Value")

st.pyplot(fig)

# -----------------------------
# 🎮 BUTTONS
# -----------------------------
col1, col2, col3 = st.columns(3)

# ⬅ BACK
if col1.button("⬅ Back"):
    if i > 0:
        st.session_state.i -= 1

        if len(st.session_state.results) > st.session_state.i:
            st.session_state.results.pop()

        st.rerun()

# ✅ TRUE
if col2.button("True"):
    record = {
        "station": sid,
        "start": start,
        "end": end,
        "real": True
    }

    if len(st.session_state.results) > i:
        st.session_state.results[i] = record
    else:
        st.session_state.results.append(record)

    st.session_state.i += 1
    st.rerun()

# ❌ FALSE
if col3.button("False"):
    record = {
        "station": sid,
        "start": start,
        "end": end,
        "real": False
    }

    if len(st.session_state.results) > i:
        st.session_state.results[i] = record
    else:
        st.session_state.results.append(record)

    st.session_state.i += 1
    st.rerun()

# -----------------------------
# 📊 PROGRESS
# -----------------------------
progress = len(st.session_state.results) / len(runs_list)
st.progress(progress)

st.write(f"**Progress:** {len(st.session_state.results)} / {len(runs_list)}")

# -----------------------------
# 📜 HISTORY
# -----------------------------
with st.expander("📜 History"):
    for j, r in enumerate(st.session_state.results):
        label = "✅ True" if r["real"] else "❌ False"
        st.write(f"{j+1}. {r['start']} → {label}")
