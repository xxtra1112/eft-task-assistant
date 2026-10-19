(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.PreferenceSync = api;
})(typeof globalThis === "undefined" ? null : globalThis, function () {
  "use strict";

  const STORAGE_PREFIX = "eft-task-assistant-ui-v1:";
  const META_PREFIX = "eft-task-assistant-preference-sync-v1:";
  const BACKUP_PREFIX = "eft-task-assistant-preference-raw-v1:";
  const LOCAL_FIELDS = new Set(["routePendingOperations", "routeCaches", "routeCacheRevisions"]);
  const FIELDS = new Set([
    "version", "selectedMapId", "selectedMapFloors", "mapAnnotationVisibility", "taskTraderFilter",
    "taskMapFilter", "mapZoom", "hiddenTaskIds", "hiddenMapTaskIds", "showHiddenTasks",
    "hiddenMapPointIds", "hiddenKeyIds", "keyFilterInitialized", "keyFilterKnownIds", "newKeyIds",
    "keyOwnershipPendingIds", "keyOwnershipAnswers", "collapsedMapTaskGroups", "collapsedTaskIds",
    "hideoutPlan", "hideoutOwnedMaterials", "operationHistory", "operationHistoryOpen",
    "hideoutPlannerOpen", "hideoutMaterialsOpen", "panels", "mapDrawings", "legacyRoutesImported",
    "routeStyle", "mobilePairingAddress",
  ]);
  const MIGRATION_HELP = "不同端口/域名的 localStorage 无法自动互读。请在旧地址导出浏览器偏好，再在此导入；旧版无按钮时，在旧页开发者工具控制台执行：copy(JSON.stringify(Object.fromEntries(Object.entries(localStorage).filter(([key]) => key.startsWith('eft-task-assistant-ui-v1:')))))，保存为 JSON 文件后导入。旧钥匙别名和旧绘线的完整原始备份随浏览器偏好导出，显示层可能有容量限制。缺少数据集归属的旧路线队列、缓存及绘线保留在原 localStorage，可显式导出，不会自动重放。路线待发送队列只保留在原浏览器。";

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function object(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function withoutLocal(value) {
    if (Array.isArray(value)) return value.map(withoutLocal);
    if (!object(value)) return value;
    return Object.fromEntries(Object.entries(value).filter(([key]) => !LOCAL_FIELDS.has(key))
      .map(([key, child]) => [key, withoutLocal(child)]));
  }

  function sharedSnapshot(value) {
    if (!object(value)) throw new Error("偏好必须是 JSON 对象；原始副本已保留。");
    const result = withoutLocal(Object.fromEntries(Object.entries(value).filter(([key]) => FIELDS.has(key))));
    if (result.version !== undefined && result.version !== 1) throw new Error("仅支持 version=1 偏好；请保留原始导出。");
    result.version = 1;
    for (const entry of result.operationHistory || []) {
      if (!object(entry?.data)) continue;
      for (const key of ["before", "beforeUi"]) {
        if (object(entry.data[key])) {
          entry.data[key] = Object.fromEntries(Object.entries(entry.data[key])
            .filter(([field]) => FIELDS.has(field) && field !== "operationHistory"));
        }
      }
      if (entry.data.beforeTask) entry.data.beforeTask = taskSnapshot(entry.data.beforeTask);
      if (Array.isArray(entry.data.beforeTasks)) entry.data.beforeTasks = entry.data.beforeTasks.map(taskSnapshot);
    }
    return clone(result);
  }

  function taskSnapshot(task) {
    if (!task) return null;
    const fields = new Set(["id", "profile_id", "trader", "title", "objective", "item_name",
      "required_count", "current_count", "state", "source_task_id", "source_url", "source_version", "requirements"]);
    return clone(Object.fromEntries(Object.entries(task).filter(([key]) => fields.has(key))));
  }

  function signature(value) {
    if (Array.isArray(value)) return "[" + value.map(signature).join(",") + "]";
    if (object(value)) return "{" + Object.keys(value).sort()
      .map(key => JSON.stringify(key) + ":" + signature(value[key])).join(",") + "}";
    return JSON.stringify(value);
  }

  function withLocal(shared, local) {
    return { ...clone(shared), ...Object.fromEntries([...LOCAL_FIELDS]
      .filter(key => Object.prototype.hasOwnProperty.call(local || {}, key))
      .map(key => [key, clone(local[key])])) };
  }

  function createClient(options) {
    const storage = options.storage;
    const transport = options.fetch || globalThis.fetch.bind(globalThis);
    const uuid = options.uuid || (() => globalThis.crypto.randomUUID());
    const schedule = options.setTimeout || globalThis.setTimeout;
    const cancel = options.clearTimeout || globalThis.clearTimeout;
    const sessions = new Map();
    let active = null;

    function read(key) {
      return storage.getItem(key);
    }

    function write(key, value) {
      try {
        storage.setItem(key, value);
      } catch {
        throw new Error("浏览器存储不可用或空间不足；未上传，请立即导出原始偏好。");
      }
    }

    function backup(session, raw) {
      if (raw === null || raw === undefined || session.lastBackup === raw) return;
      write(BACKUP_PREFIX + session.scopeId + ":" + uuid(), raw);
      session.lastBackup = raw;
    }

    function persist(session) {
      write(STORAGE_PREFIX + session.scopeId, JSON.stringify(session.local));
      write(META_PREFIX + session.scopeId, JSON.stringify({
        profileId: session.profileId, revision: session.revision, baseline: session.baseline,
        dirty: session.dirty, pending: session.pending, conflict: session.conflict, imported: session.imported,
      }));
    }

    function status(session, kind, message) {
      session.status = { scopeId: session.scopeId, profileId: session.profileId, kind, message,
        revision: session.revision, conflict: clone(session.conflict), help: MIGRATION_HELP };
      if (active === session) options.onStatus?.(clone(session.status));
    }

    function apply(session) {
      if (active === session) options.onApply?.(clone(session.local), session.scopeId);
    }

    function sameDataset(session) {
      return active !== null && active.datasetScopeId === session.datasetScopeId;
    }

    function failure(session, error) {
      session.retryable = !error.status || error.status >= 500;
      status(session, session.retryable ? "offline" : "error",
        (error.message || "连接失败") + " 未同步修改和原始备份仍在本浏览器。" );
    }

    async function request(path, payload, datasetScopeId = null) {
      const controller = new AbortController();
      const timer = schedule(() => controller.abort(), options.timeoutMs ?? 10000);
      try {
        const response = await transport(path, { cache: "no-store", credentials: "same-origin",
          signal: controller.signal, ...(payload ? { method: "POST", headers: { "Content-Type": "application/json",
            ...(datasetScopeId ? { "X-EFT-Save-Scope": encodeURIComponent(datasetScopeId) } : {}) }, body: JSON.stringify(payload) } : {}) });
        const result = await response.json();
        if (!response.ok) {
          const error = new Error(result?.error || `偏好请求失败（${response.status}）`);
          error.status = response.status;
          error.result = result;
          throw error;
        }
        return result;
      } finally {
        cancel(timer);
      }
    }

    function snapshot(session, value) {
      if (!object(value) || String(value.profile_id) !== String(session.profileId)
          || !Number.isSafeInteger(value.revision) || value.revision < 0 || !object(value.data)
          || !Array.isArray(value.conflicts)) throw new Error("服务器返回的偏好范围或格式无效。");
      return { ...clone(value), data: sharedSnapshot(value.data) };
    }

    function serialize(session, action) {
      const job = session.chain.then(action).catch(error => { failure(session, error); });
      session.chain = job;
      return job;
    }

    function accept(session, remote) {
      backup(session, read(STORAGE_PREFIX + session.scopeId));
      session.local = withLocal(remote.data, session.local);
      session.revision = remote.revision;
      session.baseline = remote.data;
      session.dirty = false;
      session.pending = null;
      session.conflict = null;
      session.imported = false;
      persist(session);
    }

    async function flush(session, applyResolved = true) {
      if (!sameDataset(session) || !session.loaded || session.conflict) return;
      while (session.pending || session.dirty) {
        if (!sameDataset(session)) return;
        if (!session.pending) {
          const data = sharedSnapshot(session.local);
          if (signature(data) === signature(session.baseline)) {
            session.dirty = false;
            persist(session);
            break;
          }
          session.pending = { kind: "save", payload: { profile_id: session.profileId, data,
            base_revision: session.revision, operation_id: uuid(), only_if_empty: session.revision === 0 } };
        }
        persist(session);
        const pending = clone(session.pending);
        status(session, "saving", "正在同步偏好；待发送操作已保存在本浏览器。");
        let remote;
        try {
          remote = snapshot(session, await request(pending.kind === "resolve" ? "/api/preferences/resolve" : "/api/preferences", pending.payload, session.datasetScopeId));
        } catch (error) {
          if (!sameDataset(session)) return;
          if (error.status !== 409 || !error.result?.conflict_id || !error.result?.current) throw error;
          const current = snapshot(session, error.result.current);
          session.conflict = { ...clone(error.result), current,
            local_data: clone(pending.kind === "save" ? pending.payload.data : pending.local_data) };
          session.pending = null;
          backup(session, JSON.stringify(session.local));
          persist(session);
          status(session, "conflict", "偏好冲突：服务器与本浏览器双方副本均已备份。请选择保留服务端或使用本浏览器；导出可查看双方备份。");
          return;
        }
        if (!sameDataset(session)) return;
        const submitted = pending.kind === "save" ? pending.payload.data : pending.local_data;
        const latest = sharedSnapshot(session.local);
        session.pending = null;
        session.conflict = null;
        session.revision = remote.revision;
        session.baseline = remote.data;
        if (pending.kind === "resolve" && pending.payload.choice === "server") {
          accept(session, remote);
          if (applyResolved) apply(session);
        } else {
          session.dirty = signature(latest) !== signature(submitted);
          if (!session.dirty) session.local = withLocal(remote.data, session.local);
          persist(session);
          if (pending.kind === "resolve" && !session.dirty && applyResolved) apply(session);
        }
      }
      session.retryable = true;
      session.imported = false;
      persist(session);
      status(session, "synced", "共享偏好已同步；路线队列与缓存仅留在本浏览器。");
    }

    async function load(session) {
      if (!sameDataset(session)) return;
      status(session, "loading", "正在读取共享偏好，请稍候…");
      const remote = snapshot(session, await request("/api/preferences?profile_id=" + encodeURIComponent(session.profileId)));
      if (!sameDataset(session)) return;
      session.loaded = true;
      if (session.imported && session.revision === null) {
        session.revision = remote.revision;
        session.baseline = remote.data;
      }
      if (session.pending || session.conflict || (session.dirty && session.revision !== null)) {
        if (session.conflict && !session.pending) {
          status(session, "conflict", "存在尚未处理的偏好冲突；双方备份已保留，请选择保留服务端或使用本浏览器。");
        } else await flush(session, false);
      } else if (remote.revision > 0) {
        accept(session, remote);
        const unresolved = remote.conflicts.filter(entry => !entry.resolution).at(-1);
        if (unresolved) {
          session.conflict = { ...unresolved, conflict_id: unresolved.id, current: remote,
            local_data: sharedSnapshot(session.local) };
          persist(session);
          status(session, "conflict", "已恢复服务端偏好；仍有未处理冲突，双方备份可导出。使用本浏览器将恢复冲突时保存的浏览器副本。");
        } else status(session, "synced", "已恢复服务端共享偏好；新地址的默认设置不会覆盖服务端。");
      } else {
        session.revision = 0;
        session.baseline = remote.data;
        if (session.hadLocal) {
          session.dirty = true;
          persist(session);
          await flush(session, false);
        } else {
          session.dirty = false;
          status(session, "empty", "服务端暂无偏好，当前地址也没有旧缓存。可从旧地址手动导出并导入。");
        }
      }
      apply(session);
    }

    async function activate({ scopeId, profileId, datasetScopeId = null, legacyKey = null, legacyKeys = [], defaults = {} }) {
      if (!Number.isSafeInteger(Number(profileId)) || Number(profileId) < 1) throw new Error("请选择有效档案。");
      let session = sessions.get(scopeId);
      if (!session) {
        session = { scopeId, profileId: Number(profileId), datasetScopeId, local: clone(defaults), loaded: false,
          revision: null, baseline: null, dirty: false, pending: null, conflict: null,
          chain: Promise.resolve(), timer: null, retryable: true, lastRetry: 0, imported: false,
          legacyKeys: [...new Set([...legacyKeys, ...(legacyKey ? [legacyKey] : [])])] };
        sessions.set(scopeId, session);
      }
      active = session;
      await serialize(session, async () => {
        try {
          if (!sameDataset(session)) return;
          const scopedRaw = read(STORAGE_PREFIX + scopeId);
          const raw = scopedRaw ?? session.legacyKeys.map(read).find(value => value !== null) ?? null;
          session.hadLocal = raw !== null;
          if (raw !== null) {
            backup(session, raw);
            const parsed = JSON.parse(raw);
            const shared = sharedSnapshot(parsed);
            if (scopedRaw === null) {
              for (const key of ["mapDrawings", "legacyRoutesImported"]) delete shared[key];
            }
            session.local = scopedRaw === null ? { ...clone(defaults), ...shared } : withLocal(shared, parsed);
          }
          const metadata = read(META_PREFIX + scopeId);
          if (metadata) {
            const saved = JSON.parse(metadata);
            if (saved.profileId !== session.profileId || !(saved.revision === null
                || (Number.isSafeInteger(saved.revision) && saved.revision >= 0))) throw new Error("本机偏好同步记录范围无效。");
            if (saved.pending) {
              const payload = saved.pending.payload;
              if (payload?.profile_id !== session.profileId || !["save", "resolve"].includes(saved.pending.kind)
                  || (saved.pending.kind === "save" && !object(payload.data))) {
                throw new Error("本机待发送操作范围无效；请导出后检查。");
              }
              if (saved.pending.kind === "save") {
                const cleaned = sharedSnapshot(payload.data);
                if (signature(payload.data) !== signature(cleaned)) {
                  backup(session, metadata);
                  payload.data = cleaned;
                  payload.operation_id = uuid();
                }
              }
            }
            Object.assign(session, { revision: saved.revision, baseline: saved.baseline,
              dirty: Boolean(saved.dirty), pending: saved.pending || null, conflict: saved.conflict || null,
              imported: Boolean(saved.imported) });
          }
          await load(session);
        } catch (error) {
          apply(session);
          throw error;
        }
      });
      return clone(session.local);
    }

    function update(scopeId, value) {
      const session = sessions.get(scopeId);
      if (!session || session !== active) return false;
      try {
        const next = clone(value);
        const changed = signature(sharedSnapshot(next)) !== signature(sharedSnapshot(session.local));
        session.local = next;
        if (changed) {
          session.dirty = true;
          session.hadLocal = true;
        }
        persist(session);
        if (changed && !session.conflict) {
          cancel(session.timer);
          session.timer = schedule(() => { session.timer = null; serialize(session, () => flush(session)); }, options.debounceMs ?? 450);
          status(session, "pending", "偏好修改已保存在本浏览器，等待同步。");
        }
        return true;
      } catch (error) {
        failure(session, error);
        return false;
      }
    }

    function retry(force = false) {
      const session = active;
      if (!session || session.conflict || (!force && (!session.retryable || Date.now() - session.lastRetry < 10000))) return Promise.resolve();
      session.lastRetry = Date.now();
      return serialize(session, () => session.loaded ? flush(session) : load(session));
    }

    function resolve(choice) {
      const session = active;
      if (!session?.conflict || !["server", "local"].includes(choice)) return Promise.resolve();
      return serialize(session, async () => {
        if (!session.conflict || session.pending) return;
        const current = snapshot(session, await request("/api/preferences?profile_id=" + encodeURIComponent(session.profileId)));
        if (!sameDataset(session)) return;
        const conflict = session.conflict;
        session.pending = { kind: "resolve", local_data: clone(conflict.local_data), payload: {
          profile_id: session.profileId, conflict_id: conflict.conflict_id, choice,
          base_revision: current.revision, operation_id: uuid(),
        } };
        session.conflict = null;
        session.loaded = true;
        backup(session, JSON.stringify(session.local));
        persist(session);
        await flush(session);
      });
    }

    function exportLocal(origin = "") {
      if (!active) throw new Error("请先选择档案。");
      const entries = {};
      for (let index = 0; index < storage.length; index += 1) {
        const key = storage.key(index);
        if (key === STORAGE_PREFIX + active.scopeId || key === META_PREFIX + active.scopeId
            || active.legacyKeys.includes(key)
            || key?.startsWith(BACKUP_PREFIX + active.scopeId + ":")) entries[key] = read(key);
      }
      if (!entries[STORAGE_PREFIX + active.scopeId]) entries[STORAGE_PREFIX + active.scopeId] = JSON.stringify(active.local);
      return { format: "eft-preferences-local-v1", scope_id: active.scopeId, profile_id: active.profileId,
        origin, storage: entries, instructions: MIGRATION_HELP };
    }

    function parseImport(text, session) {
      const value = JSON.parse(text);
      if (!object(value)) throw new Error("导入文件必须是偏好 JSON 对象。");
      if ((value.profile_id !== undefined && Number(value.profile_id) !== session.profileId)
          || (value.scope_id !== undefined && value.scope_id !== session.scopeId
            && !session.legacyKeys.includes(STORAGE_PREFIX + value.scope_id))) throw new Error("导入文件属于其他玩家或档案或数据集，请先切换到对应档案。");
      const entries = value.storage || value;
      const raw = entries[STORAGE_PREFIX + session.scopeId]
        ?? session.legacyKeys.map(key => entries[key]).find(entry => entry !== undefined)
        ?? entries[STORAGE_PREFIX + session.profileId];
      const preferences = raw !== undefined ? (typeof raw === "string" ? JSON.parse(raw) : raw) : value;
      if (!object(preferences) || !Object.keys(preferences).some(key => FIELDS.has(key))) throw new Error("没有找到当前档案的偏好；请使用旧地址导出的文件。");
      return sharedSnapshot(preferences);
    }

    async function importLocal(text, expectedScope = active?.scopeId) {
      const session = active;
      if (!session || session.scopeId !== expectedScope) throw new Error("导入时档案已切换，请重新选择文件。");
      const imported = parseImport(text, session);
      await serialize(session, async () => {
        if (active !== session) throw new Error("导入时档案已切换，请重新选择文件。");
        if (session.conflict || session.pending?.kind === "resolve") throw new Error("请先处理当前偏好冲突，再导入。");
        backup(session, text);
        backup(session, read(STORAGE_PREFIX + session.scopeId));
        session.local = withLocal(imported, session.local);
        session.hadLocal = true;
        session.imported = true;
        session.dirty = true;
        persist(session);
        apply(session);
        status(session, "pending", "已导入偏好并保留原始备份；原浏览器路线待发送队列不会迁入。");
        if (!session.loaded) await load(session);
        else await flush(session);
      });
    }

    async function exportConflicts() {
      if (!active) throw new Error("请先选择档案。");
      const session = active;
      const result = await request("/api/preferences/conflicts?profile_id=" + encodeURIComponent(session.profileId));
      if (String(result?.profile_id) !== String(session.profileId)) throw new Error("备份导出范围无效。");
      return { ...result, browser: exportFor(session) };
    }

    function exportFor(session) {
      return { scope_id: session.scopeId, profile_id: session.profileId, data: clone(session.local),
        pending: clone(session.pending), conflict: clone(session.conflict) };
    }

    function flushActive() {
      const session = active;
      return session ? serialize(session, () => flush(session)) : Promise.resolve();
    }

    return { activate, update, retry, resolve, importLocal, exportLocal, exportConflicts,
      deactivate: () => { active = null; },
      flush: flushActive,
      getState: () => active ? exportFor(active) : null };
  }

  return { createClient, sharedSnapshot, taskSnapshot, clone, STORAGE_PREFIX, META_PREFIX, BACKUP_PREFIX, MIGRATION_HELP };
});
