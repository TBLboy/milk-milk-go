"""内置签发公钥。

交付物只包含公钥；私钥（seed）仅存在于开发方签发环境（见 .secrets/license-issuer.seed）。

``MILK_LICENSE_PUBLIC_KEY`` 可用于开发与测试覆盖（生产不应设置）。
"""

from __future__ import annotations

import os

# 与 .secrets/license-issuer.seed 配对；轮换私钥时必须同步更新。
DEFAULT_PUBLIC_KEY_HEX = "400839b8919f2c5a522b13ae31a9bbc91e45838fe3ef6d5816da41a06b46aed0"


def public_key() -> bytes:
    """返回 32 字节公钥。

    安全约束：**不读取任何环境变量**。交付物中的公钥必须不可被运行期替换，
    否则客户只需设置一个环境变量并自签授权即可整体绕过授权机制（见 ALIGN-015/F3）。
    测试需要替换公钥时，用 monkeypatch 覆盖 ``DEFAULT_PUBLIC_KEY_HEX`` 模块常量。
    """
    key = bytes.fromhex(DEFAULT_PUBLIC_KEY_HEX)
    if len(key) != 32:
        raise ValueError("授权公钥必须是 32 字节")
    return key
