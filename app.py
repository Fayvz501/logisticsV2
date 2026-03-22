"""
RouteOptimizer VRPTW+ — Gloria Jeans Logistics
Полная переписка с нуля. Один файл, без внешних модулей.
"""

import io, json, math, traceback
from typing import List, Dict

import folium
import numpy as np
import pandas as pd
import requests
import streamlit as st
from folium import PolyLine, CircleMarker, Marker, Icon, Popup, FeatureGroup, LayerControl
from streamlit_folium import folium_static
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

# ╔══════════════════════════════════════════════════════════════╗
# ║                        CONSTANTS                            ║
# ╚══════════════════════════════════════════════════════════════╝

DEPOTS = [
    {"id": "depot_grivno", "name": "Склад GJ — Гривно",
     "address": "МО, Подольск, пром. парк Гривно, 1",
     "lat": 55.354159, "lon": 37.573241, "tw_start": 360, "tw_end": 1440},
    {"id": "depot_orientir", "name": "РЦ GJ — Ориентир-Юг",
     "address": "МО, Подольск, инд. парк Ориентир-Юг",
     "lat": 55.3249, "lon": 37.5335, "tw_start": 360, "tw_end": 1440},
]

STORES = [
    {"id":1,"name":"GJ Тверская","address":"Тверская ул., 16с1","lat":55.764551,"lon":37.606406,"demand":4,"pickup_demand":0,"tw_start":600,"tw_end":1320,"service_time":20},
    {"id":2,"name":"GJ Новый Арбат","address":"ул. Новый Арбат, 11с1","lat":55.752085,"lon":37.596237,"demand":3,"pickup_demand":0,"tw_start":600,"tw_end":1320,"service_time":20},
    {"id":3,"name":"GJ Киевский","address":"пл. Киевского Вокзала, 2","lat":55.744637,"lon":37.566072,"demand":5,"pickup_demand":1,"tw_start":600,"tw_end":1320,"service_time":30},
    {"id":4,"name":"GJ Мозаика","address":"7-я Кожуховская ул., 9","lat":55.710692,"lon":37.675109,"demand":3,"pickup_demand":0,"tw_start":600,"tw_end":1320,"service_time":20},
    {"id":5,"name":"GJ Орджоникидзе","address":"ул. Орджоникидзе, 11","lat":55.709160,"lon":37.595321,"demand":2,"pickup_demand":0,"tw_start":600,"tw_end":1260,"service_time":15},
    {"id":6,"name":"GJ Энтузиастов","address":"ш. Энтузиастов, 12к2","lat":55.747368,"lon":37.707107,"demand":4,"pickup_demand":1,"tw_start":600,"tw_end":1320,"service_time":25},
    {"id":7,"name":"GJ Зеленодольская","address":"Зеленодольская ул., 42","lat":55.701856,"lon":37.764528,"demand":3,"pickup_demand":0,"tw_start":600,"tw_end":1320,"service_time":20},
    {"id":8,"name":"GJ Черемушки","address":"Б. Черемушкинская ул., 1","lat":55.690283,"lon":37.601879,"demand":4,"pickup_demand":1,"tw_start":600,"tw_end":1320,"service_time":25},
    {"id":9,"name":"GJ Шереметьевская","address":"Шереметьевская ул., 6к1","lat":55.795403,"lon":37.617033,"demand":2,"pickup_demand":0,"tw_start":600,"tw_end":1320,"service_time":20},
    {"id":10,"name":"GJ Комсомольская","address":"Комсомольская пл., 6","lat":55.775864,"lon":37.660413,"demand":3,"pickup_demand":0,"tw_start":540,"tw_end":1320,"service_time":20},
    {"id":11,"name":"GJ Афимолл","address":"Пресненская наб., 2","lat":55.749162,"lon":37.539742,"demand":5,"pickup_demand":1,"tw_start":600,"tw_end":1320,"service_time":35},
    {"id":12,"name":"GJ Columbus","address":"Кировоградская ул., 13А","lat":55.612146,"lon":37.606999,"demand":5,"pickup_demand":1,"tw_start":600,"tw_end":1320,"service_time":30},
    {"id":13,"name":"GJ Хорошёвское","address":"Хорошёвское ш., 27","lat":55.777105,"lon":37.523716,"demand":3,"pickup_demand":0,"tw_start":600,"tw_end":1320,"service_time":20},
    {"id":14,"name":"GJ Каховка","address":"ул. Каховка, 29А","lat":55.656357,"lon":37.569360,"demand":2,"pickup_demand":0,"tw_start":600,"tw_end":1320,"service_time":15},
    {"id":15,"name":"GJ Открытое ш.","address":"Открытое ш., 4с1","lat":55.809090,"lon":37.729970,"demand":2,"pickup_demand":0,"tw_start":600,"tw_end":1320,"service_time":20},
    {"id":16,"name":"GJ Поречная","address":"Поречная ул., 10","lat":55.649830,"lon":37.770052,"demand":3,"pickup_demand":1,"tw_start":600,"tw_end":1320,"service_time":20},
    {"id":17,"name":"GJ Пр. Мира","address":"пр-т Мира, 211к2","lat":55.845855,"lon":37.662093,"demand":5,"pickup_demand":1,"tw_start":600,"tw_end":1320,"service_time":30},
    {"id":18,"name":"GJ Океания","address":"Кутузовский пр-т, 57","lat":55.727988,"lon":37.476061,"demand":4,"pickup_demand":1,"tw_start":600,"tw_end":1320,"service_time":25},
    {"id":19,"name":"GJ Ленинский","address":"Ленинский пр-т, 109","lat":55.663842,"lon":37.511445,"demand":3,"pickup_demand":0,"tw_start":600,"tw_end":1320,"service_time":20},
    {"id":20,"name":"GJ Спектр","address":"Новоясеневский пр-т, 1","lat":55.619472,"lon":37.509289,"demand":2,"pickup_demand":0,"tw_start":600,"tw_end":1320,"service_time":20},
    {"id":21,"name":"GJ Avenue","address":"пр-т Вернадского, 86А","lat":55.663024,"lon":37.481001,"demand":3,"pickup_demand":0,"tw_start":600,"tw_end":1320,"service_time":20},
    {"id":22,"name":"GJ Староватутинский","address":"Староватутинский пр., 14","lat":55.875804,"lon":37.665551,"demand":2,"pickup_demand":0,"tw_start":600,"tw_end":1200,"service_time":15},
    {"id":23,"name":"GJ Облака","address":"Ореховый б-р, 22А","lat":55.612045,"lon":37.732718,"demand":3,"pickup_demand":1,"tw_start":600,"tw_end":1320,"service_time":20},
]

