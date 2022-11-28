# coding: utf-8

__doc__ = """包含 pyinstaller 工具相关的类或函数。"""

import os
from subprocess import *

from __info__ import *
from PyQt5.QtCore import *
from settings import *

from utils.main import get_cmd_out


class PyiTool(QObject):
    STARTUP = STARTUPINFO()
    STARTUP.dwFlags = STARTF_USESHOWWINDOW
    STARTUP.wShowWindow = SW_HIDE
    stdout = pyqtSignal(str)
    run_time = pyqtSignal(int)
    completed = pyqtSignal(int)

    def __init__(self, py_path="", cwd=os.getcwd()):
        super().__init__()
        self.__pypath = None
        self.__cwd = None
        self.__process = None
        self.__commands = None
        self.initialize(py_path, cwd)
        self.cumulative = -200
        self.__qtimer = QTimer()
        self.__qtimer.timeout.connect(self.__time)
        self.run_time.connect(self.__timer_control)
        self.__log_level = "INFO"

    @property
    def cwd(self):
        return self.__cwd

    @cwd.setter
    def cwd(self, path):
        if os.path.isdir(path):
            self.__cwd = path

    @property
    def pyi_path(self):
        """返回给出的 Python 路径中的 Pyinstaller 可执行文件路径。"""
        pyi_exec_path = os.path.join(self.__pypath, "Scripts", "pyinstaller.exe")
        if not os.path.isfile(pyi_exec_path):
            return ""
        return pyi_exec_path

    @property
    def pyi_ready(self):
        """给出的 Python 环境中安装了 Pyinstaller 返回 True，否则返回 False。"""
        return bool(self.pyi_path)

    def initialize(self, py_path, cwd):
        # 信任传入的 py_path
        self.__pypath = py_path
        self.__cwd = cwd if cwd else None
        self.__process = None
        self.__commands = [self.pyi_path]

    def __time(self):
        if self.cumulative > 10000:
            self.cumulative = 0
        self.cumulative += 10

    def __timer_control(self, code):
        if code:
            self.__qtimer.start(10)
        else:
            self.__qtimer.stop()
            self.cumulative = -200

    def __line_division_emit(self):
        while self.__process.poll() is None:
            try:
                line = self.__process.stdout.readline()
                if line is not None:
                    line = line.strip(os.linesep)
                    if line:
                        self.stdout.emit(line)
            except Exception as e:
                self.stdout.emit(f"[{NAME}] 信息流读取异常(不影响打包)：\n    {e}")
        self.completed.emit(self.__process.wait())

    def __time_division_emit(self):
        self.run_time.emit(1)
        lines = list()
        while self.__process.poll() is None:
            try:
                line = self.__process.stdout.readline()
                if line is not None:
                    line = line.strip(os.linesep)
                    if line:
                        lines.append(line)
                if self.cumulative > 100:
                    self.stdout.emit("\n".join(lines))
                    lines.clear()
                    self.cumulative = 0
            except Exception as e:
                self.stdout.emit(f"[{NAME}] 信息流读取异常(不影响打包)：\n    {e}")
        if lines:
            self.stdout.emit("\n".join(lines))
        self.run_time.emit(0)
        self.completed.emit(self.__process.wait())

    def execute_cmd(self):
        """执行命令并读取输出流，通过信号发射字符串、返回码更新主界面面板。"""
        self.__process = Popen(
            self.__commands,
            stdin=PIPE,
            stdout=PIPE,
            stderr=STDOUT,
            startupinfo=self.STARTUP,
            text=True,
            cwd=self.__cwd,
        )
        if self.pyi_ready and self.__process:
            if self.__log_level == "TRACE":
                self.__time_division_emit()
            else:
                self.__line_division_emit()
        else:
            if not self.pyi_ready:
                self.stdout.emit("当前环境中找不到 pyinstaller.exe。")
            if self.__process is None:
                self.stdout.emit("创建打包进程失败，无法完成程序打包。")
            self.completed.emit(-1)

    @staticmethod
    def __generate_infofile(verinfo_dict):
        version_info = """# coding: utf-8
VSVersionInfo(
ffi=FixedFileInfo(
filevers=$filevers$,
prodvers=$prodvers$,
mask=0x3F,
flags=0x0,
OS=0x40004,
fileType=0x1,
subtype=0x0,
date=(0, 0),
),
kids=[StringFileInfo(
[StringTable(
"080404b0",
[
StringStruct("CompanyName", "$CompanyName$"),
StringStruct("FileDescription", "$FileDescription$"),
StringStruct("FileVersion", "$FileVersion$"),
StringStruct("LegalCopyright", "$LegalCopyright$"),
StringStruct("OriginalFilename", "$OriginalFilename$"),
StringStruct("ProductName", "$ProductName$"),
StringStruct("ProductVersion", "$ProductVersion$"),
StringStruct("LegalTrademarks", "$LegalTrademarks$"),
],)]),
VarFileInfo([VarStruct("Translation", [2052, 1200])]),
],
)
"""
        file_path = os.path.join(config_root, "VERSOIN_INFO")
        for key, val in verinfo_dict.items():
            version_info = version_info.replace(key, val)
        try:
            with open(file_path, "wt", encoding="utf-8") as f:
                f.write(version_info)
        except Exception:
            file_path = ""
        return file_path

    def pyi_info(self):
        if self.pyi_ready:
            return get_cmd_out(self.pyi_path, "-v")
        return "0.0.0"

    def prepare_cmds(self, commands: PyiConfigure):
        """从 commands 添加 PyInstaller 命令选项。"""
        self.__log_level = commands.log_level
        if commands.onedir_bundle:
            self.__commands.append("-D")
        else:
            self.__commands.append("-F")
        if commands.spec_dir:
            self.__commands.extend(("--specpath", commands.spec_dir))
        if commands.bundle_spec_name:
            self.__commands.extend(("-n", commands.bundle_spec_name))
        for data in commands.other_datas:
            self.__commands.extend(("--add-data", rf"{data[0]};{data[1]}"))
        for module_path in commands.module_paths:
            self.__commands.extend(("-p", module_path))
        if commands.encryption_key:
            self.__commands.extend(("--key", commands.encryption_key))
        debug_options = commands.debug_options
        for option in debug_options:
            if debug_options[option]:
                self.__commands.extend(("--debug", option))
        if commands.donot_use_upx:
            self.__commands.append("--noupx")
        for binary in commands.upx_excludes:
            self.__commands.extend(("--upx-exclude", binary.lower()))
        if commands.provide_console:
            self.__commands.append("-c")
        else:
            self.__commands.append("-w")
        if commands.upx_dir:
            self.__commands.extend(("--upx-dir", commands.upx_dir))
        if commands.icon_path:
            self.__commands.extend(("-i", commands.icon_path))
        if commands.distribution_dir:
            self.__commands.extend(("--distpath", commands.distribution_dir))
        if commands.working_dir:
            self.__commands.extend(("--workpath", commands.working_dir))
        info_path = self.__generate_infofile(commands.version_info)
        if commands.add_verfile and info_path:
            self.__commands.extend(("--version-file", info_path))
        if commands.runtime_tmpdir:
            self.__commands.extend(("--runtime-tmpdir", commands.runtime_tmpdir))
        if commands.no_confirm:
            self.__commands.append("-y")
        if commands.clean_building:
            self.__commands.append("--clean")
        for imp in commands.hidden_imports:
            self.__commands.extend(("--hidden-import", imp))
        for mod in commands.exclude_modules:
            self.__commands.extend(("--exclude-module", mod))
        if commands.uac_admin:
            self.__commands.append("--uac-admin")
        self.__commands.extend(("--log-level", self.__log_level))
        self.__commands.append(commands.script_path)
