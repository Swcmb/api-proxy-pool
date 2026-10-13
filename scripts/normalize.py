import csv
import sys


csv_file=sys.argv[1]
proxy_file=sys.argv[2]
output=sys.argv[3]


proxies=set()



with open(csv_file,encoding="utf8") as f:

    reader=csv.DictReader(f)

    for row in reader:

        if row.get("alive")=="true":

            protocols=row["protocols"].split(",")

            for p in protocols:

                proxies.add(
                    f"{p.strip()}://{row['ip']}:{row['port']}"
                )



with open(proxy_file,encoding="utf8") as f:

    for line in f:

        line=line.strip()

        if line:

            proxies.add(line)



with open(output,"w") as f:

    for p in sorted(proxies):

        f.write(p+"\n")



print(
    "proxy count:",
    len(proxies)
)
