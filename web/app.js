const elements = {
  appShell: document.querySelector("#appShell"),
  connection: document.querySelector("#connectionState"),
  languageToggle: document.querySelector("#languageToggle"),
  languageToggleLabel: document.querySelector("#languageToggleLabel"),
  themeToggle: document.querySelector("#themeToggle"),
  themeToggleIcon: document.querySelector("#themeToggleIcon"),
  themeToggleLabel: document.querySelector("#themeToggleLabel"),
  profile: document.querySelector("#profileSelect"),
  capture: document.querySelector("#captureButton"),
  screenshotFolderInput: document.querySelector("#screenshotFolderInput"),
  screenshotDirectoryStatus: document.querySelector("#screenshotDirectoryStatus"),
  pageBadge: document.querySelector("#pageBadge"),
  canvas: document.querySelector("#screenshotCanvas"),
  canvasPlaceholder: document.querySelector("#canvasPlaceholder"),
  captureHistory: document.querySelector("#captureHistory"),
  screenshotCandidates: document.querySelector("#screenshotCandidates"),
  analysis: document.querySelector("#analysisSummary"),
  diagnosticDetails: document.querySelector("#diagnosticDetails"),
  rows: document.querySelector("#taskRows"),
  taskCount: document.querySelector("#taskCount"),
  showHiddenTasksButton: document.querySelector("#showHiddenTasksButton"),
  clearTasks: document.querySelector("#clearTasksButton"),
  emptyTasks: document.querySelector("#emptyTasks"),
  taskTraderFilter: document.querySelector("#taskTraderFilter"),
  taskMapFilter: document.querySelector("#taskMapFilter"),
  keySummaryCount: document.querySelector("#keySummaryCount"),
  keySummaryNote: document.querySelector("#keySummaryNote"),
  keySummaryRows: document.querySelector("#keySummaryRows"),
  keyOwnershipDialog: document.querySelector("#keyOwnershipDialog"),
  keyOwnershipImage: document.querySelector("#keyOwnershipImage"),
  keyOwnershipImageFallback: document.querySelector("#keyOwnershipImageFallback"),
  keyOwnershipName: document.querySelector("#keyOwnershipName"),
  keyOwnershipQuestion: document.querySelector("#keyOwnershipQuestion"),
  keyOwnershipYesButton: document.querySelector("#keyOwnershipYesButton"),
  keyOwnershipNoButton: document.querySelector("#keyOwnershipNoButton"),
  keyOwnershipLaterButton: document.querySelector("#keyOwnershipLaterButton"),
  hideoutPlannerPanel: document.querySelector("#hideoutPlannerPanel"),
  hideoutPlannerToggle: document.querySelector("#hideoutPlannerToggle"),
  hideoutPlannerContent: document.querySelector("#hideoutPlannerContent"),
  hideoutLevelsResetButton: document.querySelector("#hideoutLevelsResetButton"),
  hideoutRefreshButton: document.querySelector("#hideoutRefreshButton"),
  hideoutStatus: document.querySelector("#hideoutStatus"),
  hideoutStations: document.querySelector("#hideoutStations"),
  hideoutMaterialsPanel: document.querySelector("#hideoutMaterialsPanel"),
  hideoutMaterialsCard: document.querySelector(".hideout-materials-bottom"),
  hideoutMaterialsCount: document.querySelector("#hideoutMaterialsCount"),
  hideoutMaterialsResetButton: document.querySelector("#hideoutMaterialsResetButton"),
  hideoutMaterials: document.querySelector("#hideoutMaterials"),
  operationHistoryList: document.querySelector("#operationHistoryList"),
  operationHistoryCount: document.querySelector("#operationHistoryCount"),
  operationHistoryPanel: document.querySelector("#operationHistoryPanel"),
  logs: document.querySelector("#logLines"),
  logPath: document.querySelector("#logPath"),
  taskForm: document.querySelector("#taskForm"),
  addTaskPanel: document.querySelector(".add-task-details"),
  catalogPanel: document.querySelector("#catalogPanel"),
  catalogRefresh: document.querySelector("#catalogRefreshButton"),
  catalogSearch: document.querySelector("#catalogSearch"),
  catalogSummary: document.querySelector("#catalogSummary"),
  catalogStatus: document.querySelector("#catalogStatus"),
  catalogResults: document.querySelector("#catalogResults"),
  catalogPreview: document.querySelector("#catalogPreview"),
  catalogTrader: document.querySelector("#catalogTrader"),
  catalogTitle: document.querySelector("#catalogTitle"),
  catalogObjectives: document.querySelector("#catalogObjectives"),
  catalogSourceLink: document.querySelector("#catalogSourceLink"),
  catalogImport: document.querySelector("#catalogImportButton"),
  mapPlannerPanel: document.querySelector("#mapPlannerPanel"),
  mobileCompanionButton: document.querySelector("#mobileCompanionButton"),
  mobilePairingDialog: document.querySelector("#mobilePairingDialog"),
  closeMobilePairingButton: document.querySelector("#closeMobilePairingButton"),
  mobilePairingNotice: document.querySelector("#mobilePairingNotice"),
  mobilePairingContent: document.querySelector("#mobilePairingContent"),
  mobilePairingAddress: document.querySelector("#mobilePairingAddress"),
  mobilePairingQr: document.querySelector("#mobilePairingQr"),
  mobilePairingStatus: document.querySelector("#mobilePairingStatus"),
  mobilePairingUrl: document.querySelector("#mobilePairingUrl"),
  refreshMobilePairingButton: document.querySelector("#refreshMobilePairingButton"),
  mapSelect: document.querySelector("#mapSelect"),
  mapFloorSelect: document.querySelector("#mapFloorSelect"),
  mapAnnotationFilters: document.querySelector("#mapAnnotationFilters"),
  mapImageFrame: document.querySelector("#mapImageFrame"),
  mapDrawings: document.querySelector("#mapDrawings"),
  mapDrawButton: document.querySelector("#mapDrawButton"),
  mapUndoDrawingButton: document.querySelector("#mapUndoDrawingButton"),
  mapClearDrawingsButton: document.querySelector("#mapClearDrawingsButton"),
  mapTooltip: document.querySelector("#mapTooltip"),
  mapPointImageDialog: document.querySelector("#mapPointImageDialog"),
  mapPointImageTitle: document.querySelector("#mapPointImageTitle"),
  mapPointImageDescription: document.querySelector("#mapPointImageDescription"),
  mapPointImageGallery: document.querySelector("#mapPointImageGallery"),
  mapPointImageUnavailable: document.querySelector("#mapPointImageUnavailable"),
  mapPointImageSource: document.querySelector("#mapPointImageSource"),
  closeMapPointImageButton: document.querySelector("#closeMapPointImageButton"),
  mapCanvas: document.querySelector("#mapCanvas"),
  mapImage: document.querySelector("#mapImage"),
  mapMarkers: document.querySelector("#mapMarkers"),
  mapZoomOutButton: document.querySelector("#mapZoomOutButton"),
  mapZoomInButton: document.querySelector("#mapZoomInButton"),
  mapZoomResetButton: document.querySelector("#mapZoomResetButton"),
  mapZoomLevel: document.querySelector("#mapZoomLevel"),
  mapFullscreenButton: document.querySelector("#mapFullscreenButton"),
  mapPlaceholder: document.querySelector("#mapPlaceholder"),
  mapSourceLink: document.querySelector("#mapSourceLink"),
  mapSummary: document.querySelector("#mapSummary"),
  mapTargetList: document.querySelector("#mapTargetList"),
  mapHint: document.querySelector("#mapHint"),
  diagnosticsPanel: document.querySelector(".diagnostics-panel"),
  profileDialog: document.querySelector("#profileDialog"),
  profileForm: document.querySelector("#profileForm"),
  profileDialogTitle: document.querySelector("#profileDialogTitle"),
  profileModeField: document.querySelector("#profileModeField"),
  cancelProfileButton: document.querySelector("#cancelProfileButton"),
  seasonField: document.querySelector("#seasonField"),
  toast: document.querySelector("#toast"),
};

const UI_TRANSLATIONS = Object.freeze({
  "EFT 任务助手": "EFT Task Assistant",
  "本地塔科夫助手": "Local Tarkov companion",
  "切换到白天模式": "Switch to light mode",
  "切换到黑夜模式": "Switch to dark mode",
  "白天模式": "Light mode",
  "黑夜模式": "Dark mode",
  "连接本地服务…": "Connecting to local service…",
  "本地服务已连接": "Local service connected",
  "本地服务连接中断": "Local service disconnected",
  "打开快速跳转目录": "Open quick navigation",
  "快速跳转目录": "Quick navigation",
  "目录": "Jump",
  "切换到英文": "Switch to English",
  "切换到中文": "Switch to Chinese",
  "截图识别": "Screenshot review",
  "任务清单": "Quest list",
  "任务钥匙": "Quest keys",
  "藏身处规划": "Hideout plan",
  "地图点位": "Map objectives",
  "升级物品统计": "Upgrade materials",
  "处理记录": "Recent actions",
  "暂无操作记录": "No actions recorded yet",
  "撤销": "Undo",
  "已撤销": "Undone",
  "先撤销较新的操作": "Undo newer actions first",
  "显示隐藏任务": "Show hidden quests",
  "收起隐藏任务": "Hide hidden quests",
  "清零藏身处等级": "Reset hideout levels",
  "识别诊断与日志": "Diagnostics & logs",
  "游戏档案": "Game profile",
  "新建档案": "New profile",
  "浏览器授权读取本机截图目录": "Browser access to local screenshots",
  "选择截图文件夹": "Choose screenshot folder",
  "等待截图": "Waiting for screenshot",
  "等待游戏画面": "Waiting for game capture",
  "选择本机游戏截图文件夹后，截图会自动导入并识别": "Choose your local game screenshot folder to import and review captures automatically",
  "尚未选择截图文件夹。截图只会在浏览器授权后读取。": "No screenshot folder selected. The browser reads it only after you grant access.",
  "截图目录授权保存在当前浏览器；截图和识别记录保存在本机，最多保留最近 10 条。": "Screenshot-folder access stays in this browser; screenshots and recognition records stay on this computer, with the latest 10 retained.",
  "当前浏览器不支持持续目录授权；请重新选择截图文件夹进行扫描。": "This browser does not support persistent folder access. Choose the screenshot folder again to scan it.",
  "尚未识别页面": "No page reviewed yet",
  "切换显示隐藏任务": "Toggle hidden quests",
  "切换显示被钥匙筛选隐藏或手动隐藏的任务": "Show or hide quests hidden by key filters or manually",
  "切换隐藏": "Toggle hidden",
  "清空任务": "Clear quests",
  "商人": "Trader",
  "地图": "Map",
  "按商人筛选": "Filter by trader",
  "按地图筛选": "Filter by map",
  "全部商人": "All traders",
  "全部地图": "All maps",
  "当前档案还没有任务。可以手动添加、从资料库导入，或在截图识别后核对候选。": "This profile has no quests yet. Add one manually, import from the catalog, or review screenshot matches.",
  "手动添加任务": "Add quest manually",
  "例如 Therapist": "e.g. Therapist",
  "任务名称": "Quest name",
  "任务要求": "Objectives",
  "每行填写一项要求，方便单独勾选进度": "Enter one objective per line to track progress separately",
  "目标物品": "Target item",
  "可选": "Optional",
  "已有": "Owned",
  "待准备": "To get",
  "所需数量": "Quantity needed",
  "不计数留空": "Leave blank if not countable",
  "保存任务": "Save quest",
  "从 EFTarkov 任务资料库导入": "Import from EFTarkov quest catalog",
  "同步公开目录": "Sync public catalog",
  "搜索任务名或商人": "Search quest or trader",
  "尚未同步任务资料。": "Quest catalog has not been synced.",
  "先同步目录，再搜索要追踪的任务。": "Sync the catalog, then search for a quest to track.",
  "加入清单": "Add to list",
  "打开 EFTarkov 来源页": "Open EFTarkov source",
  "来源页面标注版本不等于游戏补丁版本；覆盖情况未经官方逐项核对。资料只作为人工确认的候选，不会自动标记完成或修改进度。": "The source page version may differ from the game patch. Coverage is not verified item by item; imported data is a reviewable suggestion and never changes quest progress automatically.",
  "0 种": "0 types",
  "钥匙默认未勾选，勾选后显示关联任务及地图点位；新钥匙会提示确认是否已有。": "Keys start unchecked. Check one to show related quests and map points. New keys prompt you to confirm whether you own them.",
  "EFTarkov 地图来源": "EFTarkov map source",
  "地图标注": "Map annotations",
  "地图地点": "Map locations",
  "PMC撤离点": "PMC extracts",
  "SCAV撤离点": "SCAV extracts",
  "转移点": "Transit points",
  "地点": "Locations",
  "PMC撤离": "PMC extracts",
  "SCAV撤离": "SCAV extracts",
  "左键编号标记查看点位信息，右键切换到访勾选（勾显示在标记右下角）；右侧可隐藏单个点或查看全部说明图片。悬停撤离/转移标记可立即查看名称和楼层。": "Left-click numbered markers for point details; right-click to toggle visited status (the check appears at the marker's bottom-right). Hide individual points or view all source images in the list. Hover over extract/transit markers for instant names and floor details.",
  "悬停撤离/转移点立即查看名称和楼层；点击标记查看来源图片。": "Hover over extract/transit points for instant names and floor details; click a marker to view source images.",
  "底图、地点与撤离/转移点数据来自 EFTarkov 公开页面；可用上方开关筛选地图地点、PMC 撤离点、SCAV 撤离点和转移点。任务点位及标注保留楼层信息，任务隐藏会同步地图任务点位；右键任务标点可切换到访勾选。": "Basemap, locations, extraction points, and transit points come from EFTarkov. Use the switches above to filter locations, PMC/SCAV extracts, and transit points. Quest markers and annotations retain floor details; hiding a quest also hides its quest markers. Right-click quest markers to toggle visited status.",
  "手机地图二维码": "Mobile map QR code",
  "MOBILE RAID MAP": "MOBILE RAID MAP",
  "手机随身地图": "Mobile raid map",
  "手机扫码后可只读查看地图和当前档案任务，无需账号或证书。二维码两分钟内有效、只能使用一次；关闭窗口会撤销未使用的二维码。": "Scan with your phone to read the map and current profile's quests; no account or certificate is needed. The QR code expires in two minutes and works once; closing this dialog revokes an unused code.",
  "选择手机所在网络": "Choose the network used by your phone",
  "选择局域网地址": "Choose LAN address",
  "重新生成二维码": "Generate a new QR code",
  "手机访问地址：": "Phone address: ",
  "二维码有效期：": "QR code expires in: ",
  "秒": "s",
  "手机地图服务未能启动；请检查端口占用和 Windows 防火墙。": "The phone map service could not start. Check for a port conflict and Windows Firewall settings.",
  "当前没有可用的局域网 IPv4 地址。": "No usable LAN IPv4 address was found.",
  "正在查找局域网地址…": "Looking for LAN addresses…",
  "正在生成二维码…": "Generating QR code…",
  "二维码已过期，请重新生成。": "The QR code expired. Generate a new one.",
  "二维码有效期：": "QR code expires in: ",
  "扫描后手机将自动进入只读地图，无需账号或密码。": "After scanning, your phone opens the read-only map automatically; no account or password is needed.",
  "选择地址后生成二维码。": "Choose an address to generate a QR code.",
  "当前档案还没有任务。": "There are no quests in the current profile.",
  "任务地图载入失败。": "The quest map could not be loaded.",
  "请扫描电脑端生成的二维码，只读查看地图和任务；无需账号。": "Scan the QR code generated on the computer to view the map and quests; no account is needed.",
  "二维码无效或已过期，请回到电脑端重新生成。": "This QR code is invalid or expired. Generate another one on your computer.",
  "当前没有可用的地图点位。": "There are no map markers to show.",
  "已到访": "Visited",
  "可选": "Optional",
  "已完成": "Complete",
  "标记已到访": "Mark visited",
  "取消已到访标记": "Clear visited status",
  "查看来源": "View source",
  "结束手机访问": "End phone access",
  "结束访问": "End access",
  "结束": "End",
  "没有找到对应任务。": "The related quest was not found.",
  "选择地图": "Select map",
  "楼层": "Floor",
  "选择楼层": "Select floor",
  "点位图例": "Map legend",
  "任务目标": "Quest objective",
  "已到访": "Visited",
  "地图视图控制": "Map controls",
  "按住鼠标拖动绘制路线": "Click and drag to draw a route",
  "划线": "Draw route",
  "撤销线条": "Undo line",
  "清除线条": "Clear lines",
  "缩小地图": "Zoom out",
  "放大地图": "Zoom in",
  "重置": "Reset",
  "全屏": "Fullscreen",
  "正在加载地图目录…": "Loading map catalog…",
  "左键查看点位信息，右键标记/取消已到访（标记右下角显示勾）；右侧可从要求链接查看点位，或单独隐藏该点。": "Left-click a marker for details; right-click to toggle its visited check. Use the links on the right for waypoint details or hide an individual point.",
  "选择地图后显示已追踪任务的自动点位。": "Tracked quest waypoints appear after you select a map.",
  "底图与任务目标坐标来自 EFTarkov 公开页面；地图仅显示任务目标，不标记钥匙用途位置。楼层切换只更换底图，标点始终显示该地图所有楼层的任务点，地点保留楼层名；右侧任务组的“隐藏/显示”会同步任务清单与地图点位，右键标点可切换到访勾选。": "Map images and quest coordinates come from EFTarkov public pages. Maps show quest objectives, not key-use locations. Switching floors changes only the base image; markers from every floor remain visible, with floor names retained. Hiding a quest group also hides it in the quest list. Right-click a marker to toggle its visited check.",
  "升级目标": "Upgrade targets",
  "收起": "Collapse",
  "展开": "Expand",
  "清除所有设施的勾选和等级计划，不影响已有物品数量": "Clear selected stations and level targets without changing owned material counts",
  "等级清零": "Reset levels",
  "刷新资料": "Refresh data",
  "正在读取 PvE 藏身处升级资料…": "Loading PvE hideout upgrade data…",
  "需求 0 件 · 已有 0 件 · 尚缺 0 件": "Required 0 · Owned 0 · Missing 0",
  "已有数量清零": "Reset owned counts",
  "高级信息": "Advanced details",
  "刷新日志": "Refresh logs",
  "本次分区与候选": "Current regions & candidates",
  "等待分析结果": "Waiting for analysis",
  "本地运行日志": "Local runtime log",
  "加载中…": "Loading…",
  "截图仅在本机浏览器授权后读取，并发送到本机服务进行识别；最多保留最近 10 次。截图不会上传到云端，日志仅记录识别证据、操作和错误。": "Screenshots are read with browser permission on this computer and processed by its local service; up to 10 recent captures are kept. Screenshots are not sent to the cloud. Logs contain recognition evidence, actions, and errors.",
  "WAYPOINT IMAGE": "WAYPOINT IMAGE",
  "任务点位": "Quest waypoint",
  "关闭": "Close",
  "该点位没有可用的独立说明图片。": "No standalone waypoint image is available.",
  "上一张点位图片": "Previous waypoint image",
  "上一张": "Previous",
  "下一张点位图片": "Next waypoint image",
  "下一张": "Next",
  "打开 EFTarkov 点位来源": "Open EFTarkov waypoint source",
  "确认是否已有这把钥匙": "Do you already own this key?",
  "稍后": "Later",
  "我还没有": "I don't have it",
  "我有这把钥匙": "I have this key",
  "新建游戏档案": "Create game profile",
  "档案名称": "Profile name",
  "例如：主 PvE 档": "e.g. Main PvE",
  "游戏模式": "Game mode",
  "赛季 PvP": "Seasonal PvP",
  "赛季编号": "Season ID",
  "例如：2026": "e.g. 2026",
  "取消": "Cancel",
  "创建档案": "Create profile",
  "隐藏任务": "Hide quest",
  "显示任务": "Show quest",
  "显示任务并启用关联钥匙筛选": "Show quest and enable its related key filters",
  "隐藏任务与地图点位": "Hide quest and map points",
  "任务及关联钥匙筛选已显示": "Quest shown and related key filters enabled",
  "取消隐藏": "Unhide",
  "+1 进度": "+1 progress",
  "标记任务完成": "Mark quest complete",
  "删除任务": "Delete quest",
  "任务完成": "Quest complete",
  "未完成": "Incomplete",
  "已完成": "Complete",
  "进行中": "In progress",
  "待复核": "Needs review",
  "完成任务": "Complete quest",
  "需要钥匙": "Key required",
  "需要物品": "Item required",
  "钥匙获取": "Key source",
  "获取方式": "How to obtain",
  "当前等级": "Current level",
  "目标等级": "Target level",
  "未建造": "Not built",
  "最高等级": "Max level",
  "最高": "Max",
  "自动前置": "Auto prerequisite",
  "升级前置": "Upgrade prerequisite",
  "已满足": "Met",
  "已列入计划": "Planned",
  "未满足": "Not met",
  "离线缓存": "Offline cache",
  "PvE 数据": "PvE data",
  "数据": "Data",
  "结束划线": "Finish route",
  "退出全屏": "Exit fullscreen",
  "展开任务要求和操作": "Expand quest objectives and actions",
  "折叠任务要求和操作": "Collapse quest objectives and actions",
  "任务清单和地图点位共用此手动隐藏状态；钥匙筛选独立控制显示": "Manual hiding is shared by the quest list and map; key filters are independent",
  "任务与目标已加入当前档案": "Quest and objectives added to this profile",
  "任务已保存": "Quest saved",
  "任务已从当前清单删除": "Quest removed from this list",
  "档案已创建并切换": "Profile created and selected",
  "任务和地图点位已隐藏": "Quest and map points hidden",
  "任务和地图点位已显示": "Quest and map points shown",
  "本张截图没有匹配到新的任务。": "No new quests matched this capture.",
  "处理中": "Processing",
  "未命名任务": "Unnamed quest",
  "未命名目标": "Unnamed objective",
  "未命名要求": "Unnamed requirement",
  "未命名物品": "Unnamed item",
  "任务所需钥匙与物品": "Quest keys and items",
  "任务地图位置": "Quest map locations",
  "详情页暂无可验证的自动点位；资料库更新后会在地图区自动显示。": "No verifiable automatic waypoints are available yet. They will appear on the map when the catalog is updated.",
  "正在读取任务目标…": "Loading quest objectives…",
  "任务点位已读取，但 EFTarkov 底图暂时无法加载；请检查网络后重试。": "Waypoint data loaded, but the EFTarkov map image is unavailable. Check the network and try again.",
  "未能载入地图数据。": "Map data could not be loaded.",
  "截图预览加载失败": "Screenshot preview failed to load",
  "任务已加入当前档案": "Quest added to this profile",
  "任务已自动完成": "Quest completed automatically",
  "缺少要求": "Objectives remaining",
  "暂无运行日志": "No runtime logs",
  "运行日志仅管理员可查看": "Runtime logs are available to admins only",
  "正在载入": "Loading",
  "未知版本": "Unknown version",
});

const UI_TRANSLATIONS_REVERSE = Object.fromEntries(Object.entries(UI_TRANSLATIONS).map(([source, target]) => [target, source]));
let currentLanguage = "zh";

function translateUiText(value) {
  const translations = currentLanguage === "en" ? UI_TRANSLATIONS : UI_TRANSLATIONS_REVERSE;
  const match = value.match(/^(\s*)([\s\S]*?)(\s*)$/u);
  if (!match) return value;
  const [, leading, text, trailing] = match;
  let translated = translations[text];
  if (!translated) translated = translateDynamicUiText(text);
  return translated ? `${leading}${translated}${trailing}` : value;
}

