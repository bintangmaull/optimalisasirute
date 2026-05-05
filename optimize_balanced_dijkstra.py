import pickle
import pandas as pd
import numpy as np
import os

# Paths
MATRIX_PATH = r"d:\Ayak\Project Rolling\dist_matrix.pkl"
CSV_PATH = r"d:\Ayak\Project Rolling\ZRS86_Filtered.csv"
OUTPUT_CSV = r"d:\Ayak\Project Rolling\ZRS86_Filtered.csv"

DAYS = ["SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU"]
DAY_WEIGHTS = {"SENIN": 1.0, "SELASA": 1.0, "RABU": 1.0, "KAMIS": 1.0, "JUMAT": 1.0, "SABTU": 0.5}

def get_cycle(day_str):
    if pd.isna(day_str) or not day_str or str(day_str).strip() == "": return "Weekly"
    day_str = str(day_str).upper()
    if "GANJIL" in day_str: return "Ganjil"
    if "GENAP" in day_str: return "Genap"
    return "Weekly"

def calculate_targets(total_slots):
    if total_slots == 0: return {d: 0 for d in DAYS}
    total_weight = sum(DAY_WEIGHTS.values())
    unit = total_slots / total_weight
    targets = {d: int(unit * DAY_WEIGHTS[d]) for d in DAYS}
    remainder = total_slots - sum(targets.values())
    for i in range(remainder): targets[DAYS[i % 5]] += 1
    return targets

