import zipfile
import csv
import xml.etree.ElementTree as ET
import io
import os

def clean_code(code):
    if not code:
        return ""
    code = str(code).strip()
    # Remove .0 if present at the end
    if code.endswith('.0'):
        code = code[:-2]
    # Strip leading zeros
    code = code.lstrip('0')
    return code

def parse_kml_extended(kml_content):
    mapping = {}
    try:
        root = ET.fromstring(kml_content)
        # KML namespaces
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        for pm in root.findall('.//kml:Placemark', ns):
            cust_code = None
            lat = None
            lon = None
            
            for data in pm.findall('.//kml:Data', ns):
                name = data.get('name')
                value_elem = data.find('kml:value', ns)
                if value_elem is not None:
                    val = value_elem.text.strip() if value_elem.text else ""
                    if name == "Customer":
                        cust_code = clean_code(val)
                    elif name == "LAT":
                        lat = val
                    elif name == "LONG":
                        lon = val
            
            if not lat or not lon:
                coord_elem = pm.find('.//kml:coordinates', ns)
                if coord_elem is not None and coord_elem.text:
                    coords = coord_elem.text.strip().split(',')
                    if len(coords) >= 2:
                        lon = coords[0]
                        lat = coords[1]
            
            if cust_code:
                mapping[cust_code] = (lat, lon)
                
    except Exception as e:
        print(f"Error parsing KML: {e}")
    return mapping

def get_mapping_from_kmz_zip(zip_path):
    mapping = {}
    print(f"Processing {zip_path}...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if name.lower().endswith('.kml'):
                    mapping.update(parse_kml_extended(zf.read(name)))
                elif name.lower().endswith('.kmz'):
                    kmz_data = zf.read(name)
                    with zipfile.ZipFile(io.BytesIO(kmz_data), 'r') as inner_zf:
                        for inner_name in inner_zf.namelist():
                            if inner_name.lower().endswith('.kml'):
                                mapping.update(parse_kml_extended(inner_zf.read(inner_name)))
    except Exception as e:
        print(f"Error processing {zip_path}: {e}")
    return mapping

# Paths
csv_path = r"D:\Ayak\Project Rolling\ZRS86_Filtered.csv"
kmz_zips = [
    r"D:\Ayak\Project Rolling\COV LMP1 APRIL 26 F2 (1).kmz.zip",
    r"D:\Ayak\Project Rolling\COV LMP1 F4 29APr26 (1).kmz.zip"
]

# Build mapping
full_mapping = {}
for zip_p in kmz_zips:
    full_mapping.update(get_mapping_from_kmz_zip(zip_p))

print(f"Total unique mappings found: {len(full_mapping)}")

# Update CSV
print(f"Updating {csv_path}...")
rows = []
with open(csv_path, 'r', newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    rows = list(reader)

if not rows:
    print("CSV is empty.")
    exit(1)

headers = rows[0]
c_idx = -1
for i, h in enumerate(headers):
    if h == "Customer":
        c_idx = i
        break

if c_idx == -1:
    print("Error: 'Customer' column not found.")
    exit(1)

if "Latitude" not in headers:
    headers.append("Latitude")
if "Longitude" not in headers:
    headers.append("Longitude")

lat_idx = headers.index("Latitude")
lon_idx = headers.index("Longitude")

match_count = 0
for row in rows[1:]:
    cust_code = clean_code(row[c_idx])
    coords = full_mapping.get(cust_code)
    
    if coords:
        lat, lon = coords
        match_count += 1
    else:
        lat, lon = ("", "")
    
    while len(row) < len(headers):
        row.append("")
    
    row[lat_idx] = lat
    row[lon_idx] = lon

with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(rows)

print(f"CSV updated. Successfully matched {match_count} customers out of {len(rows)-1}.")
