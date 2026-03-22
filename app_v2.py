import io
import json
import traceback

import folium
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import folium_static
from vrp_core import build_template_frames, solve_vrp

st.set_page_config(page_title="RouteOptimizer VRPTW+", page_icon="🚚", layout="wide", initial_sidebar_state="expanded")

TRAFFIC_PROFILES = {"offpeak": "Вне часа пик", "day": "Дневной поток", "morning_peak": "Утренний пик", "evening_peak": "Вечерний пик"}
GOAL_LABELS = {"time": "Минимум времени", "distance": "Минимум расстояния", "fleet": "Минимум числа машин", "balanced": "Баланс маршрутов"}
COLORS = ["blue","green","red","purple","orange","darkred","darkblue","darkgreen","cadetblue","darkpurple","pink","lightblue","lightgreen","gray","black"]

st.markdown("""<style>
.metric-container {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; padding: 18px; color: white; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.12); margin-bottom: 10px;}
.metric-value { font-size: 26px; font-weight: 700; margin: 5px 0; }
.metric-label { font-size: 14px; opacity: 0.92; }
.info-box {background-color: #f8f9fa; border-left: 4px solid #3498db; padding: 15px; border-radius: 6px; margin: 10px 0; color: #2c3e50;}
</style>""", unsafe_allow_html=True)


# ── dtype enforcement ──

def _fix_depots(df):
    df = df.copy()
    df["active"] = df["active"].astype(bool)
    for c in ["id","name","address"]: df[c] = df[c].astype(str)
    for c in ["lat","lon"]: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    for c in ["tw_start","tw_end"]: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df

def _fix_stores(df):
    df = df.copy()
    df["active"] = df["active"].astype(bool)
    df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
    for c in ["name","address"]: df[c] = df[c].astype(str)
    for c in ["lat","lon","demand","pickup_demand"]: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).astype(float)
    for c in ["tw_start","tw_end","service_time"]: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df

def _fix_vehicles(df):
    df = df.copy()
    df["active"] = df["active"].astype(bool)
    df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
    df["name"] = df["name"].astype(str)
    for c in ["capacity","pickup_capacity"]: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).astype(float)
    df["depot_id"] = df["depot_id"].astype(str)
    df["max_shift_min"] = pd.to_numeric(df["max_shift_min"], errors="coerce").fillna(600).astype(int)
    return df


def init_state():
    if "depots_df" not in st.session_state:
        d, s, v = build_template_frames()
        st.session_state["depots_df"] = _fix_depots(d)
        st.session_state["stores_df"] = _fix_stores(s)
        st.session_state["vehicles_df"] = _fix_vehicles(v)
    for k in ["solution", "ui_error"]:
        if k not in st.session_state:
            st.session_state[k] = None

init_state()


# ── helpers ──

def format_time(m):
    m = int(m)
    return f"{(m//60)%24:02d}:{m%60:02d}"

def load_tabular(f):
    n = f.name.lower()
    if n.endswith(".csv"): return pd.read_csv(f)
    if n.endswith((".xlsx",".xls")): return pd.read_excel(f)
    raise ValueError("CSV или Excel")

def normalize_store_df(df):
    mp = {"pickup":"pickup_demand","delivery":"demand","open":"tw_start","close":"tw_end"}
    df = df.rename(columns=mp).copy()
    req = ["id","name","address","lat","lon","demand","pickup_demand","tw_start","tw_end","service_time"]
    for c in req:
        if c not in df.columns:
            if c == "pickup_demand": df[c] = 0
            elif c == "service_time": df[c] = 20
            else: raise ValueError(f"Нет столбца {c}")
    if "active" not in df.columns: df["active"] = True
    return _fix_stores(df[["active"] + req])

def normalize_vehicle_df(df, depots_df):
    df = df.copy()
    req = ["id","name","capacity","pickup_capacity","depot_id","max_shift_min"]
    for c in req:
        if c not in df.columns:
            if c == "pickup_capacity": df[c] = df["capacity"] if "capacity" in df.columns else 0
            elif c == "max_shift_min": df[c] = 600
            else: raise ValueError(f"Нет столбца {c}")
    if "active" not in df.columns: df["active"] = True
    valid = set(depots_df["id"].tolist())
    df["depot_id"] = df["depot_id"].where(df["depot_id"].isin(valid), depots_df.iloc[0]["id"])
    return _fix_vehicles(df[["active"] + req])

