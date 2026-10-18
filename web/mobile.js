const mobileElements = {
  gate: document.querySelector("#mobileGate"),
  gateMessage: document.querySelector("#gateMessage"),
  gateRetry: document.querySelector("#gateRetryButton"),
  app: document.querySelector("#mobileApp"),
  playerName: document.querySelector("#mobilePlayerName"),
  mapSelect: document.querySelector("#mobileMapSelect"),
  floorSelect: document.querySelector("#mobileFloorSelect"),
  annotationFilters: document.querySelector("#mobileAnnotationFilters"),
  taskPanel: document.querySelector(".mobile-task-panel"),
  taskPanelResizer: document.querySelector("#mobileTaskPanelResizer"),
  viewport: document.querySelector("#mobileMapViewport"),
  canvas: document.querySelector("#mobileMapCanvas"),
  image: document.querySelector("#mobileMapImage"),
  markers: document.querySelector("#mobileMapMarkers"),
  mapLoading: document.querySelector("#mobileMapLoading"),
  mapError: document.querySelector("#mobileMapError"),
  zoomOut: document.querySelector("#mobileZoomOut"),
  zoomReset: document.querySelector("#mobileZoomReset"),
  zoomIn: document.querySelector("#mobileZoomIn"),
  immersiveToggle: document.querySelector("#mobileImmersiveToggle"),
  taskCount: document.querySelector("#mobileTaskCount"),
  taskList: document.querySelector("#mobileTaskList"),
  toast: document.querySelector("#mobileToast"),
  theme: document.querySelector("#mobileThemeButton"),
  refresh: document.querySelector("#mobileRefreshButton"),
  logout: document.querySelector("#mobileLogoutButton"),
  pointDialog: document.querySelector("#mobilePointDialog"),
  pointTask: document.querySelector("#mobilePointTask"),
  pointTitle: document.querySelector("#mobilePointTitle"),
  pointLocation: document.querySelector("#mobilePointLocation"),
  pointDescription: document.querySelector("#mobilePointDescription"),
  pointMeta: document.querySelector("#mobilePointMeta"),
  pointImages: document.querySelector("#mobilePointImages"),
  pointSource: document.querySelector("#mobilePointSource"),
  pointClose: document.querySelector("#mobilePointClose"),
};

const MOBILE_TASK_COLORS = [
  "#e76f51", "#4f83cc", "#44a581", "#b16ac7", "#d49a2a", "#328fa3",
  "#da5a8a", "#739a3d", "#8a70dc", "#cf7440", "#4580a6", "#9c5d73",
];
const MOBILE_TASK_SHAPES = ["circle", "diamond", "square", "triangle", "pentagon", "hexagon"];
const MOBILE_ANNOTATION_DEFAULTS = {
  location: true,
  "pmc-exit": false,
  "scav-exit": false,
  transfer: false,
};
const MOBILE_REFRESH_INTERVAL = 15000;
const MOBILE_STORAGE_PREFIX = "eft-task-assistant-mobile-v1:";

let mobileState = null;
let mobileMapList = [];
let mobileMapView = null;
let mobileMapLoadGeneration = 0;
let mobileSelectedMapId = "";
let mobileSelectedMarkerId = "";
let mobilePairingAttempted = false;
let mobileToastTimer = null;
let mobileRefreshTimer = null;
let mobileZoom = 1;
let mobileTaskPanelHeightRatio = null;
let mobileTaskPanelDrag = null;
let mobileMapBaseWidth = 0;
let mobileMapBaseHeight = 0;
let mobileObservedMapViewportWidth = 0;
let mobilePanX = 0;
let mobilePanY = 0;
let mobileMapDragging = null;
let mobilePinchStart = null;
const mobilePointers = new Map();

function detectMobileDeviceType() {
  const userAgent = navigator.userAgent || "";
  const platform = navigator.userAgentData?.platform || navigator.platform || "";
  const touchPoints = navigator.maxTouchPoints || 0;
  const screenWidth = window.screen?.width || 0;
  const screenHeight = window.screen?.height || 0;
  const shortestScreenEdge = Math.min(screenWidth, screenHeight);
  const isIPad = /iPad/i.test(userAgent) || (/Mac/i.test(platform) && touchPoints > 1);
  const isAndroidTablet = /Android/i.test(userAgent) && !/Mobile/i.test(userAgent);
  const isTabletBrowser = /Tablet|PlayBook|Silk/i.test(userAgent);
  const isLargeTouchDevice = touchPoints > 1 && shortestScreenEdge >= 600 && !/Mobile/i.test(userAgent);
  return isIPad || isAndroidTablet || isTabletBrowser || isLargeTouchDevice ? "tablet" : "phone";
}

function updateMobileDeviceType() {
  const deviceType = detectMobileDeviceType();
  mobileElements.app.dataset.deviceType = deviceType;
  mobileElements.app.classList.toggle("is-tablet-device", deviceType === "tablet");
  mobileElements.app.classList.toggle("is-phone-device", deviceType === "phone");
}

function mobileUsesTabletLayout() {
  return mobileElements.app.classList.contains("is-tablet-device")
    && window.matchMedia("(min-width: 620px) and (min-height: 520px)").matches;
}

updateMobileDeviceType();

