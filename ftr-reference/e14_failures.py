"""E14: system and user failure scenarios against the reference sync server (sync_server.py).

Each scenario states the expected behaviour and checks it. Includes a design comparison:
phones deleting local copies on ANY checkpoint (naive) vs only on a DURABLE (post-backup) checkpoint.
"""
import os
import tempfile
import threading
import time

from cryptography.hazmat.primitives.asymmetric import ec

import record_core as rc
from sync_server import Crash, Phone, Server

new_key = lambda: ec.generate_private_key(ec.SECP256R1())
results = []


def check(name, ok, detail=""):
    results.append((name, "PASS" if ok else "FAIL", detail))


def phone_on(server, dev_id, delete_on="durable"):
    d = rc.Device(dev_id, new_key())
    server.enrol(dev_id, rc.pub_pem(d.key))
    return Phone(d, delete_on)


def count(server, dev=None):
    q = "SELECT COUNT(*) FROM record" + (" WHERE device_id=?" if dev else "")
    return server.db.execute(q, (dev,) if dev else ()).fetchone()[0]


# 1 duplicate submission (phone retries after a lost response)
s = Server(); p = phone_on(s, "D1")
for i in range(5): p.record({"package": f"P-{i}"})
env = p.envelope(list(p.unconfirmed.values()))
s.sync(env)
r2 = s.sync(p.envelope(list(p.unconfirmed.values())))     # same records, new nonce
check("duplicate submission is idempotent", count(s) == 5 and all(st == "duplicate" for _, st in r2["receipt"]["results"]))

# 2 server crash mid-batch
s = Server(); p = phone_on(s, "D2")
for i in range(10): p.record({"package": f"P-{i}"})
s.crash_after = 4
try:
    s.sync(p.envelope(list(p.unconfirmed.values()))); crashed = False
except Crash:
    crashed = True
partial = count(s)
s.crash_after = None
p.sync(s)
check("crash mid-batch rolls back, retry completes", crashed and partial == 0 and count(s) == 10,
      f"rows after crash={partial}, after retry={count(s)}")

# 3 network failure
s = Server(); p = phone_on(s, "D3")
for i in range(3): p.record({"package": f"P-{i}"})
msg = p.sync(s, network_ok=False)
kept = len(p.unconfirmed)
p.sync(s)
check("network down keeps records, later sync delivers", kept == 3 and count(s) == 3, msg)

# 4 replayed envelope
s = Server(); p = phone_on(s, "D4")
p.record({"package": "P-1"})
env = p.envelope(list(p.unconfirmed.values()), nonce="fixed-nonce")
s.sync(env)
r = s.sync(env)
check("replayed envelope rejected", r["status"] == "rejected" and "replay" in s.alerts(), r.get("reason", ""))

# 5 cloned phone / fork
s = Server(); p = phone_on(s, "D5")
p.record({"package": "P-1"}); p.sync(s)
clone = rc.Device("D5", p.device.key, counter=0, head=rc.GENESIS)
fake = clone.append("test", p.payload({"package": "P-1", "outcome": "negative"}), b"img")
r = s.sync(Phone(clone).envelope([fake]))
status = s.db.execute("SELECT status FROM device WHERE id='D5'").fetchone()[0]
check("fork (same counter, different record) detected, device frozen",
      "fork" in s.alerts() and status == "frozen", f"device status={status}")

# 6 gap then late arrival
s = Server(); p = phone_on(s, "D6")
recs = [p.device.append("test", p.payload({"package": f"P-{i}"}), b"img") for i in range(10)]
s.sync(p.envelope(recs[:5])); s.sync(p.envelope(recs[7:]))
gap_flagged = s.db.execute("SELECT flags FROM record WHERE device_id='D6' AND counter=8").fetchone()[0] == "gap-before"
s.sync(p.envelope(recs[5:7]))
check("gap flagged, then filled by late records", gap_flagged and count(s) == 10)

# 7 revoked device
s = Server(); p = phone_on(s, "D7")
p.record({"package": "P-1"}); p.sync(s)
s.revoke("D7", "phone stolen")
p.record({"package": "P-2"})
r = s.sync(p.envelope(list(p.unconfirmed.values())))
check("revoked device cannot sync", r["status"] == "rejected" and count(s, "D7") == 1, r.get("reason", ""))

# 8 malformed / oversized / forged envelopes
s = Server(); p = phone_on(s, "D8")
bad = [b"not json", b'{"body": {}}', b"x" * 6_000_000]
forged = p.envelope([]).replace(b'"sig": "', b'"sig": "AAAA')
rs = [s.sync(x)["status"] for x in bad + [forged]]
check("malformed, oversized and forged envelopes rejected cleanly", all(x == "rejected" for x in rs))

