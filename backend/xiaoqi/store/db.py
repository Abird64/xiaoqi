"""SQLite 持久化：状态事件与步数（M2-3/M2-6 要的原始数据，人机课报告靠它）。"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from ..hub import now_ms

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  ts        INTEGER NOT NULL,
  kind      TEXT    NOT NULL,
  state     TEXT,
  confidence REAL,
  metrics   TEXT,
  payload   TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE TABLE IF NOT EXISTS steps (
  day   TEXT PRIMARY KEY,
  steps INTEGER NOT NULL,
  ts    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
"""


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def write_event(self, event: dict) -> None:
        pose = event.get("pose") or {}
        with self._lock:
            self._conn.execute(
                "INSERT INTO events(ts,kind,state,confidence,metrics,payload)"
                " VALUES(?,?,?,?,?,?)",
                (event.get("ts", now_ms()), event.get("type", ""),
                 pose.get("state"), pose.get("confidence"),
                 json.dumps(pose.get("metrics") or {}, ensure_ascii=False),
                 json.dumps(event, ensure_ascii=False)),
            )
            if event.get("type") == "state" and "phone" in event:
                steps = (event.get("phone") or {}).get("steps")
                if isinstance(steps, int):
                    day = time.strftime("%Y-%m-%d")
                    self._conn.execute(
                        "INSERT INTO steps(day,steps,ts) VALUES(?,?,?)"
                        " ON CONFLICT(day) DO UPDATE SET steps=excluded.steps,"
                        " ts=excluded.ts",
                        (day, steps, event.get("ts", now_ms())),
                    )
                    # 另记一行 kind='phone'，否则 GET /api/history?kind=phone 查不到
                    self._conn.execute(
                        "INSERT INTO events(ts,kind,state,confidence,metrics,payload)"
                        " VALUES(?,?,?,?,?,?)",
                        (event.get("ts", now_ms()), "phone", None, None, "{}",
                         json.dumps(event, ensure_ascii=False)),
                    )
            self._conn.commit()

    def query(self, from_ms: int | None, to_ms: int | None,
              kind: str | None = None, limit: int = 5000) -> list[dict]:
        sql = ("SELECT ts,kind,state,confidence,metrics,payload FROM events"
               " WHERE ts >= ? AND ts <= ?")
        args: list = [from_ms or 0, to_ms or now_ms()]
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        sql += " ORDER BY ts DESC LIMIT ?"
        args.append(max(1, min(limit, 20000)))
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [
            {"ts": r[0], "kind": r[1], "state": r[2], "confidence": r[3],
             "metrics": json.loads(r[4] or "{}"), "payload": json.loads(r[5] or "{}")}
            for r in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
