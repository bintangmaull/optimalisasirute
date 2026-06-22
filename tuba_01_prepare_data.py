"""
Step 1: Prepare & Clean Data CSV ZRS 68 Tulang Bawang
- Drop baris duplikat
- Filter hanya 4 sales utama (Bayu, Beni, Rudi, Yuda)
- Buat kolom JWK SALESMAN standar dari kolom jadwal
- Drop baris tanpa JWK / Nama Sales
- Simpan ke ZRS68_Filtered.csv
"""

import pandas as pd
import re

INPUT_CSV  = r"D:\Ayak\Project Rolling\Fundamental Tulang Bawang.xlsx - ZRS 68.csv"
OUTPUT_CSV = r"D:\Ayak\Project Rolling\ZRS68_Filtered.csv"

DAYS = ["SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU"]

# Nama sales utama yang ada di KML
VALID_SALES = {"Ihwal Bayu Saddera", "Beni Saputra", "Rudi Anggoro", "Yuda Nurisman"}

def normalize_jwk(s):
    """
    Ubah nilai JWK dari CSV ke format standar:
    'Senin Ganjil' -> 'SENIN GANJIL'
    'Sabtu'        -> 'SABTU'
    """
    if pd.isna(s) or str(s).strip() == "":
        return ""
    s = str(s).strip().upper()
    # Pastikan spasi tunggal
    s = re.sub(r'\s+', ' ', s)
    return s

def get_personnel_number(row):
    """Bersihkan nomor personel dari scientific notation."""
    val = row.get('Represent.', '')
    if pd.isna(val):
        return ''
    try:
        return str(int(float(val)))
    except:
        return str(val).strip()

print("=" * 60)
print("STEP 1: PREPARE & CLEAN DATA ZRS 68 TULANG BAWANG")
print("=" * 60)

df = pd.read_csv(INPUT_CSV, encoding='utf-8', dtype={'Customer': str})
print(f"Baris awal     : {len(df)}")
print(f"Customer unik  : {df['Customer'].nunique()}")

# --- 1. Normalisasi kolom ---
col_jwk = 'Senin, Selasa, Rabu, Kamis, Jumat, Sabtu'
df['JWK SALESMAN']    = df[col_jwk].apply(normalize_jwk)
df['Personnel Name']  = df['Nama Sales'].fillna('').str.strip()
df['Personnel Number']= df.apply(get_personnel_number, axis=1)
df['Customer']        = df['Customer'].astype(str).str.strip()

# Bersihkan Customer dari .0 yang muncul karena float
df['Customer'] = df['Customer'].apply(lambda x: x.rstrip('.0') if x.endswith('.0') else x)

# --- 2. Drop duplikat baris persis ---
before_dedup = len(df)
df = df.drop_duplicates()
print(f"Setelah drop duplikat baris   : {len(df)} (buang {before_dedup - len(df)})")

# --- 3. Filter: hanya 4 sales utama ---
df_valid = df[df['Personnel Name'].isin(VALID_SALES)].copy()
print(f"Setelah filter sales utama    : {len(df_valid)} baris")

# --- 4. Drop baris tanpa JWK ---
df_valid = df_valid[df_valid['JWK SALESMAN'].str.len() > 0].copy()
print(f"Setelah drop tanpa JWK        : {len(df_valid)} baris")

# --- 5. Untuk Customer yang muncul 2x (Ganjil + Genap dari sales sama),
#    ini WAJAR — simpan apa adanya, optimizer akan konsolidasikan ---
print(f"Customer unik bersih          : {df_valid['Customer'].nunique()}")

# --- 6. Tambah kolom kosong untuk koordinat ---
df_valid['Latitude']  = ''
df_valid['Longitude'] = ''

# --- 7. Simpan ---
keep_cols = [
    'Customer', 'Name 1', 'Street', 'Telephone 1',
    'Zone', 'SDst', 'Personnel Number', 'Personnel Name',
    'JWK SALESMAN', 'Latitude', 'Longitude'
]
df_out = df_valid[keep_cols].reset_index(drop=True)
df_out.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')

print()
print("=== Distribusi JWK per Sales ===")
pivot = df_out.groupby(['Personnel Name', 'JWK SALESMAN']).size().unstack(fill_value=0)
print(pivot)

print()
print(f"Output tersimpan: {OUTPUT_CSV}")
print("DONE.")
