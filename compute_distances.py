import shapefile
import networkx as nx
import os
import csv
import math
import pickle
from collections import defaultdict

# Paths
shp_root = r"D:\Ayak\Project Rolling\SHP"
shp_dirs = [os.path.join(shp_root, d) for d in os.listdir(shp_root) if os.path.isdir(os.path.join(shp_root, d))]
csv_path = r"D:\Ayak\Project Rolling\ZRS86_Filtered.csv"
output_matrix = r"D:\Ayak\Project Rolling\dist_matrix.pkl"
TERMINAL_COORD = (-5.346648, 105.216119)

def build_graph(dirs):
    G = nx.Graph()
    # Snapping: use a coarser grid to merge nearby nodes at borders
    # 5 decimals ~ 1.1m
    def snap(p): return (round(p[1], 5), round(p[0], 5))

    for d in dirs:
        path = os.path.join(d, "JALAN_LN_50K.shp")
        if not os.path.exists(path): continue
        print(f"Reading {path}...")
        sf = shapefile.Reader(path)
        for shape in sf.shapes():
            pts = shape.points
            for i in range(len(pts) - 1):
                p1, p2 = snap(pts[i]), snap(pts[i+1])
                if p1 == p2: continue
                d_val = math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)
                G.add_edge(p1, p2, weight=d_val)
    return G

print("Building graph...")
G = build_graph(shp_dirs)
print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Find largest connected component (to avoid isolated tiny networks)
print("Finding connected components...")
components = sorted(nx.connected_components(G), key=len, reverse=True)
G_main = G.subgraph(components[0]).copy()
print(f"Main component: {G_main.number_of_nodes()} nodes")

# Map customers to nearest nodes in main component
customers = []
with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('Latitude') and row.get('Longitude'):
            customers.append({
                'id': row['Customer'],
                'lat': float(row['Latitude']),
                'lon': float(row['Longitude'])
            })

print(f"Mapping {len(customers)} customers...")
nodes = list(G_main.nodes())
# For speed, we'll use a simple approach but better would be a KD-tree
# But let's just do it for now
cust_nodes = []
for c in customers:
    # Find nearest node in graph
    target = (c['lat'], c['lon'])
    nearest = min(nodes, key=lambda n: (n[0]-target[0])**2 + (n[1]-target[1])**2)
    cust_nodes.append(nearest)

terminal_node = min(nodes, key=lambda n: (n[0]-TERMINAL_COORD[0])**2 + (n[1]-TERMINAL_COORD[1])**2)
all_targets = list(set(cust_nodes + [terminal_node]))

print(f"Calculating distance matrix for {len(all_targets)} nodes...")
# This is the heavy part
dist_matrix = {}
for i, source in enumerate(all_targets):
    if i % 100 == 0: print(f"Processing source {i}/{len(all_targets)}...")
    lengths = nx.single_source_dijkstra_path_length(G_main, source, weight='weight')
    dist_matrix[source] = {t: lengths.get(t, float('inf')) for t in all_targets}

# Save for next step
with open(output_matrix, 'wb') as f:
    pickle.dump({'matrix': dist_matrix, 'mapping': dict(zip([c['id'] for c in customers], cust_nodes)), 'terminal': terminal_node}, f)

print("Distance matrix saved.")