function mobileRequest(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body != null) headers["Content-Type"] = "application/json";
  return fetch(path, {
    cache: "no-store",
    credentials: "same-origin",
    ...options,
    headers,
  }).then(async (response) => {
    const contentType = response.headers.get("Content-Type") || "";
    const result = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok) {
      const error = new Error(result?.error || `请求失败（${response.status}）`);
      error.status = response.status;
      throw error;
    }
    return result;
  });
}

function mobilePost(path, payload = {}) {
  return mobileRequest(path, { method: "POST", body: JSON.stringify(payload) });
}

function showMobileGate(message, retry = false) {
  mobileElements.app.hidden = true;
  mobileElements.gate.hidden = false;
  mobileElements.gateMessage.textContent = message;
  mobileElements.gateRetry.hidden = !retry;
}

function showMobileApp() {
  mobileElements.gate.hidden = true;
  mobileElements.app.hidden = false;
  restoreMobileTaskPanelHeight();
  const bounds = mobileTaskPanelHeightBounds();
  mobileElements.taskPanelResizer.setAttribute("aria-valuemin", String(bounds.min));
  mobileElements.taskPanelResizer.setAttribute("aria-valuemax", String(bounds.max));
  mobileElements.taskPanelResizer.setAttribute("aria-valuenow", String(Math.round(
    mobileElements.taskPanel.getBoundingClientRect().height,
  )));
}

function mobileStorageKey() {
  const playerId = mobileState?.player?.id || "player";
  const profileId = mobileState?.selected_profile_id ?? "profile";
  return `${MOBILE_STORAGE_PREFIX}${playerId}:${profileId}`;
}

function readMobilePreferences() {
  try {
    const value = JSON.parse(localStorage.getItem(mobileStorageKey()) || "{}");
    if (!value || typeof value !== "object") return {};
    return {
      ...value,
      mapAnnotations: Object.fromEntries(Object.keys(MOBILE_ANNOTATION_DEFAULTS).map((key) => [
        key,
        typeof value.mapAnnotations?.[key] === "boolean"
          ? value.mapAnnotations[key]
          : MOBILE_ANNOTATION_DEFAULTS[key],
      ])),
    };
  } catch {
    return {};
  }
}

function saveMobilePreferences() {
  if (!mobileState) return;
  try {
    const preferences = readMobilePreferences();
    localStorage.setItem(mobileStorageKey(), JSON.stringify({
      mapId: mobileSelectedMapId,
      floors: preferences.floors || {},
      mapAnnotations: Object.fromEntries(
        [...mobileElements.annotationFilters.querySelectorAll("input[data-map-annotation-filter]")]
          .map((input) => [input.dataset.mapAnnotationFilter, input.checked]),
      ),
      annotationFiltersCollapsed: !mobileElements.annotationFilters.open,
      taskPanelHeightRatio: mobileTaskPanelHeightRatio ?? preferences.taskPanelHeightRatio ?? null,
    }));
  } catch {
    showMobileToast("浏览器无法保存本机地图选择。", "error");
  }
}

function applyMobileAnnotationPreferences() {
  const preferences = readMobilePreferences();
  const annotations = preferences.mapAnnotations || MOBILE_ANNOTATION_DEFAULTS;
  mobileElements.annotationFilters.open = preferences.annotationFiltersCollapsed !== true;
  mobileElements.annotationFilters.querySelectorAll("input[data-map-annotation-filter]").forEach((input) => {
    input.checked = annotations[input.dataset.mapAnnotationFilter] !== false;
  });
}

function mobileTaskPanelHeightBounds() {
  const appHeight = mobileElements.app.clientHeight;
  if (!appHeight) return { min: 0, max: appHeight };
  const fixedHeight = mobileElements.app.querySelector(".mobile-topbar").getBoundingClientRect().height
    + mobileElements.app.querySelector(".mobile-map-controls").getBoundingClientRect().height
    + mobileElements.taskPanelResizer.getBoundingClientRect().height;
  return {
    min: 0,
    max: Math.max(0, appHeight - fixedHeight - 2),
  };
}

function setMobileTaskPanelHeight(height, remember = false) {
  const appHeight = mobileElements.app.clientHeight;
  if (!appHeight || mobileUsesTabletLayout()) return;
  const bounds = mobileTaskPanelHeightBounds();
  const clampedHeight = Math.round(Math.max(bounds.min, Math.min(bounds.max, height)));
  mobileElements.app.style.setProperty("--mobile-task-panel-height", `${clampedHeight}px`);
  mobileElements.taskPanelResizer.setAttribute("aria-valuemin", String(bounds.min));
  mobileElements.taskPanelResizer.setAttribute("aria-valuemax", String(bounds.max));
  mobileElements.taskPanelResizer.setAttribute("aria-valuenow", String(clampedHeight));
  if (remember) mobileTaskPanelHeightRatio = clampedHeight / appHeight;
}

function restoreMobileTaskPanelHeight() {
  mobileTaskPanelHeightRatio = null;
  mobileElements.app.style.removeProperty("--mobile-task-panel-height");
  const storedRatio = readMobilePreferences().taskPanelHeightRatio;
  if (typeof storedRatio === "number" && Number.isFinite(storedRatio) && storedRatio >= 0 && storedRatio <= 0.95) {
    mobileTaskPanelHeightRatio = storedRatio;
    setMobileTaskPanelHeight(mobileElements.app.clientHeight * storedRatio);
  }
}

