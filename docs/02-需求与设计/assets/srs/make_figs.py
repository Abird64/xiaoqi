#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成《小栖 · 需求规格说明书》的 5 张图，并自动检查"连线标签压住方框"。

设计原则
--------
1. 图宽 6.4 英寸；Word 导出时页面左右边距设为 2.2 cm（正文宽 16.6 cm ≈ 6.53 in），
   插入后接近 1:1，8pt 文字在纸面上仍是 8pt。
2. 连线标签只放短词，长解释放正文表格或图下说明。
3. 每张图画完用真实渲染度量跑一遍碰撞检查（标签 × 图形、标签 × 标签），
   有压字则报错退出（exit 1），不靠肉眼。

用法：python3 make_figs.py
输出：同目录 fig-4-1 / fig-5-1 / fig-5-2 / fig-8-1 / fig-8-2 PNG
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse, FancyBboxPatch, Rectangle

plt.rcParams["font.sans-serif"] = ["Noto Sans SC", "Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

BORDER = "#2563EB"
FILL = "#EEF2FF"
TXT = "#1F2937"
GRAY = "#6B7280"
ARROW = "#5B6B8C"
PURPLE = "#7C3AED"

FIG_W_IN = 6.4
OUT = os.path.dirname(os.path.abspath(__file__))

PROT = []   # 受保护矩形 (x0, y0, x1, y1)：连线标签不得压入
LBL = []    # 需要检查的连线标签


def new_fig(xmax, ymax):
    PROT.clear()
    LBL.clear()
    fig, ax = plt.subplots(figsize=(FIG_W_IN, FIG_W_IN * ymax / xmax))
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.axis("off")
    ax.set_aspect("equal")
    return fig, ax


def protect(x, y, w, h, pad=0.6):
    PROT.append((x - pad, y - pad, x + w + pad, y + h + pad))


def box(ax, x, y, w, h, text, fs=8.5, fc=FILL, ec=BORDER, lw=1.3, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=2.2",
                                fc=fc, ec=ec, lw=lw, mutation_aspect=1, zorder=4))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=TXT, zorder=5, linespacing=1.6,
            fontweight="bold" if bold else "normal")
    protect(x, y, w, h)


def boundary(ax, x, y, w, h, label):
    ax.add_patch(Rectangle((x, y), w, h, fc="none", ec=BORDER, lw=1.3,
                           ls=(0, (5, 3)), zorder=1))
    ax.text(x, y + h + 1.5, label, ha="left", va="bottom", fontsize=7.5,
            color=GRAY, zorder=5)


def ellipse(ax, cx, cy, w, h, text, fs=8.0, fc=FILL):
    ax.add_patch(Ellipse((cx, cy), w, h, fc=fc, ec=BORDER, lw=1.3, zorder=4))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, color=TXT,
            zorder=5, linespacing=1.5)
    protect(cx - w / 2, cy - h / 2, w, h)


def actor(ax, x, y, label, s=1.0, fs=8.0):
    ax.add_patch(Ellipse((x, y + 5.4 * s), 3.0 * s, 3.4 * s, fc="white", ec=BORDER, lw=1.3, zorder=4))
    ax.add_line(Line2D([x, x], [y + 3.7 * s, y + 0.7 * s], color=BORDER, lw=1.3, zorder=4))
    ax.add_line(Line2D([x - 2.3 * s, x + 2.3 * s], [y + 2.8 * s, y + 2.8 * s], color=BORDER, lw=1.3, zorder=4))
    ax.add_line(Line2D([x, x - 1.9 * s], [y + 0.7 * s, y - 1.9 * s], color=BORDER, lw=1.3, zorder=4))
    ax.add_line(Line2D([x, x + 1.9 * s], [y + 0.7 * s, y - 1.9 * s], color=BORDER, lw=1.3, zorder=4))
    ax.text(x, y - 4.2 * s, label, ha="center", va="top", fontsize=fs, color=TXT, linespacing=1.5)
    protect(x - 3.4 * s, y - 8.4 * s, 6.8 * s, 9.6 * s)


def arrow(ax, p, q, label=None, lx=None, ly=None, fs=6.8, ls="-", color=ARROW,
          lw=1.15, rad=0.0, lcolor=None, ha="center", va="center"):
    ax.annotate("", xy=q, xytext=p,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, ls=ls,
                                shrinkA=0.5, shrinkB=0.5,
                                connectionstyle=f"arc3,rad={rad}"), zorder=3)
    if label:
        x = lx if lx is not None else (p[0] + q[0]) / 2
        y = ly if ly is not None else (p[1] + q[1]) / 2
        t = ax.text(x, y, label, ha=ha, va=va, fontsize=fs, color=lcolor or TXT,
                    zorder=6, linespacing=1.45,
                    bbox=dict(fc="white", ec="none", pad=0.7, alpha=0.95))
        LBL.append(t)


