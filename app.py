import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd

# -----------------------------
# 🔧 YOUR DATA SETUP HERE
# -----------------------------
# df must exist with datetime index + "value" column
# runs must be list of (start, end)
# sid must exist

# Example placeholders (REMOVE THESE)
# df = ...
# runs = ...
# sid = "station_1"

import os
import pandas as pd
import sys
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
import ipywidgets as widgets
import ipywidgets as widgets
from IPython.display import display, clear_output

sys.path.insert(1, '../')
from functions import *


station_id = '026017'
sid = '026017'

qc_column = 1
qc_flags = "7"

df = load_station_data(station_id)
df.head()

# Clean rows where value is string 'NA' (but keep numeric instances of NAN)
df = remove_empty(df)
# Ensure values are numeric
df["value"] = pd.to_numeric(df["value"], errors="coerce")
# Normalised flags to 3 characters
flag_padded = normalize_flag_to_3char(df["flag"])
# Store the padded flags in the dataframe so they are visible when inspecting the data
df["flag_padded"] = flag_padded
df.head()

for col in ("value", "flag"):
    if col not in df.columns:
        print(f"⚠️ Column '{col}' not found in {path}; skipping station {station_id}.")
        break

# Infer timestep from the full series index
expected_delta = infer_time_step(df.index)

# Build QC mask on normalized flags
mask = build_qc_mask(flag_str, qc_column=qc_column, qc_flags=qc_flags)
times = df.index[mask].sort_values()

if times.empty:
    print(
        f"ℹ️ No QC flags matching column {qc_column} with digits '{qc_flags}' "
        f"for station {station_id}.")

# Group into consecutive runs
runs = group_consecutive_times(times, expected_delta)
print(
f"👉 Station {station_id}: {len(runs)} chunk(s) to review "
f"(qc_column={qc_column}, qc_flags='{qc_flags}', step={expected_delta}).")



runs_list = runs + runs  # your test case

# -----------------------------
# 🧠 SESSION STATE INIT
# -----------------------------
if "i" not in st.session_state:
    st.session_state.i = 0
    st.session_state.results = []

i = st.session_state.i

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

        # remove last result (undo)
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
