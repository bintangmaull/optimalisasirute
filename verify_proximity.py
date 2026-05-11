import pandas as pd
import pickle
import numpy as np

MATRIX_PATH = r"d:\Ayak\Project Rolling\dist_matrix.pkl"
CSV_PATH = r"d:\Ayak\Project Rolling\ZRS86_Filtered.csv"
DAYS = ["SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU"]

def verify_proximity():
    with open(MATRIX_PATH, 'rb') as f: data = pickle.load(f)
    matrix, mapping = data['matrix'], data['mapping']
    
    df = pd.read_csv(CSV_PATH)
    df['road_node'] = df['Customer'].astype(str).map(mapping)
    valid_df = df[df['road_node'].notnull() & df['Optimized JWK'].notnull()].copy()
    
    def get_base_day(jwk):
        for d in DAYS:
            if d in str(jwk).upper(): return d
        return None

    valid_df['Day'] = valid_df['Optimized JWK'].apply(get_base_day)
    
    results = []
    for sales in valid_df['Personnel Name'].unique():
        sdf = valid_df[valid_df['Personnel Name'] == sales]
        for day in DAYS:
            ddf = sdf[sdf['Day'] == day]
            if ddf.empty: continue
            
            nodes = ddf['road_node'].unique().tolist()
            if not nodes: continue
            
            # Use medoid as center
            medoid = min(nodes, key=lambda core: sum([matrix.get(core, {}).get(other, 1e9) for other in nodes]))
            distances = [matrix.get(medoid, {}).get(n, 0) for n in nodes]
            
            results.append({
                "Personnel": sales,
                "Day": day,
                "Count": len(nodes),
                "AvgDist": np.mean(distances),
                "MaxDist": np.max(distances)
            })

    res_df = pd.DataFrame(results)
    print("\nProximity Metrics (Distance units from matrix):")
    summary = res_df.groupby("Personnel").agg({"AvgDist": "mean", "MaxDist": "max", "Count": "sum"})
    print(summary)
    return summary

if __name__ == "__main__":
    verify_proximity()
