const test = require("node:test");
const assert = require("node:assert/strict");
const { randomUUID } = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const Sync = require("../web/preference_sync.js");
const RouteTools = require("../web/route_tools.js");
const source = fs.readFileSync(path.join(__dirname, "../web/app.js"), "utf8");

function appFunction(name) {
  const match = new RegExp("^(?:async )?function " + name + "\\(", "m").exec(source);
  assert.ok(match, name);
  const remainder = source.slice(match.index);
  const next = /\n(?:async )?function \w+\(/.exec(remainder);
  return next ? remainder.slice(0, next.index) : remainder;
}

function memoryStorage() {
  const entries = new Map();
  return {
    get length() { return entries.size; },
    getItem: key => entries.get(key) ?? null,
    setItem: (key, value) => entries.set(key, String(value)),
    key: index => [...entries.keys()][index] ?? null,
  };
}

function uiHarness(storage = memoryStorage()) {
  let runtime;
  let routesOffline = false;
  const network = [];
  const queued = [];
  const renders = [];
  const preferences = new Map();
  const context = vm.createContext({
    localStorage: storage, EftRouteTools: RouteTools, crypto: { randomUUID }, URLSearchParams,
    AbortController, UI_PREFERENCE_VERSION: 1, UI_PREFERENCE_STORAGE_PREFIX: Sync.STORAGE_PREFIX,
    OPERATION_HISTORY_LIMIT: 40, MAP_ZOOM_MIN: 0.5, MAP_ZOOM_MAX: 3,
    MAP_DRAWING_MAX_STROKES_PER_MAP: 40, MAP_DRAWING_MAX_POINTS_PER_STROKE: 1000, MAP_DRAWING_MAX_POINTS_TOTAL: 12000,
    state: null, uiPreferenceScopeId: null, uiPreferenceDatasetScopeId: null, uiPreferences: null,
    uiPreferenceActivationGeneration: 0, restoringUiPreferences: false,
    keyOwnershipPromptTimer: null, keyOwnershipAnswerTimer: null, activeKeyOwnershipId: "",
    deferredKeyOwnershipIds: new Set(), mapView: null, mapViewGeneration: 0, activeMapDrawing: null,
    routeStates: new Map(), routeFlushRunning: false, routeReadError: "", hideoutCatalog: null, hideoutLoading: true,
    selectedCatalogTask: null, loadedCaptureId: null,
    elements: { keyOwnershipDialog: { open: false }, dataSourceSelect: {}, dataSourceNotice: {},
      catalogPreview: {}, catalogResults: { replaceChildren() {} }, analysis: {}, mapSelect: { value: "customs" } },
    clearTimeout() {}, queueMicrotask: callback => queued.push(callback),
    cloneUndoValue: Sync.clone, safeStorageGet: key => storage.getItem(key),
    renderPreferenceSyncStatus() {}, renderTasks: () => renders.push("tasks"),
    renderHideoutPlanner() {}, renderMapDrawings() {}, updateMapDrawingButtons() {}, toast() {},
    activateScreenshotFolder: async () => {}, setConnection() {}, renderProfiles() {}, openInitialProfileNameDialog() {},
    renderCaptureHistory() {}, renderAnalysis() {}, renderScreenshotCandidates() {}, renderCatalogSummary() {},
    loadMapIndex: async () => {}, clearScreenshotPreview() {},
  });
  context.applyActiveUiPreferences = value => {
    context.uiPreferences = value;
    context.routeStates.clear();
  };
  context.saveUiPreferences = () => {
    if (context.uiPreferences && !context.restoringUiPreferences) {
      context.preferenceClient.update(context.uiPreferenceScopeId, context.uiPreferences);
    }
  };
  context.request = async url => {
    network.push({ url, runtime: Sync.clone(runtime) });
    if (url === "/api/save-data") return Sync.clone(runtime);
    if (url === "/api/state") return { player: { id: "player", is_admin: true }, selected_profile_id: 1,
      tasks: [], data_source: "tarkov.dev", profiles: [], capture: { available: false } };
    if (url.startsWith("/api/map/drawings?")) {
      if (routesOffline) throw new Error("offline");
      return { revision: 1, strokes: [] };
    }
    throw new Error("Unexpected request: " + url);
  };
  context.post = async (url, payload) => {
    network.push({ url, payload: Sync.clone(payload), runtime: Sync.clone(runtime) });
    return { revision: 2, strokes: [payload.stroke] };
  };
  context.PreferenceSync = { createClient(options) {
    const client = Sync.createClient({ ...options, uuid: randomUUID, setTimeout: () => randomUUID(), clearTimeout() {},
      fetch: async (url, settings) => {
        network.push({ url, payload: settings.body ? JSON.parse(settings.body) : null, runtime: Sync.clone(runtime) });
        const key = JSON.stringify([runtime.root, runtime.dataset_id]);
        const remote = preferences.get(key) || { profile_id: 1, revision: 1,
          data: { version: 1, keyOwnershipAnswers: { serverKey: true } }, conflicts: [] };
        if (settings.body) {
          remote.data = JSON.parse(settings.body).data;
          remote.revision += 1;
          preferences.set(key, remote);
        }
        return { ok: true, json: async () => Sync.clone(remote) };
      } });
    context.preferenceClient = client;
    context.applyCallback = options.onApply;
    return client;
  } };
  for (const name of ["defaultUiPreferences", "sanitizeMapDrawings", "readUiPreferences", "taskSnapshot",
    "datasetUiPreferenceScope", "profileUiPreferenceScope", "activateProfileUiPreferences", "activeTaskIdSignature",
    "refreshStateOnce", "routeOperationKey", "currentRouteScope", "currentMapDrawingId", "mapDrawingStrokes",
    "cacheRouteResponse", "readMapRoutes", "queueRouteOperation", "flushRouteOperations"]) {
    vm.runInContext(appFunction(name), context);
  }
  vm.runInContext(source.slice(source.indexOf("const preferenceSync ="), source.indexOf("let hideoutCatalog =")), context);
  return { context, storage, network, queued, renders,
    setRuntime: value => { runtime = value; }, offlineRoutes: value => { routesOffline = value; } };
}

const datasetA = { status: "ready", root: "E:\\save-A", dataset_id: "copied-uuid" };
const routeScope = { source: "tarkov.dev", map_id: "customs", floor_key: "main" };
const stroke = { id: "stroke-A", color: "#e5484d", width: 4, points: [[0, 0], [1, 1]] };

for (const datasetB of [
  { status: "ready", root: "E:\\save-B", dataset_id: "copied-uuid" },
  { status: "ready", root: datasetA.root, dataset_id: "other-dataset" },
]) {
  test(`offline route append stays with its dataset across switches and browser restart: ${datasetB.root}/${datasetB.dataset_id}`, async () => {
    const setup = uiHarness();
    setup.setRuntime(datasetA);
    await setup.context.refreshStateOnce();
    const scopeA = setup.context.uiPreferenceScopeId;
    assert.equal(setup.network[0].url, "/api/save-data");
    assert.equal(setup.network[1].url, "/api/state");
    assert.equal(setup.context.queueRouteOperation("append", routeScope, { stroke }), true);
    setup.offlineRoutes(true);
    await setup.context.flushRouteOperations();
    assert.equal(setup.context.uiPreferences.routePendingOperations.length, 1);
    const rawA = setup.storage.getItem(Sync.STORAGE_PREFIX + scopeA);
    setup.setRuntime(datasetB);
    setup.offlineRoutes(false);
    await setup.context.refreshStateOnce();
    assert.notEqual(setup.context.uiPreferenceScopeId, scopeA);
    assert.deepEqual(Sync.clone(setup.context.uiPreferences.routePendingOperations), []);
    assert.deepEqual(Sync.clone(setup.context.uiPreferences.routeCaches), {});
    await setup.context.flushRouteOperations();
    for (const callback of setup.queued) await callback();
    assert.equal(setup.network.filter(call => call.payload).length, 0);
    assert.equal(setup.storage.getItem(Sync.STORAGE_PREFIX + scopeA), rawA);
    const restarted = uiHarness(setup.storage);
    restarted.setRuntime(datasetA);
    await restarted.context.refreshStateOnce();
    assert.equal(restarted.context.uiPreferenceScopeId, scopeA);
    assert.equal(restarted.context.uiPreferences.routePendingOperations.length, 1);
    assert.equal(restarted.context.uiPreferences.routePendingOperations[0].stroke.id, "stroke-A");
    await restarted.context.flushRouteOperations();
    const posts = restarted.network.filter(call => call.payload && call.url === "/api/map/drawings");
    assert.equal(posts.length, 1);
    assert.equal(posts[0].url, "/api/map/drawings");
    assert.deepEqual(posts[0].runtime, datasetA);
  });
}

test("dataset identity requires root and dataset and follows the running dataset while restart is pending", () => {
  const setup = uiHarness();
  for (const value of [null, { status: "empty", root: "E:\\save" }, { status: "ready", dataset_id: "id" },
    { status: "ready", root: "E:\\save" }]) assert.throws(() => setup.context.datasetUiPreferenceScope(value), /无法确认/);
  const running = setup.context.datasetUiPreferenceScope(datasetA);
  assert.equal(setup.context.datasetUiPreferenceScope({ ...datasetA, dataset_id: "selected-new",
    current_dataset_id: datasetA.dataset_id, pending_restart: true }), running);
  assert.notEqual(setup.context.datasetUiPreferenceScope({ status: "unmanaged", root: datasetA.root }), running);
});

test("refresh without dataset identity loads no browser preferences and cannot flush a previous dataset queue", async () => {
  const setup = uiHarness();
  setup.setRuntime(datasetA);
  await setup.context.refreshStateOnce();
  setup.context.queueRouteOperation("append", routeScope, { stroke });
  const previousScope = setup.context.uiPreferenceScopeId;
  setup.setRuntime({ status: "empty", root: datasetA.root });
  await setup.context.refreshStateOnce();
  await setup.context.flushRouteOperations();
  assert.equal(setup.context.uiPreferences, null);
  assert.equal(setup.context.uiPreferenceScopeId, null);
  assert.equal(setup.context.preferenceClient.getState(), null);
  assert.equal(setup.network.filter(call => call.payload).length, 0);
  assert.equal(JSON.parse(setup.storage.getItem(Sync.STORAGE_PREFIX + previousScope)).routePendingOperations.length, 1);
});

test("onApply and unchanged-profile refresh use the complete scope and ignore old-dataset callbacks", async () => {
  const setup = uiHarness();
  setup.setRuntime(datasetA);
  await setup.context.refreshStateOnce();
  const scopeA = setup.context.uiPreferenceScopeId;
  setup.context.applyCallback(Sync.clone(setup.context.uiPreferences), scopeA);
  assert.equal(setup.renders.length, 1);
  await Promise.resolve();
  await setup.context.refreshStateOnce();
  assert.equal(setup.context.uiPreferenceScopeId, scopeA);
  setup.setRuntime({ ...datasetA, root: "E:\\other-root" });
  await setup.context.refreshStateOnce();
  setup.context.applyCallback({ version: 1, keyOwnershipAnswers: { oldDataset: true } }, scopeA);
  assert.deepEqual(Sync.clone(setup.context.uiPreferences.keyOwnershipAnswers), { serverKey: true });
});

test("app snapshots and old local history retain requirements progress and provenance but remove derived fields", async () => {
  const setup = uiHarness();
  const task = { id: 12, profile_id: 1, title: "任务", trader: "Prapor", objective: "说明", item_name: "物品",
    current_count: 2, required_count: 5, state: "active", source_task_id: "native", source_url: "https://example.invalid",
    source_version: "v1", requirements: [{ text: "保留要求", completed: false, optional: true, target_count: 5, current_count: 2 }],
    data_provider: "tarkov.dev", key_requirements: [{ id: "derived" }] };
  const expected = Sync.taskSnapshot(task);
  assert.deepEqual(Sync.clone(setup.context.taskSnapshot(task)), expected);
  const parsed = setup.context.readUiPreferences("unused", null, { version: 1, operationHistory: [
    { id: "single", label: "勾选要求", type: "task", data: { beforeTask: task } },
    { id: "many", label: "导入", type: "tasks", data: { beforeTasks: [task] } },
  ] });
  assert.deepEqual(Sync.clone(parsed.operationHistory[0].data.beforeTask), expected);
  assert.deepEqual(Sync.clone(parsed.operationHistory[1].data.beforeTasks), [expected]);
  assert.equal(task.data_provider, "tarkov.dev");
});

test("undo restores old single and bulk task histories using only allowed snapshot fields", async () => {
  const setup = uiHarness();
  setup.setRuntime(datasetA);
  setup.context.operationUndoBusy = false;
  setup.context.renderOperationHistory = () => {};
  setup.context.refreshState = async () => {};
  setup.context.saveUiPreferences = () => {};
  setup.context.operationHistoryLabel = entry => entry.label;
  for (const name of ["mostRecentUndoableOperation", "undoOperation"]) vm.runInContext(appFunction(name), setup.context);
  const task = { id: 12, current_count: 2, source_task_id: "native", source_version: "v1",
    requirements: [{ text: "保留要求", completed: false, target_count: 5, current_count: 2 }],
    data_provider: "tarkov.dev", key_requirements: [{ id: "derived" }] };
  for (const type of ["task", "tasks"]) {
    const entry = { id: type, label: "撤销", type,
      data: type === "task" ? { beforeTask: task } : { beforeTasks: [task] } };
    setup.context.uiPreferences = { operationHistory: [entry] };
    await setup.context.undoOperation(type);
    assert.equal(entry.undone, true);
    assert.equal(setup.network.at(-1).url, "/api/tasks/restore");
    assert.deepEqual(setup.network.at(-1).payload.tasks, [Sync.taskSnapshot(task)]);
  }
  assert.equal(task.data_provider, "tarkov.dev");
});
