"""摄像头打开与诊断的唯一出口（Linux 与 Windows 共用同一套实现）。

为什么集中：抽检链（`spot_check.py`）和实时链（`camera.py`）都要开摄像头，平台差异**只有**
「先试哪个 backend」这一点。散落成各写一遍 `cv2.VideoCapture(idx)`，会让 Windows 组员的机器
和 Linux 开发机走不同后端、报不同措辞的错，联调时对不上号。

铁律：**`CAP_*` 常量只允许出现在本文件**。别处要从这里拿 cap，不要就地写平台分支。
"""
from __future__ import annotations

import logging
import sys

log = logging.getLogger("xiaoqi.camera")

_IS_WIN = sys.platform.startswith("win")


def _backend_order():
    """本平台优先后端 → 通用兜底，返回 [(backend, tag), ...]。"""
    import cv2

    if _IS_WIN:
        # DSHOW 在 Windows 上最稳；MSMF 对个别 USB 摄像头握手更慢，放第二位
        return ((cv2.CAP_DSHOW, "DSHOW"), (cv2.CAP_MSMF, "MSMF"), (cv2.CAP_ANY, "ANY"))
    return ((cv2.CAP_V4L2, "V4L2"), (cv2.CAP_ANY, "ANY"))


def open_capture(index: int, width: int | None = None, height: int | None = None):
    """按平台顺序打开摄像头，返回 `(cap, tag, err)`；打不开时 `cap is None`。"""
    import cv2

    for backend, tag in _backend_order():
        try:
            cap = cv2.VideoCapture(index, backend)
        except Exception as e:                      # 极少见：驱动层直接抛
            log.warning("摄像头打开异常（%s）：%s", tag, e)
            continue
        if cap.isOpened():
            if width:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            if height:
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            log.info("摄像头已打开 #%s（%s）", index, tag)
            return cap, tag, None
        cap.release()
    return None, None, capture_error_hint(index)


def capture_error_hint(index: int) -> str:
    """打不开时的可读原因：平台不同，能做的动作也不同。"""
    if _IS_WIN:
        return (
            f"摄像头 #{index} 打不开。常见原因：\n"
            "    1) 设备未连接或被禁用（设备管理器里看不到）；\n"
            "    2) 已被其它程序占用（相机 App / 会议软件 / 其它调试进程）；\n"
            "    3) Windows 设置 → 隐私 → 相机，未允许桌面应用访问。")
    return (
        f"摄像头 #{index}（/dev/video{index}）打不开。常见原因：\n"
        "    1) 设备不存在：`v4l2-ctl --list-devices` 里看不到这个编号；\n"
        "    2) 已被其它程序占用（会议页面 / 相机 App / 另一条采集线程）；\n"
        "    3) 权限不足：当前用户不在 video 组（`sudo usermod -aG video $USER` 后重新登录）。")
