"""On-device searchable log of tests (SIH26231: "a simple, searchable log of tests").

Reference for the Android log (Room + SQLCipher with FTS). Works offline. Every record is verified before it
is indexed, and opening a record re-verifies its signature, payload hash and schema on the spot.
Search: free text (crime number, operation, package, outcome, substances, place note, officer) plus filters
(outcome, kit batch, date range).
"""
from __future__ import annotations

import json
import sqlite3

import record_core as rc

SCHEMA = """
CREATE TABLE IF NOT EXISTS rec (hash TEXT PRIMARY KEY, device_id TEXT, counter INTEGER, body TEXT, sig TEXT, payload TEXT,
    outcome TEXT, kit_batch TEXT, device_time_ms INTEGER);
CREATE VIRTUAL TABLE IF NOT EXISTS rec_fts USING fts5(hash UNINDEXED, text);
"""


def _text(p: dict) -> str:
    parts = [p.get(k, "") for k in ("crime_no", "operation_id", "package", "outcome", "reason", "kit_batch",
                                     "place_note", "officer_id", "profile")]
    parts += p.get("consistent_with", [])
    return " ".join(str(x) for x in parts if x)


class RecordLog:
    def __init__(self, device_pub_pem: str, path=":memory:"):
        self.pub = device_pub_pem
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def add(self, rec: dict) -> bool:
        if not rc.verify_record(rec, self.pub):
            return False
        h = rc.sha256_hex(rc.canon(rec["body"]))
        p = rec["payload"]
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO rec VALUES (?,?,?,?,?,?,?,?,?)",
                            (h, rec["body"]["device_id"], rec["body"]["counter"], json.dumps(rec["body"]), rec["sig"],
                             json.dumps(p), p.get("outcome"), p.get("kit_batch"), p.get("device_time_ms")))
            if not self.db.execute("SELECT 1 FROM rec_fts WHERE hash=?", (h,)).fetchone():
                self.db.execute("INSERT INTO rec_fts VALUES (?, ?)", (h, _text(p)))
        return True

    def search(self, text: str | None = None, outcome=None, kit_batch=None, date_from_ms=None, date_to_ms=None,
               limit=100) -> list[dict]:
        sql, args = "SELECT r.hash, r.payload FROM rec r", []
        where = []
        if text:
            sql += " JOIN rec_fts f ON f.hash = r.hash"
            where.append("rec_fts MATCH ?")
            args.append(" ".join('"' + t.replace('"', '""') + '"' for t in text.split()))   # literal tokens, AND-ed
        for col, val in (("outcome", outcome), ("kit_batch", kit_batch)):
            if val is not None:
                where.append(f"r.{col} = ?"); args.append(val)
        if date_from_ms is not None:
            where.append("r.device_time_ms >= ?"); args.append(date_from_ms)
        if date_to_ms is not None:
            where.append("r.device_time_ms <= ?"); args.append(date_to_ms)
        sql += (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY r.device_time_ms LIMIT ?"
        return [{"hash": h, **json.loads(p)} for h, p in self.db.execute(sql, (*args, limit))]

    def open(self, h: str) -> dict:
        row = self.db.execute("SELECT body, sig, payload FROM rec WHERE hash=?", (h,)).fetchone()
        if row is None:
            return {"found": False}
        rec = {"body": json.loads(row[0]), "sig": row[1], "payload": json.loads(row[2])}
        return {"found": True, "verified": rc.verify_record(rec, self.pub), "record": rec}
