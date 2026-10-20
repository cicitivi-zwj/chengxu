# MSDL · 微软官方镜像下载器

从微软官方接口取 Windows ISO 直链并下载的工具。功能和 `wrxz.exe`（那个 UPX + AutoIt 加壳的"微软系统直链下载"）  
的核心部分一致，但把它的三条风险全部拿掉了。

## 一、和原软件的功能对照

| 功能                                       | wrxz.exe                | MSDL                                                         |
| ---------------------------------------- | ----------------------- | ------------------------------------------------------------ |
| 微软官方 ISO 直链                              | ✅                       | ✅ 同样通过 `www.microsoft.com/software-download-connector` 官方接口取 |
| 版本列表                                     | 硬编码在混淆脚本里               | ✅ 实时读取微软下载页 HTML                                             |
| 语言列表                                     | 硬编码                     | ✅ 实时调 `getskuinformationbyproductedition`                    |
| 多线程下载                                    | aria2c（从作者网盘下载）         | ✅ 自己实现，1–16 线程，Range 分段                                      |
| 断点续传                                     | aria2c                  | ✅ 分片落盘 + `.msdl.json` 记录分段                                   |
| 完整性校验                                    | 只显示 SHA1（不校验）           | ✅ 下载完在本机算 SHA256                                             |
| 配置下发 ver.ini                             | ✅ 有                     | ❌ 没有                                                         |
| 自动更新 / 自我替换                              | ✅ 有（可投递任意 exe）          | ❌ 没有                                                         |
| 一键下载并运行 Chrome/Edge/AnyDesk/向日葵/GotoHTTP | ✅ 有                     | ❌ 没有                                                         |
| 需要管理员权限                                  | ✅ `#RequireAdmin`       | ❌ 不需要                                                        |
| 写注册表 / 计划任务 / 服务                         | 无                       | ❌ 无                                                          |
| 采集主机信息                                   | 无                       | ❌ 无                                                          |
| 第三方依赖                                    | 7z、aria2c、curl 全部从个人网盘拉 | ❌ 仅 Python 标准库                                               |

## 二、怎么用

**方式 A：直接双击 `MSDL.exe`**（推荐，无需安装 Python）

**方式 B：跑源码**

```bat
python msdl.py
```

步骤：

1. 选产品（Windows 11 / Windows 10）
2. 选版本（多版本 ISO / 家庭中文版 / 专业中文版，列表来自微软页面）
3. 选语言（默认简体中文）
4. 点「获取官方下载链接」——直链有效期约 24 小时
5. 选保存目录、线程数，点「开始下载」

下载过程中可随时「暂停」，再点「开始下载」会从断点续传（分片文件 `.partN` 会保留）。

## 三、命令行自检

```bat
MSDL.exe --selftest          :: 检查 Win11 链路（版本 / 语言 / 直链 / 大小）
MSDL.exe --selftest --all    :: Win11 + Win10 都检查
```

## 四、实现要点

- **官方接口三步调用**
  1. 从 `https://www.microsoft.com/zh-cn/software-download/windows11` 的 `#product-edition` 下拉框解析出版本 ID
  2. `getskuinformationbyproductedition` 取该版本下的语言与 SKU
  3. `GetProductDownloadLinksBySku`（带 `Referer`）取直链
- **风控握手**：微软要求 `sessionID` 先经过 `vlscppe.microsoft.com/tags` 与  
  `ov-df.microsoft.com`（mdt.js → 回传 w/rticks）白名单，否则返回  
  `Sentinel marked this request as rejected`。代码里按这个顺序复现。
- **双重 JSON**：微软部分接口返回的是被 JSON 再包一层的字符串，需要 `json.loads` 两次。
- **分段下载**：先 HEAD 拿 `Content-Length` 与 `Accept-Ranges`；支持且文件 > 32 MB 时按线程数切片，  
  每片写 `xxx.iso.partN`；单片中断按已写字节数续传；全部完成后按顺序合并。
- **限流保护**：同一 SKU 10 分钟内复用已取到的直链；遇 Sentinel 自动换新 session 重试 2 次。

## 五、文件

```
msdl.py          图形界面 + 自检入口
msdl_core.py     微软接口封装 + 多线程下载器（纯标准库）
MSDL.exe         打包好的单文件程序
```

## 六、已知限制

- 直链 24 小时过期，过期后重新点「获取官方下载链接」即可。
- 微软对同一 IP 有下载频次限制，短时间内反复请求会返回 `715-123130`，换网络或等待即可。
- 「获取直链」接口另有更严的频控（Sentinel）：同一镜像短时间内反复获取会被暂时拒绝，  
  程序会自动换新会话重试两次，仍被拒绝时给出明确中文提示，等待几分钟后即可恢复。
- 微软未公开这些 ISO 的官方哈希，程序显示的 SHA256 是**本机计算值**，仅用于自我记录与分发比对。
- 只覆盖 Windows 11 / Windows 10。Windows 8.1 及更早版本微软已下线该接口，无法通过它取直链。

## 七、自检实录（2026-10-20）

```
Windows 11 版本数: 3 -> [多版本 ISO / 家庭版(仅限中国) / 专业中文版本]
   语言数: 38 | 中文 SKU: 27157 | 构建: Windows 11 Client - Build 26300.9457
Windows 10 版本数: 1
   语言数: 38 | 中文 SKU: 16061 | 构建: Windows 10 22H2_v1
   直链: https://software.download.prss.microsoft.com/dbazure/Win10_22H2_Chines...
   大小: 4.06 GB | 分段支持: True | 文件名: Win10_22H2_Chinese_Simplified_x32v1.iso
```

Win11 直链在当天早些时候同样取到过（`Windows11_Client_x64_zh-cn_26300_9457.iso`，8.49 GB），  
后因测试期间反复请求触发了该 SKU 的临时频控。
