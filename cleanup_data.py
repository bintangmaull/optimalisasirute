import pandas as pd
import numpy as np

csv_path = r"D:\Ayak\Project Rolling\ZRS86_Filtered.csv"
clean_path = r"D:\Ayak\Project Rolling\ZRS86_Clean.csv"

def get_cycle(day_str):
    if pd.isna(day_str) or not day_str: return "Weekly"
    day_str = str(day_str).upper()
    if "GANJIL" in day_str: return "Ganjil"
    if "GENAP" in day_str: return "Genap"
    return "Weekly"

df = pd.read_csv(csv_path)

# Determine cycle for each row
df['_temp_cycle'] = df['JWK SALESMAN'].apply(get_cycle)

# Group by Customer to consolidate
def consolidate(group):
    # Determine overall cycle
    cycles = group['_temp_cycle'].unique()
    eff_cycle = "Weekly"
    if "Weekly" in cycles:
        eff_cycle = "Weekly"
    elif "Ganjil" in cycles and "Genap" in cycles:
        eff_cycle = "Weekly"
    elif "Ganjil" in cycles:
        eff_cycle = "Ganjil"
    elif "Genap" in cycles:
        eff_cycle = "Genap"
    
    # Grab first valid name/coord/etc
    res = group.iloc[0].copy()
    res['Cycle'] = eff_cycle
    # Reconstruct a representative JWK SALESMAN
    if eff_cycle == "Weekly":
        # Find first weekly day if exists
        w_row = group[group['_temp_cycle'] == "Weekly"]
        if not w_row.empty:
            res['JWK SALESMAN'] = w_row.iloc[0]['JWK SALESMAN']
        else:
            # G+G scenario
            res['JWK SALESMAN'] = group.iloc[0]['JWK SALESMAN'].replace(" GANJIL", "").replace(" GENAP", "")
    else:
        res['JWK SALESMAN'] = group.iloc[0]['JWK SALESMAN']
        
    return res

print(f"Original rows: {len(df)}")
clean_df = df.groupby('Customer', as_index=False).apply(consolidate)
print(f"Clean rows: {len(clean_df)}")

clean_df.to_csv(clean_path, index=False)
print(f"Cleaned data saved to {clean_path}")