VEHICLES = [
    {"id":0,"name":"Фура 1 (20м³)","capacity":20.0,"pickup_capacity":20.0,"depot_id":"depot_grivno","max_shift_min":600},
    {"id":1,"name":"Фура 2 (20м³)","capacity":20.0,"pickup_capacity":20.0,"depot_id":"depot_orientir","max_shift_min":600},
    {"id":2,"name":"Грузовик 1 (15м³)","capacity":15.0,"pickup_capacity":15.0,"depot_id":"depot_grivno","max_shift_min":540},
    {"id":3,"name":"Грузовик 2 (15м³)","capacity":15.0,"pickup_capacity":15.0,"depot_id":"depot_orientir","max_shift_min":540},
    {"id":4,"name":"Газель (10м³)","capacity":10.0,"pickup_capacity":10.0,"depot_id":"depot_grivno","max_shift_min":480},
]

TRAFFIC = {"offpeak": 0.9, "day": 1.0, "morning_peak": 1.25, "evening_peak": 1.35}
TRAFFIC_LABELS = {"offpeak":"Вне пик","day":"День","morning_peak":"Утр. пик","evening_peak":"Веч. пик"}
GOAL_LABELS = {"time":"Мин. времени","distance":"Мин. расстояния","fleet":"Мин. машин","balanced":"Баланс"}
COLORS = ["blue","green","red","purple","orange","darkred","darkblue","darkgreen","cadetblue","darkpurple","pink","lightblue","lightgreen","gray","black"]


