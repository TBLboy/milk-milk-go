from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.config import get_settings
from app.services.restore import RestoreError, restore_complete_backup


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从牧衡完整备份包恢复数据库、证据和运行配置。")
    parser.add_argument("--backup", required=True, type=Path, help="完整备份 ZIP 文件路径")
    parser.add_argument("--expected-sha256", help="可选的备份包 SHA-256 值")
    parser.add_argument("--yes", action="store_true", help="跳过交互式确认，供受控恢复脚本调用")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.yes:
        print("恢复会替换当前数据库和证据文件。系统会在替换前自动创建当前状态备份。")
        confirmation = input("输入 RESTORE 继续：").strip()
        if confirmation != "RESTORE":
            print("已取消恢复。")
            return 1

    try:
        result = restore_complete_backup(
            args.backup,
            get_settings(),
            expected_checksum=args.expected_sha256,
        )
    except RestoreError as exc:
        print(f"恢复失败：{exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "status": "success",
                "backup": str(result.archive_path),
                "pre_restore_backup": str(result.pre_restore_backup) if result.pre_restore_backup else None,
                "users": result.users,
                "work_orders": result.work_orders,
                "evidence_files": result.evidence_files,
                "restored_at": result.restored_at.isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
