#!/usr/bin/env python3
"""摄像头摆位自检：告诉你"为什么检测不到人，该往哪调"。

    cd backend
    python scripts/framing_check.py                  # 实时看 20 秒
    python scripts/framing_check.py --seconds 40     # 看更久
    python scripts/framing_check.py --snapshot 拍一张.png

背景：Lightweight OpenPose 是 bottom-up，先出 18 个关键点再用 PAF 连成人。
只拍到脸（耳朵/肩膀出画）时，头前倾角会缺锚点或严重失真——这不是模型坏了，
是**构图不合格**。本工具把 18 点判据摊开，让你按提示挪摄像头。

判据（坐姿上半身照，坐标为 0~1 归一化）：
  合格：耳 y∈[0.15,0.55]  肩可见（两点 score≥0.2）且肩 y∈[0.25,0.85]
  视角：两肩跨度 / 躯干长 < 0.35 判为 side（侧对镜头，肩线/前倾角不可信）
  出画：头部关键点贴画面边缘（edge_clipped）→ 角度不可信
  加分：髋点也能看到，torso_lean 才稳（不强制）
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xiaoqi.config import load_config                                  # noqa: E402
from xiaoqi.rules.sitting_rules import classify, compute_metrics       # noqa: E402
from xiaoqi.vision.camera_util import open_capture                     # noqa: E402
from xiaoqi.vision.pose_lw import (L_EAR, L_HIP, L_SHO, LWPoseEstimator,  # noqa: E402
                                   R_EAR, R_HIP, R_SHO)

# 关键点得分低于此值当作"看不见"（LW 的后处理会把弱响应点也带出来）
MIN_KPT_SCORE = 0.2


def _pts_with_score(pts: dict, idx: int) -> tuple[float, float, float] | None:
    p = pts.get(idx)
    return p if p is not None and p[2] >= MIN_KPT_SCORE else None


def judge(person: dict | None, img_w: int, img_h: int, cfg) -> tuple[str, list[str], dict]:
    """返回 (等级, 建议列表, 指标)。等级：OK / WARN / BAD。

    判据全部基于 18 点：耳 16/17、肩 2/5、髋 8/11。
    """
    if not person:
        return "BAD", ["画面里没检测到人：请坐正、让上半身进入画面"], {}

    pts = person["pts"]
    met = compute_metrics(
        pts, img_w, img_h,
        margin_ratio=float(getattr(cfg, "sitting_margin_ratio", 0.03)))
    if person.get("score") is not None:
        met["person_score"] = round(float(person["score"]), 3)

    tips: list[str] = []
    bad = False

    ears = [p for p in (_pts_with_score(pts, R_EAR), _pts_with_score(pts, L_EAR))
            if p is not None]
    if ears:
        ear_y = sum(p[1] for p in ears) / len(ears) / float(img_h)
        met["ear_y"] = round(ear_y, 3)
    else:
        ear_y = None
        bad = True
        tips.append("耳朵不可见 → 摄像头再往下压约 15~30°，或人往后退，让头部完整进画面")

    shoulders = [p for p in (_pts_with_score(pts, R_SHO), _pts_with_score(pts, L_SHO))
                 if p is not None]
    sh_vis = min((p[2] for p in shoulders), default=0.0)
    if len(shoulders) == 2:
        sh_y = (shoulders[0][1] + shoulders[1][1]) / 2.0 / float(img_h)
        met["shoulder_y"] = round(sh_y, 3)
    else:
        sh_y = None

    if len(shoulders) < 2:
        bad = True
        tips.append(f"肩部不可见（双肩得分={sh_vis:.2f}）→ 这是检测不准的主因，"
                    "摄像头往下压约 15~30°，让肩膀进画面")
    elif not (0.25 <= sh_y <= 0.85):
        tips.append(f"肩线位置偏差（y={sh_y:.2f}，理想 0.25~0.85）→ 前后挪一下摄像头")

    if met.get("edge_clipped"):
        bad = True
        tips.append("头部关键点贴边/出画 → 人往画面中间坐，或摄像头往上/下抬，别切到头")

    if ear_y is not None:
        if ear_y < 0.10:
            bad = True
            tips.append("头太靠上（快被切了）→ 摄像头往上抬一点，或人往后退")
        elif ear_y > 0.60:
            bad = True
            tips.append("头太靠下（拍到大半天花板）→ 摄像头往下压，对准胸口方向")
        elif not (0.15 <= ear_y <= 0.55):
            tips.append(f"头部高度略偏（耳 y={ear_y:.2f}，理想 0.15~0.55）")

    if met.get("view") == "side":
        tips.append(f"侧面视角（肩跨比={met.get('shoulder_span_ratio')}）→ "
                    "请正对或斜前方 30~45°，否则肩线与前倾角会失真")

    hips = [p for p in (_pts_with_score(pts, R_HIP), _pts_with_score(pts, L_HIP))
            if p is not None]
    if len(hips) < 2:
        tips.append("髋部不可见（不影响能否检出，但躯干前倾会缺锚点）")

    if bad:
        return "BAD", tips, met
    return ("OK", tips, met) if not tips else ("WARN", tips, met)


def main() -> int:
    ap = argparse.ArgumentParser(description="小栖 · 摄像头摆位自检（Lightweight OpenPose 18 点）")
    ap.add_argument("--config", default=None)
    ap.add_argument("--index", type=int, default=None, help="摄像头编号（默认取 config.yaml）")
    ap.add_argument("--seconds", type=float, default=20.0, help="运行多久后自动退出")
    ap.add_argument("--snapshot", default=None, help="顺带存一张画面到这个路径")
    args = ap.parse_args()

    try:
        import cv2
    except Exception as e:
        print(f"❌ 需要 opencv-python：{e}", file=sys.stderr)
        return 1

    cfg = load_config(args.config)
    idx = cfg.camera_index if args.index is None else args.index

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

    cap, tag, err = open_capture(idx, cfg.camera_width, cfg.camera_height)
    if cap is None:
        print(f"❌ {err}", file=sys.stderr)
        est.close()
        return 1

    print(f"摄像头 #{idx} 已打开（{tag}），连续采样 {args.seconds:.0f} 秒")
    print("调整时看每行【等级】和【建议】，目标是连续出现 OK。\n")

    t0 = time.monotonic()
    best = "BAD"
    snap_saved = False
    try:
        while time.monotonic() - t0 < args.seconds:
            ok, frame = cap.read()
            if not ok:
                print("⚠️ 断流", file=sys.stderr)
                time.sleep(0.2)
                continue
            people = est.infer(frame)
            h, w = frame.shape[:2]
            person = people[0] if people else None
            level, tips, met = judge(person, w, h, cfg)
            state, _conf, _reason = classify(met, cfg)

            if args.snapshot and not snap_saved:
                buf = cv2.imencode(Path(args.snapshot).suffix or ".png", frame)[1]
                buf.tofile(args.snapshot)
                print(f"📸 已存画面：{args.snapshot}")
                snap_saved = True

            if level == "OK":
                best = "OK"
            elif level == "WARN" and best != "OK":
                best = "WARN"

            mark = {"OK": "✅", "WARN": "🟡", "BAD": "❌"}[level]
            ear_y = met.get("ear_y")
            sh_y = met.get("shoulder_y")
            if person:
                line = (f"{mark} [{level}] {state} "
                        f"ear_y={ear_y if ear_y is not None else '—'} "
                        f"sh_y={sh_y if sh_y is not None else '—'} "
                        f"view={met.get('view', 'unknown')} "
                        f"clip={met.get('edge_clipped')} "
                        f"conf={person['score']:.2f}")
            else:
                line = f"{mark} [{level}] {state} 画面里没有可用的 18 点"
            print(line)
            print("      建议：" + ("；".join(tips) if tips else "构图合格"))
            time.sleep(1.0 / cfg.sample_hz)
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        est.close()

    print(f"\n本次最佳等级：{best}")
    if best == "OK":
        print("✅ 构图合格，可以启动后端（抽检每 60 秒自动跑一次）")
    else:
        print("⚠️ 构图还不达标：按上面建议调整摄像头位置/角度后重跑本工具")
    return 0 if best == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
