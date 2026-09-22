#!/usr/bin/env python3
"""M1-2 / M1-3 验收工具：画骨架线 + 打印头前倾角与当前状态。

    cd backend && python scripts/debug_view.py            # 摄像头 + 骨架叠加
    python scripts/debug_view.py --headless                # 无窗口，只打印数值（SSH/远程用）

验收判据（跑给轮值主持看）：
  M1-2  画面上能看到骨架线，关键点实时跟随
  M1-3  控制台持续打印 neck_angle_deg / 基线 / delta / 当前状态

需要：真实 USB 摄像头 + mediapipe。缺任何一项会直接给出可读提示并退出，
      不会抛栈（M1-6 精神）。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xiaoqi.config import load_config                     # noqa: E402
from xiaoqi.rules.calibration import Calibration           # noqa: E402
from xiaoqi.rules.posture_rules import PostureRules        # noqa: E402
from xiaoqi.state.machine import PoseStateMachine         # noqa: E402
from xiaoqi.vision.pose_estimator import PoseEstimator     # noqa: E402

# MediaPipe BlazePose 骨架连线（33 点里的常用段）
BONES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
         (11, 23), (12, 24), (23, 24), (23, 25), (24, 26)]


def main() -> int:
    ap = argparse.ArgumentParser(description="小栖 · 姿态调试视图（M1-2/M1-3）")
    ap.add_argument("--config", default=None)
    ap.add_argument("--headless", action="store_true", help="不弹窗口，只打印数值")
    ap.add_argument("--seconds", type=int, default=0, help="运行 N 秒后自动退出（0=一直跑）")
    ap.add_argument("--calibrate", action="store_true",
                    help="启动即用前 3 秒采样基线（否则先按直立粗估）")
    args = ap.parse_args()

    try:
        import cv2
    except Exception as e:
        print(f"❌ 需要 opencv-python：{e}", file=sys.stderr)
        return 1

    est = PoseEstimator()
    if not est.ok:
        print("❌ MediaPipe 未安装 —— `pip install mediapipe` 后再跑。"
              "\n   （链路联调可用 --sim，但 M1-2 骨架线必须真机验收。）", file=sys.stderr)
        return 1

    cfg = load_config(args.config)
    cap = cv2.VideoCapture(cfg.camera_index)
    if not cap.isOpened():
        print(f"❌ 摄像头 {cfg.camera_index} 打不开 —— 检查 USB 占用与系统权限。",
              file=sys.stderr)
        return 1

    rules = PostureRules(cfg)
    machine = PoseStateMachine(cfg)
    calib = Calibration(required_samples=30)
    t0 = time.monotonic()

    print(f"{'neck°':>7} {'基线°':>7} {'Δ°':>7}  {'状态':<12} 置信度")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("❌ 断流，退出（服务端模式会自动重连，这里是调试工具）",
                      file=sys.stderr)
                return 1
            obs = est.infer(frame)

            # ---- 校准（M2-1）：前 3 秒采样「坐直」基线 ----
            if not calib.done:
                if args.calibrate and time.monotonic() - t0 < 3.0:
                    done = calib.feed(obs)
                    if done:
                        rules.baseline_neck_deg = calib.baseline_neck_deg
                        print(f"✅ 校准完成：基线 {calib.baseline_neck_deg}°"
                              f"（{len(calib.samples)} 个样本）")
                    else:
                        print(f"  采样中… {calib.progress:.0%}  保持坐直")
                elif time.monotonic() - t0 >= 3.0 and not args.calibrate:
                    rules.baseline_neck_deg = calib.baseline_neck_deg or 12.0
            state, conf, metrics = rules.classify(obs)
            ev = machine.feed(state, conf, metrics)

            neck = metrics.get("neck_angle_deg")
            base = rules.baseline_neck_deg
            delta = (round(neck - base, 1)
                     if isinstance(neck, (int, float)) and base is not None else None)
            print(f"{neck if neck is not None else '—':>7} "
                  f"{base if base is not None else '—':>7} "
                  f"{delta if delta is not None else '—':>7}  "
                  f"{machine.state:<12} {conf:.2f}"
                  + ("   ⬅ 切换" if ev else ""))

            # ---- M1-2：骨架叠加 ----
            if not args.headless and obs.landmarks:
                h, w = frame.shape[:2]
                pts = [(int(p[0] * w), int(p[1] * h)) for p in obs.landmarks]
                for a, b in BONES:
                    cv2.line(frame, pts[a], pts[b], (80, 220, 80), 2)
                for i in (0, 7, 8, 11, 12, 23, 24):
                    cv2.circle(frame, pts[i], 5, (60, 90, 255), -1)
                cv2.putText(frame, f"{machine.state}  neck={neck} d={delta}",
                            (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                            (60, 220, 120), 2, cv2.LINE_AA)
                cv2.imshow("xiaoqi debug (q to quit)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if args.seconds and time.monotonic() - t0 >= args.seconds:
                break
            time.sleep(1.0 / cfg.sample_hz)
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        est.close()
        if not args.headless:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
    print("\n结束。最后状态：", machine.state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
