import pandas as pd

csv_path = r"D:\Ayak\Project Rolling\ZRS86_Filtered.csv"

def verify():
    df = pd.read_csv(csv_path)
    if 'Optimized JWK' not in df.columns:
        print("Optimized JWK column not found.")
        return
        
    print(f"Total Rows: {len(df)}")
    
    # Workload per day
    print("\nVisit Counts per Personnel per Day:")
    # Pivot table for counts
    summary = df.groupby(['Personnel Name', 'Optimized JWK']).size().unstack(fill_value=0)
    print(summary)
    
    # Calculate Ganjil/Genap counts per day
    def get_base_day(s):
        if pd.isna(s): return "None"
        return str(s).split(' ')[0]
        
    def get_week_type(s):
        if pd.isna(s): return "None"
        if "GANJIL" in str(s): return "Ganjil"
        if "GENAP" in str(s): return "Genap"
        return "Weekly"

    df['BaseDay'] = df['Optimized JWK'].apply(get_base_day)
    df['WeekType'] = df['Optimized JWK'].apply(get_week_type)
    
    for sales in df['Personnel Name'].unique():
        print(f"\n--- {sales} ---")
        sdf = df[df['Personnel Name'] == sales]
        
        for week in ["Ganjil", "Genap"]:
            week_df = sdf[sdf['WeekType'].isin(['Weekly', week])]
            counts = week_df['BaseDay'].value_counts()
            print(f"  {week} Week: ", end="")
            for day in ["SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU"]:
                print(f"{day}: {counts.get(day, 0)} | ", end="")
            print()

if __name__ == "__main__":
    verify()