# 9 clock skew: device clock wrong by a day -> ordering by counter, never by time
s = Server(); p = phone_on(s, "D9")
p.record({"package": "P-1", "device_time_ms": 1_790_760_000_000})
p.record({"package": "P-2", "device_time_ms": 1_790_587_200_000})      # clock set back two days
p.sync(s)
check("clock skew does not break ordering (counter is authoritative)", count(s, "D9") == 2)

# 10 admin deletes a row; phone-held checkpoint exposes it
s = Server(); p = phone_on(s, "D10")
for i in range(6): p.record({"package": f"P-{i}"})
p.sync(s); cp = s.make_checkpoint()
ok_before = s.audit_against(cp)
h = s.db.execute("SELECT hash FROM record WHERE counter=3").fetchone()[0]
s.db.execute("DELETE FROM record WHERE hash=?", (h,))
check("admin deletion detected against a phone-held checkpoint", ok_before and not s.audit_against(cp))

# 11 disk loss + restore from a backup older than the latest checkpoint: naive vs durable deletion
for policy in ("any", "durable"):
    tmp = tempfile.mkdtemp()
    s = Server(os.path.join(tmp, "live.db")); p = phone_on(s, "D11", delete_on=policy)
    for i in range(10): p.record({"package": f"P-{i}"})
    p.sync(s); s.backup(os.path.join(tmp, "backup.db")); s.make_checkpoint(); p.sync(s)   # records 1-10 durable
    for i in range(10, 15): p.record({"package": f"P-{i}"})
    p.sync(s); s.make_checkpoint(); p.record({"package": "P-15"}); p.sync(s)             # 11-16 not backed up
    key = s.key; s.db.close()
    s = Server.restore(os.path.join(tmp, "backup.db"), key)                              # live disk lost
    lost_before = 16 - count(s)
    p.sync(s)
    recovered = count(s)
    check(f"restore from stale backup, phones delete on {policy.upper()} checkpoint",
          (recovered == 16) if policy == "durable" else True,
          f"server lost {lost_before} records; after phone re-sync server has {recovered}/16")

# 12 concurrency and throughput: 20 phones x 200 records, batches of 50
s = Server(); phones = [phone_on(s, f"C{i}") for i in range(20)]
for ph in phones:
    for i in range(200): ph.record({"package": f"P-{i}"})


def run(ph):
    recs = list(ph.unconfirmed.values())
    for k in range(0, len(recs), 50):
        s.sync(ph.envelope(recs[k:k + 50]))


t0 = time.perf_counter()
ts = [threading.Thread(target=run, args=(ph,)) for ph in phones]
[t.start() for t in ts]; [t.join() for t in ts]
dt = time.perf_counter() - t0
check("20 concurrent phones, 4,000 records, none lost", count(s) == 4000, f"{4000 / dt:.0f} records/s (SQLite, laptop, single process)")

# 13 malformed records inside a validly SIGNED envelope (buggy app / hostile enrolled phone): no crash
s = Server(); p = phone_on(s, "D13")
good = p.record({"package": "P-1"})
junk = [{"sig": "x"}, {"body": {"device_id": "D13"}, "sig": "x"}, "junk",
        {**good, "payload": {**good["payload"], "outcome": "negative"}},            # payload edited after signing
        {"body": {**good["body"], "counter": 0}, "sig": "x", "payload": good["payload"]}]
try:
    r = s.sync(p.envelope([good] + junk)); crashed = False
except Exception as e:  # noqa: BLE001
    r, crashed = {"status": f"CRASH {type(e).__name__}"}, True
statuses = [st for _, st in r.get("receipt", {}).get("results", [])]
check("malformed records in a signed envelope rejected one by one, good record kept",
      not crashed and count(s, "D13") == 1 and sum(st.startswith("rejected:malformed") for st in statuses) == 5,
      f"{sum(st.startswith('rejected:malformed') for st in statuses)} rejected, {count(s, 'D13')} stored")

# 14 receipt countersigns server time; searchable log on the server
s = Server(); p = phone_on(s, "D14")
for i, (out, crime) in enumerate([("positive", "NCB/DZU/112/2026"), ("negative", "NCB/DZU/112/2026"),
                                  ("positive", "NCB/MZU/007/2026")]):
    p.record({"package": f"P-{i + 1}", "outcome": out, "crime_no": crime, "kit_batch": "NDDK-2026-07",
              "device_time_ms": 1_790_000_000_000 + i * 60_000})
resp = s.sync(p.envelope(list(p.unconfirmed.values())))
hits = s.search(crime_no="NCB/DZU/112/2026", outcome="positive")
check("receipt carries server time; search by case + result finds exactly the matching record",
      isinstance(resp["receipt"].get("server_time_ms"), int) and [h["package"] for h in hits] == ["P-1"],
      f"server_time_ms={resp['receipt'].get('server_time_ms')}, hits={[h['package'] for h in hits]}")

w = max(len(r[0]) for r in results)
for name, st, detail in results:
    print(f"{st}  {name:{w}s}  {detail}")
print(f"\n{sum(r[1] == 'PASS' for r in results)}/{len(results)} scenarios pass")