function translateDynamicUiText(text) {
  const patterns = currentLanguage === "en"
    ? [
      [/^需求 ([\d,]+) 件 · 已有 ([\d,]+) 件 · 尚缺 ([\d,]+) 件$/u, ([, required, owned, missing]) => `Required ${required} · Owned ${owned} · Missing ${missing}`],
      [/^需求 ([\d,]+) 件$/u, ([, count]) => `Required ${count} items`],
      [/^尚缺 ([\d,]+) 件$/u, ([, count]) => `${count} items missing`],
      [/^需战局内获得 ([\d,]+) 件$/u, ([, count]) => `Found in raid: ${count}`],
      [/^([\d,]+) 项要求$/u, ([, count]) => `${count} objectives`],
      [/^截图添加通知（([\d,]+) 张截图 · ([\d,]+) 个任务；最新在前）：$/u, ([, captures, quests]) => `Screenshot activity (${captures} captures · ${quests} quests; newest first):`],
      [/^([\d,]+) 个识别任务$/u, ([, count]) => `${count} matched quests`],
      [/^已隐藏 · (.+)$/u, ([, status]) => `Hidden · ${translateDynamicUiText(status) || UI_TRANSLATIONS[status] || status}`],
      [/^(.+) · 来源 · (.+)$/u, ([, source, version]) => `${source} · Source: ${version}`],
      [/^(.+) · 来源标注 (.+)$/u, ([, trader, version]) => `${trader} · Source version ${version}`],
      [/^最高等级 ([\d,]+)$/u, ([, level]) => `Max level ${level}`],
      [/^最高 ([\d,]+) 级$/u, ([, level]) => `Max ${level}`],
      [/^等级 ([\d,]+)$/u, ([, level]) => `Level ${level}`],
      [/^地图目录读取失败：(.*)$/u, ([, error]) => `Map catalog failed: ${error}`],
      [/^地图载入失败：(.*)$/u, ([, error]) => `Map failed to load: ${error}`],
      [/^藏身处资料读取失败：(.*)$/u, ([, error]) => `Hideout data failed to load: ${error}`],
      [/^截图文件夹：(.+)$/u, ([, error]) => `Screenshot folder: ${error}`],
      [/^(.+) · (\d+) 个显示任务组 · (\d+) 个地图标点(?: · (\d+) 个已隐藏)?$/u, ([, map, groups, points, hidden]) => `${map} · ${groups} visible quest groups · ${points} map markers${hidden ? ` · ${hidden} hidden` : ""}`],
      [/^任务 (\d+) · (.+)$/u, ([, number, title]) => `Quest ${number} · ${title}`],
      [/^点位 (\d+)\/(\d+)$/u, ([, point, total]) => `Waypoint ${point}/${total}`],
      [/^(.+) 需要这把钥匙。你现在有吗？$/u, ([, task]) => `${task} requires this key. Do you have it?`],
      [/^需 ([\d,]+) 件$/u, ([, count]) => `${count} needed`],
      [/^需求 ([€$₽][\d,]+)$/u, ([, amount]) => `Required ${amount}`],
      [/^尚缺 ([€$₽][\d,]+)$/u, ([, amount]) => `${amount} missing`],
    ]
    : [
      [/^Required ([\d,]+) · Owned ([\d,]+) · Missing ([\d,]+)$/u, ([, required, owned, missing]) => `需求 ${required} 件 · 已有 ${owned} 件 · 尚缺 ${missing} 件`],
      [/^Required ([\d,]+) items$/u, ([, count]) => `需求 ${count} 件`],
      [/^([\d,]+) items missing$/u, ([, count]) => `尚缺 ${count} 件`],
      [/^Found in raid: ([\d,]+)$/u, ([, count]) => `需战局内获得 ${count} 件`],
      [/^([\d,]+) objectives$/u, ([, count]) => `${count} 项要求`],
      [/^Screenshot activity \(([\d,]+) captures · ([\d,]+) quests; newest first\):$/u, ([, captures, quests]) => `截图添加通知（${captures} 张截图 · ${quests} 个任务；最新在前）：`],
      [/^([\d,]+) matched quests$/u, ([, count]) => `${count} 个识别任务`],
      [/^Hidden · (.+)$/u, ([, status]) => `已隐藏 · ${UI_TRANSLATIONS_REVERSE[status] || status}`],
      [/^(.+) · Source: (.+)$/u, ([, source, version]) => `${source} · 来源 · ${version}`],
      [/^(.+) · Source version (.+)$/u, ([, trader, version]) => `${trader} · 来源标注 ${version}`],
      [/^Max level ([\d,]+)$/u, ([, level]) => `最高等级 ${level}`],
      [/^Max ([\d,]+)$/u, ([, level]) => `最高 ${level} 级`],
      [/^Level ([\d,]+)$/u, ([, level]) => `等级 ${level}`],
      [/^Map catalog failed: (.*)$/u, ([, error]) => `地图目录读取失败：${error}`],
      [/^Map failed to load: (.*)$/u, ([, error]) => `地图载入失败：${error}`],
      [/^Hideout data failed to load: (.*)$/u, ([, error]) => `藏身处资料读取失败：${error}`],
      [/^(.+) · (\d+) visible quest groups · (\d+) map markers(?: · (\d+) hidden)?$/u, ([, map, groups, points, hidden]) => `${map} · ${groups} 个显示任务组 · ${points} 个地图标点${hidden ? ` · ${hidden} 个已隐藏` : ""}`],
      [/^Quest (\d+) · (.+)$/u, ([, number, title]) => `任务 ${number} · ${title}`],
      [/^Waypoint (\d+)\/(\d+)$/u, ([, point, total]) => `点位 ${point}/${total}`],
      [/^(.+) requires this key\. Do you have it\?$/u, ([, task]) => `${task} 需要这把钥匙。你现在有吗？`],
      [/^([\d,]+) needed$/u, ([, count]) => `需 ${count} 件`],
      [/^Required ([€$₽][\d,]+)$/u, ([, amount]) => `需求 ${amount}`],
      [/^([€$₽][\d,]+) missing$/u, ([, amount]) => `尚缺 ${amount}`],
    ];
  if (currentLanguage === "en" && /^\d+ 条$/u.test(text)) {
    return `${text.replace(/ 条$/u, "")} actions`;
  }
  if (currentLanguage === "zh" && /^\d+ actions$/u.test(text)) {
    return `${text.replace(/ actions$/u, "")} 条`;
  }
  const operationLabels = currentLanguage === "en"
    ? {
      隐藏任务: "Hide quest", 显示任务: "Show quest", 隐藏地图点位: "Hide map point", 显示地图点位: "Show map point",
      显示隐藏任务: "Show hidden quests", 收起隐藏任务: "Hide hidden quests", 更新任务计数: "Updated quest counter",
      调整藏身处计划: "Changed hideout plan", 清零藏身处等级: "Reset hideout levels", 清空已有物品数量: "Reset owned materials",
      更新已有物品数量: "Updated owned quantity", 钥匙状态: "Changed key filter", 任务要求进度: "Changed quest objective",
      标记任务完成: "Completed quest", 增加任务进度: "Incremented quest progress", 删除任务: "Deleted quest",
      添加任务: "Added quest", 更新任务: "Updated quest", 导入任务: "Imported quest", 清空任务清单: "Cleared quest list",
      到访标记: "Changed waypoint visit", 新增手绘线条: "Drew map route", 撤销手绘线条: "Undid map route", 清除手绘线条: "Cleared map routes",
    }
    : {
      "Hide quest": "隐藏任务", "Show quest": "显示任务", "Hide map point": "隐藏地图点位", "Show map point": "显示地图点位",
      "Show hidden quests": "显示隐藏任务", "Hide hidden quests": "收起隐藏任务", "Updated quest counter": "更新任务计数",
      "Changed hideout plan": "调整藏身处计划", "Reset hideout levels": "清零藏身处等级", "Reset owned materials": "清空已有物品数量",
      "Updated owned quantity": "更新已有物品数量", "Changed key filter": "钥匙状态", "Changed quest objective": "任务要求进度",
      "Completed quest": "标记任务完成", "Incremented quest progress": "增加任务进度", "Deleted quest": "删除任务",
      "Added quest": "添加任务", "Updated quest": "更新任务", "Imported quest": "导入任务", "Cleared quest list": "清空任务清单",
      "Changed waypoint visit": "到访标记", "Drew map route": "新增手绘线条", "Undid map route": "撤销手绘线条", "Cleared map routes": "清除手绘线条",
    };
  const directOperationLabels = currentLanguage === "en"
    ? { 清零藏身处等级: "Reset hideout levels", 显示隐藏任务: "Show hidden quests", 收起隐藏任务: "Hide hidden quests" }
    : { "Reset hideout levels": "清零藏身处等级", "Show hidden quests": "显示隐藏任务", "Hide hidden quests": "收起隐藏任务" };
  if (directOperationLabels[text]) return directOperationLabels[text];
  const separator = currentLanguage === "en" ? "：" : ": ";
  const separatorIndex = text.indexOf(separator);
  if (separatorIndex >= 0) {
    const action = text.slice(0, separatorIndex);
    if (operationLabels[action]) {
      let detail = text.slice(separatorIndex + separator.length);
      if (currentLanguage === "en") {
        detail = detail
          .replaceAll("加入升级备料", "Added to upgrade plan")
          .replaceAll("从升级备料移除", "Removed from upgrade plan")
          .replaceAll("当前等级 ", "Current level ")
          .replaceAll("目标等级 ", "Target level ")
          .replaceAll("等级 ", "Level ")
          .replaceAll("未建造", "Not built")
          .replaceAll("标记为已有", "Marked as owned")
          .replaceAll("标记为待准备", "Marked as needed")
          .replaceAll("显示关联任务和地图点位", "Show related quests and map points")
          .replaceAll("隐藏关联任务和地图点位", "Hide related quests and map points")
          .replaceAll("已勾选完成", "Marked complete")
          .replaceAll("已取消完成勾选", "Marked incomplete")
          .replaceAll("任务已自动完成", "Quest auto-completed")
          .replaceAll(" 件", " items");
      } else {
        detail = detail
          .replaceAll("Added to upgrade plan", "加入升级备料")
          .replaceAll("Removed from upgrade plan", "从升级备料移除")
          .replaceAll("Current level ", "当前等级 ")
          .replaceAll("Target level ", "目标等级 ")
          .replaceAll("Level ", "等级 ")
          .replaceAll("Not built", "未建造")
          .replaceAll("Marked as owned", "标记为已有")
          .replaceAll("Marked as needed", "标记为待准备")
          .replaceAll("Show related quests and map points", "显示关联任务和地图点位")
          .replaceAll("Hide related quests and map points", "隐藏关联任务和地图点位")
          .replaceAll("Marked complete", "已勾选完成")
          .replaceAll("Marked incomplete", "已取消完成勾选")
          .replaceAll("Quest auto-completed", "任务已自动完成")
          .replaceAll(" items", " 件");
      }
      const detailPrefix = currentLanguage === "en" ? ": " : "：";
      return operationLabels[action] + (detail ? detailPrefix + detail : "");
    }
  }
  if (currentLanguage === "en" && text.startsWith("撤销失败：")) return `Undo failed: ${text.slice(5)}`;
  if (currentLanguage === "zh" && text.startsWith("Undo failed: ")) return `撤销失败：${text.slice(13)}`;
  if (currentLanguage === "en" && text.startsWith("已撤销：")) return `Undone: ${text.slice(4)}`;
  if (currentLanguage === "zh" && text.startsWith("Undone: ")) return `已撤销：${text.slice(8)}`;
  for (const [pattern, format] of patterns) {
    const match = text.match(pattern);
    if (match) return format(match);
  }
  return "";
}

function localizeElement(element) {
  for (const attribute of ["placeholder", "title", "aria-label"]) {
    const value = element.getAttribute(attribute);
    if (value) {
      const translated = translateUiText(value);
      if (translated !== value) element.setAttribute(attribute, translated);
    }
  }
  for (const node of element.childNodes) {
    if (node.nodeType === Node.TEXT_NODE) {
      const translated = translateUiText(node.data);
      if (translated !== node.data) node.data = translated;
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      localizeElement(node);
    }
  }
}

function applyLanguage(language, persist = false) {
  currentLanguage = language === "en" ? "en" : "zh";
  document.documentElement.lang = currentLanguage === "en" ? "en" : "zh-CN";
  document.title = currentLanguage === "en" ? "EFT Task Assistant" : "EFT 任务助手";
  elements.languageToggleLabel.textContent = currentLanguage === "en" ? "中文" : "EN";
  const targetLanguageLabel = currentLanguage === "en" ? "切换到中文" : "切换到英文";
  elements.languageToggle.setAttribute("aria-label", targetLanguageLabel);
  elements.languageToggle.title = targetLanguageLabel;
  localizeElement(document.body);
  if (persist) safeStorageSet("eft-task-assistant-language", currentLanguage);
}

const languageObserver = new MutationObserver((records) => {
  for (const record of records) {
    if (record.type === "characterData") {
      const translated = translateUiText(record.target.data);
      if (translated !== record.target.data) record.target.data = translated;
    } else if (record.type === "attributes") {
      localizeElement(record.target);
    } else {
      for (const node of record.addedNodes) {
        if (node.nodeType === Node.ELEMENT_NODE) localizeElement(node);
        else if (node.nodeType === Node.TEXT_NODE) {
          const translated = translateUiText(node.data);
          if (translated !== node.data) node.data = translated;
        }
      }
    }
  }
});
languageObserver.observe(document.body, {
  subtree: true,
  childList: true,
  characterData: true,
  attributes: true,
  attributeFilter: ["placeholder", "title", "aria-label"],
});

let state = null;
let profileNameSetupOpen = false;
let clearTasksBusy = false;
let operationUndoBusy = false;
let loadedCaptureId = null;
let sourceImage = null;
let drawnScreenshotOverlayKey = "";
let screenshotFolderHandle = null;
let screenshotFolderOwnerId = null;
let screenshotFolderName = "";
let screenshotFolderBaselineAt = 0;
let screenshotFolderSeen = new Set();
let screenshotFolderInitial = new Set();
let screenshotFolderScanning = false;
const screenshotImportsInFlight = new Set();
const SCREENSHOT_FOLDER_DB_NAME = "eft-task-assistant-screenshot-folders-v1";
const SCREENSHOT_FOLDER_DB_STORE = "folders";
const SCREENSHOT_FOLDER_STORAGE_PREFIX = "eft-task-assistant-screenshot-folder-v1:";
const SCREENSHOT_FOLDER_INITIAL_LIMIT = 8;
let toastTimer = null;
let catalogSnapshotId = null;
let selectedCatalogTask = null;
let catalogSearchTimer = null;
let catalogImportBusy = false;
let catalogQueryGeneration = 0;
let mapView = null;
let mapViewGeneration = 0;
let mobilePairingTimer = null;
let mobilePairingExpiresAt = 0;
let mobilePairingGeneration = 0;
let mobilePairingActive = false;
let mobilePairingQueue = Promise.resolve();
let mapPointImageUrls = [];
let mapDetailWarnings = [];
let mapTaskIdsByMap = new Map();
let mapZoom = 1;
let mapPan = null;
const hiddenTaskIds = new Set();
const hiddenMapPointIds = new Set();
const hiddenKeyIds = new Set();
const collapsedMapTaskGroups = new Set();
const collapsedTaskIds = new Set();
let taskKeyIdsByTask = new Map();
let keySummaryEntries = [];
let keySummaryRenderSignature = "";
let activeKeyOwnershipId = "";
const deferredKeyOwnershipIds = new Set();
let showHiddenTasks = false;
const MAP_ZOOM_MIN = 0.5;
const MAP_ZOOM_MAX = 3;
const MAP_ZOOM_STEP = 0.25;
const UI_PREFERENCE_VERSION = 1;
const UI_PREFERENCE_STORAGE_PREFIX = "eft-task-assistant-ui-v1:";
const MAP_DRAWING_MAX_STROKES_PER_MAP = 40;
const MAP_DRAWING_MAX_POINTS_PER_STROKE = 1000;
const MAP_DRAWING_MAX_POINTS_TOTAL = 12000;
const OPERATION_HISTORY_LIMIT = 40;
let uiPreferenceScopeId = null;
let uiPreferences = null;
let hideoutCatalog = null;
let hideoutLoading = null;
let mapDrawingEnabled = false;
let activeMapDrawing = null;
let activeMapDrawingElement = null;

function safeStorageGet(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeStorageSet(key, value) {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

function defaultUiPreferences() {
  return {
    version: UI_PREFERENCE_VERSION,
    selectedMapId: "",
    selectedMapFloors: {},
    mapAnnotationVisibility: {
      location: true,
      "pmc-exit": false,
      "scav-exit": false,
      transfer: false,
    },
    taskTraderFilter: "",
    taskMapFilter: "",
    mapZoom: 1,
    hiddenTaskIds: [],
    showHiddenTasks: false,
    hiddenMapPointIds: [],
    hiddenKeyIds: [],
    keyFilterInitialized: false,
    keyFilterKnownIds: [],
    newKeyIds: [],
    keyOwnershipPendingIds: [],
    keyOwnershipAnswers: {},
    collapsedMapTaskGroups: [],
    collapsedTaskIds: [],
    hideoutPlan: {},
    hideoutOwnedMaterials: {},
    operationHistory: [],
    operationHistoryOpen: true,
    hideoutPlannerOpen: true,
    hideoutMaterialsOpen: true,
    panels: {
      addTask: Boolean(elements.addTaskPanel?.open),
      catalog: Boolean(elements.catalogPanel?.open),
      diagnostics: Boolean(elements.diagnosticsPanel?.open),
    },
    mapDrawings: {},
  };
}

function sanitizeMapDrawings(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const drawings = {};
  let remainingPoints = MAP_DRAWING_MAX_POINTS_TOTAL;
  const mapEntries = Object.entries(value).filter(([mapId, strokes]) => (
    typeof mapId === "string" && mapId.length <= 120 && Array.isArray(strokes)
  )).slice(-40).reverse();
  for (const [mapId, sourceStrokes] of mapEntries) {
    const strokes = [];
    for (const sourceStroke of sourceStrokes.slice(-MAP_DRAWING_MAX_STROKES_PER_MAP).reverse()) {
      if (!Array.isArray(sourceStroke)) continue;
      const points = sourceStroke.slice(-MAP_DRAWING_MAX_POINTS_PER_STROKE).flatMap((point) => {
        if (!Array.isArray(point) || point.length < 2) return [];
        const x = Number(point[0]);
        const y = Number(point[1]);
        if (!Number.isFinite(x) || !Number.isFinite(y)) return [];
        return [[Math.min(1, Math.max(0, x)), Math.min(1, Math.max(0, y))]];
      });
      if (points.length < 2 || remainingPoints < 2) continue;
      const keptPoints = points.slice(0, remainingPoints);
      if (keptPoints.length >= 2) {
        strokes.unshift(keptPoints);
        remainingPoints -= keptPoints.length;
      }
    }
    if (strokes.length) drawings[mapId] = strokes;
    if (remainingPoints < 2) break;
  }
  return drawings;
}

function readUiPreferences(scopeId, legacyProfileId = null) {
  const defaults = defaultUiPreferences();
  try {
    const stored = safeStorageGet(UI_PREFERENCE_STORAGE_PREFIX + String(scopeId))
      || (legacyProfileId === null
        ? null
        : safeStorageGet(UI_PREFERENCE_STORAGE_PREFIX + String(legacyProfileId)));
    const parsed = stored ? JSON.parse(stored) : null;
    if (!parsed || parsed.version !== UI_PREFERENCE_VERSION) return defaults;
    const zoom = Number(parsed.mapZoom);
    return {
      ...defaults,
      selectedMapId: typeof parsed.selectedMapId === "string" ? parsed.selectedMapId : "",
      selectedMapFloors: parsed.selectedMapFloors
        && typeof parsed.selectedMapFloors === "object"
        && !Array.isArray(parsed.selectedMapFloors)
        ? Object.fromEntries(Object.entries(parsed.selectedMapFloors)
          .filter(([mapId, floorKey]) => typeof mapId === "string" && mapId.length <= 120
            && typeof floorKey === "string" && floorKey.length <= 120)
          .slice(-100))
        : {},
      taskTraderFilter: typeof parsed.taskTraderFilter === "string" ? parsed.taskTraderFilter : "",
      taskMapFilter: typeof parsed.taskMapFilter === "string" ? parsed.taskMapFilter : "",
      mapAnnotationVisibility: Object.fromEntries(Object.keys(defaults.mapAnnotationVisibility).map((key) => [
        key,
        typeof parsed.mapAnnotationVisibility?.[key] === "boolean"
          ? parsed.mapAnnotationVisibility[key]
          : defaults.mapAnnotationVisibility[key],
      ])),
      mapZoom: Number.isFinite(zoom) ? Math.min(MAP_ZOOM_MAX, Math.max(MAP_ZOOM_MIN, zoom)) : 1,
      hiddenTaskIds: Array.isArray(parsed.hiddenTaskIds || parsed.hiddenMapTaskIds)
        ? [...new Set((parsed.hiddenTaskIds || parsed.hiddenMapTaskIds).filter((key) => typeof key === "string" && key.length <= 240))].slice(-500)
        : [],
      showHiddenTasks: Boolean(parsed.showHiddenTasks),
      hiddenMapPointIds: Array.isArray(parsed.hiddenMapPointIds)
        ? [...new Set(parsed.hiddenMapPointIds.filter((key) => typeof key === "string" && key.length <= 280))].slice(-1000)
        : [],
      hiddenKeyIds: Array.isArray(parsed.hiddenKeyIds)
        ? [...new Set(parsed.hiddenKeyIds.filter((key) => typeof key === "string" && key.length <= 280))].slice(-300)
        : [],
      keyFilterInitialized: parsed.keyFilterInitialized === true,
      keyFilterKnownIds: Array.isArray(parsed.keyFilterKnownIds)
        ? [...new Set(parsed.keyFilterKnownIds.filter((key) => typeof key === "string" && key.length <= 280))].slice(-300)
        : [],
      newKeyIds: Array.isArray(parsed.newKeyIds)
        ? [...new Set(parsed.newKeyIds.filter((key) => typeof key === "string" && key.length <= 280))].slice(-300)
        : [],
      keyOwnershipPendingIds: Array.isArray(parsed.keyOwnershipPendingIds)
        ? [...new Set(parsed.keyOwnershipPendingIds.filter((key) => typeof key === "string" && key.length <= 280))].slice(-300)
        : [],
      keyOwnershipAnswers: parsed.keyOwnershipAnswers
        && typeof parsed.keyOwnershipAnswers === "object"
        && !Array.isArray(parsed.keyOwnershipAnswers)
        ? Object.fromEntries(Object.entries(parsed.keyOwnershipAnswers)
          .filter(([key, value]) => typeof key === "string" && key.length <= 280 && typeof value === "boolean")
          .slice(-300))
        : {},
      collapsedMapTaskGroups: Array.isArray(parsed.collapsedMapTaskGroups)
        ? [...new Set(parsed.collapsedMapTaskGroups.filter((key) => typeof key === "string" && key.length <= 500))].slice(-1000)
        : [],
      collapsedTaskIds: Array.isArray(parsed.collapsedTaskIds)
        ? [...new Set(parsed.collapsedTaskIds.filter((key) => typeof key === "string" && key.length <= 240))].slice(-500)
        : [],
      hideoutPlan: parsed.hideoutPlan && typeof parsed.hideoutPlan === "object" && !Array.isArray(parsed.hideoutPlan)
        ? Object.fromEntries(Object.entries(parsed.hideoutPlan)
          .filter(([key, value]) => typeof key === "string" && key.length <= 120 && value && typeof value === "object")
          .slice(-100)
          .map(([key, value]) => [key, {
            enabled: Boolean(value.enabled),
            currentLevel: Math.max(0, Math.min(20, Number(value.currentLevel) || 0)),
            targetLevel: Number.isFinite(Number(value.targetLevel))
              ? Math.max(0, Math.min(20, Number(value.targetLevel)))
              : 1,
          }]))
        : {},
      hideoutOwnedMaterials: parsed.hideoutOwnedMaterials
        && typeof parsed.hideoutOwnedMaterials === "object"
        && !Array.isArray(parsed.hideoutOwnedMaterials)
        ? Object.fromEntries(Object.entries(parsed.hideoutOwnedMaterials)
          .filter(([key, value]) => typeof key === "string" && key.length <= 280 && Number.isFinite(Number(value)))
          .slice(-500)
          .map(([key, value]) => [key, Math.min(1000000, Math.max(0, Math.floor(Number(value))))]))
        : {},
      operationHistory: Array.isArray(parsed.operationHistory)
        ? parsed.operationHistory
          .filter((entry) => entry && typeof entry === "object"
            && typeof entry.id === "string"
            && typeof entry.label === "string"
            && typeof entry.type === "string"
            && entry.data && typeof entry.data === "object"
            && !Array.isArray(entry.data))
          .slice(-OPERATION_HISTORY_LIMIT)
          .map((entry) => ({
            id: entry.id.slice(0, 100),
            label: entry.label.slice(0, 500),
            type: entry.type.slice(0, 40),
            time: typeof entry.time === "string" ? entry.time.slice(0, 40) : "",
            data: entry.data,
            undone: Boolean(entry.undone),
          }))
        : [],
      operationHistoryOpen: typeof parsed.operationHistoryOpen === "boolean"
        ? parsed.operationHistoryOpen
        : defaults.operationHistoryOpen,
      hideoutPlannerOpen: typeof parsed.hideoutPlannerOpen === "boolean"
        ? parsed.hideoutPlannerOpen
        : defaults.hideoutPlannerOpen,
      hideoutMaterialsOpen: typeof parsed.hideoutMaterialsOpen === "boolean"
        ? parsed.hideoutMaterialsOpen
        : defaults.hideoutMaterialsOpen,
      panels: {
        addTask: typeof parsed.panels?.addTask === "boolean" ? parsed.panels.addTask : defaults.panels.addTask,
        catalog: typeof parsed.panels?.catalog === "boolean" ? parsed.panels.catalog : defaults.panels.catalog,
        diagnostics: typeof parsed.panels?.diagnostics === "boolean" ? parsed.panels.diagnostics : defaults.panels.diagnostics,
      },
      mapDrawings: sanitizeMapDrawings(parsed.mapDrawings),
    };
  } catch {
    return defaults;
  }
}

function saveUiPreferences() {
  if (!uiPreferences || uiPreferenceScopeId === null) return;
  if (elements.mapSelect.value) uiPreferences.selectedMapId = elements.mapSelect.value;
  if (mapView?.map_id === elements.mapSelect.value && elements.mapFloorSelect.value) {
    uiPreferences.selectedMapFloors[mapView.map_id] = elements.mapFloorSelect.value;
  }
  uiPreferences.taskTraderFilter = elements.taskTraderFilter.value;
  uiPreferences.taskMapFilter = elements.taskMapFilter.value;
  uiPreferences.mapZoom = mapZoom;
  uiPreferences.mapAnnotationVisibility = Object.fromEntries(
    [...elements.mapAnnotationFilters.querySelectorAll("input[data-map-annotation-filter]")]
      .map((input) => [input.dataset.mapAnnotationFilter, input.checked]),
  );
  uiPreferences.hiddenTaskIds = [...hiddenTaskIds];
  uiPreferences.showHiddenTasks = showHiddenTasks;
  uiPreferences.hiddenMapPointIds = [...hiddenMapPointIds];
  uiPreferences.hiddenKeyIds = [...hiddenKeyIds];
  uiPreferences.collapsedMapTaskGroups = [...collapsedMapTaskGroups];
  uiPreferences.collapsedTaskIds = [...collapsedTaskIds];
  uiPreferences.hideoutPlannerOpen = !elements.hideoutPlannerContent.hidden;
  uiPreferences.hideoutMaterialsOpen = elements.hideoutMaterialsPanel.open;
  uiPreferences.operationHistoryOpen = elements.operationHistoryPanel.open;
  uiPreferences.panels = {
    addTask: elements.addTaskPanel.open,
    catalog: elements.catalogPanel.open,
    diagnostics: elements.diagnosticsPanel.open,
  };
  const saved = safeStorageSet(
    UI_PREFERENCE_STORAGE_PREFIX + uiPreferenceScopeId,
    JSON.stringify(uiPreferences),
  );
  if (!saved) toast("浏览器未能保存界面缓存；请检查本地存储空间或隐私设置。");
}

function cloneUndoValue(value) {
  return JSON.parse(JSON.stringify(value));
}

function captureUiUndoSnapshot() {
  if (!uiPreferences) return null;
  return {
    hiddenTaskIds: [...hiddenTaskIds],
    showHiddenTasks,
    hiddenMapPointIds: [...hiddenMapPointIds],
    hiddenKeyIds: [...hiddenKeyIds],
    keyOwnershipAnswers: cloneUndoValue(uiPreferences.keyOwnershipAnswers || {}),
    keyOwnershipPendingIds: [...(uiPreferences.keyOwnershipPendingIds || [])],
    newKeyIds: [...(uiPreferences.newKeyIds || [])],
    hideoutPlan: cloneUndoValue(uiPreferences.hideoutPlan || {}),
    hideoutOwnedMaterials: cloneUndoValue(uiPreferences.hideoutOwnedMaterials || {}),
  };
}

function captureMapDrawingUndoSnapshot(mapId) {
  if (!uiPreferences) return null;
  return { mapId, strokes: cloneUndoValue(uiPreferences.mapDrawings?.[mapId] || []) };
}

function recordMapDrawingOperation(label, before) {
  if (!before || !uiPreferences) return;
  const after = captureMapDrawingUndoSnapshot(before.mapId);
  if (JSON.stringify(before.strokes) === JSON.stringify(after.strokes)) return;
  recordOperation(label, "map-drawing", before);
}

function recordOperation(label, type, data) {
  if (!uiPreferences || !data) return;
  const history = Array.isArray(uiPreferences.operationHistory) ? uiPreferences.operationHistory : [];
  history.unshift({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
    label: String(label || "操作").slice(0, 500),
    type,
    time: new Date().toISOString(),
    data: cloneUndoValue(data),
    undone: false,
  });
  uiPreferences.operationHistory = history.slice(0, OPERATION_HISTORY_LIMIT);
  saveUiPreferences();
  renderOperationHistory();
}

function recordUiOperation(label, before) {
  if (!before || !uiPreferences) return;
  const after = captureUiUndoSnapshot();
  if (JSON.stringify(before) === JSON.stringify(after)) return;
  recordOperation(label, "ui", { before });
}

function taskSnapshot(task) {
  return task ? cloneUndoValue(task) : null;
}

function mostRecentUndoableOperation() {
  return uiPreferences?.operationHistory?.find((entry) => !entry.undone) || null;
}

function operationMapName(mapId) {
  const option = [...elements.mapSelect.options].find((entry) => entry.value === String(mapId || ""));
  return option?.dataset.mapName || option?.textContent.split(" · ")[0] || "当前地图";
}

function isOpaqueOperationDetail(value) {
  const detail = String(value || "").trim();
  return /^\d+$/u.test(detail) || /^[a-z0-9_-]{20,}$/iu.test(detail);
}

function operationHistoryLabel(entry) {
  const label = String(entry.label || "操作");
  const separatorIndex = label.indexOf("：");
  if (separatorIndex < 0) return label;
  const action = label.slice(0, separatorIndex);
  const detail = label.slice(separatorIndex + 1).trim();
  const data = entry.data || {};
  if (entry.type === "map-drawing") {
    return action + "：" + operationMapName(data.mapId);
  }
  if (action === "调整藏身处计划") {
    const stationId = detail.split(" · ")[0].trim();
    const station = hideoutCatalog?.stations?.find((item) => (
      String(item.id) === stationId || item.name === stationId
    ));
    if (!station) {
      return /[\p{Script=Han}\s]/u.test(stationId)
        ? label
        : "调整藏身处计划：升级设施";
    }
    return action + "：" + station.name + detail.slice(stationId.length);
  }
  if (action === "钥匙状态") {
    const keyName = detail.split(" · ")[0].trim();
    const key = keySummaryEntries.find((item) => item.id === keyName || item.name === keyName);
    if (key) return action + "：" + key.name + detail.slice(keyName.length);
    if (isOpaqueOperationDetail(keyName)) return "钥匙状态：钥匙";
  }
  const taskActions = new Set([
    "隐藏任务", "显示任务", "删除任务", "标记任务完成", "增加任务进度",
    "更新任务计数", "任务要求进度", "添加任务", "更新任务", "导入任务",
  ]);
  if (taskActions.has(action) && isOpaqueOperationDetail(detail)) {
    const task = data.beforeTask
      || state?.tasks?.find((item) => String(item.id) === detail || String(item.id) === String(data.afterTaskId));
    return task?.title ? action + "：" + task.title : action;
  }
  if (isOpaqueOperationDetail(detail)) return action;
  return label;
}

function renderOperationHistory() {
  if (!elements.operationHistoryList || !elements.operationHistoryCount) return;
  const history = uiPreferences?.operationHistory || [];
  elements.operationHistoryCount.textContent = `${history.length} 条`;
  elements.operationHistoryList.replaceChildren();
  if (!history.length) {
    const empty = document.createElement("li");
    empty.className = "operation-history-empty";
    empty.textContent = "暂无操作记录";
    elements.operationHistoryList.append(empty);
    return;
  }
  const undoable = mostRecentUndoableOperation();
  for (const entry of history) {
    const row = document.createElement("li");
    row.className = "operation-history-entry";
    const label = document.createElement("span");
    label.className = "operation-history-label";
    label.textContent = operationHistoryLabel(entry);
    const time = document.createElement("time");
    time.className = "operation-history-time";
    const date = new Date(entry.time);
    time.dateTime = Number.isNaN(date.getTime()) ? "" : date.toISOString();
    time.textContent = Number.isNaN(date.getTime())
      ? ""
      : new Intl.DateTimeFormat(currentLanguage === "en" ? "en-US" : "zh-CN", {
        month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
      }).format(date);
    const status = document.createElement("span");
    status.className = "operation-history-status";
    if (entry.undone) {
      status.classList.add("is-undone");
      status.textContent = "已撤销";
    } else if (entry === undoable) {
      status.textContent = "";
    } else {
      status.textContent = "先撤销较新的操作";
    }
    row.append(label, time, status);
    if (!entry.undone && entry === undoable) {
      const undoButton = document.createElement("button");
      undoButton.type = "button";
      undoButton.className = "button button-secondary button-small";
      undoButton.dataset.undoOperationId = entry.id;
      undoButton.textContent = "撤销";
      undoButton.disabled = operationUndoBusy;
      row.append(undoButton);
    }
    elements.operationHistoryList.append(row);
  }
}

async function applyUiUndoSnapshot(snapshot) {
  if (!uiPreferences || !snapshot) return;
  uiPreferences.hiddenTaskIds = [...(snapshot.hiddenTaskIds || [])];
  uiPreferences.showHiddenTasks = Boolean(snapshot.showHiddenTasks);
  uiPreferences.hiddenMapPointIds = [...(snapshot.hiddenMapPointIds || [])];
  uiPreferences.hiddenKeyIds = [...(snapshot.hiddenKeyIds || [])];
  uiPreferences.keyOwnershipAnswers = cloneUndoValue(snapshot.keyOwnershipAnswers || {});
  uiPreferences.keyOwnershipPendingIds = [...(snapshot.keyOwnershipPendingIds || [])];
  uiPreferences.newKeyIds = [...(snapshot.newKeyIds || [])];
  uiPreferences.hideoutPlan = cloneUndoValue(snapshot.hideoutPlan || {});
  uiPreferences.hideoutOwnedMaterials = cloneUndoValue(snapshot.hideoutOwnedMaterials || {});
  if (Object.prototype.hasOwnProperty.call(snapshot, "mapDrawings")) {
    uiPreferences.mapDrawings = cloneUndoValue(snapshot.mapDrawings || {});
  }
  hiddenTaskIds.clear();
  uiPreferences.hiddenTaskIds.forEach((id) => hiddenTaskIds.add(id));
  hiddenMapPointIds.clear();
  uiPreferences.hiddenMapPointIds.forEach((id) => hiddenMapPointIds.add(id));
  hiddenKeyIds.clear();
  uiPreferences.hiddenKeyIds.forEach((id) => hiddenKeyIds.add(id));
  showHiddenTasks = uiPreferences.showHiddenTasks;
  if (state) {
    renderTasks(state.tasks);
    renderMapTargets(mapView?.markers || [], mapView?.tasks || []);
  }
  if (hideoutCatalog) renderHideoutPlanner();
  renderMapDrawings();
  saveUiPreferences();
  syncHideoutMaterialsLayout();
}

async function undoOperation(operationId) {
  if (operationUndoBusy || !uiPreferences) return;
  const entry = mostRecentUndoableOperation();
  if (!entry || entry.id !== operationId) return;
  operationUndoBusy = true;
  renderOperationHistory();
  try {
    if (entry.type === "ui") {
      await applyUiUndoSnapshot(entry.data.before);
    } else if (entry.type === "task") {
      if (entry.data.beforeTask) {
        await post("/api/tasks/restore", { tasks: [entry.data.beforeTask] });
      } else if (entry.data.afterTaskId) {
        await post(`/api/tasks/${entry.data.afterTaskId}/delete`);
      }
      await refreshState();
      await loadMapIndex({ preserveSelection: true });
      if (entry.data.beforeUi) await applyUiUndoSnapshot(entry.data.beforeUi);
  } else if (entry.type === "tasks") {
      await post("/api/tasks/restore", { tasks: entry.data.beforeTasks || [] });
      await refreshState();
      await loadMapIndex({ preserveSelection: true });
      if (entry.data.beforeUi) await applyUiUndoSnapshot(entry.data.beforeUi);
    } else if (entry.type === "map-drawing") {
      if (entry.data.strokes?.length) uiPreferences.mapDrawings[entry.data.mapId] = cloneUndoValue(entry.data.strokes);
      else delete uiPreferences.mapDrawings[entry.data.mapId];
      saveUiPreferences();
      if (currentMapDrawingId() === entry.data.mapId) renderMapDrawings();
    } else if (entry.type === "map-visit") {
      await post("/api/map/markers/visit", {
        map_id: entry.data.mapId,
        marker_id: entry.data.markerId,
        visited: Boolean(entry.data.beforeVisited),
      });
      if (mapView?.map_id === entry.data.mapId) {
        const marker = mapView.markers?.find((item) => item.id === entry.data.markerId);
        if (marker) marker.visited = Boolean(entry.data.beforeVisited);
        renderMapTargets(mapView.markers || [], mapView.tasks || []);
      }
    } else {
      throw new Error("此操作类型暂不支持撤销。");
    }
    entry.undone = true;
    saveUiPreferences();
    renderOperationHistory();
    toast("已撤销：" + operationHistoryLabel(entry));
  } catch (error) {
    toast(`撤销失败：${error.message}`);
  } finally {
    operationUndoBusy = false;
    renderOperationHistory();
  }
}

function activateProfileUiPreferences(playerId, profileId, isAdmin = false) {
  const normalizedScopeId = `${String(playerId || "local")}:${String(profileId)}`;
  if (uiPreferenceScopeId === normalizedScopeId) return false;
  uiPreferenceScopeId = normalizedScopeId;
  deferredKeyOwnershipIds.clear();
  activeKeyOwnershipId = "";
  if (elements.keyOwnershipDialog.open) elements.keyOwnershipDialog.close();
  uiPreferences = readUiPreferences(normalizedScopeId, isAdmin ? profileId : null);
  hiddenTaskIds.clear();
  for (const key of uiPreferences.hiddenTaskIds) hiddenTaskIds.add(key);
  showHiddenTasks = uiPreferences.showHiddenTasks;
  hiddenMapPointIds.clear();
  for (const key of uiPreferences.hiddenMapPointIds) hiddenMapPointIds.add(key);
  hiddenKeyIds.clear();
  for (const key of uiPreferences.hiddenKeyIds) hiddenKeyIds.add(key);
  collapsedMapTaskGroups.clear();
  for (const key of uiPreferences.collapsedMapTaskGroups) collapsedMapTaskGroups.add(key);
  collapsedTaskIds.clear();
  for (const key of uiPreferences.collapsedTaskIds) collapsedTaskIds.add(key);
  elements.taskTraderFilter.value = "";
  elements.taskMapFilter.value = "";
  elements.addTaskPanel.open = uiPreferences.panels.addTask;
  elements.catalogPanel.open = uiPreferences.panels.catalog;
  elements.diagnosticsPanel.open = uiPreferences.panels.diagnostics;
  elements.mapAnnotationFilters.querySelectorAll("input[data-map-annotation-filter]").forEach((input) => {
    input.checked = uiPreferences.mapAnnotationVisibility[input.dataset.mapAnnotationFilter] !== false;
  });
  const hideoutSectionsOpen = uiPreferences.hideoutPlannerOpen && uiPreferences.hideoutMaterialsOpen;
  setHideoutSectionsOpen(hideoutSectionsOpen, false);
  elements.operationHistoryPanel.open = uiPreferences.operationHistoryOpen;
  setMapZoom(uiPreferences.mapZoom, false);
  setMapDrawingMode(false);
  renderMapDrawings();
  syncHideoutMaterialsLayout();
  renderOperationHistory();
  return true;
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const contentType = response.headers.get("Content-Type") || "";
  const result = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const error = new Error(result?.error || `请求失败（${response.status}）`);
    error.status = response.status;
    throw error;
  }
  return result;
}

function post(path, payload = {}) {
  return request(path, { method: "POST", body: JSON.stringify(payload) });
}

function setMobilePairingNotice(message, kind = "info") {
  elements.mobilePairingNotice.textContent = message;
  elements.mobilePairingNotice.dataset.kind = kind;
  elements.mobilePairingNotice.hidden = !message;
  elements.mobilePairingContent.hidden = true;
}

function drawMobilePairingQr(matrix) {
  if (!Array.isArray(matrix) || !matrix.length || matrix.some((row) => !Array.isArray(row) || row.length !== matrix.length)) {
    throw new Error("二维码数据格式无效。请重新生成。");
  }
  const size = matrix.length;
  const paths = [];
  matrix.forEach((row, y) => {
    let start = -1;
    for (let x = 0; x <= size; x += 1) {
      if (x < size && row[x]) {
        if (start < 0) start = x;
      } else if (start >= 0) {
        paths.push(`M${start} ${y}h${x - start}v1h-${x - start}z`);
        start = -1;
      }
    }
  });
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "手机地图配对二维码");
  const background = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  background.setAttribute("width", String(size));
  background.setAttribute("height", String(size));
  background.setAttribute("fill", "#fff");
  const modules = document.createElementNS("http://www.w3.org/2000/svg", "path");
  modules.setAttribute("d", paths.join(""));
  modules.setAttribute("fill", "#111214");
  modules.setAttribute("shape-rendering", "crispEdges");
  svg.append(background, modules);
  elements.mobilePairingQr.replaceChildren(svg);
}

