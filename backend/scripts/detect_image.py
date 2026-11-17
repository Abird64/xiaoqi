#!/usr/bin/env python3
"""单图姿态检测：用 Lightweight OpenPose 的 18 点做离线验证。

    cd backend
    python scripts/detect_image.py 照片.jpg
    python scripts/detect_image.py 照片.jpg --out 标注.png

为什么需要它：
  - 沙箱 / 无摄像头机器上没法跑实时抽检，但检测逻辑本身可以单独验；
  - 排查"检测不到人"到底是模型问题还是摄像头问题，这是最快的分辨手段。

判读方法：
  - 每个人打印组置信度、可见点数、compute_metrics 的全部指标；
  - 用 sitting_rules.classify 按 config.yaml 的绝对阈值给出粗判；
  - --out 把 18 点骨架画回原图并保存，肉眼核对关键点位置是否正确。

中文路径做了处理（np.fromfile / imdecode），因为项目本身在 G:\\中级实训\\ 下。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xiaoqi.config import BACKEND_DIR, load_config               # noqa: E402
from xiaoqi.rules.sitting_rules import (REASON_TEXT, classify,   # noqa: E402
                                        compute_metrics)
from xiaoqi.vision.pose_lw import (KP_NAMES, LWPoseEstimator,    # noqa: E402
                                   NUM_KPTS, draw_skeleton)

# 肉眼核对时最有用的几个点（头/颈/肩/髋）
CHECK_POINTS = (0, 1, 2, 5, 8, 11, 16, 17)


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


def _metrics(pts: dict, w: int, h: int, cfg) -> dict:
    return compute_metrics(pts, w, h,
                           margin_ratio=float(getattr(cfg, "sitting_margin_ratio",
                                                      0.03)))


def _save_annotated(frame, people: list[dict], cfg, out_arg: str) -> Path | None:
    """把每个人的 18 点骨架画上去另存；没检测到人时留一行提示。"""
    import cv2

    out = Path(out_arg).expanduser()
    if not out.is_absolute():
        out = (Path.cwd() / out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    img = frame.copy()
    h, w = img.shape[:2]
    if people:
        for i, person in enumerate(people):
            pts = person["pts"]
            draw_skeleton(img, pts, (80, 220, 80), 2)
            for idx, (x, y, _score) in pts.items():
                color = (60, 90, 255) if idx in CHECK_POINTS else (120, 160, 255)
                cv2.circle(img, (int(x), int(y)), 4, color, -1)
            state, _conf, _reason = classify(_metrics(pts, w, h, cfg), cfg)
            anchor = pts.get(0) or next(iter(pts.values()))
            cv2.putText(img, f"#{i} {person['score']:.2f} {state}",
                        (int(anchor[0]) + 8, int(anchor[1]) - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (60, 220, 120), 2,
                        cv2.LINE_AA)
    else:
        cv2.putText(img, "NO PERSON DETECTED", (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 220, 120), 2,
                    cv2.LINE_AA)

    if imwrite_unicode(out, img):
        print(f"\n标注图已保存：{out}")
        return out
    print(f"\n⚠️ 标注图保存失败：{out}", file=sys.stderr)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="小栖 · 单图姿态检测（Lightweight OpenPose 18 点）")
    ap.add_argument("image",
                    help="要检测的图片路径：任意位置都行（绝对路径最稳）。"
                         "相对路径按**当前目录**解析，找不到会再试 backend/ 下。中文路径没问题。")
    ap.add_argument("--out", default=None,
                    help="把 18 点骨架画上去另存（相对路径同样按当前目录）")
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
    est = LWPoseEstimator(
        repo_dir=getattr(cfg, "sitting_lw_repo", ""),
        checkpoint=getattr(cfg, "sitting_lw_checkpoint", ""),
        height_size=int(getattr(cfg, "sitting_height_size", 256)),
        num_threads=int(getattr(cfg, "sitting_torch_threads", 1)),
    )
    if not est.ok:
        print("❌ 姿态估计不可用：\n" + (est.last_error or "原因未知"),
              file=sys.stderr)
        return 1
    print(f"模型：{est.checkpoint}")

    people = est.infer(frame)
    print(f"推理耗时：{est.infer_ms} ms")
    print(f"检测到人数：{len(people)}")

    if not people:
        print("\n⚠️ 这一帧没检测到人。常见原因：")
        print("   1) 人不在画面里 / 太小 / 只露出手臂；")
        print("   2) 光线太暗或强逆光；")
        print("   3) 半身到全身照都行，但尽量照到「头—肩—腰」。")
        if args.out:
            _save_annotated(frame, people, cfg, args.out)
        est.close()
        return 2

    print("\n=== 每人检测结果（18 点）===")
    for i, person in enumerate(people):
        pts = person["pts"]
        m = _metrics(pts, w, h, cfg)
        state, conf, reason = classify(m, cfg)
        visible = sorted(pts)
        print(f"\n[{i}] score={person['score']:.3f}  "
              f"可见点={len(pts)}/{NUM_KPTS}")
        names = ", ".join(f"{k}:{KP_NAMES[k]}" for k in CHECK_POINTS if k in pts)
        print(f"    关键点：{names or '（无头/颈/肩/髋）'}  全部可见索引={visible}")
        print(f"    compute_metrics -> {m}")
        print(f"    classify -> {state}  conf={conf}  reason={reason}")
        text = REASON_TEXT.get(reason)
        if text:
            print(f"      说明：{text}")

    if args.out:
        _save_annotated(frame, people, cfg, args.out)

    est.close()
    print("\n✅ 检测完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
