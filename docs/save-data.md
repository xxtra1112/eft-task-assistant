# 跨版本共享存档与浏览器偏好

本文描述当前源码的托管存档启动流程。旧版 EXE、旧预览包及尚未重新构建的程序不因此自动具备这些功能。

本文件的开发机用户名、包标识和本地证据父目录已脱敏；`<local-qa>` 是本地保留的验收材料，不是安装路径，也不是随包提供的私人数据。

## 稳定根目录

Windows 默认通过 `SHGetKnownFolderPath(FOLDERID_SavedGames)` 查询当前用户配置的 Saved Games 目录，通常为 `%USERPROFILE%\Saved Games`。正式运行不拼接 `USERPROFILE` 来代替此查询，支持用户已配置的 Known Folder 重定向。生产根为 `SavedGames/EFTTaskAssistant`；不依赖 EXE 名字、版本、解压位置、当前工作目录、端口或启动宿主的 `LOCALAPPDATA`。移动 EXE 或升级后无需每版传入 `--data-dir`。

可选进程环境变量 `EFT_TASK_ASSISTANT_CHANNEL` 只接受以下白名单，未知值报错，不转成任意路径：

| 值 | 根目录 |
| --- | --- |
| 未设置或空字符串 | `SavedGames/EFTTaskAssistant` |
| `preview` | `SavedGames/EFTTaskAssistant-Preview`，跨预览版本固定 |
| `qa-<规范小写 UUID>` | `SavedGames/EFTTaskAssistant-QA/<UUID>`，同 UUID 重启共享，不同 UUID 隔离 |

preview 构建应在进程 runtime hook 使用 `os.environ.setdefault("EFT_TASK_ASSISTANT_CHANNEL", "preview")`，保留 QA 调用方指定的 channel。普通生产构建不设置 channel。不要按 EXE 文件名、版本或 CWD 推断 channel。QA channel 用于进程测试隔离，不是权限或安全边界。

显式 `--data-dir` 仍是最终根目录，不附加产品名或 channel；相对路径被拒绝，显式绝对路径不需要 Known Folder 成功，也不受 channel 环境值影响。这保留旧命令兼容性，但不能让显式指定的 AppData 路径免于系统虚拟化。

Known Folder 查询失败、返回非绝对路径或 Saved Games 指入当前用户的 AppData 时停止，不静默降级到 AppData、EXE 旁或 CWD。额外查询 Profile、LocalAppData、RoamingAppData 仅用于绝对路径归属比较，覆盖 AppData 被重定向到其他盘符的情况；不会把测试 TEMP 祖先目录恰好含 `AppData` 误当成合成用户的 AppData。解析器不创建目录、不读取存档、不调用 `Path.resolve()`、不按存档是否存在改选根；锁和 dataset 初始化仍由启动协议负责。

### 给启动与 setup 所有者的 API 合同

| API | 返回与副作用 |
| --- | --- |
| `save_data.resolve_data_dir(data_dir=None, *, environ=None)` | 返回 `Path`；显式路径兼容原行为，默认失败抛 `SaveDataError` |
| `default_paths.default_data_dir(*, environ=None)` | 返回默认 `Path`；路径或 channel 失败抛 `DefaultPathError(ValueError)` |
| `default_paths.known_folder_path(name)` | 只读查询 `SavedGames`、`LocalAppData`、`RoamingAppData`、`Profile`；不创建目录 |
| `default_paths.legacy_candidates(root, environ=None)` | 返回 `list[Path]`，也从 `save_data` 导出；绝对路径、按发现顺序去重并排除目标本身，不打开数据库、不修改文件、不决定导入或活动档案 |

`environ=None` 才使用真实进程环境和 Windows Known Folders。测试显式传入的 mapping 是封闭命名空间，不合并 `os.environ`、不调用 `Path.home()` 或 Known Folder。此模式的默认根由 mapping 中绝对 `USERPROFILE`（或 `HOME`）下的 `Saved Games` 派生，缺少两者即失败；它是测试契约，不代表正式 Windows Known Folder 重定向结果。`legacy_candidates(root, environ={})` 返回空列表，不探测真实用户；其 mapping 可只含测试 `LOCALAPPDATA`。

