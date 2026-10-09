#!/usr/bin/env python
"""开发方授权签发工具（TASK-161 / DEC-063）。

**这个工具永远不随安装器交付。** 它需要签发私钥，只应在开发方机器上运行。

用法（在仓库根 `milk-milk-go` 下）：

    # 试用到期后给客户续期 1 年
    ..\\.venv\\Scripts\\python.exe pc\\scripts\\issue_license.py ^
        --licensee "乍甸乳业" --days 365

    # 指定到期日
    ..\\.venv\\Scripts\\python.exe pc\\scripts\\issue_license.py ^
        --licensee "乍甸乳业" --expires-at 2027-10-09

    # 永久授权（写入远期限）
    ..\\.venv\\Scripts\\python.exe pc\\scripts\\issue_license.py ^
        --licensee "乍甸乳业" --perpetual

    # 自检：用内置公钥验证一个解锁码是否有效
    ..\\.venv\\Scripts\\python.exe pc\\scripts\\issue_license.py --verify "<解锁码>"

私钥来源（按优先级）：
    1. 环境变量 ``MILK_LICENSE_ISSUER_SEED``
    2. ``--seed-file`` 指定的文件（默认 ``<项目根>/.secrets/license-issuer.seed``）

签发后请把输出的解锁码交给客户，由管理员在 PC 端「输入解锁码」处粘贴。
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
SERVER_DIR = REPO_ROOT / "pc" / "server"
DEFAULT_SEED_FILE = REPO_ROOT.parent / ".secrets" / "license-issuer.seed"

sys.path.insert(0, str(SERVER_DIR))

from milk_license import codec, keys  # noqa: E402

SEED_ENV = "MILK_LICENSE_ISSUER_SEED"
PERPETUAL_EXPIRES = datetime(2099, 12, 31, tzinfo=timezone.utc)


def load_seed(seed_file: Path | None) -> bytes:
    raw = os.environ.get(SEED_ENV, "").strip()
    if not raw:
        path = seed_file or DEFAULT_SEED_FILE
        if not path.is_file():
            raise SystemExit(
                f"未找到签发私钥：{path}\n"
                f"请设置环境变量 {SEED_ENV}，或用 --seed-file 指定文件。\n"
                "（私钥绝不能提交到仓库或随安装器交付。）"
            )
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(SEED_ENV + "="):
                raw = line.split("=", 1)[1].strip()
                break
    if not raw:
        raise SystemExit("签发私钥为空")
    try:
        seed = bytes.fromhex(raw)
    except ValueError:
        raise SystemExit("签发私钥不是合法的十六进制字符串")
    if len(seed) != 32:
        raise SystemExit(f"签发私钥必须是 32 字节（当前 {len(seed)} 字节）")
    return seed


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_payload(args: argparse.Namespace) -> dict:
    now = datetime.now(timezone.utc)
    if args.perpetual:
        expires = PERPETUAL_EXPIRES
    elif args.expires_at:
        try:
            parsed = datetime.fromisoformat(args.expires_at)
        except ValueError:
            raise SystemExit(f"--expires-at 不是合法日期：{args.expires_at}")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        expires = parsed.astimezone(timezone.utc)
    elif args.days:
        expires = now + timedelta(days=args.days)
    else:
        raise SystemExit("必须指定 --days、--expires-at 或 --perpetual 之一")
    if expires <= now:
        raise SystemExit(f"到期时间必须晚于当前时间（{iso(expires)}）")
    return {
        "v": codec.PAYLOAD_VERSION,
        "licensee": args.licensee,
        "issued_at": iso(now),
        "expires_at": iso(expires),
        "level": args.level,
    }


def verify(code: str) -> int:
    public = keys.public_key()
    try:
        payload = codec.decode_license(code, public)
    except codec.LicenseError as exc:
        print(f"[无效] {exc}")
        return 1
    expires = codec.expires_at(payload)
    now = datetime.now(timezone.utc)
    state = "已到期" if expires <= now else f"剩余 {(expires - now).days} 天"
    print("[有效]")
    print(f"  客户：{payload.get('licensee')}")
    print(f"  签发：{payload.get('issued_at')}")
    print(f"  到期：{payload.get('expires_at')}（{state}）")
    print(f"  级别：{payload.get('level')}")
    print(f"  公钥指纹：{public.hex()[:16]}…")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="开发方授权签发工具（不得随交付物分发）")
    parser.add_argument("--licensee", help="客户名称（写入授权内容，用于追责与展示）")
    parser.add_argument("--licensee-file", help="从 UTF-8 文件读取客户名称（避免控制台中文乱码）")
    parser.add_argument("--days", type=int, help="自当前时间起多少天到期")
    parser.add_argument("--expires-at", help="绝对到期日，如 2027-10-09")
    parser.add_argument("--perpetual", action="store_true", help="永久授权（写入远期限）")
    parser.add_argument("--level", default="full", help="授权级别（默认 full）")
    parser.add_argument("--seed-file", help=f"私钥文件路径（默认 {DEFAULT_SEED_FILE}）")
    parser.add_argument("--out", help="把解锁码写入文件（否则打印到标准输出）")
    parser.add_argument("--verify", metavar="CODE", help="仅验证一个解锁码，不签发")
    args = parser.parse_args(argv)

    if args.verify:
        return verify(args.verify)
    if args.licensee_file:
        path = Path(args.licensee_file)
        if not path.is_file():
            raise SystemExit(f"--licensee-file 不存在：{path}")
        args.licensee = path.read_text(encoding="utf-8").strip()
    if not args.licensee:
        parser.error("签发时必须提供 --licensee 或 --licensee-file")

    seed = load_seed(Path(args.seed_file) if args.seed_file else None)
    payload = build_payload(args)
    code = codec.issue_license(payload, seed)

    # 自检：用内置公钥立刻验一遍，避免签发出一张自己都解不开的授权
    try:
        codec.decode_license(code, keys.public_key())
    except codec.LicenseError as exc:
        raise SystemExit(f"自检失败，未输出解锁码：{exc}")

    if args.out:
        Path(args.out).write_text(code + "\n", encoding="utf-8")
        print(f"已写入：{args.out}")
    else:
        print(code)
    print("", file=sys.stderr)
    print("── 授权摘要 ──", file=sys.stderr)
    print(f"  客户：{payload['licensee']}", file=sys.stderr)
    print(f"  签发：{payload['issued_at']}", file=sys.stderr)
    print(f"  到期：{payload['expires_at']}", file=sys.stderr)
    print(f"  级别：{payload['level']}", file=sys.stderr)
    print("  请把上面的解锁码交给客户，由管理员在 PC 端「输入解锁码」处粘贴。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
