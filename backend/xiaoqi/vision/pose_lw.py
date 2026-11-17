"""Lightweight OpenPose 推理封装（bottom-up，CPU 可跑）。

**为什么用它替掉旧的 top-down 方案**（2026-11 实测，四张样图逐张核对）：
  旧的 BlazePose 方案是 top-down：先框人、再在框内回归 33 点，看不见的点也会
  "猜"一个出来 —— 实测侧面时位置偏移但 visibility 仍为 1.00，肩线角算出 63~132°。
  Lightweight OpenPose 是 bottom-up：先出所有关键点、再用 PAF 连成人，连不上就不连，
  **关键点位置肉眼核对全部贴位**，且 18 点里自带 `neck`（索引 1）——
  算头前倾最需要的锚点，COCO 17 点和 BlazePose 都没有。

对外接口（与旧版保持同样的调用方式）：
    est = LWPoseEstimator(repo_dir, checkpoint)
    people = est.infer(frame_bgr)     # -> [{"pts": {idx: (x, y, score)}, "score": 0.8}, ...]
    est.close()

实现细节抄自仓库 demo.py / val.py（`val.py` 顶层 import 了 pycocotools，
这里把 normalize / pad_width 自己实现一份，避免为一个预处理函数引入 COCO 依赖）。
"""
from __future__ import annotations

import logging
import math
import sys
from pathlib import Path

log = logging.getLogger("xiaoqi.pose_lw")

# 18 点名称，与仓库 modules/pose.py 的 Pose.kpt_names 逐字一致
KP_NAMES = ["nose", "neck", "r_sho", "r_elb", "r_wri", "l_sho", "l_elb", "l_wri",
            "r_hip", "r_knee", "r_ank", "l_hip", "l_knee", "l_ank",
            "r_eye", "l_eye", "r_ear", "l_ear"]
NUM_KPTS = 18

# 索引常量（写指标时别记错）
NOSE, NECK = 0, 1
R_SHO, R_ELB, R_WRI = 2, 3, 4
L_SHO, L_ELB, L_WRI = 5, 6, 7
R_HIP, R_KNEE, R_ANK = 8, 9, 10
L_HIP, L_KNEE, L_ANK = 11, 12, 13
R_EYE, L_EYE = 14, 15
R_EAR, L_EAR = 16, 17

# 18 点骨架连线（成对索引），用于把检测结果画回图上做肉眼核对
SKELETON = [
    (NECK, NOSE),
    (NOSE, R_EYE), (R_EYE, R_EAR),
    (NOSE, L_EYE), (L_EYE, L_EAR),
    (NECK, R_SHO), (R_SHO, R_ELB), (R_ELB, R_WRI),
    (NECK, L_SHO), (L_SHO, L_ELB), (L_ELB, L_WRI),
    (NECK, R_HIP), (R_HIP, R_KNEE), (R_KNEE, R_ANK),
    (NECK, L_HIP), (L_HIP, L_KNEE), (L_KNEE, L_ANK),
]

STRIDE, UPSAMPLE = 8, 4


def normalize(img, img_mean=None, img_scale=1 / 256):
    """等价于仓库 val.py:normalize。"""
    import numpy as np

    if img_mean is None:
        img_mean = np.array([128, 128, 128], np.float32)
    return (np.array(img, dtype=np.float32) - img_mean) * img_scale


def pad_width(img, stride, pad_value, min_dims):
    """等价于仓库 val.py:pad_width；返回 (padded, [top, left, bottom, right])。"""
    import cv2

    h, w, _ = img.shape
    h = min(min_dims[0], h)
    min_dims = list(min_dims)
    min_dims[0] = math.ceil(min_dims[0] / float(stride)) * stride
    min_dims[1] = max(min_dims[1], w)
    min_dims[1] = math.ceil(min_dims[1] / float(stride)) * stride
    pad = [int(math.floor((min_dims[0] - h) / 2.0)),
           int(math.floor((min_dims[1] - w) / 2.0))]
    pad.append(int(min_dims[0] - h - pad[0]))
    pad.append(int(min_dims[1] - w - pad[1]))
    padded = cv2.copyMakeBorder(img, pad[0], pad[2], pad[1], pad[3],
                                cv2.BORDER_CONSTANT, value=pad_value)
    return padded, pad


def draw_skeleton(img, pts: dict, color=(80, 220, 80), thickness: int = 2):
    """在 BGR 图上画 18 点骨架；`pts` 为 {idx: (x, y, score)}（像素坐标）。

    只画两端都检测到的连线，缺失点自然断开，不会凭空连线。
    """
    import cv2

    for a, b in SKELETON:
        pa, pb = pts.get(a), pts.get(b)
        if pa is None or pb is None:
            continue
        cv2.line(img, (int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])),
                 color, thickness, cv2.LINE_AA)
    return img


