"""进程适配器公共部分。"""

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List, Optional

from ...core.i18n import t


@dataclass
class OpResult:
    ok: bool
    output: str = ""
    exit_code: Optional[int] = None
    pid: Optional[int] = None
    running: Optional[bool] = None


@dataclass
class Status:
    running: bool
    pid: Optional[int] = None
    detail: str = ""


@dataclass
class InstanceTarget:
    id: int
    name: str
    binary: str
    prefix: str
    conf_path: str
    run_mode: str = "local"
    systemd_unit: str = ""

    @property
    def conf_abs(self) -> str:
        return self.conf_path if os.path.isabs(self.conf_path) else os.path.join(self.prefix, self.conf_path)

    @property
    def pid_path(self) -> str:
        return os.path.join(self.prefix, "logs", "nginx.pid")


def decode_output(data: bytes) -> str:
    if not data:
        return ""
    for enc in ("utf-8", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def resolve_binary(binary: str) -> str:
    binary = (binary or "nginx").strip().strip('"')
    if os.path.isabs(binary):
        return binary
    found = shutil.which(binary)
    if found:
        return found
    if sys.platform == "win32" and not binary.lower().endswith(".exe"):
        found = shutil.which(binary + ".exe")
        if found:
            return found
    return binary


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) == 0:
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_pid(path: str) -> Optional[int]:
    try:
        with open(path, "r", encoding="ascii", errors="ignore") as fh:
            value = fh.read().strip()
        return int(value) if value.isdigit() else None
    except OSError:
        return None


class ProcessAdapter:
    def status(self) -> Status:
        raise NotImplementedError

    def test(self) -> OpResult:
        raise NotImplementedError

    def start(self) -> OpResult:
        raise NotImplementedError

    def stop(self) -> OpResult:
        raise NotImplementedError

    def reload(self) -> OpResult:
        raise NotImplementedError

    def restart(self) -> OpResult:
        raise NotImplementedError

    # 辅助：等待 pid 文件出现
    def wait_pid(self, timeout: float = 8.0, interval: float = 0.15) -> Optional[int]:
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            pid = read_pid(self.pid_file())
            if pid and pid_alive(pid):
                return pid
            time.sleep(interval)
        return None

    def pid_file(self) -> str:
        return self._pid_file

    def _read_status_from_pid(self) -> Status:
        pid = read_pid(self._pid_file)
        if pid and pid_alive(pid):
            return Status(True, pid, t("process.running"))
        return Status(False, None, t("process.stopped"))


def run_command(args: List[str], cwd: Optional[str] = None, timeout: int = 20) -> OpResult:
    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        output = (decode_output(proc.stdout) + decode_output(proc.stderr)).strip()
        return OpResult(proc.returncode == 0, output, proc.returncode)
    except FileNotFoundError:
        return OpResult(False, t("process.command_missing", name=args[0]), 127)
    except subprocess.TimeoutExpired:
        return OpResult(False, t("process.timeout"), -1)
    except OSError as exc:
        return OpResult(False, t("process.exec_failed", error=exc), -1)