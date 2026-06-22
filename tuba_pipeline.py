"""
PIPELINE LENGKAP: Optimalisasi Rute ZRS 68 Tulang Bawang
=========================================================
Step 1: Prepare & Clean Data
Step 2: Add Coordinates from KML
Step 3: Route Optimization (Balanced Dijkstra-style dengan Haversine)
Step 4: Generate Interactive Map (HTML)
"""

import pandas as pd
import re
import xml.etree.ElementTree as ET
import os
import math
import json
import pickle

# ============================================================
#  KONFIGURASI PATH
# ============================================================
INPUT_CSV   = r"D:\Ayak\Project Rolling\Fundamental Tulang Bawang.xlsx - ZRS 68.csv"
OUTPUT_CSV  = r"D:\Ayak\Project Rolling\ZRS68_Filtered.csv"
KML_DIR     = r"D:\Ayak\Project Rolling\COV TUBA MEY 26 (1).kmz (1)"
OUTPUT_HTML = r"D:\Ayak\Project Rolling\ZRS68_map.html"

# Koordinat terminal (kantor/depo)
# Tulang Bawang — pakai titik
TERMINAL_COORD = (-4.280465, 105.2165843)

DAYS = ["SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU"]

VALID_SALES = {
    "Beni Saputra",
    "Rudi Anggoro",
    "Yuda Nurisman",
    "Ihwal Bayu Saddera",
}

# ============================================================
#  STEP 1: PREPARE DATA
# ============================================================
def normalize_jwk(s):
    if pd.isna(s) or str(s).strip() == "":
        return ""
    s = str(s).strip().upper()
    s = re.sub(r'\s+', ' ', s)
    # Mapping kata Indonesia ke format standar
    s = s.replace("MONDAY","SENIN").replace("TUESDAY","SELASA")\
         .replace("WEDNESDAY","RABU").replace("THURSDAY","KAMIS")\
         .replace("FRIDAY","JUMAT").replace("SATURDAY","SABTU")
    return s

def clean_customer_id(val):
    val = str(val).strip()
    # Hapus .0 dari float
    if val.endswith('.0'):
        val = val[:-2]
    return val

def step1_prepare():
    print("=" * 60)
    print("STEP 1: PREPARE & CLEAN DATA")
    print("=" * 60)

    df = pd.read_csv(INPUT_CSV, encoding='utf-8', sep=';',
                     dtype={'Customer': str}, on_bad_lines='skip')
    print(f"Baris awal          : {len(df)}")

    # Bersihkan Customer ID
    df['Customer'] = df['Customer'].apply(clean_customer_id)

    # Normalisasi kolom
    df['JWK SALESMAN']     = df['JWK'].apply(normalize_jwk)
    df['Personnel Name']   = df['Sales'].fillna('').str.strip()
    df['Personnel Number'] = df['Represent.'].apply(
        lambda x: str(int(float(x))) if pd.notna(x) and str(x).strip() != '' else ''
    )

    # Filter hanya 4 sales utama (buang baris kosong / PR)
    df_valid = df[df['Personnel Name'].isin(VALID_SALES)].copy()
    print(f"Setelah filter sales: {len(df_valid)}")

    # Drop baris duplikat persis
    df_valid = df_valid.drop_duplicates()
    print(f"Setelah drop duplikat: {len(df_valid)}")

    # Drop baris tanpa JWK
    df_valid = df_valid[df_valid['JWK SALESMAN'].str.len() > 0].copy()
    print(f"Setelah drop no-JWK : {len(df_valid)}")
    print(f"Customer unik       : {df_valid['Customer'].nunique()}")

    # Tambah kolom koordinat kosong
    df_valid['Latitude']  = ''
    df_valid['Longitude'] = ''

    keep_cols = ['Customer', 'Name 1', 'Street',
                 'Personnel Number', 'Personnel Name',
                 'JWK SALESMAN', 'Latitude', 'Longitude']
    df_out = df_valid[keep_cols].reset_index(drop=True)

    print("\n=== Distribusi JWK per Sales ===")
    for sales in sorted(df_out['Personnel Name'].unique()):
        sdf = df_out[df_out['Personnel Name'] == sales]
        counts = sdf['JWK SALESMAN'].value_counts()
        print(f"\n  {sales} ({len(sdf)} toko):")
        for k, v in counts.items():
            print(f"    {k}: {v}")

    df_out.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
    print(f"\nOutput: {OUTPUT_CSV}")
    return df_out


# ============================================================
#  STEP 2: ADD COORDINATES FROM KML
# ============================================================
def parse_kml_simpledata(kml_path):
    """Parse KML dengan SimpleData schema."""
    mapping = {}  # customer_id -> (lat, lon)
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    try:
        tree = ET.parse(kml_path)
        root = tree.getroot()
        for pm in root.findall('.//kml:Placemark', ns):
            cust = None
            lat  = None
            lon  = None
            for sd in pm.findall('.//kml:SimpleData', ns):
                name = sd.get('name', '')
                val  = sd.text.strip() if sd.text else ''
                if name == 'Customer':
                    # Bersihkan ID
                    try:
                        cust = str(int(float(val)))
                    except:
                        cust = val.rstrip('.0') if val.endswith('.0') else val
                elif name == 'LAT':
                    lat = val
                elif name == 'LONG':
                    lon = val
            # Fallback ke koordinat langsung jika LAT/LONG tidak ada
            if (lat is None or lon is None):
                coords_elem = pm.find('.//kml:coordinates', ns)
                if coords_elem is not None and coords_elem.text:
                    parts = coords_elem.text.strip().split(',')
                    if len(parts) >= 2:
                        lon = parts[0].strip()
                        lat = parts[1].strip()
            if cust and lat and lon:
                mapping[cust] = (lat, lon)
    except Exception as e:
        print(f"  ERROR parsing {kml_path}: {e}")
    return mapping