def dataframe_to_records(df, kind):
    rows = []
    for row in df.to_dict(orient="records"):
        if not row.get("active", True):
            continue
        base = {k: row[k] for k in row if k != "active"}
        if kind in {"store", "depot"}:
            base["time_window"] = (int(base.pop("tw_start")), int(base.pop("tw_end")))
            base["lat"] = float(base["lat"])
            base["lon"] = float(base["lon"])
            if kind == "store":
                base["demand"] = float(base["demand"])
                base["pickup_demand"] = float(base.get("pickup_demand", 0))
                base["service_time"] = int(base["service_time"])
        elif kind == "vehicle":
            base["capacity"] = float(base["capacity"])
            base["pickup_capacity"] = float(base["pickup_capacity"])
            base["max_shift_min"] = int(base["max_shift_min"])
        rows.append(base)
    return rows

def compute_constraints(stores, vehicles):
    total_delivery = sum(s["demand"] for s in stores)
    total_pickup = sum(s.get("pickup_demand", 0) for s in stores)
    total_delivery_cap = sum(v["capacity"] for v in vehicles)
    total_pickup_cap = sum(v.get("pickup_capacity", v["capacity"]) for v in vehicles)
    return {"delivery_demand": total_delivery, "pickup_demand": total_pickup, "delivery_gap": total_delivery_cap - total_delivery, "pickup_gap": total_pickup_cap - total_pickup}

def route_export_frames(solution):
    summary_rows, stop_rows = [], []
    for idx, route in enumerate(solution["routes"], start=1):
        summary_rows.append({"route_no": idx, "vehicle": route["vehicle_type"], "depot": route["depot_name"], "stops": route["stops_count"], "distance_km": round(route["distance"] / 1000, 2), "drive_minutes": route["drive_minutes"], "service_minutes": route["service_minutes"], "waiting_minutes": route["waiting_minutes"], "duration_minutes": route["duration"], "delivery_used": route["delivery_used"], "pickup_used": route["pickup_used"], "avg_speed_kmh": route["avg_speed_kmh"]})
        for stop in route["stops_detail"]:
            stop_rows.append({"route_no": idx, "vehicle": route["vehicle_type"], "sequence": stop["sequence"], "node_type": stop["node_type"], "name": stop["name"], "address": stop["address"], "arrival": format_time(stop["arrival"]), "departure": format_time(stop["departure"]), "delivery": stop.get("delivery", 0), "pickup": stop.get("pickup", 0), "waiting_min": stop.get("waiting", 0), "service_min": stop.get("service_time", 0)})
    return pd.DataFrame(summary_rows), pd.DataFrame(stop_rows)

