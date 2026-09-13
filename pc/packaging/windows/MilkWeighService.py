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
    _svc_display_name_ = "牧衡辅料称重防错系统后台服务"
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

    def _start_backend(self):
        install_root, config_dir, data_dir, log_dir = self._paths()
        config_dir.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["MILK_DATA_DIR"] = str(data_dir)
        env["PYTHONPATH"] = str(install_root / "server")
        python_exe = install_root / "python" / "python.exe"
        server_dir = install_root / "server"
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
        try:
            while True:
                if win32event.WaitForSingleObject(self.stop_event, 2000) == win32event.WAIT_OBJECT_0:
                    break
                if self.process is not None and self.process.poll() is not None:
                    servicemanager.LogErrorMsg(
                        f"MilkWeigh backend exited unexpectedly with code {self.process.returncode}"
                    )
                    break
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