function selectedMobileMapTaskIds() {
  const map = mobileMapList.find((item) => String(item.map_id) === String(mobileSelectedMapId));
  return Array.isArray(map?.task_ids) ? new Set(map.task_ids.map(String)) : null;
}

function showMobileToast(message, kind = "info") {
  mobileElements.toast.textContent = message;
  mobileElements.toast.dataset.kind = kind;
  mobileElements.toast.classList.add("is-visible");
  clearTimeout(mobileToastTimer);
  mobileToastTimer = setTimeout(() => mobileElements.toast.classList.remove("is-visible"), 2400);
}

function activeMobileTasks() {
  const mapTaskIds = selectedMobileMapTaskIds();
  return (mobileState?.tasks || []).filter((task) => (
    task.state !== "complete" && (!mapTaskIds || mapTaskIds.has(String(task.id)))
  ));
}

function requirementProgress(task) {
  const requirements = Array.isArray(task.requirements) ? task.requirements : [];
  const required = requirements.filter((item) => !item.optional);
  const completed = required.filter((item) => item.completed);
  return { completed: completed.length, total: required.length };
}

function renderMobileTasks() {
  const tasks = activeMobileTasks();
  const openTasks = new Set(
    [...mobileElements.taskList.querySelectorAll("details[open]")].map((card) => card.dataset.taskId),
  );
  mobileElements.taskCount.textContent = `${tasks.length} 项`;
  mobileElements.taskList.replaceChildren();
  if (!tasks.length) {
    const empty = document.createElement("p");
    empty.className = "mobile-empty";
    empty.textContent = selectedMobileMapTaskIds()
      ? "当前地图暂无未完成任务。"
      : "当前档案还没有任务。";
    mobileElements.taskList.append(empty);
    return;
  }

  for (const [taskIndex, task] of tasks.entries()) {
    const color = MOBILE_TASK_COLORS[taskIndex % MOBILE_TASK_COLORS.length];
    const progress = requirementProgress(task);
    const card = document.createElement("details");
    card.className = "mobile-task-card";
    card.dataset.taskId = String(task.id);
    card.style.setProperty("--task-color", color);
    card.open = openTasks.has(String(task.id));

    const summary = document.createElement("summary");
    const title = document.createElement("span");
    title.className = "mobile-task-title";
    title.textContent = task.title || "未命名任务";
    const trader = document.createElement("span");
    trader.className = "mobile-task-trader";
    trader.textContent = task.trader || "";
    title.prepend(trader);
    const count = document.createElement("span");
    count.className = "mobile-task-progress";
    count.textContent = `${progress.completed}/${progress.total}`;
    summary.append(title, count);

    const body = document.createElement("div");
    body.className = "mobile-task-body";
    const requirements = Array.isArray(task.requirements) ? task.requirements : [];
    if (!requirements.length) {
      const empty = document.createElement("p");
      empty.className = "mobile-empty";
      empty.textContent = "该任务暂无细分要求。";
      body.append(empty);
    }
    requirements.forEach((requirement, index) => {
      const row = document.createElement("div");
      row.className = "mobile-requirement";
      const target = Number(requirement.target_count || 0);
      const label = document.createElement("div");
      label.className = `mobile-requirement-label${requirement.optional ? " is-optional" : ""}`;
      if (target > 1) {
        label.textContent = requirement.text || "未命名要求";
        if (requirement.optional) label.append(mobileOptionalBadge());
        const counter = document.createElement("div");
        counter.className = "requirement-counter";
        const count = document.createElement("span");
        count.textContent = `${Number(requirement.current_count || 0)}/${target}`;
        counter.append(count);
        row.append(label, counter);
      } else {
        const status = document.createElement("span");
        status.className = `mobile-requirement-check${requirement.completed ? " is-complete" : ""}`;
        status.textContent = requirement.completed ? "✓" : "";
        status.setAttribute("aria-hidden", "true");
        const text = document.createElement("span");
        text.textContent = requirement.text || "未命名要求";
        label.append(status, text);
        if (requirement.optional) label.append(mobileOptionalBadge());
        row.append(label);
      }
      body.append(row);
    });
    card.append(summary, body);
    mobileElements.taskList.append(card);
  }
}

function mobileOptionalBadge() {
  const badge = document.createElement("span");
  badge.className = "mobile-optional-badge";
  badge.textContent = "可选";
  return badge;
}

function mobileMapRequestUrl(mapId, floorKey = "") {
  const query = new URLSearchParams({ map_id: mapId });
  if (floorKey) query.set("floor", floorKey);
  return `/api/map?${query}`;
}

function renderMobileMapOptions(selectedMapId) {
  mobileElements.mapSelect.replaceChildren();
  for (const map of mobileMapList) {
    const option = document.createElement("option");
    option.value = map.map_id;
    option.textContent = map.active_task_count
      ? `${map.name} · ${map.active_task_count} 个任务`
      : map.name;
    mobileElements.mapSelect.append(option);
  }
  mobileElements.mapSelect.value = selectedMapId;
  mobileElements.mapSelect.disabled = mobileMapList.length === 0;
}

