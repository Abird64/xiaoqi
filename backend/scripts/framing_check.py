#!/usr/bin/env python3
"""摄像头摆位自检：告诉你"为什么检测不到人，该往哪调"。

    cd backend
    python scripts/framing_check.py                  # 实时看 20 秒
    python scripts/framing_check.py --seconds 40     # 看更久
    python scripts/framing_check.py --snapshot 拍一张.png

背景：MediaPipe 的 BlazePose 要靠「耳—肩—髋」的几何关系算头前倾角。
只拍到脸（肩膀在画面外）时会检出一堆荒谬数值：置信度接近 0、
shoulder_tilt_deg 变成 170° 左右、neck_angle_deg 随机。这不是模型坏了，
是**构图不合格**。本工具把判据摊开，让你按提示挪摄像头。

判据（坐姿上半身照）：
  合格：耳 y∈[0.15,0.55]  肩可见(v>0.5)且 y∈[0.25,0.85]
  理想：髋点也能看到，neck_angle 才稳
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xiaoqi.config import load_config                  # noqa: E402
from xiaoqi.rules.posture_rules import compute_metrics  # noqa: E402
from xiaoqi.vision.pose_estimator import PoseEstimator  # noqa: E402

NOSE, EAR_L, EAR_R, SH_L, SH_R, HIP_L, HIP_R = 0, 7, 8, 11, 12, 23, 24


def judge(obs) -> tuple[str, list[str]]:
    """返回 (等级, 建议列表)。等级：OK / WARN / BAD。"""
    if not obs.person_present or not obs.landmarks or len(obs.landmarks) < 25:
        return "BAD", ["画面里没检测到人：请坐正、让上半身进入画面"]

    lm = obs.landmarks
    tips: list[str] = []
    bad = False

    ear_y = (lm[EAR_L][1] + lm[EAR_R][1]) / 2
    sh_vis = min(lm[SH_L][3], lm[SH_R][3])
    sh_y = (lm[SH_L][1] + lm[SH_R][1]) / 2
    hip_vis = min(lm[HIP_L][3], lm[HIP_R][3])

    if ear_y < 0.10:
        bad = True
        tips.append("头太靠上（快被切了）→ 摄像头往上抬一点，或人往后退")
    elif ear_y > 0.60:
        bad = True
        tips.append("头太靠下（拍到大半天花板）→ 摄像头往下压，对准胸口方向")
    elif not (0.15 <= ear_y <= 0.55):
        tips.append(f"头部高度略偏（耳 y={ear_y:.2f}，理想 0.15~0.55）")

    if sh_vis < 0.5:
        bad = True
        tips.append(f"肩部不可见（visibility={sh_vis:.2f}）→ 这是检测不准的主因，"
                    "摄像头再往下压约 15~30°，让肩膀进画面")
    elif not (0.25 <= sh_y <= 0.85):
        tips.append(f"肩线位置偏差（y={sh_y:.2f}）→ 前后挪一下摄像头")

    if hip_vis < 0.5:
        tips.append("髋部不可见（不影响能否检测，但跨镜头比对时头前倾角会更稳）")

    if bad:
        return "BAD", tips
    return ("OK", tips) if not tips else ("WARN", tips)


def main() -> int:
    ap = argparse.ArgumentParser(description="小栖 · 摄像头摆位自检")
    ap.add_argument("--config", default=None)
    ap.add_argument("--index", type=int, default=None, help="摄像头编号（默认取 config.yaml）")
    ap.add_argument("--seconds", type=float, default=20.0, help="运行多久后自动退出")
    ap.add_argument("--interval", type=float, default=2.0, help="每几秒报一次")
    ap.add_argument("--snapshot", default=None, help="顺带存一张画面到这个路径")
    args = ap.parse_args()

    try:
        import cv2
    except Exception as e:
        print(f"❌ 需要 opencv-python：{e}", file=sys.stderr)
        return 1

    cfg = load_config(args.config)
    idx = cfg.camera_index if args.index is None else args.index

    est = PoseEstimator(cfg)
    if not est.ok:
        print("❌ 姿态估计不可用：\n" + (est.last_error or "原因未知"), file=sys.stderr)
        return 1

    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        print(f"❌ 摄像头 {idx} 打不开：换 --index 试别的编号，或检查是否被其它程序占用",
              file=sys.stderr)
        return 1

    print(f"摄像头 #{idx} 已打开，连续采样 {args.seconds:.0f} 秒（每 {args.interval:.0f}s 报一次）")
    print("调整时看每行的【等级】和【建议】，目标是连续出现 OK。\n")

    t0 = time.monotonic()
    last_report = 0.0
    best = "BAD"
    snap_saved = False
    try:
        while time.monotonic() - t0 < args.seconds:
            ok, frame = cap.read()
            if not ok:
                print("⚠️ 断流", file=sys.stderr)
                time.sleep(0.2)
                continue
            obs = est.infer(frame)
            now = time.monotonic()

            if args.snapshot and not snap_saved:
                import numpy as np

                cv2.imencode(Path(args.snapshot).suffix or ".png", frame)[1].tofile(args.snapshot)
                print(f"📸 已存画面：{args.snapshot}")
                snap_saved = True

            if now - last_report >= args.interval:
                last_report = now
                level, tips = judge(obs)
                if level == "OK":
                    best = "OK"
                elif level == "WARN" and best != "OK":
                    best = "WARN"
                met = obs.metrics or {}
                mark = {"OK": "✅", "WARN": "🟡", "BAD": "❌"}[level]
                print(f"{mark} [{level}] 检测={'有' if obs.person_present else '无'} "
                      f"conf={obs.confidence:.3f} "
                      f"neck={met.get('neck_angle_deg')} "
                      f"tilt={met.get('shoulder_tilt_deg')} "
                      f"dist={met.get('distance_cm')}")
                for t in tips:
                    print(f"      · {t}")
            time.sleep(1.0 / cfg.sample_hz)
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        est.close()

    print(f"\n本次最佳等级：{best}")
    if best == "OK":
        print("✅ 构图合格，可以跑 python scripts/debug_view.py --calibrate 做正式校准了")
    else:
        print("⚠️ 构图还不达标：按上面建议调整摄像头位置/角度后重跑本工具")
    return 0 if best == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
