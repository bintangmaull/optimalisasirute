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
        
        def calculate_perfect_targets(total_visits):
            sat_target = round(total_visits / 11.0)
            remaining = total_visits - sat_target
            wd_base = remaining // 5
            wd_extra = remaining % 5
            
            res = {d: wd_base for d in DAYS if d != 'SABTU'}
            res['SABTU'] = sat_target
            # Distribute extras to early weekdays
            for i, d in enumerate(DAYS):
                if i < wd_extra:
                    res[d] += 1
            return res
            
        targets_w1 = calculate_perfect_targets(len(weekly_idx) + len(ganjil_idx))
        targets_w2 = calculate_perfect_targets(len(weekly_idx) + len(genap_idx))
        
        # 1. Seeding for 6 clusters with K-Medoids refinement
        nodes = sdf['road_node'].unique().tolist()
        if not nodes: continue
        
        seeds_nodes = []
        # Seed 1: farthest from terminal (coverage)
        seeds_nodes.append(max(nodes, key=lambda n: matrix.get(terminal, {}).get(n, 0)))
        for _ in range(5):
            seeds_nodes.append(max(nodes, key=lambda n: min([matrix.get(s, {}).get(n, 1e9) for s in seeds_nodes])))
        
        # K-Medoids Refinement: Iterate to find best centers
        for _ in range(10): 
            clusters = {s: [] for s in seeds_nodes}
            for n in nodes:
                best_s = min(seeds_nodes, key=lambda s: matrix.get(s, {}).get(n, 1e9))
                clusters[best_s].append(n)
            
            new_seeds = []
            for s, c_nodes in clusters.items():
                if not c_nodes:
                    new_seeds.append(s)
                    continue
                # Medoid: node in cluster that minimizes sum of distances to other nodes in cluster
                best_medoid = min(c_nodes, key=lambda core: sum([matrix.get(core, {}).get(other, 1e9) for other in c_nodes]))
                new_seeds.append(best_medoid)
            seeds_nodes = new_seeds

        day_to_seed = {d: seeds_nodes[i] for i, d in enumerate(DAYS)}
        
        # Initial assign to nearest seed (PROXIMITY FIRST)
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

        # 2. Ultra-Tight Balancing: Essential for "Rata" workload
        # Rules: Weekdays +/- 1, Saturday +/- 0 (if possible)
        
        for it in range(10000):
            l1, l2 = get_loads(day_map)
            
            def get_dev_strict(load, target, d):
                tol = 0 if d == 'SABTU' else 1
                if load > target + tol: return (load - (target + tol)) ** 2
                if load < target - tol: return ((target - tol) - load) ** 2
                return 0
            
            total_dev = sum(get_dev_strict(l1[d], targets_w1[d], d) + get_dev_strict(l2[d], targets_w2[d], d) for d in DAYS)
            if total_dev == 0: break
            
            best_move = None
            
            for idx, d_from in day_map.items():
                node = sdf.at[idx, 'road_node']
                cyc = sdf.at[idx, 'Cycle']
                s_from = day_to_seed[d_from]
                dist_from = matrix.get(s_from, {}).get(node, 1e9)
                
                cur_dev_from = get_dev_strict(l1[d_from], targets_w1[d_from], d_from) + get_dev_strict(l2[d_from], targets_w2[d_from], d_from)
                
                for d_to in DAYS:
                    if d_to == d_from: continue
                    s_to = day_to_seed[d_to]
                    dist_to = matrix.get(s_to, {}).get(node, 1e9)
                    
                    cur_dev_to = get_dev_strict(l1[d_to], targets_w1[d_to], d_to) + get_dev_strict(l2[d_to], targets_w2[d_to], d_to)
                    
                    nl1_f, nl1_t = l1[d_from], l1[d_to]
                    nl2_f, nl2_t = l2[d_from], l2[d_to]
                    if cyc != 'Genap': nl1_f -= 1; nl1_t += 1
                    if cyc != 'Ganjil': nl2_f -= 1; nl2_t += 1
                    
                    new_dev_from = get_dev_strict(nl1_f, targets_w1[d_from], d_from) + get_dev_strict(nl2_f, targets_w2[d_from], d_from)
                    new_dev_to = get_dev_strict(nl1_t, targets_w1[d_to], d_to) + get_dev_strict(nl2_t, targets_w2[d_to], d_to)
                    
                    improvement = (cur_dev_from + cur_dev_to) - (new_dev_from + new_dev_to)
                    
                    if improvement > 0:
                        cost = dist_to - dist_from
                        score = (improvement, -cost)
                        if best_move is None or score > best_move[2]:
                            best_move = (idx, d_to, score)
            
            if not best_move: 
                print(f"No more improvements found. Total Dev: {total_dev}")
                break
            
            # print(f"Move {best_move[0]} to {best_move[1]}, Improvement: {best_move[2][0]}")
            day_map[best_move[0]] = best_move[1]

        # 3. Local Search: Swaps (Further proximity refinement without breaking limits)
        for _ in range(5):
            swapped = False
            items = list(day_map.keys())
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    idx1, idx2 = items[i], items[j]
                    d1, d2 = day_map[idx1], day_map[idx2]
                    if d1 == d2: continue
                    
                    c1, c2 = sdf.at[idx1, 'Cycle'], sdf.at[idx2, 'Cycle']
                    if c1 != c2: continue
                    
                    n1, n2 = sdf.at[idx1, 'road_node'], sdf.at[idx2, 'road_node']
                    s1, s2 = day_to_seed[d1], day_to_seed[d2]
                    
                    curr_dist = matrix.get(s1, {}).get(n1, 1e9) + matrix.get(s2, {}).get(n2, 1e9)
                    new_dist = matrix.get(s1, {}).get(n2, 1e9) + matrix.get(s2, {}).get(n1, 1e9)
                    
                    if new_dist < curr_dist - 0.001:
                        day_map[idx1], day_map[idx2] = d2, d1
                        swapped = True
            if not swapped: break
            
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