function renderMobileFloorOptions(floors, selectedFloor) {
  mobileElements.floorSelect.replaceChildren();
  for (const floor of floors || []) {
    const option = document.createElement("option");
    option.value = String(floor.key);
    option.textContent = floor.active_point_count
      ? `${floor.name} · ${floor.active_point_count} 点`
      : floor.name;
    mobileElements.floorSelect.append(option);
  }
  mobileElements.floorSelect.value = String(selectedFloor || "");
  mobileElements.floorSelect.disabled = mobileElements.floorSelect.options.length < 2;
}

function setMobileMapError(message) {
  mobileElements.mapLoading.hidden = true;
  mobileElements.mapError.textContent = message;
  mobileElements.mapError.hidden = !message;
}

function sizeMobileMapCanvas() {
  const floor = mobileMapView?.floor;
  if (!floor || !Number(floor.width) || !Number(floor.height)) return;
  const ratio = Number(floor.width) / Number(floor.height);
  const viewportWidth = mobileElements.viewport.clientWidth;
  const viewportHeight = mobileElements.viewport.clientHeight;
  if (viewportWidth <= 0 || viewportHeight <= 0) return;
  const width = Math.max(1, Math.min(viewportWidth, viewportHeight * ratio));
  mobileMapBaseWidth = width;
  mobileMapBaseHeight = width / ratio;
  applyMobileMapTransform();
}

function applyMobileMapTransform() {
  mobileElements.canvas.style.width = `${mobileMapBaseWidth * mobileZoom}px`;
  mobileElements.canvas.style.height = `${mobileMapBaseHeight * mobileZoom}px`;
  mobileElements.canvas.style.left = `calc(50% + ${mobilePanX}px)`;
  mobileElements.canvas.style.top = `calc(50% + ${mobilePanY}px)`;
  mobileElements.zoomReset.textContent = `${Math.round(mobileZoom * 100)}%`;
}

function setMobileMapZoom(value, resetPan = false) {
  mobileZoom = Math.min(5, Math.max(0.65, value));
  if (resetPan) {
    mobilePanX = 0;
    mobilePanY = 0;
  }
  applyMobileMapTransform();
}

function mobileMarkerGroups(markers, tasks) {
  const taskIndex = new Map((tasks || []).map((task, index) => [String(task.id), index]));
  const grouped = new Map();
  for (const marker of markers || []) {
    const key = marker.task_id == null ? `title:${marker.task_title}` : String(marker.task_id);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(marker);
  }
  const groups = [...grouped.entries()].sort(([left], [right]) => (
    (taskIndex.get(left) ?? Number.MAX_SAFE_INTEGER) - (taskIndex.get(right) ?? Number.MAX_SAFE_INTEGER)
  ));
  return groups.flatMap(([key, taskMarkers], groupIndex) => taskMarkers.map((marker, pointIndex) => {
    const index = taskIndex.get(key) ?? groupIndex;
    return {
      ...marker,
      groupKey: key,
      pointNumber: pointIndex + 1,
      taskColor: MOBILE_TASK_COLORS[index % MOBILE_TASK_COLORS.length],
      taskShape: MOBILE_TASK_SHAPES[index % MOBILE_TASK_SHAPES.length],
    };
  }));
}

function selectedMobileAnnotationCategories() {
  return new Set(
    [...mobileElements.annotationFilters.querySelectorAll("input[data-map-annotation-filter]")]
      .filter((input) => input.checked)
      .map((input) => input.dataset.mapAnnotationFilter),
  );
}

function renderMobileMarkers() {
  mobileElements.markers.replaceChildren();
  if (!mobileMapView) return;
  const tasks = mobileMapView.tasks || [];
  const markers = mobileMarkerGroups(mobileMapView.markers, tasks);
  const visibleCategories = selectedMobileAnnotationCategories();
  const annotations = (mobileMapView.annotations || []).map((annotation) => ({
    ...annotation,
    activeCategories: (annotation.categories || []).filter((category) => visibleCategories.has(category)),
  })).filter((annotation) => annotation.activeCategories.length);
  if (!markers.length && !annotations.length) {
    mobileElements.mapError.textContent = "当前没有可用的地图点位。";
    mobileElements.mapError.hidden = false;
    return;
  }
  mobileElements.mapError.hidden = true;
  markers.forEach((marker) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `mobile-marker${marker.visited ? " is-visited" : ""}`;
    button.dataset.markerId = marker.id;
    button.dataset.kind = marker.point_kind || "objective";
    button.style.left = `${Number(marker.x_percent)}%`;
    button.style.top = `${Number(marker.y_percent)}%`;
    button.style.setProperty("--task-color", marker.taskColor);
    const markerFace = document.createElement("span");
    markerFace.className = "mobile-marker-face";
    markerFace.dataset.shape = marker.taskShape;
    markerFace.textContent = String(marker.pointNumber);
    const visitedBadge = document.createElement("span");
    visitedBadge.className = "mobile-marker-visited-badge";
    visitedBadge.setAttribute("aria-hidden", "true");
    visitedBadge.textContent = "✓";
    button.append(markerFace, visitedBadge);
    button.setAttribute("aria-label", [marker.task_title || "任务", marker.title || "任务点位", marker.floor_name]
      .filter(Boolean).join(" · "));
    button.addEventListener("click", () => openMobilePoint(marker));
    mobileElements.markers.append(button);
  });
  annotations.forEach((annotation) => {
    if (annotation.activeCategories.includes("location")) {
      const label = document.createElement("span");
      label.className = "mobile-location-label";
      label.textContent = annotation.title;
      label.style.left = Number(annotation.x_percent) + "%";
      label.style.top = Number(annotation.y_percent) + "%";
      mobileElements.markers.append(label);
      return;
    }
    const category = annotation.activeCategories.length > 1 ? "shared-exit" : annotation.activeCategories[0];
    const button = document.createElement("button");
    button.type = "button";
    button.className = "mobile-annotation-marker";
    button.dataset.category = category;
    button.style.left = Number(annotation.x_percent) + "%";
    button.style.top = Number(annotation.y_percent) + "%";
    const iconUrl = annotation.icon_urls?.[annotation.activeCategories[0]]
      || Object.values(annotation.icon_urls || {})[0]
      || "";
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
    button.setAttribute("aria-label", [annotation.annotation_label, annotation.title, annotation.floor_name]
      .filter(Boolean).join(" · "));
    button.addEventListener("click", () => openMobilePoint({
      ...annotation,
      task_title: annotation.annotation_label || "地图标注",
    }));
    mobileElements.markers.append(button);
  });
}