def note(ax, x, y, text, fs=6.6, ha="left"):
    ax.text(x, y, text, ha=ha, va="top", fontsize=fs, color=GRAY, zorder=6, linespacing=1.6)


def extent_data(ax, artist, renderer):
    bb = artist.get_window_extent(renderer=renderer)
    inv = ax.transData.inverted()
    (x0, y0), (x1, y1) = inv.transform([[bb.x0, bb.y0], [bb.x1, bb.y1]])
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def check(ax, name):
    """检查连线标签是否压住图形或彼此重叠。"""
    fig = ax.figure
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    bad, boxes = [], []
    for t in LBL:
        e = extent_data(ax, t, r)
        tagname = t.get_text().replace("\n", " ")
        boxes.append((tagname, e))
        for (x0, y0, x1, y1) in PROT:
            if e[0] < x1 and e[2] > x0 and e[1] < y1 and e[3] > y0:
                bad.append(f"  [{name}] 标签「{tagname}」{tuple(round(v,1) for v in e)} "
                           f"压住图形 {tuple(round(v,1) for v in (x0,y0,x1,y1))}")
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i][1], boxes[j][1]
            if a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]:
                bad.append(f"  [{name}] 标签「{boxes[i][0]}」{tuple(round(v,1) for v in a)} 与 "
                           f"「{boxes[j][0]}」{tuple(round(v,1) for v in b)} 重叠")
    return bad


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white", pad_inches=0.06)
    plt.close(fig)
    return path


# ─────────────────────────── 图 4-1 系统上下文 ───────────────────────────
def fig_context():
    fig, ax = new_fig(176, 96)

    box(ax, 2, 68, 32, 14, "用户\n大学生 / 办公族", fs=8.5)
    box(ax, 2, 49, 32, 13, "外置 USB 摄像头\n«device»", fs=8)
    box(ax, 2, 29, 32, 13, "Windows 操作系统\n«system»", fs=8)
    box(ax, 2, 4, 32, 14, "手机健康 App\n导出文件 «artifact»", fs=8)
    box(ax, 62, 30, 46, 32, "小栖系统\n姿态判定 · 状态机\n房间渲染 · 提醒调度", fs=9, bold=True)
    box(ax, 134, 66, 40, 20, "手机侧自动化工具\n«external system»\niOS 快捷指令 /\nHTTP Shortcuts", fs=7.8)

    arrow(ax, (34, 74), (62, 60), "使用 / 设置", lx=48, ly=70)
    arrow(ax, (62, 52), (34, 66), "视觉状态 / 提醒", lx=48, ly=56, color=PURPLE, lcolor=PURPLE)
    arrow(ax, (34, 56), (62, 48), "视频帧", lx=48, ly=44)
    arrow(ax, (34, 36), (62, 40), "前台应用 · 时间", lx=48, ly=32)
    arrow(ax, (34, 12), (62, 34), "手动导入（兜底）", lx=48, ly=16)
    arrow(ax, (134, 74), (108, 58), "HTTP 上报步数\n（令牌 + 幂等）", lx=121, ly=84)

    note(ax, 2, 94, "系统边界之外：用户（人）· 外置设备 · 操作系统 · 外部工具 · 导出文件")
    return check(ax, "图4-1"), fig, "fig-4-1-context.png"


