"""坐姿指标与判定（Lightweight OpenPose 18 点版）。

和旧 `posture_rules.py` 的区别：
  - 旧版基于 BlazePose 33 点（耳 7/8、肩 11/12、髋 23/24），且只有 neck_angle 一个量；
  - 本版基于 18 点（**自带 neck = 索引 1**），并给出三个互补指标：
      head_pitch_deg       头相对 neck 与竖直的夹角 —— 伏案头前伸最直观
      head_forward_ratio   头前移量 / 颈髋距离 —— 归一化后不受远近影响
      torso_lean_deg       躯干相对竖直的前倾 —— 区分"整体前探"和"只是低头"
  - 输出额外带 `view` / `edge_clipped` / `visible_kpts`，供上层判断数据可不可信。

设计原则（老大 2026-11-16 定的当前阶段范围）：
  只做「检测 + 出数 + 粗判」，**不做个人化校准**。绝对阈值先写进 config 便于调，
  等 M2 实测数据出来再换成"相对基线增量"。
"""
from __future__ import annotations

import math

from ..vision.pose_lw import (L_EAR, L_EYE, L_HIP, L_SHO, NECK, NOSE, NUM_KPTS,
                              R_EAR, R_EYE, R_HIP, R_SHO)

# 判断"人是否出画"时看的头部关键点：贴在画面边缘说明头被裁掉了，角度不可信
HEAD_KEYS = (NOSE, NECK, R_EAR, L_EAR)


def _mid(pts: dict, a: int, b: int) -> tuple[float, float] | None:
    if a in pts and b in pts:
        return ((pts[a][0] + pts[b][0]) / 2.0, (pts[a][1] + pts[b][1]) / 2.0)
    return None


def _head_point(pts: dict) -> tuple[float, float] | None:
    """头部代表点：优先鼻尖，没有就用双眼中点，再没有用双耳中点。"""
    if NOSE in pts:
        return (pts[NOSE][0], pts[NOSE][1])
    eyes = _mid(pts, R_EYE, L_EYE)
    if eyes:
        return eyes
    return _mid(pts, R_EAR, L_EAR)


def is_edge_clipped(pts: dict, img_w: int, img_h: int,
                    margin_ratio: float = 0.03) -> bool:
    """头部关键点贴在画面边缘 → 人出画了，算出来的角度会失真。"""
    m = max(2.0, min(img_w, img_h) * margin_ratio)
    for k in HEAD_KEYS:
        if k in pts:
            x, y, _ = pts[k]
            if x < m or x > img_w - m or y < m or y > img_h - m:
                return True
    return False


def compute_metrics(pts: dict, img_w: int, img_h: int,
                    margin_ratio: float = 0.03) -> dict:
    """用**可见的点**算局部指标；缺什么就少算什么，不硬凑。"""
    out: dict = {
        "visible_kpts": len(pts),
        "edge_clipped": is_edge_clipped(pts, img_w, img_h, margin_ratio),
        "view": "unknown",
    }

    head = _head_point(pts)
    neck = (pts[NECK][0], pts[NECK][1]) if NECK in pts else None
    hip = _mid(pts, R_HIP, L_HIP)
    sho = _mid(pts, R_SHO, L_SHO)

    # 没有 neck 就退回双肩中点（会偏，但聊胜于无，并标 degraded）
    anchor = neck or sho
    if neck is None and sho is not None:
        out["anchor_degraded"] = True

    # ① 头相对锚点与竖直的夹角
    if head and anchor:
        dx = head[0] - anchor[0]
        dy = head[1] - anchor[1]
        if abs(dy) > 1e-6:
            out["head_pitch_deg"] = round(math.degrees(math.atan2(abs(dx), abs(dy))), 1)
        # ② 归一化前移量：除以颈髋距离，抵消远近/镜头差异
        if hip is not None:
            torso_len = math.hypot(anchor[0] - hip[0], anchor[1] - hip[1])
            if torso_len > 1e-6:
                out["head_forward_ratio"] = round(abs(dx) / torso_len, 3)

    # ③ 躯干前倾
    if anchor and hip:
        dx = anchor[0] - hip[0]
        dy = anchor[1] - hip[1]
        if abs(dy) > 1e-6:
            out["torso_lean_deg"] = round(math.degrees(math.atan2(abs(dx), abs(dy))), 1)

    # ④ 视角：两肩跨度 / 躯干长。太窄说明侧对镜头，肩线类指标无意义
    if R_SHO in pts and L_SHO in pts and anchor and hip:
        span = math.hypot(pts[R_SHO][0] - pts[L_SHO][0],
                          pts[R_SHO][1] - pts[L_SHO][1])
        torso_len = math.hypot(anchor[0] - hip[0], anchor[1] - hip[1]) or 1e-6
        ratio = span / torso_len
        out["shoulder_span_ratio"] = round(ratio, 2)
        out["view"] = "side" if ratio < 0.35 else "frontal"

    return out


