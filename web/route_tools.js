(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.EftRouteTools = api;
})(typeof globalThis === "undefined" ? null : globalThis, function () {
  const DEFAULT_COLOR = "#e5484d";
  const DEFAULT_WIDTH = 4;

  function scopeKey(scope) {
    return "route-v2:" + JSON.stringify([scope.source, scope.map_id, scope.floor_key || ""]);
  }

  function parseScopeKey(value) {
    if (typeof value !== "string") return null;
    if (value.startsWith("route-v2:")) {
      try {
        const parts = JSON.parse(value.slice(9));
        if (!Array.isArray(parts) || parts.length !== 3 || !parts.every(part => typeof part === "string")) return null;
        if (!["tarkov.dev", "eftarkov", "reemr"].includes(parts[0])) return null;
        return { source: parts[0], map_id: parts[1], floor_key: parts[2] };
      } catch {
        return null;
      }
    }
    const match = value.match(/^(tarkov\.dev|eftarkov|reemr):(.+)$/);
    return { source: match ? match[1] : "tarkov.dev", map_id: match ? match[2] : value, floor_key: "" };
  }

  function pointHash(points) {
    let hash = 2166136261;
    for (const character of JSON.stringify(points)) hash = Math.imul(hash ^ character.charCodeAt(0), 16777619);
    return (hash >>> 0).toString(16);
  }

  function normalizeStroke(value, index = 0) {
    const legacy = Array.isArray(value);
    const points = legacy ? value : value?.points;
    if (!Array.isArray(points) || points.length < 2 || points.length > 1000) return null;
    if (!points.every(point => Array.isArray(point) && point.length === 2
      && point.every(coordinate => typeof coordinate === "number" && Number.isFinite(coordinate) && coordinate >= 0 && coordinate <= 1))) return null;
    const color = /^#[0-9a-f]{6}$/i.test(value?.color || "") ? value.color.toLowerCase() : DEFAULT_COLOR;
    const width = [2, 4, 6].includes(value?.width) ? value.width : DEFAULT_WIDTH;
    const id = typeof value?.id === "string" && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/.test(value.id)
      ? value.id : `legacy-${pointHash(points)}-${index}`;
    return { id, points: points.map(point => [...point]), color, width };
  }

  function normalizeStrokes(values) {
    return Array.isArray(values) ? values.map(normalizeStroke).filter(Boolean) : [];
  }

  function appendStroke(svg, value, scale = 1) {
    const stroke = normalizeStroke(value);
    if (!stroke) return null;
    const pathData = stroke.points.map((point, index) =>
      `${index ? "L" : "M"}${(point[0] * 100).toFixed(3)} ${(point[1] * 100).toFixed(3)}`).join(" ");
    const paths = {};
    for (const [name, color, width] of [["outline", "#ffffff", stroke.width + 2], ["line", stroke.color, stroke.width]]) {
      const element = svg.ownerDocument.createElementNS("http://www.w3.org/2000/svg", "path");
      element.dataset.strokeId = stroke.id;
      element.dataset.strokeWidth = String(stroke.width);
      element.setAttribute("class", "route-" + name);
      element.setAttribute("d", pathData);
      element.setAttribute("fill", "none");
      element.setAttribute("stroke", color);
      element.setAttribute("stroke-width", String(width / Math.max(.1, scale)));
      element.setAttribute("stroke-opacity", name === "outline" ? ".75" : "1");
      element.setAttribute("stroke-linecap", "round");
      element.setAttribute("stroke-linejoin", "round");
      element.setAttribute("vector-effect", "non-scaling-stroke");
      svg.append(element);
      paths[name] = element;
    }
    return paths;
  }

  function render(svg, strokes, scale = 1) {
    svg.replaceChildren();
    for (const stroke of normalizeStrokes(strokes)) appendStroke(svg, stroke, scale);
  }

  return { DEFAULT_COLOR, DEFAULT_WIDTH, scopeKey, parseScopeKey, normalizeStroke, normalizeStrokes, appendStroke, render, fingerprint: pointHash };
});