class LWPoseEstimator:
    """一帧 BGR → 若干人的 18 点。失败时 ok=False 并写明 last_error。"""

    def __init__(self, repo_dir: str | Path, checkpoint: str | Path,
                 height_size: int = 256, num_threads: int = 1) -> None:
        self.ok = False
        self.last_error: str | None = None
        self.infer_ms: float = 0.0
        self.height_size = int(height_size)
        self.repo_dir = Path(repo_dir).expanduser().resolve()
        self.checkpoint = Path(checkpoint)
        if not self.checkpoint.is_absolute():
            self.checkpoint = (self.repo_dir / self.checkpoint).resolve()
        self._net = None
        self._torch = None

        try:
            import torch  # noqa: F401
            self._torch = torch
            # ⚠️ 实测（2026-11-16，16 核机器）：这个网络大量用 depthwise conv，
            # torch 的多线程反而**严重拖慢**——12 线程 17s、4 线程 34s、1 线程 6s。
            # 加上宿主上还有浏览器等进程争抢 CPU，线程越多抖动越大。
            # 抽检是 60 秒一次、对延迟不敏感，固定单线程最稳。
            torch.set_num_threads(max(1, int(num_threads)))
        except Exception as e:
            self.last_error = (
                f"PyTorch 不可用（{type(e).__name__}: {e}）。\n"
                "    安装：pip install torch torchvision "
                "--index-url https://download.pytorch.org/whl/cpu")
            log.error(self.last_error)
            return

        if not self.repo_dir.exists():
            self.last_error = (f"Lightweight OpenPose 仓库不存在：{self.repo_dir}\n"
                               "    git clone https://github.com/Daniil-Osokin/"
                               "lightweight-human-pose-estimation.pytorch.git")
            log.error(self.last_error)
            return
        if not self.checkpoint.exists():
            self.last_error = (f"模型权重不存在：{self.checkpoint}\n"
                               "    需放置 checkpoint_iter_370000.pth")
            log.error(self.last_error)
            return

        try:
            if str(self.repo_dir) not in sys.path:
                sys.path.insert(0, str(self.repo_dir))
            from models.with_mobilenet import PoseEstimationWithMobileNet
            from modules.load_state import load_state

            net = PoseEstimationWithMobileNet()
            torch = self._torch
            try:
                ckpt = torch.load(str(self.checkpoint), map_location="cpu",
                                  weights_only=False)
            except TypeError:                      # 老版本 torch 没有 weights_only
                ckpt = torch.load(str(self.checkpoint), map_location="cpu")
            load_state(net, ckpt)
            net.eval()
            self._net = net
            self.ok = True
            log.info("Lightweight OpenPose 已加载：%s", self.checkpoint.name)
        except Exception as e:
            self.last_error = f"模型加载失败：{type(e).__name__}: {e}"
            log.exception("Lightweight OpenPose 加载失败")

    # ------------------------------------------------------------------
    def infer(self, frame_bgr) -> list[dict]:
        """返回 [{"pts": {kpt_idx: (x, y, score)}, "score": 组内总分}, ...]。

        单帧异常返回空列表，不抛出（M1-6 精神）。
        """
        if not self.ok or self._net is None:
            return []
        try:
            import cv2
            import numpy as np

            t0 = __import__("time").perf_counter()
            h, w = frame_bgr.shape[:2]
            scale = self.height_size / h
            scaled = cv2.resize(frame_bgr, (0, 0), fx=scale, fy=scale,
                                interpolation=cv2.INTER_LINEAR)
            scaled = normalize(scaled)
            min_dims = [self.height_size, max(scaled.shape[1], self.height_size)]
            padded, pad = pad_width(scaled, STRIDE, (0, 0, 0), min_dims)

            torch = self._torch
            tensor = torch.from_numpy(np.ascontiguousarray(
                padded.transpose(2, 0, 1)[None])).float()
            with torch.no_grad():
                stages = self._net(tensor)

            hm = np.transpose(stages[-2].squeeze().cpu().data.numpy(), (1, 2, 0))
            hm = cv2.resize(hm, (0, 0), fx=UPSAMPLE, fy=UPSAMPLE,
                            interpolation=cv2.INTER_CUBIC)
            pafs = np.transpose(stages[-1].squeeze().cpu().data.numpy(), (1, 2, 0))
            pafs = cv2.resize(pafs, (0, 0), fx=UPSAMPLE, fy=UPSAMPLE,
                              interpolation=cv2.INTER_CUBIC)

            self.infer_ms = round((__import__("time").perf_counter() - t0) * 1000, 1)
            return self._extract(hm, pafs, scale, pad, w, h)
        except Exception:
            log.exception("Lightweight OpenPose 推理失败")
            return []

    def _extract(self, heatmaps, pafs, scale, pad, img_w, img_h) -> list[dict]:
        """官方 demo.py 的后处理：heatmap → 点 → PAF 连成人 → 坐标还原。"""
        from modules.keypoints import extract_keypoints, group_keypoints

        total = 0
        by_type: list = []
        for kpt_idx in range(NUM_KPTS):
            total += extract_keypoints(heatmaps[:, :, kpt_idx], by_type, total)

        pose_entries, all_keypoints = group_keypoints(by_type, pafs)
        if all_keypoints is None or len(all_keypoints) == 0:
            return []

        for k in range(all_keypoints.shape[0]):
            all_keypoints[k, 0] = (all_keypoints[k, 0] * STRIDE / UPSAMPLE
                                   - pad[1]) / scale
            all_keypoints[k, 1] = (all_keypoints[k, 1] * STRIDE / UPSAMPLE
                                   - pad[0]) / scale

        people: list[dict] = []
        for n in range(len(pose_entries)):
            entry = pose_entries[n]
            if len(entry) == 0:
                continue
            pts: dict[int, tuple[float, float, float]] = {}
            for kpt_id in range(NUM_KPTS):
                j = int(entry[kpt_id])
                if j < 0 or j >= all_keypoints.shape[0]:
                    continue
                x, y = float(all_keypoints[j, 0]), float(all_keypoints[j, 1])
                if not (0 <= x < img_w and 0 <= y < img_h):
                    continue                        # 画面外的点没有意义
                sc = float(all_keypoints[j, 2]) if all_keypoints.shape[1] > 2 else 1.0
                pts[kpt_id] = (x, y, sc)
            if pts:
                score = float(entry[NUM_KPTS]) if len(entry) > NUM_KPTS else 0.0
                people.append({"pts": pts, "score": score})

        people.sort(key=lambda p: p["score"], reverse=True)   # 最可信的人排前面
        return people

    def close(self) -> None:
        self._net = None
        self.ok = False
