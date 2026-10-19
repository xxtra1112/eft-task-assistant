const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const Sync = require("../web/preference_sync.js");
const { randomUUID } = require("node:crypto");
const source = fs.readFileSync(path.join(__dirname, "../web/app.js"), "utf8");

function appFunction(name) {
  const match = new RegExp("^(?:async )?function " + name + "\\(", "m").exec(source);
  assert.ok(match);
  const rest = source.slice(match.index);
  const end = /\n(?:async )?function \w+\(/.exec(rest);
  return end ? rest.slice(0, end.index) : rest;
}

test("desktop mutation binds the Unicode dataset scope without changing GET requests", async () => {
  const calls = [];
  const context = vm.createContext({ uiPreferenceDatasetScopeId: 'dataset-v1:["C:\\玩家\\存档","A"]',
    fetch: async (url, options) => {
      calls.push({ url, options });
      return { ok: true, headers: { get: () => "application/json" }, json: async () => ({ ok: true }) };
    } });
  vm.runInContext(appFunction("request"), context);
  await context.request("/api/profiles/name", { method: "POST", body: '{}' });
  assert.equal(decodeURIComponent(calls[0].options.headers["X-EFT-Save-Scope"]), context.uiPreferenceDatasetScopeId);
  assert.equal(calls[0].options.headers["Content-Type"], "application/json");
  await context.request("/api/state");
  assert.equal(calls[1].options.headers["X-EFT-Save-Scope"], undefined);
});

test("explicit mutation owner scope wins over a later active dataset", async () => {
  let captured;
  const context = vm.createContext({ uiPreferenceDatasetScopeId: "dataset-B", mapView: null, state: {},
    request: async (_url, options) => { captured = options; return {}; } });
  vm.runInContext(appFunction("post"), context);
  await context.post("/api/map/drawings", { operation: "append" }, "dataset-A");
  assert.equal(decodeURIComponent(captured.headers["X-EFT-Save-Scope"]), "dataset-A");
});

test("route flush captures its dataset before asynchronous revision reads", async () => {
  const captures = [];
  const context = vm.createContext({
    routeFlushRunning: false, uiPreferenceScopeId: "owner-A", uiPreferenceDatasetScopeId: "dataset-A",
    uiPreferences: { routePendingOperations: [{ operation_id: "op", operation: "append", source: "tarkov.dev", profile_id: 1 }] },
    state: { data_source: "tarkov.dev", selected_profile_id: 1 }, mapView: {}, activeMapDrawing: false,
    routeOperationKey: () => "map", saveUiPreferences() {}, renderMapDrawings() {}, cacheRouteResponse() {},
    post: async (_url, _payload, scope) => { captures.push(scope); return { revision: 2, strokes: [] }; },
  });
  context.readMapRoutes = async () => {
    context.uiPreferenceDatasetScopeId = "dataset-B";
    return { revision: 1, strokes: [] };
  };
  vm.runInContext(appFunction("flushRouteOperations"), context);
  await context.flushRouteOperations();
  assert.deepEqual(captures, ["dataset-A"]);
});

test("shared preference writes carry their owning session scope", async () => {
  const storage = new Map();
  const writes = [];
  const scope = 'dataset-v1:["C:\\玩家","dataset-A"]';
  let revision = 1;
  let remote = { version: 1 };
  const client = Sync.createClient({ storage: { getItem: key => storage.get(key) || null,
    setItem: (key, value) => storage.set(key, value), key: index => [...storage.keys()][index],
    get length() { return storage.size; } }, uuid: randomUUID,
    setTimeout: () => "timer", clearTimeout() {},
    fetch: async (_url, options) => {
      if (options.body) {
        writes.push(options.headers);
        remote = JSON.parse(options.body).data;
        revision += 1;
      }
      return { ok: true, status: 200, json: async () => ({ profile_id: 1, revision, data: remote, conflicts: [] }) };
    } });
  await client.activate({ scopeId: "local-A", profileId: 1, datasetScopeId: scope, defaults: { version: 1 } });
  client.update("local-A", { version: 1, hiddenTaskIds: ["task"] });
  await client.flush();
  assert.equal(writes.length, 1);
  assert.equal(decodeURIComponent(writes[0]["X-EFT-Save-Scope"]), scope);
});

test("screenshot upload captures scope before asynchronous image encoding", async () => {
  let captured;
  const image = { size: 100 };
  const context = vm.createContext({ uiPreferenceDatasetScopeId: "dataset-A",
    fetch: async (_url, options) => {
      captured = options;
      return { ok: true, headers: { get: () => "application/json" }, json: async () => ({ accepted: true }) };
    } });
  context.encodeScreenshotAsJpeg = async () => {
    context.uiPreferenceDatasetScopeId = "dataset-B";
    return image;
  };
  vm.runInContext(appFunction("uploadScreenshotFile"), context);
  await context.uploadScreenshotFile({});
  assert.equal(decodeURIComponent(captured.headers["X-EFT-Save-Scope"]), "dataset-A");
  assert.equal(captured.headers["Content-Type"], "image/jpeg");
  assert.equal(captured.body, image);
});
