import os
import subprocess
import sys
from pathlib import Path

import servicemanager
import win32event
import win32service
import win32serviceutil


class MilkWeighBackendService(win32serviceutil.ServiceFramework):
    _svc_name_ = "MilkWeighBackend"
    _svc_display_name_ = "乍甸乳业辅料防错追溯系统后台服务"
    _svc_description_ = "提供局域网 API、数据库和浏览器管理界面。"

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process: subprocess.Popen[bytes] | None = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self._stop_backend()

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("MilkWeigh backend service starting")
        self._run_backend()

    def _paths(self):
        install_root = Path(sys.executable).resolve().parent.parent
        program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
        return (
            install_root,
            program_data / "MilkWeigh" / "config",
            program_data / "MilkWeigh" / "data",
            program_data / "MilkWeigh" / "logs",
        )

    # 后端异常退出后的自愈：最多重试 RESTART_LIMIT 次，间隔逐次拉长。
    # 原实现是直接 break，服务以"干净停止"（退出码 0）结束 —— 既不触发 sc failure 的
    # 自动重启，也不给任何人提示，于是表现为"装完打不开"却毫无动静（见 DEC-070）。
    RESTART_LIMIT = 3
    RESTART_BACKOFF_SECONDS = 5

    def _start_backend(self, log_stream=None):
        install_root, config_dir, data_dir, log_dir = self._paths()
        config_dir.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["MILK_DATA_DIR"] = str(data_dir)
        env["PYTHONPATH"] = str(install_root / "server")
        python_exe = install_root / "python" / "python.exe"
        server_dir = install_root / "server"
        if log_stream is None:
            log_stream = open(log_dir / "backend-service.log", "ab", buffering=0)
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            [
                str(python_exe),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8011",
                "--app-dir",
                str(server_dir),
            ],
            cwd=str(config_dir),
            env=env,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
        )
        return log_stream

    def _run_backend(self):
        log_stream = self._start_backend()
        failures = 0
        try:
            while True:
                if win32event.WaitForSingleObject(self.stop_event, 2000) == win32event.WAIT_OBJECT_0:
                    return
                if self.process is not None and self.process.poll() is not None:
                    exit_code = self.process.returncode
                    servicemanager.LogErrorMsg(
                        f"MilkWeigh backend exited unexpectedly with code {exit_code}"
                    )
                    failures += 1
                    if failures > self.RESTART_LIMIT:
                        # 抛异常使 SCM 收到非零退出码，从而触发 sc failure 的自动重启
                        # （win32serviceutil.SvcRun 的注释明确说明该行为）。
                        raise RuntimeError(
                            f"MilkWeigh backend failed {failures} times "
                            f"(last exit code {exit_code}); "
                            "see backend-service.log for the traceback"
                        )
                    wait_seconds = self.RESTART_BACKOFF_SECONDS * failures
                    servicemanager.LogInfoMsg(
                        f"Restarting MilkWeigh backend in {wait_seconds}s "
                        f"(attempt {failures}/{self.RESTART_LIMIT})"
                    )
                    if (
                        win32event.WaitForSingleObject(self.stop_event, wait_seconds * 1000)
                        == win32event.WAIT_OBJECT_0
                    ):
                        return
                    log_stream = self._start_backend(log_stream)
        finally:
            self._stop_backend()
            log_stream.close()
            servicemanager.LogInfoMsg("MilkWeigh backend service stopped")

    def _stop_backend(self):
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(MilkWeighBackendService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(MilkWeighBackendService)
