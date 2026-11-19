"""systemd 管理的 nginx 适配器（Linux）。"""

from ...core.i18n import t
from .base import InstanceTarget, OpResult, ProcessAdapter, Status, read_pid, run_command


class SystemdAdapter(ProcessAdapter):
    def __init__(self, target: InstanceTarget):
        self.target = target
        self.unit = target.systemd_unit or "nginx"
        self._pid_file = target.pid_path

    def _systemctl(self, *args: str):
        return run_command(["systemctl", *args, self.unit], timeout=40)

    def status(self) -> Status:
        res = run_command(["systemctl", "is-active", self.unit], timeout=15)
        active = res.output.strip().splitlines()[0] if res.output.strip() else "unknown"
        pid_res = run_command(["systemctl", "show", "-p", "MainPID", "--value", self.unit], timeout=15)
        pid = None
        if pid_res.output.strip().isdigit():
            value = int(pid_res.output.strip())
            pid = value if value > 0 else None
        if pid is None:
            pid = read_pid(self._pid_file)
        running = active == "active" or bool(pid)
        return Status(running, pid, active)

    def test(self) -> OpResult:
        # systemd 模式下仍用 nginx -t 做配置校验
        binary = self.target.binary or "nginx"
        return run_command(
            [binary, "-t", "-p", self.target.prefix, "-c", self.target.conf_abs], cwd=self.target.prefix, timeout=30
        )

    def start(self) -> OpResult:
        res = self._systemctl("start")
        st = self.status()
        return OpResult(res.ok and st.running, res.output or t("process.started_systemd"), res.exit_code, pid=st.pid, running=st.running)

    def stop(self) -> OpResult:
        res = self._systemctl("stop")
        st = self.status()
        return OpResult(res.ok and not st.running, res.output or t("process.stopped_systemd"), res.exit_code, running=st.running)

    def reload(self) -> OpResult:
        test = self.test()
        if not test.ok:
            return OpResult(False, t("process.test_failed_reload", output=test.output), test.exit_code)
        res = self._systemctl("reload")
        st = self.status()
        return OpResult(res.ok and st.running, res.output or t("process.reload_ok"), res.exit_code, pid=st.pid, running=st.running)

    def restart(self) -> OpResult:
        test = self.test()
        if not test.ok:
            return OpResult(False, t("process.test_failed_restart", output=test.output), test.exit_code)
        res = self._systemctl("restart")
        st = self.status()
        return OpResult(res.ok and st.running, res.output or t("process.restarted"), res.exit_code, pid=st.pid, running=st.running)