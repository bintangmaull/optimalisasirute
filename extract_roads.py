import shapefile
import json
import os

shp_root = r"D:\Ayak\Project Rolling\SHP"
output_json = r"D:\Ayak\Project Rolling\roads.json"

road_features = []
total_segments = 0

print("Scanning for all Shapefiles in subdirectories...")
for root, dirs, files in os.walk(shp_root):
    for f in files:
        if f.upper() == "JALAN_LN_50K.SHP":
            path = os.path.join(root, f)
            print(f"Reading {path}...")
            try:
                sf = shapefile.Reader(path)
                for shape in sf.shapes():
                    if len(shape.points) < 2: continue
                    
                    # Round coords to save space
                    points = [[round(p[1], 4), round(p[0], 4)] for p in shape.points]
                    # Also include a pre-calculated bbox for FAST filtering in JS: [min_lat, min_lon, max_lat, max_lon]
                    lats = [p[0] for p in points]
                    lons = [p[1] for p in points]
                    bbox = [min(lats), min(lons), max(lats), max(lons)]
                    
                    road_features.append({"pts": points, "bbox": bbox})
                    total_segments += 1
            except Exception as e:
                print(f"Error reading {path}: {e}")

print(f"Extracted {total_segments} road segments total with BBox metadata.")

with open(output_json, 'w') as f:
    json.dump(road_features, f)

print(f"Road data saved to {output_json}")
