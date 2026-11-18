"""本机 nginx 进程适配器。

Windows：nginx 以控制台进程常驻，必须用 DETACHED_PROCESS 启动，停止用 `nginx -s stop`。
Linux：nginx 自身守护化，直接 run 即可，停止同样走 `-s stop`。
"""

import os
import subprocess
import sys
import time

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
                    return OpResult(True, f"nginx 已启动，master PID {pid}", pid=pid, running=True)
                # 启动失败时进程可能已退出
                code = proc.poll()
                return OpResult(False, f"nginx 启动失败（进程退出码 {code}），请查看 error.log", code, running=False)
            proc = run_command(self._args(), cwd=self.prefix, timeout=20)
            if not proc.ok:
                return proc
            pid = self.wait_pid(6.0)
            if pid:
                return OpResult(True, f"nginx 已启动，master PID {pid}", 0, pid=pid, running=True)
            return OpResult(False, "nginx 启动命令已执行，但未检测到 pid 文件", 0, running=False)
        except FileNotFoundError:
            return OpResult(False, f"找不到 nginx 可执行文件: {self.binary}", 127)
        except OSError as exc:
            return OpResult(False, f"启动失败: {exc}", -1)

    def start(self) -> OpResult:
        st = self.status()
        if st.running:
            return OpResult(True, f"nginx 已在运行（PID {st.pid}）", pid=st.pid, running=True)
        return self._spawn()

    def stop(self) -> OpResult:
        st = self.status()
        if not st.running:
            return OpResult(True, "nginx 未在运行", running=False)
        res = run_command(self._args("-s", "stop"), cwd=self.prefix, timeout=30)
        pid = st.pid
        deadline = time.time() + 12
        while time.time() < deadline:
            if not pid_alive(pid or 0):
                return OpResult(True, "nginx 已停止", 0, running=False)
            time.sleep(0.2)
        return OpResult(False, "停止超时，进程仍在运行", res.exit_code, running=True)

    def reload(self) -> OpResult:
        st = self.status()
        if not st.running:
            return OpResult(False, "nginx 未运行，无法 reload", running=False)
        test = self.test()
        if not test.ok:
            return OpResult(False, "配置校验失败，未执行 reload\n" + test.output, test.exit_code, running=True)
        res = run_command(self._args("-s", "reload"), cwd=self.prefix, timeout=30)
        time.sleep(0.6)
        st2 = self.status()
        if not st2.running:
            return OpResult(False, "reload 后 nginx 未在运行，请检查 error.log\n" + res.output, res.exit_code, running=False)
        return OpResult(res.ok, ("reload 成功" if res.ok else "reload 失败") + (("\n" + res.output) if res.output else ""), res.exit_code, pid=st2.pid, running=True)

    def restart(self) -> OpResult:
        stop = self.stop()
        if not stop.ok:
            return stop
        return self.start()