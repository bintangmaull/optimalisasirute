import pickle
import pandas as pd
import numpy as np
import os
import math

# Paths
matrix_path = r"D:\Ayak\Project Rolling\dist_matrix.pkl"
csv_path = r"D:\Ayak\Project Rolling\ZRS86_Filtered.csv"
output_csv = r"D:\Ayak\Project Rolling\ZRS86_Filtered.csv"

# Config
DAYS = ["SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU"]
DAY_WEIGHTS = {"SENIN": 1.0, "SELASA": 1.0, "RABU": 1.0, "KAMIS": 1.0, "JUMAT": 1.0, "SABTU": 0.5}
VISIT_DURATION_MINS = 20
AVERAGE_SPEED_KMH = 30

def haversine(lat1, lon1, lat2, lon2):
    R = 6371 # km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def get_base_day(s):
    if pd.isna(s) or not s: return "SENIN"
    s = str(s).upper()
    for d in DAYS:
        if d in s: return d
    return "SENIN"

def get_visit_cycle(s):
    if pd.isna(s) or not s: return "Weekly"
    s = str(s).upper()
    if "GANJIL" in s: return "Ganjil"
    if "GENAP" in s: return "Genap"
    return "Weekly"

def optimize():
    print("Loading data...")
    df = pd.read_csv(csv_path)
    # Filter rows with coordinates
    valid_data = df[df['Latitude'].notnull() & df['Longitude'].notnull()].copy()
    
    # Identify visit cycles and base days for grouping
    valid_data['BaseDay'] = valid_data['JWK SALESMAN'].apply(get_base_day)
    valid_data['Cycle'] = valid_data['JWK SALESMAN'].apply(get_visit_cycle)
    
    # Load distance matrix for Dijkstra (if available)
    matrix = {}
    mapping = {}
    TERMINAL_COORD = (-5.346648, 105.216119)
    if os.path.exists(matrix_path):
        with open(matrix_path, 'rb') as f:
            data = pickle.load(f)
            matrix = data.get('matrix', {})
            mapping = data.get('mapping', {})

    def get_dist(c1_id, c2_id, p1_coords, p2_coords):
        n1, n2 = mapping.get(str(c1_id)), mapping.get(str(c2_id))
        if n1 and n2 and n1 in matrix and n2 in matrix[n1]:
            return matrix[n1][n2] * 111
        return haversine(p1_coords[0], p1_coords[1], p2_coords[0], p2_coords[1]) * 1.4

    # CONSOLIDATION: Group by (Personnel, Customer, BaseDay)
    # This prevents merging Tuesday visits with Friday visits,
    # but ALLOWS merging Monday Ganjil with Monday Genap into one Weekly visit.
    groups = valid_data.groupby(['Personnel Name', 'Customer', 'BaseDay']).agg({
        'Name 1': 'first', 'Latitude': 'first', 'Longitude': 'first', 'Cycle': list
    }).reset_index()
    
    def resolve_type(l):
        if 'Weekly' in l or ('Ganjil' in l and 'Genap' in l): return 'Weekly'
        if 'Ganjil' in l: return 'Ganjil'
        return 'Genap'
    
    groups['FinalType'] = groups['Cycle'].apply(resolve_type)
    
    results = []
    salespeople = groups['Personnel Name'].unique()
    
    for sales in salespeople:
        sdf = groups[groups['Personnel Name'] == sales].copy()
        if sdf.empty: continue
        
        # Calculate targets for this salesperson
        v_ganjil = sdf[sdf['FinalType'].isin(['Weekly', 'Ganjil'])]
        v_genap = sdf[sdf['FinalType'].isin(['Weekly', 'Genap'])]
        
        def calc_targets(total):
            t = {d: int((total / 5.5) * (0.5 if d == 'SABTU' else 1.0)) for d in DAYS}
            rem = total - sum(t.values())
            for i in range(rem): t[DAYS[i % 5]] += 1
            return t
            
        t_ganjil = calc_targets(len(v_ganjil))
        t_genap = calc_targets(len(v_genap))
        
        print(f"Optimizing {sales}: Items={len(sdf)}, GanjilTarget={sum(t_ganjil.values())}, GenapTarget={sum(t_genap.values())}")

        # Seeding
        all_ids = list(sdf.index)
        all_coords = list(zip(sdf['Latitude'], sdf['Longitude']))
        seeds = []
        # Seed 1: farthest from terminal
        f_idx = np.argmax([get_dist(None, None, TERMINAL_COORD, c) for c in all_coords])
        seeds.append(all_ids[f_idx])
        for _ in range(1, 6):
            def min_d_to_seeds(idx):
                return min([get_dist(None, None, all_coords[idx], all_coords[list(sdf.index).index(s)]) for s in seeds])
            n_idx = np.argmax([min_d_to_seeds(i) for i in range(len(all_ids)) if all_ids[i] not in seeds])
            seeds.append(all_ids[n_idx])
        
        day_seeds = dict(zip(DAYS, seeds))
        day_counts_ganjil = {d: 0 for d in DAYS}
        day_counts_genap = {d: 0 for d in DAYS}
        sdf['OptimizedDay'] = ""
        
        # Sort shops by nearest seed distance to process core clusters first
        seed_coords = {d: (sdf.loc[day_seeds[d], 'Latitude'], sdf.loc[day_seeds[d], 'Longitude']) for d in DAYS}
        sdf['min_seed_dist'] = [min([get_dist(None, None, (row.Latitude, row.Longitude), seed_coords[d]) for d in DAYS]) for _, row in sdf.iterrows()]
        sdf = sdf.sort_values('min_seed_dist')

        for idx, row in sdf.iterrows():
            v_type = row['FinalType']
            coords = (row['Latitude'], row['Longitude'])
            
            # Sort days by proximity to the specific seed of that day
            sorted_days = sorted(DAYS, key=lambda d: get_dist(None, None, coords, seed_coords[d]))
            
            chosen_day = None
            for d in sorted_days:
                can_fit = True
                if v_type in ['Weekly', 'Ganjil'] and day_counts_ganjil[d] >= t_ganjil[d]: can_fit = False
                if v_type in ['Weekly', 'Genap'] and day_counts_genap[d] >= t_genap[d]: can_fit = False
                if can_fit:
                    chosen_day = d
                    break
            
            if not chosen_day:
                # Fallback: day with least relative load
                chosen_day = min(DAYS, key=lambda d: (day_counts_ganjil[d]/t_ganjil[d] if v_type in ['Weekly','Ganjil'] else 0) + (day_counts_genap[d]/t_genap[d] if v_type in ['Weekly','Genap'] else 0))
            
            sdf.loc[idx, 'OptimizedDay'] = chosen_day
            if v_type in ['Weekly', 'Ganjil']: day_counts_ganjil[chosen_day] += 1
            if v_type in ['Weekly', 'Genap']: day_counts_genap[chosen_day] += 1

        results.append(sdf)

    merged = pd.concat(results)
    
    # Final step: Map back to original rows
    # We use (Personnel, Customer, BaseDay) as the matching key
    def get_match_key(row, is_original=True):
        bd = get_base_day(row['JWK SALESMAN']) if is_original else row['BaseDay']
        return f"{row['Personnel Name']}_{row['Customer']}_{bd}"

    merged['match_key'] = merged.apply(lambda r: get_match_key(r, is_original=False), axis=1)
    key_to_day = dict(zip(merged['match_key'], merged['OptimizedDay']))
    key_to_type = dict(zip(merged['match_key'], merged['FinalType']))

    final_rows = []
    for _, row in df.iterrows():
        if pd.isna(row['Latitude']):
            final_rows.append(row)
            continue
        key = get_match_key(row, is_original=True)
        if key in key_to_day:
            opt_day = key_to_day[key]
            v_type = key_to_type[key]
            suffix = ""
            if v_type == "Ganjil": suffix = " GANJIL"
            elif v_type == "Genap": suffix = " GENAP"
            row['Optimized JWK'] = str(opt_day) + suffix
        final_rows.append(row)
        
    pd.DataFrame(final_rows).to_csv(output_csv, index=False)
    print("Success. Run verify_schedule.py to check counts.")

if __name__ == "__main__":
    optimize()
