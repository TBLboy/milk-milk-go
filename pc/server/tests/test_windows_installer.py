from pathlib import Path


def test_windows_installer_preserves_existing_configuration():
    pc_root = Path(__file__).resolve().parents[2]
    installer = (pc_root / "packaging" / "windows" / "installer.nsi").read_text(
        encoding="utf-8"
    )

    config_block_start = installer.index(
        'SetOutPath "$COMMONPROGRAMDATA\\MilkWeigh\\config"'
    )
    config_block_end = installer.index(
        'CreateDirectory "$COMMONPROGRAMDATA\\MilkWeigh\\data"',
        config_block_start,
    )
    config_block = installer[config_block_start:config_block_end]

    overwrite_off = config_block.index("SetOverwrite off")
    env_copy = config_block.index('File /nonfatal "${CONFIG_ENV}"')
    config_copy = config_block.index('File /r "${CONFIG_GLOB}"')
    overwrite_on = config_block.index(
        "SetOverwrite on",
        config_copy,
    )

    assert overwrite_off < env_copy < config_copy < overwrite_on


def test_windows_installer_runs_bounded_smtp_self_test_after_service_start():
    pc_root = Path(__file__).resolve().parents[2]
    installer = (pc_root / "packaging" / "windows" / "installer.nsi").read_text(
        encoding="utf-8"
    )
    build_script = (pc_root / "scripts" / "build-windows-installer.sh").read_text(
        encoding="utf-8"
    )

    service_start = installer.index('"${SERVICE_SCRIPT}" start')
    smtp_test = installer.index('"$INSTDIR\\server\\smtp_test.py"', service_start)
    failure_warning = installer.index("邮件反馈自检失败", smtp_test)
    smtp_command_start = installer.rfind(
        "nsExec::ExecToLog /TIMEOUT=15000",
        service_start,
        smtp_test,
    )
    warning_line_start = installer.rfind("MessageBox", smtp_test, failure_warning)
    smtp_block = installer[smtp_command_start:warning_line_start]

    assert "/TIMEOUT=15000" in smtp_block
    assert "MessageBox" in installer[warning_line_start : warning_line_start + 300]
    assert "Abort" not in installer[smtp_command_start : warning_line_start + 300]
    assert (
        'cp "$PC_DIR/packaging/windows/smtp_test.py" '
        '"$PAYLOAD_DIR/server/smtp_test.py"'
    ) in build_script


def test_windows_installer_ships_no_demo_or_test_data():
    """交付包必须保持干净：不打包演示素材，也不在安装时灌入演示数据。

    演示种子（pc/server/seed.py 与 pc/packaging/windows/seed_install.py）只作为
    开发期工具保留在仓库中；安装包与安装流程都不得引用它们。
    """
    pc_root = Path(__file__).resolve().parents[2]
    build_script = (pc_root / "scripts" / "build-windows-installer.sh").read_text(
        encoding="utf-8"
    )
    installer = (pc_root / "packaging" / "windows" / "installer.nsi").read_text(
        encoding="utf-8"
    )

    # 只检查可执行内容，忽略注释（注释里会说明这些工具为何不再打包）
    script_code = "\n".join(
        line
        for line in build_script.splitlines()
        if not line.lstrip().startswith("#")
    )

    assert "DEMO_MATERIAL_IMAGE_IDS" not in script_code
    assert "demo_assets" not in script_code
    assert '"FILE-' not in script_code
    assert "seed" not in script_code

    assert "seed" not in installer
    assert "demo" not in installer


def test_windows_installer_offers_backup_path_page():
    pc_root = Path(__file__).resolve().parents[2]
    installer = (pc_root / "packaging" / "windows" / "installer.nsi").read_text(
        encoding="utf-8"
    )

    assert 'Page custom BackupPathPageCreate BackupPathPageLeave' in installer
    assert 'nsDialogs::SelectFolderDialog' in installer
    assert 'backup_path.conf' in installer
    assert '!include "nsDialogs.nsh"' in installer
    assert '!include "LogicLib.nsh"' in installer


def test_windows_installer_selects_path_separator_per_platform():
    """The Windows build of makensis rejects "/" separators in File directives.

    installer.nsi therefore defines the payload/config paths and their globs once
    per platform and the section consumes only those defines.
    """
    pc_root = Path(__file__).resolve().parents[2]
    installer = (pc_root / "packaging" / "windows" / "installer.nsi").read_text(
        encoding="utf-8"
    )
    build_script = (pc_root / "scripts" / "build-windows-installer.sh").read_text(
        encoding="utf-8"
    )

    assert "!ifdef WIN" in installer
    for define in (
        "PAYLOAD_DIR",
        "CONFIG_DIR",
        "PAYLOAD_GLOB",
        "CONFIG_GLOB",
        "CONFIG_ENV",
    ):
        assert installer.count("!define %s " % define) == 2, define

    assert '!define PAYLOAD_GLOB "${PAYLOAD_DIR}\\*.*"' in installer
    assert '!define PAYLOAD_GLOB "${PAYLOAD_DIR}/*.*"' in installer

    assert 'File /r "${PAYLOAD_GLOB}"' in installer
    assert 'File /nonfatal "${CONFIG_ENV}"' in installer
    assert 'File /r "${CONFIG_GLOB}"' in installer

    # installer.nsi is UTF-8 without a BOM, so the charset must be stated
    # explicitly; on Windows the paths must be Windows-style and -DWIN must be
    # passed so the backslash branch above is compiled in.
    assert "-INPUTCHARSET UTF8" in build_script
    assert 'MAKENSIS_PLATFORM="-DWIN"' in build_script
    assert "cygpath -w" in build_script