正常 discovery 同时考虑进程 `LOCALAPPDATA`、Known Folder LocalAppData、Profile 下旧 `AppData/Local` 以及 RoamingAppData/进程 `APPDATA` 下的产品目录。旧直接目录即使缺失也返回，供上层统一检查。还仅枚举这些 Local 基目录的 `Packages/<package-family>/` 中已存在的 `LocalCache/Local/EFTTaskAssistant`、`LocalCache/Roaming/EFTTaskAssistant`、`LocalState/EFTTaskAssistant`。这里只读目录名及 stat 元数据，不读 DB、manifest 或文件内容，不递归遍历任意路径，不跟随扫描中的包目录 symlink/junction；目录访问失败会抛 `DefaultPathError`，不能当成没有旧档继续创建空档。

preview discovery 同时列 `EFTTaskAssistant-Preview` 和历史未标 channel 的 `EFTTaskAssistant`；旧目录名不能证明历史发布通道，必须显示来源并明确确认。QA discovery **只**使用测试进程的 `LOCALAPPDATA`，派生旧版实际使用的 `EFTTaskAssistant` 与该基目录内的包候选；不读 native LocalAppData、APPDATA、Profile。QA 调用方必须将 `LOCALAPPDATA` 设为新 QA 临时目录，缺失或非绝对值即停止。不会自动找到历史任意 `--data-dir` 或已经改变过的旧启动器自定义环境目录，这些仍允许明确选择外部来源。

启动所有者在未发现目标活动 manifest/DB 时，先把候选交给 `discover_legacy_saves(root, candidates)` 只读盘点并让 setup 列出每份来源的完整性、schema、计数及不能迁移原因；不能因新根为空就让一份新空档遮住旧档。用户一次明确选择来源后才备份、复制、提交活动清单；后续版本通过同一默认根复用清单。若选择明确创建空档，也保留全部旧来源。目标和另一来源都非空时，二者都保留，不能自动合并或覆盖，也不能自动选择“最新”一份。路径模块不执行上述 setup 决策。发现失败与解析失败均应在主入口捕获并清晰停止。

### Microsoft 资料与真实限制（2026-10-20 核对）

- [KNOWNFOLDERID](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid)：Saved Games 的 GUID 为 `{4C5C32FF-BB9D-43B0-B5B4-2D72E54EAAA4}`，是每用户文件夹，默认位置只是默认值，不应硬编码代替查询。
- [SHGetKnownFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath)：本实现使用当前用户 token，配置返回 Unicode 指针与 HRESULT 的 ctypes 签名，并在成功或失败后用 `CoTaskMemFree` 释放返回内存。
- [KNOWN_FOLDER_FLAG](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/ne-shlobj_core-known_folder_flag)：使用 `KF_FLAG_DONT_VERIFY | KF_FLAG_NO_PACKAGE_REDIRECTION`（`0x14000`），不用 `CREATE`、`DEFAULT_PATH`。前者允许目录不存在且避免验证目录，后者控制返回路径名；**不等于关闭后续文件 I/O 虚拟化**。NO_PACKAGE_REDIRECTION 的该名称适用于 Windows 10 1703 起；更旧系统不在本次支持验证范围。
- [MSIX 运行行为](https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-behind-the-scenes)：虚拟化应用可将 AppData 新建操作转到私有位置并提供合并视图，具体取决于应用类型、信任级别及 Windows 版本。不能以 `LOCALAPPDATA` 字符串或 `Path.resolve()` 证明写入物理上不被虚拟化。因此默认选择 AppData 之外的 Saved Games；不靠改注册表、系统策略或包配置来绕过。

承诺范围是同一 Windows 用户、具有访问权限且系统 Known Folder 配置不变的已测进程。不同账户、AppContainer 权限、第三方宿主的额外重定向、Known Folder 后续改址、网络盘不可用或目录 junction 指向另处，均可能影响实际访问；查询成功不证明可写，也不构成所有 Windows 包身份部署均已验证。权限错误应保留原数据并停止，不换到第二份根。包候选只是尽力发现的已知布局，不能宣称覆盖所有厂商重定向规则。

### 本机只读路径证据

