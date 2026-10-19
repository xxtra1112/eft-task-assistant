const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const tools = require("../web/save_tools.js");

function browser(cache = {}) {
  const elements = new Map();
  const requests = [];
  const document = {
    getElementById(identifier) {
      if (!elements.has(identifier)) elements.set(identifier, {
        textContent: "", value: "factory", open: false,
        addEventListener() {},
        set innerHTML(value) { throw new Error(`Unexpected HTML rendering: ${value}`); },
      });
      return elements.get(identifier);
    },
  };
  const context = vm.createContext({
    document, setInterval() {}, confirm: () => true,
    async fetch(url, options) {
      const payload = options.body ? JSON.parse(options.body) : null;
      requests.push({ url, payload });
      return { ok: !cache.error, status: cache.error ? 403 : 200, json: async () => cache };
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../web/save_tools.js"), "utf8"), context);
  return { elements, requests, click: identifier => elements.get(identifier).onclick() };
}

test("legacy done/total never imply new downloads or complete map coverage", () => {
  const summary = tools.formatCacheStatus({ preload: {
    source: "reemr", mode: "pve", total: 5, done: 5, failed: 0,
    running: false, discovering: false, cancelled: false, errors: {},
  } });
  assert.match(summary, /来源 reemr/);
  assert.match(summary, /已发现 5/);
  assert.match(summary, /本轮完成处理 5（含缓存命中，非新增下载数）/);
  assert.match(summary, /本次下载 未报告/);
  assert.match(summary, /缓存已有\/命中 未报告/);
  assert.match(summary, /未确认覆盖完整/);
  assert.match(summary, /不代表所有来源、全地图下载成功或永久留存/);
  assert.doesNotMatch(summary, /全部成功|全部下载完成|100%/);
});

test("cache hits downloads blocks failures and deferrals remain separate", () => {
  const summary = tools.formatCacheStatus({ assets: { bytes: 1048576, entries: 3 }, preload: {
    total: 20, done: 9, cached: 6, downloaded: 3, blocked: 7, failed: 1, deferred: 3,
    paused_budget: true, cancelled_count: 0, complete: false,
  } });
  for (const phrase of ["1.0 MiB", "当前磁盘条目 3", "已发现 20", "缓存已有/命中 6",
    "本轮完成处理 9", "本次下载 3", "来源拦截 7", "失败 1", "待继续 3", "预算暂停，可继续", "取消项 0"]) {
    assert.ok(summary.includes(phrase), phrase);
  }
});

test("discovery cancellation budget pauses and reported completion have distinct wording", () => {
  const cases = [
    [{ discovering: true, running: true, total: 0, done: 0 }, /正在发现资源（总数仍可能增加）/],
    [{ running: true }, /后台预热中/],
    [{ cancelled: true, running: true, complete: true }, /已取消/],
    [{ cancelled: 2 }, /已取消.*取消项 2/],
    [{ paused_budget: true, complete: true }, /预算暂停，可继续/],
    [{ complete: true, blocked: 7, failed: 1 }, /本轮处理结束（仅限已发现资源）/],
    [{}, /后台空闲（未确认覆盖完整）/],
  ];
  for (const [preload, expected] of cases) assert.match(tools.formatPreload(preload), expected);
});

test("zero stays zero while absent malformed and unsafe counters are unreported", () => {
  const zero = tools.formatCacheStatus({ disk: { bytes: 0, total_bytes: 99, entries: 0, count: 99 }, preload: {
    total: 0, done: 0, failed: 0, cached: 0, downloaded: 0, blocked: 0, deferred: 0,
  } });
  assert.match(zero, /0.0 MiB.*当前磁盘条目 0/);
  assert.match(zero, /已发现 0.*本轮完成处理 0/);
  for (const bad of [undefined, null, -1, 1.5, Infinity, NaN, Number.MAX_SAFE_INTEGER + 1, "8", true, {}, []]) {
    const summary = tools.formatCacheStatus({ assets: { bytes: bad, entries: bad }, preload: {
      total: bad, done: bad, failed: bad, downloaded: bad, cached: bad, blocked: bad, deferred: bad,
    } });
    assert.match(summary, /地图磁盘缓存：未报告.*当前磁盘条目 未报告/);
    assert.match(summary, /已发现 未报告.*本轮完成处理 未报告/);
    assert.doesNotMatch(summary, /NaN|Infinity|\[object Object\]/);
  }
  assert.match(tools.formatPreload({ cancelled: "true", paused_budget: "true", complete: "true", running: "true" }), /后台空闲/);
});

test("null or unexpected response shapes and error containers do not break formatting", () => {
  for (const value of [null, undefined, false, "bad", [], { assets: [], preload: null },
    { preload: { errors: 42, per_source: [null, "bad"], coverage: null }, warnings: true }]) {
    assert.doesNotThrow(() => tools.formatCacheStatus(value));
    assert.doesNotMatch(tools.formatCacheStatus(value), /undefined|NaN|\[object Object\]/);
  }
  const summary = tools.formatCacheStatus({ warnings: ["离线回退"], preload: { errors: { reemr: "robots 拒绝" } } });
  assert.match(summary, /提示：0：离线回退/);
  assert.match(summary, /错误：reemr：robots 拒绝/);
});

test("per-source and coverage reports retain source-specific limitations", () => {
  const summary = tools.formatCacheStatus({ preload: {
    per_source: { reemr: { total: 10, downloaded: 3, blocked: 7 }, "tarkov.dev": { total: 2, cached: 2 } },
    coverage: { complete: false, allowed_sources: 3 },
  } });
  assert.match(summary, /各来源：来源 reemr.*已发现 10.*本次下载 3.*来源拦截 7/);
  assert.match(summary, /各来源：来源 tarkov.dev.*缓存已有\/命中 2/);
  assert.match(summary, /覆盖信息（服务报告）：complete：否；allowed_sources：3/);
  assert.match(tools.formatCacheStatus({ preload: { per_source: [{ source: "eftarkov", failed: 1 }], coverage: false } }),
    /各来源：来源 eftarkov.*失败 1.*覆盖尚不完整/);
});

test("status text bounds unexpected strings and does not coerce objects", () => {
  const explosive = { toString() { throw new Error("Unsafe conversion"); } };
  const summary = tools.formatCacheStatus({ warnings: explosive, preload: {
    source: explosive, mode: "pve\nmode", errors: { request: "x".repeat(100000) },
    coverage: { source: explosive },
  } });
  assert.ok(summary.length < 2000);
  assert.match(summary, /模式 pve mode/);
  assert.doesNotMatch(summary, /\[object Object\]/);
});

test("requests default to all allowed sources and reject unsupported fields", () => {
  assert.deepEqual(tools.buildPreloadRequest("resume"), {
    action: "resume", scope: "all", force: false, all_sources: true, map_id: "",
  });
  assert.deepEqual(tools.buildPreloadRequest("start", "current", true, "factory"), {
    action: "start", scope: "current", force: true, all_sources: false, map_id: "factory",
  });
  assert.throws(() => tools.buildPreloadRequest("delete"));
  assert.throws(() => tools.buildPreloadRequest("start", "reemr"));
  assert.throws(() => tools.buildPreloadRequest("start", "all", "true"));
});

test("all five desktop buttons exist and send scope force and compatibility fields", async () => {
  const desktop = browser();
  const html = fs.readFileSync(path.join(__dirname, "../web/index.html"), "utf8");
  const sequence = [
    ["mapPreloadResumeButton", "resume", "all", false],
    ["mapPreloadButton", "start", "current", false],
    ["mapPreloadRestartButton", "start", "current", true],
    ["mapPreloadCancelButton", "cancel", "current", false],
    ["mapPreloadAllButton", "start", "all", false],
    ["mapPreloadRestartButton", "start", "all", true],
  ];
  for (const [identifier, action, scope, force] of sequence) {
    assert.ok(html.includes(`id="${identifier}"`));
    await desktop.click(identifier);
    const request = desktop.requests.at(-2);
    assert.equal(request.url, "/api/map/cache");
    assert.deepEqual(request.payload, { action, scope, force, all_sources: scope === "all", map_id: "factory" });
    assert.deepEqual(desktop.requests.at(-1), { url: "/api/map/cache", payload: null });
  }
});

test("resume adopts the server-reported scope and renders source errors only as text", async () => {
  const markup = '<img src=x onerror="throw 1">';
  const desktop = browser({ preload: { scope: "current", source: markup, errors: { request: markup } } });
  await desktop.click("mapPreloadAllButton");
  await desktop.click("mapPreloadResumeButton");
  assert.equal(desktop.requests.at(-2).payload.scope, "current");
  assert.ok(desktop.elements.get("mapCacheStatus").textContent.includes(markup));
});

test("cache request rejection stays visible in the cache status", async () => {
  const desktop = browser({ error: "RE3MR 来源策略拒绝" });
  await desktop.click("mapPreloadAllButton");
  assert.equal(desktop.requests.length, 1);
  assert.equal(desktop.elements.get("mapCacheStatus").textContent, "缓存操作失败：RE3MR 来源策略拒绝");
  assert.equal(desktop.elements.get("saveDataStatus").textContent, "");
});
