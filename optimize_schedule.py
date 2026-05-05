import csv
import math

csv_path = r"D:\Ayak\Project Rolling\ZRS86_Filtered.csv"

# Load data
rows = []
with open(csv_path, 'r', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

# Group by salesperson
sales_data = {}
for i, row in enumerate(rows):
    if not row['Latitude'] or not row['Longitude']:
        continue
    
    person = row['Personnel Name']
    if person not in sales_data:
        sales_data[person] = []
    
    # Store original index and key data
    sales_data[person].append({
        "index": i,
        "lat": float(row['Latitude']),
        "lon": float(row['Longitude']),
        "day": row['JWK SALESMAN']
    })

days_base = ["SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU"]

for person, stores in sales_data.items():
    # Sort stores spatially (simple lat-lon sort or cluster-like order)
    # Using atan2 for a radial sort from the centroid to group them somewhat spatially
    centroid_lat = sum(s['lat'] for s in stores) / len(stores)
    centroid_lon = sum(s['lon'] for s in stores) / len(stores)
    
    for s in stores:
        # Distance from centroid and angle
        s['angle'] = math.atan2(s['lat'] - centroid_lat, s['lon'] - centroid_lon)
    
    # Sort by angle to get a sequence that flows around the centroid
    stores.sort(key=lambda x: x['angle'])
    
    # Calculate total slots: Full day = 2, Ganjil/Genap = 1
    total_slots = 0
    for s in stores:
        if s['day'] in ["SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU"]:
            s['slots'] = 2
            s['type'] = 'FULL'
        else:
            s['slots'] = 1
            s['type'] = 'HALF'
        total_slots += s['slots']
    
    # Target per day: Mon-Fri = 1 unit, Sat = 0.5 unit
    # Total units = 5.5
    unit_cap = total_slots / 5.5
    day_caps = {
        "SENIN": unit_cap,
        "SELASA": unit_cap,
        "RABU": unit_cap,
        "KAMIS": unit_cap,
        "JUMAT": unit_cap,
        "SABTU": unit_cap * 0.5
    }
    
    # Rough assignment
    current_slots = 0
    day_idx = 0
    
    # We need to assign each slot to GANJIL/GENAP if HALF
    # Or both if FULL
    
    half_trackers = {
        "SENIN": "GANJIL",
        "SELASA": "GANJIL",
        "RABU": "GANJIL",
        "KAMIS": "GANJIL",
        "JUMAT": "GANJIL",
        "SABTU": "GANJIL"
    }

    for s in stores:
        current_day = days_base[day_idx]
        
        if s['type'] == 'FULL':
            s['new_day'] = current_day
            current_slots += 2
        else:
            # Alternate GANJIL/GENAP within the same day for HALF slots
            freq = half_trackers[current_day]
            s['new_day'] = f"{current_day} {freq}"
            current_slots += 1
            # Flip next freq
            half_trackers[current_day] = "GENAP" if freq == "GANJIL" else "GANJIL"
            
        # Move to next day if cap reached
        if current_slots >= day_caps[current_day] and day_idx < 5:
            current_slots = 0
            day_idx += 1

# Update the overall rows
if "Optimized JWK" not in fieldnames:
    fieldnames.append("Optimized JWK")

for person, stores in sales_data.items():
    for s in stores:
        rows[s['index']]['Optimized JWK'] = s.get('new_day', s['day'])

# Handle missing (those without lat/lon)
for row in rows:
    if 'Optimized JWK' not in row:
        row['Optimized JWK'] = row['JWK SALESMAN']

# Save CSV
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("Schedule optimized and saved to Optimized JWK column.")