2026-10-20 使用指定构建 Python 子进程查询，[GetCurrentPackageFullName](https://learn.microsoft.com/en-us/windows/win32/api/appmodel/nf-appmodel-getcurrentpackagefullname) 返回 `15700`（`APPMODEL_ERROR_NO_PACKAGE`，无包身份）：

| 查询 | 实测值 / 是否存在 |
| --- | --- |
| SavedGames | `%USERPROFILE%\Saved Games` |
| LocalAppData | `%USERPROFILE%\AppData\Local` |
| RoamingAppData | `%USERPROFILE%\AppData\Roaming` |
| 生产默认根 | `%USERPROFILE%\Saved Games\EFTTaskAssistant`，不存在 |
| preview 默认根 | `%USERPROFILE%\Saved Games\EFTTaskAssistant-Preview`，不存在 |
| 预检查 QA 根 | `%USERPROFILE%\Saved Games\EFTTaskAssistant-QA\71db9e63-45ae-4d63-b2e5-704e759b0029`，不存在，未创建 |
| 普通旧默认 | `%USERPROFILE%\AppData\Local\EFTTaskAssistant`，目录存在，未读库 |
| Codex 包旧默认 | `%USERPROFILE%\AppData\Local\Packages\<package-family>\LocalCache\Local\EFTTaskAssistant`，目录存在，未读库 |

这些是查询时快照，不是对真实存档的写入/迁移验收。未创建或迁移真实生产、preview 或 QA 根。Stage3 报告中的移动 EXE/换端口通过依赖显式 `--data-dir`，不构成本次默认路径的编译程序证明。

目录结构如下：

```text
root/
  .save-data.lock
  active-dataset.json
  datasets/
    <dataset-uuid>/
      dataset.json
      tasks.sqlite3
      players.sqlite3
      players/
        <player-id>.sqlite3
  backups/
    <imported-dataset-uuid>/
      tasks.sqlite3
      players.sqlite3
      players/
        <player-id>.sqlite3
  manifest-backups/
    <uuid>.json
  public-data/
    source-cache/
    hideout-pve.json
  logs/
    app.log
  tasks.sqlite3                    旧文件若存在，继续保留
  players.sqlite3                  旧文件若存在，继续保留
  players/                        旧目录若存在，继续保留
```

每个 dataset 是独立存档集。`tasks.sqlite3` 保存本机档案的任务及对应的路线、偏好等数据；`players.sqlite3` 保存本地身份与会话信息，其他玩家任务库位于该 dataset 的 `players/` 中。

`public-data/` 位于根目录，供不同 dataset、不同版本共享公共地图、物品和藏身处数据缓存。它不承担玩家任务、偏好或身份存档功能。诊断日志也位于根目录，切换 dataset 不改变日志路径。

## 第一次启动与旧库确认

全新根目录直接建立新的 UUID dataset，完成 schema 初始化和检查后才原子提交活动指针。根目录不会新建兼作活动存档的旧布局数据库。

如果没有活动清单，但发现根目录中的 `tasks.sqlite3`、`players.sqlite3` 或 `players/*.sqlite3`，默认启动只读取完整性、schema 和表计数，返回 `legacy_import_required`。即使旧库暂时没有任务，也不会直接覆盖或重置。

主程序此时只开放本机回环地址上的确认页。用户明确确认后，程序影子复制整组数据库，保留备份，完成检查，再关闭确认页服务并启动实际应用。未确认时不创建新的导入副本、不迁移原始库，也不启动实际任务服务。若目录中只有待恢复或未选择的 managed dataset，需要明确选择，不能自动创建另一份空存档遮住它。

## 导入另一份存档与切换

导入不合并任务、身份、路线或偏好。每次成功导入都生成新的 UUID dataset；同名玩家或任务也不会被猜测合并。

在设置中导入外部根目录时，调用 `prepare_runtime(..., source_root=..., migrate=True, activate=False)`。返回 `status="imported"` 及新 dataset 的路径，但当前 `active-dataset.json` 的内容保持不变。新 dataset 可以列出和检查，直到用户另行明确选择才会修改活动指针。

选择存档集或回滚都只安排下次启动。当前进程仍使用启动时绑定的 dataset，已有数据库连接不会中途切换。关闭应用后重新启动，才使用新的指针。回滚只改变指针，不撤销 dataset 内已经发生的任务或偏好修改，也不删除任何 dataset。

设置 API：

| 接口 | 行为 |
| --- | --- |
| `GET /api/save-data` | 只读状态、目录、dataset ID、schema 和表计数；不返回数据库行内容 |
| `POST /api/save-data/import` | `confirmed: true` 与绝对 `source_root`；复制独立 dataset，保持活动指针 |
| `POST /api/save-data/select` | `confirmed: true` 与 `dataset_id`；安排下次启动使用该 dataset |
| `POST /api/save-data/rollback` | `confirmed: true`；安排下次启动使用上一次指针指向的 dataset |

来源也可以是另一个托管根目录：只复制该根目录当前选中的 dataset，不合并其其他 dataset 或历史备份。

## 备份、一致性和失败保全

导入顺序是：只读盘点整组源库、记录 stat → SQLite 在线备份到 `backups/<uuid>/` → 从备份复制到新 dataset → 仅在副本初始化 schema → 检查完整性与源库 stat → 写入 dataset 元数据 → 按需要原子提交活动指针。

在线备份使用 SQLite backup API，会包含 WAL 中已经提交的数据；不能用只复制 `.sqlite3` 文件的方式代替。每个库获得一致快照，整组库再检查源文件集合及主库、WAL、回滚日志的大小、时间与文件标识。发现写入、文件替换或新增玩家库就中止。SHM 是读者锁协调文件，不用其时间变化判断业务写入。

导入前应退出使用源目录的旧版程序。新版本的进程锁只约束遵守协议的程序；stat 检测也不能阻止不遵守锁的旧程序在最后一次检查之后重新写入，不能据此宣称可以安全热迁移任意旧进程。

原始库、已完成的备份和失败的 dataset 均保留。schema 初始化、复制或清单提交失败，不会覆盖根目录旧库，也不会把失败副本设成活动存档。修改既有活动清单之前，其原始字节另存至 `manifest-backups/`；同目录临时文件写完并同步后，才以原子替换提交新清单。

发生失败后，可先查看状态及错误中的 `dataset_id`、`backup_dir`。副本完整且兼容时可以明确选择；需要重新导入时，也可把完整的 `backups/<uuid>/` 作为来源，生成另一份独立 dataset。不要把旧库、备份或失败目录直接覆盖到当前活动目录。完整数据库备份含身份与会话资料，应留在本机；状态导出只有元数据和计数，不能代替完整备份。

## Schema 与版本兼容

当前支持 SQLite `user_version` 最高为 `1`。历史 `0` 版本可在确认后的影子副本中执行现有 Store 初始化迁移；原始源库及原始备份保留旧版本。

`TaskStore`、`PlayerAuthStore` 在构造和每次获取写连接前，先用只读连接检查 schema。发现高于 `1` 的库就抛出 `UnsupportedSchemaError`，在打开写连接之前停止。活动 dataset、导入源中的任一玩家库，以及活动清单或 dataset 元数据中的未来版本也会被拒绝。

旧版本不能通过调低 `user_version` 来强行打开新库。应选择兼容的独立 dataset，或使用相应的新版本程序。早期二进制可能既不检查 schema，也不遵守进程锁，因此不应把它们直接指向新的 managed dataset。

## 浏览器偏好与旧端口边界

共享偏好按 profile 保存在当前 dataset 的 SQLite 中。已提交的钥匙状态、隐藏任务、隐藏地图点、藏身处计划、材料数量、面板状态等，可由另一个浏览器或新端口重新读取。同一根目录中另一个独立 dataset 的偏好不会自动合并过来。

第一次接入时，只能自动读取当前 origin 的旧 `localStorage`。origin 包含协议、主机和端口；`127.0.0.1` 与 `localhost` 不同，两个端口也不同。服务器还没有偏好时，客户端可以尝试 `only_if_empty` 的首次导入；服务器已有数据时以服务器状态为优先，不能用旧浏览器内容自动覆盖。冲突版本保留备份，并要求明确选择。

跨旧端口、不同主机名或不同浏览器，必须手动导出、导入：

1. 在原来的浏览器、原来的地址打开旧页面，选择“导出本浏览器偏好”。
2. 在新地址选择目标档案，使用“导入偏好文件”载入 JSON。
3. 如果存在服务器版本，核对冲突后明确选择“保留服务端版本”或“使用本浏览器版本”。必要时先“导出偏好备份与冲突”。

旧页面没有导出按钮时，可在 Chrome/Edge 的旧页面开发者工具控制台执行以下命令，将剪贴板内容保存为 JSON 文件，再在新页面导入：

```javascript
copy(JSON.stringify(Object.fromEntries(Object.entries(localStorage).filter(([key]) => key.startsWith('eft-task-assistant-ui-v1:')))))
```

该命令只选取旧 UI 偏好键，不导出其他 localStorage 项。必须在原 origin 执行；新页面不能代替旧页面读取其他端口的存储。服务器不能通过数据库迁移找回从未上传、也未导出的旧浏览器偏好。

偏好保存使用 revision CAS 和 UUID 幂等操作。版本不匹配时，双方 UI 快照先持久备份，再返回 409，原服务器快照不变；显式解决后也保留备份。旧钥匙字典 alias 和旧线条不按名称猜测物品或楼层，不静默截断。共享 JSON 上限为 2 MiB，列表、字典另有安全限额；超限明确拒绝，需保留调用方本地原副本。

`routePendingOperations`、`routeCaches`、`routeCacheRevisions` 属于原浏览器本机状态，不上传共享偏好，也不在新窗口重放旧待发送队列。离线尚未提交的路线仍需在原浏览器完成同步。旧 `mapDrawings` 快照保留，但缺失的来源、楼层不会凭空补出；路线使用边界见 [路线同步说明](route-sync.md)。偏好接口及其备份导出不读取身份、Session 或 token 表。

## 启动与接线

普通发行程序直接双击 EXE 或运行 `python main.py`；无需每版指定数据目录。以下显式路径命令供外部来源选择和诊断使用，目录仅作示例，执行前应换成明确选定的绝对路径：

```powershell
python main.py --data-dir "E:\EFT-Saves" --list-saves
python main.py --data-dir "E:\EFT-Saves"
python main.py --data-dir "E:\EFT-Saves" --migrate-legacy
python main.py --data-dir "E:\EFT-Saves" --import-data-dir "D:\Old-EFT-Save" --migrate-legacy
python main.py --data-dir "E:\EFT-Saves" --select-dataset "<dataset-uuid>"
```

`--list-saves` 只读盘点后退出。启动时的 `--import-data-dir` 配合明确确认可以选用新导入副本；运行中设置页导入始终使用 `activate=False`，还需单独选择并重启。

主程序持有根目录 `DataDirectoryLock`，调用 `prepare_runtime`，必要时运行确认页。取得 `ready` 后执行 `configure_paths(runtime.paths)`，再构造 Store；所有 Store 和服务关闭后，才清除路径绑定并释放锁。默认 Store 构造要求已经准备好 runtime；显式路径构造供隔离测试和工具使用。

路径 getter 未绑定时只解析稳定根，不创建目录或探测真实存档。`public_cache_root(fallback)` 绑定后返回 `root/public-data`；未绑定且提供显式 fallback 时返回 `fallback/public-data`，否则返回默认根下的 `public-data`。导入、选择和回滚不会修改当前进程的绑定。

## 普通发行两 EXE、无 `--data-dir` 的验收方案

本节是交给主线程执行的编译程序验证计划，不表示路径模块子任务已经启动或写过真实根。现用 r2/Stage1/2/3 服务均不参与；旧 Stage3 只运行独立复制的 EXE，数据库只使用合成或明确许可的离线副本。不要结束任何按名字匹配到的其他程序。

1. 生成一个本轮专属 UUID，查询当前用户实际 KnownFolder SavedGames，计算 `SavedGames/EFTTaskAssistant-QA/<uuid>`。启动前用 `Test-Path -LiteralPath` 确认**该最终目录不存在**，已存在就另取 UUID，不能重置它。新建独立 QA 工作目录存放 EXE 副本、CWD、TEMP/TMP、`legacy-env` 与日志；生产/preview 根只记录目录元数据，不能创建或迁移。runtime hook 必须保留调用者给出的 `qa-<uuid>`。
2. 为每个测试子进程单独设置 `EFT_TASK_ASSISTANT_CHANNEL=qa-<uuid>`、`LOCALAPPDATA=<QA>/legacy-env`、TEMP/TMP；不改用户/系统环境。在隔离 CWD 运行旧 Stage3 副本，**不传 `--data-dir`**，用合成任务、路线、偏好及身份形成非空旧存档；确认旧版实际写到 `<QA>/legacy-env/EFTTaskAssistant`，随后仅关闭本轮进程并等待其退出。记录旧库/sidecar 文件集合及散列，保留源目录。
3. Stage4 EXE A 同样不传 `--data-dir`，相同 QA channel 与旧 LOCALAPPDATA 启动。应选中 SavedGames QA 根，并在目标还没有活动 DB/manifest 时发现旧根。setup 应列出来源路径、表计数、schema；未确认前不得导入、不得创建替代空 dataset。明确选择该来源并确认一次，核对新 dataset 的任务、路线、偏好、身份计数与 UI，保留原始旧根和备份，记录根、dataset UUID 及活动清单。存在多个非空候选时，确认前各份均可见，确认后未选来源仍字节保留。
4. 正常退出 A。在旧 LOCALAPPDATA 外另建空 CWD 与第二个空 `LOCALAPPDATA`，移动/改名 EXE A，以相同 QA channel、不同端口启动，仍无 `--data-dir`。应使用同一 SavedGames 根和 dataset UUID，读取同一组任务/路线/偏好；无需重新确认迁移。此时不能因旧根不再可发现而换成空档。
5. 用另一个版本的 Stage4 EXE B 放到另一目录，从第三个 CWD、第三个 LOCALAPPDATA 启动，channel 相同且无 `--data-dir`。先在 A 运行时验证 B 的同根写锁拒绝（退出 2），再正常退出 A、重启 B，验证根、dataset UUID、数据一致。所有终止/等待操作仅使用本轮持有的进程句柄/PID，启动后台进程使用隐藏窗口。不同 UUID 应得到不同根；preview 的固定根只做解析比较，不为本轮验证写入真实 preview 根。
6. 对有两份非空 roots、未来 schema、坏库或扫描权限失败的隔离夹具补测：两份数据均保留，失败候选仍清晰显示，不能自动选择最新或合并；未确认前不创建空 dataset。选择“明确创建空档”时也必须保留全部旧来源。最后只读比对原生产/preview 和真实旧目录的元数据，确认本轮没有修改它们。QA 目录作为证据保留，不自动删除存档。

验收需分别记录当前 Python/EXE 子进程包身份、是否由普通终端或 Codex/MSIX 宿主发起、Windows 版本和实际根。通过一台机器的两个 EXE/CWD 用例只证明该当前用户及已测宿主组合；不会外推为第三方所有 MSIX 身份、AppContainer 或其他 Windows 用户均已写入验证。

全量 pytest 的 `tests/conftest.py` 会将 Known Folder、用户 HOME/USERPROFILE、AppData 环境隔离到每个测试的 `tmp_path/windows-user`，清除继承 channel，并在结束时关闭本测试临时目录中的 `eft_task_assistant` 文件日志 handler。显式传 environ 的单测保持自包含。子进程不继承 Python monkeypatch；涉及子进程的路径测试显式传合成环境或明确根，不在真实 SavedGames 初始化服务。原有未来 schema 的只读拒绝及逐连接 guard 测试保留。

### 本路径子任务的实际测试结果

使用 `python -B -m pytest`，禁用 pytest cache，每轮使用全新 QA TEMP/TMP 和独立 `--basetemp`：

| 范围 | 结果 |
| --- | --- |
| 首轮 default_paths + save_data + app_paths | `85 passed in 43.19s` |
| 全量 Python tests | `631 passed, 1 skipped, 7 subtests passed in 695.09s` |
| 冻结后的 default_paths + app_paths/schema | `54 passed in 12.08s` |
| 全量结束后串行 LocalAccess | `2 passed in 8.35s`，未见临时日志文件句柄清理错误 |

全量进程在最终 AppData 归属比较边界修订前已加载源码，最终新增/修订的边界由后续 54 项路径/schema 测试覆盖；不能把全量结果误称为重新全量验证过冻结后的每一行。一次与全量同时进行的 default_paths + app_paths + LocalAccess 复跑曾出现 `54 passed, 2 failed`，失败为 LocalAccess 的 3 秒 HTTP 超时；全量本身通过这两项，全量结束后串行复跑两项均通过。没有修改超时、放松断言或修改服务器来掩盖这次中间失败。

全量证据目录为 `<local-qa>\eft-stage4-defaultpaths-full-qa-faa981fb-5c44-4874-9001-efbc8b27068a`；最终路径/schema 证据目录为 `<local-qa>\eft-stage4-defaultpaths-core-qa-e69c4f3e-048c-45e4-9da0-cdf2495f6887`；LocalAccess 串行复跑证据目录为 `<local-qa>\eft-stage4-defaultpaths-localaccess-qa-198d1b3c-bd3d-4e26-a2ff-c7bd5ad1a969`。本子任务仅执行源码/临时夹具验证和真实目录的只读路径查询；正常发行两 EXE 迁移/搬移验证由主线程按上节计划执行，结果需另行记录。

### Stage4 最终编译验收（2026-10-20）

以下为主线程实际执行结果，不替代前面保留的中间失败记录。全部使用全新 QA UUID 通道、隔离副本；没有停止或覆盖用户在用的原版、r2、Stage1/2/3/4 服务，也没有写入正式或 preview 默认根。

| 场景 | 实际结果 |
| --- | --- |
| 旧 Stage3 编译版普通启动 | 不传 `--data-dir`，在隔离 `LOCALAPPDATA` 的历史根读取 30 个任务 |
| 新 Stage4 编译版普通启动 | 不传 `--data-dir`，实际 Known Folder Saved Games 下发现两份非空历史根；未选择前无替代空 dataset；用户式显式选择后迁移 30 个任务及共享偏好 |
| 冲突来源保留 | 未选来源仍保留；三份历史源 DB 与迁移前关闭旧实例后记录的 SHA-256 一致，不合并、不覆盖 |
| 搬移、改名与不同 CWD | 另建独立 QA 默认根，使用只读在线备份；Stage4 A/B 为相同最终 EXE 的两份副本，改名、换 EXE 所在目录、CWD、端口与 `LOCALAPPDATA` 后，仍取得相同 Saved Games 根和 dataset UUID |
| 数据继承 | A/B 的全部任务及要求、共享偏好、7 条 Factory 路线和版本数据一致；宿主独立只读打开报告中的物理路径亦读到 30 个任务 |
| 同根双实例 | A 运行时 B 以退出码 `2` 拒绝写入；只关闭本轮独立 A 进程后 B 成功启动；在用 Stage4 的 20025 服务不参与关闭 |
| 缓存重启与离线模拟 | 仅使新隔离根的 Reserve 缓存验证时间过期；B 进程使用不可达代理模拟上游离线，返回相同 6,719,090 bytes / SHA-256 原图并明确显示 stale/offline 提示；没有改系统代理或真实断网 |
| 浏览器运行 | 搬移后的编译版实际显示 Reserve 原图 5760×3240，缩放和全屏通过；手机/平板为浏览器模拟，7 条共享路线的颜色、宽度和缩放后归一化几何保持；手机 RE3MR 热缓存图与预热写接口均返回 403 |
| 最终源码回归 | `656 passed, 1 skipped, 7 subtests passed`；前端 `39 passed`；22 个 Python 模块（含 main）及 9 个前端资源与最终 EXE 一致 |

前一次主线程全量曾为 `654 passed, 2 failed, 1 skipped`，两项 LocalAccess 的测试服务在首次 schema 初始化前就开放端口，触发其 3 秒超时。修正测试夹具，使其与实际程序一样先完成本地 state 初始化再监听；没有放宽超时或断言。之后专项 `38 passed`，上述最终全量全部通过。唯一跳过项仍是需明确私有真实 DB 的可选回归，未拿真实活动库冒险。

本地证据位于 `eft-repair-stage4-20261020/reports/`：`old-normal-baseline.json`、`default-migration.json`、`moved-default-runtime.json`、`browser-final.json`、`artifact-validation.json`、`full-r2.txt`、`node-final.txt`。最终预览标识为 `1.2.0-stage4-preview.20261020`，不是正式发布或已上传声明。

跨版本证据是旧 Stage3 → 新 Stage4；A/B 改名重启证据是相同 Stage4 二进制，不把相同散列的副本说成另一次版本升级。QA 只证明当前 Windows 用户及已测宿主组合，未涵盖第三方所有 MSIX 身份、其他用户、实体手机或所有地图原图。为避免再下载媒体，搬移重启使用 `--no-preload`；此前独立启动预热的单图验证已完成，产品正常启动默认仍是所有允许来源。
