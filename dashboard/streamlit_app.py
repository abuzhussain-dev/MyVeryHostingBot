import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime

st.set_page_config(page_title="SMP Player Tracker", layout="wide")

API_BASE = st.sidebar.text_input("Bot API URL", "https://repo-fix-production.up.railway.app")
HF_DATASET = "https://huggingface.co/datasets/abuzarhussain/smp-player-tracking/raw/main/data.jsonl"
REFRESH = st.sidebar.slider("Auto-refresh (s)", 5, 120, 15)

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Bot Status")
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        if r.ok:
            data = r.json()
            status_color = "🟢" if data["status"] == "connected" else "🔴"
            st.metric("Status", f"{status_color} {data['status']}")
            st.metric("Uptime", f"{data['uptime'] // 60}m {data['uptime'] % 60}s")
            if data.get("coords"):
                c = data["coords"]
                st.metric("Position", f"{c['x']:.0f}, {c['z']:.0f}")
            st.metric("Memory", f"{data.get('memoryUsage', 0):.1f} MB")
            st.metric("Reconnects", data.get("reconnectAttempts", 0))
        else:
            st.error(f"API error: {r.status_code}")
    except Exception as e:
        st.error(f"Offline: {e}")

    st.subheader("Players Tracked")
    try:
        r = requests.get(f"{API_BASE}/api/players", timeout=5)
        if r.ok:
            players = r.json()
            st.metric("Total records", players.get("total", 0))
            st.metric("Recent", len(players.get("players", [])))
            for p in players.get("players", [])[-5:]:
                t = datetime.fromtimestamp(p["time"] / 1000).strftime("%H:%M:%S")
                pos = f"x={p.get('botX')} z={p.get('botZ')}"
                label = p.get("wpType", "pos") or "pos"
                st.caption(f"{t} - {label} {pos}")
    except Exception as e:
        st.error(f"API error: {e}")

with col2:
    st.subheader("Player Map")
    try:
        df = pd.read_json(HF_DATASET, lines=True)
        if not df.empty:
            df["time"] = pd.to_datetime(df["time"], unit="ms")
            has_coords = "playerX" in df.columns and df["playerX"].notna().any()
            has_azimuth = "azimuth" in df.columns and df["azimuth"].notna().any()

            if has_coords:
                map_df = df[df["playerX"].notna()].copy()
                st.map(map_df, latitude="playerZ", longitude="playerX")

                with st.expander("Data Table"):
                    cols = ["time", "botX", "botZ", "playerX", "playerZ", "uuid", "wpType"]
                    show_cols = [c for c in cols if c in map_df.columns]
                    st.dataframe(map_df[show_cols].tail(50), use_container_width=True)
            elif has_azimuth:
                st.info(f"{df['azimuth'].notna().sum()} azimuth readings recorded. Map needs triangulation (2+ positions per player).")
                with st.expander("Raw Data"):
                    cols = ["time", "botX", "botZ", "azimuth", "uuid"]
                    show_cols = [c for c in cols if c in df.columns]
                    st.dataframe(df[show_cols].tail(100), use_container_width=True)
            else:
                st.info("No player waypoints received yet. Bot is recording positions during scan cycles.")
                with st.expander("Raw Data"):
                    cols = ["time", "botX", "botZ", "type"]
                    show_cols = [c for c in cols if c in df.columns]
                    st.dataframe(df[show_cols].tail(100), use_container_width=True)
        else:
            st.info("No data in dataset yet.")
    except Exception as e:
        st.warning(f"HF data not available: {e}")

    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

if st.sidebar.button("Refresh Now"):
    st.rerun()

time.sleep(REFRESH)
st.rerun()
