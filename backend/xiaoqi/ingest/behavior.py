"""电脑前台应用行为采集（W10 · 主责成员 C）—— Windows 走 pywin32，Linux X11 走 XGetInputFocus，
Wayland 下方案未定（D-015 / P10）。

M1 不做，这里只留接口形状 —— 产出 BehaviorEvent 走 hub.publish_threadsafe，
与姿态链完全独立：这条挂了，另两条照常工作。
"""
from __future__ import annotations

import logging
import threading

from ..hub import Hub

log = logging.getLogger("xiaoqi.behavior")


class BehaviorWatcher(threading.Thread):
    """轮询前台窗口 → active_app / session_sec / level（ok|warn|alert）。"""

    def __init__(self, hub: Hub, warn_sec: int = 1800, alert_sec: int = 3600) -> None:
        super().__init__(daemon=True, name="xiaoqi-behavior")
        self.hub = hub
        self.warn_sec, self.alert_sec = warn_sec, alert_sec
        self._stop_event = threading.Event()   # 不叫 _stop：会覆盖 Thread 内部方法
        # TODO(W10)：前台窗口采集 —— Windows 用 pywin32 GetForegroundWindow + psutil 进程名；
        # Linux X11 用 XGetInputFocus / xdotool；本机是 Wayland，X11 那套直接不可用，
        # 只能走 xdg-desktop-portal 或退化成进程活跃度估算（方案未定，见 D-015 / P10）
        # TODO：同一应用 session_sec 累计、切窗重置、按阈值定 level

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        log.info("行为采集线程：W10 未实现，本链路保持静默（capabilities 不含 behavior）")
        while not self._stop_event.is_set():
            self._stop_event.wait(5.0)
