# EFT 任务助手

**给《逃离塔科夫》玩家的本地任务、地图与藏身处规划工具。**

从商人截图识别任务，逐项记录进度，把任务地点、钥匙和升级材料整理在一起。电脑管理任务，同一局域网的手机或平板扫码查看地图；无需注册账号。

[English](README.en.md) · [下载 Windows 版本](https://github.com/xxtra1112/eft-task-assistant/releases) · [反馈问题](https://github.com/xxtra1112/eft-task-assistant/issues)
[![CI](https://github.com/xxtra1112/eft-task-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/xxtra1112/eft-task-assistant/actions/workflows/ci.yml)

> 当前源码面向 **1.3.0 发布候选**。以 Releases 页实际提供的版本和资产为准，不把本地候选当作已发布版本。本项目为非官方社区工具，与 Battlestate Games 无关；请以游戏内要求为准。

## 能做什么

- **截图识别：** 浏览器授权读取这台电脑的游戏截图文件夹；本地 OCR 识别商人任务，自动加入清单，按截图顺序显示处理通知。未出现在截图中的任务不会被自动删除。
- **任务进度：** 每项要求独立勾选或计数，支持地图/商人筛选、隐藏、折叠、完成与操作撤销。
- **多来源地图：** 可切换 Tarkov.dev、EFTarkov 和 RE3MR，显示来源及限制；缩放、拖动、全屏、楼层切换和到访标记均保留。
- **路线与随身地图：** 路线可选颜色、粗细，按档案/来源/地图/楼层保存；配对手机可只读同步受支持来源的路线。平板为左地图、右任务列表。
- **钥匙与备料：** 汇总任务真正需要的钥匙；藏身处升级自动纳入前置设施，统计所需、已有和缺少的物品。货币不计入物品件数。
- **本机持久存档：** 任务、已提交的界面偏好及路线保存在同一台电脑；支持独立存档集、明确导入、冲突备份和回滚。

## 界面预览

以下是已有版本的隔离演示档案截图，**不是 1.3.0 新功能全量验收图**，不包含个人存档或游戏截图。界面支持中英文、明暗主题。

![电脑端任务工作区](https://raw.githubusercontent.com/xxtra1112/eft-task-assistant/main/docs/images/desktop-overview-zh.png)
![平板随身地图](https://raw.githubusercontent.com/xxtra1112/eft-task-assistant/main/docs/images/tablet-map-zh.png)
![手机随身地图](https://raw.githubusercontent.com/xxtra1112/eft-task-assistant/main/docs/images/mobile-map-zh.png)

## 安装与启动

1. 在 [Releases](https://github.com/xxtra1112/eft-task-assistant/releases) 下载 Windows x64 可执行文件，或下载对应便携 ZIP 并完整解压到新文件夹。
2. 直接运行下载或解压后的 EXE。**不需要安装 Python、Conda 或捕获助手。**
3. 保持程序运行，浏览器打开启动窗口显示的本机地址，通常为 `http://127.0.0.1:8765/`。默认端口占用时自动尝试后续端口；显式指定的端口冲突则报错，不会替你结束其他实例。
4. 首次输入档案名称，选择实际使用的游戏截图文件夹并授权读取。每位玩家在自己的电脑运行完整程序。
5. 核对识别结果，选择地图并规划任务。需要时在资料库手动同步、搜索或导入任务。

桌面管理只监听 `127.0.0.1`。程序尚未代码签名，请核对下载来源与 `SHA256SUMS.txt`，不要关闭系统防护。关闭程序窗口或按 `Ctrl+C` 会停止服务。

### 截图怎么来

在游戏中正常截图，再由电脑上的 Chrome/Edge 授权读取游戏的 `Screenshots` 文件夹。程序不会猜测固定的 Windows 用户路径，也不会读取其他设备的截图。支持 PNG、JPG/JPEG、WebP；最近识别记录最多保留 10 条。

OCR 在本机运行，不将截图发送给云端大模型。识别受语言、截图范围、分辨率和游戏界面更新影响；漏识别时可同步资料后搜索或手动添加。截图看不到某个任务不等于完成，删除/完成由玩家操作。

## 地图来源与适用范围

| 来源 | 用途与边界 |
| --- | --- |
| **Tarkov.dev** | 默认任务/地图来源，提供任务区域、地点、撤离/转移点及地图资源；藏身处和物品图标仍来自 Tarkov.dev |
| **EFTarkov** | 中文公开任务与地图资料；只使用此来源能核验的关联，不把名称相近当作同一个点位 |
| **RE3MR** | 官网明确链接且通过访问规则检查的高清参考原图，仅限桌面本机个人非商业查看；没有经校准的任务坐标，不叠加其他来源点位或路线，不向手机/LAN 返回原图字节 |

切换来源不会重新导入或覆盖任务，已导入任务保留自身来源和进度。无法核验点位时保留任务及说明，不编造坐标或拿任务封面充当现场图。PMC、SCAV、阵营未确认的撤离点分别显示，缺少证据时不推断阵营。

地图、任务和物品资料均可能不完整或过时，社区 API 没有声明覆盖每个游戏补丁；PvE、常规 PvP、赛季 PvP 以来源实际支持为准，不套用其他模式填补空缺。现场图和媒体许可见 [来源说明](docs/data-sources.md) 与 [第三方声明](THIRD_PARTY_NOTICES.md)。

### 后台缓存

启动默认后台预热所有允许来源，优先处理当前地图。下载并发最多 2、完整解码并发 1；磁盘上限 512 MiB 并使用 LRU。可取消、继续或重新预热，分别显示发现、命中、新下载、拦截、失败、预算待继续等状态。

**本轮完成不等于全部地图已下载，更不保证所有大图永久驻留。** robots、401/403 或规则核查失败时不绕过，也不能用旧缓存掩盖拒绝。

```powershell
.\EFTTaskAssistant-v1.3.0-Windows-x64.exe --no-preload
.\EFTTaskAssistant-v1.3.0-Windows-x64.exe --preload-budget-mib 32 --preload-max-assets 1
```

`--no-preload` 只关闭启动预热；按需和手动加载仍可用。两个预算参数均为整数 `1..512`，默认分别为 512 MiB 与 512 个新增资产。批次预算和磁盘容量分别计算。详见 [预热证据与限制](docs/preload-evidence.md)。

## 手机 / 平板

电脑和手机连接同一个可信局域网，在电脑端点击“手机地图二维码”并扫码。无需再次登录或下载证书。二维码有效两分钟且仅可使用一次；配对后手机仅有受限只读访问，可在手机端结束访问。

手机可以切换地图、楼层、缩放和沉浸显示；任务面板可拖动调整，平板自动采用分栏。受支持来源的路线同步见 [路线说明](docs/route-sync.md)。RE3MR 在手机仅显示来源链接和限制提示，不再托管原图。

若连接失败，确认同网并允许应用通过 Windows 防火墙的**专用网络**，不要开放公用网络或把端口转发到公网。可在电脑端选择实际网卡地址；不要向不信任的人分享二维码或已配对页面。

## 存档、升级与回滚

1.3.0 默认通过 Windows Known Folder 查询“保存的游戏”（Saved Games），通常为：

```text
%USERPROFILE%\Saved Games\EFTTaskAssistant
```

实际根以“存档与缓存”里的 `root` 为准。正式通道与独立预览通道分开；EXE 改名、搬移、换工作目录或端口不应另建空档。需要自定义根时才使用绝对路径 `--data-dir`。

首次发现旧根时，**先核对路径和任务计数，再明确选择来源**。迁移保留原库、备份和独立副本，不自动合并两份非空档案，也不按修改时间猜测哪份正确。导入的存档需另行选择下次启动使用。未来 schema、坏库或发现失败会明确停止/提示，不静默换空根。

已提交的钥匙回答、显隐、折叠、藏身处计划及材料数量保存在本机档案数据库，可供本机另一浏览器重新读取；共享路线也在本机服务端。截图目录授权、未提交的离线路线队列和部分临时缓存仍留在原浏览器。旧端口/主机名/origin 尚未上传的浏览器偏好，需要在原页面导出后明确导入，服务器无法凭空找回。

备份前正常关闭程序，再复制**完整存档根**，不要在运行中单独复制 SQLite 文件。备份可能含截图、历史记录和会话，请保密。回滚使用保留的旧 EXE 及其原数据根；不要让不支持新版 schema 的旧程序写入新 dataset，也不要降低 schema 号或删除冲突双方。新版新增进度不会自动倒灌旧版。详见 [迁移、冲突与回滚](docs/save-data.md)。

## 隐私与网络

不需要在线账号，不连接游戏内存，也不将截图发送给云端 AI。同步时会访问所选公开来源；物品图标来自 Tarkov.dev，主图床失败时可经图像代理加载同一公开图标，不发送档案或截图。地图访问受来源规则和许可约束，不随程序包携带个人数据、缓存或地图原图。

提交 Issue/日志前请遮盖用户名、截图、文件路径和个人资料。不要公开存档数据库、配对令牌或完整浏览器状态。

## 已验证与未覆盖

Stage4 的隔离验收已覆盖旧版迁移、默认路径跨 EXE/CWD 重启、双实例锁、共享偏好冲突、路线恢复，以及真实 Reserve 单图的后台缓存、显示、缩放、全屏和模拟离线。最终正式候选的准确源码、包大小和 SHA-256 以其 `BUILD-INFO.json`、`SHA256SUMS.txt` 和验收报告为准。

**尚未实体手机测试，也未真实下载/离线验证全部地图原图，未覆盖所有 Windows 用户及应用包宿主。** 手机/平板已做浏览器模拟，不等于实体设备通过。一次预热仅下载了额外一张 Reserve，其余覆盖见 [实测记录](docs/preload-evidence.md)，不宣传“全地图离线”。

## 开发与构建

运行源码需 Windows x64、Python 3.11：

```powershell
git clone https://github.com/xxtra1112/eft-task-assistant.git
cd eft-task-assistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

发布构建从**干净、固定提交**开始，使用仓库的版本元数据和 Windows 锁定依赖：

```powershell
python -m pip install -r requirements-build.txt
python -m pip check
& "$PWD/build_windows.ps1" -Version 1.3.0
```

产物在 `dist`；本地和 CI 使用同一构建入口。锁定提交、依赖和流程便于核验，不承诺不同构建机/时间的 EXE 字节必然相同。测试命令：`python -m pytest -q`、`node --test tests/test_*.cjs`。

CI 的精确 Python 补丁通过仓库 `.github/conda-release.yml` 安装，固定 Miniforge 与 conda-forge Python build；不是不可用的 setup-python Windows 3.11.17 包。`BUILD-INFO.json` 记录完整运行时字符串，区分本地 Anaconda 与 CI conda-forge 等发行来源。

CI 在 main/PR 检查源码；手动构建用于候选资产，不等于发布。新版本 tag 需与元数据及双语发布说明一致，验证通过后才执行发行流程。正式 GitHub 发行还须把同一验证包同步到已确认的蓝奏云目标并核对大小/散列；未完成上传不提供伪造链接。详见 [发布检查清单](docs/release-checklist.md)。

## 许可

原创代码采用 [MIT License](LICENSE)。地图、游戏商标、第三方资料和依赖均有各自许可，**不因为代码是 MIT 就变成无限制媒体授权**。请阅读 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)；使用本工具仍应遵守来源规则，并在游戏内核对任务。

发布包另附 `THIRD_PARTY_LICENSES.txt`，收录所用依赖和 Python 的许可正文及上游声明，同一份文件也嵌入 EXE。它的散列记录在 `BUILD-INFO.json`，便携包的校验和也覆盖此文件；重新分发时请一起保留。
