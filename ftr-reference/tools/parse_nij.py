"""Parse NIJ Standard-0604.01 Table 1 (final colours) into docs/research/data/nij0604_table1.csv.

Handles: 4-digit ISCC codes where the last digit is a phase footnote (e.g. Duquenois-Levine "2041" =
ISCC 204, footnote 1 = aqueous phase), continuation lines listing further phases for the same analyte,
"to" ranges, and "Black". Source text: docs/sources/NIJ_Standard_0604_01_extracted.txt.
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs/sources/NIJ_Standard_0604_01_extracted.txt"
OUT = Path(__file__).resolve().parents[1] / "docs/research/data/nij0604_table1.csv"

NAMES = {1: "Cobalt thiocyanate", 2: "Dille-Koppanyi (modified)", 3: "Duquenois-Levine (modified)", 4: "Mandelin",
         5: "Marquis", 6: "Nitric acid", 7: "p-DMAB", 8: "Ferric chloride", 9: "Froede", 10: "Mecke",
         11: "Zwikker", 12: "Simon's"}
PHASES = {"1": "aqueous", "2": "aqueous after chloroform extraction", "3": "chloroform", "4": "not extracted", "5": ""}
MUNSELL = r"((?:\d+(?:\.\d+)?(?:R|YR|Y|GY|G|BG|B|PB|P|RP) \d+(?:\.\d+)?/\d+)|(?:N ?\d+(?:\.\d+)?/?)|Black)"
FORMS = ("CHCl3", "Powder", "powder", "crystals", "leaves", "H2O", "EtOH", "extract")
row_rx = re.compile(r"^A\.(\d+) (.+?) (\d{1,4})(?: to)? ([A-Z][a-z].*?) " + MUNSELL + r"(?: to)?\s*$")
cont_rx = re.compile(r"^(\d{1,4}) ([A-Z][a-z].*?) " + MUNSELL + r"\s*$")


def split_iscc(code, reagent):
    """Duquenois-Levine codes carry a trailing phase footnote digit."""
    if reagent == 3 and len(code) == 4:
        return code[:3], PHASES.get(code[3], code[3])
    return code, ""


def main():
    lines = SRC.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("Table 1."))
    end = next(i for i, l in enumerate(lines) if "APPENDIX A" in l and i > start)
    rows, last = [], None
    for raw in lines[start:end]:
        line = raw.strip()
        m = row_rx.match(line)
        if m:
            rid, rest, code, cname, mun = int(m.group(1)), m.group(2), m.group(3), m.group(4), m.group(5)
            parts = rest.rsplit(" ", 1)
            analyte, form = (parts[0], parts[1]) if len(parts) == 2 and parts[1] in FORMS else (rest, "")
            iscc, phase = split_iscc(code, rid)
            last = (rid, analyte.replace("*", "").strip(), form)
            rows.append([rid, NAMES[rid], last[1], form, phase, iscc, cname.strip(), mun])
            continue
        c = cont_rx.match(line)
        if c and last:
            iscc, phase = split_iscc(c.group(1), last[0])
            rows.append([last[0], NAMES[last[0]], last[1], last[2], phase, iscc, c.group(2).strip(), c.group(3)])
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["reagent_no", "reagent", "analyte", "form", "phase", "iscc_nist_no", "colour_name", "munsell"])
        w.writerows(rows)
    from collections import Counter
    print(len(rows), "rows:", dict(sorted(Counter(r[1] for r in rows).items())))


if __name__ == "__main__":
    main()