def step2_add_coordinates():
    print("\n" + "=" * 60)
    print("STEP 2: ADD COORDINATES FROM KML")
    print("=" * 60)

    # Gabungkan semua KML
    full_mapping = {}
    for fname in os.listdir(KML_DIR):
        if fname.lower().endswith('.kml'):
            path = os.path.join(KML_DIR, fname)
            m = parse_kml_simpledata(path)
            print(f"  {fname}: {len(m)} titik")
            full_mapping.update(m)
    print(f"Total mapping KML: {len(full_mapping)} titik unik")

    df = pd.read_csv(OUTPUT_CSV, dtype={'Customer': str})
    matched = 0
    not_matched = []

    for i, row in df.iterrows():
        cid = str(row['Customer']).strip()
        if cid in full_mapping:
            lat, lon = full_mapping[cid]
            df.at[i, 'Latitude']  = lat
            df.at[i, 'Longitude'] = lon
            matched += 1
        else:
            not_matched.append(cid)

    df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')

    total = len(df)
    print(f"\nMatched  : {matched}/{total} ({matched/total*100:.1f}%)")
    print(f"Unmatched: {len(not_matched)}")
    if not_matched[:10]:
        print(f"  Contoh tidak match: {not_matched[:10]}")

    return df


# ============================================================
#  STEP 3: ROUTE OPTIMIZATION
# ============================================================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_base_day(s):
    if pd.isna(s) or not s: return "SENIN"
    s = str(s).upper()
    for d in DAYS:
        if d in s: return d
    return "SENIN"

def get_cycle(s):
    if pd.isna(s) or not s: return "Weekly"
    s = str(s).upper()
    if "GANJIL" in s: return "Ganjil"
    if "GENAP" in s: return "Genap"
    return "Weekly"

def calculate_targets(total_visits):
    """Distribusi target per hari: Sabtu ~0.5x hari kerja."""
    sat_target = round(total_visits / 11.0)
    remaining  = total_visits - sat_target
    wd_base    = remaining // 5
    wd_extra   = remaining % 5
    res = {d: wd_base for d in DAYS if d != 'SABTU'}
    res['SABTU'] = sat_target
    for i, d in enumerate(DAYS):
        if i < wd_extra:
            res[d] += 1
    return res

