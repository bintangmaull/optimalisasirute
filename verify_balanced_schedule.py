import pandas as pd
import numpy as np

CSV_PATH = r"d:\Ayak\Project Rolling\ZRS86_Filtered.csv"
DAYS = ["SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU"]

def verify():
    df = pd.read_csv(CSV_PATH)
    if 'Optimized JWK' not in df.columns:
        print("Optimized JWK column missing.")
        return

    def get_base_day(jwk):
        if pd.isna(jwk): return None
        for d in DAYS:
            if d in jwk.upper(): return d
        return None

    def get_is_ganjil(jwk):
        return "GANJIL" in str(jwk).upper()

    def get_is_genap(jwk):
        return "GENAP" in str(jwk).upper()

    def get_is_weekly(jwk):
        return not get_is_ganjil(jwk) and not get_is_genap(jwk)

    salespeople = df['Personnel Name'].unique()
    
    results = []
    
    for sales in salespeople:
        sdf = df[df['Personnel Name'] == sales]
        
        # Check weekly stores consistency (should have same base day in both cycles? 
        # Actually our script generates JWK strings like "SENIN", "SENIN GANJIL")
        # Let's count Week 1 vs Week 2
        
        # Week 1 = Weekly + Ganjil
        # Week 2 = Weekly + Genap
        
        w1_counts = {d: 0 for d in DAYS}
        w2_counts = {d: 0 for d in DAYS}
        
        for _, row in sdf.iterrows():
            jwk = row['Optimized JWK']
            day = get_base_day(jwk)
            if not day: continue
            
            if get_is_weekly(jwk):
                w1_counts[day] += 1
                w2_counts[day] += 1
            elif get_is_ganjil(jwk):
                w1_counts[day] += 1
            elif get_is_genap(jwk):
                w2_counts[day] += 1
        
        row_data = {"Personnel": sales}
        for d in DAYS:
            row_data[f"W1_{d}"] = w1_counts[d]
            row_data[f"W2_{d}"] = w2_counts[d]
        
        results.append(row_data)

    res_df = pd.DataFrame(results)
    print("\nVisit Counts per Day (Week 1 / Week 2):")
    
    # Prettier output
    cols = ["Personnel"]
    for d in DAYS:
        res_df[d] = res_df.apply(lambda r: f"{r[f'W1_{d}']}/{r[f'W2_{d}']}", axis=1)
        cols.append(d)
    
    print(res_df[cols].to_string(index=False))

    # Check Saturday Ratio
    print("\nSaturday to Weekday Ratio (Target ~0.5):")
    for sales in salespeople:
        s_data = res_df[res_df['Personnel'] == sales].iloc[0]
        w1_avg = np.mean([s_data[f"W1_{d}"] for d in DAYS[:5]])
        w1_sat = s_data["W1_SABTU"]
        w2_avg = np.mean([s_data[f"W2_{d}"] for d in DAYS[:5]])
        w2_sat = s_data["W2_SABTU"]
        print(f"{sales[:15]:15}: W1: {w1_sat}/{w1_avg:.1f} ({w1_sat/w1_avg if w1_avg>0 else 0:.2f}), W2: {w2_sat}/{w2_avg:.1f} ({w2_sat/w2_avg if w2_avg>0 else 0:.2f})")

if __name__ == "__main__":
    verify()
