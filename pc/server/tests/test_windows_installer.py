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
    env_copy = config_block.index('File /nonfatal "${CONFIG_DIR}/.env"')
    config_copy = config_block.index('File /r "${CONFIG_DIR}/*.*"')
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