# ──────────────────────── 图 5-1 用户主链用例图 ────────────────────────
def fig_usecase_main():
    fig, ax = new_fig(216, 196)

    boundary(ax, 26, 10, 138, 182, "系统边界：小栖")
    actor(ax, 10, 156, "用户", s=0.95, fs=8)

    mains = [("首次启动与坐姿校准", 182), ("实时观看房间与健康伙伴", 162),
             ("标记已喝水", 140), ("查看当日健康概览", 118),
             ("调整提醒偏好", 96), ("配对手机接入", 68)]
    for t, y in mains:
        ellipse(ax, 56, y, 48, 14, t, fs=8)
        arrow(ax, (14.5, 156 + (y - 156) * 0.06), (32, y), lw=1.0)

    inner = [("驼背提醒", 182), ("状态机实时判定", 162), ("久坐提醒", 142),
             ("喝水提醒", 122), ("校验配对令牌", 74), ("幂等去重落库", 52)]
    for t, y in inner:
        ellipse(ax, 138, y, 44, 13, t, fs=7.6)

    arrow(ax, (80, 162), (116, 162), "«include»", lx=98, ly=169, fs=6.4, ls="--", lcolor=GRAY)
    arrow(ax, (80, 167), (116, 180), "«extend»", lx=98, ly=177, fs=6.4, ls="--", lcolor=GRAY)
    arrow(ax, (80, 158), (116, 144), "«extend»", lx=98, ly=150, fs=6.4, ls="--", lcolor=GRAY)
    arrow(ax, (80, 155), (116, 122), "«extend»", lx=98, ly=136, fs=6.4, ls="--", lcolor=GRAY)
    arrow(ax, (80, 71), (116, 73.5), "«include»", lx=98, ly=64, fs=6.4, ls="--", lcolor=GRAY)
    arrow(ax, (138, 67.5), (138, 58.5), "«include»", lx=157, ly=63, fs=6.4, ls="--", lcolor=GRAY)

    box(ax, 188, 174, 26, 17, "外置 USB\n摄像头 «device»", fs=7.2)
    box(ax, 188, 144, 26, 17, "Windows\n操作系统 «system»", fs=7.2)
    box(ax, 188, 50, 26, 21, "手机侧\n自动化工具\n«external\nsystem»", fs=7.2)
    arrow(ax, (188, 178), (160, 166), "视频帧", lx=176, ly=190, fs=6.4, ls="--", lcolor=GRAY)
    arrow(ax, (188, 152), (160, 158), "前台应用", lx=176, ly=146, fs=6.4, ls="--", lcolor=GRAY)
    arrow(ax, (188, 58), (160, 58), "POST 上报", lx=176, ly=50, fs=6.4, ls="--", lcolor=GRAY)

    return check(ax, "图5-1"), fig, "fig-5-1-usecase-main.png"


# ─────────────────────── 图 5-2 设置与兜底用例图 ───────────────────────
def fig_usecase_settings():
    fig, ax = new_fig(176, 100)

    boundary(ax, 30, 8, 76, 84, "系统边界：小栖")
    actor(ax, 9, 48, "用户", s=0.9, fs=8)

    items = [("重新坐姿校准", 76), ("查看 / 重置配对令牌", 62),
             ("手动导入健康数据", 48), ("摄像头与静默时段设置", 34),
             ("查看本地数据与隐私状态", 20)]
    for t, y in items:
        ellipse(ax, 68, y, 62, 13, t, fs=8)
        arrow(ax, (13.5, 48 + (y - 48) * 0.07), (37, y), lw=1.0)

    box(ax, 134, 42, 40, 14, "健康 App 导出文件\n«artifact»", fs=7.6)
    arrow(ax, (134, 49), (99, 48), "读取并解析", lx=116, ly=56, fs=6.8, ls="--", lcolor=GRAY)

    return check(ax, "图5-2"), fig, "fig-5-2-usecase-settings.png"


# ─────────────────────── 图 8-1 核心数据对象关系 ───────────────────────
def entity(ax, x, y, w, cn, en, fields, fs_field=6.2):
    lh = 2.8
    h = 11.2 + lh * len(fields)
    ax.add_patch(Rectangle((x, y), w, h, fc="white", ec=BORDER, lw=1.2, zorder=4))
    ax.add_patch(Rectangle((x, y + h - 10.4), w, 10.4, fc=FILL, ec=BORDER, lw=1.2, zorder=5))
    ax.text(x + w / 2, y + h - 3.2, cn, ha="center", va="center", fontsize=7.4,
            color=TXT, fontweight="bold", zorder=6)
    ax.text(x + w / 2, y + h - 7.4, en, ha="center", va="center", fontsize=6.0,
            color=GRAY, zorder=6)
    for i, f in enumerate(fields):
        yy = y + h - 10.4 - lh * i
        if i:
            ax.add_line(Line2D([x + 1.2, x + w - 1.2], [yy, yy], color="#D7DEEA", lw=0.6, zorder=6))
        ax.text(x + 1.8, yy - lh / 2, f, ha="left", va="center", fontsize=fs_field,
                color=TXT, zorder=6)
    ax.add_line(Line2D([x + 1.2, x + w - 1.2], [y, y], color="#D7DEEA", lw=0.6, zorder=6))
    protect(x, y, w, h)
    return h


