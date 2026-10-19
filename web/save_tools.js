(() => {
  function record(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function count(value) {
    return Number.isSafeInteger(value) && value >= 0 ? value : null;
  }

  function text(value) {
    return typeof value === "string" ? value.replace(/[\u0000-\u001f\u007f]/g, " ").slice(0, 240) : "";
  }

  function reported(value) {
    return count(value) ?? "未报告";
  }

  function messages(value, depth = 0) {
    if (typeof value === "string") return [text(value)].filter(Boolean);
    if (!value || typeof value !== "object" || depth >= 2) return [];
    return Object.entries(value).slice(0, 8).flatMap(([key, entry]) =>
      messages(entry, depth + 1).map(message => `${text(key)}：${message}`));
  }

  function formatPreload(value) {
    const preload = record(value);
    const cancelled = preload.cancelled === true || (count(preload.cancelled) ?? 0) > 0;
    const paused = preload.paused_budget === true || (count(preload.paused_budget) ?? 0) > 0;
    const phase = cancelled ? "已取消" : paused ? "预算暂停，可继续" : preload.discovering === true
      ? "正在发现资源（总数仍可能增加）" : preload.running === true ? "后台预热中"
        : preload.complete === true ? "本轮处理结束（仅限已发现资源）" : "后台空闲（未确认覆盖完整）";
    return [text(preload.source) ? `来源 ${text(preload.source)}` : "", text(preload.mode) ? `模式 ${text(preload.mode)}` : "",
      preload.scope === "all" ? "范围：所有允许来源" : preload.scope === "current" ? "范围：当前来源" : "",
      phase, `已发现 ${reported(preload.total)}`,
      `缓存已有/命中 ${reported(preload.cached)}`, `本轮完成处理 ${reported(preload.done)}（含缓存命中，非新增下载数）`,
      `本次下载 ${reported(preload.downloaded)}`, `来源拦截 ${reported(preload.blocked)}`,
      `失败 ${reported(preload.failed)}`, `待继续 ${reported(preload.deferred)}`,
      `取消项 ${reported(preload.cancelled_count ?? (typeof preload.cancelled === "number" ? preload.cancelled : undefined))}`]
      .filter(Boolean).join(" · ");
  }

  function formatCoverage(value) {
    if (typeof value === "string") return text(value);
    if (typeof value === "boolean") return value ? "服务已报告覆盖；仍受来源限制及缓存配额约束" : "覆盖尚不完整";
    if (count(value) !== null) return String(value);
    if (!value || typeof value !== "object") return "";
    return Object.entries(value).slice(0, 8).map(([key, entry]) => {
      const detail = typeof entry === "string" ? text(entry) : typeof entry === "boolean" ? (entry ? "是" : "否")
        : count(entry) !== null ? String(entry) : entry && typeof entry === "object" ? "详见各来源状态" : "未报告";
      const labels = { scope_complete: "本轮覆盖完整", all_sources_complete: "所有来源覆盖完整" };
      return `${labels[key] || text(key)}：${detail}`;
    }).join("；");
  }

  function formatCacheStatus(value) {
    const result = record(value);
    const disk = record(result.assets || result.disk || result.cache || result);
    const preload = record(result.preload);
    const bytes = count(disk.bytes ?? disk.total_bytes);
    const perSource = record(preload.per_source);
    const sources = Array.isArray(preload.per_source)
      ? preload.per_source.slice(0, 8).map(entry => formatPreload(entry))
      : Object.entries(perSource).slice(0, 8).map(([source, entry]) => formatPreload({ ...record(entry), source }));
    const coverage = formatCoverage(preload.coverage);
    return [`地图磁盘缓存：${bytes === null ? "未报告" : `${(bytes / 1048576).toFixed(1)} MiB`}`,
      `当前磁盘条目 ${reported(disk.entries ?? disk.count)}`, formatPreload(preload),
      ...sources.map(summary => `各来源：${summary}`), coverage ? `覆盖信息（服务报告）：${coverage}` : "",
      ...messages(result.warnings).map(message => `提示：${message}`),
      ...messages(preload.errors).map(message => `错误：${message}`),
      "本轮结束或完成数等于已发现数，不代表所有来源、全地图下载成功或永久留存。缺失字段显示未报告。"]
      .filter(Boolean).join(" · ");
  }

  function buildPreloadRequest(action, scope = "all", force = false, mapId = "") {
    if (!["start", "resume", "cancel"].includes(action) || !["current", "all"].includes(scope)
      || typeof force !== "boolean") throw new Error("缓存请求字段无效。");
    return { action, scope, force, all_sources: scope === "all", map_id: typeof mapId === "string" ? mapId : "" };
  }

  if (typeof module === "object" && module.exports) module.exports = { formatPreload, formatCacheStatus, buildPreloadRequest };
  if (typeof document === "undefined") return;
  const panel = document.getElementById("saveDataPanel");
  const status = document.getElementById("saveDataStatus");
  const list = document.getElementById("saveDatasetList");
  const cacheStatus = document.getElementById("mapCacheStatus");
  let busy = false;
  let preloadScope = "all";

  async function call(path, payload) {
    const response = await fetch(path, { cache: "no-store", ...(payload ? {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    } : {}) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `请求失败 ${response.status}`);
    return result;
  }

  async function refreshSaves() {
    const result = await call("/api/save-data");
    const counts = (result.databases || []).map(entry => `${entry.path || entry.relative_path || "数据库"}：${JSON.stringify(entry.table_counts || entry.counts || {})}`);
    status.textContent = [`存档根目录：${result.root}`, result.current_dataset_id ? `当前：${result.current_dataset_id}` : "",
      result.pending_restart ? "已选择另一存档，下次启动生效；本次仍使用原存档。" : "", ...counts].filter(Boolean).join(" · ");
    list.replaceChildren();
    for (const identifier of result.datasets || []) {
      const row = document.createElement("div");
      row.className = "save-dataset-row";
      const label = document.createElement("span");
      label.textContent = identifier + (identifier === result.current_dataset_id ? " · 当前使用" : "")
        + (identifier === result.dataset_id ? " · 下次启动" : "");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button button-secondary button-small";
      button.textContent = "下次启动使用";
      button.disabled = identifier === result.dataset_id;
      button.onclick = () => operate(async () => {
        if (!confirm("选择此独立存档供下次启动使用？当前任务和另一份存档均保留，不合并。")) return;
        await call("/api/save-data/select", { confirmed: true, dataset_id: identifier });
        await refreshSaves();
      });
      row.append(label, button);
      list.append(row);
    }
  }

  async function refreshCache() {
    const result = await call("/api/map/cache");
    if (["current", "all"].includes(result?.preload?.scope)) preloadScope = result.preload.scope;
    cacheStatus.textContent = formatCacheStatus(result);
  }

  async function operate(action) {
    if (busy) return;
    busy = true;
    try { await action(); } catch (error) { status.textContent = error.message; } finally { busy = false; }
  }

  document.getElementById("saveRefreshButton").onclick = () => operate(refreshSaves);
  document.getElementById("saveImportButton").onclick = () => operate(async () => {
    const source = document.getElementById("saveImportPath").value.trim();
    if (!source) throw new Error("请输入要复制的存档根目录的绝对路径。");
    if (!confirm("请先关闭使用来源存档的旧程序。备份并导入为独立存档集？原文件和当前存档均保留。")) return;
    status.textContent = "正在备份并校验独立存档，请勿关闭程序…";
    const result = await call("/api/save-data/import", { confirmed: true, source_root: source });
    await refreshSaves();
    status.textContent += ` · 已导入 ${result.dataset_id}，未切换；请在列表选择下次启动使用的存档。`;
  });
  for (const [identifier, action, scope, force] of [
    ["mapPreloadButton", "start", "current", false], ["mapPreloadAllButton", "start", "all", false],
    ["mapPreloadResumeButton", "resume", null, false], ["mapPreloadRestartButton", "start", null, true],
    ["mapPreloadCancelButton", "cancel", null, false],
  ]) {
    document.getElementById(identifier).onclick = () => operate(async () => {
      try {
        const selectedScope = scope || preloadScope;
        await call("/api/map/cache", buildPreloadRequest(action, selectedScope, force, document.getElementById("mapSelect").value));
        preloadScope = selectedScope;
        await refreshCache();
      } catch (error) {
        cacheStatus.textContent = `缓存操作失败：${error.message}`;
      }
    });
  }
  panel.addEventListener("toggle", () => {
    if (panel.open) operate(async () => { await refreshSaves(); await refreshCache(); });
  });
  setInterval(() => {
    if (panel.open && !busy) operate(refreshCache);
  }, 3000);
})();