function updateMobilePairingCountdown() {
  const remaining = Math.max(0, Math.ceil((mobilePairingExpiresAt - Date.now()) / 1000));
  if (!remaining) {
    clearInterval(mobilePairingTimer);
    mobilePairingTimer = null;
    elements.mobilePairingStatus.textContent = "二维码已过期，请重新生成。";
    return;
  }
  elements.mobilePairingStatus.textContent = `${translateUiText("二维码有效期：")}${remaining} ${translateUiText("秒")}`;
}

function generateMobilePairing() {
  const generation = ++mobilePairingGeneration;
  clearInterval(mobilePairingTimer);
  mobilePairingTimer = null;
  mobilePairingActive = true;
  elements.refreshMobilePairingButton.disabled = true;
  elements.mobilePairingQr.replaceChildren();
  elements.mobilePairingUrl.textContent = "";
  const operation = mobilePairingQueue.then(async () => {
    if (!elements.mobilePairingDialog.open || generation !== mobilePairingGeneration) return;
    elements.mobilePairingStatus.textContent = "正在生成二维码…";
    try {
      await post("/api/mobile/pairing/cancel");
      if (!elements.mobilePairingDialog.open || generation !== mobilePairingGeneration) return;
      const result = await post("/api/mobile/pairing", { address: elements.mobilePairingAddress.value });
      if (!elements.mobilePairingDialog.open) {
        await post("/api/mobile/pairing/cancel").catch(() => {});
        return;
      }
      if (generation !== mobilePairingGeneration) return;
      drawMobilePairingQr(result.matrix);
      elements.mobilePairingUrl.textContent = result.url;
      mobilePairingExpiresAt = Date.now() + Number(result.expires_in || 120) * 1000;
      mobilePairingActive = true;
      elements.mobilePairingNotice.hidden = true;
      elements.mobilePairingContent.hidden = false;
      updateMobilePairingCountdown();
      mobilePairingTimer = setInterval(updateMobilePairingCountdown, 1000);
    } catch (error) {
      if (generation === mobilePairingGeneration && elements.mobilePairingDialog.open) {
        setMobilePairingNotice(error.message, "error");
        elements.mobilePairingContent.hidden = false;
      }
    } finally {
      if (generation === mobilePairingGeneration) elements.refreshMobilePairingButton.disabled = false;
    }
  });
  mobilePairingQueue = operation.catch(() => {});
  return operation;
}

async function openMobilePairing() {
  if (!elements.mobilePairingDialog.open) elements.mobilePairingDialog.showModal();
  setMobilePairingNotice("正在查找局域网地址…");
  elements.mobilePairingQr.replaceChildren();
  elements.mobilePairingUrl.textContent = "";
  try {
    const network = await request("/api/mobile/info");
    if (!elements.mobilePairingDialog.open) return;
    if (!network.lan_enabled) {
      setMobilePairingNotice("手机地图服务未能启动；请检查端口占用和 Windows 防火墙。", "error");
      return;
    }
    const addresses = Array.isArray(network.addresses) ? network.addresses : [];
    if (!addresses.length) {
      setMobilePairingNotice("当前没有可用的局域网 IPv4 地址。", "error");
      return;
    }
    elements.mobilePairingAddress.replaceChildren(...addresses.map((address) => {
      const option = document.createElement("option");
      option.value = address;
      option.textContent = `${address}:${network.port}`;
      return option;
    }));
    elements.mobilePairingContent.hidden = false;
    await generateMobilePairing();
  } catch (error) {
    if (elements.mobilePairingDialog.open) setMobilePairingNotice(error.message, "error");
  }
}

function revokeMobilePairing() {
  mobilePairingGeneration += 1;
  clearInterval(mobilePairingTimer);
  mobilePairingTimer = null;
  elements.mobilePairingQr.replaceChildren();
  elements.mobilePairingUrl.textContent = "";
  elements.mobilePairingContent.hidden = true;
  elements.mobilePairingNotice.hidden = true;
  if (!mobilePairingActive) return;
  mobilePairingActive = false;
  post("/api/mobile/pairing/cancel").catch(() => {});
}

function closeMobilePairing() {
  if (elements.mobilePairingDialog.open) elements.mobilePairingDialog.close();
  revokeMobilePairing();
}

function screenshotFingerprint(entry) {
  return `${entry.path}|${entry.file.size}|${entry.file.lastModified}`;
}

function openScreenshotFolderDatabase() {
  return new Promise((resolve, reject) => {
    const opening = indexedDB.open(SCREENSHOT_FOLDER_DB_NAME, 1);
    opening.onupgradeneeded = () => {
      if (!opening.result.objectStoreNames.contains(SCREENSHOT_FOLDER_DB_STORE)) {
        opening.result.createObjectStore(SCREENSHOT_FOLDER_DB_STORE);
      }
    };
    opening.onsuccess = () => resolve(opening.result);
    opening.onerror = () => reject(opening.error || new Error("无法打开本机目录授权缓存。"));
  });
}

async function readScreenshotFolderRecord(playerId) {
  const database = await openScreenshotFolderDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(SCREENSHOT_FOLDER_DB_STORE, "readonly");
    const reading = transaction.objectStore(SCREENSHOT_FOLDER_DB_STORE).get(String(playerId));
    reading.onsuccess = () => resolve(reading.result || null);
    reading.onerror = () => reject(reading.error || new Error("无法读取本机目录授权缓存。"));
    transaction.oncomplete = () => database.close();
    transaction.onerror = () => database.close();
  });
}

async function writeScreenshotFolderRecord(playerId) {
  if (!screenshotFolderHandle || screenshotFolderOwnerId !== String(playerId)) return;
  const record = {
    handle: screenshotFolderHandle,
    name: screenshotFolderName,
    baselineAt: screenshotFolderBaselineAt,
    seen: [...screenshotFolderSeen].slice(-10000),
    initial: [...screenshotFolderInitial],
  };
  const database = await openScreenshotFolderDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(SCREENSHOT_FOLDER_DB_STORE, "readwrite");
    transaction.objectStore(SCREENSHOT_FOLDER_DB_STORE).put(record, String(playerId));
    transaction.oncomplete = () => {
      database.close();
      resolve();
    };
    transaction.onerror = () => {
      database.close();
      reject(transaction.error || new Error("无法保存本机目录授权缓存。"));
    };
  });
}

function setScreenshotDirectoryStatus(message) {
  elements.screenshotDirectoryStatus.textContent = message;
}

function isScreenshotFile(file) {
  return /\.(?:jpe?g|png|webp)$/i.test(file.name || "");
}

async function enumerateScreenshotFiles(directoryHandle, parentPath = "") {
  const files = [];
  for await (const [name, entry] of directoryHandle.entries()) {
    const path = parentPath ? `${parentPath}/${name}` : name;
    if (entry.kind === "directory") {
      files.push(...await enumerateScreenshotFiles(entry, path));
    } else if (entry.kind === "file") {
      const file = await entry.getFile();
      if (isScreenshotFile(file)) files.push({ file, path });
    }
  }
  return files;
}

async function encodeScreenshotAsJpeg(file) {
  const bitmap = await createImageBitmap(file);
  try {
    if (bitmap.width < 320 || bitmap.height < 200) {
      throw new Error("截图分辨率过低，无法识别游戏界面。");
    }
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    canvas.getContext("2d").drawImage(bitmap, 0, 0);
    const jpeg = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.88));
    if (!jpeg) throw new Error("浏览器无法转换截图格式。");
    if (jpeg.size > 16 * 1024 * 1024) throw new Error("截图转换后仍超过 16 MB。");
    return jpeg;
  } finally {
    bitmap.close?.();
  }
}

async function uploadScreenshotFile(file) {
  const jpeg = await encodeScreenshotAsJpeg(file);
  const response = await fetch("/api/capture/upload?source=screenshot_folder", {
    method: "POST",
    cache: "no-store",
    credentials: "same-origin",
    headers: { "Content-Type": "image/jpeg" },
    body: jpeg,
  });
  const contentType = response.headers.get("Content-Type") || "";
  const result = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) throw new Error(result?.error || `截图导入失败（${response.status}）`);
  if (!result?.accepted) throw new Error(result?.message || "截图队列已满，请稍后重试。");
  return result;
}

async function processScreenshotEntries(entries, { playerId, baselineAt, seen, initial }) {
  if (screenshotFolderScanning || !elements.appShell || elements.appShell.hidden) return;
  screenshotFolderScanning = true;
  const candidates = entries
    .filter((entry) => {
      const fingerprint = screenshotFingerprint(entry);
      return !seen.has(fingerprint)
        && !screenshotImportsInFlight.has(fingerprint)
        && (initial.has(fingerprint) || entry.file.lastModified > baselineAt);
    })
    .sort((left, right) => left.file.lastModified - right.file.lastModified)
    .slice(0, SCREENSHOT_FOLDER_INITIAL_LIMIT);
  let importedCount = 0;
  try {
    for (const entry of candidates) {
      const fingerprint = screenshotFingerprint(entry);
      screenshotImportsInFlight.add(fingerprint);
      try {
        const result = await uploadScreenshotFile(entry.file);
        seen.add(fingerprint);
        initial.delete(fingerprint);
        importedCount += 1;
        if (screenshotFolderHandle && screenshotFolderOwnerId === String(playerId)) {
          screenshotFolderSeen = seen;
          screenshotFolderInitial = initial;
          await writeScreenshotFolderRecord(playerId);
        } else {
          const storageKey = SCREENSHOT_FOLDER_STORAGE_PREFIX + playerId;
          const saved = JSON.parse(safeStorageGet(storageKey) || "{}");
          saved.seen = [...seen].slice(-10000);
          saved.initial = [...initial];
          safeStorageSet(storageKey, JSON.stringify(saved));
        }
        if (state?.player?.id === playerId) {
          setScreenshotDirectoryStatus(`已连接“${screenshotFolderName || "截图文件夹"}” · 已导入 ${importedCount} 张，正在识别…`);
          await refreshState();
        }
      } catch (error) {
        if (state?.player?.id === playerId) {
          setScreenshotDirectoryStatus(`截图导入暂停：${error.message}；稍后会重试。`);
        }
        break;
      } finally {
        screenshotImportsInFlight.delete(fingerprint);
      }
    }
  } finally {
    screenshotFolderScanning = false;
    if (state?.player?.id === playerId && !candidates.length) {
      setScreenshotDirectoryStatus(screenshotFolderHandle
        ? `已连接“${screenshotFolderName}” · 等待新截图`
        : "已选择截图文件夹；再次点按钮重新扫描新截图。");
    } else if (state?.player?.id === playerId && importedCount > 0) {
      setScreenshotDirectoryStatus(`已连接“${screenshotFolderName || "截图文件夹"}” · 本轮导入 ${importedCount} 张，等待新截图`);
    }
  }
}

async function scanScreenshotFolder() {
  if (!screenshotFolderHandle || screenshotFolderOwnerId !== String(state?.player?.id || "")) return;
  if (elements.appShell.hidden || document.hidden || screenshotFolderScanning) return;
  try {
    const permission = await screenshotFolderHandle.queryPermission({ mode: "read" });
    if (permission !== "granted") {
      setScreenshotDirectoryStatus(`已记住“${screenshotFolderName}”，请点击“选择截图文件夹”重新授权。`);
      return;
    }
    const files = await enumerateScreenshotFiles(screenshotFolderHandle);
    await processScreenshotEntries(files, {
      playerId: state.player.id,
      baselineAt: screenshotFolderBaselineAt,
      seen: screenshotFolderSeen,
      initial: screenshotFolderInitial,
    });
  } catch (error) {
    setScreenshotDirectoryStatus(`无法读取截图文件夹：${error.message}`);
  }
}

async function activateScreenshotFolder(playerId) {
  screenshotFolderHandle = null;
  screenshotFolderOwnerId = playerId ? String(playerId) : null;
  screenshotFolderName = "";
  screenshotFolderBaselineAt = 0;
  screenshotFolderSeen = new Set();
  screenshotFolderInitial = new Set();
  if (!playerId) return;
  if (!window.isSecureContext || typeof window.showDirectoryPicker !== "function") {
    setScreenshotDirectoryStatus(window.isSecureContext
      ? "当前浏览器不支持持续目录授权；请重新选择截图文件夹进行扫描。"
      : "当前浏览器无法持续读取目录；请重新选择截图文件夹进行扫描。"
    );
    return;
  }
  try {
    const saved = await readScreenshotFolderRecord(playerId);
    if (!saved?.handle) {
      setScreenshotDirectoryStatus("尚未选择截图文件夹。点击上方按钮并选择 Escape from Tarkov 的 Screenshots 文件夹。");
      return;
    }
    screenshotFolderHandle = saved.handle;
    screenshotFolderName = saved.name || saved.handle.name || "截图文件夹";
    screenshotFolderBaselineAt = Number(saved.baselineAt) || Date.now();
    screenshotFolderSeen = new Set(saved.seen || []);
    screenshotFolderInitial = new Set(saved.initial || []);
    const permission = await screenshotFolderHandle.queryPermission({ mode: "read" });
    setScreenshotDirectoryStatus(permission === "granted"
      ? `已连接“${screenshotFolderName}” · 自动监控新截图`
      : `已记住“${screenshotFolderName}”，点击上方按钮重新授权或选择文件夹。`);
  } catch {
    setScreenshotDirectoryStatus("无法恢复目录授权，请点击上方按钮重新选择截图文件夹。");
  }
}

async function chooseScreenshotFolder() {
  if (typeof window.showDirectoryPicker !== "function" || !window.isSecureContext) {
    elements.screenshotFolderInput.value = "";
    elements.screenshotFolderInput.click();
    return;
  }
  try {
    const handle = await window.showDirectoryPicker({ id: "eft-tarkov-screenshots", mode: "read" });
    const permission = await handle.requestPermission({ mode: "read" });
    if (permission !== "granted") throw new Error("浏览器未授予文件夹读取权限。");
    const files = await enumerateScreenshotFiles(handle);
    screenshotFolderHandle = handle;
    screenshotFolderOwnerId = String(state.player.id);
    screenshotFolderName = handle.name || "截图文件夹";
    screenshotFolderBaselineAt = Date.now();
    screenshotFolderSeen = new Set();
    screenshotFolderInitial = new Set(
      [...files]
        .sort((left, right) => right.file.lastModified - left.file.lastModified)
        .slice(0, SCREENSHOT_FOLDER_INITIAL_LIMIT)
        .map(screenshotFingerprint),
    );
    await writeScreenshotFolderRecord(state.player.id);
    setScreenshotDirectoryStatus(`已连接“${screenshotFolderName}” · 导入最近截图并自动监控新截图`);
    await scanScreenshotFolder();
  } catch (error) {
    if (error.name !== "AbortError") {
      setScreenshotDirectoryStatus(`无法连接截图文件夹：${error.message}`);
      toast(error.message);
    }
  }
}

async function importSelectedScreenshotFolder() {
  const selectedFiles = [...(elements.screenshotFolderInput.files || [])]
    .filter(isScreenshotFile)
    .map((file) => ({ file, path: file.webkitRelativePath || file.name }));
  if (!selectedFiles.length || !state?.player) return;
  const playerId = state.player.id;
  const storageKey = SCREENSHOT_FOLDER_STORAGE_PREFIX + playerId;
  let saved;
  try {
    saved = JSON.parse(safeStorageGet(storageKey) || "{}");
  } catch {
    saved = {};
  }
  const directoryName = selectedFiles[0].path.split("/")[0];
  if (saved.directoryName !== directoryName) {
    saved = {
      directoryName,
      baselineAt: Date.now(),
      seen: [],
      initial: [...selectedFiles]
        .sort((left, right) => right.file.lastModified - left.file.lastModified)
        .slice(0, SCREENSHOT_FOLDER_INITIAL_LIMIT)
        .map(screenshotFingerprint),
    };
  }
  screenshotFolderName = directoryName || "截图文件夹";
  const seen = new Set(saved.seen || []);
  const initial = new Set(saved.initial || []);
  setScreenshotDirectoryStatus(`正在扫描“${screenshotFolderName}”中的新截图…`);
  await processScreenshotEntries(selectedFiles, {
    playerId,
    baselineAt: Number(saved.baselineAt) || Date.now(),
    seen,
    initial,
  });
  saved.seen = [...seen].slice(-10000);
  saved.initial = [...initial];
  safeStorageSet(storageKey, JSON.stringify(saved));
}

async function initializeLocalApp() {
  await refreshState();
  await refreshLogs();
}

function toast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => elements.toast.classList.remove("show"), 2800);
}

function applyTheme(theme, persist = false) {
  const normalizedTheme = theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = normalizedTheme;
  const targetTheme = normalizedTheme === "dark" ? "light" : "dark";
  elements.themeToggleIcon.textContent = targetTheme === "light" ? "☼" : "☾";
  elements.themeToggleLabel.textContent = targetTheme === "light" ? "白天模式" : "黑夜模式";
  elements.themeToggle.setAttribute("aria-pressed", String(normalizedTheme === "dark"));
  elements.themeToggle.setAttribute("aria-label", `切换到${targetTheme === "light" ? "白天" : "黑夜"}模式`);
  elements.themeToggle.title = `切换到${targetTheme === "light" ? "白天" : "黑夜"}模式`;
  document.querySelector('meta[name="theme-color"]').content = normalizedTheme === "dark" ? "#000000" : "#f5f5f7";
  if (persist) safeStorageSet("eft-task-assistant-theme", normalizedTheme);
}

function initializeTheme() {
  const savedTheme = safeStorageGet("eft-task-assistant-theme");
  const systemTheme = window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
  applyTheme(savedTheme || systemTheme);
}

function setConnection(connected) {
  elements.connection.textContent = connected ? "本地服务已连接" : "本地服务连接中断";
  elements.connection.previousElementSibling.style.background = connected ? "#91c475" : "#db8070";
}

function renderProfiles(profiles, selectedId) {
  const currentValue = elements.profile.value;
  elements.profile.replaceChildren();
  for (const profile of profiles) {
    const option = document.createElement("option");
    option.value = String(profile.id);
    option.textContent = `${profile.name} · ${profile.mode_label}${profile.season_id ? ` · ${profile.season_id}` : ""}`;
    elements.profile.append(option);
  }
  const desired = String(selectedId ?? currentValue);
  if ([...elements.profile.options].some((option) => option.value === desired)) {
    elements.profile.value = desired;
  }
}

function openInitialProfileNameDialog() {
  if (!state?.profile_name_required || profileNameSetupOpen) return;
  profileNameSetupOpen = true;
  elements.profileDialog.dataset.initialName = "true";
  elements.profileDialogTitle.textContent = "给本地档案命名";
  elements.profileModeField.hidden = true;
  elements.seasonField.hidden = true;
  elements.cancelProfileButton.hidden = true;
  elements.profileForm.querySelector('button[type="submit"]').textContent = "开始使用";
  elements.profileForm.reset();
  elements.profileDialog.showModal();
  elements.profileForm.elements.name.focus();
}

