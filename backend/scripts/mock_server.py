#!/usr/bin/env python3
"""Mock 数据源 —— 给成员 B 做前端联调（XQ-011），也用于接口协议冻结验收（XQ-002）。

实现上直接复用 `--sim`：同一份协议、同一份消息格式，只是数据来自剧本而非摄像头。
这样 B 消费的假数据和将来真数据**字段完全一致**，联调时不需要改前端。

    cd backend && python scripts/mock_server.py          # 等价于 python -m xiaoqi --sim
    python scripts/mock_server.py --port 8001            # 多开一个实例
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xiaoqi.main import run  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="小栖 mock 数据源")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--config", default=None)
    a = ap.parse_args()
    run(sim=True, host=a.host, port=a.port, config=a.config)
