# 牧衡辅料称重防错系统 Android 1.0.3 测试包

## 版本

- 版本：`1.0.3`
- Android `versionCode`：`4`
- 变更：服务器设置中 IPv4 四段均可编辑，前两段默认 `192.168`
- Windows 安装包保持 `1.0.2`，本版本不修改 PC 代码

## 产物

- 文件：`发布版本/牧衡辅料称重防错系统-Android-1.0.3.apk`
- SHA-256：`326b35937e09b45aef0551caeedd074a67b5615f468195d166c19c980f15797d`
- 包名：`com.muheng.milkweigh`
- 签名：APK Signature Scheme v2、v3 通过
- 证书 SHA-256：`62898a2442b84ddd2e114e380ba33fed303b83d135e26aa408d3304b1900f204`

## 已验证

- Android Debug 构建和 Lint 通过。
- Android 15 模拟器打开服务器设置后显示四个 IPv4 输入字段，默认地址为 `192.168.1.100`。
- 发布 APK 构建成功，版本识别为 `1.0.3 / versionCode=4`。
- v2/v3 签名和 SHA-256 校验通过。

## 尚未验证

- 真实平板覆盖安装及原有服务器地址、账号和会话保留。
- 真实局域网连接测试。