function resetProfileDialog() {
  delete elements.profileDialog.dataset.initialName;
  profileNameSetupOpen = false;
  elements.profileDialogTitle.textContent = "新建游戏档案";
  elements.profileModeField.hidden = false;
  elements.seasonField.hidden = true;
  elements.cancelProfileButton.hidden = false;
  elements.profileForm.querySelector('button[type="submit"]').textContent = "创建档案";
}

function renderCaptureHistory(captures = []) {
  elements.captureHistory.replaceChildren();
  for (const capture of captures) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `capture-history-item${capture.selected ? " is-selected" : ""}`;
    button.dataset.captureId = capture.id;
    button.dataset.state = capture.state;
    button.setAttribute("aria-pressed", String(Boolean(capture.selected)));
    const time = document.createElement("span");
    time.className = "capture-history-time";
    const createdAt = new Date(capture.created_at);
    time.textContent = Number.isNaN(createdAt.getTime())
      ? capture.created_at
      : createdAt.toLocaleString();
    const status = document.createElement("span");
    status.className = "capture-history-status";
    status.textContent = capture.status;
    button.append(time, status);
    elements.captureHistory.append(button);
  }
}

function orderedTraders(traders) {
  const order = new Map((state?.trader_order || []).map((trader, index) => [trader.toLocaleLowerCase(), index]));
  return [...traders].sort((left, right) => {
    const leftRank = order.get(left.toLocaleLowerCase()) ?? Number.MAX_SAFE_INTEGER;
    const rightRank = order.get(right.toLocaleLowerCase()) ?? Number.MAX_SAFE_INTEGER;
    return leftRank - rightRank || left.localeCompare(right, "zh-CN");
  });
}

function orderedTasks(tasks) {
  const order = new Map((state?.trader_order || []).map((trader, index) => [trader.toLocaleLowerCase(), index]));
  return [...tasks].sort((left, right) => {
    const leftTrader = String(left.trader || "").trim();
    const rightTrader = String(right.trader || "").trim();
    const leftRank = order.get(leftTrader.toLocaleLowerCase()) ?? Number.MAX_SAFE_INTEGER;
    const rightRank = order.get(rightTrader.toLocaleLowerCase()) ?? Number.MAX_SAFE_INTEGER;
    return leftRank - rightRank
      || leftTrader.localeCompare(rightTrader, "zh-CN")
      || String(left.title || "").localeCompare(String(right.title || ""), "zh-CN");
  });
}

function updateTraderFilterOptions(tasks) {
  const activeTraders = new Set(tasks
    .filter((task) => task.state !== "complete")
    .map((task) => String(task.trader || "").trim())
    .filter(Boolean));
  const traders = orderedTraders(activeTraders);
  const expectedValues = ["", ...traders];
  const currentValues = [...elements.taskTraderFilter.options].map((option) => option.value);
  if (expectedValues.length !== currentValues.length || expectedValues.some((value, index) => value !== currentValues[index])) {
    const previous = elements.taskTraderFilter.value;
    elements.taskTraderFilter.replaceChildren();
    const allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = "全部商人";
    elements.taskTraderFilter.append(allOption);
    for (const trader of traders) {
      const option = document.createElement("option");
      option.value = trader;
      option.textContent = trader;
      elements.taskTraderFilter.append(option);
    }
    elements.taskTraderFilter.value = expectedValues.includes(previous) ? previous : "";
  }
}

function taskKeyIdentifiers(task) {
  return [...new Set((Array.isArray(task.key_requirements) ? task.key_requirements : [])
    .filter((key) => isKeyItem(key))
    .map((key) => String(key.item_id || key.id || key.name || "").trim().toLocaleLowerCase())
    .filter(Boolean))];
}

function taskHiddenByKey(task) {
  return taskKeyIdentifiers(task).some((keyId) => hiddenKeyIds.has(keyId));
}

function itemImageProxyUrl(imageUrl) {
  try {
    const url = new URL(imageUrl);
    if (url.protocol !== "https:" || !["assets.tarkov.dev", "www.eftarkov.com"].includes(url.hostname)) return "";
    return `https://images.weserv.nl/?url=${encodeURIComponent(url.host + url.pathname)}`;
  } catch {
    return "";
  }
}

function setItemImageSources(image, fallback, imageUrls) {
  const sources = [...new Set(imageUrls.filter(Boolean))];
  let nextSourceIndex = 0;
  image.referrerPolicy = "no-referrer";
  fallback.hidden = false;
  image.hidden = false;
  image.onload = () => {
    image.hidden = false;
    fallback.hidden = true;
  };
  image.onerror = () => {
    if (nextSourceIndex < sources.length) {
      image.src = sources[nextSourceIndex++];
      return;
    }
    image.hidden = true;
    fallback.hidden = false;
  };
  image.removeAttribute("src");
  if (sources.length) image.src = sources[nextSourceIndex++];
  else image.hidden = true;
}

function renderKeySummary(tasks) {
  const keysById = new Map();
  taskKeyIdsByTask = new Map();
  for (const task of tasks) {
    const taskId = String(task.id);
    const taskKeys = new Set();
    for (const key of Array.isArray(task.key_requirements) ? task.key_requirements : []) {
      if (!isKeyItem(key)) continue;
      const itemId = String(key.item_id || key.id || "").trim().toLocaleLowerCase();
      const id = String(key.item_id || key.id || key.name || "").trim().toLocaleLowerCase();
      if (!id) continue;
      taskKeys.add(id);
      const requestedCount = Number(key.count || key.quantity || 1);
      const keyCount = Math.max(1, Number.isFinite(requestedCount) ? requestedCount : 1);
      if (!keysById.has(id)) {
        keysById.set(id, {
          id,
          name: String(key.name || "未命名钥匙").trim(),
          sourceUrl: /^[0-9a-f]{24}$/i.test(itemId)
            ? `https://www.eftarkov.com/item/${itemId}`
            : "",
          imageUrl: String(key.image_url || (/^[0-9a-f]{24}$/i.test(itemId)
            ? `https://assets.tarkov.dev/${itemId}-icon.webp`
            : "")),
          count: keyCount,
          tasks: new Map(),
        });
      }
      const entry = keysById.get(id);
      entry.count = Math.max(entry.count, keyCount);
      entry.tasks.set(taskId, task.title);
    }
    taskKeyIdsByTask.set(taskId, taskKeys);
  }

  const keys = [...keysById.values()].sort((left, right) => left.name.localeCompare(right.name, "zh-CN"));
  if (keys.length && uiPreferences) {
    const currentKeyIds = keys.map((key) => key.id);
    const knownKeyIds = new Set(uiPreferences.keyFilterKnownIds);
    const newKeyIds = new Set(uiPreferences.newKeyIds);
    const pendingOwnershipIds = new Set(uiPreferences.keyOwnershipPendingIds);
    let preferencesChanged = false;
    if (!uiPreferences.keyFilterInitialized) {
      currentKeyIds.forEach((keyId) => {
        hiddenKeyIds.add(keyId);
        if (!Object.prototype.hasOwnProperty.call(uiPreferences.keyOwnershipAnswers, keyId)) {
          pendingOwnershipIds.add(keyId);
        }
      });
      uiPreferences.keyFilterInitialized = true;
      preferencesChanged = true;
    } else {
      currentKeyIds.forEach((keyId) => {
        if (knownKeyIds.has(keyId)) return;
        hiddenKeyIds.add(keyId);
        newKeyIds.add(keyId);
        pendingOwnershipIds.add(keyId);
        preferencesChanged = true;
      });
    }
    const updatedKnownKeyIds = [...new Set([...knownKeyIds, ...currentKeyIds])].slice(-300);
    if (updatedKnownKeyIds.length !== uiPreferences.keyFilterKnownIds.length) preferencesChanged = true;
    uiPreferences.keyFilterKnownIds = updatedKnownKeyIds;
    const updatedNewKeyIds = [...newKeyIds].slice(-300);
    if (updatedNewKeyIds.length !== uiPreferences.newKeyIds.length) preferencesChanged = true;
    uiPreferences.newKeyIds = updatedNewKeyIds;
    const updatedPendingOwnershipIds = [...pendingOwnershipIds].slice(-300);
    if (updatedPendingOwnershipIds.length !== uiPreferences.keyOwnershipPendingIds.length) preferencesChanged = true;
    uiPreferences.keyOwnershipPendingIds = updatedPendingOwnershipIds;
    if (preferencesChanged) saveUiPreferences();
  }
  keySummaryEntries = keys;
  const totalCount = keys.reduce((total, key) => total + key.count, 0);
  const keyHiddenTaskCount = tasks.filter(taskHiddenByKey).length;
  const renderSignature = JSON.stringify({
    language: currentLanguage,
    keys: keys.map((key) => [
      key.id,
      key.name,
      key.imageUrl,
      key.sourceUrl,
      key.count,
      [...key.tasks],
      hiddenKeyIds.has(key.id),
      uiPreferences?.keyOwnershipAnswers?.[key.id] ?? null,
      uiPreferences?.newKeyIds.includes(key.id) || false,
    ]),
    keyHiddenTaskCount,
    pendingOwnershipIds: uiPreferences?.keyOwnershipPendingIds || [],
  });
  if (renderSignature === keySummaryRenderSignature) {
    showNextKeyOwnershipPrompt();
    return;
  }
  keySummaryRenderSignature = renderSignature;
  elements.keySummaryCount.textContent = keys.length + " 种";
  elements.keySummaryNote.textContent = keys.length
    ? "共需准备至少 " + totalCount + " 把钥匙；同一把钥匙用于多个任务时只计一次。未勾选钥匙会隐藏关联任务和地图点位；当前钥匙筛选隐藏 " + keyHiddenTaskCount + " 个任务。"
    : "当前进行中的任务没有已识别的钥匙需求。钥匙资料在导入任务详情后汇总。";
  elements.keySummaryRows.replaceChildren();
  if (!keys.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state planning-empty";
    empty.textContent = "任务加入清单后，识别到的钥匙会汇总在这里。";
    elements.keySummaryRows.append(empty);
    return;
  }

  for (const key of keys) {
    const row = document.createElement("div");
    const hidden = hiddenKeyIds.has(key.id);
    row.className = "key-summary-row" + (hidden ? " is-filtered" : "");
    const taskNames = [...key.tasks.values()];
    row.title = "需要此钥匙的任务：" + taskNames.join("、");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.dataset.keyId = key.id;
    checkbox.checked = !hidden;
    checkbox.setAttribute("aria-label", "显示需要" + key.name + "的任务");
    checkbox.title = row.title;
    const icon = document.createElement("img");
    icon.className = "key-summary-icon";
    icon.alt = "";
    icon.loading = "lazy";
    icon.decoding = "async";
    const iconFallback = document.createElement("span");
    iconFallback.className = "key-summary-icon-fallback";
    iconFallback.textContent = "🔑";
    setItemImageSources(icon, iconFallback, [key.imageUrl, itemImageProxyUrl(key.imageUrl)]);
    const imageLink = document.createElement(key.sourceUrl ? "a" : "span");
    imageLink.className = "key-summary-image-link";
    if (key.sourceUrl) {
      imageLink.href = key.sourceUrl;
      imageLink.target = "_blank";
      imageLink.rel = "noopener noreferrer";
      imageLink.setAttribute("aria-label", `在 EFTarkov 查看${key.name}`);
      imageLink.title = `在 EFTarkov 查看${key.name}`;
    }
    imageLink.append(icon, iconFallback);
    const name = document.createElement("strong");
    name.className = "key-summary-name";
    name.textContent = key.name;
    const ownership = document.createElement("span");
    ownership.className = "key-summary-ownership";
    const ownershipAnswer = uiPreferences?.keyOwnershipAnswers?.[key.id];
    ownership.textContent = ownershipAnswer === true
      ? "已有"
      : ownershipAnswer === false ? "待准备" : "未确认";
    if (ownershipAnswer === true) ownership.classList.add("is-owned");
    if (ownershipAnswer === false) ownership.classList.add("is-needed");
    if (uiPreferences?.newKeyIds.includes(key.id)) {
      const newBadge = document.createElement("button");
      newBadge.type = "button";
      newBadge.className = "key-summary-new";
      newBadge.dataset.dismissNewKey = key.id;
      newBadge.textContent = "NEW";
      newBadge.title = "点击标记为已查看";
      newBadge.setAttribute("aria-label", `将${key.name}标记为已查看`);
      row.append(newBadge);
    }
    const quantity = document.createElement("span");
    quantity.className = "key-summary-quantity";
    quantity.textContent = "×" + key.count;
    row.dataset.keyId = key.id;
    row.append(checkbox, imageLink, name, ownership, quantity);
    row.addEventListener("click", (event) => {
      if (event.target.closest("button, input, a")) return;
      checkbox.click();
    });
    elements.keySummaryRows.append(row);
  }
  showNextKeyOwnershipPrompt();
}

function showNextKeyOwnershipPrompt() {
  if (!uiPreferences || elements.keyOwnershipDialog.open || !keySummaryEntries.length) return;
  const key = uiPreferences.keyOwnershipPendingIds
    .filter((keyId) => !deferredKeyOwnershipIds.has(keyId))
    .map((keyId) => keySummaryEntries.find((entry) => entry.id === keyId))
    .find(Boolean);
  if (!key) return;
  activeKeyOwnershipId = key.id;
  elements.keyOwnershipName.textContent = key.name;
  const taskNames = [...key.tasks.values()];
  const displayedTaskNames = taskNames.slice(0, 3).join("、");
  const remainingTaskCount = taskNames.length - 3;
  const taskSummary = remainingTaskCount > 0
    ? `${displayedTaskNames} 等 ${taskNames.length} 个任务`
    : displayedTaskNames || "当前任务";
  elements.keyOwnershipQuestion.textContent = `「${taskSummary}」需要这把钥匙。你现在有吗？`;
  const imageUrl = key.imageUrl || "";
  setItemImageSources(
    elements.keyOwnershipImage,
    elements.keyOwnershipImageFallback,
    [imageUrl, itemImageProxyUrl(imageUrl)],
  );
  elements.keyOwnershipDialog.showModal();
}

function answerKeyOwnership(hasKey) {
  if (!uiPreferences || !activeKeyOwnershipId) return;
  const before = captureUiUndoSnapshot();
  const keyId = activeKeyOwnershipId;
  uiPreferences.keyOwnershipAnswers[keyId] = hasKey;
  if (hasKey) hiddenKeyIds.delete(keyId);
  uiPreferences.keyOwnershipPendingIds = uiPreferences.keyOwnershipPendingIds
    .filter((pendingId) => pendingId !== keyId);
  activeKeyOwnershipId = "";
  const row = [...elements.keySummaryRows.querySelectorAll(".key-summary-row")]
    .find((entry) => entry.dataset.keyId === keyId);
  const ownership = row?.querySelector(".key-summary-ownership");
  if (ownership) {
    ownership.textContent = hasKey ? "已有" : "待准备";
    ownership.classList.toggle("is-owned", hasKey);
    ownership.classList.toggle("is-needed", !hasKey);
  }
  const keyName = keySummaryEntries.find((entry) => entry.id === keyId)?.name || "钥匙";
  recordUiOperation("钥匙状态：" + keyName + " · " + (hasKey ? "标记为已有" : "标记为待准备"), before);
  saveUiPreferences();
  elements.keyOwnershipDialog.close();
  if (hasKey && state) {
    renderTasks(state.tasks);
    renderMapTargets(mapView?.markers || [], mapView?.tasks || []);
  }
}

function deferKeyOwnershipQuestion() {
  if (activeKeyOwnershipId) deferredKeyOwnershipIds.add(activeKeyOwnershipId);
  activeKeyOwnershipId = "";
  elements.keyOwnershipDialog.close();
}

function updateTaskMapFilterOptions(tasks) {
  for (const option of elements.taskMapFilter.options) {
    if (!option.value) continue;
    const mapName = option.dataset.mapName || option.textContent.split(" · ")[0];
    option.dataset.mapName = mapName;
    const taskIds = mapTaskIdsByMap.get(option.value) || new Set();
    const mapTasks = tasks.filter((task) => taskIds.has(String(task.id)));
    const visibleCount = mapTasks.filter((task) => (
      showHiddenTasks || (!hiddenTaskIds.has(String(task.id)) && !taskHiddenByKey(task))
    )).length;
    option.textContent = mapName + " · " + visibleCount + "/" + mapTasks.length + " 个任务";
  }
}

function hideoutPlanFor(station) {
  if (!uiPreferences) return { enabled: false, currentLevel: 0, targetLevel: 1 };
  const plan = uiPreferences.hideoutPlan[station.id];
  return plan && typeof plan === "object"
    ? plan
    : { enabled: false, currentLevel: 0, targetLevel: 1 };
}

function updateHideoutPlan(stationId, update) {
  if (!uiPreferences) return;
  const before = captureUiUndoSnapshot();
  const station = hideoutCatalog?.stations?.find((item) => String(item.id) === String(stationId));
  const current = uiPreferences.hideoutPlan[stationId] || {
    enabled: false,
    currentLevel: 0,
    targetLevel: 1,
  };
  const next = { ...current, ...update };
  uiPreferences.hideoutPlan[stationId] = next;
  const changes = [];
  if (Object.prototype.hasOwnProperty.call(update, "enabled")) {
    changes.push(next.enabled ? "加入升级备料" : "从升级备料移除");
  }
  const levelLabel = (level) => Number(level) === 0 ? "未建造" : "等级 " + level;
  if (Object.prototype.hasOwnProperty.call(update, "currentLevel")) {
    changes.push("当前等级 " + levelLabel(current.currentLevel) + " → " + levelLabel(next.currentLevel));
  }
  if (Object.prototype.hasOwnProperty.call(update, "targetLevel")) {
    changes.push("目标等级 " + levelLabel(current.targetLevel) + " → " + levelLabel(next.targetLevel));
  }
  const stationName = station?.name || "藏身处设施";
  recordUiOperation("调整藏身处计划：" + stationName + (changes.length ? " · " + changes.join("；") : ""), before);
  saveUiPreferences();
  renderHideoutPlanner();
}

function normalizedHideoutPlan(station) {
  const levels = [...(station.levels || [])].map((entry) => Number(entry.level)).filter(Number.isFinite);
  const stored = hideoutPlanFor(station);
  const currentLevel = levels.includes(Number(stored.currentLevel)) ? Number(stored.currentLevel) : 0;
  const upgradeLevels = levels.filter((level) => level > currentLevel).sort((left, right) => left - right);
  const targetLevels = [...new Set([currentLevel, ...upgradeLevels])].sort((left, right) => left - right);
  const targetLevel = targetLevels.includes(Number(stored.targetLevel))
    ? Number(stored.targetLevel)
    : upgradeLevels[0] ?? currentLevel;
  return {
    enabled: Boolean(stored.enabled) && upgradeLevels.length > 0,
    currentLevel,
    targetLevel,
    fullyUpgraded: !upgradeLevels.length,
  };
}

function buildHideoutDependencyPlan() {
  const stations = hideoutCatalog?.stations || [];
  const stationsById = new Map(stations.map((station) => [String(station.id), station]));
  const plans = new Map();
  const manuallySelected = new Set();
  const prerequisiteNotes = new Map();
  const automaticReasons = new Map();
  const pending = [];

  for (const station of stations) {
    const plan = normalizedHideoutPlan(station);
    if (!plan.enabled) continue;
    plans.set(String(station.id), plan);
    manuallySelected.add(String(station.id));
    pending.push(String(station.id));
  }

  const processedTargets = new Map();
  while (pending.length) {
    const stationId = pending.shift();
    const station = stationsById.get(stationId);
    const plan = plans.get(stationId);
    if (!station || !plan || (processedTargets.get(stationId) || 0) >= plan.targetLevel) continue;
    processedTargets.set(stationId, plan.targetLevel);

    for (const level of station.levels || []) {
      const levelNumber = Number(level.level);
      if (levelNumber <= plan.currentLevel || levelNumber > plan.targetLevel) continue;
      for (const requirement of level.station_requirements || []) {
        const requiredStationId = String(requirement.station_id || "");
        const requiredLevel = Number(requirement.level);
        if (!requiredStationId || requiredStationId === stationId || !Number.isFinite(requiredLevel) || requiredLevel < 1) continue;
        const requiredStation = stationsById.get(requiredStationId);
        if (!requiredStation) continue;
        const requiredPlan = normalizedHideoutPlan(requiredStation);
        let notes = prerequisiteNotes.get(stationId);
        if (!notes) {
          notes = new Map();
          prerequisiteNotes.set(stationId, notes);
        }
        const previousNote = notes.get(requiredStationId);
        if (!previousNote || requiredLevel > previousNote.level) {
          notes.set(requiredStationId, {
            id: requiredStationId,
            name: requiredStation.name,
            level: requiredLevel,
          });
        }
        if (requiredLevel <= requiredPlan.currentLevel) continue;

        const currentPlan = plans.get(requiredStationId);
        const currentLevel = currentPlan?.currentLevel ?? requiredPlan.currentLevel;
        const desiredTarget = Math.max(requiredLevel, currentPlan?.targetLevel || requiredLevel);
        const availableTargets = (requiredStation.levels || [])
          .map((entry) => Number(entry.level))
          .filter((availableLevel) => availableLevel > currentLevel)
          .sort((left, right) => left - right);
        const targetLevel = availableTargets.find((availableLevel) => availableLevel >= desiredTarget)
          || availableTargets.at(-1);
        if (!targetLevel) continue;
        if (!currentPlan || targetLevel > currentPlan.targetLevel) {
          plans.set(requiredStationId, { enabled: true, currentLevel, targetLevel, fullyUpgraded: false });
          pending.push(requiredStationId);
        }
        if (!manuallySelected.has(requiredStationId)) {
          let reasons = automaticReasons.get(requiredStationId);
          if (!reasons) {
            reasons = new Set();
            automaticReasons.set(requiredStationId, reasons);
          }
          reasons.add(`${station.name} ${levelNumber}级`);
        }
      }
    }
  }

  return { plans, manuallySelected, prerequisiteNotes, automaticReasons };
}

function renderHideoutPlanner() {
  if (!hideoutCatalog) return;
  elements.hideoutStations.replaceChildren();
  const materials = new Map();
  let selectedStationCount = 0;
  const dependencyPlan = buildHideoutDependencyPlan();

  for (const station of hideoutCatalog.stations || []) {
    const levels = [...(station.levels || [])].sort((left, right) => left.level - right.level);
    if (!levels.length) continue;
    const availableLevels = levels.map((entry) => Number(entry.level)).filter(Number.isFinite);
    const maxLevel = Math.max(...availableLevels);
    const stationId = String(station.id);
    const userPlan = normalizedHideoutPlan(station);
    const plan = dependencyPlan.plans.get(stationId) || { ...userPlan, enabled: false };
    const currentLevel = plan.currentLevel;
    const upgradeLevels = availableLevels.filter((level) => level > currentLevel);
    const targetLevels = [...new Set([currentLevel, ...upgradeLevels])].sort((left, right) => left - right);
    const targetLevel = targetLevels.includes(Number(plan.targetLevel))
      ? Number(plan.targetLevel)
      : upgradeLevels[0] ?? currentLevel;
    const fullyUpgraded = !upgradeLevels.length;
    const automaticReasons = dependencyPlan.automaticReasons.get(stationId);
    const automaticOnly = Boolean(automaticReasons?.size) && !dependencyPlan.manuallySelected.has(stationId);
    const card = document.createElement("article");
    card.className = "hideout-station-card" + (plan.enabled && !fullyUpgraded ? " is-selected" : "");
    const header = document.createElement("label");
    header.className = "hideout-station-heading";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = Boolean(plan.enabled) && !fullyUpgraded;
    checkbox.disabled = fullyUpgraded || automaticOnly;
    if (automaticOnly) checkbox.title = "由前置设施自动勾选；取消依赖此设施的升级后会自动解除。";
    checkbox.dataset.stationId = station.id;
    const name = document.createElement("strong");
    name.textContent = station.name;
    const max = document.createElement("span");
    max.className = "hideout-station-max";
    max.textContent = fullyUpgraded ? "最高等级 " + maxLevel : "最高 " + maxLevel + " 级";
    header.append(checkbox, name, max);
    card.append(header);

    const notes = [];
    if (automaticOnly) notes.push("自动前置：" + [...automaticReasons].join("、"));
    const stationPrerequisites = dependencyPlan.prerequisiteNotes.get(stationId);
    if (stationPrerequisites?.size) {
      const prerequisiteText = [...stationPrerequisites.values()].map((requirement) => {
        const prerequisiteStation = hideoutCatalog.stations.find((entry) => String(entry.id) === requirement.id);
        const prerequisitePlan = dependencyPlan.plans.get(requirement.id);
        const prerequisiteCurrent = prerequisiteStation ? normalizedHideoutPlan(prerequisiteStation).currentLevel : 0;
        const status = prerequisiteCurrent >= requirement.level
          ? "已满足"
          : prerequisitePlan?.targetLevel >= requirement.level
            ? "已列入计划"
            : "未满足";
        return `${requirement.name} ${requirement.level}级（${status}）`;
      });
      notes.push("升级前置：" + prerequisiteText.join("、"));
    }
    if (notes.length) {
      const note = document.createElement("small");
      note.className = "hideout-station-note";
      note.textContent = notes.join(" · ");
      card.append(note);
    }

    const levelsRow = document.createElement("div");
    levelsRow.className = "hideout-level-selectors";
    const currentLabel = document.createElement("label");
    currentLabel.textContent = "当前等级";
    const currentSelect = document.createElement("select");
    currentSelect.dataset.stationId = station.id;
    currentSelect.dataset.levelKind = "current";
    currentSelect.disabled = fullyUpgraded || !plan.enabled;
    for (const level of [...new Set([0, ...availableLevels])]) {
      currentSelect.add(new Option(level === 0 ? "未建造" : "等级 " + level, String(level)));
    }
    currentSelect.value = String(currentLevel);
    currentLabel.append(currentSelect);

    const targetLabel = document.createElement("label");
    targetLabel.textContent = "目标等级";
    const targetSelect = document.createElement("select");
    targetSelect.dataset.stationId = station.id;
    targetSelect.dataset.levelKind = "target";
    targetSelect.disabled = fullyUpgraded || !plan.enabled;
    for (const level of targetLevels) {
      targetSelect.add(new Option(level === 0 ? "未建造" : "等级 " + level, String(level)));
    }
    targetSelect.value = String(targetLevel);
    targetLabel.append(targetSelect);
    levelsRow.append(currentLabel, targetLabel);
    card.append(levelsRow);
    elements.hideoutStations.append(card);

    if (!plan.enabled || fullyUpgraded) continue;
    selectedStationCount += 1;
    for (const level of levels) {
      if (level.level <= currentLevel || level.level > targetLevel) continue;
      for (const cost of level.items || []) {
        const key = String(cost.item_id || cost.name);
        if (!materials.has(key)) {
          const itemId = String(cost.item_id || "").toLocaleLowerCase();
          const currency = hideoutCurrencyType(cost);
          materials.set(key, {
            key,
            name: cost.name,
            currency,
            imageUrl: /^[a-f0-9]{24}$/i.test(itemId)
              ? `https://assets.tarkov.dev/${itemId}-icon.webp`
              : "",
            count: 0,
            foundInRaidCount: 0,
            uses: new Set(),
          });
        }
        const item = materials.get(key);
        const count = Math.max(0, Number(cost.count) || 0);
        item.count += count;
        if (cost.found_in_raid) item.foundInRaidCount += count;
        item.uses.add(station.name + " " + level.level + "级");
      }
    }
  }

  const materialRows = [...materials.values()].sort((left, right) => (
    Number(right.foundInRaidCount > 0) - Number(left.foundInRaidCount > 0)
    || left.name.localeCompare(right.name, "zh-CN")
  ));
  elements.hideoutMaterials.replaceChildren();
  if (!materialRows.length) {
    const empty = document.createElement("li");
    empty.className = "hideout-material-empty";
    empty.textContent = selectedStationCount
      ? "所选升级没有额外物品需求。"
      : "勾选准备升级的设施，并选择当前等级和目标等级。";
    elements.hideoutMaterials.append(empty);
    updateHideoutMaterialSummary();
    return;
  }
  for (const material of materialRows) {
    const row = document.createElement("li");
    row.className = "hideout-material-card";
    row.dataset.materialKey = material.key;
    row.dataset.requiredCount = String(material.count);
    row.dataset.currency = material.currency;
    const imageWrap = document.createElement("div");
    imageWrap.className = "hideout-material-image-wrap";
    const image = document.createElement("img");
    image.className = "hideout-material-image";
    image.alt = "";
    image.loading = "lazy";
    image.decoding = "async";
    const imageFallback = document.createElement("span");
    imageFallback.className = "hideout-material-image-fallback";
    imageFallback.textContent = "📦";
    setItemImageSources(image, imageFallback, [material.imageUrl, itemImageProxyUrl(material.imageUrl)]);
    imageWrap.append(image, imageFallback);
    const name = document.createElement("strong");
    name.className = "hideout-material-name";
    name.textContent = material.name;
    const requiredCount = document.createElement("span");
    requiredCount.className = "hideout-material-required";
    const currencySymbols = { rubles: "₽", euros: "€", dollars: "$" };
    const unit = currencySymbols[material.currency] || "件";
    requiredCount.textContent = material.currency
      ? "需求 " + unit + material.count.toLocaleString("zh-CN")
      : "需求 " + material.count.toLocaleString("zh-CN") + " 件";
    const details = document.createElement("small");
    details.className = "hideout-material-details";
    details.textContent = [...material.uses].join("、");
    const firRequirement = document.createElement("span");
    firRequirement.className = "hideout-material-fir";
    firRequirement.hidden = material.foundInRaidCount <= 0;
    if (material.foundInRaidCount > 0) {
      firRequirement.classList.add("is-required");
      firRequirement.textContent = "需战局内获得 "
        + material.foundInRaidCount.toLocaleString("zh-CN") + " 件";
      firRequirement.title = firRequirement.textContent;
    }
    const counter = document.createElement("div");
    counter.className = "hideout-material-counter";
    const ownedLabel = document.createElement("label");
    ownedLabel.textContent = "已有";
    const ownedInput = document.createElement("input");
    ownedInput.type = "number";
    ownedInput.min = "0";
    ownedInput.max = "1000000";
    ownedInput.step = "1";
    ownedInput.inputMode = "numeric";
    ownedInput.value = String(uiPreferences?.hideoutOwnedMaterials?.[material.key] || 0);
    ownedInput.dataset.materialKey = material.key;
    ownedInput.setAttribute("aria-label", material.name + " 已有数量");
    ownedLabel.append(ownedInput, document.createTextNode(" " + unit));
    const remaining = document.createElement("span");
    remaining.className = "hideout-material-remaining";
    remaining.dataset.materialRemaining = "";
    counter.append(ownedLabel, remaining);
    row.append(imageWrap, name, requiredCount, firRequirement, counter, details);
    elements.hideoutMaterials.append(row);
  }
  updateHideoutMaterialSummary();
}