def step3_optimize():
    print("\n" + "=" * 60)
    print("STEP 3: ROUTE OPTIMIZATION")
    print("=" * 60)

    df = pd.read_csv(OUTPUT_CSV, dtype={'Customer': str})

    # Filter hanya baris dengan koordinat
    df['Latitude']  = pd.to_numeric(df['Latitude'],  errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')

    def fix_lat(val):
        if pd.isna(val): return val
        v = float(val)
        while abs(v) > 90: v /= 10.0
        if v < -10: v /= 10.0
        return v

    def fix_lon(val):
        if pd.isna(val): return val
        v = float(val)
        while abs(v) > 180: v /= 10.0
        return v
    
    df['Latitude'] = df['Latitude'].apply(fix_lat)
    df['Longitude'] = df['Longitude'].apply(fix_lon)
    df['Cycle']     = df['JWK SALESMAN'].apply(get_cycle)

    valid_df = df[df['Latitude'].notnull() & df['Longitude'].notnull()].copy()
    print(f"Baris dengan koordinat: {len(valid_df)}")
    print(f"Baris tanpa koordinat : {len(df) - len(valid_df)} (dilewati)")

    valid_df['Optimized JWK'] = ""

    salespeople = valid_df['Personnel Name'].unique()
    summaries   = []

    for sales in salespeople:
        sdf = valid_df[valid_df['Personnel Name'] == sales].copy()
        if sdf.empty: continue
        print(f"\n  Optimizing: {sales} ({len(sdf)} toko dengan koordinat)")

        # Kelompokkan per (Customer, BaseDay) untuk konsolidasi Ganjil+Genap
        sdf['BaseDay'] = sdf['JWK SALESMAN'].apply(get_base_day)

        # Gunakan index langsung (sudah unik karena tidak di-group lagi)
        weekly_idx = sdf[sdf['Cycle'] == 'Weekly'].index.tolist()
        ganjil_idx = sdf[sdf['Cycle'] == 'Ganjil'].index.tolist()
        genap_idx  = sdf[sdf['Cycle'] == 'Genap'].index.tolist()

        targets_w1 = calculate_targets(len(weekly_idx) + len(ganjil_idx))
        targets_w2 = calculate_targets(len(weekly_idx) + len(genap_idx))

        print(f"    W1 targets: {targets_w1}")
        print(f"    W2 targets: {targets_w2}")

        # --- Seeding: K-Medoids dengan Haversine ---
        nodes = list(sdf.index)
        coords = {idx: (sdf.at[idx, 'Latitude'], sdf.at[idx, 'Longitude']) for idx in nodes}

        def dist_to_terminal(idx):
            c = coords[idx]
            return haversine(TERMINAL_COORD[0], TERMINAL_COORD[1], c[0], c[1])

        def dist_nodes(i, j):
            ci, cj = coords[i], coords[j]
            return haversine(ci[0], ci[1], cj[0], cj[1])

        # Seed awal: K-Means++ style untuk 6 cluster
        seeds = []
        seeds.append(max(nodes, key=dist_to_terminal))  # Terjauh dari terminal
        for _ in range(5):
            seeds.append(max(
                [n for n in nodes if n not in seeds],
                key=lambda n: min(dist_nodes(n, s) for s in seeds)
            ))

        # K-Medoids refinement (10 iterasi)
        for _ in range(10):
            clusters = {s: [] for s in seeds}
            for n in nodes:
                best = min(seeds, key=lambda s: dist_nodes(n, s))
                clusters[best].append(n)
            new_seeds = []
            for s, c_nodes in clusters.items():
                if not c_nodes:
                    new_seeds.append(s)
                    continue
                best_medoid = min(
                    c_nodes,
                    key=lambda core: sum(dist_nodes(core, other) for other in c_nodes)
                )
                new_seeds.append(best_medoid)
            seeds = new_seeds

        day_to_seed   = {d: seeds[i] for i, d in enumerate(DAYS)}
        day_map       = {}  # idx -> day

        # Assign awal ke seed terdekat
        for idx in nodes:
            best_d = min(DAYS, key=lambda d: dist_nodes(idx, day_to_seed[d]))
            day_map[idx] = best_d

        def get_loads(cmap):
            l1 = {d: 0 for d in DAYS}
            l2 = {d: 0 for d in DAYS}
            for idx, d in cmap.items():
                cyc = sdf.at[idx, 'Cycle']
                if cyc != 'Genap':  l1[d] += 1
                if cyc != 'Ganjil': l2[d] += 1
            return l1, l2

        # Ultra-tight balancing
        for it in range(5000):
            l1, l2 = get_loads(day_map)

            def get_dev(load, target, d):
                tol = 0 if d == 'SABTU' else 1
                over  = max(0, load - (target + tol))
                under = max(0, (target - tol) - load)
                return over**2 + under**2

            total_dev = sum(
                get_dev(l1[d], targets_w1[d], d) +
                get_dev(l2[d], targets_w2[d], d)
                for d in DAYS
            )
            if total_dev == 0:
                break

            best_move = None
            for idx, d_from in day_map.items():
                cyc   = sdf.at[idx, 'Cycle']
                s_from = day_to_seed[d_from]
                dist_from = dist_nodes(idx, s_from)

                dev_from_cur = (
                    get_dev(l1[d_from], targets_w1[d_from], d_from) +
                    get_dev(l2[d_from], targets_w2[d_from], d_from)
                )

                for d_to in DAYS:
                    if d_to == d_from: continue
                    s_to = day_to_seed[d_to]
                    dist_to = dist_nodes(idx, s_to)

                    dev_to_cur = (
                        get_dev(l1[d_to], targets_w1[d_to], d_to) +
                        get_dev(l2[d_to], targets_w2[d_to], d_to)
                    )

                    nl1_f, nl1_t = l1[d_from], l1[d_to]
                    nl2_f, nl2_t = l2[d_from], l2[d_to]
                    if cyc != 'Genap':  nl1_f -= 1; nl1_t += 1
                    if cyc != 'Ganjil': nl2_f -= 1; nl2_t += 1

                    dev_from_new = (
                        get_dev(nl1_f, targets_w1[d_from], d_from) +
                        get_dev(nl2_f, targets_w2[d_from], d_from)
                    )
                    dev_to_new = (
                        get_dev(nl1_t, targets_w1[d_to], d_to) +
                        get_dev(nl2_t, targets_w2[d_to], d_to)
                    )

                    improvement = (dev_from_cur + dev_to_cur) - (dev_from_new + dev_to_new)
                    if improvement > 0:
                        score = (improvement, -(dist_to - dist_from))
                        if best_move is None or score > best_move[2]:
                            best_move = (idx, d_to, score)

            if not best_move:
                break
            day_map[best_move[0]] = best_move[1]

        # Local search swap (proximity refinement)
        for _ in range(5):
            swapped = False
            items = list(day_map.keys())
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    idx1, idx2 = items[i], items[j]
                    d1, d2 = day_map[idx1], day_map[idx2]
                    if d1 == d2: continue
                    if sdf.at[idx1, 'Cycle'] != sdf.at[idx2, 'Cycle']: continue
                    s1, s2 = day_to_seed[d1], day_to_seed[d2]
                    curr = dist_nodes(idx1, s1) + dist_nodes(idx2, s2)
                    new  = dist_nodes(idx1, s2) + dist_nodes(idx2, s1)
                    if new < curr - 0.001:
                        day_map[idx1], day_map[idx2] = d2, d1
                        swapped = True
            if not swapped:
                break

        # Tulis hasil
        for idx, day in day_map.items():
            cyc = sdf.at[idx, 'Cycle']
            suffix = ""
            if cyc == 'Ganjil': suffix = " GANJIL"
            elif cyc == 'Genap': suffix = " GENAP"
            valid_df.at[idx, 'Optimized JWK'] = day + suffix

        final_l1, final_l2 = get_loads(day_map)
        row_data = {"Personnel": sales}
        for d in DAYS:
            row_data[f"{d}_G1"] = final_l1[d]
            row_data[f"{d}_G2"] = final_l2[d]
        summaries.append(row_data)

    # Merge kembali ke df utama
    df.loc[valid_df.index, 'Optimized JWK'] = valid_df['Optimized JWK']
    df.to_csv(OUTPUT_CSV, index=False)

    print("\n" + "=" * 60)
    print("TERRITORY BALANCED SUMMARY (W1=Ganjil / W2=Genap)")
    print("=" * 60)
    summary_df = pd.DataFrame(summaries)
    for d in DAYS:
        summary_df[d] = summary_df.apply(
            lambda r: f"{r[f'{d}_G1']}/{r[f'{d}_G2']}", axis=1
        )
    print(summary_df[["Personnel"] + DAYS].to_string(index=False))

    return df


# ============================================================
#  STEP 4: GENERATE MAP
# ============================================================
def solve_tsp_greedy(terminal, points):
    """Greedy nearest-neighbor TSP."""
    if not points: return []
    unvisited = list(points)
    route = []
    current = terminal
    while unvisited:
        nearest = min(unvisited, key=lambda p: haversine(
            current['lat'], current['lon'], p['lat'], p['lon']
        ))
        route.append(nearest)
        unvisited.remove(nearest)
        current = nearest
    return route

def step4_generate_map():
    print("\n" + "=" * 60)
    print("STEP 4: GENERATE INTERACTIVE MAP")
    print("=" * 60)

    df = pd.read_csv(OUTPUT_CSV, dtype={'Customer': str})
    df['Latitude']  = pd.to_numeric(df['Latitude'],  errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')

    def fix_lat(val):
        if pd.isna(val): return val
        v = float(val)
        while abs(v) > 90: v /= 10.0
        if v < -10: v /= 10.0
        return v

    def fix_lon(val):
        if pd.isna(val): return val
        v = float(val)
        while abs(v) > 180: v /= 10.0
        return v
    
    df['Latitude'] = df['Latitude'].apply(fix_lat)
    df['Longitude'] = df['Longitude'].apply(fix_lon)
    df_map = df[df['Latitude'].notnull() & df['Longitude'].notnull()].copy()

    # Sales colors
    sales_list = sorted(df_map['Personnel Name'].unique())
    sales_colors = {
        "Beni Saputra":       "#60a5fa",
        "Rudi Anggoro":       "#818cf8",
        "Yuda Nurisman":      "#34d399",
        "Ihwal Bayu Saddera": "#fb923c",
    }

    # Build data_pts JSON
    data_pts = []
    for _, row in df_map.iterrows():
        opt_jwk = str(row.get('Optimized JWK', '') or '')
        orig_jwk = str(row.get('JWK SALESMAN', '') or '')
        data_pts.append({
            "id":       row['Customer'],
            "name":     str(row['Name 1']),
            "lat":      row['Latitude'],
            "lon":      row['Longitude'],
            "sales":    row['Personnel Name'],
            "day_old":  orig_jwk.upper(),
            "day_new":  opt_jwk.upper(),
        })

    data_pts_json = json.dumps(data_pts, ensure_ascii=False)
    terminal_json = json.dumps({"lat": TERMINAL_COORD[0], "lon": TERMINAL_COORD[1]})
    sales_colors_json = json.dumps(sales_colors)
    sales_list_json   = json.dumps(sales_list)

    day_colors = {
        "SENIN": "#60a5fa", "SELASA": "#a78bfa", "RABU": "#34d399",
        "KAMIS": "#fb923c", "JUMAT": "#f472b6", "SABTU": "#facc15",
        "": "#94a3b8"
    }
    day_colors_json = json.dumps(day_colors)

    html_content = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Optimalisasi Rute ZRS 68 – Tulang Bawang</title>
<meta name="description" content="Peta interaktif optimalisasi rute kunjungan sales ZRS 68 wilayah Tulang Bawang">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  :root {{
    --bg: #0f172a;
    --surface: #1e293b;
    --surface2: #263347;
    --border: #334155;
    --text: #f1f5f9;
    --text-muted: #94a3b8;
    --accent: #6366f1;
    --accent2: #818cf8;
    --radius: 12px;
    --shadow: 0 4px 24px rgba(0,0,0,0.4);
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}

  /* HEADER */
  .header {{
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border-bottom: 1px solid var(--border);
    padding: 10px 20px;
    display: flex; align-items: center; gap: 16px;
    flex-shrink: 0;
    box-shadow: 0 2px 20px rgba(0,0,0,0.5);
  }}
  .header-logo {{
    width: 36px; height: 36px;
    background: linear-gradient(135deg, var(--accent), #a855f7);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; flex-shrink: 0;
  }}
  .header-title {{ font-size: 15px; font-weight: 700; color: var(--text); }}
  .header-sub {{ font-size: 11px; color: var(--text-muted); margin-top: 1px; }}
  .header-badge {{
    margin-left: auto; background: rgba(99,102,241,0.15);
    border: 1px solid rgba(99,102,241,0.4);
    color: var(--accent2); padding: 4px 12px; border-radius: 20px;
    font-size: 11px; font-weight: 600; letter-spacing: 0.5px;
    white-space: nowrap;
  }}

  /* MAIN LAYOUT */
  .main {{
    flex: 1; display: flex; overflow: hidden;
  }}

  /* PANELS */
  .panel {{
    flex: 1; display: flex; flex-direction: column; position: relative;
    border-right: 1px solid var(--border);
    min-width: 0;
  }}
  .panel:last-child {{ border-right: none; }}

  /* PANEL HEADER */
  .panel-header {{
    background: var(--surface); padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    display: flex; flex-direction: column; gap: 8px; flex-shrink: 0;
  }}
  .panel-title {{
    font-size: 11px; font-weight: 700; letter-spacing: 1px;
    text-transform: uppercase; color: var(--text-muted);
  }}
  .controls {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}

  select {{
    background: var(--surface2); color: var(--text);
    border: 1px solid var(--border); border-radius: 8px;
    padding: 5px 10px; font-size: 12px; font-family: 'Inter', sans-serif;
    cursor: pointer; flex: 1; min-width: 100px;
    transition: border-color .2s;
  }}
  select:hover {{ border-color: var(--accent); }}
  select:focus {{ outline: none; border-color: var(--accent); }}

  .toggle-group {{ display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }}
  .toggle-label {{
    display: flex; align-items: center; gap: 5px;
    font-size: 11px; color: var(--text-muted); cursor: pointer;
    user-select: none;
  }}
  input[type=checkbox] {{ cursor: pointer; accent-color: var(--accent); width: 13px; height: 13px; }}

  .count-badge {{
    font-size: 11px; color: var(--text-muted);
    background: var(--surface2); border: 1px solid var(--border);
    padding: 3px 10px; border-radius: 20px; white-space: nowrap;
  }}
  .count-badge b {{ color: var(--accent2); }}

  /* MAP */
  .map-container {{ flex: 1; position: relative; }}
  .leaflet-map {{ width: 100%; height: 100%; }}
  .leaflet-container {{ background: #0d1117; }}
  .leaflet-popup-content-wrapper {{
    background: var(--surface); color: var(--text);
    border: 1px solid var(--border); border-radius: 10px;
    font-family: 'Inter', sans-serif; font-size: 12px;
    box-shadow: var(--shadow);
  }}
  .leaflet-popup-tip {{ background: var(--surface); }}

  /* ROUTE ACTIONS */
  .route-actions {{
    background: var(--surface); border-top: 1px solid var(--border);
    padding: 8px 12px; display: flex; gap: 6px; flex-wrap: wrap; flex-shrink: 0;
  }}
  .route-btn {{
    background: linear-gradient(135deg, var(--accent), #7c3aed);
    color: white; border: none; border-radius: 8px;
    padding: 6px 12px; font-size: 11px; font-weight: 600;
    cursor: pointer; font-family: 'Inter', sans-serif;
    transition: opacity .2s, transform .1s;
  }}
  .route-btn:hover {{ opacity: 0.85; transform: translateY(-1px); }}
  .route-btn.secondary {{
    background: var(--surface2); color: var(--text-muted);
    border: 1px solid var(--border);
  }}

  /* TIMELINE */
  .timeline-overlay {{
    position: absolute; top: 8px; right: 8px;
    width: 210px; max-height: 60vh; overflow-y: auto;
    background: rgba(15,23,42,0.92); backdrop-filter: blur(12px);
    border: 1px solid var(--border); border-radius: var(--radius);
    padding: 8px; z-index: 1000; display: none;
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  }}
  .timeline-title {{
    font-size: 10px; font-weight: 700; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 1px;
    margin-bottom: 6px; padding-bottom: 5px;
    border-bottom: 1px solid var(--border);
  }}
  .timeline-card {{
    background: rgba(30,41,59,0.8); border-left: 3px solid #6366f1;
    border-radius: 6px; padding: 5px 7px; margin-bottom: 5px;
    display: flex; flex-direction: column; gap: 2px; font-size: 10px;
  }}
  .timeline-card b {{ color: var(--text); font-size: 10px; }}
  .timeline-card .time {{ color: #60a5fa; font-weight: 600; font-size: 10px; }}
  .timeline-card span {{ color: var(--text-muted); }}

  /* STORE LABEL */
  .store-label {{
    position: absolute; bottom: 18px; left: 50%; transform: translateX(-50%);
    white-space: nowrap; font-size: 9px; color: var(--text);
    background: rgba(15,23,42,0.8); padding: 1px 4px;
    border-radius: 3px; pointer-events: none;
  }}
  .stop-number {{
    font-size: 8px; font-weight: 700; background: var(--accent);
    color: white; border-radius: 50%; width: 14px; height: 14px;
    display: flex; align-items: center; justify-content: center;
  }}

  /* LOADING */
  .loading-overlay {{
    position: absolute; inset: 0; background: rgba(15,23,42,0.7);
    display: none; align-items: center; justify-content: center;
    z-index: 2000; backdrop-filter: blur(4px);
  }}
  .spinner {{
    width: 36px; height: 36px; border: 3px solid var(--border);
    border-top-color: var(--accent); border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

  /* DIVIDER toggle */
  .divider-btn {{
    position: absolute; left: 50%; transform: translateX(-50%);
    z-index: 1500; top: 50%;
    width: 28px; height: 28px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 50%; display: flex; align-items: center; justify-content: center;
    cursor: pointer; color: var(--text-muted); font-size: 14px;
    box-shadow: var(--shadow); transition: background .2s;
  }}
  .divider-btn:hover {{ background: var(--accent); color: white; }}

  /* LEGEND */
  .legend {{
    position: absolute; bottom: 60px; left: 8px;
    background: rgba(15,23,42,0.9); backdrop-filter: blur(8px);
    border: 1px solid var(--border); border-radius: 10px;
    padding: 8px 12px; z-index: 1000; font-size: 10px;
  }}
  .legend-title {{ color: var(--text-muted); font-weight: 600; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; margin-bottom: 3px; color: var(--text); }}
  .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
</style>
</head>
<body>

<div class="header">
  <div class="header-logo">🗺️</div>
  <div>
    <div class="header-title">Optimalisasi Rute ZRS 68 — Tulang Bawang</div>
    <div class="header-sub">Perbandingan Jadwal Lama vs Jadwal Optimasi</div>
  </div>
  <div class="header-badge">✦ 4 Sales · Tulang Bawang</div>
</div>

<div class="main" id="mainLayout">

  <!-- PANEL KIRI: Jadwal Lama -->
  <div class="panel" id="panelL">
    <div class="panel-header">
      <div style="display:flex;align-items:center;gap:8px;">
        <div class="panel-title" style="color:#60a5fa;">◈ Jadwal Lama (Original)</div>
        <span class="count-badge"><b id="countL">-</b></span>
      </div>
      <div class="controls">
        <select id="salesL" onchange="triggerL()">
          <option value="all">— Semua Sales —</option>
        </select>
        <select id="dayL" onchange="triggerL()">
          <option value="all">— Semua Hari —</option>
          <option value="SENIN">Senin</option>
          <option value="SELASA">Selasa</option>
          <option value="RABU">Rabu</option>
          <option value="KAMIS">Kamis</option>
          <option value="JUMAT">Jumat</option>
          <option value="SABTU">Sabtu</option>
        </select>
        <select id="weekL" onchange="triggerL()">
          <option value="all">— Semua Minggu —</option>
          <option value="GANJIL">Minggu Ganjil</option>
          <option value="GENAP">Minggu Genap</option>
        </select>
      </div>
      <div class="toggle-group">
        <label class="toggle-label"><input type="checkbox" id="showTimelineL" onchange="triggerL()"> Timeline</label>
      </div>
    </div>
    <div class="map-container">
      <div id="mapL" class="leaflet-map"></div>
      <div class="timeline-overlay" id="timelineL">
        <div class="timeline-title">⏱ Timeline Kunjungan</div>
        <div id="timelineFlexL"></div>
      </div>
      <div class="legend" id="legendL"></div>
      <div class="loading-overlay" id="loadingL"><div class="spinner"></div></div>
    </div>
    <div class="route-actions" id="actionsL"></div>
  </div>

  <!-- PANEL KANAN: Jadwal Optimasi -->
  <div class="panel" id="panelR">
    <div class="panel-header">
      <div style="display:flex;align-items:center;gap:8px;">
        <div class="panel-title" style="color:#818cf8;">◈ Jadwal Optimasi (Baru)</div>
        <span class="count-badge"><b id="countR">-</b></span>
      </div>
      <div class="controls">
        <select id="salesR" onchange="triggerR()">
          <option value="all">— Semua Sales —</option>
        </select>
        <select id="dayR" onchange="triggerR()">
          <option value="all">— Semua Hari —</option>
          <option value="SENIN">Senin</option>
          <option value="SELASA">Selasa</option>
          <option value="RABU">Rabu</option>
          <option value="KAMIS">Kamis</option>
          <option value="JUMAT">Jumat</option>
          <option value="SABTU">Sabtu</option>
        </select>
        <select id="weekR" onchange="triggerR()">
          <option value="all">— Semua Minggu —</option>
          <option value="GANJIL">Minggu Ganjil</option>
          <option value="GENAP">Minggu Genap</option>
        </select>
      </div>
      <div class="toggle-group">
        <label class="toggle-label"><input type="checkbox" id="showTimelineR" onchange="triggerR()"> Timeline</label>
      </div>
    </div>
    <div class="map-container">
      <div id="mapR" class="leaflet-map"></div>
      <div class="timeline-overlay" id="timelineR">
        <div class="timeline-title">⏱ Timeline Kunjungan</div>
        <div id="timelineFlexR"></div>
      </div>
      <div class="legend" id="legendR"></div>
      <div class="loading-overlay" id="loadingR"><div class="spinner"></div></div>
    </div>
    <div class="route-actions" id="actionsR"></div>
  </div>

</div>

<script>
// ============================================================
//  DATA
// ============================================================
const data_pts = {data_pts_json};
const terminal = {terminal_json};
const salesColors = {sales_colors_json};
const salesList   = {sales_list_json};
const dayColors   = {day_colors_json};

// ============================================================
//  MAP INIT
// ============================================================
const tileUrl = 'https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png';
const tileOpts = {{ attribution: '© OpenStreetMap © CARTO', subdomains: 'abcd', maxZoom: 19 }};
const center = [terminal.lat, terminal.lon];

const mapL = L.map('mapL', {{ zoomControl: true,  preferCanvas: true }}).setView(center, 10);
const mapR = L.map('mapR', {{ zoomControl: false, preferCanvas: true }}).setView(center, 10);
L.tileLayer(tileUrl, tileOpts).addTo(mapL);
L.tileLayer(tileUrl, tileOpts).addTo(mapR);

// Independent maps

// Terminal markers
const termIcon = L.divIcon({{ html: '<div style="font-size:20px;">🏢</div>', className: '', iconAnchor: [10,10] }});
L.marker([terminal.lat, terminal.lon], {{icon: termIcon}}).bindPopup('<b>Terminal / Depo</b>').addTo(mapL);
L.marker([terminal.lat, terminal.lon], {{icon: termIcon}}).bindPopup('<b>Terminal / Depo</b>').addTo(mapR);

// Layers
const layerMarkersL = L.layerGroup().addTo(mapL);
const layerMarkersR = L.layerGroup().addTo(mapR);
const layerRouteL   = L.layerGroup().addTo(mapL);
const layerRouteR   = L.layerGroup().addTo(mapR);

// ============================================================
//  POPULATE SELECTS
// ============================================================
salesList.forEach(s => {{
  ['salesL','salesR'].forEach(id => {{
    const opt = document.createElement('option');
    opt.value = s; opt.textContent = s;
    document.getElementById(id).appendChild(opt);
  }});
}});

// ============================================================
//  HELPERS
// ============================================================
function haversine(lat1, lon1, lat2, lon2) {{
  const R = 6371, toRad = x => x * Math.PI / 180;
  const dLat = toRad(lat2-lat1), dLon = toRad(lon2-lon1);
  const a = Math.sin(dLat/2)**2 + Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*Math.sin(dLon/2)**2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}}

function solveTSP(term, pts) {{
  if (!pts.length) return [];
  const unvisited = [...pts];
  const route = [];
  let cur = term;
  while (unvisited.length) {{
    let best = 0, bestD = Infinity;
    unvisited.forEach((p, i) => {{
      const d = haversine(cur.lat, cur.lon, p.lat, p.lon);
      if (d < bestD) {{ bestD = d; best = i; }}
    }});
    route.push(unvisited.splice(best, 1)[0]);
    cur = route[route.length-1];
  }}
  return route;
}}

function matchesDay(dayStr, filter) {{
  if (!filter || filter === 'all') return true;
  return dayStr && dayStr.includes(filter);
}}

function formatTime(d) {{
  return d.toTimeString().slice(0,5);
}}

function buildLegend(containerId, salesVisible) {{
  const el = document.getElementById(containerId);
  if (!el) return;
  let html = '<div class="legend-title">Sales</div>';
  salesVisible.forEach(s => {{
    const color = salesColors[s] || '#94a3b8';
    html += '<div class="legend-item"><div class="legend-dot" style="background:'+color+'"></div>'+s+'</div>';
  }});
  el.innerHTML = html;
}}

// ============================================================
//  RENDER
// ============================================================
function renderMap(side, sVal, dVal, layerMarkers, layerRoute, actionId, color) {{
  const loading = document.getElementById('loading'+side);
  loading.style.display = 'flex';
  setTimeout(() => {{
    layerMarkers.clearLayers(); layerRoute.clearLayers();
    const wVal = document.getElementById('week'+side).value;

    const filtered = data_pts.filter(item => {{
      const dayStr = side === 'L' ? item.day_old : item.day_new;
      if (!matchesDay(dayStr, dVal)) return false;
      if (sVal !== 'all' && item.sales !== sVal) return false;
      
      const isWeekly = !dayStr.includes('GANJIL') && !dayStr.includes('GENAP');
      const isGanjil = dayStr.includes('GANJIL') || isWeekly;
      const isGenap  = dayStr.includes('GENAP')  || isWeekly;
      
      if (wVal === 'GANJIL' && !isGanjil) return false;
      if (wVal === 'GENAP'  && !isGenap)  return false;
      return true;
    }});

    const isAll  = (sVal === 'all' && dVal === 'all');
    const route  = isAll ? filtered : solveTSP(terminal, filtered);

    // Timeline
    const timelineFlex = document.getElementById('timelineFlex'+side);
    const timelineOverlay = document.getElementById('timeline'+side);
    timelineFlex.innerHTML = '';
    const showTimeline = document.getElementById('showTimeline'+side).checked;
    timelineOverlay.style.display = (!isAll && showTimeline && route.length > 0) ? 'block' : 'none';

    let curTime = new Date(); curTime.setHours(7,0,0,0);
    let prevPt  = terminal, breakTaken = false;
    const speedKmh = 30, visitMins = 20;

    route.forEach((p, i) => {{
      const dist = haversine(prevPt.lat, prevPt.lon, p.lat, p.lon);
      curTime = new Date(curTime.getTime() + (dist/speedKmh)*3600000);

      if (!breakTaken && curTime.getHours() >= 12) {{
        timelineFlex.innerHTML += '<div class="timeline-card" style="border-left-color:#f87171;"><b>🍽 Istirahat</b><span class="time">12:00 – 13:00</span></div>';
        curTime = new Date(curTime.getTime() + 3600000);
        breakTaken = true;
      }}

      const arrival   = new Date(curTime.getTime());
      curTime = new Date(curTime.getTime() + visitMins*60000);
      const departure = new Date(curTime.getTime());
      p.arrival = formatTime(arrival); p.departure = formatTime(departure);
      prevPt = p;

      const dayStr   = side === 'L' ? p.day_old : p.day_new;
      const baseDay  = dayStr.split(' ')[0];
      const dotColor = salesColors[p.sales] || '#94a3b8';
      const dayColor = dayColors[baseDay]   || '#94a3b8';

      // Marker
      const iconHtml = '<div style="position:relative;">' +
        '<div style="width:12px;height:12px;border-radius:50%;background:'+dotColor+';border:2px solid rgba(255,255,255,0.6);box-shadow:0 0 6px '+dotColor+'80;"></div>' +
        (isAll ? '' : '<div class="stop-number" style="position:absolute;top:-8px;right:-8px;">'+(i+1)+'</div>') +
        '<div class="store-label">'+p.name+'</div></div>';

      L.marker([p.lat, p.lon], {{icon: L.divIcon({{html:iconHtml, className:'', iconSize:[12,12], iconAnchor:[6,6]}})}})
       .bindPopup('<b>'+p.name+'</b><br><span style="color:'+dotColor+'">'+p.sales+'</span><br>'+
                  '<span style="color:#94a3b8">'+dayStr+'</span><br>'+
                  (p.arrival ? '<span style="color:#60a5fa">Tiba: '+p.arrival+'</span><br><span style="color:#818cf8">Keluar: '+p.departure+'</span>' : ''))
       .addTo(layerMarkers);

      // Timeline card
      if (!isAll && showTimeline) {{
        const cycleLabel = dayStr.includes('GANJIL') ? 'Minggu Ganjil' : dayStr.includes('GENAP') ? 'Minggu Genap' : 'Setiap Minggu';
        timelineFlex.innerHTML += '<div class="timeline-card" style="border-left-color:'+dayColor+'">' +
          '<b>#'+(i+1)+' ['+p.id+'] '+p.name+'</b>' +
          '<span class="time">'+p.arrival+' – '+p.departure+'</span>' +
          '<span style="color:#818cf8;font-size:9px;">'+cycleLabel+'</span>' +
          '<span>'+dist.toFixed(1)+' km dari prev</span></div>';
      }}
    }});

    // Route polyline
    if (route.length > 0 && !isAll) {{
      const latlngs = [[terminal.lat,terminal.lon], ...route.map(p=>[p.lat,p.lon])];
      L.polyline(latlngs, {{color, weight:2, opacity:0.5, dashArray:'6,4'}}).addTo(layerRoute);
    }}

    // Count & Google Maps buttons
    const salesVisible = [...new Set(filtered.map(p=>p.sales))].sort();
    buildLegend('legend'+side, salesVisible);

    document.getElementById('count'+side).textContent = 'Total: '+filtered.length+' toko';
    const actions = document.getElementById(actionId);
    actions.innerHTML = '';
    if (route.length > 0 && !isAll) {{
      const limit = 20, parts = Math.ceil(route.length/limit);
      for (let i=0; i<parts; i++) {{
        const btn = document.createElement('button');
        btn.className = 'route-btn'+(i>0?' secondary':'');
        btn.textContent = 'G-Maps Bagian '+(i+1);
        btn.onclick = () => {{
          const subset = route.slice(i*limit,(i+1)*limit);
          const origin = i===0 ? terminal.lat+','+terminal.lon : route[i*limit-1].lat+','+route[i*limit-1].lon;
          const dest   = subset[subset.length-1].lat+','+subset[subset.length-1].lon;
          const wps    = subset.slice(0,-1).map(p=>p.lat+','+p.lon).join('|');
          window.open('https://www.google.com/maps/dir/?api=1&origin='+origin+'&destination='+dest+'&waypoints='+wps+'&travelmode=driving','_blank');
        }};
        actions.appendChild(btn);
      }}
    }}

    loading.style.display = 'none';
    if (route.length > 0) {{
      const bounds = L.featureGroup(route.map(p=>L.marker([p.lat,p.lon]))).getBounds().pad(0.1);
      if (side==='L') mapL.fitBounds(bounds); else mapR.fitBounds(bounds);
    }}
  }}, 50);
}}

const triggerL = () => renderMap('L', document.getElementById('salesL').value, document.getElementById('dayL').value, layerMarkersL, layerRouteL, 'actionsL', '#60a5fa');
const triggerR = () => renderMap('R', document.getElementById('salesR').value, document.getElementById('dayR').value, layerMarkersR, layerRouteR, 'actionsR', '#818cf8');

triggerL(); triggerR();
</script>
</body>
</html>"""

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Map tersimpan: {OUTPUT_HTML}")
    print(f"Ukuran file  : {os.path.getsize(OUTPUT_HTML)/1024:.1f} KB")


# ============================================================
#  MAIN
# ============================================================
if __name__ == "__main__":
    step1_prepare()
    step2_add_coordinates()
    step3_optimize()
    step4_generate_map()
    print("\n" + "=" * 60)
    print("SEMUA SELESAI!")
    print(f"  Data CSV  : {OUTPUT_CSV}")
    print(f"  Peta HTML : {OUTPUT_HTML}")
    print("=" * 60)
