const test = require("node:test");
const assert = require("node:assert/strict");
const { randomUUID } = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const Sync = require("../web/preference_sync.js");

function memoryStorage(initial = {}) {
  const entries = new Map(Object.entries(initial));
  return {
    get length() { return entries.size; },
    getItem: key => entries.get(key) ?? null,
    setItem: (key, value) => entries.set(key, String(value)),
    key: index => [...entries.keys()][index] ?? null,
  };
}

function deferred() {
  let resolve;
  const promise = new Promise(complete => { resolve = complete; });
  return { promise, resolve };
}

function response(status, result) {
  return { ok: status >= 200 && status < 300, status, json: async () => Sync.clone(result) };
}

function server(initial = {}) {
  const profiles = new Map(Object.entries(initial).map(([profileId, value]) => [Number(profileId), {
    profile_id: Number(profileId), revision: value.revision ?? 1, data: value.data, conflicts: [],
  }]));
  const calls = [];
  const replays = new Map();
  const backups = new Map();
  function current(profileId) {
    if (!profiles.has(profileId)) profiles.set(profileId, { profile_id: profileId, revision: 0, data: { version: 1 }, conflicts: [] });
    return Sync.clone(profiles.get(profileId));
  }
  async function fetch(url, options = {}) {
    const payload = options.body ? JSON.parse(options.body) : null;
    calls.push({ url, payload });
    const profileId = Number(payload?.profile_id ?? new URL(url, "http://test.invalid").searchParams.get("profile_id"));
    const state = current(profileId);
    if (!payload) return response(200, url.startsWith("/api/preferences/conflicts")
      ? { profile_id: profileId, conflicts: state.conflicts, backups: [...backups.values()] } : state);
    const replayKey = profileId + ":" + payload.operation_id;
    if (replays.has(replayKey)) {
      const previous = replays.get(replayKey);
      assert.deepEqual(payload, previous.payload);
      return response(previous.status, previous.result);
    }
    assert.match(payload.operation_id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    const conflict = state.conflicts.find(entry => entry.id === payload.conflict_id);
    let data = payload.data;
    if (url.endsWith("/resolve")) {
      assert.ok(conflict);
      data = backups.get(payload.choice === "server" ? conflict.server_backup_id : conflict.local_backup_id).data;
    }
    let status = 200;
    let result;
    if (payload.base_revision !== state.revision || (payload.only_if_empty && state.revision > 0)) {
      status = 409;
      const entry = { id: randomUUID(), server_backup_id: randomUUID(), local_backup_id: randomUUID(), resolution: null };
      backups.set(entry.server_backup_id, { backup_id: entry.server_backup_id, data: state.data });
      backups.set(entry.local_backup_id, { backup_id: entry.local_backup_id, data });
      state.conflicts.push(entry);
      profiles.set(profileId, state);
      result = { error: "版本冲突", current: state, conflict_id: entry.id,
        server_backup_id: entry.server_backup_id, local_backup_id: entry.local_backup_id };
    } else {
      state.revision += 1;
      state.data = data;
      if (conflict) conflict.resolution = payload.choice;
      profiles.set(profileId, state);
      result = state;
    }
    replays.set(replayKey, { payload: Sync.clone(payload), status, result: Sync.clone(result) });
    return response(status, result);
  }
  return { fetch, current, profiles, calls, backups, writes: () => calls.filter(call => call.payload) };
}

function harness(service, storage = memoryStorage(), customFetch = null) {
  const timers = new Map();
  const applied = [];
  const statuses = [];
  const client = Sync.createClient({
    storage, uuid: randomUUID, fetch: customFetch || service.fetch,
    onApply: (preferences, scopeId) => applied.push({ preferences, scopeId }),
    onStatus: status => statuses.push(status),
    setTimeout: (callback, delay) => {
      const token = randomUUID();
      timers.set(token, { callback, delay });
      return token;
    },
    clearTimeout: token => timers.delete(token),
  });
  const activate = (profileId = 1, extra = {}) => client.activate({ scopeId: "player:" + profileId, profileId,
    defaults: { version: 1, hiddenKeyIds: [], keyOwnershipAnswers: {}, routePendingOperations: [],
      routeCaches: {}, routeCacheRevisions: {} }, ...extra });
  return { client, storage, activate, applied, statuses, timers };
}

const rawKey = profileId => Sync.STORAGE_PREFIX + "player:" + profileId;

test("whitelist removes local routes recursively without modifying aliases or truncating legacy data", () => {
  const source = { version: 1, hiddenMapTaskIds: ["legacy"], hiddenKeyIds: Array.from({ length: 450 }, (_, index) => "alias-" + index),
    mapDrawings: { customs: Array.from({ length: 80 }, () => [[0, 0], [1, 1]]) },
    routePendingOperations: [{ secret: "queue" }], unknown: "not-whitelisted",
    operationHistory: [{ id: "undo", data: { beforeUi: { hiddenKeyIds: ["alias"], unknown: true,
      routeCaches: { secret: true }, operationHistory: [], routeCacheRevisions: {}, routePendingOperations: [] } } }] };
  const original = Sync.clone(source);
  const shared = Sync.sharedSnapshot(source);
  assert.deepEqual(source, original);
  assert.deepEqual(shared.hiddenMapTaskIds, ["legacy"]);
  assert.equal(shared.hiddenKeyIds.length, 450);
  assert.equal(shared.mapDrawings.customs.length, 80);
  assert.equal(shared.unknown, undefined);
  assert.doesNotMatch(JSON.stringify(shared), /routePendingOperations|routeCaches|routeCacheRevisions|secret/);
  assert.deepEqual(shared.operationHistory[0].data.beforeUi, { hiddenKeyIds: ["alias"] });
});

test("server preferences win before application, including keys and hideout collapse on a new origin", async () => {
  const data = { version: 1, keyFilterInitialized: true, keyOwnershipAnswers: { alias: false },
    hiddenKeyIds: ["alias"], hideoutPlannerOpen: false, hideoutMaterialsOpen: false };
  const service = server({ 1: { revision: 7, data } });
  const setup = harness(service);
  await setup.activate();
  assert.equal(service.writes().length, 0);
  assert.deepEqual(setup.applied[0].preferences.hiddenKeyIds, ["alias"]);
  assert.equal(setup.applied[0].preferences.hideoutPlannerOpen, false);
  assert.equal(setup.client.getState().data.keyFilterInitialized, true);
  assert.match(setup.statuses.at(-1).help, /无法自动互读/);
  assert.match(Sync.MIGRATION_HELP, /copy\(JSON.stringify/);
});

test("first migration uploads the raw snapshot only_if_empty and archives it without truncation", async () => {
  const raw = JSON.stringify({ version: 1, hiddenKeyIds: ["eftarkov:old-key", "tarkov.dev:key"],
    mapDrawings: { customs: Array.from({ length: 75 }, () => [[0, 0], [1, 1]]) },
    routePendingOperations: [{ operation_id: "only-here" }], routeCaches: { old: [] }, routeCacheRevisions: { old: 12 } });
  const storage = memoryStorage({ [rawKey(1)]: raw });
  const service = server();
  const setup = harness(service, storage);
  await setup.activate();
  const payload = service.writes()[0].payload;
  assert.equal(payload.only_if_empty, true);
  assert.equal(payload.base_revision, 0);
  assert.equal(payload.data.mapDrawings.customs.length, 75);
  assert.doesNotMatch(JSON.stringify(payload.data), /routePendingOperations|routeCaches|routeCacheRevisions/);
  assert.equal(setup.client.getState().data.routePendingOperations[0].operation_id, "only-here");
  const exported = setup.client.exportLocal("http://old-port");
  assert.ok(Object.entries(exported.storage).some(([key, value]) => key.startsWith(Sync.BACKUP_PREFIX) && value === raw));
});

test("empty server plus a new origin performs no default upload", async () => {
  const service = server();
  const setup = harness(service);
  await setup.activate();
  assert.equal(service.writes().length, 0);
  assert.equal(setup.statuses.at(-1).kind, "empty");
});

test("legacy numeric profile keys migrate only when the caller explicitly grants a fallback", async () => {
  const key = Sync.STORAGE_PREFIX + "1";
  const raw = JSON.stringify({ version: 1, hiddenMapTaskIds: ["old"] });
  const service = server();
  const storage = memoryStorage({ [key]: raw });
  await harness(service, storage).activate();
  assert.equal(service.writes().length, 0);
  await harness(service, storage).activate(1, { legacyKey: key });
  assert.deepEqual(service.writes()[0].payload.data.hiddenMapTaskIds, ["old"]);
  assert.equal(storage.getItem(key), raw);
});

test("debounced detached updates are serialized and local route cache updates never upload", async () => {
  const service = server({ 1: { data: { version: 1, hiddenKeyIds: [] } } });
  const setup = harness(service);
  await setup.activate();
  const local = setup.client.getState().data;
  local.routeCaches.cache = [[0, 0], [1, 1]];
  setup.client.update("player:1", local);
  await setup.client.flush();
  assert.equal(service.writes().length, 0);
  for (let index = 0; index < 5; index += 1) {
    local.hiddenKeyIds = [String(index)];
    setup.client.update("player:1", local);
  }
  assert.equal([...setup.timers.values()].filter(timer => timer.delay === 450).length, 1);
  local.hiddenKeyIds.push("external mutation");
  await setup.client.flush();
  assert.equal(service.writes().length, 1);
  assert.deepEqual(service.current(1).data.hiddenKeyIds, ["4"]);
});

test("a committed response lost offline replays the exact durable UUID after restart", async () => {
  const service = server({ 1: { data: { version: 1, hiddenKeyIds: [] } } });
  const storage = memoryStorage();
  let failOnce = true;
  const setup = harness(service, storage, async (url, options) => {
    const result = await service.fetch(url, options);
    if (options.body && failOnce) { failOnce = false; throw new Error("offline after commit"); }
    return result;
  });
  await setup.activate();
  setup.client.update("player:1", { ...setup.client.getState().data, hiddenKeyIds: ["mine"] });
  await setup.client.flush();
  const pending = setup.client.getState().pending;
  assert.ok(pending);
  assert.equal(setup.statuses.at(-1).kind, "offline");
  const restarted = harness(service, storage);
  await restarted.activate();
  assert.equal(service.writes().length, 2);
  assert.deepEqual(service.writes()[0].payload, service.writes()[1].payload);
  assert.equal(service.current(1).revision, 2);
  assert.equal(restarted.client.getState().pending, null);
});

test("edits during an inflight save follow with a fresh UUID and returned revision", async () => {
  const service = server({ 1: { data: { version: 1, hiddenKeyIds: [] } } });
  const gate = deferred();
  const started = deferred();
  let waitOnce = true;
  const setup = harness(service, memoryStorage(), async (url, options) => {
    if (options.body && waitOnce) { waitOnce = false; started.resolve(); await gate.promise; }
    return service.fetch(url, options);
  });
  await setup.activate();
  setup.client.update("player:1", { ...setup.client.getState().data, hiddenKeyIds: ["first"] });
  const saving = setup.client.flush();
  await started.promise;
  setup.client.update("player:1", { ...setup.client.getState().data, hiddenKeyIds: ["second"] });
  gate.resolve();
  await saving;
  const writes = service.writes();
  assert.equal(writes.length, 2);
  assert.notEqual(writes[0].payload.operation_id, writes[1].payload.operation_id);
  assert.equal(writes[1].payload.base_revision, 2);
  assert.deepEqual(service.current(1).data.hiddenKeyIds, ["second"]);
});

test("late activation and queued flush cannot apply to a different scope", async () => {
  const service = server({ 1: { data: { version: 1, hiddenKeyIds: ["one"] } }, 2: { data: { version: 1, hiddenKeyIds: ["two"] } } });
  const gate = deferred();
  const started = deferred();
  const setup = harness(service, memoryStorage(), async (url, options) => {
    if (url.endsWith("profile_id=1")) { started.resolve(); await gate.promise; }
    return service.fetch(url, options);
  });
  const first = setup.activate(1);
  await started.promise;
  await setup.activate(2);
  gate.resolve();
  await first;
  assert.deepEqual(setup.applied.map(entry => entry.scopeId), ["player:2"]);
  assert.equal(setup.client.update("player:1", { version: 1, hiddenKeyIds: ["wrong"] }), false);
  assert.equal(setup.client.getState().scope_id, "player:2");
});

for (const choice of ["server", "local"]) {
  test(`409 pauses saves, exports both backups and resolves ${choice} with a fresh UUID`, async () => {
    const service = server({ 1: { data: { version: 1, hiddenKeyIds: ["original"] } } });
    const setup = harness(service);
    await setup.activate();
    const local = { ...setup.client.getState().data, hiddenKeyIds: ["browser"], routePendingOperations: [{ id: "local-route" }] };
    setup.client.update("player:1", local);
    service.profiles.set(1, { ...service.current(1), revision: 2, data: { version: 1, hiddenKeyIds: ["server"] } });
    await setup.client.flush();
    const conflict = setup.client.getState().conflict;
    assert.ok(conflict.server_backup_id && conflict.local_backup_id);
    assert.equal(setup.statuses.at(-1).kind, "conflict");
    await setup.client.retry(true);
    await setup.client.flush();
    assert.equal(service.writes().length, 1);
    const exported = await setup.client.exportConflicts();
    assert.equal(exported.backups.length, 2);
    await setup.client.resolve(choice);
    const writes = service.writes();
    assert.equal(writes.length, 2);
    assert.equal(writes[1].url, "/api/preferences/resolve");
    assert.equal(writes[1].payload.base_revision, 2);
    assert.notEqual(writes[0].payload.operation_id, writes[1].payload.operation_id);
    assert.deepEqual(service.current(1).data.hiddenKeyIds, [choice === "server" ? "server" : "browser"]);
    assert.deepEqual(setup.client.getState().data.routePendingOperations, [{ id: "local-route" }]);
    assert.equal(setup.client.getState().conflict, null);
  });
}

test("offline resolution retries the exact operation instead of creating another conflict", async () => {
  const service = server({ 1: { data: { version: 1, hiddenKeyIds: [] } } });
  let loseResolution = true;
  const setup = harness(service, memoryStorage(), async (url, options) => {
    const result = await service.fetch(url, options);
    if (url.endsWith("/resolve") && loseResolution) { loseResolution = false; throw new Error("offline"); }
    return result;
  });
  await setup.activate();
  setup.client.update("player:1", { version: 1, hiddenKeyIds: ["browser"] });
  service.profiles.set(1, { ...service.current(1), revision: 2 });
  await setup.client.flush();
  await setup.client.resolve("local");
  assert.equal(setup.client.getState().pending.kind, "resolve");
  await setup.client.retry(true);
  const requests = service.writes().filter(call => call.url.endsWith("/resolve"));
  assert.deepEqual(requests[0].payload, requests[1].payload);
  assert.equal(service.current(1).revision, 3);
});

test("a new browser can discover and resolve an existing server conflict", async () => {
  const service = server({ 1: { data: { version: 1, hiddenKeyIds: [] } } });
  const first = harness(service);
  await first.activate();
  first.client.update("player:1", { version: 1, hiddenKeyIds: ["saved-browser"] });
  service.profiles.set(1, { ...service.current(1), revision: 2 });
  await first.client.flush();
  const fresh = harness(service);
  await fresh.activate();
  assert.equal(fresh.statuses.at(-1).kind, "conflict");
  await fresh.client.resolve("local");
  assert.deepEqual(service.current(1).data.hiddenKeyIds, ["saved-browser"]);
  assert.deepEqual(fresh.applied.at(-1).preferences.hiddenKeyIds, ["saved-browser"]);
});

test("raw import retains aliases, archives the complete file and never transfers another browser's route queue", async () => {
  const service = server({ 1: { data: { version: 1, hiddenKeyIds: [] } } });
  const setup = harness(service);
  await setup.activate();
  setup.client.update("player:1", { ...setup.client.getState().data, routePendingOperations: [{ id: "this-browser" }] });
  const source = { version: 1, hiddenKeyIds: ["old-alias"], hideoutPlannerOpen: false,
    routePendingOperations: [{ id: "other-browser" }], routeCaches: { alien: [] },
    operationHistory: [{ id: "undo", label: "old", type: "ui", data: { before: { routePendingOperations: [{ id: "alien" }], hiddenKeyIds: ["old"] } } }] };
  const raw = JSON.stringify({ [rawKey(1)]: JSON.stringify(source) });
  await setup.client.importLocal(raw);
  assert.deepEqual(setup.client.getState().data.routePendingOperations, [{ id: "this-browser" }]);
  assert.deepEqual(service.current(1).data.hiddenKeyIds, ["old-alias"]);
  assert.doesNotMatch(JSON.stringify(service.current(1).data), /routePendingOperations|routeCaches|routeCacheRevisions/);
  assert.ok(Object.values(setup.client.exportLocal().storage).includes(raw));
  await assert.rejects(setup.client.importLocal(JSON.stringify({ profile_id: 2, data: source })), /其他玩家或档案/);
  await assert.rejects(setup.client.importLocal(raw, "player:2"), /档案已切换/);
});

test("offline explicit import survives reconnect while new-origin generated defaults yield to the server", async () => {
  const service = server({ 1: { data: { version: 1, hiddenKeyIds: ["server"] } } });
  let online = false;
  const setup = harness(service, memoryStorage(), (...args) => {
    if (!online) throw new Error("offline");
    return service.fetch(...args);
  });
  await setup.activate();
  await setup.client.importLocal(JSON.stringify({ version: 1, hiddenKeyIds: ["imported"] }));
  online = true;
  await setup.client.retry(true);
  assert.deepEqual(service.current(1).data.hiddenKeyIds, ["imported"]);
  const second = harness(service, memoryStorage(), (...args) => {
    if (!online) throw new Error("offline");
    return service.fetch(...args);
  });
  online = false;
  await second.activate();
  second.client.update("player:1", { version: 1, hiddenKeyIds: ["automatic-default"] });
  online = true;
  await second.client.retry(true);
  assert.deepEqual(second.client.getState().data.hiddenKeyIds, ["imported"]);
});

test("malformed JSON, wrong-profile responses and storage failures preserve raw data without uploads", async () => {
  for (const raw of ["{broken", JSON.stringify({ version: 99 })]) {
    const service = server();
    const setup = harness(service, memoryStorage({ [rawKey(1)]: raw }));
    await setup.activate();
    assert.equal(service.writes().length, 0);
    assert.equal(setup.storage.getItem(rawKey(1)), raw);
    assert.ok(Object.values(setup.client.exportLocal().storage).includes(raw));
  }
  const service = server();
  const setup = harness(service, memoryStorage(), async () => response(200, { profile_id: 2, revision: 8, data: { version: 1 }, conflicts: [] }));
  await setup.activate();
  assert.equal(setup.statuses.at(-1).kind, "offline");
  const storage = memoryStorage({ [rawKey(1)]: JSON.stringify({ version: 1, hiddenKeyIds: ["keep"] }) });
  storage.setItem = () => { throw new Error("quota"); };
  const full = harness(service, storage);
  await full.activate();
  assert.equal(service.calls.length, 0);
  assert.match(full.statuses.at(-1).message, /存储不可用或空间不足/);
});

test("HTTP validation errors retain the pending body and do not automatically retry", async () => {
  const service = server({ 1: { data: { version: 1 } } });
  let rejected = 0;
  const setup = harness(service, memoryStorage(), (url, options) => {
    if (options.body) { rejected += 1; return response(413, { error: "偏好超过容量限制" }); }
    return service.fetch(url, options);
  });
  await setup.activate();
  setup.client.update("player:1", { version: 1, hiddenKeyIds: ["large"] });
  await setup.client.flush();
  assert.equal(setup.statuses.at(-1).kind, "error");
  assert.ok(setup.client.getState().pending);
  await setup.client.retry();
  assert.equal(rejected, 1);
});

test("browser script exports window.PreferenceSync without CommonJS", () => {
  const context = vm.createContext({});
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../web/preference_sync.js"), "utf8"), context);
  assert.equal(typeof context.PreferenceSync.createClient, "function");
});

test("queued explicit flush captures its original scope when the active profile changes", async () => {
  const service = server({ 1: { data: { version: 1, hiddenKeyIds: [] } }, 2: { data: { version: 1, hiddenKeyIds: ["two"] } } });
  const gate = deferred();
  const started = deferred();
  const setup = harness(service, memoryStorage(), async (url, options) => {
    if (options.body && JSON.parse(options.body).profile_id === 1) { started.resolve(); await gate.promise; }
    return service.fetch(url, options);
  });
  await setup.activate(1);
  setup.client.update("player:1", { version: 1, hiddenKeyIds: ["one"] });
  const saving = setup.client.flush();
  await started.promise;
  const queued = setup.client.flush();
  await setup.activate(2);
  gate.resolve();
  await Promise.all([saving, queued]);
  assert.equal(setup.client.getState().scope_id, "player:2");
  assert.deepEqual(service.writes().map(call => call.payload.profile_id), [1]);
  assert.deepEqual(setup.applied.at(-1).preferences.hiddenKeyIds, ["two"]);
});

test("request timeout aborts and retains the original offline key answers", async () => {
  const service = server();
  const storage = memoryStorage({ [rawKey(1)]: JSON.stringify({ version: 1, keyOwnershipAnswers: { old: false } }) });
  const started = deferred();
  const setup = harness(service, storage, (url, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener("abort", () => reject(new Error("request timed out")));
    started.resolve();
  }));
  const loading = setup.activate();
  await started.promise;
  [...setup.timers.values()].find(timer => timer.delay === 10000).callback();
  await loading;
  assert.equal(setup.statuses.at(-1).kind, "offline");
  assert.deepEqual(setup.applied.at(-1).preferences.keyOwnershipAnswers, { old: false });
  assert.equal(service.writes().length, 0);
});

test("task history snapshots remove derived fields while retaining every restorable task field", () => {
  const task = { id: 12, profile_id: 1, trader: "Prapor", title: "任务", objective: "搜集物品",
    item_name: "物品", required_count: null, current_count: 2, state: "active", source_task_id: "native-id",
    source_url: "https://example.invalid/task", source_version: "snapshot-version",
    requirements: [{ text: "找到物品", optional: false, completed: false, target_count: 5, current_count: 2 }],
    data_provider: "tarkov.dev", key_requirements: [{ id: "derived-key" }], future_derived: true };
  const original = Sync.clone(task);
  const { data_provider, key_requirements, future_derived, ...expected } = task;
  const source = { version: 1, operationHistory: [
    { id: "single", label: "勾选要求", type: "task", data: { beforeTask: task, afterTaskId: 12 } },
    { id: "many", label: "导入任务", type: "tasks", data: { beforeTasks: [task] } },
  ] };
  const cleaned = Sync.sharedSnapshot(source);
  assert.deepEqual(Sync.taskSnapshot(task), expected);
  assert.deepEqual(cleaned.operationHistory[0].data.beforeTask, expected);
  assert.deepEqual(cleaned.operationHistory[1].data.beforeTasks, [expected]);
  assert.deepEqual(task, original);
  assert.equal(Sync.taskSnapshot(null), null);
});

test("an old rejected pending task snapshot is cleaned and subsequent key answers can sync", async () => {
  const service = server({ 1: { data: { version: 1 } } });
  const local = { version: 1, operationHistory: [{ id: "undo", label: "勾选要求", type: "task", data: {
    beforeTask: { id: 12, requirements: [{ text: "保留要求", current_count: 2, target_count: 5 }],
      current_count: 2, source_task_id: "native", data_provider: "tarkov.dev", key_requirements: [] },
  } }] };
  const oldId = randomUUID();
  const metadata = JSON.stringify({ profileId: 1, revision: 1, baseline: { version: 1 }, dirty: true,
    pending: { kind: "save", payload: { profile_id: 1, data: local, base_revision: 1, operation_id: oldId } } });
  const storage = memoryStorage({ [rawKey(1)]: JSON.stringify(local), [Sync.META_PREFIX + "player:1"]: metadata });
  const setup = harness(service, storage, (url, options) => {
    if (options.body) assert.doesNotMatch(options.body, /data_provider|key_requirements/);
    return service.fetch(url, options);
  });
  await setup.activate();
  assert.equal(setup.statuses.at(-1).kind, "synced");
  assert.notEqual(service.writes()[0].payload.operation_id, oldId);
  assert.deepEqual(service.current(1).data.operationHistory[0].data.beforeTask.requirements,
    local.operationHistory[0].data.beforeTask.requirements);
  assert.ok(Object.values(setup.client.exportLocal().storage).includes(metadata));
  setup.client.update("player:1", { ...setup.client.getState().data, keyOwnershipAnswers: { key: true } });
  await setup.client.flush();
  assert.deepEqual(service.current(1).data.keyOwnershipAnswers, { key: true });
});

test("unbound legacy browser data migrates safe preferences but preserves its original offline queue", async () => {
  const old = { version: 1, keyOwnershipAnswers: { alias: false }, routePendingOperations: [{ operation_id: "unknown-dataset" }],
    routeCaches: { old: [] }, routeCacheRevisions: { old: 3 }, mapDrawings: { customs: [[0, 0], [1, 1]] },
    legacyRoutesImported: { customs: "old" }, operationHistory: [{ id: "old-task-undo", label: "保留任务记录", type: "task",
      data: { beforeTask: { id: 12, current_count: 2, data_provider: "tarkov.dev", key_requirements: [] } } }] };
  const raw = JSON.stringify(old);
  const oldMeta = JSON.stringify({ profileId: 1, revision: 4, dirty: true, pending: { mustNotReplay: true } });
  const storage = memoryStorage({ [rawKey(1)]: raw, [Sync.META_PREFIX + "player:1"]: oldMeta });
  const service = server();
  const setup = harness(service, storage);
  await setup.activate(1, { scopeId: "root-and-dataset:player:1", datasetScopeId: "root-and-dataset",
    legacyKeys: [rawKey(1)] });
  assert.deepEqual(setup.client.getState().data.routePendingOperations, []);
  assert.deepEqual(setup.client.getState().data.routeCaches, {});
  assert.deepEqual(setup.client.getState().data.operationHistory[0].data.beforeTask, { id: 12, current_count: 2 });
  assert.deepEqual(service.current(1).data.keyOwnershipAnswers, { alias: false });
  assert.doesNotMatch(JSON.stringify(service.writes()), /unknown-dataset|customs|data_provider|key_requirements/);
  assert.equal(storage.getItem(rawKey(1)), raw);
  assert.equal(storage.getItem(Sync.META_PREFIX + "player:1"), oldMeta);
  assert.equal(setup.client.exportLocal().storage[rawKey(1)], raw);
});

test("the same dataset on a new origin keeps server key answers ahead of stale legacy local answers", async () => {
  const service = server({ 1: { revision: 9, data: { version: 1, keyOwnershipAnswers: { key: true }, keyFilterInitialized: true } } });
  const raw = JSON.stringify({ version: 1, keyOwnershipAnswers: { key: false }, routePendingOperations: [{ id: "old" }] });
  const setup = harness(service, memoryStorage({ [rawKey(1)]: raw }));
  await setup.activate(1, { scopeId: "root-and-dataset:player:1", datasetScopeId: "root-and-dataset", legacyKeys: [rawKey(1)] });
  assert.deepEqual(setup.applied.at(-1).preferences.keyOwnershipAnswers, { key: true });
  assert.deepEqual(setup.applied.at(-1).preferences.routePendingOperations, []);
  assert.equal(service.writes().length, 0);
  assert.equal(setup.storage.getItem(rawKey(1)), raw);
});

test("switching datasets pauses an old pending preference save until its own dataset returns", async () => {
  const first = server({ 1: { data: { version: 1 } } });
  const second = server({ 1: { data: { version: 1 } } });
  let service = first;
  const setup = harness(first, memoryStorage(), (...args) => service.fetch(...args));
  await setup.activate(1, { scopeId: "dataset-A:player:1", datasetScopeId: "dataset-A" });
  setup.client.update("dataset-A:player:1", { version: 1, keyOwnershipAnswers: { onlyA: true } });
  const oldTimer = [...setup.timers.values()].find(timer => timer.delay === 450);
  setup.client.deactivate();
  service = second;
  await setup.activate(1, { scopeId: "dataset-B:player:1", datasetScopeId: "dataset-B" });
  await oldTimer.callback();
  await setup.client.flush();
  assert.equal(second.writes().length, 0);
  service = first;
  await setup.activate(1, { scopeId: "dataset-A:player:1", datasetScopeId: "dataset-A" });
  assert.deepEqual(first.current(1).data.keyOwnershipAnswers, { onlyA: true });
});

test("explicit old-origin exports remain importable into the full scope without transferring their queue", async () => {
  const service = server({ 1: { data: { version: 1 } } });
  const setup = harness(service);
  const scopeId = "root-and-dataset:player:1";
  await setup.activate(1, { scopeId, datasetScopeId: "root-and-dataset", legacyKeys: [rawKey(1)] });
  setup.client.update(scopeId, { ...setup.client.getState().data, routePendingOperations: [{ id: "own-dataset" }] });
  await setup.client.importLocal(JSON.stringify({ scope_id: "player:1", profile_id: 1, storage: {
    [rawKey(1)]: JSON.stringify({ version: 1, keyOwnershipAnswers: { imported: false },
      routePendingOperations: [{ id: "unknown-dataset" }] }),
  } }));
  assert.deepEqual(service.current(1).data.keyOwnershipAnswers, { imported: false });
  assert.deepEqual(setup.client.getState().data.routePendingOperations, [{ id: "own-dataset" }]);
  assert.doesNotMatch(JSON.stringify(service.writes()), /unknown-dataset/);
});

const appSource = fs.readFileSync(path.join(__dirname, "../web/app.js"), "utf8");

function appFunction(name) {
  const expression = new RegExp("^(?:async )?function " + name + "\\(", "m");
  const match = expression.exec(appSource);
  assert.ok(match, name);
  const start = match.index;
  const remainder = appSource.slice(start);
  const next = /\n(?:async )?function \w+\(/.exec(remainder);
  return next ? remainder.slice(0, next.index) : remainder;
}

function mapHarness(fixture) {
  const renders = [];
  const network = [];
  let appended = 0;
  const select = value => ({ value, options: [], dataset: {}, disabled: false,
    replaceChildren() { this.options = []; }, append(option) { this.options.push(option); } });
  const context = vm.createContext({
    URLSearchParams, Boolean, Number, String, Set, Map,
    state: { data_source: "reemr", selected_profile_id: 1, tasks: [] },
    mapView: null, mapViewGeneration: 0, activeMapDrawing: null, uiPreferenceScopeId: "player:1",
    uiPreferences: { selectedMapFloors: {}, routePendingOperations: [], mapDrawings: {} },
    currentLanguage: "zh", mapDetailWarnings: [], routeFlushRunning: false,
    elements: {
      mapSelect: select("customs"), mapFloorSelect: select(""), taskMapFilter: select(""),
      mapImage: { hidden: true, naturalWidth: 0, naturalHeight: 0, removeAttribute(key) { delete this[key]; } },
      mapDrawings: { style: {}, replaceChildren() {} }, mapMarkers: { replaceChildren() {} },
      mapCanvas: { style: {} }, mapPlaceholder: {}, mapSourceLink: {}, mapArtworkAttribution: {},
      mapSummary: { textContent: "tasks" }, mapHint: {}, dataSourceNotice: {},
    },
    document: { createElement: () => ({ dataset: {} }) },
    request: async url => { network.push(url); return fixture; },
    setMapDrawingMode() {}, updateMapDrawingButtons() {}, saveUiPreferences() {},
    sourceMapPreferenceId: value => "reemr:" + value,
    updateTaskMapFilterOptions() {}, updateMapArtworkAttribution() {}, renderTasks() {},
    renderMapTargets: (markers, tasks) => renders.push({ markers: Sync.clone(markers), tasks: Sync.clone(tasks) }),
    syncHideoutMaterialsLayout() {},
    mapDrawingStrokes: () => [{ id: "must-not-render" }], appendMapDrawingStroke: () => { appended += 1; },
  });
  for (const name of ["renderMapDrawings", "syncCurrentMapRoutes", "flushRouteOperations", "renderMapAnnotations", "loadMapView"]) {
    vm.runInContext(appFunction(name), context);
  }
  return { context, renders, network, appended: () => appended };
}

test("RE3MR original PNG resolves unknown dimensions on load and never requests or renders routes", async () => {
  const fixture = { map_id: "customs", source_provider: "reemr", reference_material: true, reference_only: false,
    image_url: "/api/map/image?source=reemr&map_id=customs&floor=main", map_name: "海关", source_url: "https://reemr.se/",
    source_notice: "参考材料", floor: { key: "main", width: null, height: null }, floors: [{ key: "main", name: "原图" }],
    markers: [{ task_id: 42, x_percent: 50, y_percent: 50 }], annotations: [{ title: "foreign" }],
    tasks: [{ id: 42, title: "同地图任务" }], task_contexts: [{ id: 42, map_relevant: true, point_status: "reference_only" }] };
  const setup = mapHarness(fixture);
  await setup.context.loadMapView();
  assert.equal(setup.context.elements.mapImage.src, fixture.image_url);
  assert.equal(setup.context.elements.mapCanvas.style.aspectRatio, "auto");
  assert.equal(setup.context.elements.mapImage.hidden, false);
  assert.equal(fixture.markers.length, 0);
  assert.equal(fixture.annotations.length, 0);
  assert.deepEqual(setup.renders.at(-1).tasks, [{ id: 42, title: "同地图任务" }]);
  setup.context.elements.mapImage.naturalWidth = 6400;
  setup.context.elements.mapImage.naturalHeight = 4200;
  setup.context.elements.mapImage.onload();
  assert.equal(setup.context.mapView.floor.width, 6400);
  assert.equal(setup.context.mapView.floor.height, 4200);
  assert.equal(setup.context.elements.mapCanvas.style.aspectRatio, "6400 / 4200");
  assert.equal(setup.context.elements.mapPlaceholder.hidden, true);
  assert.match(setup.context.elements.mapHint.textContent, /不叠加其他来源任务标点或路线/);
  await setup.context.flushRouteOperations();
  setup.context.renderMapAnnotations();
  assert.equal(setup.appended(), 0);
  assert.equal(setup.network.length, 1);
  assert.match(setup.network[0], /^\/api\/map\?/);
  const staleLoad = setup.context.elements.mapImage.onload;
  setup.context.mapViewGeneration += 1;
  setup.context.elements.mapImage.naturalWidth = 123;
  staleLoad();
  assert.equal(setup.context.mapView.floor.width, 6400);
});

test("reference_only retains the existing no-image fallback", async () => {
  const fixture = { map_id: "customs", source_provider: "reemr", reference_only: true, reference_material: false,
    map_name: "海关", source_url: "https://reemr.se/", source_notice: "无底图", floors: [], tasks: [], markers: [] };
  const setup = mapHarness(fixture);
  await setup.context.loadMapView();
  assert.equal(setup.context.elements.mapImage.hidden, true);
  assert.equal(setup.context.elements.mapImage.src, undefined);
  assert.match(setup.context.elements.mapPlaceholder.textContent, /暂无允许读取的原图/);
  assert.equal(setup.network.length, 1);
  assert.equal(setup.appended(), 0);
});

test("blocked reference image displays the exact source-policy reason without image fetch", async () => {
  const fixture = { map_id: "customs", source_provider: "reemr", reference_only: true, reference_material: true,
    availability_notice: "robots 返回 HTML，禁止读取该图", map_name: "海关", source_url: "https://reemr.se/",
    source_notice: "参考资料", floors: [], tasks: [], markers: [] };
  const setup = mapHarness(fixture);
  await setup.context.loadMapView();
  assert.equal(setup.context.elements.mapImage.hidden, true);
  assert.equal(setup.context.elements.mapPlaceholder.textContent, fixture.availability_notice);
  assert.match(setup.context.elements.mapHint.textContent, /robots 返回 HTML/);
  assert.equal(setup.network.length, 1);
});

test("reference tasks continue as context cards with no generated coordinates", () => {
  const context = vm.createContext({ groupMapMarkers: () => [], MAP_TASK_COLORS: ["red"], MAP_TASK_SHAPES: ["circle"] });
  vm.runInContext(appFunction("mapTaskDisplayEntries"), context);
  const result = context.mapTaskDisplayEntries([], [{ id: 42, title: "保留任务", state: "active" }],
    [{ id: 42, map_relevant: true, point_status: "reference_only" }]);
  assert.equal(result.length, 1);
  assert.equal(result[0].contextOnly, true);
  assert.equal(result[0].x_percent, undefined);
  assert.equal(result[0].y_percent, undefined);
});
