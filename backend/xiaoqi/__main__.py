"""`python -m xiaoqi` —— D-007：一条命令起全部（后端 + WS + 手机接入 + 前端静态）。"""
from __future__ import annotations

import argparse
import logging


def main() -> None:
    p = argparse.ArgumentParser(prog="xiaoqi", description="小栖 · 健康陪伴后端")
    p.add_argument("--sim", action="store_true",
                   help="模拟链路：无摄像头也能跑通（B 联调 / 演示兜底）")
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--config", default=None, help="配置文件路径（默认 backend/config.yaml）")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    from .main import run
    run(sim=args.sim, host=args.host, port=args.port, config=args.config)


if __name__ == "__main__":
    main()