def fig_data_objects():
    fig, ax = new_fig(192, 144)
    w, hh = 54, 30
    col = [2, 68, 134]
    row = [104, 64, 24]

    entity(ax, col[0], row[0], w, "校准档案", "CalibrationProfile",
           ["baseline_metrics", "threshold_slouch", "threshold_desk_hunch", "status"])
    entity(ax, col[1], row[0], w, "姿态采样", "PoseSample",
           ["ts / pose_state / confidence", "neck_angle_deg", "shoulder_tilt_deg"])
    entity(ax, col[2], row[0], w, "行为会话", "BehaviorSession",
           ["active_app / level", "duration_sec"])
    entity(ax, col[0], row[1], w, "用户设置", "UserSetting",
           ["water_interval_min", "sit_threshold_min", "debounce_sec", "quiet_start"])
    entity(ax, col[1], row[1], w, "当日统计（聚合中心）", "DailyStat",
           ["steps / water_count", "sit_sec / standup_count", "phone_stale"])
    entity(ax, col[2], row[1], w, "手机上报", "PhoneIngest",
           ["device_id / steps", "ts / source"])
    entity(ax, col[0], row[2], w, "操作日志", "OperationLog",
           ["action / target / ts"])
    entity(ax, col[1], row[2], w, "提醒事件", "ReminderEvent",
           ["kind / level / ts", "suppressed"])
    entity(ax, col[2], row[2], w, "配对令牌", "PairToken",
           ["token / status", "created_ts", "last_used_ts"])

    m = row[0] + hh / 2
    num = dict(fs=7.0, lcolor="#111827")
    arrow(ax, (56, m), (68, m), "①", lx=62, ly=m + 5, **num)
    arrow(ax, (95, row[0]), (95, row[1] + hh), "②", lx=95, ly=99, **num)
    arrow(ax, (161, row[0]), (95, row[1] + hh), "③", lx=140, ly=99, **num)
    arrow(ax, (134, m), (122, m), "④", lx=128, ly=m + 5, **num)
    arrow(ax, (161, row[2] + hh), (161, row[1]), "⑤", lx=172, ly=row[1] - 10, **num)
    arrow(ax, (50, row[1]), (72, row[2] + hh), "⑥", lx=61, ly=59, **num)
    arrow(ax, (29, row[1]), (29, row[2] + hh), "⑦", lx=44, ly=59, **num)
    arrow(ax, (95, row[1]), (95, row[2] + hh), "⑧", lx=95, ly=59, **num)

    note(ax, 2, 142, "关系图例：① 判定基准（校准档案 → 姿态判定）②③④ 聚合（三路数据 → 当日统计）"
                     "⑤ 令牌校验 ⑥ 静默抑制 ⑦ 操作留痕 ⑧ 超阈值触发")
    note(ax, 2, 20, "关键操作（校准 / 令牌重置 / 设置变更）写入 OperationLog；"
                    "ReminderEvent.suppressed 记录静默时段抑制")

    return check(ax, "图8-1"), fig, "fig-8-1-data-objects.png"


# ─────────────────────── 图 8-2 姿态状态机图 ───────────────────────
def fig_state_machine():
    fig, ax = new_fig(190, 142)

    ellipse(ax, 28, 106, 36, 15, "unknown\n未知", fs=8)
    ellipse(ax, 90, 110, 36, 15, "upright\n坐直", fs=8)
    ellipse(ax, 152, 110, 36, 15, "slouch\n驼背", fs=8)
    ellipse(ax, 152, 66, 36, 15, "desk_hunch\n伏案", fs=8)
    ellipse(ax, 90, 28, 36, 15, "away\n离开", fs=8)

    arrow(ax, (46, 106), (72, 108), "基准范围内", lx=59, ly=99, fs=6.4)
    arrow(ax, (40, 99), (136, 105), "头前倾超阈值", lx=88, ly=86, fs=6.4, rad=-0.20)
    arrow(ax, (32, 99), (136, 70), "躯干前倾超阈值", lx=86, ly=62, fs=6.4, rad=0.10)
    arrow(ax, (108, 113), (134, 112), "超阈值 + N 秒", lx=121, ly=125, fs=6.4)
    arrow(ax, (134, 107), (108, 108), "回到基准 + N 秒", lx=121, ly=98, fs=6.4)
    arrow(ax, (152, 102), (152, 74), "进一步前倾", lx=173, ly=88, fs=6.4)
    arrow(ax, (84, 103), (86, 36), "无人", lx=68, ly=70, fs=6.4)
    arrow(ax, (146, 103), (100, 36), "无人", lx=146, ly=52, fs=6.4)
    arrow(ax, (146, 59), (100, 33), "无人", lx=159, ly=44, fs=6.4)
    arrow(ax, (76, 34), (20, 99), "重新检测到人", lx=38, ly=80, fs=6.4)

    note(ax, 2, 140, "防抖：超阈值需持续 N 秒（默认 3 s）才切换；过渡期保持原状态，避免状态闪烁。"
                     "「无人」＝画面无人体或置信度过低")

    return check(ax, "图8-2"), fig, "fig-8-2-pose-state.png"


FIGS = [fig_context, fig_usecase_main, fig_usecase_settings, fig_data_objects, fig_state_machine]


if __name__ == "__main__":
    problems = []
    for fn in FIGS:
        bad, fig, name = fn()
        save(fig, name)
        problems += bad
        print(f"  {name}: {'OK' if not bad else str(len(bad)) + ' 处压字'}")
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    print("all figures clean:", sorted(f for f in os.listdir(OUT) if f.endswith(".png")))
