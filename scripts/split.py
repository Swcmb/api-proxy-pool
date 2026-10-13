from __future__ import annotations

import math
import sys
from pathlib import Path

OUTPUT_DIR = Path("workspace/chunks")


def read_lines(path: Path) -> list[str]:
    lines: list[str] = []

    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                lines.append(line)

    return lines


def split_chunks(lines: list[str], count: int) -> list[list[str]]:
    if count <= 0:
        raise ValueError("count must be a positive integer")

    chunk_size = math.ceil(len(lines) / count)

    return [
        lines[i * chunk_size : (i + 1) * chunk_size]
        for i in range(count)
    ]


def write_chunks(chunks: list[list[str]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for i, chunk in enumerate(chunks):
        file = output_dir / f"{i}.txt"
        file.write_text("\n".join(chunk), encoding="utf-8")
        print(f"{file}: {len(chunk)}")


def main() -> None:
    if len(sys.argv) != 3:
        print(
            f"Usage: {Path(sys.argv[0]).name} <source_file> <count>",
            file=sys.stderr,
        )
        raise SystemExit(1)

    source = Path(sys.argv[1])

    try:
        count = int(sys.argv[2])
    except ValueError:
        print("Error: count must be an integer", file=sys.stderr)
        raise SystemExit(1)

    lines = read_lines(source)

    if not lines:
        raise RuntimeError("Input proxy list is empty")

    chunks = split_chunks(lines, count)
    write_chunks(chunks, OUTPUT_DIR)


if __name__ == "__main__":
    main()
