import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime

st.set_page_config(page_title="SMP Player Tracker", layout="wide")

API_BASE = st.sidebar.text_input("Bot API URL", "https://repo-fix-production.up.railway.app")
HF_DATASET = "https://huggingface.co/datasets/abuzarhussain/smp-player-tracking/raw/main/data.jsonl"
REFRESH = st.sidebar.slider("Auto-refresh (s)", 5, 120, 15)

if st.sidebar.button("Refresh Now"):
    st.rerun()

# Fetch data once
health_data = None
api_players = []
hf_df = None

try:
    r = requests.get(f"{API_BASE}/health", timeout=5)
    if r.ok:
        health_data = r.json()
except Exception:
    pass

try:
    r = requests.get(f"{API_BASE}/api/players", timeout=5)
    if r.ok:
        api_players = r.json().get("players", [])
except Exception:
    pass

try:
    hf_df = pd.read_json(HF_DATASET, lines=True)
    if not hf_df.empty and "time" in hf_df.columns:
        hf_df["time"] = pd.to_datetime(hf_df["time"], unit="ms")
except Exception:
    hf_df = pd.DataFrame()

# Header
st.title("SMP Player Tracker")

tab_overview, tab_map, tab_players, tab_data = st.tabs(["Overview", "Player Map", "Players Online", "Raw Data"])

# ── TAB: Overview ──
with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    if health_data:
        status_icon = "🟢" if health_data["status"] == "connected" else "🔴"
        c1.metric("Bot Status", f"{status_icon} {health_data['status']}")
        c2.metric("Uptime", f"{health_data['uptime'] // 60}m {health_data['uptime'] % 60}s")
        c3.metric("Memory", f"{health_data.get('memoryUsage', 0):.1f} MB")
        c4.metric("Reconnects", health_data.get("reconnectAttempts", 0))
        if health_data.get("coords"):
            c = health_data["coords"]
            st.caption(f"Bot position: X={c['x']:.0f} Y={c['y']:.0f} Z={c['z']:.0f}")
    else:
        st.error("Cannot reach bot API")

    st.divider()
    mc1, mc2, mc3 = st.columns(3)
    unique_uuids = set()
    if api_players:
        for p in api_players:
            if p.get("uuid"):
                unique_uuids.add(p["uuid"])
    mc1.metric("Players Tracked (session)", len(unique_uuids))
    mc2.metric("Total Records (session)", len(api_players))
    mc3.metric("Total Records (HF)", len(hf_df) if not hf_df.empty else 0)

# ── TAB: Player Map ──
with tab_map:
    if hf_df.empty:
        st.info("No data in dataset yet.")
    elif "playerX" not in hf_df.columns or not hf_df["playerX"].notna().any():
        st.info("No player coordinates received yet. Waiting for tracked_waypoint packets.")
    else:
        map_df = hf_df[hf_df["playerX"].notna()].copy()
        map_df["X"] = map_df["playerX"].astype(int)
        map_df["Z"] = map_df["playerZ"].astype(int)

        # Minecraft scatter plot using scatter_chart
        chart_df = map_df[["X", "Z"]].copy()
        chart_df["label"] = chart_df.index.astype(str)
        st.subheader("Player Positions (Minecraft Coords)")
        st.scatter_chart(chart_df, x="X", y="Z", width=700, height=500)

        st.caption(f"Showing {len(chart_df)} data points from {len(map_df['uuid'].unique())} unique player(s)")

# ── TAB: Players Online ──
with tab_players:
    st.subheader("Currently Tracked Players")

    if not api_players:
        st.info("No players tracked in current session.")
    else:
        player_map = {}
        for p in api_players:
            uuid = p.get("uuid", "unknown")
            if uuid not in player_map:
                player_map[uuid] = {
                    "uuid": uuid,
                    "iconStyle": p.get("iconStyle", ""),
                    "wpType": p.get("wpType", ""),
                    "lastBotX": p.get("botX"),
                    "lastBotZ": p.get("botZ"),
                    "lastPlayerX": p.get("playerX"),
                    "lastPlayerY": p.get("playerY"),
                    "lastPlayerZ": p.get("playerZ"),
                    "azimuth": p.get("azimuth"),
                    "lastSeen": p.get("time"),
                    "count": 0,
                }
            entry = player_map[uuid]
            entry["count"] += 1
            if p.get("time", 0) > (entry["lastSeen"] or 0):
                entry["lastSeen"] = p.get("time")
                entry["lastBotX"] = p.get("botX")
                entry["lastBotZ"] = p.get("botZ")
                entry["lastPlayerX"] = p.get("playerX")
                entry["lastPlayerY"] = p.get("playerY")
                entry["lastPlayerZ"] = p.get("playerZ")
                entry["azimuth"] = p.get("azimuth")

        for uuid, info in sorted(player_map.items(), key=lambda x: x[1]["lastSeen"] or 0, reverse=True):
            with st.container(border=True):
                col_a, col_b, col_c = st.columns([2, 2, 1])
                short_uuid = uuid[:8] + "..."
                col_a.markdown(f"**{short_uuid}**")
                col_a.caption(f"Icon: {info['iconStyle']} | Type: {info['wpType']}")
                if info["lastPlayerX"] is not None:
                    col_b.metric("Position", f"X={info['lastPlayerX']} Y={info['lastPlayerY']} Z={info['lastPlayerZ']}")
                elif info["azimuth"] is not None:
                    col_b.metric("Azimuth", f"{info['azimuth']:.4f} rad")
                else:
                    col_b.caption("No coords")
                if info["lastSeen"]:
                    t = datetime.fromtimestamp(info["lastSeen"] / 1000).strftime("%H:%M:%S")
                    col_c.metric("Last Seen", t)
                st.caption(f"Bot was at X={info['lastBotX']} Z={info['lastBotZ']} | {info['count']} packets received")

# ── TAB: Raw Data ──
with tab_data:
    source = st.radio("Source", ["HF Dataset (all history)", "Session (recent 100)"], horizontal=True)
    if source == "HF Dataset (all history)":
        df = hf_df
    else:
        df = pd.DataFrame(api_players) if api_players else pd.DataFrame()
        if not df.empty and "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"], unit="ms")

    if df.empty:
        st.info("No data available.")
    else:
        priority_cols = ["time", "uuid", "wpType", "azimuth", "playerX", "playerY", "playerZ", "botX", "botZ", "iconStyle"]
        show_cols = [c for c in priority_cols if c in df.columns]
        extra_cols = [c for c in df.columns if c not in show_cols]
        st.dataframe(df[show_cols + extra_cols].tail(200), use_container_width=True)

    st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

time.sleep(REFRESH)
st.rerun()