async function loadMobileMap(mapId, floorKey = "") {
  if (!mapId) return;
  const generation = ++mobileMapLoadGeneration;
  mobileSelectedMapId = String(mapId);
  renderMobileMapOptions(mobileSelectedMapId);
  renderMobileTasks();
  mobileElements.mapError.hidden = true;
  mobileElements.mapLoading.textContent = "正在载入地图…";
  mobileElements.mapLoading.hidden = false;
  mobileElements.image.hidden = true;
  try {
    const result = await mobileRequest(mobileMapRequestUrl(mapId, floorKey));
    if (generation !== mobileMapLoadGeneration) return;
    mobileMapView = result;
    mobileMapBaseWidth = 0;
    mobileMapBaseHeight = 0;
    renderMobileFloorOptions(result.floors, result.floor?.key);
    const preferences = readMobilePreferences();
    preferences.floors = preferences.floors || {};
    preferences.floors[mapId] = String(result.floor?.key || "");
    try {
      localStorage.setItem(mobileStorageKey(), JSON.stringify({
        mapId: mobileSelectedMapId,
        floors: preferences.floors,
        mapAnnotations: preferences.mapAnnotations || MOBILE_ANNOTATION_DEFAULTS,
        annotationFiltersCollapsed: preferences.annotationFiltersCollapsed === true,
        taskPanelHeightRatio: preferences.taskPanelHeightRatio ?? null,
      }));
    } catch {
      showMobileToast("浏览器无法保存本机地图选择。", "error");
    }
    sizeMobileMapCanvas();
    renderMobileMarkers();
    mobileElements.image.onload = () => {
      if (generation !== mobileMapLoadGeneration) return;
      mobileElements.image.hidden = false;
      mobileElements.mapLoading.hidden = true;
      sizeMobileMapCanvas();
    };
    mobileElements.image.onerror = () => {
      if (generation !== mobileMapLoadGeneration) return;
      mobileElements.image.hidden = true;
      mobileElements.mapLoading.hidden = true;
      setMobileMapError("地图底图载入失败。请检查网络后刷新。" + (result.detail_warnings?.length ? ` ${result.detail_warnings[0]}` : ""));
    };
    mobileElements.image.src = result.image_url;
    if (mobileElements.image.complete && mobileElements.image.naturalWidth) {
      mobileElements.image.onload?.(new Event("load"));
    }
    applyMobileMapTransform();
    if (mobileSelectedMarkerId) {
      const selected = [...(result.markers || []), ...(result.annotations || [])]
        .find((marker) => marker.id === mobileSelectedMarkerId);
      if (selected && mobileElements.pointDialog.open) openMobilePoint(selected);
    }
  } catch (error) {
    if (generation !== mobileMapLoadGeneration) return;
    mobileMapView = null;
    mobileElements.markers.replaceChildren();
    mobileElements.image.hidden = true;
    mobileElements.mapLoading.hidden = true;
    setMobileMapError(`任务地图载入失败：${error.message || "未知错误"}`);
  }
}

async function loadMobileMapIndex() {
  const result = await mobileRequest("/api/maps");
  mobileMapList = Array.isArray(result.maps) ? result.maps : [];
  const preferences = readMobilePreferences();
  const mapId = mobileMapList.some((map) => String(map.map_id) === String(preferences.mapId))
    ? String(preferences.mapId)
    : String(result.preferred_map_id || mobileMapList[0]?.map_id || "");
  renderMobileMapOptions(mapId);
  if (!mapId) {
    setMobileMapError("地图目录中没有可显示的地图。");
    return;
  }
  mobileSelectedMapId = mapId;
  const savedFloor = String(preferences.floors?.[mapId] || "");
  await loadMobileMap(mapId, savedFloor);
}