def build_geojson(solution):
    features = []
    for idx, route in enumerate(solution["routes"], start=1):
        for seg in route["geometry"]:
            if not seg: continue
            features.append({"type": "Feature", "properties": {"route_no": idx, "vehicle": route["vehicle_type"], "depot": route["depot_name"]}, "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in seg]}})
    return {"type": "FeatureCollection", "features": features}

def build_excel_bytes(summary_df, stops_df, unserved_df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="routes", index=False)
        stops_df.to_excel(writer, sheet_name="stops", index=False)
        if unserved_df is not None and not unserved_df.empty:
            unserved_df.to_excel(writer, sheet_name="unserved", index=False)
    buf.seek(0)
    return buf.getvalue()

def safe_data_editor(df, **kwargs):
    try:
        return st.data_editor(df, **kwargs)
    except Exception as e:
        st.warning(f"⚠️ Data editor недоступен, показываю таблицу в безопасном режиме: {e}")
        st.dataframe(df, use_container_width=True)
        return df

def safe_folium_display(fmap, height=560):
    try:
        folium_static(fmap, width=None, height=height)
    except Exception as e:
        st.warning(f"⚠️ Карта отображается в упрощённом режиме: {e}")
        html = fmap._repr_html_()
        st.components.v1.html(html, height=height + 40, scrolling=False)

def reset_defaults():
    d, s, v = build_template_frames()
    st.session_state["depots_df"] = _fix_depots(d)
    st.session_state["stores_df"] = _fix_stores(s)
    st.session_state["vehicles_df"] = _fix_vehicles(v)
    st.session_state["solution"] = None
    st.session_state["ui_error"] = None


st.sidebar.title("🚚 RouteOptimizer+")
st.sidebar.markdown("---")

with st.sidebar.expander("Импорт данных", expanded=False):
    store_upload = st.file_uploader("Загрузить магазины (CSV/XLSX)", type=["csv", "xlsx", "xls"], key="store_upload")
    vehicle_upload = st.file_uploader("Загрузить транспорт (CSV/XLSX)", type=["csv", "xlsx", "xls"], key="vehicle_upload")
    if st.button("Применить импорт", use_container_width=True, key="apply_import"):
        try:
            if store_upload is not None:
                st.session_state["stores_df"] = normalize_store_df(load_tabular(store_upload))
            if vehicle_upload is not None:
                st.session_state["vehicles_df"] = normalize_vehicle_df(load_tabular(vehicle_upload), st.session_state["depots_df"])
            st.session_state["ui_error"] = None
            st.success("Импорт применён")
        except Exception as exc:
            st.session_state["ui_error"] = f"Ошибка импорта: {exc}"
            st.error(st.session_state["ui_error"])

with st.sidebar.form("controls"):
    st.subheader("⚙️ Оптимизация")
    goal = st.selectbox("Цель оптимизации", list(GOAL_LABELS.keys()), format_func=lambda x: GOAL_LABELS[x], key="goal")
    traffic_profile = st.selectbox("Профиль трафика", list(TRAFFIC_PROFILES.keys()), format_func=lambda x: TRAFFIC_PROFILES[x], key="traffic")
    max_search_time = st.slider("Время поиска, сек", 1, 60, 12, key="search_time")
    penalty = st.number_input("Штраф за пропуск точки", min_value=1000, max_value=1000000, value=100000, step=5000, key="penalty")
    balance_routes = st.checkbox("Балансировать маршруты", value=True, key="balance")
    calc = st.form_submit_button("🚀 Рассчитать", use_container_width=True)

if st.sidebar.button("Сбросить к шаблону", use_container_width=True, key="reset_defaults"):
    reset_defaults()

st.title("🗺️ Gloria Jeans Logistics VRPTW+")
st.markdown("### Реальные магазины, мультисклады, возвраты, сценарии и аналитика")

if st.session_state["ui_error"]:
    st.error(st.session_state["ui_error"])
    with st.expander("Показать traceback"):
        st.code(st.session_state["ui_error"])

tab_data, tab_result = st.tabs(["✏️ Данные", "📊 Результаты"])

with tab_data:
    c_left, c_right = st.columns([1, 2])
    with c_left:
        st.subheader("🏭 Склады")
        st.caption("В проект включены реальные объекты Gloria Jeans в Подольске.")
        st.session_state["depots_df"] = safe_data_editor(st.session_state["depots_df"], use_container_width=True, hide_index=True, num_rows="fixed", column_config={"active": st.column_config.CheckboxColumn("Вкл"), "tw_start": st.column_config.NumberColumn("Открытие", min_value=0, max_value=1440, step=5), "tw_end": st.column_config.NumberColumn("Закрытие", min_value=0, max_value=1440, step=5)}, key="depots_df_editor")
        st.subheader("🚛 Парк")
        st.session_state["vehicles_df"] = safe_data_editor(st.session_state["vehicles_df"], use_container_width=True, hide_index=True, num_rows="fixed", column_config={"active": st.column_config.CheckboxColumn("В рейс"), "capacity": st.column_config.NumberColumn("Доставка, м³", min_value=0.0, step=1.0), "pickup_capacity": st.column_config.NumberColumn("Забор, м³", min_value=0.0, step=1.0), "max_shift_min": st.column_config.NumberColumn("Смена, мин", min_value=60, max_value=1440, step=30), "depot_id": st.column_config.SelectboxColumn("Склад", options=st.session_state["depots_df"]["id"].tolist())}, key="vehicles_df_editor")
    with c_right:
        st.subheader("🏬 Магазины")
        st.session_state["stores_df"] = safe_data_editor(st.session_state["stores_df"], use_container_width=True, hide_index=True, num_rows="fixed", column_config={"active": st.column_config.CheckboxColumn("Активен"), "demand": st.column_config.NumberColumn("Доставка, м³", min_value=0.0, step=1.0), "pickup_demand": st.column_config.NumberColumn("Возвраты, м³", min_value=0.0, step=1.0), "tw_start": st.column_config.NumberColumn("Открытие", min_value=0, max_value=1440, step=5), "tw_end": st.column_config.NumberColumn("Закрытие", min_value=0, max_value=1440, step=5), "service_time": st.column_config.NumberColumn("Разгрузка, мин", min_value=0, max_value=240, step=5)}, key="stores_df_editor")
    stores = dataframe_to_records(st.session_state["stores_df"], "store")
    depots = dataframe_to_records(st.session_state["depots_df"], "depot")
    vehicles = dataframe_to_records(st.session_state["vehicles_df"], "vehicle")
    cons = compute_constraints(stores, vehicles)
    st.markdown("---")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Спрос на доставку", f"{cons['delivery_demand']:.0f} м³", f"{cons['delivery_gap']:+.0f} м³")
    k2.metric("Возвраты", f"{cons['pickup_demand']:.0f} м³", f"{cons['pickup_gap']:+.0f} м³")
    k3.metric("Активных складов", len(depots))
    k4.metric("Активных машин", len(vehicles))

if calc:
    try:
        stores = dataframe_to_records(st.session_state["stores_df"], "store")
        depots = dataframe_to_records(st.session_state["depots_df"], "depot")
        vehicles = dataframe_to_records(st.session_state["vehicles_df"], "vehicle")
        if not depots:
            raise ValueError("Нужно оставить хотя бы один активный склад.")
        if not vehicles:
            raise ValueError("Нужно выбрать хотя бы одну машину.")
        if not stores:
            raise ValueError("Нет активных магазинов для расчёта.")
        with st.spinner("⏳ Выполняется расчёт маршрутов..."):
            st.session_state["solution"] = solve_vrp(depots=depots, stores=stores, vehicles_config=vehicles, max_search_time=max_search_time, optimization_goal=goal, traffic_profile=traffic_profile, penalty=int(penalty), balance_routes=balance_routes)
        st.session_state["ui_error"] = None
    except Exception as exc:
        st.session_state["solution"] = None
        st.session_state["ui_error"] = f"{exc}\n\n{traceback.format_exc()}"

with tab_result:
    solution = st.session_state["solution"]
    if solution:
        summary_df, stops_df = route_export_frames(solution)
        unserved_df = pd.DataFrame(solution["unserved"]) if solution["unserved"] else pd.DataFrame()
        total_capacity = sum(v["capacity"] for v in dataframe_to_records(st.session_state["vehicles_df"], "vehicle"))
        used_capacity = sum(r["delivery_used"] for r in solution["routes"])
        util_percent = (used_capacity / total_capacity * 100) if total_capacity else 0
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"<div class='metric-container'><div class='metric-label'>🌍 Общая дистанция</div><div class='metric-value'>{solution['total_distance_km']:.1f} км</div></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='metric-container' style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);'><div class='metric-label'>⏱️ Время рейсов</div><div class='metric-value'>{solution['total_duration_min']//60}ч {solution['total_duration_min']%60}м</div></div>", unsafe_allow_html=True)
        with m3:
            st.markdown(f"<div class='metric-container' style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);'><div class='metric-label'>🚛 Машин в рейсе</div><div class='metric-value'>{solution['used_vehicles']}</div></div>", unsafe_allow_html=True)
        with m4:
            st.markdown(f"<div class='metric-container' style='background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);'><div class='metric-label'>📦 Загрузка парка</div><div class='metric-value'>{util_percent:.1f}%</div></div>", unsafe_allow_html=True)
        st.subheader("📋 Сводная таблица")
        st.dataframe(summary_df, use_container_width=True)
        if not unserved_df.empty:
            st.subheader("⚠️ Необслуженные магазины")
            st.dataframe(unserved_df, use_container_width=True)
        st.subheader("🗺️ Карта")
        all_points = dataframe_to_records(st.session_state["depots_df"], "depot") + dataframe_to_records(st.session_state["stores_df"], "store")
        if all_points:
            center_lat = sum(p["lat"] for p in all_points) / len(all_points)
            center_lon = sum(p["lon"] for p in all_points) / len(all_points)
            fmap = folium.Map(location=[center_lat, center_lon], zoom_start=10)
            for depot in dataframe_to_records(st.session_state["depots_df"], "depot"):
                folium.Marker([depot["lat"], depot["lon"]], tooltip=f"🏭 {depot['name']}", popup=f"{depot['name']}<br>{depot['address']}", icon=folium.Icon(color="black", icon="home", prefix="fa")).add_to(fmap)
            for idx, route in enumerate(solution["routes"], start=1):
                color = COLORS[(idx - 1) % len(COLORS)]
                group = folium.FeatureGroup(name=f"Маршрут {idx}: {route['vehicle_type']}")
                for seg in route["geometry"]:
                    if seg:
                        folium.PolyLine(seg, color=color, weight=5, opacity=0.75, tooltip=f"Маршрут {idx}").add_to(group)
                group.add_to(fmap)
            folium.LayerControl(collapsed=False).add_to(fmap)
            safe_folium_display(fmap)
        st.subheader("📤 Экспорт")
        geojson_bytes = json.dumps(build_geojson(solution), ensure_ascii=False, indent=2).encode("utf-8")
        excel_bytes = build_excel_bytes(summary_df, stops_df, unserved_df)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button("CSV (маршруты)", summary_df.to_csv(index=False).encode("utf-8-sig"), "routes_summary.csv", "text/csv")
        with c2:
            st.download_button("Excel", excel_bytes, "vrp_routes.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with c3:
            st.download_button("GeoJSON", geojson_bytes, "routes.geojson", "application/geo+json")
    else:
        st.markdown("<div class='info-box'><h3>👋 Версия с защитой интерфейса</h3><ul><li>безопасный data editor</li><li>безопасное отображение карты</li><li>traceback прямо в UI</li></ul></div>", unsafe_allow_html=True)