def classify(metrics: dict, cfg) -> tuple[str, float, str]:
    """给一帧指标 → (pose_state, confidence, reason_code)。

    pose_state 取值严格落在协议冻结的六枚举里（unknown/upright/slouch/desk_hunch/away）。
    reason 用**英文 code**（便于程序判断与跨工具显示），中文说明见 REASON_TEXT。
    当前是**绝对阈值**的粗判；M2 换成相对基线后，这里只改比较对象、接口不变。
    """
    visible = int(metrics.get("visible_kpts", 0))
    if visible == 0:
        # 单帧没人 → unknown，不写 away。连续多帧没人才由调用方升级成 away，
        # 否则构图差/逆光会被记成"人离开了"，直接污染 away 时长统计。
        return "unknown", 0.0, "no_person"
    if visible < int(getattr(cfg, "sitting_min_visible_kpts", 4)):
        return "unknown", 0.0, f"too_few_kpts:{visible}"
    if metrics.get("edge_clipped"):
        return "unknown", 0.0, "edge_clipped"

    head = metrics.get("head_pitch_deg")
    torso = metrics.get("torso_lean_deg")
    if head is None:
        return "unknown", 0.0, "no_head_angle"

    head_thr = float(getattr(cfg, "sitting_head_pitch_deg", 58.0))
    torso_thr = float(getattr(cfg, "sitting_torso_lean_deg", 20.0))

    # 置信度：可见点越多越可信，封顶 0.95
    conf = round(min(0.95, visible / float(NUM_KPTS) * 1.3), 2)

    if torso is not None and torso >= torso_thr:
        return "desk_hunch", conf, f"torso_lean:{torso}>={torso_thr}"
    if head >= head_thr:
        return "slouch", conf, f"head_pitch:{head}>={head_thr}"
    return "upright", conf, f"ok:head={head},torso={torso}"


# reason code → 中文说明（给前端/报告直接用，避免在 JSON 里塞中英混排）
REASON_TEXT: dict[str, str] = {
    "no_person": "画面中没检测到人（仅一轮，暂不判定离开）",
    "no_person_away": "连续两轮都没检测到人，判定为离开",
    "edge_clipped": "头部出画，角度不可信",
    "no_head_angle": "缺少算头部角度所需的点",
}


def reason_text(reason: str) -> str:
    """把 reason code 翻成人话（带参数的 code 也能匹配前缀）。"""
    if reason in REASON_TEXT:
        return REASON_TEXT[reason]
    head, _, tail = reason.partition(":")
    if head == "too_few_kpts":
        return f"可见关键点太少（{tail} 个），不足以判断"
    if head == "head_pitch":
        return f"头前倾超过阈值（{tail}）"
    if head == "torso_lean":
        return f"躯干前倾超过阈值（{tail}）"
    if head == "ok":
        return f"坐姿正常（{tail}）"
    return reason


__all__ = ["compute_metrics", "classify", "is_edge_clipped", "reason_text"]
