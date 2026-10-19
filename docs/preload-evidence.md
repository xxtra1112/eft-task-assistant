# EFT Stage4 Preview：来源许可复核与代表性实测证据

复核日期：**2026-10-20，Asia/Shanghai（UTC+08:00）**。
前段来源复核只读官网 HTML/robots；下文另补主线程现有 QA 报告中的单图实测，不能混同。
本次文档收尾没有请求媒体、启动服务、编译或操作 Git，也未修改原仓库或上传内容。
交付状态为 **Stage4 Preview，未正式发布、未上传**；Factory 沿用 Stage3 记录，Stage4 仅新增一张 Reserve。

## 1. 当前 primary 与许可结论

| 一手来源 | 2026-10-20 观察及可用边界 |
| --- | --- |
| [首页](https://reemr.se/) | 页脚声明地图采用 CC BY-NC-SA 4.0，实际链接为 [4.0 legalcode](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode)；免费提供本身不等于无条件使用或背书 |
| [FAQ](https://reemr.se/about/) | 网站/应用上传问题的答复为 “Contact me”；没有发现专门禁止个人本机非商业后台预取的文字，不能扩大为全部个人缓存禁令；本轮未联系作者 |
| [Factory canonical page](https://reemr.se/factory/) | 同页识别 [2.0 deed](https://creativecommons.org/licenses/by-nc-sa/2.0/deed.en)、[4.0 deed](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.en)、[4.0 legalcode](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode)；版本差异保留，不声称已获澄清 |
| [Reserve canonical page](https://reemr.se/reserve/) | 本轮识别 4.0 deed、4.0 legalcode，没有识别到 2.0 链接；逐页保留证据 |
| [CC BY-NC-SA 4.0 正文](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode) | §2(a)(1)(A) 授予非商业复制/分享；§3(a) 规定分享时的署名、来源/许可及修改说明，§3(b) 规定分享改编内容时相同方式共享；§2(a)(6) 不表示作者背书 |
| [CC BY-NC-SA 2.0 正文](https://creativecommons.org/licenses/by-nc-sa/2.0/legalcode.en) | §3(a) 包含复制，§4(c) 限非商业；§4(a)、(b)、(d) 分别规定相关分发许可、改编分享及署名条件；不能忽略页面的混合版本证据 |

判断：已查文字支持在公开许可条件下作个人本机非商业复制的有限解释；未发现把这种复制按
“前台点击/后台预取”区分并禁止后者的条款。这个判断不等于作者对本软件单独授权，
不等于确认全部未查页面，也不代表网站上传、商业用途或再托管已经获准。
保持 `usage_scope: personal-local-noncommercial`、`separate_author_permission: false`、
`redistribution_enabled: false`；保留 re3mr 署名、来源、实际许可链接、版本与是否修改记录。

Stage3 **“排除后台预取”是谨慎实现选择，不是已确认的授权禁令**。
Stage4 Preview 默认将 `reemr`、`eftarkov`、`tarkov.dev` 所有允许来源纳入后台预取，当前地图优先。
下载并发 2、完整解码并发 1；磁盘缓存上限 512 MiB，采用 LRU 淘汰，支持取消和逐项状态。
每项入队及使用缓存前仍需权限检查，许可解释不会覆盖 robots、401/403 或其他访问限制。
不随 EXE/ZIP 带图、不上传仓库/CDN/网站、不提供公共代理；手机/LAN 不返回这些图片，
包括桌面热缓存；手机保留来源链接和“高清原图仅在桌面本机显示；手机可手动开来源”提示。

## 2. 本轮 HTTP 与 robots 证据（已核查）

普通 GET，使用模块现有明确 User-Agent；关闭自动重定向，不换域名、代理或伪装身份绕过。
只读目录实例未设置 `cache_root`，注入的 fetcher 拒绝所有图片请求；没有调用 `floor_image()`。
HTML 在内存解析，SHA-256 是对应响应正文摘要，不是媒体哈希。UTC 时间见表，均对应上海日期 2026-10-20。

| 请求 URL | HTTP / 类型 | 完成时间 UTC |
| --- | --- | --- |
| [reemr.se robots](https://reemr.se/robots.txt) | 200 / text/plain，166 bytes | `2026-10-19T16:18:22.311161+00:00` |
| [首页](https://reemr.se/) | 200 / text/html，152727 bytes | `2026-10-19T16:18:24.923833+00:00` |
| [Factory 实际目录入口](https://reemr.se/Factory/) | 200 / text/html，154850 bytes；HTML canonical 为 `/factory/` | `2026-10-19T16:18:32.805212+00:00` |
| [Reserve](https://reemr.se/reserve/) | 200 / text/html，198991 bytes；首轮目录/权限核查 | `2026-10-19T16:18:35.916825+00:00` |
| [Customs](https://reemr.se/customs/) | 200 / text/html，221166 bytes | `2026-10-19T16:18:48.626378+00:00` |
| [www.re3mr.com robots](https://www.re3mr.com/robots.txt) | 200 / text/plain，166 bytes | `2026-10-19T16:18:50.938163+00:00` |
| [maps.reemr.se robots](https://maps.reemr.se/robots.txt) | 301，Location 为 `https://reemr.se/`；未跟随，不是有效 robots | 同一轮核查；传输适配器未记录此跳转的精确完成时间 |
| [FAQ](https://reemr.se/about/) | 200 / text/html，124862 bytes | `2026-10-19T16:19:19.305543+00:00` |
| [Reserve](https://reemr.se/reserve/) | 200 / text/html，198991 bytes；补核 canonical、明确 anchor 与大小提示 | `2026-10-19T16:19:21.697352+00:00` |

两个 200 robots 正文相同，SHA-256 均为
`c919b7dd2cb837681018545b0aa594b78496e5e53e97857fd3979f2280258e5b`。
规则正文如下（保留换行；末行无换行）：

```text
# START YOAST BLOCK
# ---------------------------
User-agent: *
Disallow:

Sitemap: https://reemr.se/sitemap_index.xml
# ---------------------------
# END YOAST BLOCK
```

通配 User-agent、空 Disallow，允许本轮对应公开路径；这是访问规则证据，不能当作版权授权。
`maps.reemr.se/robots.txt` 指向首页的异常跳转没有被当作允许；不访问该域名图片，
不改写原图域名寻找副本。301 由适配器返回空 body，不把空 body 的摘要冒充服务器 robots 正文摘要。
403 不重试绕过；HTML robots、失效规则、网络失败或明确 Disallow 均不能借旧允许状态继续取图。

正文摘要：

| HTML 响应 | SHA-256 |
| --- | --- |
| 首页 | `f86bf34c733c6cad6f1f3515be4c6c4f954b45f1e2688752f4c0667a6487c704` |
| Factory `/Factory/` | `2799bdf778cf12d044c580918bc21b14354bd66b213656211a1d9226e706da36` |
| Reserve 首轮 | `28dbb7dfbe1bfec1d72fda88510506f1ab77cba4f6fb4d2602d3dbf45cfecfd7` |
| Customs | `0311dd1060c30878c3df6ea776f556ee9ef4fec8c45a3b74195e45c47f639e9f` |
| FAQ | `b88eab2bd4bea71f7051e7f541daddc28cf90f53c4c6606effc1699b6507ac3d` |
| Reserve 补核 | `ee473d1511475c8862ee7fed11136c9c7ba592ae6b09972a864345454388cdd2` |

Reserve 两次 HTML 摘要不同，候选 href、版本、canonical 和大小提示一致；不将动态 HTML 摘要变化
断言为图片更新。本表是前段目录核查证据，不冒充后续单图实测时的页面快照。

### 仍须拒绝的 7 项

对 Factory、Reserve 主图的 `check_floor_access()` 本轮返回 `allowed: true`；
下列 7 项全部抛出 `ReemrPolicyError`。这些调用只检查 HTML/robots，没有读取媒体。

| canonical page / mapId | 名称 / floorKey | HTML 中的明确原图 href（仅记录，未请求） |
| --- | --- | --- |
| [Customs](https://reemr.se/customs/) / `customs` | CUSTOMS / `image-55b82fecdfe4824228fb` | `https://maps.reemr.se/Customs/re3mrCustoms2.png` |
| 同上 | DORMS 2D 1.1B / `image-17ee93f2f4d9aaf92dd9` | `https://maps.reemr.se/Customs/re3mrCustomsDorms.png` |
| 同上 | CUSTOMS [OLD] / `image-65a162b547cf4e2eba89` | `https://maps.reemr.se/Customs/re3mrCustomsCardinalNDay.png` |
| 同上 | DORMS 3D [OLD] / `image-88c2aa9c3d9f2f979ffc` | `https://maps.reemr.se/Customs/re3mrDorms3d.png` |
| [Reserve](https://reemr.se/reserve/) / `reserve` | TUNNELS 2D / `image-fa116515842271b17a77` | `https://maps.reemr.se/Reserve/re3mrReserveTunnels.png` |
| 同上 | TUNNELS 3D / `image-101621472b2de669592a` | `https://maps.reemr.se/Reserve/re3mrReserveTunnels3D.png` |
| 同上 | OLD / `image-976ffa196c45e31bc457` | `https://maps.reemr.se/Reserve/re3mrReserveNight.png` |

原因均为该 origin 未取得有效 robots，不是伪称规则明确写了 `Disallow`。即使本机已有旧图片缓存，
也必须在返回图片字节前拒绝。未来 robots 恢复有效时须重新核查，本文没有放行这些项。

## 3. 唯一新增代表性原图：Reserve

| 字段 | 当前证据 |
| --- | --- |
| canonical page / 模块 source_page_url | [https://reemr.se/reserve/](https://reemr.se/reserve/)；HTML `rel="canonical"` 与目录一致 |
| source_provider / mapId | `reemr` / `reserve` |
| floorKey | `image-4914dcf5533a14f4aa0b`，由当前模块 `map_data("reserve")` 返回 |
| 名称 / 版本 | RESERVE / Version 1.3F；当前非 OLD 版本 |
| 明确原图 href | `https://reemr.se/maps/Reserve/Re3mrReserveLossless.png` |
| 链接来源 | 同页具名 RESERVE anchor 与 Version 1.3F anchor 指向同一 href，均含 lightbox 尺寸属性；不是猜链接、缩略图或 Photoshop 文件 |
| 页面文件大小提示 | **约 17.1 MB**，仅为候选筛选提示；实测为 **6,719,090 bytes**，不以提示替代实际大小 |
| HTML 尺寸提示 | `data-lbwps-width="5760"`、`data-lbwps-height="3240"`；后续 QA 实际解码结果也为 **5760 × 3240** |
| origin / robots | `https://reemr.se`；上述有效 robots 允许，`check_floor_access` 已返回允许 |
| 许可 | 页面 4.0 deed 与 4.0 legalcode；个人本机非商业，未获单独授权 |
| 实际格式 / 大小 / 尺寸 | **PNG / 6,719,090 bytes / 5760 × 3240**；QA 记录在编译应用内解码并复用磁盘热缓存 |
| 实际媒体 SHA-256 | `b00692eba5c04cdab77429edca280b6bb5d2328da3420c852185c4dc5ce6066f` |
| HTTP/MIME 响应头、耗时、ETag/Last-Modified | 本次引用报告未提供，不从扩展名或 HTML 提示推断 |

Factory 原图 origin 为 `https://www.re3mr.com`，floorKey 为 `image-e67e61c0c039bb7980e0`；
Reserve 主图来自不同 origin，且是不同地图/目录项，可以补充跨 origin 代表性。
这里的 floorKey 是原图切换项，不声称验证了另一个独立游戏楼层。
Reserve 的隧道项虽有不同区域意义，但 robots 未通过，不为追求楼层覆盖而读取。

明确 anchor 的精简摘录：

```html
<a href="https://reemr.se/maps/Reserve/Re3mrReserveLossless.png" data-lbwps-width="5760" data-lbwps-height="3240">RESERVE</a>
```

## 4. 主线程 QA 结果与实际预算

证据：`<local-qa>\eft-repair-stage4-20261020\reports\default-migration.json`。
以下读取 **`report.preload.preload`**，各来源状态位于 **`report.preload.preload.sources`**，
不要误读外层 `report.preload.sources`。报告 `status: passed` 表示该次 QA 检查通过，不表示全图下载完成。

本次范围为 `scope: all`，但显式限制 **1 个新增资产 + 32 MiB（33,554,432 bytes）**。
实际 `pass_requests: 1`、`pass_assets: 1`、`pass_bytes: 6719090`，没有全图下载。

| 来源 | 发现 | 缓存已有/命中 | 新下载 | 拦截 | 预算待继续（`over_budget`） |
| --- | ---: | ---: | ---: | ---: | ---: |
| `reemr` | 28 | 1 | 1 | 8 | 18 |
| `eftarkov` | 57 | 2 | 0 | 0 | 55 |
| `tarkov.dev` | 38 | 38 | 0 | 0 | 0 |
| 合计 | **123** | **41** | **1** | **8** | **73** |

`done: 42` 包含 41 项缓存与 1 项下载，不能算作 42 次新增下载；资源计数也不等于独立媒体张数。
`deferred: 73`、`paused_budget: true`、`scope_complete: false`、`all_complete: false`，
`failed: 0` 不会抵消 8 项拦截。7 项 `maps.reemr.se` 因无有效 robots 继续拒绝；
额外 Woods 首项 `image-9db5574720b7f2e2d669` 因 robots 读取超时而 fail closed，禁止缓存回退。
这 **不是 8 张媒体都返回 HTTP 403**，也不是 Woods 明确被永久 Disallow。

旧计划中的 **25,000,000 bytes 单图硬流拦截未实施**；实际沿用产品既有
**50,000,000 bytes/图**安全上限及格式/像素校验。Reserve 实测大小小于 25 MB，
但不能据此声称验证过 25 MB 流拦截。32 MiB 是本次预热批次预算，与单图安全上限和磁盘缓存容量分开。

## 5. 启动参数与覆盖边界

| CLI 参数 | Stage4 Preview 行为 |
| --- | --- |
| `--no-preload` | 仅关闭启动预热，不关闭按需取图或手动预热；不传时默认所有允许来源 |
| `--preload-budget-mib N` | 每批预热下载预算，整数 `1..512`，默认 `512` MiB；本次 QA 为 `32` |
| `--preload-max-assets N` | 每批新增资产上限，整数 `1..512`，默认 `512`；本次 QA 为 `1` |

磁盘缓存上限 512 MiB + LRU 与单批下载预算分别计算；后台下载并发 2、解码并发 1。
预算暂停后需明确继续，不保证所有允许原图永久同时保留。

Factory 沿用 Stage3 已有单图证据；Reserve 是本次唯一新增真实媒体，报告确认应用内解码及磁盘热缓存复用。
第 2 节仍只代表 HTML/robots 核查，合成 fixture 也不等于真实地图验收。
历史“13 页 / 28 项 / 21 项域名规则可读”是目录记录，不能推成 21 张原图均已验证。
手机/LAN 不返回 RE3MR 原图（包括桌面热缓存），保留来源链接；**未实体手机验证，未所有地图真实原图验证**。
本报告没有补齐逐图桌面缩放/全屏、全面离线或实体手机覆盖。默认路径重启及编译验证由主线程独立完成，
本次文档收尾不重复执行，也不预写其结果。
