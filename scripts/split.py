import sys
from pathlib import Path


src=sys.argv[1]

count=int(sys.argv[2])


lines=open(src).readlines()


out=Path("workspace/chunks")

out.mkdir(
    parents=True,
    exist_ok=True
)


size=len(lines)//count+1



for i in range(count):

    part=lines[
        i*size:
        (i+1)*size
    ]


    Path(
        out/f"{i}.txt"
    ).write_text(
        "".join(part)
    )


    print(
        i,
        len(part)
    )