function setHideoutSectionsOpen(isOpen, persist = true) {
  const open = Boolean(isOpen);
  elements.hideoutPlannerContent.hidden = !open;
  elements.hideoutPlannerToggle.textContent = open ? "收起" : "展开";
  elements.hideoutPlannerToggle.setAttribute("aria-expanded", String(open));
  elements.hideoutMaterialsPanel.open = open;
  if (uiPreferences) {
    uiPreferences.hideoutPlannerOpen = open;
    uiPreferences.hideoutMaterialsOpen = open;
  }
  if (persist) saveUiPreferences();
  syncHideoutMaterialsLayout();
}

function syncHideoutMaterialsLayout() {
  const shouldMatchPlanner = window.matchMedia("(min-width: 851px)").matches
    && !elements.hideoutPlannerContent.hidden;
  if (!shouldMatchPlanner) {
    elements.hideoutMaterialsCard.style.height = "";
    elements.hideoutMaterialsCard.classList.remove("is-height-synced");
    return;
  }
  const plannerHeight = elements.hideoutPlannerPanel.getBoundingClientRect().height;
  if (!plannerHeight) return;
  elements.hideoutMaterialsCard.style.height = `${plannerHeight}px`;
  elements.hideoutMaterialsCard.classList.add("is-height-synced");
}

function updateHideoutMaterialSummary() {
  let requiredTotal = 0;
  let ownedTotal = 0;
  let remainingTotal = 0;
  let materialCount = 0;
  const currencyTotals = new Map();
  for (const row of elements.hideoutMaterials.querySelectorAll("li[data-material-key]")) {
    const required = Math.max(0, Number(row.dataset.requiredCount) || 0);
    const input = row.querySelector("input[data-material-key]");
    const owned = Math.min(1000000, Math.max(0, Math.floor(Number(input?.value) || 0)));
    const remaining = Math.max(0, required - owned);
    const remainingLabel = row.querySelector("[data-material-remaining]");
    const currency = row.dataset.currency;
    const currencySymbols = { rubles: "₽", euros: "€", dollars: "$" };
    if (remainingLabel) {
      remainingLabel.textContent = currency
        ? "尚缺 " + currencySymbols[currency] + remaining.toLocaleString("zh-CN")
        : "尚缺 " + remaining.toLocaleString("zh-CN") + " 件";
    }
    if (currency) {
      if (!currencyTotals.has(currency)) {
        currencyTotals.set(currency, { required: 0, owned: 0, remaining: 0 });
      }
      const totals = currencyTotals.get(currency);
      totals.required += required;
      totals.owned += owned;
      totals.remaining += remaining;
      continue;
    }
    requiredTotal += required;
    ownedTotal += owned;
    remainingTotal += remaining;
    materialCount += 1;
  }
  const currencyLabels = { rubles: "卢布", euros: "欧元", dollars: "美元" };
  const currencySummary = [...currencyTotals.entries()].map(([currency, totals]) => (
    currencyLabels[currency] + "：需求 " + currencySymbolsFor(currency) + totals.required.toLocaleString("zh-CN")
      + " · 已有 " + currencySymbolsFor(currency) + totals.owned.toLocaleString("zh-CN")
      + " · 尚缺 " + currencySymbolsFor(currency) + totals.remaining.toLocaleString("zh-CN")
  )).join(" · ");
  elements.hideoutMaterialsCount.textContent = "需求 " + requiredTotal.toLocaleString("zh-CN")
    + " 件 · 已有 " + ownedTotal.toLocaleString("zh-CN") + " 件 · 尚缺 "
    + remainingTotal.toLocaleString("zh-CN") + " 件 · " + materialCount.toLocaleString("zh-CN") + " 种"
    + (currencySummary ? " · " + currencySummary : "");
}

function currencySymbolsFor(currency) {
  return { rubles: "₽", euros: "€", dollars: "$" }[currency] || "";
}

function hideoutCurrencyType(cost) {
  const name = String(cost.name || "").toLocaleLowerCase();
  const itemId = String(cost.item_id || "").toLocaleLowerCase();
  if (/卢布|rubles?|roubles?|₽/iu.test(name) || itemId === "5449016a4bdc2d6f028b456f") return "rubles";
  if (/欧元|euros?|€/iu.test(name) || itemId === "569668774bdc2da2298b4568") return "euros";
  if (/美元|dollars?|usd|\$/iu.test(name) || itemId === "5696686a4bdc2da3298b456a") return "dollars";
  return "";
}

async function loadHideoutCatalog(forceRefresh = false) {
  if (hideoutLoading) return hideoutLoading;
  if (hideoutCatalog && !forceRefresh) return;
  elements.hideoutRefreshButton.disabled = true;
  elements.hideoutStatus.textContent = "正在读取 Tarkov.dev 的 PvE 藏身处和简中物品资料…";
  const query = forceRefresh ? "?refresh=1" : "";
  hideoutLoading = request("/api/hideout" + query)
    .then((result) => {
      hideoutCatalog = result;
      const fetchedAt = result.fetched_at ? new Date(result.fetched_at) : null;
      const timeLabel = fetchedAt && !Number.isNaN(fetchedAt.getTime())
        ? fetchedAt.toLocaleString()
        : "时间未知";
      elements.hideoutStatus.textContent = (result.cache_status === "stale" ? "离线缓存" : "PvE 数据")
        + " · " + (result.stations?.length || 0) + " 个设施 · 更新于 " + timeLabel
        + " · 来源 Tarkov.dev" + (result.warning ? " · " + result.warning : "");
      renderHideoutPlanner();
      renderOperationHistory();
    })
    .catch((error) => {
      elements.hideoutStatus.textContent = "藏身处资料读取失败：" + error.message;
    })
    .finally(() => {
      hideoutLoading = null;
      elements.hideoutRefreshButton.disabled = false;
    });
  return hideoutLoading;
}

function renderTasks(tasks) {
  const activeTasks = orderedTasks(tasks.filter((task) => task.state !== "complete"));
  updateTraderFilterOptions(activeTasks);
  renderKeySummary(activeTasks);
  updateTaskMapFilterOptions(activeTasks);
  if (uiPreferences && uiPreferenceScopeId === `${String(state?.player?.id || "local")}:${String(state?.selected_profile_id)}`) {
    const traderPreferenceExists = [...elements.taskTraderFilter.options]
      .some((option) => option.value === uiPreferences.taskTraderFilter);
    if (traderPreferenceExists) elements.taskTraderFilter.value = uiPreferences.taskTraderFilter;
  }
  const hiddenTaskCount = activeTasks.filter((task) => (
    hiddenTaskIds.has(String(task.id)) || taskHiddenByKey(task)
  )).length;
  elements.showHiddenTasksButton.textContent = showHiddenTasks ? "收起隐藏" : `切换隐藏 ${hiddenTaskCount}`;
  elements.showHiddenTasksButton.disabled = hiddenTaskCount === 0 && !showHiddenTasks;
  elements.showHiddenTasksButton.title = "切换显示被钥匙筛选隐藏或手动隐藏的任务";
  elements.showHiddenTasksButton.setAttribute("aria-label", showHiddenTasks ? "收起隐藏任务" : "切换显示隐藏任务");
  elements.showHiddenTasksButton.setAttribute("aria-pressed", String(showHiddenTasks));
  const selectedTrader = elements.taskTraderFilter.value;
  const selectedMap = elements.taskMapFilter.value;
  const mapTaskIds = selectedMap ? mapTaskIdsByMap.get(selectedMap) || new Set() : null;
  const filteredTasks = activeTasks.filter((task) => (
    (!selectedTrader || task.trader === selectedTrader)
    && (!mapTaskIds || mapTaskIds.has(String(task.id)))
  ));
  const keyHiddenFilteredTaskCount = filteredTasks.filter(taskHiddenByKey).length;
  const manuallyHiddenFilteredTaskCount = filteredTasks.filter((task) => (
    !taskHiddenByKey(task) && hiddenTaskIds.has(String(task.id))
  )).length;
  const visibleTasks = filteredTasks.filter((task) => (
    showHiddenTasks || (!hiddenTaskIds.has(String(task.id)) && !taskHiddenByKey(task))
  ));
  const tasksToRender = showHiddenTasks
    ? [
      ...visibleTasks.filter((task) => !hiddenTaskIds.has(String(task.id)) && !taskHiddenByKey(task)),
      ...visibleTasks.filter((task) => hiddenTaskIds.has(String(task.id)) || taskHiddenByKey(task)),
    ]
    : visibleTasks;
  elements.rows.replaceChildren();
  elements.clearTasks.disabled = tasks.length === 0 || clearTasksBusy;
  elements.taskCount.textContent = selectedTrader || selectedMap
    ? `${visibleTasks.length}/${filteredTasks.length}`
    : String(visibleTasks.length);
  elements.emptyTasks.hidden = visibleTasks.length > 0;
  elements.emptyTasks.textContent = activeTasks.length
    ? visibleTasks.length === 0 && (keyHiddenFilteredTaskCount || (!showHiddenTasks && manuallyHiddenFilteredTaskCount))
      ? [
        keyHiddenFilteredTaskCount ? `钥匙筛选隐藏 ${keyHiddenFilteredTaskCount} 个任务` : "",
        !showHiddenTasks && manuallyHiddenFilteredTaskCount ? `手动隐藏 ${manuallyHiddenFilteredTaskCount} 个任务` : "",
      ].filter(Boolean).join("；") + "。点击“切换隐藏”可查看。"
      : "没有符合当前筛选条件的任务。试试切换到全部商人或全部地图。"
    : "当前档案还没有进行中的任务。可以手动添加、从资料库导入，或在截图识别后核对候选。";
  for (const task of tasksToRender) {
    const taskId = String(task.id);
    const manuallyHidden = hiddenTaskIds.has(taskId);
    const taskHidden = manuallyHidden || taskHiddenByKey(task);
    const requirements = Array.isArray(task.requirements) ? task.requirements : [];
    const isMp133Gunsmith = isMp133GunsmithTask(task);
    const completedCount = requirements.length
      ? requirements.filter((requirement) => !requirement.optional && requirement.completed).length
      : Number(task.current_count || 0);
    const requiredCount = requirements.length
      ? requirements.filter((requirement) => !requirement.optional).length
      : task.required_count;
    const card = document.createElement("article");
    card.className = `task-card${task.state === "complete" ? " is-complete" : ""}${isMp133Gunsmith ? " task-card-gunsmith" : ""}${taskHidden ? " is-hidden" : ""}`;
    const detailsCollapsed = collapsedTaskIds.has(taskId);
    if (detailsCollapsed) card.classList.add("is-collapsed");
    const top = document.createElement("div");
    top.className = "task-card-top";
    const trader = document.createElement("span");
    trader.className = "task-trader";
    trader.textContent = task.trader || "—";
    const status = document.createElement("span");
    status.className = "task-status";
    status.dataset.state = task.state;
    const taskStatus = ({ active: "进行中", missing_review: "待复核", complete: "已完成" })[task.state] || task.state;
    status.textContent = taskHidden ? `已隐藏 · ${taskStatus}` : taskStatus;
    top.append(trader, status);
    const heading = document.createElement("div");
    heading.className = "task-card-heading";
    const title = document.createElement("h3");
    title.className = "task-title";
    if (task.source_url) {
      const titleLink = document.createElement("a");
      titleLink.className = "task-title-link";
      titleLink.href = task.source_url;
      titleLink.target = "_blank";
      titleLink.rel = "noopener noreferrer";
      titleLink.textContent = task.title;
      title.append(titleLink);
    } else {
      title.textContent = task.title;
    }
    heading.append(title);
    if (task.source_url) {
      const source = document.createElement("a");
      source.className = "task-source-link";
      source.href = task.source_url;
      source.target = "_blank";
      source.rel = "noopener noreferrer";
      source.textContent = `来源 · ${task.source_version || "EFTarkov"}`;
      heading.append(source);
    }
    const collapseButton = document.createElement("button");
    collapseButton.type = "button";
    collapseButton.className = "task-collapse-button";
    collapseButton.dataset.action = "toggle-collapse";
    collapseButton.dataset.id = taskId;
    collapseButton.textContent = detailsCollapsed ? "展开" : "收起";
    collapseButton.title = detailsCollapsed ? "展开任务要求和操作" : "折叠任务要求和操作";
    collapseButton.setAttribute("aria-expanded", String(!detailsCollapsed));
    heading.append(collapseButton);
    card.append(top, heading);

    if (requiredCount) {
      const progress = document.createElement("div");
      progress.className = "task-progress";
      const progressLabel = document.createElement("span");
      progressLabel.className = "task-progress-label";
      progressLabel.textContent = `${completedCount}/${requiredCount} 项要求`;
      const progressTrack = document.createElement("div");
      progressTrack.className = "task-progress-track";
      progressTrack.setAttribute("role", "progressbar");
      progressTrack.setAttribute("aria-valuemin", "0");
      progressTrack.setAttribute("aria-valuemax", String(requiredCount));
      progressTrack.setAttribute("aria-valuenow", String(completedCount));
      const progressFill = document.createElement("span");
      progressFill.style.width = `${Math.min(100, completedCount / requiredCount * 100)}%`;
      progressTrack.append(progressFill);
      progress.append(progressLabel, progressTrack);
      card.append(progress);
    }

    const taskContent = document.createElement("div");
    taskContent.className = "task-card-content";
    taskContent.hidden = detailsCollapsed;
    if (requirements.length) {
      taskContent.append(buildTaskRequirementList(task));
    }

    const normalizeTaskInfo = (text) => formatTaskRequirement(text).replace(/\s+/g, " ").toLocaleLowerCase();
    const requirementTexts = new Set(requirements.map((requirement) => normalizeTaskInfo(requirement.text)));
    const extraLines = String(task.objective || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .map(formatTaskRequirement)
      .filter((line) => line && !requirementTexts.has(normalizeTaskInfo(line)));
    const visibleExtraLines = filterAssaultWeaponChoices(
      task,
      extraLines.filter((line) => !isUnavailableAcquisitionLine(line)),
    );
    const supplemental = isMp133Gunsmith ? [] : [...new Set([...visibleExtraLines, task.item_name].filter(Boolean))];
    if (supplemental.length) {
      const infoList = document.createElement("ul");
      infoList.className = "task-info-list";
      let lastTaskInfoIsKey = false;
      for (const line of supplemental) {
        const item = document.createElement("li");
        item.className = "task-info-item";
        const requiredItemInfo = line.match(/^需要(?:钥匙|物品)\s*[:：]\s*(.*)$/u);
        const acquisitionInfo = line.match(/^(?:钥匙获取|获取方式|物品获取方式)\s*[:：]\s*(.*)$/u);
        if (requiredItemInfo) {
          lastTaskInfoIsKey = isKeyItem({ name: requiredItemInfo[1] });
          const label = document.createElement("strong");
          label.className = "task-info-label";
          label.textContent = `${lastTaskInfoIsKey ? "需要钥匙" : "需要物品"}：`;
          const value = document.createElement("span");
          value.textContent = requiredItemInfo[1];
          item.append(label, value);
        } else if (acquisitionInfo) {
          const label = document.createElement("strong");
          label.className = "task-info-label";
          label.textContent = `${lastTaskInfoIsKey ? "钥匙获取" : "获取方式"}：`;
          const value = document.createElement("span");
          value.textContent = lastTaskInfoIsKey
            ? acquisitionInfo[1]
            : acquisitionInfo[1].replace(/钥匙详情/g, "物品详情");
          item.append(label, value);
        } else {
          item.textContent = line;
        }
        infoList.append(item);
      }
      taskContent.append(infoList);
    }

    const actions = document.createElement("div");
    actions.className = "task-card-actions";
    const visibility = document.createElement("button");
    visibility.className = "button button-secondary button-small";
    visibility.dataset.action = "toggle-hide";
    visibility.dataset.id = String(task.id);
    visibility.textContent = taskHidden ? "显示任务" : "隐藏任务";
    visibility.title = taskHidden
      ? "显示任务并启用关联钥匙筛选"
      : "隐藏任务与地图点位";
    actions.append(visibility);
    if (!requirements.length) {
      const increment = document.createElement("button");
      increment.className = "button button-quiet";
      increment.dataset.action = "increment";
      increment.dataset.id = String(task.id);
      increment.textContent = "+1 进度";
      increment.disabled = task.state === "complete";
      actions.append(increment);
    }
    const complete = document.createElement("button");
    complete.className = "button button-secondary button-small";
    complete.dataset.action = "complete";
    complete.dataset.id = String(task.id);
    complete.textContent = "标记任务完成";
    complete.disabled = task.state === "complete";
    actions.append(complete);
    const remove = document.createElement("button");
    remove.className = "button button-danger button-small";
    remove.dataset.action = "delete";
    remove.dataset.id = String(task.id);
    remove.textContent = "删除任务";
    actions.append(remove);
    taskContent.append(actions);
    card.append(taskContent);
    elements.rows.append(card);
  }
}

function formatTaskRequirement(rawText) {
  const text = String(rawText || "").replace(/^\s*\d+\s*[.、)]?\s*/, "").trim();
  return text || "未命名要求";
}

function buildTaskRequirementList(task, mapContext = false) {
  const requirements = Array.isArray(task.requirements) ? task.requirements : [];
  const list = document.createElement("ul");
  list.className = mapContext ? "task-requirements map-task-requirements" : "task-requirements";
  list.setAttribute("aria-label", `${task.title || "任务"}的要求`);
  requirements.forEach((requirement, index) => {
    const item = document.createElement("li");
    item.className = [requirement.completed ? "is-checked" : "", requirement.optional ? "is-optional" : ""]
      .filter(Boolean)
      .join(" ");
    const text = document.createElement("span");
    text.className = "task-requirement-label";
    text.textContent = formatTaskRequirement(requirement.text);
    const copy = document.createElement("span");
    copy.className = "task-requirement-copy";
    copy.append(text);
    if (requirement.optional) {
      const optional = document.createElement("span");
      optional.className = "task-optional-badge";
      optional.textContent = "可选";
      copy.append(optional);
    }
    if (Number(requirement.target_count) > 1) {
      const row = document.createElement("div");
      row.className = "task-requirement-count-row";
      const counter = document.createElement("input");
      counter.type = "number";
      counter.min = "0";
      counter.max = String(requirement.target_count);
      counter.step = "1";
      counter.value = String(requirement.current_count || 0);
      counter.dataset.previousValue = counter.value;
      counter.className = "task-requirement-count-input";
      counter.setAttribute("aria-label", `${text.textContent}进度`);
      counter.disabled = task.state === "complete";
      counter.dataset.action = "requirement-count";
      counter.dataset.id = String(task.id);
      counter.dataset.index = String(index);
      const target = document.createElement("span");
      target.className = "task-requirement-target";
      target.textContent = `/ ${requirement.target_count}`;
      row.append(counter, target, copy);
      item.append(row);
    } else {
      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = Boolean(requirement.completed);
      checkbox.disabled = task.state === "complete";
      checkbox.dataset.action = "requirement";
      checkbox.dataset.id = String(task.id);
      checkbox.dataset.index = String(index);
      label.append(checkbox, copy);
      item.append(label);
    }
    list.append(item);
  });
  return list;
}

function isUnavailableAcquisitionLine(line) {
  const acquisitionInfo = line.match(/^(?:钥匙获取|获取方式|物品获取方式)\s*[:：]\s*(.*)$/u);
  if (!acquisitionInfo) return false;
  const methodText = acquisitionInfo[1].trim();
  return !methodText || /(?:未列出可验证的购买\/交换方式|未解析到购买\/交换方式|未能读取获取方式|无法获取(?:到)?购买方式)/u.test(methodText);
}

function filterAssaultWeaponChoices(task, lines) {
  if (!usesAssaultWeaponCategoryForKills(task)) return lines;

  const visibleLines = [];
  let skipAcquisition = false;
  for (const line of lines) {
    const requiredItem = line.match(/^需要(钥匙|物品)\s*[:：]\s*(.*)$/u);
    if (requiredItem?.[1] === "物品") {
      skipAcquisition = true;
      continue;
    }
    if (skipAcquisition && /^(?:获取方式|物品获取方式)\s*[:：]/u.test(line)) {
      skipAcquisition = false;
      continue;
    }
    skipAcquisition = false;
    visibleLines.push(line);
  }
  return visibleLines;
}

function usesAssaultWeaponCategoryForKills(task) {
  const text = [
    task.objective,
    ...(Array.isArray(task.requirements) ? task.requirements.map((requirement) => requirement.text) : []),
    ...(Array.isArray(task.objectives) ? task.objectives.map((objective) => objective.text) : []),
  ].filter(Boolean).join("\n");
  return /使用[^。！？\r\n]{0,100}(?:突击步枪|突击卡宾枪)[^。！？\r\n]{0,100}(?:消灭|击杀|击败|杀死)/u.test(text);
}

function isMp133GunsmithTask(task) {
  const normalizedTitle = String(task.title || "").replace(/[^\p{L}\p{N}]/gu, "").toLocaleLowerCase();
  const isMp133 = normalizedTitle.includes("mp133");
  const isGunsmith = /枪匠|gunsmith/i.test(task.title || "");
  return task.source_task_id === "5ac23c6186f7741247042bad" || (isMp133 && isGunsmith);
}

function renderCatalogSummary() {
  const catalog = state?.catalog;
  const profile = state?.profiles?.find((entry) => entry.id === state.selected_profile_id);
  const unsupportedSeason = profile?.game_mode === "pvp-season";
  elements.catalogRefresh.disabled = Boolean(state?.catalog_busy) || unsupportedSeason;
  elements.catalogRefresh.textContent = state?.catalog_busy
    ? "同步中…"
    : unsupportedSeason ? "赛季 PvP 暂不支持" : "同步公开目录";
  if (catalog) {
    const version = catalog.source_version && catalog.source_version !== "unknown"
      ? catalog.source_version
      : "版本未知";
    const fetchedAt = catalog.fetched_at ? new Date(catalog.fetched_at).toLocaleString() : "时间未知";
    elements.catalogSummary.textContent = `${catalog.task_count} 条任务 · EFTarkov 页面标注 ${version} · 获取于 ${fetchedAt} · 游戏补丁覆盖未核实`;
  } else {
    elements.catalogSummary.textContent = unsupportedSeason
      ? "EFTarkov 未提供独立赛季 PvP 目录，不会套用常规 PvP 数据。"
      : "尚未同步任务资料。同步只读取公开任务页面，不会覆盖个人进度。";
  }
  elements.catalogStatus.textContent = state?.catalog_error || state?.catalog_status || "";

  const nextSnapshotId = catalog?.id ?? null;
  if (nextSnapshotId !== catalogSnapshotId) {
    catalogSnapshotId = nextSnapshotId;
    selectedCatalogTask = null;
    elements.catalogPreview.hidden = true;
    if (catalogSnapshotId && elements.catalogPanel.open) refreshCatalogTasks();
  }
  elements.catalogImport.disabled = catalogImportBusy || !selectedCatalogTask?.objectives?.length;
}

function renderCatalogResults(tasks) {
  elements.catalogResults.replaceChildren();
  if (!tasks.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = state?.catalog
      ? "没有匹配任务；可换名称或商人继续搜索。"
      : "先同步目录，再搜索要追踪的任务。";
    elements.catalogResults.append(empty);
    return;
  }
  for (const task of tasks) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "catalog-result";
    button.dataset.taskId = task.source_task_id;
    button.setAttribute("aria-selected", String(selectedCatalogTask?.source_task_id === task.source_task_id));
    const title = document.createElement("span");
    title.className = "catalog-result-title";
    title.textContent = task.title;
    const trader = document.createElement("span");
    trader.className = "catalog-result-trader";
    trader.textContent = task.trader;
    button.append(title, trader);
    button.addEventListener("click", () => selectCatalogTask(task));
    elements.catalogResults.append(button);
  }
}

function renderCatalogDetail(task) {
  selectedCatalogTask = task;
  elements.catalogPreview.hidden = false;
  elements.catalogTrader.textContent = `${task.trader} · 来源标注 ${task.source_version || "未知版本"}`;
  elements.catalogTitle.textContent = task.title;
  elements.catalogObjectives.replaceChildren();
  for (const objective of task.objectives || []) {
    const item = document.createElement("li");
    item.textContent = objective.text || "未命名目标";
    elements.catalogObjectives.append(item);
  }
  if (!task.objectives?.length) {
    const item = document.createElement("li");
    item.textContent = "未能读取任务目标；请打开来源页确认。";
    elements.catalogObjectives.append(item);
  }
  appendTaskSupportDetails(elements.catalogObjectives, task);
  elements.catalogSourceLink.href = task.source_url;
  elements.catalogImport.disabled = catalogImportBusy || !task.objectives?.length || task.details_status === "loading";
  for (const button of elements.catalogResults.querySelectorAll(".catalog-result")) {
    button.setAttribute("aria-selected", String(button.dataset.taskId === task.source_task_id));
  }
}

function appendSourceLink(parent, href, label) {
  if (!href) return;
  const link = document.createElement("a");
  link.href = href;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = label;
  parent.append(link);
}

function isKeyItem(item) {
  return Boolean(item && /钥匙|(?<![A-Za-z])key(?:[\s-]?card)?(?![A-Za-z])/i.test(String(item.name || "")));
}

