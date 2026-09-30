"""Reference sync server + phone client (protocol spec for the Spring Boot / Kotlin versions).

Storage: SQLite (stands in for PostgreSQL; the protocol logic is what is being tested, not the database).
Server duties: store signed records idempotently, detect forks / gaps / replays / revoked devices,
append every accepted record to a hash-chained ledger, issue signed receipts and daily checkpoints.
Phone duty: keep every record until it is covered by a DURABLE checkpoint (one taken after a backup).
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import threading
import time

from cryptography.hazmat.primitives.asymmetric import ec

import record_core as rc

SCHEMA = """
CREATE TABLE IF NOT EXISTS device (id TEXT PRIMARY KEY, pub TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
    revoked_at REAL, last_counter INTEGER NOT NULL DEFAULT 0, head TEXT NOT NULL DEFAULT '%s');
CREATE TABLE IF NOT EXISTS record (hash TEXT PRIMARY KEY, device_id TEXT NOT NULL, counter INTEGER NOT NULL,
    prev TEXT NOT NULL, body TEXT NOT NULL, sig TEXT NOT NULL, received_at REAL NOT NULL, flags TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL DEFAULT '{}', UNIQUE (device_id, counter));
CREATE TABLE IF NOT EXISTS ledger (seq INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL, entry TEXT NOT NULL, prev TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS nonce (device_id TEXT NOT NULL, nonce TEXT NOT NULL, PRIMARY KEY (device_id, nonce));
CREATE TABLE IF NOT EXISTS alert (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, detail TEXT, at REAL);
CREATE TABLE IF NOT EXISTS checkpoint (seq INTEGER PRIMARY KEY, head TEXT NOT NULL, durable INTEGER NOT NULL, sig TEXT NOT NULL);
""" % rc.GENESIS

MAX_BATCH = 500
MAX_ENVELOPE_BYTES = 5_000_000


class Crash(Exception):
    """Injected fault for tests."""


def _record_problem(r):
    """Shape + payload-hash + schema check for one record; None if fine."""
    if not isinstance(r, dict) or not isinstance(r.get("body"), dict) or not isinstance(r.get("sig"), str):
        return "record shape"
    b = r["body"]
    if set(b) != {"device_id", "counter", "prev", "payload_sha256"}:
        return "header fields"
    if not isinstance(b["counter"], int) or isinstance(b["counter"], bool) or b["counter"] < 1:
        return "counter"
    if not all(isinstance(b[k], str) for k in ("device_id", "prev", "payload_sha256")):
        return "header types"
    if not isinstance(r.get("payload"), dict):
        return "payload missing (sync carries full records)"
    try:
        if rc.sha256_hex(rc.canon(r["payload"])) != b["payload_sha256"]:
            return "payload does not match signed header"
        rc.canon(b)
    except ValueError as e:
        return str(e)
    probs = rc.payload_problems(r["payload"])
    return "; ".join(probs) if probs else None


class Server:
    def __init__(self, path=":memory:"):
        self.path = path
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL") if path != ":memory:" else None
        self.db.executescript(SCHEMA)
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.pub = rc.pub_pem(self.key)
        self.lock = threading.Lock()
        self.crash_after = None            # inject: crash after N records inserted in a batch
        self.backup_seq = 0                # highest ledger seq included in the last completed backup

    # ---------------- administration
    def enrol(self, device_id, pub_pem):
        self.db.execute("INSERT INTO device (id, pub) VALUES (?, ?)", (device_id, pub_pem))

    def revoke(self, device_id, reason="revoked"):
        self.db.execute("UPDATE device SET status='revoked', revoked_at=? WHERE id=?", (time.time(), device_id))
        self._alert("revoked", f"{device_id}: {reason}")

    def _alert(self, kind, detail):
        self.db.execute("INSERT INTO alert (kind, detail, at) VALUES (?, ?, ?)", (kind, detail, time.time()))

    def alerts(self):
        return [r[0] for r in self.db.execute("SELECT kind FROM alert")]

    # ---------------- sync
    def sync(self, envelope_json: bytes):
        if len(envelope_json) > MAX_ENVELOPE_BYTES:
            return {"status": "rejected", "reason": "envelope too large"}
        try:
            env = json.loads(envelope_json)
            body, sig = env["body"], env["sig"]
            dev_id, nonce, records = body["device_id"], body["nonce"], body["records"]
            assert isinstance(records, list) and len(records) <= MAX_BATCH
        except Exception:  # noqa: BLE001
            return {"status": "rejected", "reason": "malformed envelope"}
        with self.lock:
            dev = self.db.execute("SELECT pub, status, last_counter, head FROM device WHERE id=?", (dev_id,)).fetchone()
            if dev is None:
                return {"status": "rejected", "reason": "unknown device"}
            pub, status, last_counter, head = dev
            try:
                env_bytes = rc.canon(body)
            except ValueError as e:
                return {"status": "rejected", "reason": f"envelope not canonicalisable: {e}"}
            if not rc.verify_sig(pub, env_bytes, sig):
                return {"status": "rejected", "reason": "bad envelope signature"}
            if status != "active":
                return {"status": "rejected", "reason": "device revoked"}
            if self.db.execute("SELECT 1 FROM nonce WHERE device_id=? AND nonce=?", (dev_id, nonce)).fetchone():
                self._alert("replay", dev_id)
                return {"status": "rejected", "reason": "replayed envelope"}
            results = []
            valid = []
            for i, r in enumerate(records):          # a signed envelope can still carry malformed records
                why = _record_problem(r)
                if why:
                    results.append((f"#{i}", f"rejected:malformed ({why})"))
                else:
                    valid.append(r)
            now_ms = int(time.time() * 1000)
            self.db.execute("BEGIN IMMEDIATE")
            try:
                self.db.execute("INSERT INTO nonce VALUES (?, ?)", (dev_id, nonce))
                inserted = 0
                for r in sorted(valid, key=lambda r: r["body"]["counter"]):
                    b = r["body"]
                    h = rc.sha256_hex(rc.canon(b))
                    if b.get("device_id") != dev_id or not rc.verify_sig(pub, rc.canon(b), r["sig"]):
                        results.append((h, "rejected:bad signature")); continue
                    existing = self.db.execute("SELECT hash FROM record WHERE device_id=? AND counter=?",
                                               (dev_id, b["counter"])).fetchone()
                    if existing and existing[0] == h:
                        results.append((h, "duplicate")); continue
                    if existing:
                        self.db.execute("UPDATE device SET status='frozen' WHERE id=?", (dev_id,))
                        self._alert("fork", f"{dev_id}#{b['counter']}")
                        results.append((h, "rejected:FORK")); continue
                    flags = ""
                    prev_row = self.db.execute("SELECT hash FROM record WHERE device_id=? AND counter=?",
                                               (dev_id, b["counter"] - 1)).fetchone()
                    if b["counter"] > 1 and prev_row is None:
                        flags = "gap-before"
                    elif b["counter"] > 1 and prev_row[0] != b["prev"]:
                        self._alert("chain-mismatch", f"{dev_id}#{b['counter']}")
                        results.append((h, "rejected:chain mismatch")); continue
                    self.db.execute("INSERT INTO record VALUES (?,?,?,?,?,?,?,?,?)",
                                    (h, dev_id, b["counter"], b["prev"], json.dumps(b), r["sig"], now_ms / 1000, flags,
                                     json.dumps(r["payload"])))
                    self._ledger_append(h)
                    inserted += 1
                    if self.crash_after is not None and inserted >= self.crash_after:
                        raise Crash("injected crash mid-batch")
                    results.append((h, "accepted" + (" (gap before)" if flags else "")))
                top = self.db.execute("SELECT MAX(counter) FROM record WHERE device_id=?", (dev_id,)).fetchone()[0] or 0
                self.db.execute("UPDATE device SET last_counter=? WHERE id=?", (top, dev_id))
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                raise
            seq = self.db.execute("SELECT MAX(seq) FROM ledger").fetchone()[0] or 0
            # server countersigns its receive time: an upper bound on when each accepted record existed
            receipt = {"device_id": dev_id, "results": results, "ledger_seq": seq, "server_time_ms": now_ms}
            return {"status": "ok", "receipt": receipt, "receipt_sig": rc.sign(self.key, rc.canon(receipt)),
                    "checkpoint": self.latest_checkpoint()}

    def _ledger_append(self, ref):
        last = self.db.execute("SELECT entry FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
        prev = last[0] if last else rc.GENESIS
        entry = rc.sha256_hex((prev + ref).encode())
        self.db.execute("INSERT INTO ledger (ref, entry, prev) VALUES (?, ?, ?)", (ref, entry, prev))

    # ---------------- searchable log (server side; PostgreSQL uses the same filters on JSONB)
    def search(self, crime_no=None, operation_id=None, package=None, outcome=None, kit_batch=None,
               officer_id=None, date_from_ms=None, date_to_ms=None, limit=100):
        where, args = [], []
        for col, val in (("crime_no", crime_no), ("operation_id", operation_id), ("package", package),
                         ("outcome", outcome), ("kit_batch", kit_batch), ("officer_id", officer_id)):
            if val is not None:
                where.append(f"json_extract(payload, '$.{col}') = ?"); args.append(val)
        if date_from_ms is not None:
            where.append("json_extract(payload, '$.device_time_ms') >= ?"); args.append(date_from_ms)
        if date_to_ms is not None:
            where.append("json_extract(payload, '$.device_time_ms') <= ?"); args.append(date_to_ms)
        sql = ("SELECT hash, device_id, counter, payload FROM record" + (" WHERE " + " AND ".join(where) if where else "")
               + " ORDER BY json_extract(payload, '$.device_time_ms'), device_id, counter LIMIT ?")
        return [{"hash": h, "device_id": d, "counter": c, **json.loads(p)}
                for h, d, c, p in self.db.execute(sql, (*args, limit))]

    # ---------------- checkpoints and backups
    def backup(self, dst_path):
        dst = sqlite3.connect(dst_path)
        with self.lock:
            self.db.backup(dst)
            self.backup_seq = self.db.execute("SELECT MAX(seq) FROM ledger").fetchone()[0] or 0
        dst.close()

    def make_checkpoint(self):
        with self.lock:
            row = self.db.execute("SELECT seq, entry FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
            if not row:
                return None
            seq, head = row
            durable = int(seq <= self.backup_seq)
            body = {"seq": seq, "head": head, "durable": durable}
            self.db.execute("INSERT OR REPLACE INTO checkpoint VALUES (?, ?, ?, ?)",
                            (seq, head, durable, rc.sign(self.key, rc.canon(body))))
            return body

    def latest_checkpoint(self):
        row = self.db.execute("SELECT seq, head, durable FROM checkpoint ORDER BY seq DESC LIMIT 1").fetchone()
        return {"seq": row[0], "head": row[1], "durable": row[2]} if row else None

    def audit_against(self, checkpoint):
        """Recompute the ledger chain up to a checkpoint held OUTSIDE the server (e.g. on a phone)."""
        prev = rc.GENESIS
        for seq, ref, entry, p in self.db.execute("SELECT seq, ref, entry, prev FROM ledger ORDER BY seq"):
            if p != prev or rc.sha256_hex((prev + ref).encode()) != entry:
                return False
            if not self.db.execute("SELECT 1 FROM record WHERE hash=?", (ref,)).fetchone():
                return False                                   # a ledgered record row was deleted
            prev = entry
            if seq == checkpoint["seq"]:
                return entry == checkpoint["head"]
        return False                                          # ledger shorter than the checkpoint

    @classmethod
    def restore(cls, backup_path, key):
        s = cls.__new__(cls)
        s.path = backup_path
        s.db = sqlite3.connect(backup_path, check_same_thread=False, isolation_level=None)
        s.key, s.pub, s.lock, s.crash_after = key, rc.pub_pem(key), threading.Lock(), None
        s.backup_seq = s.db.execute("SELECT MAX(seq) FROM ledger").fetchone()[0] or 0
        return s


class Phone:
    """Holds records until a DURABLE checkpoint covers them; retries safely."""

    def __init__(self, device: rc.Device, delete_on="durable", officer_id="OFF-1", operation_id="OP-1"):
        self.device = device
        self.officer_id, self.operation_id = officer_id, operation_id
        self.unconfirmed = {}                 # record hash -> record
        self.ledger_seq_of = {}               # record hash -> server ledger seq (from receipt)
        self.checkpoints = []                 # copies of server checkpoints (outside-the-server witnesses)
        self.delete_on = delete_on            # "durable" (correct) or "any" (naive, for comparison)

    def payload(self, fields):
        """A valid test payload: defaults for operation/officer/time/location, overridden by `fields`."""
        f = dict(fields)
        return rc.test_payload(f.pop("operation_id", self.operation_id), f.pop("package", "P-1"),
                               f.pop("officer_id", self.officer_id), f.pop("device_time_ms", int(time.time() * 1000)),
                               f.pop("location", rc.LOCATION_UNAVAILABLE), **f)

    def record(self, fields, image_bytes=None):
        rec = self.device.append("test", self.payload(fields),
                                 image_bytes if image_bytes is not None else os.urandom(16))
        self.unconfirmed[rc.sha256_hex(rc.canon(rec["body"]))] = rec
        return rec

    def envelope(self, records, nonce=None):
        body = {"device_id": self.device.device_id, "nonce": nonce or base64.b64encode(os.urandom(12)).decode(),
                "records": records}
        return json.dumps({"body": body, "sig": rc.sign(self.device.key, rc.canon(body))}).encode()

    def sync(self, server, network_ok=True):
        if not self.unconfirmed:
            return "nothing to send"
        if not network_ok:
            return "network down: kept locally"
        resp = server.sync(self.envelope(list(self.unconfirmed.values())))
        if resp["status"] != "ok":
            return resp["reason"]
        seq = resp["receipt"]["ledger_seq"]
        for h, st in resp["receipt"]["results"]:
            if st.startswith("accepted") or st == "duplicate":
                self.ledger_seq_of.setdefault(h, seq)
        cp = resp.get("checkpoint")
        if cp:
            self.checkpoints.append(cp)
            if cp["durable"] or self.delete_on == "any":
                for h in [h for h, s in self.ledger_seq_of.items() if s <= cp["seq"] and h in self.unconfirmed]:
                    del self.unconfirmed[h]
        return "ok"
