import openpyxl
import os

file_path = r"D:\Ayak\Project Rolling\ZR268 (1).xlsx"

wb = openpyxl.load_workbook(file_path, data_only=True)
ws = wb.active # Assuming first sheet is the one to preview

rows = []
for i, row in enumerate(ws.iter_rows(values_only=True)):
    if i >= 20: # Limit to 20 rows
        break
    rows.append([str(cell) if cell is not None else "" for cell in row])

if rows:
    # Print as markdown table
    header = rows[0]
    separator = ["---"] * len(header)
    print("| " + " | ".join(header) + " |")
    print("| " + " | ".join(separator) + " |")
    for row in rows[1:]:
        print("| " + " | ".join(row) + " |")
else:
    print("No data found.")
