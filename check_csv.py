import pandas as pd

df = pd.read_csv(r'D:\Ayak\Project Rolling\Fundamental Tulang Bawang.xlsx - ZRS 68.csv',
                 encoding='utf-8', sep=';', dtype={'Customer': str}, on_bad_lines='skip')

print("=== INFO DASAR ===")
print(f"Total baris  : {len(df)}")
print(f"Total kolom  : {len(df.columns)}")
print()
print("=== KOLOM ===")
for c in df.columns:
    print(f"  {c}")
print()
print("=== 5 BARIS PERTAMA ===")
print(df.head(5).to_string())
print()

# Nama Sales
print("=== Nama Sales unik ===")
for col in df.columns:
    col_l = col.lower()
    if any(k in col_l for k in ['sales','nama','represent','personnel']):
        print(f"  [{col}]:", df[col].value_counts().head(10).to_dict())
print()

# JWK
print("=== Kolom JWK / Jadwal ===")
for col in df.columns:
    col_l = col.lower()
    if any(k in col_l for k in ['jwk','jadwal','senin','hari']):
        print(f"  [{col}] sample values:", df[col].dropna().unique()[:15].tolist())
print()

# Duplikat
cust_col = 'Customer'
print("=== Duplikat Customer ===")
print(f"  Customer unik  : {df[cust_col].nunique()}")
print(f"  Baris duplikat : {df.duplicated(cust_col, keep=False).sum()}")
print()

# Baris kosong
print("=== Baris tanpa Nama Sales ===")
for col in df.columns:
    col_l = col.lower()
    if any(k in col_l for k in ['sales','nama']):
        n = df[col].isna().sum()
        print(f"  [{col}] NaN: {n}")
print()

# Apakah ada Lat/Lon
print("=== Kolom Koordinat ===")
coord_cols = [c for c in df.columns if 'lat' in c.lower() or 'lon' in c.lower()]
print(f"  {coord_cols}")