def optimize():
    if not os.path.exists(MATRIX_PATH):
        print(f"Error: {MATRIX_PATH} not found.")
        return

    print("Loading distance matrix...")
    with open(MATRIX_PATH, 'rb') as f: data = pickle.load(f)
    matrix, mapping, terminal = data['matrix'], data['mapping'], data['terminal']
    
    df = pd.read_csv(CSV_PATH)
    print(f"Original rows: {len(df)}")
    
    df['road_node'] = df['Customer'].astype(str).map(mapping)
    df['Cycle'] = df['JWK SALESMAN'].apply(get_cycle)

    def aggregate_cycles(cycles):
        s = set(cycles)
        if 'Weekly' in s or ('Ganjil' in s and 'Genap' in s): return 'Weekly'
        return 'Ganjil' if 'Ganjil' in s else ('Genap' if 'Genap' in s else 'Weekly')

    print("Aggregating cycles and deduplicating...")
    agg_df = df.groupby(['Personnel Name', 'Customer']).agg({
        'Cycle': aggregate_cycles, 'road_node': 'first', 'Name 1': 'first', 'Street': 'first', 'JWK SALESMAN': 'first'
    }).reset_index()
    
    for col in df.columns:
        if col not in agg_df.columns:
            mapper = df.groupby(['Personnel Name', 'Customer'])[col].first().to_dict()
            agg_df[col] = agg_df.apply(lambda r: mapper.get((r['Personnel Name'], r['Customer'])), axis=1)

    df = agg_df
    valid_df = df[df['road_node'].notnull()].copy()
    valid_df['Optimized JWK'] = ""
    
    salespeople = valid_df['Personnel Name'].unique()
    summaries = []

    for sales in salespeople:
        sdf = valid_df[valid_df['Personnel Name'] == sales].copy()
        if sdf.empty: continue
        
        print(f"Territory Optimization for {sales} ({len(sdf)} unique stores)...")
        
        weekly_idx = sdf[sdf['Cycle'] == 'Weekly'].index.tolist()
        ganjil_idx = sdf[sdf['Cycle'] == 'Ganjil'].index.tolist()
        genap_idx = sdf[sdf['Cycle'] == 'Genap'].index.tolist()
        
        targets_w1 = calculate_targets(len(weekly_idx) + len(ganjil_idx))
        targets_w2 = calculate_targets(len(weekly_idx) + len(genap_idx))
        
        # 1. Seeding for 6 clusters
        nodes = sdf['road_node'].unique().tolist()
        seeds_nodes = []
        if nodes:
            seeds_nodes.append(max(nodes, key=lambda n: matrix.get(terminal, {}).get(n, 0)))
            for _ in range(5):
                seeds_nodes.append(max(nodes, key=lambda n: min([matrix.get(s, {}).get(n, 1e9) for s in seeds_nodes])))
        
        day_to_seed = {d: seeds_nodes[i] for i, d in enumerate(DAYS)}
        
        # Initial assign to nearest seed
        day_map = {}
        for idx in sdf.index:
            node = sdf.at[idx, 'road_node']
            best_d = min(DAYS, key=lambda d: matrix.get(day_to_seed[d], {}).get(node, 1e9))
            day_map[idx] = best_d

        def get_loads(cmap):
            l1, l2 = {d: 0 for d in DAYS}, {d: 0 for d in DAYS}
            for idx, d in cmap.items():
                cyc = sdf.at[idx, 'Cycle']
                if cyc != 'Genap': l1[d] += 1
                if cyc != 'Ganjil': l2[d] += 1
            return l1, l2

        # 2. Iterative Balancing Migration
        for it in range(2000):
            l1, l2 = get_loads(day_map)
            overflows = []
            for d in DAYS:
                if l1[d] > targets_w1[d]: overflows.append((d, 1, l1[d] - targets_w1[d]))
                if l2[d] > targets_w2[d]: overflows.append((d, 2, l2[d] - targets_w2[d]))
            
            if not overflows: break
            
            shuffled_overflows = sorted(overflows, key=lambda x: x[2], reverse=True)
            d_from, week_type, _ = shuffled_overflows[0]
            
            candidates = [idx for idx, d in day_map.items() if d == d_from]
            if week_type == 1: candidates = [i for i in candidates if sdf.at[i, 'Cycle'] != 'Genap']
            else: candidates = [i for i in candidates if sdf.at[i, 'Cycle'] != 'Ganjil']
            
            if not candidates: break
            
            seed_from = day_to_seed[d_from]
            best_move = None # (item, target_day, cost_diff)
            for idx in candidates:
                node = sdf.at[idx, 'road_node']
                dist_from = matrix.get(seed_from, {}).get(node, 1e9)
                for d_to in DAYS:
                    if d_to == d_from: continue
                    cyc = sdf.at[idx, 'Cycle']
                    if cyc != 'Genap' and l1[d_to] >= targets_w1[d_to]: continue
                    if cyc != 'Ganjil' and l2[d_to] >= targets_w2[d_to]: continue
                    
                    dist_to = matrix.get(day_to_seed[d_to], {}).get(node, 1e9)
                    diff = dist_to - dist_from
                    if best_move is None or diff < best_move[2]:
                        best_move = (idx, d_to, diff)
            
            if not best_move: break
            day_map[best_move[0]] = best_move[1]
            
        for idx, day in day_map.items():
            cyc = sdf.at[idx, 'Cycle']
            suffix = ""
            if cyc == 'Ganjil': suffix = " GANJIL"
            elif cyc == 'Genap': suffix = " GENAP"
            valid_df.at[idx, 'Optimized JWK'] = day + suffix

        final_l1, final_l2 = get_loads(day_map)
        res = {"Personnel": sales}
        for d in DAYS: res[f"{d}_G1"], res[f"{d}_G2"] = final_l1[d], final_l2[d]
        summaries.append(res)

    df.loc[valid_df.index, 'Optimized JWK'] = valid_df['Optimized JWK']
    df.to_csv(OUTPUT_CSV, index=False)
    
    print("\n" + "="*50 + "\nTERRITORY BALANCED SUMMARY\n" + "="*50)
    summary_df = pd.DataFrame(summaries)
    for d in DAYS: summary_df[d] = summary_df.apply(lambda r: f"{r[f'{d}_G1']}/{r[f'{d}_G2']}", axis=1)
    print(summary_df[["Personnel"] + DAYS].to_string(index=False))

if __name__ == "__main__": optimize()