function appendTaskSupportDetails(parent, task) {
  const allRequiredItems = task.key_requirements || [];
  const usesWeaponCategoryForKills = usesAssaultWeaponCategoryForKills(task);
  const requiredItems = usesWeaponCategoryForKills
    ? allRequiredItems.filter((item) => isKeyItem(item))
    : allRequiredItems;
  const keyTitle = document.createElement("li");
  keyTitle.className = "candidate-detail-heading";
  keyTitle.textContent = "任务所需钥匙与物品";
  parent.append(keyTitle);
  if (!requiredItems.length) {
    const item = document.createElement("li");
    item.textContent = usesWeaponCategoryForKills
      ? "本任务按枪械类别计数，无需逐一指定枪械型号。"
      : "来源页未标记额外钥匙或物品需求。";
    parent.append(item);
  }
  for (const requiredItem of requiredItems) {
    const itemIsKey = isKeyItem(requiredItem);
    const item = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = `${itemIsKey ? "钥匙" : "物品"}：${requiredItem.name || "未命名物品"}`;
    item.append(name);
    const methods = (requiredItem.acquisition_methods || []).filter((method) => (
      [method.trader, method.loyalty_level, method.requirements]
        .some((value) => String(value || "").trim())
    ));
    if (methods.length) {
      for (const method of methods) {
        const details = document.createElement("div");
        details.textContent = [
          itemIsKey ? "钥匙获取：" : "获取方式：",
          [method.trader, method.loyalty_level, method.requirements].filter(Boolean).join(" · "),
        ].join("");
        item.append(details);
      }
    }
    appendSourceLink(item, requiredItem.source_url, `${itemIsKey ? "钥匙" : "物品"}详情来源`);
    for (const point of requiredItem.map_points || []) {
      const location = document.createElement("div");
      location.textContent = `${itemIsKey ? "钥匙用途点" : "相关点位"}：${[point.map_name, point.floor_name, point.title].filter(Boolean).join(" · ")}${itemIsKey ? "（不是钥匙刷新点）" : ""}`;
      item.append(location);
      item.append(createPointImageLink(point, {
        taskTitle: task.title,
        pointNumber: point.pointNumber || 1,
        groupCount: point.groupCount || (requiredItem.map_points || []).length,
      }));
    }
    parent.append(item);
  }

  const mapTitle = document.createElement("li");
  mapTitle.className = "candidate-detail-heading";
  mapTitle.textContent = "任务地图位置";
  parent.append(mapTitle);
  const points = task.map_points || [];
  if (!points.length) {
    const item = document.createElement("li");
    item.textContent = "详情页暂无可验证的自动点位；资料库更新后会在地图区自动显示。";
    parent.append(item);
  }
  for (const [pointIndex, point] of points.entries()) {
    const item = document.createElement("li");
    item.textContent = [point.map_name, point.floor_name, point.title, point.description]
      .filter(Boolean)
      .join(" · ");
    item.append(createPointImageLink(point, {
      taskTitle: task.title,
      pointNumber: pointIndex + 1,
      groupCount: points.length,
    }));
    parent.append(item);
  }
}

async function refreshCatalogTasks() {
  if (!state?.catalog || !elements.catalogPanel.open) return;
  const generation = ++catalogQueryGeneration;
  const query = new URLSearchParams({ q: elements.catalogSearch.value.trim(), limit: "100" });
  try {
    const result = await request(`/api/catalog/tasks?${query}`);
    if (generation === catalogQueryGeneration) renderCatalogResults(result.tasks);
  } catch (error) {
    if (generation === catalogQueryGeneration) elements.catalogStatus.textContent = error.message;
  }
}

async function selectCatalogTask(task) {
  selectedCatalogTask = task;
  elements.catalogPreview.hidden = false;
  elements.catalogTrader.textContent = task.trader;
  elements.catalogTitle.textContent = task.title;
  elements.catalogObjectives.replaceChildren();
  const loading = document.createElement("li");
  loading.textContent = "正在读取任务目标…";
  elements.catalogObjectives.append(loading);
  elements.catalogImport.disabled = true;
  try {
    const result = await post("/api/catalog/details", {
      snapshot_id: task.snapshot_id,
      source_task_id: task.source_task_id,
    });
    if (selectedCatalogTask?.source_task_id === task.source_task_id) renderCatalogDetail(result.task);
  } catch (error) {
    if (selectedCatalogTask?.source_task_id !== task.source_task_id) return;
    elements.catalogObjectives.replaceChildren();
    const message = document.createElement("li");
    message.textContent = error.message;
    elements.catalogObjectives.append(message);
    elements.catalogSourceLink.href = task.source_url;
    elements.catalogPreview.hidden = false;
  }
}

function renderAnalysis() {
  const analysis = state?.analysis;
  const capture = state?.capture;
  elements.capture.disabled = false;
  elements.capture.textContent = "选择截图文件夹";
  elements.pageBadge.textContent = analysis?.kind || capture?.status || "等待截图";
  elements.pageBadge.dataset.kind = analysis?.kind || "";
  const profile = state?.profiles?.find((entry) => entry.id === state.analysis_profile_id);
  const summary = [];
  if (capture?.status) summary.push(capture.status);
  if (capture?.pending_count > 0) summary.push(`待处理截图：${capture.pending_count} 张`);
  if (profile) summary.push(`分析档案：${profile.name}（${profile.mode_label}）`);
  if (analysis?.trader) summary.push(`商人：${analysis.trader}`);
  if (analysis?.task_page_confident) summary.push("任务列表证据充分");
  if (analysis?.warning) summary.push(analysis.warning);
  if (capture?.error) summary.push(`错误：${capture.error}`);
  elements.analysis.textContent = summary.join("\n") || "尚未识别页面";

  const diagnostics = analysis?.diagnostics;
  elements.diagnosticDetails.textContent = diagnostics
    ? JSON.stringify({
        页面结论: analysis.kind,
        商人: analysis.trader,
        任务页置信: analysis.task_page_confident,
        页面证据: diagnostics.page_decision,
        商人卡片: diagnostics.trader_card_decision,
        卡片亮度: diagnostics.trader_card_scores,
        任务页签: diagnostics.task_tab_scores,
        装备页签: diagnostics.equipment_tab_scores,
        任务列表OCR: diagnostics.task_list_ocr,
      }, null, 2)
    : "等待分析结果";
  if (sourceImage && capture?.id === loadedCaptureId
    && screenshotOverlaySignature() !== drawnScreenshotOverlayKey) {
    drawCanvas();
  }
}

function renderScreenshotCandidates() {
  const analysis = state?.analysis;
  const currentScreenshotIsTaskPage = analysis?.kind === "商人任务"
    && analysis.task_page_confident
    && !state.capture?.processing
    && state.analysis_profile_id === state.selected_profile_id;
  const notifications = state?.capture?.task_notifications || [];
  const currentCaptureNotifications = notifications.filter(
    (notification) => notification.capture_id === state?.capture?.id,
  );
  const notificationsByCapture = new Map();
  notifications.forEach((notification, index) => {
    const captureId = String(notification.capture_id || `unknown-${index}`);
    if (!notificationsByCapture.has(captureId)) {
      notificationsByCapture.set(captureId, {
        captureId,
        createdAt: notification.created_at || "",
        firstIndex: index,
        tasks: [],
      });
    }
    notificationsByCapture.get(captureId).tasks.push(notification);
  });
  const captureNotifications = [...notificationsByCapture.values()]
    .map((capture) => ({
      ...capture,
      tasks: capture.tasks
        .map((task, index) => ({ task, index }))
        .sort((left, right) => {
          const leftOrder = Number(left.task.image_order);
          const rightOrder = Number(right.task.image_order);
          const normalizedLeft = Number.isFinite(leftOrder) && leftOrder > 0 ? leftOrder : left.index + 1;
          const normalizedRight = Number.isFinite(rightOrder) && rightOrder > 0 ? rightOrder : right.index + 1;
          return normalizedLeft - normalizedRight;
        })
        .map(({ task }) => task),
    }))
    .sort((left, right) => {
      const leftTime = Date.parse(left.createdAt) || 0;
      const rightTime = Date.parse(right.createdAt) || 0;
      return rightTime - leftTime || right.firstIndex - left.firstIndex;
    });
  const visible = currentScreenshotIsTaskPage || notifications.length > 0;
  const container = elements.screenshotCandidates;
  const previousList = container.querySelector(".task-notification-list");
  const previousScrollTop = previousList?.scrollTop || 0;
  const previousListTop = previousList?.getBoundingClientRect().top || 0;
  const previousAnchor = previousList
    ? [...previousList.querySelectorAll(".task-notification")]
      .find((card) => card.getBoundingClientRect().bottom > previousList.getBoundingClientRect().top)
    : null;
  const previousAnchorId = previousAnchor?.dataset.captureId || "";
  const previousAnchorOffset = previousAnchor
    ? previousAnchor.getBoundingClientRect().top - previousListTop
    : 0;
  container.replaceChildren();
  container.hidden = !visible;
  if (!visible) return;

  const heading = document.createElement("strong");
  heading.textContent = `截图添加通知（${captureNotifications.length} 张截图 · ${notifications.length} 个任务；最新在前）：`;
  container.append(heading);

  if (currentScreenshotIsTaskPage && !currentCaptureNotifications.length) {
    const message = document.createElement("p");
    message.textContent = "本张截图没有匹配到新的任务。";
    container.append(message);
  }

  if (!notifications.length) {
    return;
  }

  const list = document.createElement("div");
  list.className = "task-notification-list";
  for (const capture of captureNotifications) {
    const card = document.createElement("div");
    card.className = "task-notification";
    card.dataset.captureId = capture.captureId;
    const count = document.createElement("span");
    count.className = "task-notification-order";
    count.textContent = String(capture.tasks.length);
    count.title = `${capture.tasks.length} 个识别任务`;
    const description = document.createElement("div");
    description.className = "task-notification-content";
    const captureHeading = document.createElement("div");
    captureHeading.className = "task-notification-capture-heading";
    const trader = [...new Set(capture.tasks.map((task) => task.trader).filter(Boolean))].join("、") || "商人未知";
    const shotDate = capture.createdAt ? new Date(capture.createdAt) : null;
    const timeLabel = shotDate && !Number.isNaN(shotDate.getTime())
      ? shotDate.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" })
      : "";
    captureHeading.textContent = [trader, timeLabel].filter(Boolean).join(" · ");
    description.append(captureHeading);
    const taskList = document.createElement("div");
    taskList.className = "task-notification-tasks";
    for (const [index, notification] of capture.tasks.entries()) {
      const taskRow = document.createElement("div");
      taskRow.className = `task-notification-task is-${notification.status || "processing"}`;
      const order = document.createElement("span");
      order.className = "task-notification-task-order";
      order.textContent = String(notification.image_order || index + 1).padStart(2, "0");
      const title = document.createElement("strong");
      title.textContent = notification.title || "未命名任务";
      const status = document.createElement("span");
      status.className = "task-notification-task-status";
      const statusMessages = {
        processing: "查询中",
        importing: "加入中",
        added: "已加入",
        failed: "失败",
      };
      status.textContent = statusMessages[notification.status] || notification.message || "处理中";
      if (notification.message) status.title = notification.message;
      taskRow.append(order, title, status);
      if (notification.recognized_text && notification.recognized_text !== notification.title) {
        const evidence = document.createElement("small");
        evidence.className = "task-notification-evidence";
        evidence.textContent = `识别：${notification.recognized_text}`;
        taskRow.append(evidence);
      }
      if (notification.status === "failed" && notification.message) {
        const error = document.createElement("small");
        error.className = "task-notification-error";
        error.textContent = notification.message;
        taskRow.append(error);
      }
      if (notification.status === "failed" && notification.source_url) {
        appendSourceLink(taskRow, notification.source_url, "来源");
      }
      taskList.append(taskRow);
    }
    description.append(taskList);
    card.append(count, description);
    list.append(card);
  }
  container.append(list);
  if (previousScrollTop > 0) {
    const anchor = previousAnchorId
      ? [...list.querySelectorAll(".task-notification")]
        .find((card) => card.dataset.captureId === previousAnchorId)
      : null;
    if (anchor && previousAnchor) {
      const newAnchorOffset = anchor.getBoundingClientRect().top - list.getBoundingClientRect().top;
      list.scrollTop = Math.max(0, newAnchorOffset - previousAnchorOffset);
    } else {
      list.scrollTop = Math.min(previousScrollTop, list.scrollHeight - list.clientHeight);
    }
  }
}

async function loadMapIndex({ preserveSelection = false, restorePreferences = false } = {}) {
  elements.mapPlaceholder.hidden = false;
  elements.mapPlaceholder.textContent = "正在读取地图目录和清单任务点位；首次载入可能稍慢…";
  try {
    const result = await request("/api/maps");
    const previousMapId = elements.mapSelect.value;
    const previousTaskMapId = elements.taskMapFilter.value;
    const preferredTaskMapId = restorePreferences ? uiPreferences?.taskMapFilter : previousTaskMapId;
    mapDetailWarnings = result.detail_warnings || [];
    mapTaskIdsByMap = new Map();
    elements.taskMapFilter.replaceChildren();
    const allMapsOption = document.createElement("option");
    allMapsOption.value = "";
    allMapsOption.textContent = "全部地图";
    elements.taskMapFilter.append(allMapsOption);
    for (const map of result.maps || []) {
      const taskIds = (map.task_ids || []).map(String);
      mapTaskIdsByMap.set(String(map.map_id), new Set(taskIds));
      const option = document.createElement("option");
      option.value = String(map.map_id);
      option.textContent = map.active_task_count
        ? `${map.name} · ${map.active_task_count} 个任务`
        : map.name;
      elements.taskMapFilter.append(option);
    }
    elements.taskMapFilter.value = [...elements.taskMapFilter.options]
      .some((option) => option.value === preferredTaskMapId)
      ? preferredTaskMapId
      : "";
    elements.mapSelect.replaceChildren();
    for (const map of result.maps || []) {
      const option = document.createElement("option");
      option.value = map.map_id;
      option.textContent = map.active_point_count
        ? `${map.name} · ${map.active_point_count} 个点位`
        : map.name;
      elements.mapSelect.append(option);
    }
    if (!elements.mapSelect.options.length) throw new Error("地图目录为空");
    const preferredMapId = preserveSelection
      ? previousTaskMapId || previousMapId
      : restorePreferences
        ? preferredTaskMapId || uiPreferences?.selectedMapId
        : "";
    const selectedMapExists = [...elements.mapSelect.options]
      .some((option) => option.value === preferredMapId);
    elements.mapSelect.value = selectedMapExists
      ? preferredMapId
      : result.preferred_map_id || elements.mapSelect.options[0].value;
    elements.mapSelect.disabled = false;
    if (state) renderTasks(state.tasks);
    saveUiPreferences();
    await loadMapView();
  } catch (error) {
    elements.mapPlaceholder.textContent = `地图目录读取失败：${error.message}`;
    elements.mapSourceLink.removeAttribute("href");
    mapTaskIdsByMap.clear();
    elements.taskMapFilter.replaceChildren(new Option("全部地图", ""));
    if (state) renderTasks(state.tasks);
  }
}

const MAP_TASK_COLORS = [
  "#e76f51", "#4f83cc", "#44a581", "#b16ac7", "#d49a2a", "#328fa3",
  "#da5a8a", "#739a3d", "#8a70dc", "#cf7440", "#4580a6", "#9c5d73",
];
const MAP_TASK_SHAPES = ["circle", "diamond", "square", "triangle", "pentagon", "hexagon"];

function groupMapMarkers(markers, tasks) {
  const taskOrder = new Map((tasks || []).map((task, index) => [String(task.id), index]));
  const groupsByKey = new Map();
  for (const marker of markers) {
    const key = marker.task_id != null ? String(marker.task_id) : `title:${marker.task_title}`;
    if (!groupsByKey.has(key)) groupsByKey.set(key, []);
    groupsByKey.get(key).push(marker);
  }
  const groups = [...groupsByKey.entries()].sort(([leftKey], [rightKey]) => {
    const leftOrder = taskOrder.get(leftKey) ?? Number.MAX_SAFE_INTEGER;
    const rightOrder = taskOrder.get(rightKey) ?? Number.MAX_SAFE_INTEGER;
    return leftOrder - rightOrder;
  });
  const groupedMarkers = [];
  groups.forEach(([key, taskMarkers], groupIndex) => {
    const taskIndex = taskOrder.get(key) ?? groupIndex;
    taskMarkers.forEach((marker, markerIndex) => {
      groupedMarkers.push({
        ...marker,
        groupKey: key,
        groupNumber: groupIndex + 1,
        groupCount: taskMarkers.length,
        pointNumber: markerIndex + 1,
        taskColor: MAP_TASK_COLORS[taskIndex % MAP_TASK_COLORS.length],
        taskShape: MAP_TASK_SHAPES[taskIndex % MAP_TASK_SHAPES.length],
      });
    });
  });
  return groupedMarkers;
}

function renderMapAnnotations() {
  if (!mapView) return;
  const visibleCategories = new Set(
    [...elements.mapAnnotationFilters.querySelectorAll("input[data-map-annotation-filter]")]
      .filter((input) => input.checked)
      .map((input) => input.dataset.mapAnnotationFilter),
  );
  for (const annotation of mapView.annotations || []) {
    const activeCategories = (annotation.categories || []).filter((category) => visibleCategories.has(category));
    if (!activeCategories.length) continue;
    if (activeCategories.includes("location")) {
      const label = document.createElement("span");
      label.className = "map-location-label";
      label.textContent = annotation.title;
      label.style.left = annotation.x_percent + "%";
      label.style.top = annotation.y_percent + "%";
      elements.mapMarkers.append(label);
      continue;
    }
    const category = activeCategories.length > 1 ? "shared-exit" : activeCategories[0];
    const button = document.createElement("button");
    button.type = "button";
    button.className = "map-annotation-marker";
    button.dataset.category = category;
    button.style.left = annotation.x_percent + "%";
    button.style.top = annotation.y_percent + "%";
    const iconUrl = annotation.icon_urls?.[activeCategories[0]] || Object.values(annotation.icon_urls || {})[0] || "";
    if (iconUrl) {
      button.classList.add("has-icon");
      const icon = document.createElement("img");
      icon.src = iconUrl;
      icon.alt = "";
      icon.loading = "lazy";
      icon.addEventListener("error", () => {
        icon.remove();
        button.classList.remove("has-icon");
      }, { once: true });
      button.append(icon);
    }
    const annotationTitle = mapAnnotationTooltipText(annotation);
    button.setAttribute("aria-label", annotationTitle.split("\n")[0]);
    button.setAttribute("aria-describedby", "mapTooltip");
    const tooltipKey = `annotation:${annotation.id}`;
    button.addEventListener("pointerenter", (event) => showMapTooltipText(annotationTitle, tooltipKey, event));
    button.addEventListener("pointermove", positionMapTooltip);
    button.addEventListener("pointerleave", hideMapTooltip);
    button.addEventListener("focus", () => {
      const bounds = button.getBoundingClientRect();
      showMapTooltipText(annotationTitle, tooltipKey, { clientX: bounds.right, clientY: bounds.top });
    });
    button.addEventListener("blur", hideMapTooltip);
    button.addEventListener("click", () => showMapPointImage({
      ...annotation,
      task_title: annotation.annotation_label || "地图标注",
      pointNumber: 1,
      groupCount: 1,
    }));
    elements.mapMarkers.append(button);
  }
}

function mapMarkerOffsets(markers) {
  const mapWidth = elements.mapImageFrame.clientWidth;
  const mapHeight = mapWidth * (mapView?.floor?.height || 1) / (mapView?.floor?.width || 1);
  const positions = markers.map((marker) => ({
    x: Number(marker.x_percent) * mapWidth / 100,
    y: Number(marker.y_percent) * mapHeight / 100,
  }));
  const clusters = [];
  positions.forEach((position, index) => {
    let cluster = clusters.find((candidate) => candidate.some((member) => {
      const dx = position.x - positions[member].x;
      const dy = position.y - positions[member].y;
      return Math.hypot(dx, dy) < 24;
    }));
    if (!cluster) {
      cluster = [];
      clusters.push(cluster);
    }
    cluster.push(index);
  });
  const offsets = markers.map(() => ({ x: 0, y: 0 }));
  for (const cluster of clusters) {
    if (cluster.length < 2) continue;
    const radius = Math.min(26, Math.max(15, cluster.length * 6));
    cluster.forEach((markerIndex, clusterIndex) => {
      const angle = (2 * Math.PI * clusterIndex) / cluster.length - Math.PI / 2;
      offsets[markerIndex] = {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
      };
    });
  }
  return offsets;
}

function mapMarkerVisitTitle(marker) {
  const english = currentLanguage === "en";
  return [
    english ? `Quest ${marker.groupNumber}` : `任务 ${marker.groupNumber}`,
    marker.task_title,
    marker.floor_name,
    english ? `Point ${marker.pointNumber}/${marker.groupCount}` : `点位 ${marker.pointNumber}/${marker.groupCount}`,
    marker.title,
    marker.visited ? (english ? "✓ Visited" : "✓ 已到访") : "",
    marker.description,
    english ? "Left-click to view point details" : "左键查看点位信息",
    english ? "Right-click or Shift+Enter to toggle visited" : "右键或 Shift+Enter 切换到访勾选",
  ].filter(Boolean).join("\n");
}

function mapAnnotationTooltipText(annotation) {
  const categoryLabels = (annotation.categories || []).map((category) => {
    const categoryLabel = annotation.category_labels?.[category] || "地图标注";
    return translateUiText(categoryLabel);
  });
  const title = [
    [...new Set(categoryLabels)].join(" / "),
    annotation.title,
  ].filter(Boolean).join(" · ");
  return [
    title,
    annotation.floor_name ? `${translateUiText("楼层")}: ${annotation.floor_name}` : "",
    annotation.description,
  ].filter(Boolean).join("\n");
}

function positionMapTooltip(event) {
  const tooltip = elements.mapTooltip;
  if (tooltip.hidden || event.pointerType === "touch") return;
  const margin = 10;
  const offset = 12;
  const bounds = tooltip.getBoundingClientRect();
  let left = event.clientX + offset;
  let top = event.clientY + offset;
  if (left + bounds.width > window.innerWidth - margin) {
    left = Math.max(margin, event.clientX - bounds.width - offset);
  }
  if (top + bounds.height > window.innerHeight - margin) {
    top = Math.max(margin, event.clientY - bounds.height - offset);
  }
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

function showMapTooltip(marker, event) {
  showMapTooltipText(mapMarkerVisitTitle(marker), marker.id, event);
}

function showMapTooltipText(text, key, event) {
  if (event.pointerType === "touch") return;
  elements.mapTooltip.textContent = text;
  elements.mapTooltip.dataset.markerId = key;
  elements.mapTooltip.hidden = false;
  positionMapTooltip(event);
}

function hideMapTooltip() {
  elements.mapTooltip.hidden = true;
}

function updateMapMarkerVisitPresentation(marker, pin, visited) {
  marker.visited = visited;
  const storedMarker = mapView?.markers?.find((entry) => entry.id === marker.id);
  if (storedMarker) storedMarker.visited = visited;
  if (pin) {
    pin.classList.toggle("is-visited", visited);
    pin.setAttribute("aria-label", mapMarkerVisitTitle(marker));
  }
  if (!elements.mapTooltip.hidden && elements.mapTooltip.dataset.markerId === marker.id) {
    elements.mapTooltip.textContent = mapMarkerVisitTitle(marker);
  }
}

async function toggleMapMarkerVisited(marker, pin) {
  if (pin?.disabled) return;
  if (pin) pin.disabled = true;
  const beforeVisited = Boolean(marker.visited);
  const mapId = mapView?.map_id || elements.mapSelect.value;
  const visited = !marker.visited;
  try {
    const result = await post("/api/map/markers/visit", {
      map_id: mapId,
      marker_id: marker.id,
      visited,
    });
    updateMapMarkerVisitPresentation(marker, pin, result.visited);
    recordOperation("到访标记：" + marker.task_title + " · " + marker.title + " · "
      + (result.visited ? "标记已到访" : "取消到访标记"), "map-visit", {
      mapId,
      markerId: marker.id,
      beforeVisited,
    });
    const scrollTop = elements.mapTargetList.scrollTop;
    renderMapTargets(mapView?.markers || [], mapView?.tasks || []);
    elements.mapTargetList.scrollTop = scrollTop;
  } catch (error) {
    toast(error.message);
  } finally {
    if (pin?.isConnected) pin.disabled = false;
  }
}

function currentMapPointKey(marker) {
  return `${mapView?.map_id || elements.mapSelect.value}:${marker.id}`;
}

function setTaskHidden(taskId, hidden, announce = false) {
  const before = captureUiUndoSnapshot();
  const key = String(taskId);
  const task = state?.tasks?.find((item) => String(item.id) === key);
  if (hidden) {
    hiddenTaskIds.delete(key);
    hiddenTaskIds.add(key);
    while (hiddenTaskIds.size > 500) {
      hiddenTaskIds.delete(hiddenTaskIds.values().next().value);
    }
  } else hiddenTaskIds.delete(key);
  recordUiOperation((hidden ? "隐藏任务：" : "显示任务：") + (task?.title || "任务"), before);
  saveUiPreferences();
  if (state) {
    renderTasks(state.tasks);
    renderMapTargets(mapView?.markers || [], mapView?.tasks || []);
  }
  if (announce) {
    toast(hidden ? "任务和地图点位已隐藏" : "任务和地图点位已显示");
  }
}

function showTask(taskId, announce = false) {
  const before = captureUiUndoSnapshot();
  const key = String(taskId);
  const task = state?.tasks?.find((item) => String(item.id) === key);
  hiddenTaskIds.delete(key);
  for (const keyId of taskKeyIdsByTask.get(key) || []) hiddenKeyIds.delete(keyId);
  recordUiOperation("显示任务：" + (task?.title || "任务"), before);
  saveUiPreferences();
  if (state) {
    renderTasks(state.tasks);
    renderMapTargets(mapView?.markers || [], mapView?.tasks || []);
  }
  if (announce) toast("任务及关联钥匙筛选已显示");
}

function setMapPointHidden(marker, hidden) {
  const before = captureUiUndoSnapshot();
  const key = currentMapPointKey(marker);
  if (hidden) {
    hiddenMapPointIds.delete(key);
    hiddenMapPointIds.add(key);
    while (hiddenMapPointIds.size > 1000) {
      hiddenMapPointIds.delete(hiddenMapPointIds.values().next().value);
    }
  } else hiddenMapPointIds.delete(key);
  recordUiOperation(`${hidden ? "隐藏地图点位" : "显示地图点位"}：${marker.title}`, before);
  saveUiPreferences();
  renderMapTargets(mapView?.markers || [], mapView?.tasks || []);
}

function safePointImageUrl(value) {
  try {
    const url = new URL(value, "https://www.eftarkov.com");
    if (url.hostname === "eftarkov.com") url.hostname = "www.eftarkov.com";
    if (
      url.protocol !== "https:"
      || url.hostname !== "www.eftarkov.com"
      || !/^\/uploads\/infoImg\/[A-Za-z0-9._-]+\.(?:webp|png|jpe?g)$/i.test(url.pathname)
    ) return "";
    return url.href;
  } catch {
    return "";
  }
}

function safePointImageUrls(marker) {
  const candidates = [
    marker.source_image_urls,
    marker.info_image_urls,
    marker.image_urls,
    marker.source_image_url,
    marker.info_image_url,
    marker.image_url,
  ].flatMap((value) => Array.isArray(value) ? value : value ? [value] : [])
    .map((value) => typeof value === "string" ? value : value?.url || value?.src || value?.image_url || "");
  return [...new Set(candidates.map(safePointImageUrl).filter(Boolean))];
}

function createPointImageLink(point, options = {}) {
  const imageCount = safePointImageUrls(point).length;
  const link = document.createElement("a");
  link.className = options.className || "map-point-info-link";
  link.href = point.source_page_url || point.source_url || "#";
  link.textContent = imageCount
    ? `查看点位图片（${imageCount}张）`
    : "查看点位信息";
  link.title = imageCount
    ? `通过此链接查看该点位的全部 ${imageCount} 张图片和说明`
    : "打开 EFTarkov 点位说明";
  link.addEventListener("click", (event) => {
    event.preventDefault();
    showMapPointImage({
      ...point,
      task_title: options.taskTitle || point.task_title || "任务点位",
      pointNumber: options.pointNumber ?? point.pointNumber ?? 1,
      groupCount: options.groupCount ?? point.groupCount ?? 1,
    });
  });
  return link;
}

function renderMapPointImage() {
  elements.mapPointImageGallery.replaceChildren();
  elements.mapPointImageUnavailable.hidden = mapPointImageUrls.length > 0;
  elements.mapPointImageUnavailable.textContent = mapPointImageUrls.length
    ? ""
    : "该点位没有可用的说明图片，可打开 EFTarkov 来源页查看。";
  for (const [index, imageUrl] of mapPointImageUrls.entries()) {
    const card = document.createElement("figure");
    card.className = "map-point-image-card";
    const image = document.createElement("img");
    image.alt = currentLanguage === "en"
      ? `Waypoint image ${index + 1} of ${mapPointImageUrls.length}`
      : `点位图片 ${index + 1}/${mapPointImageUrls.length}`;
    image.loading = index < 2 ? "eager" : "lazy";
    image.decoding = "async";
    image.addEventListener("error", () => {
      image.remove();
      const failure = document.createElement("figcaption");
      failure.className = "map-point-image-load-error";
      failure.textContent = currentLanguage === "en" ? "Image unavailable" : "图片暂时无法加载";
      card.append(failure);
    }, { once: true });
    image.src = imageUrl;
    const caption = document.createElement("figcaption");
    caption.textContent = `${index + 1} / ${mapPointImageUrls.length}`;
    card.append(image, caption);
    elements.mapPointImageGallery.append(card);
  }
}

function showMapPointImage(marker) {
  mapPointImageUrls = safePointImageUrls(marker);
  elements.mapPointImageTitle.textContent = `${marker.task_title} · 点位 ${marker.pointNumber}/${marker.groupCount}`;
  elements.mapPointImageDescription.textContent = [
    marker.title,
    marker.floor_name,
    marker.description,
  ].filter(Boolean).join(" · ");
  const sourceUrl = marker.source_page_url || marker.source_url;
  elements.mapPointImageSource.hidden = !sourceUrl;
  if (sourceUrl) elements.mapPointImageSource.href = sourceUrl;
  renderMapPointImage();
  if (!elements.mapPointImageDialog.open) elements.mapPointImageDialog.showModal();
}

function currentMapDrawingId() {
  return String(elements.mapSelect.value || mapView?.map_id || "");
}

function mapDrawingStrokes(mapId = currentMapDrawingId()) {
  return uiPreferences?.mapDrawings?.[mapId] || [];
}

function updateMapDrawingButtons() {
  const hasMap = Boolean(mapView && !elements.mapImage.hidden);
  const hasDrawings = mapDrawingStrokes().length > 0;
  elements.mapDrawButton.disabled = !hasMap;
  elements.mapUndoDrawingButton.disabled = !hasDrawings;
  elements.mapClearDrawingsButton.disabled = !hasDrawings;
}

function appendMapDrawingStroke(points) {
  if (points.length < 2) return;
  const pathData = points.map((point, index) => {
    const command = index === 0 ? "M" : "L";
    return command + (point[0] * 100).toFixed(3) + " " + (point[1] * 100).toFixed(3);
  }).join(" ");
  const outline = document.createElementNS("http://www.w3.org/2000/svg", "path");
  outline.setAttribute("d", pathData);
  outline.setAttribute("fill", "none");
  outline.setAttribute("stroke", "#ffffff");
  outline.setAttribute("stroke-opacity", "0.78");
  outline.setAttribute("stroke-width", "0.62");
  outline.setAttribute("stroke-linecap", "round");
  outline.setAttribute("stroke-linejoin", "round");
  outline.setAttribute("vector-effect", "non-scaling-stroke");
  const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
  line.setAttribute("d", pathData);
  line.setAttribute("fill", "none");
  line.setAttribute("stroke", "#e5484d");
  line.setAttribute("stroke-width", "0.3");
  line.setAttribute("stroke-linecap", "round");
  line.setAttribute("stroke-linejoin", "round");
  line.setAttribute("vector-effect", "non-scaling-stroke");
  elements.mapDrawings.append(outline, line);
  return { outline, line };
}

function renderMapDrawings() {
  elements.mapDrawings.replaceChildren();
  for (const stroke of mapDrawingStrokes()) appendMapDrawingStroke(stroke);
  activeMapDrawingElement = null;
  updateMapDrawingButtons();
}

function setMapDrawingMode(enabled) {
  const nextEnabled = Boolean(enabled && mapView && !elements.mapImage.hidden);
  if (!nextEnabled && activeMapDrawing) endMapDrawing(null, false);
  mapDrawingEnabled = nextEnabled;
  elements.mapImageFrame.classList.toggle("is-drawing", mapDrawingEnabled);
  elements.mapDrawButton.setAttribute("aria-pressed", String(mapDrawingEnabled));
  elements.mapDrawButton.textContent = mapDrawingEnabled ? "结束划线" : "划线";
  elements.mapDrawButton.title = mapDrawingEnabled ? "结束划线模式" : "按住鼠标拖动绘制路线";
  updateMapDrawingButtons();
}

function mapPointFromPointer(event) {
  const bounds = elements.mapCanvas.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return null;
  return [
    Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width)),
    Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height)),
  ];
}

