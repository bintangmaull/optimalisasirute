import pickle
import pandas as pd
import numpy as np
import os
import csv

# Paths
matrix_path = r"D:\Ayak\Project Rolling\dist_matrix.pkl"
csv_path = r"D:\Ayak\Project Rolling\ZRS86_Filtered.csv"
output_csv = r"D:\Ayak\Project Rolling\ZRS86_Filtered.csv"

# Weights
DAYS = ["SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU"]
DAY_WEIGHTS = {"SENIN": 1.0, "SELASA": 1.0, "RABU": 1.0, "KAMIS": 1.0, "JUMAT": 1.0, "SABTU": 0.5}

def get_cycle(day_str):
    if pd.isna(day_str) or not day_str: return "Weekly"
    day_str = str(day_str).upper()
    if "GANJIL" in day_str: return "Ganjil"
    if "GENAP" in day_str: return "Genap"
    return "Weekly"

def optimize():
    if not os.path.exists(matrix_path):
        print(f"Waiting for {matrix_path}...")
        return

    print("Loading distance matrix...")
    with open(matrix_path, 'rb') as f:
        data = pickle.load(f)
    
    matrix = data['matrix']
    mapping = data['mapping'] # cust_id -> node
    terminal = data['terminal']
    
    df = pd.read_csv(csv_path)
    df['road_node'] = df['Customer'].astype(str).map(mapping)
    df['Cycle'] = df['JWK SALESMAN'].apply(get_cycle)
    
    valid_df = df[df['road_node'].notnull()].copy()
    
    # We will use the dataframe index to assign values, avoiding Customer ID collisions
    valid_df['final_jwk'] = ""
    
    salespeople = valid_df['Personnel Name'].unique()
    for sales in salespeople:
        sdf = valid_df[valid_df['Personnel Name'] == sales]
        print(f"Processing Salesperson: {sales} ({len(sdf)} visits)")
        
        for cycle in ["Weekly", "Ganjil", "Genap"]:
            cdf = sdf[sdf['Cycle'] == cycle].copy()
            if cdf.empty: continue
            
            total_cust = len(cdf)
            total_weight = sum(DAY_WEIGHTS.values())
            targets = {day: int((total_cust / total_weight) * w) for day, w in DAY_WEIGHTS.items()}
            remainder = total_cust - sum(targets.values())
            for i in range(remainder):
                targets[DAYS[i % 5]] += 1
            
            # Use all nodes available for this set
            cust_nodes = list(cdf['road_node'].unique())
            seeds = {}
            # Seed 1: Farthest from terminal
            seeds["SENIN"] = max(cust_nodes, key=lambda n: matrix[terminal].get(n, 0))
            for d_idx, day in enumerate(DAYS[1:]):
                def min_dist_to_seeds(node):
                    active_seeds = [seeds[d] for d in DAYS[:d_idx+1] if d in seeds]
                    return min([matrix[s].get(node, float('inf')) for s in active_seeds])
                seeds[day] = max(cust_nodes, key=min_dist_to_seeds)
                
            day_counts = {d: 0 for d in DAYS}
            # Order by distance from terminal
            sorted_indices = cdf.index[np.argsort([matrix[terminal].get(n, 0) for n in cdf['road_node']])]
            
            for idx in sorted_indices:
                node = cdf.loc[idx, 'road_node']
                sorted_days = sorted(DAYS, key=lambda d: matrix.get(seeds[d], {}).get(node, float('inf')))
                
                chosen_day = sorted_days[0]
                for d in sorted_days:
                    if day_counts[d] < targets[d]:
                        chosen_day = d
                        break
                
                day_suffix = ""
                if cycle == "Ganjil": day_suffix = " GANJIL"
                elif cycle == "Genap": day_suffix = " GENAP"
                
                valid_df.at[idx, 'final_jwk'] = chosen_day + day_suffix
                day_counts[chosen_day] += 1

    # Update main DF using index mapping
    df['Optimized JWK'] = valid_df['final_jwk']
    df.to_csv(output_csv, index=False)
    print(f"Optimization results updated in {output_csv}. Total Rows preserved: {len(df)}")
    
    # Check counts for high level verification
    print("\nTotal Optimized JWK counts:")
    print(df['Optimized JWK'].value_counts())

if __name__ == "__main__":
    optimize()
