"""SQLite 持久化：状态事件与步数（M2-3/M2-6 要的原始数据，人机课报告靠它）。"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from ..hub import now_ms

# 协议 §4.1 samples 收纳的事件类型（error / reminder 不是样本）
SAMPLE_KINDS = ("state", "behavior", "phone")

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

    def query_snapshots(self, from_ms: int | None, to_ms: int | None,
                        kind: str | None = None,
                        limit: int = 5000) -> list[dict]:
        """`GET /api/history` 用：按 `接口协议.md` §4.1 输出 `samples`。

        字段来源（协议 §3.1 的顶层三块）：
          `pose.state`                  → `pose_state`
          `pose.metrics.neck_angle_deg` → `neck_angle_deg`
          `behavior.active_app`         → `behavior_app`
          `behavior.level`              → `behavior_level`
          `phone.steps`                 → `steps`

        v0.1 **不做时间聚合**：库里姿态 / 行为 / 步数是分开的行
        （`kind` = `state` / `behavior` / `phone`），本方法逐行原样映射、
        缺测填 `null`（协议 §4.1「缺测字段用 `null`」）。
        消费方（M2 报告）按 `ts` 就近合并；「一行完整快照」所需的聚合窗口
        大小属产品决策，未定，故不在此实现。
        """
        sql = ("SELECT ts,kind,state,metrics,payload FROM events"
               " WHERE ts >= ? AND ts <= ?")
        args: list = [from_ms or 0, to_ms or now_ms()]
        if kind:
            sql += " AND kind = ?"            # 本站扩展：按事件类型过滤
            args.append(kind)
        else:
            sql += " AND kind IN (?,?,?)"
            args.extend(SAMPLE_KINDS)
        sql += " ORDER BY ts DESC LIMIT ?"    # 先取「最近 N 条」
        args.append(max(1, min(limit, 20000)))
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()

        samples: list[dict] = []
        for ts, k, state, metrics_txt, payload_txt in rows:
            payload = json.loads(payload_txt or "{}")
            metrics = json.loads(metrics_txt or "{}")
            behavior = payload.get("behavior") or {}
            phone = payload.get("phone") or {}
            is_pose = k == "state"
            samples.append({
                "ts": ts,
                "pose_state": state if is_pose else None,
                "neck_angle_deg": (metrics.get("neck_angle_deg")
                                   if is_pose else None),
                "behavior_app": behavior.get("active_app"),
                "behavior_level": behavior.get("level"),
                "steps": phone.get("steps"),
            })
        samples.reverse()                     # 协议 §4.1：对外按 ts 升序
        return samples

    def close(self) -> None:
        with self._lock:
            self._conn.close()