async function loadMobileState() {
  const next = await mobileRequest("/api/mobile/state");
  const profileChanged = mobileState && mobileState.selected_profile_id !== next.selected_profile_id;
  const previousActiveIds = activeMobileTasks().map((task) => String(task.id)).join(",");
  mobileState = next;
  applyMobileAnnotationPreferences();
  if (profileChanged) restoreMobileTaskPanelHeight();
  const selectedProfile = (next.profiles || []).find((profile) => profile.id === next.selected_profile_id);
  mobileElements.playerName.textContent = selectedProfile?.name || "档案";
  renderMobileTasks();
  if (profileChanged) {
    mobileMapList = [];
    mobileMapView = null;
    mobileSelectedMapId = "";
    await loadMobileMapIndex();
    return next;
  }
  const nextActiveIds = activeMobileTasks().map((task) => String(task.id)).join(",");
  if (mobileMapView && previousActiveIds !== nextActiveIds) {
    await loadMobileMap(mobileSelectedMapId, mobileElements.floorSelect.value);
  }
  return next;
}

async function initializeMobileSession() {
  mobileElements.gateRetry.disabled = true;
  showMobileGate("正在验证手机地图访问权限…");
  try {
    if (!mobilePairingAttempted) {
      const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
      const pairingToken = params.get("pair");
      if (pairingToken) {
        mobilePairingAttempted = true;
        history.replaceState(null, document.title, `${location.pathname}${location.search}`);
        await mobilePost("/api/auth/mobile-pair", { token: pairingToken });
      }
    }
    await loadMobileState();
    showMobileApp();
    let savedTheme = "dark";
    try {
      savedTheme = localStorage.getItem("eft-task-assistant-theme") || "dark";
    } catch {
      savedTheme = "dark";
    }
    applyMobileTheme(savedTheme);
    if (!mobileMapList.length) {
      try {
        await loadMobileMapIndex();
      } catch (error) {
        setMobileMapError(`地图目录载入失败：${error.message || "未知错误"}`);
      }
    }
    clearInterval(mobileRefreshTimer);
    mobileRefreshTimer = setInterval(() => {
      loadMobileState().catch(handleMobileSessionError);
    }, MOBILE_REFRESH_INTERVAL);
  } catch (error) {
    showMobileGate(error.status === 401
      ? (mobilePairingAttempted ? "二维码无效或已过期，请回到电脑端重新生成。" : "请扫描电脑端生成的二维码，只读查看地图和任务；无需账号。")
      : error.message || "手机地图访问验证失败，请回到电脑端重新生成二维码。", true);
  } finally {
    mobileElements.gateRetry.disabled = false;
  }
}

function handleMobileSessionError(error) {
  if (error?.status === 401) {
    clearInterval(mobileRefreshTimer);
    mobileRefreshTimer = null;
    showMobileGate("手机地图访问已失效，请从电脑端重新扫描二维码。", true);
  } else if (error) {
    showMobileToast(error.message || "同步失败，请稍后重试。", "error");
  }
}