def haversine(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.atan2(math.sqrt(a), math.sqrt(1-a))


def build_matrices(nodes, traffic_profile="day"):
    factor = TRAFFIC.get(traffic_profile, 1.0)
    coords = ";".join(f"{n['lon']},{n['lat']}" for n in nodes)
    try:
        resp = requests.get(
            f"http://router.project-osrm.org/table/v1/driving/{coords}",
            params={"annotations": "duration,distance"}, timeout=10
        )
        data = resp.json()
        if data.get("code") == "Ok":
            n = len(nodes)
            tm = [[0]*n for _ in range(n)]
            dm = [[0]*n for _ in range(n)]
            for i in range(n):
                for j in range(n):
                    if i != j:
                        tm[i][j] = max(1, int((data["durations"][i][j] / 60) * factor))
                        dm[i][j] = int(data["distances"][i][j])
            return tm, dm
    except Exception:
        pass
    speeds = {"offpeak":36,"day":30,"morning_peak":24,"evening_peak":22}
    spd = speeds.get(traffic_profile, 30)
    n = len(nodes)
    tm = [[0]*n for _ in range(n)]
    dm = [[0]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                d = int(haversine(nodes[i]["lat"], nodes[i]["lon"], nodes[j]["lat"], nodes[j]["lon"]) * 1.35)
                dm[i][j] = d
                tm[i][j] = max(1, int((d/1000/spd)*60))
    return tm, dm


def fetch_road_geometry(nodes, route_indices):
    if len(route_indices) < 2:
        return []
    coords = ";".join(f"{nodes[i]['lon']},{nodes[i]['lat']}" for i in route_indices)
    try:
        resp = requests.get(
            f"http://router.project-osrm.org/route/v1/driving/{coords}",
            params={"overview": "full", "geometries": "geojson", "steps": "false"},
            timeout=8
        )
        data = resp.json()
        if data.get("code") == "Ok" and data.get("routes"):
            coords_list = data["routes"][0]["geometry"]["coordinates"]
            return [[(c[1], c[0]) for c in coords_list]]
    except Exception:
        pass
    segments = []
    for k in range(len(route_indices) - 1):
        a, b = route_indices[k], route_indices[k+1]
        segments.append([(nodes[a]["lat"], nodes[a]["lon"]), (nodes[b]["lat"], nodes[b]["lon"])])
    return segments


def solve_vrp(depots, stores, vehicles_config, max_search_time=10, optimization_goal="time", traffic_profile="day", penalty=100000, balance_routes=True):
    nodes = []
    depot_map = {}
    for d in depots:
        depot_map[d["id"]] = len(nodes)
        nodes.append({**d, "node_type": "depot", "service_time": 0, "demand": 0, "pickup_demand": 0, "time_window": (d["tw_start"], d["tw_end"])})
    for s in stores:
        nodes.append({**s, "node_type": "store", "time_window": (s["tw_start"], s["tw_end"])})

    tm, dm = build_matrices(nodes, traffic_profile)
    starts = [depot_map[v["depot_id"]] for v in vehicles_config]
    ends = [depot_map[v["depot_id"]] for v in vehicles_config]

    manager = pywrapcp.RoutingIndexManager(len(nodes), len(vehicles_config), starts, ends)
    routing = pywrapcp.RoutingModel(manager)

    def transit_time(from_i, to_i):
        f, t = manager.IndexToNode(from_i), manager.IndexToNode(to_i)
        return tm[f][t] + int(nodes[f].get("service_time", 0))

    def transit_dist(from_i, to_i):
        f, t = manager.IndexToNode(from_i), manager.IndexToNode(to_i)
        return dm[f][t]

    def demand_cb(index):
        return int(nodes[manager.IndexToNode(index)].get("demand", 0))

    def pickup_cb(index):
        return int(nodes[manager.IndexToNode(index)].get("pickup_demand", 0))

    time_idx = routing.RegisterTransitCallback(transit_time)
    dist_idx = routing.RegisterTransitCallback(transit_dist)
    routing.SetArcCostEvaluatorOfAllVehicles(dist_idx if optimization_goal == "distance" else time_idx)

    demand_idx = routing.RegisterUnaryTransitCallback(demand_cb)
    pickup_idx = routing.RegisterUnaryTransitCallback(pickup_cb)
    routing.AddDimensionWithVehicleCapacity(demand_idx, 0, [int(v["capacity"]) for v in vehicles_config], True, "Delivery")
    routing.AddDimensionWithVehicleCapacity(pickup_idx, 0, [int(v.get("pickup_capacity", v["capacity"])) for v in vehicles_config], True, "Pickup")

    max_shift = max(int(v.get("max_shift_min", 600)) for v in vehicles_config)
    routing.AddDimension(time_idx, 1440, max_shift + 1440, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")

    for n_idx, node in enumerate(nodes):
        idx = manager.NodeToIndex(n_idx)
        s, e = node["time_window"]
        if node["node_type"] == "store":
            time_dim.CumulVar(idx).SetRange(int(s), int(e))
            routing.AddDisjunction([idx], int(penalty))

    for vid, veh in enumerate(vehicles_config):
        s_idx, e_idx = routing.Start(vid), routing.End(vid)
        ds, de = nodes[starts[vid]]["time_window"]
        time_dim.CumulVar(s_idx).SetRange(int(ds), int(de))
        time_dim.CumulVar(e_idx).SetRange(int(ds), int(min(de, ds + veh.get("max_shift_min", 600))))
        routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(s_idx))
        routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(e_idx))
        if optimization_goal == "fleet":
            routing.SetFixedCostOfVehicle(50000, vid)

    if optimization_goal == "balanced" or balance_routes:
        time_dim.SetGlobalSpanCostCoefficient(80)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = int(max_search_time)

    solution = routing.SolveWithParameters(params)
    if not solution:
        return {"routes": [], "unserved": stores, "total_distance_km": 0.0, "used_vehicles": 0, "total_duration_min": 0}

    routes, served = [], set()
    total_dist, total_dur = 0, 0

    for vid, veh in enumerate(vehicles_config):
        idx = routing.Start(vid)
        if routing.IsEnd(solution.Value(routing.NextVar(idx))):
            continue
        route_nodes, times = [], []
        while not routing.IsEnd(idx):
            route_nodes.append(manager.IndexToNode(idx))
            times.append(solution.Value(time_dim.CumulVar(idx)))
            idx = solution.Value(routing.NextVar(idx))
        route_nodes.append(manager.IndexToNode(idx))
        times.append(solution.Value(time_dim.CumulVar(idx)))

        dist = drive = wait = service = 0
        del_used = pick_used = 0
        stops = []
        for seq, node_idx in enumerate(route_nodes):
            node = nodes[node_idx]
            arr = times[seq]
            svc = int(node.get("service_time", 0))
            dep = arr + svc
            w = 0
            if seq > 0:
                prev = route_nodes[seq - 1]
                expected = times[seq - 1] + int(nodes[prev].get("service_time", 0)) + tm[prev][node_idx]
                w = max(0, arr - expected)
                wait += w
                dist += dm[prev][node_idx]
                drive += tm[prev][node_idx]
            if node["node_type"] == "store":
                served.add(node["id"])
                del_used += node.get("demand", 0)
                pick_used += node.get("pickup_demand", 0)
                service += svc
            stops.append({
                "sequence": seq, "node_type": node["node_type"], "name": node["name"],
                "address": node.get("address", ""), "lat": node["lat"], "lon": node["lon"],
                "arrival": arr, "departure": dep, "service_time": svc, "waiting": w,
                "delivery": node.get("demand", 0), "pickup": node.get("pickup_demand", 0),
            })

        duration = times[-1] - times[0]
        geom = fetch_road_geometry(nodes, route_nodes)
        total_dist += dist
        total_dur += duration
        routes.append({
            "vehicle_type": veh["name"], "depot_name": nodes[route_nodes[0]]["name"],
            "route": route_nodes, "times": times, "distance": dist, "duration": duration,
            "drive_minutes": drive, "service_minutes": service, "waiting_minutes": wait,
            "stops_count": sum(1 for n in route_nodes if nodes[n]["node_type"] == "store"),
            "delivery_used": del_used, "pickup_used": pick_used,
            "avg_speed_kmh": round((dist / 1000) / max(drive / 60, 1e-9), 1) if drive else 0,
            "geometry": geom, "stops_detail": stops,
        })

    unserved = [s for s in stores if s["id"] not in served]
    return {
        "routes": routes,
        "unserved": unserved,
        "total_distance_km": round(total_dist / 1000, 1),
        "used_vehicles": len(routes),
        "total_duration_min": int(total_dur),
    }


def fmt(minutes):
    minutes = int(minutes)
    return f"{(minutes//60)%24:02d}:{minutes%60:02d}"


def build_template_frames():
    dep = pd.DataFrame([{**d, "active": True} for d in DEPOTS])
    sto = pd.DataFrame([{**s, "active": True} for s in STORES])
    veh = pd.DataFrame([{**v, "active": True} for v in VEHICLES])
    return dep, sto, veh


def df_to_list(df, kind):
    rows = []
    for row in df.to_dict(orient="records"):
        if not row.get("active", True):
            continue
        x = {k: row[k] for k in row if k != "active"}
        if kind in ("depot", "store"):
            x["lat"] = float(x["lat"])
            x["lon"] = float(x["lon"])
            x["tw_start"] = int(x["tw_start"])
            x["tw_end"] = int(x["tw_end"])
            if kind == "store":
                x["demand"] = float(x["demand"])
                x["pickup_demand"] = float(x.get("pickup_demand", 0))
                x["service_time"] = int(x["service_time"])
        elif kind == "vehicle":
            x["capacity"] = float(x["capacity"])
            x["pickup_capacity"] = float(x["pickup_capacity"])
            x["max_shift_min"] = int(x["max_shift_min"])
        rows.append(x)
    return rows


def safe_data_editor(df, **kwargs):
    try:
        return st.data_editor(df, **kwargs)
    except Exception as e:
        st.warning(f"⚠️ data_editor недоступен: {e}. Показана обычная таблица.")
        st.dataframe(df, use_container_width=True)
        return df


st.set_page_config(page_title="RouteOptimizer VRPTW", page_icon="🚚", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.metric-box{border-radius:12px;padding:16px;color:#fff;text-align:center;box-shadow:0 3px 10px rgba(0,0,0,.12);margin-bottom:8px}
.metric-box .lbl{font-size:14px;opacity:.92}.metric-box .val{font-size:26px;font-weight:700;margin-top:4px}
.info-box{background:#f8f9fa;border-left:4px solid #3498db;padding:14px;border-radius:6px;color:#2c3e50}
</style>
""", unsafe_allow_html=True)

if "dep" not in st.session_state:
    st.session_state.dep, st.session_state.sto, st.session_state.veh = build_template_frames()
    st.session_state.result = None
    st.session_state.err = None

st.sidebar.title("🚚 RouteOptimizer VRPTW")
st.sidebar.markdown("---")

with st.sidebar.form("ctl"):
    st.subheader("⚙️ Параметры")
    goal = st.selectbox("Цель", list(GOAL_LABELS.keys()), format_func=lambda x: GOAL_LABELS[x])
    traffic = st.selectbox("Трафик", list(TRAFFIC_LABELS.keys()), format_func=lambda x: TRAFFIC_LABELS[x])
    search_sec = st.slider("Время поиска, сек", 1, 60, 12)
    penalty_val = st.number_input("Штраф за пропуск точки", min_value=1000, max_value=1_000_000, value=100000, step=5000)
    do_balance = st.checkbox("Балансировать маршруты", value=True)
    run_btn = st.form_submit_button("🚀 Рассчитать", use_container_width=True)

if st.sidebar.button("Сбросить к шаблону", use_container_width=True):
    st.session_state.dep, st.session_state.sto, st.session_state.veh = build_template_frames()
    st.session_state.result = None
    st.session_state.err = None

st.title("🗺️ Gloria Jeans Logistics VRPTW")
st.markdown("### Реальные магазины · мультисклады · временные окна · возвраты")
if st.session_state.err:
    st.error(st.session_state.err)

tab1, tab2 = st.tabs(["✏️ Данные", "📊 Результаты"])

with tab1:
    left, right = st.columns([1,2])
    with left:
        st.subheader("🏭 Склады")
        st.session_state.dep = safe_data_editor(
            st.session_state.dep, use_container_width=True, hide_index=True, num_rows="fixed",
            column_config={
                "active": st.column_config.CheckboxColumn("Вкл"),
                "tw_start": st.column_config.NumberColumn("Открытие", min_value=0, max_value=1440, step=5),
                "tw_end": st.column_config.NumberColumn("Закрытие", min_value=0, max_value=1440, step=5),
            }, key="ed_dep"
        )
        st.subheader("🚛 Парк")
        st.session_state.veh = safe_data_editor(
            st.session_state.veh, use_container_width=True, hide_index=True, num_rows="fixed",
            column_config={
                "active": st.column_config.CheckboxColumn("В рейс"),
                "capacity": st.column_config.NumberColumn("Доставка, м³", min_value=0.0, step=1.0),
                "pickup_capacity": st.column_config.NumberColumn("Забор, м³", min_value=0.0, step=1.0),
                "max_shift_min": st.column_config.NumberColumn("Смена, мин", min_value=60, max_value=1440, step=30),
                "depot_id": st.column_config.SelectboxColumn("Склад", options=st.session_state.dep["id"].tolist()),
            }, key="ed_veh"
        )
    with right:
        st.subheader("🏬 Магазины")
        st.session_state.sto = safe_data_editor(
            st.session_state.sto, use_container_width=True, hide_index=True, num_rows="fixed",
            column_config={
                "active": st.column_config.CheckboxColumn("Активен"),
                "demand": st.column_config.NumberColumn("Доставка, м³", min_value=0.0, step=1.0),
                "pickup_demand": st.column_config.NumberColumn("Возвраты, м³", min_value=0.0, step=1.0),
                "tw_start": st.column_config.NumberColumn("Открытие", min_value=0, max_value=1440, step=5),
                "tw_end": st.column_config.NumberColumn("Закрытие", min_value=0, max_value=1440, step=5),
                "service_time": st.column_config.NumberColumn("Разгрузка, мин", min_value=0, max_value=240, step=5),
            }, key="ed_sto"
        )
    try:
        _dep = st.session_state.get("ed_dep", st.session_state.dep)
        _sto = st.session_state.get("ed_sto", st.session_state.sto)
        _veh = st.session_state.get("ed_veh", st.session_state.veh)
        sl = df_to_list(_sto, "store")
        vl = df_to_list(_veh, "vehicle")
        dd = sum(s["demand"] for s in sl)
        dp = sum(s.get("pickup_demand",0) for s in sl)
        cd = sum(v["capacity"] for v in vl)
        cp = sum(v.get("pickup_capacity",0) for v in vl)
        st.markdown("---")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Доставка", f"{dd:.0f} м³", f"{cd-dd:+.0f} м³")
        c2.metric("Возвраты", f"{dp:.0f} м³", f"{cp-dp:+.0f} м³")
        c3.metric("Складов", len(df_to_list(_dep, "depot")))
        c4.metric("Машин", len(vl))
    except Exception:
        pass

if run_btn:
    try:
        dep_df = st.session_state.get("ed_dep", st.session_state.dep)
        sto_df = st.session_state.get("ed_sto", st.session_state.sto)
        veh_df = st.session_state.get("ed_veh", st.session_state.veh)
        st.session_state.dep = dep_df
        st.session_state.sto = sto_df
        st.session_state.veh = veh_df
        depots_list = df_to_list(dep_df, "depot")
        stores_list = df_to_list(sto_df, "store")
        vehicles_list = df_to_list(veh_df, "vehicle")
        if not depots_list: raise ValueError("Нужен хотя бы один склад")
        if not vehicles_list: raise ValueError("Нужна хотя бы одна машина")
        if not stores_list: raise ValueError("Нет активных магазинов")
        with st.spinner("⏳ Расчёт маршрутов…"):
            st.session_state.result = solve_vrp(
                depots=depots_list, stores=stores_list, vehicles_config=vehicles_list,
                max_search_time=search_sec, optimization_goal=goal,
                traffic_profile=traffic, penalty=int(penalty_val), balance_routes=do_balance,
            )
        st.session_state.err = None
    except Exception as exc:
        st.session_state.result = None
        st.session_state.err = f"Ошибка: {exc}"

with tab2:
    res = st.session_state.result
    if res and res.get("routes"):
        try:
            udf = pd.DataFrame(res["unserved"]) if res["unserved"] else pd.DataFrame()
            veh_list = df_to_list(st.session_state.veh, "vehicle")
            tc = sum(v["capacity"] for v in veh_list) or 1
            uc = sum(r["delivery_used"] for r in res["routes"])
            cols = st.columns(4)
            labels = ["🌍 Дистанция","⏱️ Время","🚛 Машин","📦 Загрузка"]
            values = [f"{res['total_distance_km']:.1f} км", f"{res['total_duration_min']//60}ч {res['total_duration_min']%60}м", str(res['used_vehicles']), f"{uc/tc*100:.1f}%"]
            bgs = ["linear-gradient(135deg,#667eea,#764ba2)","linear-gradient(135deg,#f093fb,#f5576c)","linear-gradient(135deg,#4facfe,#00f2fe)","linear-gradient(135deg,#43e97b,#38f9d7)"]
            for col, lbl, val, bg in zip(cols, labels, values, bgs):
                col.markdown(f"<div class='metric-box' style='background:{bg}'><div class='lbl'>{lbl}</div><div class='val'>{val}</div></div>", unsafe_allow_html=True)
            rows = []
            for i, r in enumerate(res["routes"], 1):
                rows.append({"№":i,"Машина":r["vehicle_type"],"Склад":r["depot_name"],"Точек":r["stops_count"],"Км":round(r["distance"]/1000,1),"Езда мин":r["drive_minutes"],"Сервис мин":r["service_minutes"],"Ожид мин":r["waiting_minutes"],"Всего мин":r["duration"],"Дост м³":r["delivery_used"],"Забор м³":r["pickup_used"],"Ср.скор км/ч":r["avg_speed_kmh"]})
            st.subheader("📋 Сводка")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            if not udf.empty:
                st.subheader("⚠️ Необслуженные")
                st.dataframe(udf, use_container_width=True, hide_index=True)
            st.subheader("🗺️ Карта маршрутов")
            dep_list = df_to_list(st.session_state.dep, "depot")
            sto_list = df_to_list(st.session_state.sto, "store")
            all_pts = dep_list + sto_list
            if all_pts:
                clat = sum(p["lat"] for p in all_pts) / len(all_pts)
                clon = sum(p["lon"] for p in all_pts) / len(all_pts)
                m = folium.Map(location=[clat, clon], zoom_start=10, tiles="CartoDB positron")
                for d in dep_list:
                    Marker([d["lat"],d["lon"]], tooltip=f"🏭 {d['name']}", popup=f"<b>{d['name']}</b><br>{d.get('address','')}", icon=Icon(color="black", icon="home", prefix="fa")).add_to(m)
                for i, route in enumerate(res["routes"], 1):
                    color = COLORS[(i-1) % len(COLORS)]
                    grp = FeatureGroup(name=f"Маршрут {i}: {route['vehicle_type']}")
                    for seg in route["geometry"]:
                        if seg and len(seg) >= 2:
                            PolyLine(seg, color=color, weight=5, opacity=0.8, tooltip=f"Маршрут {i}").add_to(grp)
                    for stop in route["stops_detail"]:
                        if stop["node_type"] == "depot":
                            continue
                        html = (f"<b>Маршрут {i}</b><br>{stop['name']}<br>⏰ {fmt(stop['arrival'])} → {fmt(stop['departure'])}<br>📦 {stop['delivery']} м³ / ♻️ {stop['pickup']} м³<br>🕒 ожид. {stop['waiting']} мин")
                        CircleMarker([stop["lat"], stop["lon"]], radius=9, color=color, fill=True, fill_color=color, fill_opacity=0.85, popup=Popup(html, max_width=280), tooltip=f"{stop['sequence']}. {stop['name']}").add_to(grp)
                    grp.add_to(m)
                if not udf.empty:
                    for _, row in udf.iterrows():
                        Marker([row["lat"],row["lon"]], tooltip=f"⚠ {row['name']}", icon=Icon(color="lightgray", icon="remove-sign")).add_to(m)
                LayerControl(collapsed=False).add_to(m)
                folium_static(m, width=None, height=580)
            st.subheader("📍 Маршрутный лист")
            with st.expander("Подробности"):
                for i, route in enumerate(res["routes"], 1):
                    st.markdown(f"**Маршрут {i} — {route['vehicle_type']} ({route['depot_name']})**")
                    for s in route["stops_detail"]:
                        st.text(f"  {s['sequence']:>2}. {s['name']:30s} {fmt(s['arrival'])}→{fmt(s['departure'])}  дост {s['delivery']}м³  забор {s['pickup']}м³  ожид {s['waiting']}мин")
                    st.divider()
            st.subheader("📤 Экспорт")
            sdf = pd.DataFrame(rows)
            stdf_rows = []
            for i, r in enumerate(res["routes"], 1):
                for s in r["stops_detail"]:
                    stdf_rows.append({"маршрут":i,"машина":r["vehicle_type"],"seq":s["sequence"],"тип":s["node_type"],"название":s["name"],"адрес":s["address"],"прибытие":fmt(s["arrival"]),"убытие":fmt(s["departure"]),"доставка":s["delivery"],"забор":s["pickup"],"ожид":s["waiting"]})
            stdf = pd.DataFrame(stdf_rows)
            feats = []
            for i, r in enumerate(res["routes"], 1):
                for seg in r["geometry"]:
                    if seg:
                        feats.append({"type":"Feature","properties":{"route":i,"vehicle":r["vehicle_type"]},"geometry":{"type":"LineString","coordinates":[[p[1],p[0]] for p in seg]}})
            gj = json.dumps({"type":"FeatureCollection","features":feats}, ensure_ascii=False)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                sdf.to_excel(w, sheet_name="маршруты", index=False)
                stdf.to_excel(w, sheet_name="остановки", index=False)
                if not udf.empty:
                    udf.to_excel(w, sheet_name="необслуженные", index=False)
            buf.seek(0)
            e1,e2,e3 = st.columns(3)
            e1.download_button("CSV", sdf.to_csv(index=False).encode("utf-8-sig"), "routes.csv")
            e2.download_button("Excel", buf.getvalue(), "routes.xlsx")
            e3.download_button("GeoJSON", gj.encode("utf-8"), "routes.geojson")
        except Exception as exc:
            st.error(f"Ошибка вывода: {exc}")
            st.code(traceback.format_exc())
    elif res and not res.get("routes"):
        st.warning("Решение не найдено — ни одна машина не вышла. Увеличьте время поиска или снизьте штраф.")
        if res.get("unserved"):
            st.dataframe(pd.DataFrame(res["unserved"]), use_container_width=True)
    else:
        st.markdown("<div class='info-box'><h3>👋 Нажмите «🚀 Рассчитать» в боковой панели</h3><p>Мультисклады · Временные окна · Возвраты · 4 цели оптимизации · Экспорт</p></div>", unsafe_allow_html=True)
