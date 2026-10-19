# RE3MR 高清底图模块：来源核查与接入交接

许可与代表性实测复核日期：**2026-10-20（Asia/Shanghai）**。本文区分官网观察、历史 Factory 实测、
Stage4 Reserve 新增实测与合成测试；下文 2026-10-19 的历史记录保留原始日期。
当前交付为 **Stage4 Preview，未正式发布、未上传**。本次收尾只更新文档，未修改代码或运行服务。

## 许可结论及边界

依据当前公开许可，已实现**本机个人非商业运行时读取原图**，供本地应用显示和本用户缓存；
没有把 FAQ 关于上传的提示扩大解释成禁止个人缓存，也没有声称取得作者单独授权。
这是根据公开文字作出的有限使用判断，不是作者对本软件的授权确认。

主要证据：

- [官网首页](https://reemr.se/)：页脚说明全部地图采用 CC BY-NC-SA 4.0，链接实际指向
  [4.0 legalcode](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode)。
- [Factory 官网页](https://reemr.se/factory/)：原图与 Photoshop 文件均有版权说明；
  显示 4.0 的按钮、页脚 4.0 链接和一个实际指向
  [2.0 deed](https://creativecommons.org/licenses/by-nc-sa/2.0/deed.en) 的版权链接同时存在。
  模块保留全部 `page_license_urls`，没有把这个版本差异抹掉或声称只有一种版本。
- [FAQ](https://reemr.se/about/)：允许朋友和论坛分享，要求视频等用途署名；
  对 “Can I upload your maps to my own website or application?” 的回答是 “Contact me”。
  本轮未联系作者。
- [4.0 正文 §2(a)(1)](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.en)：
  非商业目的的复制属于公开许可授予范围；§3 规定分享时的署名、许可链接与修改说明，
  分享改编内容须遵守相同方式共享要求；§2(a)(6) 不允许暗示背书。
- [2.0 正文 §3、§4](https://creativecommons.org/licenses/by-nc-sa/2.0/legalcode.en)：
  同样包含复制许可及非商业、署名、相同方式共享条件。

因此，此模块的固定使用范围是 `personal-local-noncommercial`。
不随 EXE/ZIP 带图、不提交图片到仓库、不上传 CDN/站点、不开放公共地图代理、不声称商业许可。
FAQ 对网站/应用上传的具体提示以及 2.0/4.0 链接差异仍是**打包再分发、再托管**需要另行澄清的证据，
不以本地运行成功推断这些用途获准。
运行服务应限本用户本机；现有手机/LAN 服务不能自动复用此许可判断。

### Stage4 复核：个人本机后台预取的边界

2026-10-20 重读 [primary 首页](https://reemr.se/)、[FAQ](https://reemr.se/about/)、
[4.0 正文](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode) 和
[2.0 正文](https://creativecommons.org/licenses/by-nc-sa/2.0/legalcode.en)，
在这些已查公开文字中**未发现专门禁止个人本机非商业后台预取的条款**。
4.0 §2(a)(1)(A)、2.0 §3(a) 均包含复制许可，相关非商业和分享条件继续适用。
这是对已查来源的有限解释，不是作者另行确认，不保证未查页面不存在其他信息；**未联系作者**。

FAQ 的网站/应用上传问题及其 “Contact me” 答复，不能扩大解释为所有个人本机后台缓存均被禁止；
也不能据此声称作者已同意本软件、网站上传或再托管。
Factory 页面仍同时含 2.0 deed、4.0 deed 和 4.0 legalcode 链接；Reserve 页面本轮识别的许可链接为 4.0。
保留逐页许可证据，不擅自统一版本，也不把公开复制许可当作跳过 robots 或访问控制的依据。

**Stage3 的“排除后台预取”应记录为当时谨慎的实现选择，而非已确认的授权禁令。**
Stage4 Preview 默认将 `reemr`、`eftarkov`、`tarkov.dev` 所有允许来源纳入个人本机后台队列，
逐项检查来源、许可、robots 和大小/格式；下载并发 2、完整解码并发 1，前台优先，支持取消。
磁盘缓存上限 512 MiB + LRU；默认全来源不表示本次已读取全部图片。
仍拒绝 `maps.reemr.se` 的 7 项；已有缓存也不能越过权限拒绝。手机/LAN 图片限制保持不变。

前段来源复核仅读取 HTML/robots；后续主线程 QA 仅新增 **1 张 Reserve 原图**，Factory 沿用 Stage3 记录。
本次 QA 限 1 个新增资产 + 32 MiB：123 项发现、41 项缓存、1 项下载、8 项拦截、73 项预算待继续，
`all_complete: false`。来源状态取自 `report.preload.preload.sources`：7 项 `maps.reemr.se` 无有效 robots，
另 1 项为 Woods 首项 robots 读取超时而保守拒绝，不是 8 张媒体均返回 403。
具体 HTTP/哈希、7 项清单、来源统计及 CLI 说明见 [Stage4 预取实测证据](preload-evidence.md)。
`--no-preload` 仅关闭启动预热；`--preload-budget-mib`、`--preload-max-assets` 均接受整数 `1..512`，
默认分别为 512 MiB/批与 512 个新增资产/批，和磁盘缓存上限分别计算。

### 当前接线边界：桌面独享原图

主 agent 已确定本轮接线采用桌面本机独享高清原图；以下是主 agent 负责落实的路由合同，
本文更新本身不代表已完成对应 HTTP/UI 集成验收。

- 桌面本机应用正常读取、验证、缓存并显示原图，保留 `reference_material: true`、
  `reference_only: false`；无任务点也应显示底图。
- `mobile_only` 路由对 RE3MR 图片请求直接返回 **HTTP 403**，包括命中桌面图片缓存的请求；
  拒绝应发生在读取/返回图片字节之前，不由手机请求触发原图下载。
- 手机 `map_view` 遇到 RE3MR `reference_material` 结果时转换为 `reference_only: true`、
  `image_url: ''`，并明确显示：**“高清原图仅在桌面本机显示；手机可手动开来源”**。
  实际渲染使用的图片 URL 应清空，不能保留可用的本机取图端点绕过此边界。
- 手机保留来源页链接供用户手动打开；手机外链/参考模式**不算高清原图显示验收**，
  也不表示应用已向手机提供高清底图。

本轮不联系作者、不上传或公开再托管地图；此边界也不扩大 robots 对 7 个受阻图片项的允许范围。
桌面原图显示、手机图片 403、手机参考提示应由主 agent 分别验收。

`map_license` 保留官网 4.0 声明并提示页面可能同时链接 2.0；
`license_evidence` 保存页面 URL、页面 SHA-256、核查时间、所有许可链接、FAQ URL、
`separate_author_permission: false` 和 `redistribution_enabled: false`。
本地导入使用用户明确提供的个人使用权说明，不把导入内容自动标成已获 4.0 许可。

## robots 与访问限制的真实核查

以下均为普通只读 HTTP 请求，没有切换代理、伪装浏览器或重试绕过访问限制。

接线收尾再次使用 web 浏览读取 [FAQ](https://reemr.se/about/)、[Factory](https://reemr.se/factory/)、
[4.0 正文](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode.en)，并点击 Factory 版权链接确认仍指向
[2.0 deed](https://creativecommons.org/licenses/by-nc-sa/2.0/deed.en)。FAQ 的应用上传提示及许可差异仍存在。
web 工具无法读取三个 robots 端点，因此用关闭自动重定向的普通 HTTP 读取作补证：

- `2026-10-19T14:15:36.262509+00:00`：`https://reemr.se/robots.txt`，200、`text/plain; charset=utf-8`，空 Disallow。
- `2026-10-19T14:15:37.579245+00:00`：`https://www.re3mr.com/robots.txt`，200、同样纯文本及空 Disallow。
- `2026-10-19T14:15:39.087778+00:00`：`https://maps.reemr.se/robots.txt`，**301**，
  Location 为 `https://reemr.se/`、MIME 为 `text/html; charset=UTF-8`；没有跟随该异常跳转，也没有请求其图片。

| 实际域名及 robots URL | 2026-10-19 观察 | 模块处理 |
| --- | --- | --- |
| [reemr.se/robots.txt](https://reemr.se/robots.txt) | 200、`text/plain`，通配 User-agent、空 Disallow | 按当前规则读取公开目录和实际原图链接 |
| [www.re3mr.com/robots.txt](https://www.re3mr.com/robots.txt) | 200、`text/plain`，通配 User-agent、空 Disallow | 允许 Factory 等实际链接的原图 |
| [re3mr.com/robots.txt](https://re3mr.com/robots.txt) | 200、`text/plain`，通配 User-agent、空 Disallow | 若将来官网实际链接至此，仍逐域检查 |
| [www.reemr.se/robots.txt](https://www.reemr.se/robots.txt) | 正常重定向到 `https://reemr.se/robots.txt`，返回纯文本规则 | 先检查重定向 URL，再采用规则 |
| [maps.reemr.se/robots.txt](https://maps.reemr.se/robots.txt) | 普通请求最终落到 `https://reemr.se/`，200 HTML，未取得有效 robots | 停止该域名图片下载；不把首页 HTML 当允许规则，不替换域名找副本 |

`maps.reemr.se` 当前是明确的技术阻碍：目录仍能显示对应版本，但选择图片会返回 `CatalogError`，
应在应用内显示原因并提供本地导入。不会把这种状态伪装成已成功缓存。
robots 以后恢复有效响应时，重新检查后才可能读取。

传输层关闭自动重定向，逐跳执行 HTTPS、官方域名、路径、robots 检查；
不向非白名单重定向目标发请求。robots 的重定向只允许官方域名的 `/robots.txt`。
404/410 的 robots 按不存在规则处理；403、401、429、5xx、连接失败或 HTML robots 不采用允许策略。
robots 规则支持特定 User-agent、最长路径、通配符和结尾匹配；不访问 PSD、ZIP、RAR、脚本、SVG、广告。

## 真实 HTML 目录覆盖

目录从官网首页实时识别，地图 ID 保留旧 13 slug；静态表只用于支持范围和中英文名称，
不硬编码图片 URL、版本、楼层或文件名。
首页真实链接含 `/Factory/`、`/Terminal`、`/Transit`、`/icebreaker` 等大小写及尾斜杠差异，
模块保留实际链接并检查服务器的正常重定向。

原图候选来自地图页有文字名称且附 lightbox 尺寸属性的 PNG/JPEG/WebP 链接。
网络白名单进一步限制为本轮官网实际链接出现的地图资产目录，如 `Factory`、`Customs`、
`Reserve`、`Groundzero`、`Streets` 等；不读取同域名的广告目录或 WordPress uploads。
同 URL 的名称和版本链接合并；空文本手机预览、普通 `<img>` 缩略图、旗帜翻译链接、
没有尺寸属性的图片链接不自动导入。译图另有贡献者，当前未实现其逐项权利与署名解析。
新格式未能识别时明确报错，不猜文件名或回落到其他来源。

前阶段目录识别结果（此表尺寸除历史 Factory 实测外均为 HTML 提示；Stage4 新增 Reserve 解码证据另见下文）：

共 **13 个地图页、28 个具名原图版本/区域**。其中 Customs 的 4 项、Reserve 的 3 项
链接至 `maps.reemr.se`，这 **7 项** 当前因 robots 异常被拦截；
其余 21 项的域名 robots 规则可读取，不表示这 21 张图片均已实际下载验证。

| 官网地图页 | 识别的原图版本/区域 |
| --- | --- |
| [Customs](https://reemr.se/customs/) | CUSTOMS 1.1E、DORMS 2D 1.1b、CUSTOMS OLD 1.1e、DORMS 3D OLD 1.0 |
| [Factory](https://reemr.se/factory/) | TOP-DOWN 1.7C |
| [Ground Zero](https://reemr.se/ground-zero/) | TOP-DOWN 0.3C |
| [Icebreaker](https://reemr.se/icebreaker/) | ICEBREAKER；版本标题是未链接的文本，模块不推断版本归属 |
| [Interchange](https://reemr.se/interchange/) | INTERCHANGE 0.2D、MALL INTERIOR 1.3D |
| [Labyrinth](https://reemr.se/labyrinth/) | LABYRINTH 0.6E |
| [Lighthouse](https://reemr.se/lighthouse/) | VERTICAL MAP 1.7、HORIZONTAL MAP 1.4 |
| [Reserve](https://reemr.se/reserve/) | RESERVE 1.3F、TUNNELS 2D 1.0b、TUNNELS 3D 1.0b、OLD |
| [Shoreline](https://reemr.se/shoreline/) | SHORELINE 2.4E、RESORT 1.0B、SHORELINE OLD 1.3D、RESORT OLD 1.0F |
| [Streets](https://reemr.se/streetsoftarkov/) | STREETS OF TARKOV 1.6e、LEXOS MINEFIELD 0.4、CACHE MAP 1.0 |
| [Terminal](https://reemr.se/terminal/) | 2D MAP 1.1F |
| [Transit](https://reemr.se/transit/) | TRANSIT；版本链接目标有错，未赋予版本号 |
| [Woods](https://reemr.se/woods/) | WOODS 1.7、WOODS NO MARKERS 1.6C、TRAIN DEPOT 1.6C |

这里的 `floors` 是应用切图接口的容器：它们可能是另一投影视图、区域、旧版或合并多楼层的图，
不是声称官网提供独立游戏楼层。保留英文原始名称，不人为拆层或编坐标。
`deprecated` 仅按官网名称中的 OLD 标记。

一个已核查的官网内容错误：Transit 页的 TRANSIT 名称链接指向
`https://www.re3mr.com/maps/Transit/re3mrTransits.png`，
但 Version 0.4 链接实际指向 Factory PNG。
模块只识别具有明确名称的原图，将这个无配对版本链接保留在 `unmatched_version_links`，
不会把 Factory 混入 Transit，也不会按名称猜测修正后的版本链接。

## 接口与主 agent 接入

依赖：Pillow。现场使用已存在的 Python 构建环境及 Pillow 13.0.0，没有安装软件。
本次已在 `requirements.txt` 纳入 `Pillow>=13.0,<14`；
`requirements-build.txt` 通过 `-r requirements.txt` 继承，不需重复添加，也未修改构建依赖文件。

公开接口：

```python
from reemr_maps import ReemrMaps, validate_image

provider = ReemrMaps(cache_root=runtime_cache_root)
index = provider.map_index()
config = provider.map_data("factory")
selected = config["floors"][0]
provider.check_floor_access("factory", selected["key"])
response = provider.floor_image("factory", selected["key"])

selected.update({key: response.metadata[key] for key in (
    "width", "height", "dimensions_verified", "dimensions_basis", "sha256",
)})
original_bytes = response.body
content_type = response.content_type
cache_metadata = response.metadata
```

同名模块级 `map_index()`、`map_data(map_id)`、`floor_image(map_id, floor_key)` 使用同一默认实例。
`FetchResponse` 包含 `.body: bytes`、`.content_type`、`.source_url`、`.metadata`；错误为 `CatalogError`。
构造合同：`ReemrMaps(*, cache_root: Path | None = None, usage="personal-local", fetcher=None)`。
只有显式传入 `cache_root` 才写磁盘；默认实例纯内存，接线应持有一个有独立缓存根的实例。
`fetcher(url, limit, accept) -> FetchResponse` 仅为测试/受控传输注入，不得自动跟随重定向。

`map_data()` 返回 `map_id/name/name_en/source_url`、`floors`、`annotations: []`、
`reference_only: false`、`reference_material: true`、署名、许可及 notice。
各图有稳定的 URL SHA-256 派生 key、实际 `image_url/source_image_url`、官网原始名称和版本。

首次读取目录时不下载图片：`width/height` 为 `None`、`dimensions_verified` 为 false，
HTML 声明单独存在 `html_width_hint/html_height_hint`。
**切图时先取 `floor_image()` 并使用其完整解码尺寸，再创建/更新画布。**
同一实例随后 `map_data()` 会返回最近成功解码尺寸；页面 SHA-256 改变时不沿用旧尺寸。
不要拿 HTML hint 当已验证尺寸，也不要为了获取所有尺寸而在 `map_data()` 中批量下载所有版本。

主 agent 需要接上的行为：

1. 应用实际图片接口读取 `response.body` 并返回真实 MIME；将 `image_url` 改为应用自己的本机图片接口。
   当前 `image_url` 是来源标识而非让浏览器直连的最终 `<img src>`；
   `requires_local_image_endpoint: true` 是强制接入约定，避免绕过解码、许可和缓存检查。
   该原图接口仅供桌面本机；`mobile_only` 按前述合同返回 403、只提供参考来源。
2. 只有成功返回的已完整验证图片才可原子写入本用户运行时缓存，连同全部 metadata 保存。
   metadata 包括 SHA-256、实际宽高、MIME、原始/最终资源 URL、官网页 SHA-256、版本、
   ETag/Last-Modified（上游提供时）、时间、耗时、许可与署名、`modified: false`。
   缓存目录不得在包资源/仓库中，也不能通过公共或 LAN 路由默认发布。
3. 离线读取由主应用的来源隔离缓存实现：原字节与记录的 SHA-256/MIME/尺寸须重新验证，
   展示明确的离线时间、来源及许可。导出/发布包时排除这些运行时资产。
   `validate_image()` 可独立用于缓存校验。不能把机器人规则拒绝或图片验证失败的响应写成成功缓存。
4. 提供加载/失败/缓存命中状态和完整署名链接；没有任务点也必须显示底图。
   保持 `annotations: []`，不可叠加未经校准的其他来源点位。

Stage3 模块交付时未实现后台预热或全图并发下载，这是当时的实现范围，不能作为许可禁止预取的证据。
Stage4 Preview 已按上文边界接入有限并发预取；图片原始字节由调用者持有。
当前 QA 只支持下文 Reserve 的应用内解码与磁盘热缓存复用记录，不能扩大为全部地图的 UI/离线验收。
应用层其他集成验收由主线程记录；本次文档收尾不重复默认路径重启或编译验证。

### 磁盘目录 JSON 与拒绝状态合同

显式缓存路径为 `<cache_root>/reemr/directory-v1.json`，不读取系统默认存档或其他来源根目录。
JSON 最大 40 MB；采用同目录随机临时文件、flush/fsync、原子 replace。文件结构为：

- `schema_version`、`source_provider: reemr`、固定个人非商业使用范围；跨来源/未知 schema 的 JSON 不采用。
- `documents`：URL 键、原始 UTF-8 HTML、正文 SHA-256、实际来源 URL、抓取时间、上游 metadata。
- `directories`：实时 index、每张地图的解析配置与版本/原图 URL/许可证据、成功解码图片的 metadata；不含图片 bytes。
- `robots`：每个官方 origin 的规则正文、规则哈希、HTTP 状态、时间；或明确的 `blocked`、拒绝原因。
- `operations`：每个目录/robots/图片操作的最新状态、最近成功时间、最近失败时间/类型/消息/HTTP 状态。
  成功恢复会更新当前状态，但保留上次失败证据。
- `imports`：本用户明确选定文件的私有路径、哈希、个人使用权说明及确认时间；不复制图片。

HTML TTL 为 12 小时。过期刷新失败可返回**同一 URL、同一来源、哈希正确的磁盘目录**，
`map_index()` 条目和 `map_data().cache_status` 明示 stale/offline、上次抓取时间和失败原因；
同一实例 30 秒内不重复请求失败目录。不会用其他来源或旧静态 13 项伪造成功目录。
损坏或跨来源目录不会用于离线回退。

robots 正、负结果 TTL 均为 1 小时，并跨实例重启保存。有效 Disallow、异常跳转、HTML robots、
401/403/网络失败都不会采用旧允许规则下载图片。robots 过期且离线时，只保证目录可查看，
图片权限检查会保守拒绝；不把离线目录当作图片访问授权。

**图片缓存接线必须先调用 `check_floor_access(map_id, floor_key)`，再读取任意外部图片缓存。**
它检查官网、地图页和原图 origin 的 robots；返回允许证据，或抛出 `ReemrPolicyError`（继承 `CatalogError`）。
这个异常必须直接交给 UI，不能放进“任意抓取失败都返回旧图片”的捕获分支；
最近已知原图 401/403 同样禁止旧图片回退。`floor_image()` 自身也执行权限检查。
目录 floor 的 `robots` 是上次已知状态，不能代替这个强制检查。

每个缓存根应由一个长寿命 `ReemrMaps` 实例管理；实例内部线程安全，未实现多个进程/独立实例同时写同一 JSON 的协调。
不同测试/实例应使用不同根；不要把这个路径放入原仓库、预览服务数据根或发布包。

### 给 data_sources / asset_cache agent 的直接接线合同

已只读核对当前 `asset_cache.DiskAssetCache` 和 `FetchResult`。`FetchResponse` 是本模块的数据类，
不能直接传给 `DiskAssetCache` 当作 bytes；callback 应转换为该模块的 `FetchResult`：

```python
from asset_cache import FetchResult

provider.check_floor_access(map_id, floor_key)

def fetch_selected(**validators):
    result = provider.floor_image(map_id, floor_key)
    return FetchResult(
        data=result.body, content_type=result.content_type,
        etag=result.metadata.get("etag") or None,
        last_modified=result.metadata.get("last_modified") or None,
    )

image_bytes = image_cache.get_or_fetch(asset_key, fetch_selected)
image_info = validate_image(image_bytes)
```

`asset_key` 必须含 `reemr` 来源、map/floor、原图 URL、官网版本与页面 SHA-256；
key 命名可沿用 `make_asset_key`。成功缓存命中后，画布仍须用实际解码的 `image_info` 更新宽高。
允许点和路线的校准不能从其他来源推断。

现有 `DiskAssetCache` 默认 15 秒抓取截止、100 MP 像素上限、1 次重试，接 RE3MR 时须明确配置：
`fetch_timeout=60`、`max_asset_bytes=50_000_000`、`max_pixels=160_000_000`、`retries=0`，
并限制高清解码并发。真实 Factory 首次读图曾为 27.125 秒；Interchange 内部图 HTML 提示约 102.58 MP，
默认参数可能误判失败。这里没有改动其他 agent 的缓存代码。
本模块当前不实现条件请求/304；callback 接受的 validators 不代表已发送 If-None-Match。

## 本地导入：无需联网的实际字节接口

若原图域名 robots 失败、页面结构变化或用户选择不联网，可注册用户明确选定、有权个人使用的图片：

```python
from pathlib import Path
from reemr_maps import ReemrMaps

provider = ReemrMaps()
floor = provider.import_image(
    "factory", Path(r"C:\Users\Example\Pictures\my-lawful-map.png"),
    name="工厂本地原图", rights_confirmed=True,
    license_evidence="用户记录的真实来源、许可或个人使用依据",
)
index = provider.map_index(local_only=True)
config = provider.map_data("factory")
response = provider.floor_image("factory", floor["key"])
```

本地导入不扫描目录、没有网络请求、没有复制或重编码。
文件大小和像素解码限制相同；登记后文件内容改变会拒绝读取，需重新导入确认。
公开 config 不暴露绝对文件路径；`local-import:...` 仅是内部标识，须由本机图片接口返回字节。
同一地图有本地导入时优先只返回该地图的导入版本，确保离线可用。
显式配置缓存根时，登记与权限说明保留在私有目录 JSON，重启后可继续读取；
`rights_confirmed` 不为 true、缺使用范围或来源说明的登记不会恢复。
未传缓存根时仅保留在实例内存。文件选择 UI 由主应用处理。
`rights_confirmed` 是用户确认，不表示本软件或作者已经替用户核验了任意文件的权利。

## 图片安全与清晰度

- 最大 **50,000,000 bytes/图**；响应 Content-Length 过大直接拒绝，无长度时读取上限加一个字节判溢出。
- Stage4 旧计划的 25 MB 单图硬流限制未实施；本次沿用上述产品安全上限。Reserve 实际小于 25 MB，不能据此声称验证了 25 MB 流拦截。
- 最大 **160,000,000 pixels/图**，不更改 Pillow 全局像素限制；只在解码范围内处理其警告。
- Pillow 识别 PNG/JPEG/WebP，先 `verify()`、再重新打开 `load()` 全量解码；
  拒绝坏图、截断、动画、SVG、HTML 错误页和 MIME/实际格式不一致。
- 保留原始编码字节、清晰度、嵌入署名；不缩图、不转换、不抹水印。
- 原图完整解码可能需要数百 MB 内存；应用必须限制同时解码数量，避免全地图预热挤占前台。

## 真实单图核验记录（不是 fixture）

历史模块核验仅获取一张 Factory 高清媒体，未落盘、未提交、未打包；其他地图只检查 HTML 目录和 robots。
下表是上一阶段留下的真实完整下载记录；2026-10-20 文档复核没有重复下载高清图，也未批量请求媒体。
模块测试仅使用合成 fixture。Stage3 集成验收中的 Factory 显示记录另由主线程保管，
不把它与此表的模块传输记录混为一条实测。Stage4 主线程仅新增 Reserve 1.3F 一张原图：
`https://reemr.se/maps/Reserve/Re3mrReserveLossless.png`，实际 **6,719,090 bytes，PNG，5760 × 3240**，
SHA-256 为 `b00692eba5c04cdab77429edca280b6bb5d2328da3420c852185c4dc5ce6066f`。
现有 QA 报告记录应用内解码及磁盘热缓存复用；响应头与耗时未在该报告提供，不补造。
证据路径及受限预算见 [preload-evidence.md](preload-evidence.md)；本次没有全图下载。

| 字段 | 实测 |
| --- | --- |
| 请求页面 | `https://reemr.se/Factory/`，等价人工核查入口 `/factory/` |
| 原图真实链接 | `https://www.re3mr.com/maps/Factory/FactorybyRe3mr.png` |
| 页面标示版本 | Version 1.7C |
| HTTP / MIME | 200 / `image/png` |
| Pillow 实际尺寸 | **13440 × 6656**（89,456,640 pixels） |
| 原始编码大小 | **15,273,462 bytes** |
| SHA-256 | `9893433ba729530924b70980ff38ad6e6cfffeb2d9bedad79103ee230b6fc596` |
| 请求完成时间 UTC | `2026-10-19T13:22:14.137587+00:00` |
| 上游 Last-Modified | `Thu, 27 Nov 2025 13:03:41 GMT` |
| 上游 ETag | 未提供，不编造 |
| floor_image 耗时 | **27.125 秒**，包括该图域名 robots 检查、传输和完整解码 |
| 首次目录至解码总耗时 | **41.703 秒**，单次本机网络样本，不代表性能保证 |

历史 Factory 的大小、MIME、实际像素及下载时延经过媒体读取验证；Stage4 另确认上述 Reserve 字节与解码尺寸。
其他页面尺寸仍只是 lightbox HTML 提示。手机/LAN 不返回 RE3MR 原图，包括桌面热缓存；
未实体手机验证、未所有地图真实原图验证，不能宣称全图下载/离线/应用 UI 已验收。

## 合成 fixture 自动测试

`tests/test_reemr_maps.py` 内的路径含 `synthetic`，图片由 Pillow 现场生成，
所有 HTTP 由内存 fixture 提供，**不是真实官网内容快照**，也不访问网络。
覆盖目录大小写、版本去重、空预览/翻译/广告/PSD/ZIP/脚本/SVG 排除、Transit 型错误链接、
许可缺失、robots 拒绝/HTML/跨域跳转、403 等不重试、URL 白名单、
流大小限制、像素限制、格式/MIME/坏图/动画拒绝、本地离线导入及修改后拒绝。

针对本次文件运行：

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python `
  -m pytest tests/test_reemr_maps.py -q -p no:cacheprovider `
  --basetemp="$env:TEMP\eft-reemr-module-tests"
```

现有其他模块正在并行修改，本轮不把它们的测试或旧 r2 验证结果记为本模块覆盖。
接线收尾增加真实临时目录的 JSON 写入/重启/过期断网回退、robots 拒绝跨重启保留、
旧允许被新拒绝替换、图片 403 状态、损坏与跨来源缓存拒绝、原子写失败保留旧 JSON、本地权限登记恢复测试。
另通过真实 `DiskAssetCache` + `FetchResult` 的纯 fixture 接线测试：首次读取验证小图，
第二次命中缓存不重复请求，随后 robots 改为 Disallow 时，已有热缓存也被前置检查拦截。
最终针对本次文件运行结果：**74 passed**；所有测试目录仅位于系统 TEMP，没有联网 fixture，也没有启动任何预览服务。
