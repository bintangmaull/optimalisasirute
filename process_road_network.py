import shapefile
import networkx as nx
import os

# Paths
shp_dirs = [
    r"D:\Ayak\Project Rolling\SHP\[Lapak GIS.com] KAB. TANGGAMUS",
    r"D:\Ayak\Project Rolling\SHP\[Lapak GIS.com] KAB. PESAWARAN",
    r"D:\Ayak\Project Rolling\SHP\[Lapak GIS.com] KOTA BANDARLAMPUNG"
]

def build_graph(dirs):
    G = nx.Graph()
    for d in dirs:
        path = os.path.join(d, "JALAN_LN_50K.shp")
        if not os.path.exists(path):
            print(f"Warning: {path} not found")
            continue
        
        print(f"Reading {path}...")
        sf = shapefile.Reader(path)
        shapes = sf.shapes()
        
        for shape in shapes:
            points = shape.points
            for i in range(len(points) - 1):
                p1 = (round(points[i][1], 6), round(points[i][0], 6)) # (lat, lon)
                p2 = (round(points[i+1][1], 6), round(points[i+1][0], 6))
                
                # Haversine distance for accuracy (simplified to degrees for comparison works too)
                # But let's use Euclidean in degrees for now as it's sufficient for relative distance
                d_val = ((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)**0.5
                G.add_edge(p1, p2, weight=d_val)
    
    return G

G = build_graph(shp_dirs)
print(f"Graph built with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")

terminal = (-5.346648, 105.216119)
nodes = list(G.nodes())
if nodes:
    nearest = min(nodes, key=lambda n: ((n[0]-terminal[0])**2 + (n[1]-terminal[1])**2)**0.5)
    print(f"Terminal: {terminal}")
    print(f"Nearest Node: {nearest}")
    dist = ((nearest[0]-terminal[0])**2 + (nearest[1]-terminal[1])**2)**0.5
    print(f"Dist: {dist} degrees (~{dist*111:.3f} km)")
else:
    print("No nodes found!")