function updateActiveMapDrawingPath() {
  if (!activeMapDrawing || activeMapDrawing.points.length < 2) return;
  const pathData = activeMapDrawing.points.map((point, index) => {
    const command = index === 0 ? "M" : "L";
    return command + (point[0] * 100).toFixed(3) + " " + (point[1] * 100).toFixed(3);
  }).join(" ");
  if (!activeMapDrawingElement) {
    activeMapDrawingElement = appendMapDrawingStroke(activeMapDrawing.points);
    return;
  }
  activeMapDrawingElement.outline.setAttribute("d", pathData);
  activeMapDrawingElement.line.setAttribute("d", pathData);
}

function startMapDrawing(event) {
  if (!mapDrawingEnabled || event.button !== 0 || !mapView) return;
  const point = mapPointFromPointer(event);
  if (!point) return;
  activeMapDrawing = { pointerId: event.pointerId, mapId: currentMapDrawingId(), points: [point] };
  activeMapDrawingElement = null;
  elements.mapImageFrame.setPointerCapture(event.pointerId);
  event.preventDefault();
  event.stopPropagation();
}

function moveMapDrawing(event) {
  if (!activeMapDrawing || event.pointerId !== activeMapDrawing.pointerId) return;
  const point = mapPointFromPointer(event);
  if (!point) return;
  const previous = activeMapDrawing.points[activeMapDrawing.points.length - 1];
  const bounds = elements.mapCanvas.getBoundingClientRect();
  if (Math.hypot((point[0] - previous[0]) * bounds.width, (point[1] - previous[1]) * bounds.height) < 3) return;
  if (activeMapDrawing.points.length < MAP_DRAWING_MAX_POINTS_PER_STROKE) {
    activeMapDrawing.points.push(point);
  } else {
    activeMapDrawing.points[activeMapDrawing.points.length - 1] = point;
  }
  updateActiveMapDrawingPath();
  event.preventDefault();
}

function endMapDrawing(event, commit = true) {
  if (!activeMapDrawing || (event?.pointerId != null && event.pointerId !== activeMapDrawing.pointerId)) return;
  const drawing = activeMapDrawing;
  const pointerId = drawing.pointerId;
  activeMapDrawing = null;
  activeMapDrawingElement = null;
  if (elements.mapImageFrame.hasPointerCapture(pointerId)) {
    elements.mapImageFrame.releasePointerCapture(pointerId);
  }
  if (commit && drawing.points.length > 1 && drawing.mapId === currentMapDrawingId() && uiPreferences) {
    const before = captureMapDrawingUndoSnapshot(drawing.mapId);
    const strokes = uiPreferences.mapDrawings[drawing.mapId] || [];
    strokes.push(drawing.points);
    delete uiPreferences.mapDrawings[drawing.mapId];
    uiPreferences.mapDrawings[drawing.mapId] = strokes.slice(-MAP_DRAWING_MAX_STROKES_PER_MAP);
    uiPreferences.mapDrawings = sanitizeMapDrawings(uiPreferences.mapDrawings);
    recordMapDrawingOperation("新增手绘线条：" + operationMapName(drawing.mapId), before);
    saveUiPreferences();
  }
  renderMapDrawings();
}

function undoMapDrawing() {
  const mapId = currentMapDrawingId();
  const strokes = mapDrawingStrokes(mapId);
  if (!strokes.length || !uiPreferences) return;
  const before = captureMapDrawingUndoSnapshot(mapId);
  strokes.pop();
  if (!strokes.length) delete uiPreferences.mapDrawings[mapId];
  recordMapDrawingOperation("撤销手绘线条：" + operationMapName(mapId), before);
  saveUiPreferences();
  renderMapDrawings();
}

function clearMapDrawings() {
  const mapId = currentMapDrawingId();
  const strokes = mapDrawingStrokes(mapId);
  if (!strokes.length || !uiPreferences) return;
  if (!window.confirm("清除当前地图上的全部手绘线条？可在处理记录中撤销。")) return;
  const before = captureMapDrawingUndoSnapshot(mapId);
  delete uiPreferences.mapDrawings[mapId];
  recordMapDrawingOperation("清除手绘线条：" + operationMapName(mapId), before);
  saveUiPreferences();
  renderMapDrawings();
}

function mapTaskCollapseKey(taskId) {
  return `${String(mapView?.map_id || elements.mapSelect.value || "")}:${String(taskId)}`;
}

function buildMapPointRow(marker, pointHidden) {
  const row = document.createElement("div");
  row.className = `map-point-row${pointHidden ? " is-hidden" : ""}`;
  const location = document.createElement("span");
  location.className = "map-point-location";
  location.textContent = [marker.title, marker.floor_name].filter(Boolean).join(" · ");
  const infoLink = createPointImageLink(marker, {
    className: "map-point-info-link",
    taskTitle: marker.task_title,
    pointNumber: marker.pointNumber,
    groupCount: marker.groupCount,
  });
  const visibility = document.createElement("button");
  visibility.type = "button";
  visibility.className = "button button-quiet button-small map-point-visibility";
  visibility.textContent = pointHidden ? "显示此点" : "隐藏此点";
  visibility.title = pointHidden ? "在地图上显示此点" : "仅在地图上隐藏此点";
  visibility.addEventListener("click", () => setMapPointHidden(marker, !pointHidden));
  row.append(location, infoLink, visibility);
  return row;
}

function renderMapTargets(markers, tasks = []) {
  hideMapTooltip();
  elements.mapTargetList.replaceChildren();
  elements.mapMarkers.replaceChildren();
  const tasksById = new Map((state?.tasks || []).map((task) => [String(task.id), task]));
  const groupedMarkers = groupMapMarkers(markers.filter((marker) => marker.point_kind !== "local"), orderedTasks(tasks));
  const keyVisibleMarkers = groupedMarkers.filter((marker) => (
    ![...(taskKeyIdsByTask.get(marker.groupKey) || [])].some((keyId) => hiddenKeyIds.has(keyId))
  ));
  const taskVisibleMarkers = keyVisibleMarkers.filter((marker) => !hiddenTaskIds.has(marker.groupKey));
  const visibleMarkers = taskVisibleMarkers.filter((marker) => !hiddenMapPointIds.has(currentMapPointKey(marker)));
  const offsets = mapMarkerOffsets(visibleMarkers);
  const offsetsByMarkerKey = new Map(visibleMarkers.map((marker, index) => [
    `${marker.groupKey}:${marker.pointNumber}`,
    offsets[index],
  ]));
  if (!keyVisibleMarkers.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "当前地图暂无已追踪任务的自动点位。资料库中有可验证坐标时，会自动显示在这里。";
    elements.mapTargetList.append(empty);
  }
  let currentGroupKey = "";
  let currentGroupContent = null;
  for (const marker of keyVisibleMarkers) {
    if (marker.groupKey !== currentGroupKey) {
      currentGroupKey = marker.groupKey;
      const groupCard = document.createElement("section");
      const groupHeading = document.createElement("div");
      const isHidden = hiddenTaskIds.has(marker.groupKey);
      groupCard.className = `task-card map-task-card${isHidden ? " is-hidden" : ""}`;
      groupHeading.className = "map-task-group";
      const swatch = document.createElement("span");
      swatch.className = "map-task-swatch";
      swatch.dataset.shape = marker.taskShape;
      swatch.style.setProperty("--task-color", marker.taskColor);
      const collapseKey = mapTaskCollapseKey(marker.groupKey);
      const isCollapsed = collapsedMapTaskGroups.has(collapseKey);
      const collapseButton = document.createElement("button");
      collapseButton.type = "button";
      collapseButton.className = "map-task-collapse";
      collapseButton.setAttribute("aria-expanded", String(!isCollapsed));
      const label = document.createElement("strong");
      label.textContent = `任务 ${marker.groupNumber} · ${marker.task_title}`;
      const collapseIcon = document.createElement("span");
      collapseIcon.className = "map-task-collapse-icon";
      collapseIcon.setAttribute("aria-hidden", "true");
      const updateCollapseButton = (collapsed) => {
        collapseIcon.textContent = collapsed ? "▸" : "▾";
        collapseButton.setAttribute("aria-expanded", String(!collapsed));
        collapseButton.setAttribute("aria-label", `${collapsed ? "展开" : "收起"}任务要求：${marker.task_title}`);
        collapseButton.title = `${collapsed ? "展开" : "收起"}此任务的要求`;
        groupHeading.classList.toggle("is-collapsed", collapsed);
        groupContent.hidden = collapsed;
      };
      collapseButton.append(label, collapseIcon);
      const count = document.createElement("span");
      count.className = "map-task-group-count";
      const groupPointCount = keyVisibleMarkers.filter((entry) => entry.groupKey === marker.groupKey).length;
      const displayedPointCount = visibleMarkers.filter((entry) => entry.groupKey === marker.groupKey).length;
      count.textContent = `${displayedPointCount}/${groupPointCount} 个地图标点`;
      const visibility = document.createElement("button");
      visibility.type = "button";
      visibility.className = "button button-secondary button-small map-task-visibility";
      visibility.textContent = isHidden ? "显示" : "隐藏";
      visibility.title = isHidden
        ? "在任务清单和地图上显示此任务"
        : "同时从任务清单和地图上隐藏此任务";
      visibility.setAttribute("aria-label", isHidden
        ? `显示任务：${marker.task_title}`
        : `隐藏任务：${marker.task_title}`);
      visibility.addEventListener("click", () => {
        const scrollTop = elements.mapTargetList.scrollTop;
        setTaskHidden(marker.groupKey, !hiddenTaskIds.has(marker.groupKey));
        elements.mapTargetList.scrollTop = scrollTop;
      });
      const completeButton = document.createElement("button");
      completeButton.type = "button";
      completeButton.className = "button button-secondary button-small map-task-complete";
      completeButton.textContent = "完成任务";
      completeButton.title = `直接标记任务为完成：${marker.task_title}`;
      completeButton.setAttribute("aria-label", `直接完成任务：${marker.task_title}`);
      const completeTaskId = String(marker.task_id || "");
      completeButton.disabled = !/^\d+$/.test(completeTaskId);
      completeButton.addEventListener("click", async (event) => {
        event.stopPropagation();
        if (completeButton.disabled) return;
        const task = state?.tasks?.find((item) => String(item.id) === completeTaskId);
        if (!task) return;
        const beforeUi = captureUiUndoSnapshot();
        const scrollTop = elements.mapTargetList.scrollTop;
        completeButton.disabled = true;
        try {
          await post(`/api/tasks/${completeTaskId}/complete`);
          recordOperation(`标记任务完成：${task.title}`, "task", {
            beforeTask: taskSnapshot(task),
            afterTaskId: completeTaskId,
            beforeUi,
          });
          await refreshState();
          await loadMapIndex({ preserveSelection: true });
          elements.mapTargetList.scrollTop = scrollTop;
          toast(`任务已完成：${marker.task_title}`);
        } catch (error) {
          completeButton.disabled = false;
          toast(error.message);
        }
      });
      const groupActions = document.createElement("div");
      groupActions.className = "map-task-group-actions";
      groupActions.append(visibility, completeButton);
      const groupContent = document.createElement("div");
      groupContent.className = "map-task-group-content";
      groupContent.hidden = isCollapsed;
      currentGroupContent = groupContent;
      const groupTask = tasksById.get(String(marker.groupKey));
      if (groupTask?.requirements?.length) {
        groupContent.append(buildTaskRequirementList(groupTask, true));
      }
      collapseButton.addEventListener("click", () => {
        const nextCollapsed = !collapsedMapTaskGroups.has(collapseKey);
        if (nextCollapsed) collapsedMapTaskGroups.add(collapseKey);
        else collapsedMapTaskGroups.delete(collapseKey);
        saveUiPreferences();
        updateCollapseButton(nextCollapsed);
      });
      groupHeading.append(swatch, collapseButton, count, groupActions);
      updateCollapseButton(isCollapsed);
      groupCard.append(groupHeading, groupContent);
      elements.mapTargetList.append(groupCard);
    }
    const taskHidden = hiddenTaskIds.has(marker.groupKey);
    const pointHidden = hiddenMapPointIds.has(currentMapPointKey(marker));
    let pin = null;
    if (!taskHidden && !pointHidden) {
      pin = document.createElement("button");
      pin.type = "button";
      pin.className = "map-marker";
      pin.dataset.kind = marker.point_kind || "objective";
      pin.style.setProperty("--task-color", marker.taskColor);
      pin.style.left = `${marker.x_percent}%`;
      pin.style.top = `${marker.y_percent}%`;
      const offset = offsetsByMarkerKey.get(`${marker.groupKey}:${marker.pointNumber}`) || { x: 0, y: 0 };
      pin.style.setProperty("--marker-offset-x", `${offset.x}px`);
      pin.style.setProperty("--marker-offset-y", `${offset.y}px`);
      const markerFace = document.createElement("span");
      markerFace.className = "map-marker-face";
      markerFace.dataset.shape = marker.taskShape;
      markerFace.textContent = String(marker.pointNumber);
      const visitedBadge = document.createElement("span");
      visitedBadge.className = "map-marker-visited-badge";
      visitedBadge.setAttribute("aria-hidden", "true");
      visitedBadge.textContent = "✓";
      pin.append(markerFace, visitedBadge);
      pin.classList.toggle("is-visited", Boolean(marker.visited));
      pin.setAttribute("aria-label", mapMarkerVisitTitle(marker));
      pin.setAttribute("aria-keyshortcuts", "Shift+Enter");
      pin.setAttribute("aria-describedby", "mapTooltip");
      pin.addEventListener("pointerenter", (event) => showMapTooltip(marker, event));
      pin.addEventListener("pointermove", positionMapTooltip);
      pin.addEventListener("pointerleave", hideMapTooltip);
      pin.addEventListener("focus", () => {
        const bounds = pin.getBoundingClientRect();
        showMapTooltip(marker, { clientX: bounds.right, clientY: bounds.top });
      });
      pin.addEventListener("blur", hideMapTooltip);
      pin.addEventListener("click", (event) => {
        event.stopPropagation();
        if (event.button === 0) showMapPointImage(marker);
      });
      pin.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && event.shiftKey) {
          event.preventDefault();
          toggleMapMarkerVisited(marker, pin);
        }
      });
      pin.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        event.stopPropagation();
        toggleMapMarkerVisited(marker, pin);
      });
      elements.mapMarkers.append(pin);
    }

    currentGroupContent?.append(buildMapPointRow(marker, pointHidden));
  }
  renderMapAnnotations();
  const taskCount = new Set(taskVisibleMarkers.map((marker) => marker.groupKey)).size;
  const hiddenPointCount = taskVisibleMarkers.length - visibleMarkers.length;
  elements.mapSummary.textContent = `${mapView?.map_name || "地图"} · ${taskCount} 个显示任务组 · ${visibleMarkers.length} 个地图标点${hiddenPointCount ? ` · ${hiddenPointCount} 个已隐藏` : ""}`;
}

function setMapZoom(value, persist = true) {
  mapZoom = Math.round(Math.min(MAP_ZOOM_MAX, Math.max(MAP_ZOOM_MIN, value)) * 100) / 100;
  elements.mapCanvas.style.transform = `scale(${mapZoom})`;
  elements.mapCanvas.style.setProperty("--map-overlay-inverse-zoom", String(1 / mapZoom));
  elements.mapZoomLevel.textContent = `${Math.round(mapZoom * 100)}%`;
  elements.mapZoomOutButton.disabled = mapZoom <= MAP_ZOOM_MIN;
  elements.mapZoomInButton.disabled = mapZoom >= MAP_ZOOM_MAX;
  elements.mapZoomResetButton.disabled = mapZoom === 1;
  if (persist) saveUiPreferences();
}

function startMapPan(event) {
  if (event.button !== 0 || event.target.closest(".map-marker")) return;
  mapPan = {
    pointerId: event.pointerId,
    pointerX: event.clientX,
    pointerY: event.clientY,
    scrollLeft: elements.mapImageFrame.scrollLeft,
    scrollTop: elements.mapImageFrame.scrollTop,
    moved: false,
  };
  elements.mapImageFrame.classList.add("is-dragging");
  elements.mapImageFrame.setPointerCapture(event.pointerId);
  event.preventDefault();
}

function moveMapPan(event) {
  if (!mapPan || event.pointerId !== mapPan.pointerId) return;
  const deltaX = event.clientX - mapPan.pointerX;
  const deltaY = event.clientY - mapPan.pointerY;
  if (Math.abs(deltaX) + Math.abs(deltaY) > 3) mapPan.moved = true;
  if (!mapPan.moved) return;
  elements.mapImageFrame.scrollLeft = mapPan.scrollLeft - deltaX;
  elements.mapImageFrame.scrollTop = mapPan.scrollTop - deltaY;
  event.preventDefault();
}

function endMapPan(event) {
  if (!mapPan || (event.pointerId != null && event.pointerId !== mapPan.pointerId)) return;
  const pointerId = mapPan.pointerId;
  mapPan = null;
  elements.mapImageFrame.classList.remove("is-dragging");
  if (elements.mapImageFrame.hasPointerCapture(pointerId)) {
    elements.mapImageFrame.releasePointerCapture(pointerId);
  }
}

function syncMapFullscreenButton() {
  const fullscreen = document.fullscreenElement === elements.mapPlannerPanel;
  elements.mapFullscreenButton.textContent = fullscreen ? "退出全屏" : "全屏";
  elements.mapFullscreenButton.setAttribute("aria-label", fullscreen ? "退出地图全屏" : "地图全屏");
  elements.mapFullscreenButton.title = fullscreen ? "退出全屏" : "地图全屏";
}

async function toggleMapFullscreen() {
  try {
    if (document.fullscreenElement === elements.mapPlannerPanel) {
      await document.exitFullscreen();
    } else {
      await elements.mapPlannerPanel.requestFullscreen();
    }
  } catch (error) {
    toast(`无法切换全屏：${error.message}`);
  }
}

async function loadMapView(requestedFloorKey = "") {
  const mapId = elements.mapSelect.value;
  if (!mapId) return;
  if (activeMapDrawing) endMapDrawing(null, false);
  const generation = ++mapViewGeneration;
  const params = new URLSearchParams({ map_id: mapId });
  const floorKey = requestedFloorKey || uiPreferences?.selectedMapFloors?.[mapId] || "";
  if (floorKey) params.set("floor", floorKey);
  if (mapView?.map_id !== mapId) {
    elements.mapFloorSelect.replaceChildren();
    elements.mapFloorSelect.disabled = true;
  }
  elements.mapImage.hidden = true;
  updateMapDrawingButtons();
  elements.mapPlaceholder.hidden = false;
  elements.mapPlaceholder.textContent = "正在载入地图任务点位…";
  try {
    const result = await request(`/api/map?${params}`);
    if (generation !== mapViewGeneration) return;
    mapView = result;
    const floors = result.floors || [];
    elements.mapFloorSelect.replaceChildren();
    for (const floor of floors) {
      const option = document.createElement("option");
      option.value = String(floor.key);
      option.textContent = floor.name || `楼层 ${floor.key}`;
      elements.mapFloorSelect.append(option);
    }
    elements.mapFloorSelect.value = String(result.floor?.key || "");
    elements.mapFloorSelect.disabled = floors.length <= 1;
    if (result.floor?.key && uiPreferences) {
      uiPreferences.selectedMapFloors[result.map_id] = String(result.floor.key);
      saveUiPreferences();
    }
    const activeMarkers = (result.markers || []).filter((marker) => marker.point_kind !== "local");
    const activeTaskIds = new Set(activeMarkers
      .filter((marker) => marker.task_id != null)
      .map((marker) => String(marker.task_id)));
    const mapOption = [...elements.mapSelect.options].find((option) => option.value === String(result.map_id));
    if (mapOption) {
      mapOption.textContent = activeMarkers.length
        ? `${result.map_name} · ${activeMarkers.length} 个点位`
        : result.map_name;
    }
    const taskMapOption = [...elements.taskMapFilter.options]
      .find((option) => option.value === String(result.map_id));
    if (taskMapOption) {
      taskMapOption.textContent = activeTaskIds.size
        ? `${result.map_name} · ${activeTaskIds.size} 个任务`
        : result.map_name;
      if (elements.taskMapFilter.value === String(result.map_id) && state) renderTasks(state.tasks);
    }
    if (state) updateTaskMapFilterOptions(state.tasks);
    elements.mapSourceLink.href = result.source_url;
    renderMapTargets(result.markers || [], result.tasks || []);
    renderMapDrawings();
    elements.mapImage.hidden = false;
    elements.mapImage.onload = () => {
      if (generation !== mapViewGeneration) return;
      elements.mapPlaceholder.hidden = true;
      updateMapDrawingButtons();
    };
    elements.mapImage.onerror = () => {
      if (generation !== mapViewGeneration) return;
      elements.mapImage.hidden = true;
      elements.mapPlaceholder.hidden = false;
      elements.mapPlaceholder.textContent = "地图点位已读取，但 EFTarkov 底图暂时无法加载；请检查网络后重试。";
      updateMapDrawingButtons();
    };
    elements.mapImage.src = result.image_url;
    const detailWarnings = result.detail_warnings || mapDetailWarnings;
    const hasMarkers = (result.markers || []).some((marker) => marker.point_kind !== "local");
    const hasAnnotations = (result.annotations || []).length > 0;
    elements.mapHint.textContent = detailWarnings.length
      ? `部分任务详情暂时未能读取，自动点位可能不完整：${detailWarnings.join("、")}`
      : hasMarkers
        ? "左键编号标记查看点位信息，右键切换到访勾选（勾显示在标记右下角）；右侧可隐藏单个点或查看全部说明图片。悬停撤离/转移标记可立即查看名称和楼层。"
        : hasAnnotations
          ? "悬停撤离/转移点立即查看名称和楼层；点击标记查看来源图片。"
        : result.tasks.length
          ? "当前任务暂无可验证坐标；资料库提供点位后会自动标注。"
          : "加入或导入任务后，可在这里查看资料库中的自动点位。";
  } catch (error) {
    if (generation !== mapViewGeneration) return;
    mapView = null;
    elements.mapFloorSelect.disabled = true;
    elements.mapImage.hidden = true;
    elements.mapMarkers.replaceChildren();
    renderMapDrawings();
    elements.mapPlaceholder.hidden = false;
    elements.mapPlaceholder.textContent = `地图载入失败：${error.message}`;
    elements.mapSummary.textContent = "未能载入地图数据。";
    elements.mapSourceLink.removeAttribute("href");
  }
}

function drawCanvas() {
  if (!sourceImage) return;
  const canvas = elements.canvas;
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.drawImage(sourceImage, 0, 0, canvas.width, canvas.height);
  drawScreenshotRegionOverlays(context, canvas.width, canvas.height);
  drawnScreenshotOverlayKey = screenshotOverlaySignature();
}

function screenshotOverlaySignature() {
  const analysis = state?.analysis;
  const diagnostics = analysis?.diagnostics || {};
  return JSON.stringify([
    state?.capture?.id || "",
    analysis?.kind || "",
    analysis?.trader || "",
    diagnostics.regions || {},
    Boolean(diagnostics.task_list_ocr),
  ]);
}

