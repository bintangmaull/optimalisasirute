import csv
import json
import os

csv_path = r"D:\Ayak\Project Rolling\ZRS86_Filtered.csv"
roads_path = r"D:\Ayak\Project Rolling\roads.json"
output_html = r"D:\Ayak\Project Rolling\index.html"
START_COORD = [-5.346648, 105.216119]

print(f"Reading {csv_path}...")
data = []
with open(csv_path, 'r', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('Latitude') and row.get('Longitude'):
            try:
                lat = float(row['Latitude'])
                lon = float(row['Longitude'])
                data.append({
                    "id": str(row.get('Customer')),
                    "name": row.get('Name 1'),
                    "address": row.get('Street'),
                    "sales": row.get('Personnel Name'),
                    "day_old": row.get('JWK SALESMAN'),
                    "day_new": row.get('Optimized JWK'),
                    "lat": lat,
                    "lon": lon
                })
            except:
                continue

print(f"Extracted {len(data)} points.")

# Load Roads with BBox Metadata
roads_data = []
if os.path.exists(roads_path):
    print(f"Loading {roads_path} (33MB)...")
    with open(roads_path, 'r') as f:
        roads_data = json.load(f)
    print(f"Loaded {len(roads_data)} road segments with BBox.")

html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enterprise Route Planner - Dynamic Road Filter</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #6366f1;
            --bg: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.9);
            --text: #f8fafc;
        }}
        body, html {{ margin: 0; padding: 0; height: 100%; font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); overflow: hidden; }}
        
        .container {{ display: flex; width: 100vw; height: 100vh; }}
        .map-wrapper {{ flex: 1; position: relative; border-right: 1px solid #334155; }}
        .map-container {{ height: 100%; width: 100%; }}
        
        .map-overlay {{
            position: absolute;
            top: 20px;
            left: 20px;
            z-index: 1001;
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            padding: 15px;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.1);
            width: 220px;
            max-height: 85vh;
            overflow-y: auto;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        }}

        .map-header {{
            background: var(--card-bg);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: #818cf8;
            border: 1px solid rgba(255,255,255,0.1);
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }}
        
        h2 {{ margin: 0 0 5px 0; font-size: 14px; font-weight: 600; color: #fff; }}
        .count-badge {{ font-size: 10px; color: #818cf8; margin-bottom: 8px; display: block; }}

        .filter-group {{ margin-bottom: 10px; }}
        label {{ display: block; margin-bottom: 4px; font-size: 9px; color: #94a3b8; text-transform: uppercase; }}
        select {{ width: 100%; padding: 6px; background: #1e293b; border: 1px solid #334155; color: #f8fafc; border-radius: 4px; font-size: 11px; }}
        
        .checkbox-group {{ display: flex; align-items: center; gap: 8px; margin-top: 10px; font-size: 10px; color: #94a3b8; }}
        .checkbox-group input {{ width: auto; cursor: pointer; }}

        .route-actions {{ border-top: 1px solid #334155; margin-top: 5px; padding-top: 10px; }}
        .route-btn {{
            width: 100%;
            padding: 8px;
            background: #6366f1;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 10px;
            font-weight: 600;
            cursor: pointer;
            margin-bottom: 5px;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .route-btn:hover {{ background: #4f46e5; }}
        .route-btn.secondary {{ background: #1e293b; border: 1px solid #6366f1; color: #818cf8; }}
        
        .stop-number {{
            background: rgba(255,255,255,0.9);
            color: #0f172a;
            border-radius: 50%;
            width: 14px;
            height: 14px;
            font-size: 8px;
            font-weight: 700;
            line-height: 14px;
            text-align: center;
            border: 1px solid #334155;
        }}
        
        .store-label {{
            display: none;
            position: absolute;
            top: -18px;
            left: 20px;
            background: rgba(15, 23, 42, 0.85);
            padding: 2px 6px;
            border-radius: 4px;
            color: white;
            font-size: 9px;
            white-space: nowrap;
            pointer-events: none;
            border: 1px solid rgba(255,255,255,0.2);
            z-index: 2000;
        }}
        .show-labels .store-label {{ display: block; }}

        .legend-section {{ margin-top: 12px; padding-top: 8px; border-top: 1px solid #334155; }}
        .legend-title {{ font-size: 9px; color: #94a3b8; text-transform: uppercase; margin-bottom: 5px; }}
        .legend-item {{ display: flex; align-items: center; margin-bottom: 3px; font-size: 10px; }}
        .color-box {{ width: 10px; height: 10px; border-radius: 2px; margin-right: 8px; flex-shrink: 0; }}
        .shape-icon {{ width: 14px; height: 14px; margin-right: 8px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
        
        #loading {{
            position: fixed; top: 10px; right: 10px;
            background: rgba(0,0,0,0.8); padding: 8px 15px; border-radius: 20px;
            z-index: 9999; display: none; color: white; font-size: 11px;
        }}

        .timeline-overlay {{
            position: absolute;
            top: 20px;
            bottom: 20px;
            right: 20px;
            z-index: 1001;
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            padding: 15px;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.1);
            width: 200px;
            overflow-y: auto;
            display: none;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        }}
        
        .timeline-flex {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        
        .timeline-card {{
            background: rgba(255,255,255,0.05);
            padding: 10px;
            border-radius: 8px;
            font-size: 10px;
            border-left: 3px solid var(--primary);
            position: relative;
        }}
        
        .timeline-card b {{ display: block; margin-bottom: 2px; color: #fff; }}
        .timeline-card span {{ color: #94a3b8; display: block; font-size: 9px; }}
        .timeline-card .time {{ color: #818cf8; font-weight: 600; font-size: 11px; margin-bottom: 4px; }}
        .hidden {{ display: none !important; }}
    </style>
</head>
<body>
<div id="loading">Memperbarui rute...</div>

<div class="main-header" style="display:flex; justify-content:space-between; align-items:center; padding: 10px 20px; background: var(--card-bg); border-bottom: 1px solid rgba(255,255,255,0.1); z-index: 2000; position:relative;">
    <h1 style="margin:0; font-size:18px;">Sales Visit Dashboard</h1>
    <button onclick="toggleOriginal()" class="route-btn" style="width:auto; padding: 8px 15px; margin:0; background:#4f46e5; border:1px solid rgba(255,255,255,0.2);">
        Buka/Tutup Pembanding
    </button>
</div>

<div class="container">
    <div class="map-wrapper">
        <div class="map-header">Original Schedule</div>
        <div class="map-overlay">
            <h2>Original</h2>
            <span class="count-badge" id="countL">Total: 0 toko</span>
            <div class="filter-group">
                <label>Sales Analyst</label>
                <select id="salesL"><option value="all">All Personnel</option></select>
            </div>
            <div class="filter-group">
                <label>Visit Day</label>
                <select id="dayL"><option value="all">All Days</option></select>
            </div>
            <div class="checkbox-group">
                <input type="checkbox" id="showRoadsL"> <label for="showRoadsL">Tampilkan Jalan</label>
            </div>
            <div class="checkbox-group">
                <input type="checkbox" id="showTimelineL"> <label for="showTimelineL">Tampilkan Timeline</label>
            </div>
            <div id="actionsL" class="route-actions"></div>
            <div class="legend-section"><div class="legend-title">Days</div><div id="dayLegendL"></div></div>
            <div class="legend-section"><div class="legend-title">Analysts</div><div id="salesLegendL"></div></div>
        </div>
        <div id="mapL" class="map-container"></div>
        <div id="timelineL" class="timeline-overlay"><div class="timeline-flex" id="timelineFlexL"></div></div>
    </div>
    <div class="map-wrapper">
        <div class="map-header">Optimized Schedule</div>
        <div class="map-overlay">
            <h2>Optimized</h2>
            <span class="count-badge" id="countR">Total: 0 toko</span>
            <div class="filter-group">
                <label>Sales Analyst</label>
                <select id="salesR"><option value="all">All Personnel</option></select>
            </div>
            <div class="filter-group">
                <label>Visit Day</label>
                <select id="dayR"><option value="all">All Days</option></select>
            </div>
            <div class="checkbox-group">
                <input type="checkbox" id="showRoadsR"> <label for="showRoadsR">Tampilkan Jalan</label>
            </div>
            <div class="checkbox-group">
                <input type="checkbox" id="showTimelineR"> <label for="showTimelineR">Tampilkan Timeline</label>
            </div>
            <div id="actionsR" class="route-actions"></div>
            <div class="legend-section"><div class="legend-title">Days</div><div id="dayLegendR"></div></div>
            <div class="legend-section"><div class="legend-title">Analysts</div><div id="salesLegendR"></div></div>
        </div>
        <div id="mapR" class="map-container"></div>
        <div id="timelineR" class="timeline-overlay"><div class="timeline-flex" id="timelineFlexR"></div></div>
    </div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
    const data_pts = {json.dumps(data)};
    const roads_pts = {json.dumps(roads_data)};
    const terminal = {{ lat: {START_COORD[0]}, lon: {START_COORD[1]} }};
    
    const dayColors = {{
        "SENIN": "#6366f1", "SENIN GANJIL": "#818cf8", "SENIN GENAP": "#4f46e5",
        "SELASA": "#f59e0b", "SELASA GANJIL": "#fbbf24", "SELASA GENAP": "#d97706",
        "RABU": "#10b981", "RABU GANJIL": "#34d399", "RABU GENAP": "#059669",
        "KAMIS": "#8b5cf6", "KAMIS GANJIL": "#a78bfa", "KAMIS GENAP": "#7c3aed",
        "JUMAT": "#ec4899", "JUMAT GANJIL": "#f472b6", "JUMAT GENAP": "#db2777",
        "SABTU": "#06b6d4", "SABTU GANJIL": "#22d3ee", "SABTU GENAP": "#0891b2"
    }};
    const shapes = [
        '<circle cx="8" cy="8" r="6" fill="COLOR" stroke="#fff" stroke-width="1" />',
        '<rect x="2" y="2" width="12" height="12" fill="COLOR" stroke="#fff" stroke-width="1" />',
        '<path d="M8 2 L14 14 L2 14 Z" fill="COLOR" stroke="#fff" stroke-width="1" />',
        '<path d="M8 2 L14 8 L8 14 L2 8 Z" fill="COLOR" stroke="#fff" stroke-width="1" />'
    ];

    const mapL = L.map('mapL', {{ zoomControl: false, preferCanvas: true }}).setView([terminal.lat, terminal.lon], 11);
    const mapR = L.map('mapR', {{ zoomControl: false, preferCanvas: true }}).setView([terminal.lat, terminal.lon], 11);

    L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{ attribution: '&copy; CARTO' }}).addTo(mapL);
    L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{ attribution: '&copy; CARTO' }}).addTo(mapR);

    mapL.on('move', () => mapR.setView(mapL.getCenter(), mapL.getZoom(), {{ animate: false }}));
    mapR.on('move', () => mapL.setView(mapR.getCenter(), mapR.getZoom(), {{ animate: false }}));

    const handleZoom = () => {{
        const show = mapL.getZoom() >= 14;
        document.getElementById('mapL').classList.toggle('show-labels', show);
        document.getElementById('mapR').classList.toggle('show-labels', show);
    }};
    mapL.on('zoomend', handleZoom); mapR.on('zoomend', handleZoom);

    const layerMarkersL = L.layerGroup().addTo(mapL);
    const layerMarkersR = L.layerGroup().addTo(mapR);
    const layerRouteL = L.layerGroup().addTo(mapL);
    const layerRouteR = L.layerGroup().addTo(mapR);
    const layerRoadsL = L.featureGroup().addTo(mapL);
    const layerRoadsR = L.featureGroup().addTo(mapR);

    const houseIcon = L.divIcon({{ 
        html: '<svg viewBox="0 0 24 24" width="24" height="24" fill="#ef4444" stroke="#fff" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
        className: '', iconSize: [24, 24], iconAnchor: [12, 12]
    }});
    L.marker([terminal.lat, terminal.lon], {{ icon: houseIcon, zIndexOffset: 1000 }}).addTo(mapL).bindPopup("Start");
    L.marker([terminal.lat, terminal.lon], {{ icon: houseIcon, zIndexOffset: 1000 }}).addTo(mapR).bindPopup("Start");

    const salesNames = [...new Set(data_pts.map(d => d.sales))].sort();
    const salesShapes = {{}};
    salesNames.forEach((n, i) => salesShapes[n] = shapes[i % shapes.length]);

    const populate = (id, options) => {{
        const el = document.getElementById(id);
        options.forEach(o => el.add(new Option(o, o)));
    }};
    populate('salesL', salesNames); populate('salesR', salesNames);
    populate('dayL', Object.keys(dayColors)); populate('dayR', Object.keys(dayColors));

    const buildLegend = (dayId, salesId) => {{
        const dL = document.getElementById(dayId);
        ["SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU"].forEach(d => {{
            dL.innerHTML += `<div class="legend-item"><span class="color-box" style="background:${{dayColors[d]}}"></span>${{d}}</div>`;
        }});
        const sL = document.getElementById(salesId);
        salesNames.forEach(n => sL.innerHTML += `<div class="legend-item"><span class="shape-icon"><svg width="14" height="14">${{salesShapes[n].replace('COLOR', '#94a3b8')}}</svg></span>${{n}}</div>`);
    }};
    buildLegend('dayLegendL', 'salesLegendL'); buildLegend('dayLegendR', 'salesLegendR');

    function matchesDay(itemDay, filterDay) {{
        if (filterDay === 'all') return true;
        if (!filterDay.includes('GANJIL') && !filterDay.includes('GENAP')) {{ return itemDay === filterDay; }}
        if (filterDay.includes('GANJIL')) {{
            const base = filterDay.replace(' GANJIL', '');
            return itemDay === filterDay || itemDay === base;
        }}
        if (filterDay.includes('GENAP')) {{
            const base = filterDay.replace(' GENAP', '');
            return itemDay === filterDay || itemDay === base;
        }}
        return false;
    }}

    function haversineDistance(p1, p2) {{
        const R = 6371; // km
        const dLat = (p2.lat - p1.lat) * Math.PI / 180;
        const dLon = (p2.lon - p1.lon) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(p1.lat * Math.PI / 180) * Math.cos(p2.lat * Math.PI / 180) * 
                  Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    }}

    function formatTime(date) {{
        return date.getHours().toString().padStart(2, '0') + ":" + date.getMinutes().toString().padStart(2, '0');
    }}

    function solveTSP(start, stops) {{
        let current = start; let remaining = [...stops]; let route = [];
        while (remaining.length > 0) {{
            let nearestIdx = 0; let minDist = Math.sqrt(Math.pow(current.lat - remaining[0].lat, 2) + Math.pow(current.lon - remaining[0].lon, 2));
            for (let i = 1; i < remaining.length; i++) {{
                let d = Math.sqrt(Math.pow(current.lat - remaining[i].lat, 2) + Math.pow(current.lon - remaining[i].lon, 2));
                if (d < minDist) {{ minDist = d; nearestIdx = i; }}
            }}
            current = remaining[nearestIdx]; route.push(current); remaining.splice(nearestIdx, 1);
        }}
        return route;
    }}

    function renderMap(side, sVal, dVal, layerMarkers, layerRoute, actionId, color) {{
        document.getElementById('loading').style.display = 'block';
        layerMarkers.clearLayers(); layerRoute.clearLayers();
        const filtered = data_pts.filter(item => (sVal === 'all' || item.sales === sVal) && matchesDay(side === 'L' ? item.day_old : item.day_new, dVal));
        
        // PERFORMANCE OPTIMIZATION: If All Personnel & All Days is selected, skip TSP and Polyline
        const isAll = (sVal === 'all' && dVal === 'all');
        const route = isAll ? filtered : solveTSP(terminal, filtered);
        
        let currentTime = new Date();
        currentTime.setHours(7, 0, 0, 0); // Start at 07:00
        const speedKmh = 30;
        const visitDurationMins = 20;
        let breakTaken = false;
        
        const timelineFlex = document.getElementById('timelineFlex' + side);
        const currentTimelineOverlay = document.getElementById('timeline' + side);
        timelineFlex.innerHTML = '';
        
        const showTimeline = document.getElementById('showTimeline' + side).checked;
        if (route.length > 0 && showTimeline && !isAll) {{
            currentTimelineOverlay.style.display = 'block';
        }} else {{
            currentTimelineOverlay.style.display = 'none';
        }}

        let prevPoint = terminal;
        route.forEach((p, i) => {{
            const dist = haversineDistance(prevPoint, p);
            const travelTimeMins = (dist / speedKmh) * 60;
            currentTime = new Date(currentTime.getTime() + travelTimeMins * 60000);
            
            // Break logic: 12:00 - 13:00
            if (!breakTaken && currentTime.getHours() >= 12) {{
                timelineFlex.innerHTML += `
                    <div class="timeline-card" style="border-left-color: #f87171; background: rgba(248, 113, 113, 0.1);">
                        <b>☕ ISTIRAHAT</b>
                        <span class="time">12:00 - 13:00</span>
                    </div>
                `;
                currentTime = new Date(currentTime.getTime() + 60 * 60000);
                breakTaken = true;
            }}

            const arrival = new Date(currentTime.getTime());
            currentTime = new Date(currentTime.getTime() + visitDurationMins * 60000);
            const departure = new Date(currentTime.getTime());
            
            p.arrival = formatTime(arrival);
            p.departure = formatTime(departure);
            prevPoint = p;

            const labelCol = dayColors[side === 'L' ? p.day_old : p.day_new] || '#94a3b8';
            const iconHtml = `<div style="position:relative;"><svg width="18" height="18">${{salesShapes[p.sales].replace('COLOR', labelCol)}}</svg><div class="stop-number" style="position:absolute; top:-7px; right:-7px;">${{isAll ? '-' : i+1}}</div><div class="store-label">${{p.name}}</div></div>`;
            
            L.marker([p.lat, p.lon], {{ icon: L.divIcon({{ html: iconHtml, className: '', iconSize:[18,18], iconAnchor:[9,9] }}) }})
                .bindPopup(`<b>${{p.name}}</b><br><span style="color:#818cf8">Arrival: ${{p.arrival}}</span><br><span style="color:#6366f1">Departure: ${{p.departure}}</span>`)
                .addTo(layerMarkers);
                
            if (!isAll) {{
                const dayStr = (side === 'L' ? p.day_old : p.day_new) || "";
                let cycleLabel = "Ganjil & Genap";
                if (dayStr.includes("GANJIL")) cycleLabel = "Minggu Ganjil";
                else if (dayStr.includes("GENAP")) cycleLabel = "Minggu Genap";

                timelineFlex.innerHTML += `
                    <div class="timeline-card" style="border-left-color: ${{labelCol}}">
                        <b>#${{i+1}} [${{p.id}}] ${{p.name}}</b>
                        <span class="time">${{p.arrival}} - ${{p.departure}}</span>
                        <span style="color:#818cf8; font-size:8px; margin-bottom:2px;">${{cycleLabel}}</span>
                        <span>${{dist.toFixed(1)}} km from prev</span>
                    </div>
                `;
            }}
        }});

        if (route.length > 0 && !isAll) L.polyline([ [terminal.lat, terminal.lon], ...route.map(p => [p.lat, p.lon]) ], {{ color: color, weight: 2, opacity: 0.4, dashArray: '5, 5' }}).addTo(layerRoute);

        // Update Road Filter if checked
        const roadChecked = document.getElementById('showRoads' + side).checked;
        updateRoads(side, roadChecked, filtered);

        const actions = document.getElementById(actionId); actions.innerHTML = '';
        if (route.length > 0 && !isAll) {{
            const limit = 20; const parts = Math.ceil(route.length / limit);
            for (let i = 0; i < parts; i++) {{
                const btn = document.createElement('button'); btn.className = 'route-btn' + (i > 0 ? ' secondary' : '');
                btn.innerText = `Buka G-Maps Bagian ${{i+1}}`;
                btn.onclick = () => {{
                    const subset = route.slice(i*limit, (i+1)*limit);
                    const origin = (i === 0 ? terminal.lat+','+terminal.lon : route[i*limit-1].lat+','+route[i*limit-1].lon);
                    const destination = subset[subset.length - 1].lat+','+subset[subset.length - 1].lon;
                    const waypoints = subset.slice(0, -1).map(p => p.lat+','+p.lon).join('|');
                    window.open(`https://www.google.com/maps/dir/?api=1&origin=${{origin}}&destination=${{destination}}&waypoints=${{waypoints}}&travelmode=driving`, '_blank');
                }};
                actions.appendChild(btn);
            }}
        }}
        document.getElementById('count' + side).innerText = `Total: ${{filtered.length}} toko`;
        document.getElementById('loading').style.display = 'none';
    }}

    function updateRoads(side, checked, filteredStores) {{
        const layer = side === 'L' ? layerRoadsL : layerRoadsR;
        layer.clearLayers();
        if (checked && roads_pts.length > 0 && (filteredStores.length > 0 || side === 'L')) {{
            let pointsForBBox = [...filteredStores, terminal];
            let minLat = Math.min(...pointsForBBox.map(p => p.lat)) - 0.02;
            let maxLat = Math.max(...pointsForBBox.map(p => p.lat)) + 0.02;
            let minLon = Math.min(...pointsForBBox.map(p => p.lon)) - 0.02;
            let maxLon = Math.max(...pointsForBBox.map(p => p.lon)) + 0.02;

            roads_pts.forEach(road => {{
                const b = road.bbox;
                if (!(b[0] > maxLat || b[2] < minLat || b[1] > maxLon || b[3] < minLon)) {{
                    L.polyline(road.pts, {{ color: '#94a3b8', weight: 1.2, opacity: 0.5, interactive: false }}).addTo(layer);
                }}
            }});
        }}
    }}

    function toggleOriginal() {{
        const left = document.querySelector('.map-wrapper:first-child');
        left.classList.toggle('hidden');
        mapR.invalidateSize();
        mapL.invalidateSize();
    }}

    const triggerL = () => renderMap('L', document.getElementById('salesL').value, document.getElementById('dayL').value, layerMarkersL, layerRouteL, 'actionsL', '#60a5fa');
    const triggerR = () => renderMap('R', document.getElementById('salesR').value, document.getElementById('dayR').value, layerMarkersR, layerRouteR, 'actionsR', '#818cf8');

    document.getElementById('salesL').onchange = document.getElementById('dayL').onchange = triggerL;
    document.getElementById('salesR').onchange = document.getElementById('dayR').onchange = triggerR;
    
    document.getElementById('showRoadsL').onchange = triggerL;
    document.getElementById('showRoadsR').onchange = triggerR;
    document.getElementById('showTimelineL').onchange = triggerL;
    document.getElementById('showTimelineR').onchange = triggerR;

    triggerL(); triggerR();
    if (data_pts.length > 0) mapL.fitBounds(new L.featureGroup(data_pts.map(d => L.marker([d.lat, d.lon]))).getBounds().pad(0.1));
</script>
</body>
</html>
"""

with open(output_html, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"Dynamic Map generated: {output_html}")
