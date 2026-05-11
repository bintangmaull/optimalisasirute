import pandas as pd

# Load the filtered data
df = pd.read_csv('ZRS86_Filtered.csv')

# Personnel of interest
personnel_list = df['Personnel Name'].unique()

print("# Detailed Visit List Summary\n")

for p_name in personnel_list:
    print(f"## Personnel: {p_name}")
    p_df = df[df['Personnel Name'] == p_name]
    
    # Define day order
    day_order = ['SENIN', 'SELASA', 'RABU', 'KAMIS', 'JUMAT', 'SABTU']
    
    for cycle in ['Ganjil', 'Genap']:
        print(f"\n### Cycle: {cycle}")
        for day in day_order:
            target_jwk = f"{day} {cycle.upper()}"
            mask_exact = (df['Personnel Name'] == p_name) & (df['Optimized JWK'] == target_jwk)
            mask_weekly = (df['Personnel Name'] == p_name) & (df['Optimized JWK'] == day)
            
            current_day_shops = df[mask_exact | mask_weekly]
            
            if not current_day_shops.empty:
                print(f"\n#### {day}")
                print(f"Count: {len(current_day_shops)}")
                shop_names = [str(n) for n in current_day_shops['Name 1'].tolist()]
                print(f"Shops: {', '.join(shop_names[:10])}{' ...' if len(shop_names) > 10 else ''}")
    print("\n---")
