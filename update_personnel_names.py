import csv

file_path = r"D:\Ayak\Project Rolling\ZRS86_Filtered.csv"
name_map = {
    "90051274": "SUPRAYOGA ABDI PUTRA",
    "90052003": "TAUFAN DWI SEPTIAN",
    "90052197": "YUDDY SYAHPUTRA",
    "90052353": "REKI YULIANDRI"
}

print(f"Updating {file_path}...")
rows = []
with open(file_path, "r", newline="", encoding="utf-8") as f:
    reader = csv.reader(f)
    rows = list(reader)

if not rows:
    print("Error: CSV is empty.")
    exit(1)

headers = rows[0]
p_idx = -1
for i, h in enumerate(headers):
    if h == "Personnel Number":
        p_idx = i
        break

if p_idx == -1:
    print("Error: 'Personnel Number' column not found.")
    exit(1)

# Add header if not already there
if "Personnel Name" not in headers:
    headers.append("Personnel Name")

for row in rows[1:]:
    p_num = str(row[p_idx]).strip()
    name = name_map.get(p_num, "Unknown")
    # If we already added the column, update the last element, otherwise append
    if len(row) < len(headers):
        row.append(name)
    else:
        # Assuming the last column is Personnel Name if already present
        # Or just append to be safe if count matches
        row[-1] = name

with open(file_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows(rows)

print("Personnel names added successfully.")