function drawScreenshotRegionOverlays(context, imageWidth, imageHeight) {
  const analysis = state?.analysis;
  const diagnostics = analysis?.diagnostics;
  const regions = diagnostics?.regions;
  if (!regions || typeof regions !== "object") return;
  const definitions = [];
  if (Array.isArray(regions.top_tabs)) {
    definitions.push({ bounds: regions.top_tabs, normalized: true, label: "顶部页签识别区", color: "#52b7ff" });
  }
  if (analysis.trader) {
    const selectedCard = (diagnostics.trader_card_scores || []).find(
      (entry) => entry.trader === analysis.trader && Array.isArray(entry.bounds),
    );
    if (selectedCard) {
      definitions.push({ bounds: selectedCard.bounds, normalized: false, label: `商人卡片 · ${analysis.trader}`, color: "#c78bff" });
    }
  }
  if (analysis.kind === "商人任务" || Array.isArray(diagnostics.task_list_ocr)) {
    if (Array.isArray(regions.task_list)) {
      definitions.push({ bounds: regions.task_list, normalized: true, label: "任务列表识别区", color: "#ffc857" });
    }
  }
  const lineWidth = Math.max(2, Math.min(imageWidth, imageHeight) * 0.002);
  const fontSize = Math.max(13, imageWidth * 0.018);
  context.save();
  context.lineWidth = lineWidth;
  context.font = `700 ${fontSize}px ${getComputedStyle(document.body).fontFamily}`;
  for (const definition of definitions) {
    const bounds = definition.bounds;
    if (!Array.isArray(bounds) || bounds.length !== 4 || !bounds.every((value) => Number.isFinite(Number(value)))) {
      continue;
    }
    const scaleX = definition.normalized ? imageWidth : 1;
    const scaleY = definition.normalized ? imageHeight : 1;
    const [leftValue, topValue, rightValue, bottomValue] = bounds.map((value) => Number(value));
    const left = Math.max(0, Math.min(imageWidth - 1, leftValue * scaleX));
    const top = Math.max(0, Math.min(imageHeight - 1, topValue * scaleY));
    const right = Math.max(left + 1, Math.min(imageWidth, rightValue * scaleX));
    const bottom = Math.max(top + 1, Math.min(imageHeight, bottomValue * scaleY));
    const width = right - left;
    const height = bottom - top;
    context.globalAlpha = 0.08;
    context.fillStyle = definition.color;
    context.fillRect(left, top, width, height);
    context.globalAlpha = 1;
    context.strokeStyle = definition.color;
    context.strokeRect(left, top, width, height);
    const paddingX = fontSize * 0.42;
    const paddingY = fontSize * 0.2;
    const labelWidth = context.measureText(definition.label).width + paddingX * 2;
    const labelHeight = fontSize + paddingY * 2;
    const labelTop = Math.max(0, top - labelHeight - lineWidth);
    context.fillStyle = definition.color;
    context.fillRect(left, labelTop, labelWidth, labelHeight);
    context.fillStyle = "#101317";
    context.textBaseline = "top";
    context.fillText(definition.label, left + paddingX, labelTop + paddingY);
  }
  context.restore();
}

function clearScreenshotPreview() {
  sourceImage = null;
  loadedCaptureId = null;
  drawnScreenshotOverlayKey = "";
  elements.canvas.width = 0;
  elements.canvas.height = 0;
  elements.canvas.classList.remove("ready");
  elements.canvasPlaceholder.hidden = false;
}

async function loadScreenshot(captureId) {
  const image = new Image();
  image.onload = () => {
    if (state?.capture?.id !== captureId) return;
    sourceImage = image;
    elements.canvas.width = image.naturalWidth;
    elements.canvas.height = image.naturalHeight;
    elements.canvas.classList.add("ready");
    elements.canvasPlaceholder.hidden = true;
    loadedCaptureId = captureId;
    drawCanvas();
  };
  image.onerror = () => toast("截图预览加载失败");
  image.src = `/api/screenshot?capture=${encodeURIComponent(captureId)}&v=${Date.now()}`;
}

function activeTaskIdSignature(tasks) {
  return tasks
    .filter((task) => task.state !== "complete")
    .map((task) => String(task.id))
    .sort()
    .join("|");
}

async function refreshState() {
  try {
    const previousPlayerId = state?.player?.id;
    const previousProfileId = state?.selected_profile_id;
    const previousTaskIds = state ? activeTaskIdSignature(state.tasks) : null;
    state = await request("/api/state");
    if (String(previousPlayerId || "") !== String(state.player?.id || "")) {
      await activateScreenshotFolder(state.player?.id);
    }
    const profileChanged = activateProfileUiPreferences(
      state.player?.id,
      state.selected_profile_id,
      Boolean(state.player?.is_admin),
    );
    const mapTaskMembershipChanged = previousTaskIds !== null
      && previousPlayerId === state.player?.id
      && previousProfileId === state.selected_profile_id
      && previousTaskIds !== activeTaskIdSignature(state.tasks);
    setConnection(true);
    renderProfiles(state.profiles, state.selected_profile_id);
    openInitialProfileNameDialog();
    renderCaptureHistory(state.captures || []);
    renderAnalysis();
    renderScreenshotCandidates();
    renderCatalogSummary();
    if (profileChanged) {
      await loadMapIndex({ restorePreferences: true });
      if (hideoutCatalog) renderHideoutPlanner();
    } else {
      renderTasks(state.tasks);
      if (mapTaskMembershipChanged) loadMapIndex({ preserveSelection: true });
    }
    if (!hideoutCatalog && !hideoutLoading) loadHideoutCatalog();
    if (state.capture.available && state.capture.id && state.capture.id !== loadedCaptureId) {
      loadScreenshot(state.capture.id);
    } else if (!state.capture.available) {
      clearScreenshotPreview();
    }
  } catch (error) {
    if (error.status !== 401) {
      setConnection(false);
      elements.analysis.textContent = error.message;
    }
  }
}

async function refreshLogs() {
  if (!state?.player?.is_admin) {
    elements.logs.textContent = "运行日志仅管理员可查看";
    elements.logPath.textContent = "";
    return;
  }
  try {
    const result = await request("/api/logs");
    elements.logs.textContent = result.lines.slice(-70).join("\n") || "暂无运行日志";
    elements.logPath.textContent = result.path;
  } catch (error) {
    elements.logs.textContent = error.message;
  }
}

elements.capture.addEventListener("click", async () => {
  await chooseScreenshotFolder();
});

elements.screenshotFolderInput.addEventListener("change", importSelectedScreenshotFolder);

elements.captureHistory.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-capture-id]");
  if (!button || button.getAttribute("aria-pressed") === "true") return;
  try {
    await post("/api/captures/select", { capture_id: button.dataset.captureId });
    await refreshState();
  } catch (error) {
    toast(error.message);
  }
});

elements.profile.addEventListener("change", async () => {
  try {
    await post("/api/profiles/select", { profile_id: Number(elements.profile.value) });
    await refreshState();
  } catch (error) {
    toast(error.message);
  }
});

document.querySelector("#newProfileButton").addEventListener("click", () => {
  resetProfileDialog();
  elements.profileForm.reset();
  elements.profileDialog.showModal();
});
elements.cancelProfileButton.addEventListener("click", () => elements.profileDialog.close());
elements.profileDialog.addEventListener("cancel", (event) => {
  if (profileNameSetupOpen) event.preventDefault();
});
elements.profileDialog.addEventListener("close", resetProfileDialog);
elements.profileForm.elements.game_mode.addEventListener("change", () => {
  elements.seasonField.hidden = elements.profileForm.elements.game_mode.value !== "pvp-season";
});
elements.profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(elements.profileForm);
  try {
    if (state?.profile_name_required) {
      await post("/api/profiles/name", { name: form.get("name") });
      await refreshState();
      elements.profileDialog.close();
      toast("本地档案已命名");
      return;
    }
    await post("/api/profiles", {
      name: form.get("name"),
      game_mode: form.get("game_mode"),
      season_id: form.get("season_id"),
    });
    elements.profileDialog.close();
    elements.profileForm.reset();
    elements.seasonField.hidden = true;
    await refreshState();
    toast("档案已创建并切换");
  } catch (error) {
    toast(error.message);
  }
});

elements.taskForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(elements.taskForm);
  const trader = String(form.get("trader") || "");
  const title = String(form.get("title") || "");
  const existingTask = state?.tasks?.find((task) => task.trader === trader && task.title === title);
  const beforeUi = captureUiUndoSnapshot();
  try {
    const result = await post("/api/tasks", {
      trader,
      title,
      objective: form.get("objective"),
      item_name: form.get("item_name"),
      required_count: form.get("required_count") || null,
    });
    recordOperation(`${existingTask ? "更新任务" : "添加任务"}：${title}`, "task", {
      beforeTask: taskSnapshot(existingTask),
      afterTaskId: result.task.id,
      beforeUi,
    });
    elements.taskForm.reset();
    await refreshState();
    toast("任务已保存");
  } catch (error) {
    toast(error.message);
  }
});

elements.catalogRefresh.addEventListener("click", async () => {
  try {
    const result = await post("/api/catalog/refresh");
    toast(result.message);
    await refreshState();
  } catch (error) {
    toast(error.message);
  }
});

elements.catalogPanel.addEventListener("toggle", () => {
  if (elements.catalogPanel.open) refreshCatalogTasks();
});
for (const panel of [elements.addTaskPanel, elements.catalogPanel, elements.diagnosticsPanel]) {
  panel.querySelector("summary").addEventListener("click", () => setTimeout(saveUiPreferences, 0));
}

elements.catalogSearch.addEventListener("input", () => {
  clearTimeout(catalogSearchTimer);
  catalogSearchTimer = setTimeout(refreshCatalogTasks, 250);
});

elements.catalogImport.addEventListener("click", async () => {
  if (!selectedCatalogTask || catalogImportBusy) return;
  catalogImportBusy = true;
  renderCatalogSummary();
  try {
    const beforeTask = state?.tasks?.find((task) => (
      task.source_task_id === selectedCatalogTask.source_task_id
      || task.trader === selectedCatalogTask.trader && task.title === selectedCatalogTask.title
    ));
    const beforeUi = captureUiUndoSnapshot();
    const result = await post("/api/catalog/import", {
      snapshot_id: selectedCatalogTask.snapshot_id,
      source_task_id: selectedCatalogTask.source_task_id,
    });
    recordOperation(`${beforeTask ? "更新任务" : "导入任务"}：${result.task.title}`, "task", {
      beforeTask: taskSnapshot(beforeTask),
      afterTaskId: result.task.id,
      beforeUi,
    });
    await refreshState();
    toast("任务与目标已加入当前档案");
  } catch (error) {
    toast(error.message);
  } finally {
    catalogImportBusy = false;
    renderCatalogSummary();
  }
});

elements.rows.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  if (action === "toggle-hide") {
    const taskId = String(button.dataset.id);
    const task = state?.tasks?.find((item) => String(item.id) === taskId);
    if (task && (hiddenTaskIds.has(taskId) || taskHiddenByKey(task))) {
      showTask(taskId, true);
    } else {
      setTaskHidden(taskId, true, true);
    }
    return;
  }
  if (action === "toggle-collapse") {
    const taskId = button.dataset.id;
    const card = button.closest(".task-card");
    const content = card?.querySelector(".task-card-content");
    if (!content) return;
    const detailsCollapsed = !content.hidden;
    content.hidden = detailsCollapsed;
    button.textContent = detailsCollapsed ? "展开" : "收起";
    button.title = detailsCollapsed ? "展开任务要求和操作" : "折叠任务要求和操作";
    button.setAttribute("aria-expanded", String(!detailsCollapsed));
    card.classList.toggle("is-collapsed", detailsCollapsed);
    if (detailsCollapsed) collapsedTaskIds.add(taskId);
    else collapsedTaskIds.delete(taskId);
    saveUiPreferences();
    return;
  }
  if (action === "delete") {
    const task = state?.tasks?.find((item) => String(item.id) === button.dataset.id);
    const title = task?.title || "此任务";
    if (!window.confirm(`确定从当前清单删除“${title}”？可在处理记录中撤销。`)) return;
  }
  try {
    const task = state?.tasks?.find((item) => String(item.id) === button.dataset.id);
    const beforeUi = captureUiUndoSnapshot();
    const result = await post(`/api/tasks/${button.dataset.id}/${action}`);
    if (task && action !== "toggle-collapse") {
      const labels = { delete: "删除任务", complete: "标记任务完成", increment: "增加任务进度" };
      if (labels[action]) {
        recordOperation(`${labels[action]}：${task.title}`, "task", {
          beforeTask: taskSnapshot(task),
          afterTaskId: action === "delete" ? null : result.task?.id,
          beforeUi,
        });
      }
    }
    await refreshState();
    if (action === "delete") toast("任务已从当前清单删除");
  } catch (error) {
    toast(error.message);
  }
});

elements.showHiddenTasksButton.addEventListener("click", () => {
  const before = captureUiUndoSnapshot();
  showHiddenTasks = !showHiddenTasks;
  if (uiPreferences) uiPreferences.showHiddenTasks = showHiddenTasks;
  recordUiOperation(`${showHiddenTasks ? "显示隐藏任务" : "收起隐藏任务"}`, before);
  saveUiPreferences();
  if (state) renderTasks(state.tasks);
});

elements.clearTasks.addEventListener("click", async () => {
  if (!state?.tasks?.length || clearTasksBusy) return;
  const profile = state.profiles.find((item) => item.id === state.selected_profile_id);
  const profileName = profile?.name || "当前档案";
  const taskCount = state.tasks.length;
  const beforeTasks = state.tasks.map(taskSnapshot);
  const beforeUi = captureUiUndoSnapshot();
  const confirmed = window.confirm(
    `即将清空档案“${profileName}”中的全部 ${taskCount} 个任务，包括已完成任务和当前筛选隐藏的任务，以及关联地图点位。可在处理记录中撤销。确定继续吗？`
  );
  if (!confirmed) return;
  clearTasksBusy = true;
  renderTasks(state.tasks);
  try {
    const result = await post("/api/tasks/clear");
    recordOperation(`清空任务清单：${result.cleared_count} 个任务`, "tasks", { beforeTasks, beforeUi });
    await refreshState();
    await loadMapIndex({ preserveSelection: true });
    toast(`已清空 ${result.cleared_count} 个任务`);
  } catch (error) {
    toast(error.message);
  } finally {
    clearTasksBusy = false;
    if (state) renderTasks(state.tasks);
  }
});

async function handleTaskRequirementChange(event) {
  const checkbox = event.target.closest("input[data-action=\"requirement\"]");
  const counter = event.target.closest("input[data-action=\"requirement-count\"]");
  const input = checkbox || counter;
  if (!input) return;
  const task = state?.tasks?.find((item) => String(item.id) === String(input.dataset.id));
  const beforeTask = taskSnapshot(task);
  const beforeUi = captureUiUndoSnapshot();
  const actionLabel = counter ? "更新任务计数" : "任务要求进度";
  const completed = checkbox?.checked;
  const previousCount = counter?.dataset.previousValue;
  input.disabled = true;
  try {
    let result;
    if (counter) {
      result = await post(`/api/tasks/${counter.dataset.id}/requirements/${counter.dataset.index}/count`, {
        current_count: Number(counter.value),
      });
    } else {
      result = await post(`/api/tasks/${checkbox.dataset.id}/requirements/${checkbox.dataset.index}`, { completed });
    }
    const requirementIndex = Number(input.dataset.index);
    const previousRequirement = beforeTask?.requirements?.[requirementIndex];
    const updatedRequirement = result.task?.requirements?.[requirementIndex];
    const requirementName = formatTaskRequirement(updatedRequirement?.text || previousRequirement?.text);
    let changeDescription;
    if (counter) {
      const oldCount = Number(previousRequirement?.current_count ?? previousCount ?? 0);
      const newCount = Number(updatedRequirement?.current_count ?? counter.value ?? 0);
      const targetCount = Number(updatedRequirement?.target_count ?? previousRequirement?.target_count ?? 0);
      changeDescription = requirementName + "：" + oldCount.toLocaleString("zh-CN") + " → "
        + newCount.toLocaleString("zh-CN") + (targetCount ? " / " + targetCount.toLocaleString("zh-CN") : "");
    } else {
      const isCompleted = updatedRequirement
        ? Boolean(updatedRequirement.completed)
        : Boolean(completed);
      changeDescription = requirementName + " · " + (isCompleted ? "已勾选完成" : "已取消完成勾选");
    }
    if (result.task?.state === "complete") changeDescription += " · 任务已自动完成";
    if (beforeTask) {
      recordOperation(actionLabel + "：" + task.title + " · " + changeDescription, "task", { beforeTask, beforeUi });
    }
    const mapTargetScrollTop = elements.mapTargetList.scrollTop;
    await refreshState();
    if (mapView) {
      renderMapTargets(mapView.markers || [], mapView.tasks || []);
      elements.mapTargetList.scrollTop = mapTargetScrollTop;
    }
    if (result.task?.state === "complete") toast(`${result.task.title} 已自动完成`);
  } catch (error) {
    if (checkbox) checkbox.checked = !completed;
    if (counter) counter.value = previousCount || "0";
    input.disabled = false;
    toast(error.message);
  }
}

elements.rows.addEventListener("change", handleTaskRequirementChange);
elements.mapTargetList.addEventListener("change", handleTaskRequirementChange);
elements.operationHistoryList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-undo-operation-id]");
  if (button) undoOperation(button.dataset.undoOperationId);
});
elements.operationHistoryPanel.addEventListener("toggle", saveUiPreferences);

document.querySelector("#refreshLogsButton").addEventListener("click", refreshLogs);
elements.mobileCompanionButton.addEventListener("click", openMobilePairing);
elements.closeMobilePairingButton.addEventListener("click", closeMobilePairing);
elements.refreshMobilePairingButton.addEventListener("click", generateMobilePairing);
elements.mobilePairingAddress.addEventListener("change", generateMobilePairing);
elements.mobilePairingDialog.addEventListener("close", revokeMobilePairing);
elements.mobilePairingDialog.addEventListener("click", (event) => {
  if (event.target === elements.mobilePairingDialog) closeMobilePairing();
});
elements.mapAnnotationFilters.addEventListener("change", (event) => {
  if (!event.target.matches("input[data-map-annotation-filter]")) return;
  saveUiPreferences();
  renderMapTargets(mapView?.markers || [], mapView?.tasks || []);
});
elements.mapSelect.addEventListener("change", () => {
  setMapDrawingMode(false);
  if (elements.taskMapFilter.value !== elements.mapSelect.value) {
    elements.taskMapFilter.value = elements.mapSelect.value;
  }
  saveUiPreferences();
  if (state) renderTasks(state.tasks);
  renderMapDrawings();
  loadMapView();
});
elements.mapFloorSelect.addEventListener("change", () => {
  if (!elements.mapFloorSelect.value) return;
  if (uiPreferences) {
    uiPreferences.selectedMapFloors[elements.mapSelect.value] = elements.mapFloorSelect.value;
    saveUiPreferences();
  }
  loadMapView(elements.mapFloorSelect.value);
});
elements.mapDrawButton.addEventListener("click", () => setMapDrawingMode(!mapDrawingEnabled));
elements.mapUndoDrawingButton.addEventListener("click", undoMapDrawing);
elements.mapClearDrawingsButton.addEventListener("click", clearMapDrawings);
elements.closeMapPointImageButton.addEventListener("click", () => elements.mapPointImageDialog.close());
elements.mapPointImageDialog.addEventListener("click", (event) => {
  if (event.target === elements.mapPointImageDialog) elements.mapPointImageDialog.close();
});
elements.mapZoomOutButton.addEventListener("click", () => setMapZoom(mapZoom - MAP_ZOOM_STEP));
elements.mapZoomInButton.addEventListener("click", () => setMapZoom(mapZoom + MAP_ZOOM_STEP));
elements.mapZoomResetButton.addEventListener("click", () => setMapZoom(1));
elements.mapFullscreenButton.addEventListener("click", toggleMapFullscreen);
elements.mapImageFrame.addEventListener("pointerdown", (event) => {
  if (mapDrawingEnabled) startMapDrawing(event);
  else startMapPan(event);
});
elements.mapImageFrame.addEventListener("pointermove", (event) => {
  if (activeMapDrawing) moveMapDrawing(event);
  else moveMapPan(event);
});
elements.mapImageFrame.addEventListener("pointerup", (event) => {
  endMapDrawing(event);
  endMapPan(event);
});
elements.mapImageFrame.addEventListener("pointercancel", (event) => {
  endMapDrawing(event, false);
  endMapPan(event);
});
elements.mapImageFrame.addEventListener("lostpointercapture", (event) => {
  endMapDrawing(event, false);
  endMapPan(event);
});
elements.mapImageFrame.addEventListener("wheel", (event) => {
  if (!event.ctrlKey) return;
  event.preventDefault();
  setMapZoom(mapZoom + (event.deltaY < 0 ? 0.1 : -0.1));
}, { passive: false });
document.addEventListener("fullscreenchange", syncMapFullscreenButton);
elements.taskTraderFilter.addEventListener("change", () => {
  saveUiPreferences();
  if (state) renderTasks(state.tasks);
});
elements.taskMapFilter.addEventListener("change", () => {
  const selectedMapId = elements.taskMapFilter.value;
  if (selectedMapId && elements.mapSelect.value !== selectedMapId) {
    elements.mapSelect.value = selectedMapId;
    setMapDrawingMode(false);
    renderMapDrawings();
    loadMapView();
  }
  saveUiPreferences();
  if (state) renderTasks(state.tasks);
});
elements.hideoutPlannerToggle.addEventListener("click", () => {
  setHideoutSectionsOpen(elements.hideoutPlannerContent.hidden);
});
elements.hideoutMaterialsPanel.addEventListener("toggle", () => {
  const plannerOpen = !elements.hideoutPlannerContent.hidden;
  if (plannerOpen !== elements.hideoutMaterialsPanel.open) {
    setHideoutSectionsOpen(elements.hideoutMaterialsPanel.open);
    return;
  }
  saveUiPreferences();
  syncHideoutMaterialsLayout();
});
elements.hideoutLevelsResetButton.addEventListener("click", () => {
  if (!uiPreferences) return;
  const before = captureUiUndoSnapshot();
  uiPreferences.hideoutPlan = {};
  recordUiOperation("清零藏身处等级", before);
  saveUiPreferences();
  renderHideoutPlanner();
});
elements.keySummaryRows.addEventListener("change", (event) => {
  const checkbox = event.target.closest("input[data-key-id]");
  if (!checkbox) return;
  const before = captureUiUndoSnapshot();
  if (checkbox.checked) hiddenKeyIds.delete(checkbox.dataset.keyId);
  else hiddenKeyIds.add(checkbox.dataset.keyId);
  const key = keySummaryEntries.find((entry) => entry.id === checkbox.dataset.keyId);
  recordUiOperation("钥匙状态：" + (key?.name || "钥匙") + " · "
    + (checkbox.checked ? "显示关联任务和地图点位" : "隐藏关联任务和地图点位"), before);
  saveUiPreferences();
  if (state) renderTasks(state.tasks);
  renderMapTargets(mapView?.markers || [], mapView?.tasks || []);
});
elements.keySummaryRows.addEventListener("click", (event) => {
  const newBadge = event.target.closest("button[data-dismiss-new-key]");
  if (!newBadge || !uiPreferences) return;
  event.preventDefault();
  event.stopPropagation();
  const before = captureUiUndoSnapshot();
  const keyId = newBadge.dataset.dismissNewKey;
  const keyName = keySummaryEntries.find((entry) => entry.id === keyId)?.name || "钥匙";
  uiPreferences.newKeyIds = uiPreferences.newKeyIds.filter((currentId) => currentId !== keyId);
  recordUiOperation("钥匙状态：" + keyName + " · 移除新钥匙标记", before);
  saveUiPreferences();
  newBadge.remove();
});
elements.keyOwnershipYesButton.addEventListener("click", () => answerKeyOwnership(true));
elements.keyOwnershipNoButton.addEventListener("click", () => answerKeyOwnership(false));
elements.keyOwnershipLaterButton.addEventListener("click", deferKeyOwnershipQuestion);
elements.keyOwnershipDialog.addEventListener("close", () => {
  if (activeKeyOwnershipId) {
    deferredKeyOwnershipIds.add(activeKeyOwnershipId);
    activeKeyOwnershipId = "";
  }
  showNextKeyOwnershipPrompt();
});
document.querySelector(".quick-nav-menu").addEventListener("click", (event) => {
  if (event.target.closest("a[href^='#']")) document.querySelector(".quick-nav").open = false;
});
elements.hideoutRefreshButton.addEventListener("click", () => loadHideoutCatalog(true));
elements.hideoutMaterialsResetButton.addEventListener("click", () => {
  if (!uiPreferences) return;
  const before = captureUiUndoSnapshot();
  uiPreferences.hideoutOwnedMaterials = {};
  const materialInputs = [...elements.hideoutMaterials.querySelectorAll("input[data-material-key]")];
  const clearedMaterialCount = materialInputs.filter((input) => Number(input.value) > 0).length;
  for (const input of materialInputs) {
    input.value = "0";
  }
  recordUiOperation("清空已有物品数量：" + clearedMaterialCount + " 种材料", before);
  saveUiPreferences();
  updateHideoutMaterialSummary();
});
elements.hideoutMaterials.addEventListener("focusin", (event) => {
  const input = event.target.closest("input[data-material-key]");
  if (!input || !uiPreferences) return;
  input.dataset.undoBefore = JSON.stringify(captureUiUndoSnapshot());
});
elements.hideoutMaterials.addEventListener("change", (event) => {
  const input = event.target.closest("input[data-material-key]");
  if (!input || !uiPreferences || !input.dataset.undoBefore) return;
  try {
    const before = JSON.parse(input.dataset.undoBefore);
    const materialRow = input.closest("li");
    const materialName = materialRow?.querySelector(".hideout-material-name")?.textContent || "藏身处物品";
    const previousCount = Number(before.hideoutOwnedMaterials?.[input.dataset.materialKey] || 0);
    const currentCount = Number(input.value) || 0;
    const currencySymbol = { rubles: "₽", euros: "€", dollars: "$" }[materialRow?.dataset.currency];
    const formatCount = (count) => currencySymbol
      ? currencySymbol + count.toLocaleString("zh-CN")
      : count.toLocaleString("zh-CN") + " 件";
    recordUiOperation("更新已有物品数量：" + materialName + " · " + formatCount(previousCount)
      + " → " + formatCount(currentCount), before);
  } catch {
    input.dataset.undoBefore = "";
  }
  delete input.dataset.undoBefore;
});
elements.hideoutMaterials.addEventListener("input", (event) => {
  const input = event.target.closest("input[data-material-key]");
  if (!input || !uiPreferences) return;
  const ownedCount = Math.min(1000000, Math.max(0, Math.floor(Number(input.value) || 0)));
  uiPreferences.hideoutOwnedMaterials[input.dataset.materialKey] = ownedCount;
  saveUiPreferences();
  updateHideoutMaterialSummary();
});
elements.hideoutStations.addEventListener("change", (event) => {
  const checkbox = event.target.closest("input[data-station-id]");
  if (checkbox) {
    updateHideoutPlan(checkbox.dataset.stationId, { enabled: checkbox.checked });
    return;
  }
  const select = event.target.closest("select[data-station-id][data-level-kind]");
  if (!select || !hideoutCatalog) return;
  const station = hideoutCatalog.stations.find((entry) => entry.id === select.dataset.stationId);
  if (!station) return;
  const current = hideoutPlanFor(station);
  if (select.dataset.levelKind === "current") {
    const currentLevel = Number(select.value);
    const upgradeLevels = (station.levels || [])
      .map((level) => Number(level.level))
      .filter((level) => level > currentLevel)
      .sort((left, right) => left - right);
    const targetLevels = [...new Set([currentLevel, ...upgradeLevels])].sort((left, right) => left - right);
    const targetLevel = targetLevels.includes(Number(current.targetLevel))
      ? Number(current.targetLevel)
      : upgradeLevels[0] ?? currentLevel;
    updateHideoutPlan(station.id, { enabled: true, currentLevel, targetLevel });
  } else {
    updateHideoutPlan(station.id, { enabled: true, targetLevel: Number(select.value) });
  }
});
elements.themeToggle.addEventListener("click", () => {
  const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(nextTheme, true);
});
elements.languageToggle.addEventListener("click", () => {
  applyLanguage(currentLanguage === "zh" ? "en" : "zh", true);
});
applyLanguage(safeStorageGet("eft-task-assistant-language") || "zh");
initializeTheme();
setMapZoom(1);
syncMapFullscreenButton();
const hideoutPlannerResizeObserver = new ResizeObserver(syncHideoutMaterialsLayout);
hideoutPlannerResizeObserver.observe(elements.hideoutPlannerPanel);
window.addEventListener("resize", syncHideoutMaterialsLayout, { passive: true });
syncHideoutMaterialsLayout();
initializeLocalApp();
setInterval(() => {
  refreshState();
}, 1500);
setInterval(() => {
  refreshLogs();
}, 7000);
setInterval(scanScreenshotFolder, 2500);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) scanScreenshotFolder();
});
