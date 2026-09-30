"""Searchable on-device log: offline search by case, package, result, kit batch, date, substance, place;
opening a record re-verifies it; tampered records are refused at indexing and flagged at opening."""
import copy

from cryptography.hazmat.primitives.asymmetric import ec

import record_core as rc
from record_log import RecordLog

dev = rc.Device("DEV-1", ec.generate_private_key(ec.SECP256R1()))
log = RecordLog(rc.pub_pem(dev.key))
T = 1_790_000_000_000
rows = [("NCB/DZU/112/2026", "P-1", "positive", ["Morphine", "Codeine", "Heroin"], "Paharganj godown", 0),
        ("NCB/DZU/112/2026", "P-2", "negative", [], "Paharganj godown", 1),
        ("NCB/MZU/007/2026", "P-1", "inconclusive", ["Amphetamine", "Methamphetamine"], "Andheri East", 30)]
for crime, pkg, out, subs, place, day in rows:
    rec = dev.append("test", rc.test_payload(f"OP-{crime[-8:-5]}", pkg, "OFF-1", T + day * 86_400_000,
                                             rc.location_fix(28.6, 77.2, 5), crime_no=crime, outcome=out,
                                             consistent_with=subs, place_note=place, kit_batch="NDDK-2026-07"),
                     image_bytes=f"{crime}{pkg}".encode())
    assert log.add(rec)

checks = []
def check(name, got, want):
    checks.append((name, got == want, got))

check("free text: case number", [r["package"] for r in log.search("NCB/DZU/112/2026")], ["P-1", "P-2"])
check("free text: substance", [r["crime_no"] for r in log.search("heroin")], ["NCB/DZU/112/2026"])
check("free text: place, two words", [r["package"] for r in log.search("Andheri East")], ["P-1"])
check("filter: outcome", [r["package"] for r in log.search(outcome="negative")], ["P-2"])
check("filter: date range", len(log.search(date_from_ms=T + 10 * 86_400_000)), 1)
check("text + filter", [r["package"] for r in log.search("Paharganj", outcome="positive")], ["P-1"])
h = log.search(outcome="positive")[0]["hash"]
check("open re-verifies", log.open(h)["verified"], True)
bad = copy.deepcopy(dev.records[0]); bad["payload"]["outcome"] = "negative"
check("tampered record refused at indexing", log.add(bad), False)
log.db.execute("UPDATE rec SET payload = replace(payload, 'positive', 'negative') WHERE hash = ?", (h,))
check("record edited inside the log database is flagged when opened", log.open(h)["verified"], False)
check("query with FTS operators is treated literally", log.search('heroin" OR "x'), [])

for name, ok, got in checks:
    print(f"{'PASS' if ok else 'FAIL'}  {name:58s} {got if not ok else ''}")
print(f"\n{sum(ok for _, ok, _ in checks)}/{len(checks)} log checks pass")
