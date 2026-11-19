"""本机 nginx 进程适配器。

Windows：nginx 以控制台进程常驻，必须用 DETACHED_PROCESS 启动，停止用 `nginx -s stop`。
Linux：nginx 自身守护化，直接 run 即可，停止同样走 `-s stop`。
"""

import os
import subprocess
import sys
import time

from ...core.i18n import t
from .base import InstanceTarget, OpResult, ProcessAdapter, Status, pid_alive, read_pid, resolve_binary, run_command


class LocalAdapter(ProcessAdapter):
    def __init__(self, target: InstanceTarget, pid_file: str):
        self.target = target
        self.prefix = target.prefix
        self.binary = resolve_binary(target.binary)
        self._pid_file = pid_file

    def _args(self, *extra: str):
        return [self.binary, "-p", self.prefix, "-c", self.target.conf_abs, *extra]

    def status(self) -> Status:
        return self._read_status_from_pid()

    def test(self) -> OpResult:
        return run_command([self.binary, "-t", "-p", self.prefix, "-c", self.target.conf_abs], cwd=self.prefix, timeout=30)

    def _spawn(self) -> OpResult:
        try:
            if sys.platform == "win32":
                DETACHED_PROCESS = 0x00000008
                CREATE_NEW_PROCESS_GROUP = 0x00000200
                proc = subprocess.Popen(
                    self._args(),
                    cwd=self.prefix,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                )
                pid = self.wait_pid(6.0)
                if pid:
                    return OpResult(True, t("process.started", pid=pid), pid=pid, running=True)
                # 启动失败时进程可能已退出
                code = proc.poll()
                return OpResult(False, t("process.start_failed_exit", code=code), code, running=False)
            proc = run_command(self._args(), cwd=self.prefix, timeout=20)
            if not proc.ok:
                return proc
            pid = self.wait_pid(6.0)
            if pid:
                return OpResult(True, t("process.started", pid=pid), 0, pid=pid, running=True)
            return OpResult(False, t("process.pid_missing"), 0, running=False)
        except FileNotFoundError:
            return OpResult(False, t("process.binary_missing", path=self.binary), 127)
        except OSError as exc:
            return OpResult(False, t("process.start_error", error=exc), -1)

    def start(self) -> OpResult:
        st = self.status()
        if st.running:
            return OpResult(True, t("process.already_running", pid=st.pid), pid=st.pid, running=True)
        return self._spawn()

    def stop(self) -> OpResult:
        st = self.status()
        if not st.running:
            return OpResult(True, t("process.not_running"), running=False)
        res = run_command(self._args("-s", "stop"), cwd=self.prefix, timeout=30)
        pid = st.pid
        deadline = time.time() + 12
        while time.time() < deadline:
            if not pid_alive(pid or 0):
                return OpResult(True, t("process.stopped_ok"), 0, running=False)
            time.sleep(0.2)
        return OpResult(False, t("process.stop_timeout"), res.exit_code, running=True)

    def reload(self) -> OpResult:
        st = self.status()
        if not st.running:
            return OpResult(False, t("process.reload_not_running"), running=False)
        test = self.test()
        if not test.ok:
            return OpResult(False, t("process.test_failed_reload", output=test.output), test.exit_code, running=True)
        res = run_command(self._args("-s", "reload"), cwd=self.prefix, timeout=30)
        time.sleep(0.6)
        st2 = self.status()
        if not st2.running:
            return OpResult(False, t("process.reload_dead", output=res.output), res.exit_code, running=False)
        return OpResult(
            res.ok,
            (t("process.reload_ok") if res.ok else t("process.reload_failed")) + (("\n" + res.output) if res.output else ""),
            res.exit_code,
            pid=st2.pid,
            running=True,
        )

    def restart(self) -> OpResult:
        stop = self.stop()
        if not stop.ok:
            return stop
        return self.start()