function safeMobileExternalUrl(value) {
  try {
    const url = new URL(value, location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

function safeMobilePointImageUrl(value) {
  try {
    const url = new URL(value, "https://assets.tarkov.dev");
    const approvedAsset = url.hostname === "assets.tarkov.dev"
      && /^\/(?:[A-Za-z0-9._/-]+)\.(?:webp|png|jpe?g)$/i.test(url.pathname);
    const approvedPointPhoto = url.hostname === "www.eftarkov.com"
      && /^\/uploads\/infoImg\/[A-Za-z0-9_-]+\.(?:webp|png|jpe?g)$/i.test(url.pathname);
    if (url.protocol !== "https:" || url.username || url.password || url.port
      || url.search || url.hash || !(approvedAsset || approvedPointPhoto)
      || url.pathname.split("/").includes("..")) return "";
    return url.href;
  } catch {
    return "";
  }
}

function applyMobileTheme(theme) {
  const normalizedTheme = theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = normalizedTheme;
  mobileElements.theme.textContent = normalizedTheme === "light" ? "☾" : "☼";
  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) themeColor.content = normalizedTheme === "light" ? "#f5f5f7" : "#000000";
}

function appendMobileMeta(label, value) {
  const text = String(value || "").trim();
  if (!text) return;
  const row = document.createElement("p");
  row.className = "point-meta-row";
  const heading = document.createElement("strong");
  heading.textContent = `${label}：`;
  const detail = document.createElement("span");
  detail.textContent = text;
  row.append(heading, detail);
  mobileElements.pointMeta.append(row);
}

function openMobilePoint(marker) {
  mobileSelectedMarkerId = marker.id;
  const task = (mobileMapView?.tasks || []).find((item) => String(item.id) === String(marker.task_id));
  const isMapAnnotation = Array.isArray(marker.categories);
  mobileElements.pointTask.textContent = isMapAnnotation
    ? (marker.annotation_label || "地图标注")
    : [task?.trader, marker.task_title || "任务"].filter(Boolean).join(" · ");
  mobileElements.pointTitle.textContent = marker.title || "任务点位";
  mobileElements.pointLocation.textContent = [mobileMapView?.map_name, marker.floor_name].filter(Boolean).join(" · ");
  mobileElements.pointDescription.textContent = marker.description || "";
  mobileElements.pointDescription.hidden = !marker.description;
  mobileElements.pointMeta.replaceChildren();
  appendMobileMeta("需要物品", marker.key_name);
  appendMobileMeta("获取方式", marker.key_acquisition);
  mobileElements.pointImages.replaceChildren();
  const images = [...new Set([
    ...(Array.isArray(marker.source_image_urls) ? marker.source_image_urls : []),
    marker.source_image_url,
  ].map(safeMobilePointImageUrl).filter(Boolean))];
  for (const [index, url] of images.entries()) {
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    const image = document.createElement("img");
    image.src = url;
    image.alt = `${marker.title || "任务点位"} · ${index + 1}`;
    image.loading = "lazy";
    image.referrerPolicy = "no-referrer";
    image.addEventListener("error", () => {
      const failure = document.createElement("p");
      failure.className = "map-point-image-load-error";
      failure.textContent = "图片暂时无法加载";
      link.replaceWith(failure);
    }, { once: true });
    link.append(image);
    mobileElements.pointImages.append(link);
  }
  const sourceUrl = safeMobileExternalUrl(marker.source_image_page_url || marker.source_page_url || marker.source_url);
  mobileElements.pointSource.href = sourceUrl;
  mobileElements.pointSource.hidden = !sourceUrl;
  if (!mobileElements.pointDialog.open) mobileElements.pointDialog.showModal();
}

mobileElements.gateRetry.addEventListener("click", initializeMobileSession);
mobileElements.annotationFilters.addEventListener("change", (event) => {
  if (!event.target.matches("input[data-map-annotation-filter]")) return;
  saveMobilePreferences();
  renderMobileMarkers();
});
mobileElements.annotationFilters.addEventListener("toggle", saveMobilePreferences);
mobileElements.mapSelect.addEventListener("change", () => {
  mobilePanX = 0;
  mobilePanY = 0;
  setMobileMapZoom(1);
  const mapId = mobileElements.mapSelect.value;
  saveMobilePreferences();
  const preferences = readMobilePreferences();
  loadMobileMap(mapId, String(preferences.floors?.[mapId] || ""));
});
mobileElements.floorSelect.addEventListener("change", () => {
  if (!mobileSelectedMapId) return;
  const preferences = readMobilePreferences();
  preferences.floors = preferences.floors || {};
  preferences.floors[mobileSelectedMapId] = mobileElements.floorSelect.value;
  try {
    localStorage.setItem(mobileStorageKey(), JSON.stringify({
      mapId: mobileSelectedMapId,
      floors: preferences.floors,
      mapAnnotations: preferences.mapAnnotations || MOBILE_ANNOTATION_DEFAULTS,
      annotationFiltersCollapsed: preferences.annotationFiltersCollapsed === true,
      taskPanelHeightRatio: preferences.taskPanelHeightRatio ?? null,
    }));
  } catch {
    showMobileToast("浏览器无法保存本机地图选择。", "error");
  }
  loadMobileMap(mobileSelectedMapId, mobileElements.floorSelect.value);
});
mobileElements.zoomOut.addEventListener("click", () => setMobileMapZoom(mobileZoom - 0.2));
mobileElements.zoomIn.addEventListener("click", () => setMobileMapZoom(mobileZoom + 0.2));
mobileElements.zoomReset.addEventListener("click", () => setMobileMapZoom(1, true));
mobileElements.immersiveToggle.addEventListener("click", () => {
  const immersive = !mobileElements.app.classList.contains("is-map-immersive");
  mobileElements.app.classList.toggle("is-map-immersive", immersive);
  mobileElements.immersiveToggle.setAttribute("aria-pressed", String(immersive));
  mobileElements.immersiveToggle.setAttribute("aria-label", immersive ? "退出地图沉浸模式" : "沉浸显示地图");
  mobileElements.immersiveToggle.title = immersive ? "退出地图沉浸模式" : "沉浸显示地图";
  mobileElements.immersiveToggle.textContent = immersive ? "×" : "⛶";
  requestAnimationFrame(sizeMobileMapCanvas);
});
mobileElements.refresh.addEventListener("click", async () => {
  mobileElements.refresh.disabled = true;
  try {
    await loadMobileState();
    if (mobileSelectedMapId) await loadMobileMap(mobileSelectedMapId, mobileElements.floorSelect.value);
    showMobileToast("地图与任务已刷新。");
  } catch (error) {
    handleMobileSessionError(error);
  } finally {
    mobileElements.refresh.disabled = false;
  }
});
mobileElements.theme.addEventListener("click", () => {
  const nextTheme = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  applyMobileTheme(nextTheme);
  try {
    localStorage.setItem("eft-task-assistant-theme", nextTheme);
  } catch {
    showMobileToast("浏览器无法保存主题设置。", "error");
  }
});
mobileElements.logout.addEventListener("click", async () => {
  mobileElements.logout.disabled = true;
  try {
    await mobilePost("/api/auth/logout");
    clearInterval(mobileRefreshTimer);
    mobileRefreshTimer = null;
    mobileState = null;
    mobileMapList = [];
    mobileMapView = null;
    mobileSelectedMapId = "";
    showMobileGate("手机访问已结束。再次使用时，请扫描电脑端二维码。", true);
  } catch (error) {
    showMobileToast(error.message, "error");
  } finally {
    mobileElements.logout.disabled = false;
  }
});
mobileElements.pointClose.addEventListener("click", () => mobileElements.pointDialog.close());
mobileElements.pointDialog.addEventListener("click", (event) => {
  if (event.target === mobileElements.pointDialog) mobileElements.pointDialog.close();
});

mobileElements.taskPanelResizer.addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || mobileUsesTabletLayout()) return;
  mobileTaskPanelDrag = {
    pointerId: event.pointerId,
    startY: event.clientY,
    startHeight: mobileElements.taskPanel.getBoundingClientRect().height,
  };
  mobileElements.taskPanelResizer.classList.add("is-dragging");
  mobileElements.taskPanelResizer.setPointerCapture(event.pointerId);
  event.preventDefault();
});
mobileElements.taskPanelResizer.addEventListener("pointermove", (event) => {
  if (mobileTaskPanelDrag?.pointerId !== event.pointerId) return;
  setMobileTaskPanelHeight(mobileTaskPanelDrag.startHeight + mobileTaskPanelDrag.startY - event.clientY, true);
  event.preventDefault();
});
const finishMobileTaskPanelResize = (event) => {
  if (mobileTaskPanelDrag?.pointerId !== event.pointerId) return;
  mobileTaskPanelDrag = null;
  mobileElements.taskPanelResizer.classList.remove("is-dragging");
  if (mobileElements.taskPanelResizer.hasPointerCapture(event.pointerId)) {
    mobileElements.taskPanelResizer.releasePointerCapture(event.pointerId);
  }
  saveMobilePreferences();
};
mobileElements.taskPanelResizer.addEventListener("pointerup", finishMobileTaskPanelResize);
mobileElements.taskPanelResizer.addEventListener("pointercancel", finishMobileTaskPanelResize);
mobileElements.taskPanelResizer.addEventListener("lostpointercapture", finishMobileTaskPanelResize);
mobileElements.taskPanelResizer.addEventListener("keydown", (event) => {
  if (mobileUsesTabletLayout()) return;
  const currentHeight = mobileElements.taskPanel.getBoundingClientRect().height;
  const bounds = mobileTaskPanelHeightBounds();
  const nextHeight = event.key === "ArrowUp" ? currentHeight + 16
    : event.key === "ArrowDown" ? currentHeight - 16
      : event.key === "Home" ? bounds.min
        : event.key === "End" ? bounds.max
          : null;
  if (nextHeight == null) return;
  event.preventDefault();
  setMobileTaskPanelHeight(nextHeight, true);
  saveMobilePreferences();
});

