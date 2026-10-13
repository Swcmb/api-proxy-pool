import sys
import json
from pathlib import Path
from datetime import datetime,timezone


folder=sys.argv[1]

output=Path(sys.argv[2])

output.mkdir(
    exist_ok=True
)


alive=set()



for file in Path(folder).rglob("*.txt"):

    for line in file.read_text().splitlines():

        if line.strip():

            alive.add(line.strip())



alive=sorted(alive)



(output/"alive.txt").write_text(
    "\n".join(alive)
)



json.dump(

    [
        {
            "proxy":p
        }

        for p in alive

    ],

    open(
        output/"alive.json",
        "w"
    ),

    indent=2

)



metadata={

    "generated_at":
    datetime.now(timezone.utc).isoformat(),

    "count":
    len(alive),

    "sources":[

        "proxifly/free-proxy-list",

        "hproxy-com/free-proxy-list"

    ],

    "checker":
    "mubeng"

}



json.dump(

    metadata,

    open(
        output/"metadata.json",
        "w"
    ),

    indent=2

)



print(metadata)

