#!/usr/bin/env python3
"""单图姿态检测：不依赖摄像头验证关键点与头前倾角（M1-2 / M1-3 的离线版）。

    cd backend
    python scripts/detect_image.py 照片.jpg
    python scripts/detect_image.py 照片.jpg --out 标注.png --baseline 12.0

为什么需要它：
  - 沙箱 / 无摄像头机器上没法跑 debug_view.py，但检测逻辑本身可以单独验；
  - 排查"检测不到人"到底是模型问题还是摄像头问题，这是最快的分辨手段。

判读方法（对应 M1-3）：
  - 打印 neck_angle_deg（头前倾角）、shoulder_tilt_deg、distance_cm；
  - 用 --baseline 给一个"坐直"基准角，Δ = neck - baseline 用 config.yaml 的阈值判定状态；
  - --out 会把 35 条骨架线画回原图并保存，肉眼核对关键点位置是否正确。

中文路径做了处理（np.fromfile / imdecode），因为项目本身在 G:\\中级实训\\ 下。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xiaoqi.config import BACKEND_DIR, load_config              # noqa: E402
from xiaoqi.rules.posture_rules import PostureRules             # noqa: E402
from xiaoqi.vision.pose_estimator import SKELETON, PoseEstimator  # noqa: E402

# 只标这几个关键点，方便肉眼核对（耳/肩/髋）
KEY_POINTS = {0: "nose", 7: "ear_L", 8: "ear_R", 11: "shoulder_L",
              12: "shoulder_R", 23: "hip_L", 24: "hip_R"}


def imread_unicode(path: Path):
    """cv2.imread 不支持中文路径，这里绕一下。"""
    import cv2
    import numpy as np

    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def imwrite_unicode(path: Path, img) -> bool:
    import cv2

    ok, buf = cv2.imencode(path.suffix or ".png", img)
    if not ok:
        return False
    buf.tofile(str(path))
    return True


def _save_annotated(frame, obs, out_arg: str) -> Path | None:
    """把骨架画上去另存；没检测到人时只留一行提示（方便回看"为什么没检出"）。"""
    import cv2

    out = Path(out_arg).expanduser()
    if not out.is_absolute():
        # 和输入保持同一口径：相对当前目录
        out = (Path.cwd() / out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    img = frame.copy()
    h, w = img.shape[:2]
    if obs.person_present and obs.landmarks:
        pts = [(int(p[0] * w), int(p[1] * h)) for p in obs.landmarks]
        for a, b in SKELETON:
            if a < len(pts) and b < len(pts):
                cv2.line(img, pts[a], pts[b], (80, 220, 80), 2)
        for i in KEY_POINTS:
            if i < len(pts):
                cv2.circle(img, pts[i], 5, (60, 90, 255), -1)
        met = obs.metrics or {}
        label = f"neck={met.get('neck_angle_deg')} conf={obs.confidence:.2f}"
    else:
        label = "NO PERSON DETECTED"

    cv2.putText(img, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (60, 220, 120), 2, cv2.LINE_AA)

    if imwrite_unicode(out, img):
        print(f"\n标注图已保存：{out}")
        return out
    print(f"\n⚠️ 标注图保存失败：{out}", file=sys.stderr)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="小栖 · 单图姿态检测（M1-2/M1-3 离线验证）")
    ap.add_argument("image",
                    help="要检测的图片路径：任意位置都行（绝对路径最稳）。"
                         "相对路径按**当前目录**解析，找不到会再试 backend/ 下。中文路径没问题。")
    ap.add_argument("--out", default=None,
                    help="把骨架画上去另存（相对路径同样按当前目录）")
    ap.add_argument("--baseline", type=float, default=None,
                    help="坐直基准角（度）；不填则不做状态判定，只报指标")
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    src = Path(args.image).expanduser()
    tried = [src]
    if not src.is_absolute() and not src.exists():
        # 相对路径先按当前目录找；找不到再回退到 backend/（常见的 cd backend 场景）
        alt = (BACKEND_DIR / src).resolve()
        tried.append(alt)
        if alt.exists():
            src = alt
    if not src.exists():
        print("❌ 找不到图片，试过这些位置：", file=sys.stderr)
        for t in tried:
            print(f"     {t}", file=sys.stderr)
        print("\n   提示：直接把照片拖进终端，或写成绝对路径，例如"
              "\n         python scripts/detect_image.py \"C:\\Users\\你\\Desktop\\姿势.jpg\"",
              file=sys.stderr)
        return 1

    frame = imread_unicode(src)
    if frame is None:
        print(f"❌ 图片读不出来（格式或路径问题）：{src}", file=sys.stderr)
        return 1
    h, w = frame.shape[:2]
    print(f"图片：{src}  {w}x{h}")

    cfg = load_config(args.config)
    # 单图必须用 IMAGE 模式：VIDEO 模式带帧间跟踪，连跑多张不同照片时
    # 会带着上一张的状态，同一张图换个顺序能差好几倍（实测 7.8° ↔ 47.8°）。
    est = PoseEstimator(cfg, running_mode="image")
    if not est.ok:
        print("❌ 姿态估计不可用：\n" + (est.last_error or "原因未知"), file=sys.stderr)
        return 1
    print(f"模型：{cfg.vision_model_path}（已加载，IMAGE 模式/无状态）")

    obs = est.infer(frame)
    print(f"推理耗时：{est.infer_ms} ms")
    print(f"检测到人：{obs.person_present}   置信度：{obs.confidence:.3f}")

    if not obs.person_present:
        print("\n⚠️ 这一帧没检测到人。常见原因：")
        print("   1) 人不在画面里 / 太小 / 只露出手臂；")
        print("   2) 光线太暗或强逆光；")
        print("   3) 全身照比半身照更容易检出，尽量照到「头—肩—腰」。")
        if args.out:
            _save_annotated(frame, obs, args.out)
        est.close()
        return 2

    m = obs.metrics
    view = m.get("view", "?")
    print("\n=== 姿态指标（M1-3）===")
    print(f"  相对躯干前屈 neck_angle_deg : {m.get('neck_angle_deg')}°"
          "   （头相对背的方向）")
    print(f"  绝对前倾   head_pitch_deg   : {m.get('head_pitch_deg')}°"
          "   （头相对竖直，越驼越大）")
    if m.get("shoulder_tilt_deg") is None:
        print("  肩线歪斜   shoulder_tilt   : —（不可用）")
        print("       ⚠️ 检测到**侧面视角**：两肩在画面里重叠，肩线角数学上无解。")
        print("          想要这项指标，请从正前方或斜前方 30~45° 拍。")
    else:
        print(f"  肩线歪斜   shoulder_tilt   : {m.get('shoulder_tilt_deg')}°")
    print(f"  视角判定   view            : {view}")
    print(f"  估计距离   distance_cm     : {m.get('distance_cm')} cm")

    print("\n=== 关键点（归一化坐标，0~1）===")
    for idx, name in KEY_POINTS.items():
        if idx < len(obs.landmarks):
            x, y, z, v = obs.landmarks[idx]
            print(f"    [{idx:2d}] {name:11s} x={x:.3f} y={y:.3f} visibility={v:.2f}")

    if args.baseline is not None:
        rules = PostureRules(cfg)
        rules.baseline_neck_deg = args.baseline
        state, conf, _ = rules.classify(obs)
        delta = m["neck_angle_deg"] - args.baseline
        print(f"\n=== 状态判定（基准 {args.baseline}°，Δ={delta:+.1f}°）===")
        print(f"  Δ ≥ {cfg.neck_delta_deg}° → slouch，Δ ≥ {cfg.hunch_delta_deg}° → desk_hunch")
        print(f"  判定结果：{state}")

    if args.out:
        _save_annotated(frame, obs, args.out)

    est.close()
    print("\n✅ 检测完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