mobileElements.viewport.addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || event.target.closest("button")) return;
  mobilePointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
  mobileElements.viewport.setPointerCapture(event.pointerId);
  if (mobilePointers.size === 2) {
    const points = [...mobilePointers.values()];
    mobilePinchStart = {
      distance: Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y),
      zoom: mobileZoom,
    };
    mobileMapDragging = null;
  } else {
    mobileMapDragging = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, panX: mobilePanX, panY: mobilePanY };
  }
});
mobileElements.viewport.addEventListener("pointermove", (event) => {
  if (!mobilePointers.has(event.pointerId)) return;
  mobilePointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
  if (mobilePointers.size >= 2 && mobilePinchStart) {
    const points = [...mobilePointers.values()];
    const distance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
    if (mobilePinchStart.distance > 0) setMobileMapZoom(mobilePinchStart.zoom * distance / mobilePinchStart.distance);
    event.preventDefault();
  } else if (mobileMapDragging?.pointerId === event.pointerId) {
    mobilePanX = mobileMapDragging.panX + event.clientX - mobileMapDragging.x;
    mobilePanY = mobileMapDragging.panY + event.clientY - mobileMapDragging.y;
    applyMobileMapTransform();
    event.preventDefault();
  }
});
const finishMobilePan = (event) => {
  mobilePointers.delete(event.pointerId);
  if (mobileElements.viewport.hasPointerCapture(event.pointerId)) mobileElements.viewport.releasePointerCapture(event.pointerId);
  if (mobilePointers.size < 2) mobilePinchStart = null;
  mobileMapDragging = mobilePointers.size === 1
    ? { pointerId: [...mobilePointers.keys()][0], ...mobilePointers.values().next().value, panX: mobilePanX, panY: mobilePanY }
    : null;
};
mobileElements.viewport.addEventListener("pointerup", finishMobilePan);
mobileElements.viewport.addEventListener("pointercancel", finishMobilePan);
mobileElements.viewport.addEventListener("lostpointercapture", finishMobilePan);
window.addEventListener("resize", () => {
  updateMobileDeviceType();
  sizeMobileMapCanvas();
  if (mobileTaskPanelHeightRatio != null) {
    setMobileTaskPanelHeight(mobileElements.app.clientHeight * mobileTaskPanelHeightRatio);
  }
}, { passive: true });
new ResizeObserver((entries) => {
  const width = entries[0]?.contentRect.width ?? mobileElements.viewport.clientWidth;
  if (Math.abs(width - mobileObservedMapViewportWidth) > 1 || !mobileMapBaseWidth) {
    mobileObservedMapViewportWidth = width;
    sizeMobileMapCanvas();
  }
}).observe(mobileElements.viewport);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && mobileState) {
    loadMobileState().catch(handleMobileSessionError);
    if (mobileSelectedMapId) loadMobileMap(mobileSelectedMapId, mobileElements.floorSelect.value);
  }
});

initializeMobileSession();
