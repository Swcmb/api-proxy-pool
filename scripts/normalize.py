import csv
import sys

csv_file = sys.argv[1]
proxifly = sys.argv[2]
output = sys.argv[3]

result = set()

with open(csv_file, encoding="utf8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get("alive") != "true":
            continue
        for protocol in row["protocols"].split(","):
            result.add(f"{protocol.strip()}://{row['ip']}:{row['port']}")

with open(proxifly, encoding="utf8") as f:
    for line in f:
        line = line.strip()
        if line:
            result.add(line)

with open(output, "w", encoding="utf8") as f:
    for item in sorted(result):
        f.write(item + "\n")

print("total:", len(result))