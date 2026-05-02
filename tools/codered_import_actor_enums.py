from pathlib import Path
import csv
import re

ENUMS_H = Path(r"D:\Games\Red Dead Redemption\game\BACKUP BEFORE MODDING\2025\Next\Enums.h")
OUT_CSV = Path(r"D:\Games\Red Dead Redemption\RDR-SteamGG.NET\data\codered\actor_enum_map.csv")

enum_start = re.compile(r"enum\s+e_ActorModel\s*:\s*int")
entry_re = re.compile(r"^\s*(ACTOR_[A-Za-z0-9_]+)\s*(?:=\s*(-?\d+))?\s*,?")

def make_aliases(name: str) -> list[str]:
    aliases = [name]

    # Common readable lowercase forms.
    aliases.append(name.lower())

    # Remove ACTOR_ prefix.
    if name.startswith("ACTOR_"):
        short = name[len("ACTOR_"):]
        aliases.append(short)
        aliases.append(short.lower())

        # Your older roster used AE_ names sometimes.
        aliases.append("AE_" + short)
        aliases.append("AE_" + short.lower())

    return list(dict.fromkeys(aliases))

inside = False
value = -1
rows = []

for raw in ENUMS_H.read_text(encoding="utf-8", errors="ignore").splitlines():
    line = raw.split("//", 1)[0].strip()

    if not inside:
        if enum_start.search(line):
            inside = True
        continue

    if line.startswith("};"):
        break

    m = entry_re.match(line)
    if not m:
        continue

    name, explicit = m.groups()

    if explicit is not None:
        value = int(explicit)
    else:
        value += 1

    for alias in make_aliases(name):
        rows.append({
            "label": alias,
            "actor_enum": value,
            "source": "Enums.h:e_ActorModel",
            "canonical": name,
            "status": "candidate"
        })

OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["label", "actor_enum", "source", "canonical", "status"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {len(rows)} actor enum aliases to {OUT_CSV}")