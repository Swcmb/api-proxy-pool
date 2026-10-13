import sys
from pathlib import Path

source = sys.argv[1]
count = int(sys.argv[2])

with open(source, encoding="utf-8") as f:
    lines = f.readlines()

folder = Path("workspace/chunks")
folder.mkdir(parents=True, exist_ok=True)

size = len(lines) // count + 1

for i in range(count):
    data = lines[i * size : (i + 1) * size]
    (folder / f"{i}.txt").write_text("".join(data), encoding="utf-8")
    print(i, len(data))