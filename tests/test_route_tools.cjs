const assert = require("node:assert/strict");
const { test } = require("node:test");
const routes = require("../web/route_tools.js");

test("legacy lines retain all points with stable identity and default appearance", () => {
  const points = [[.1, .2], [.3, .4]];
  const first = routes.normalizeStroke(points, 2);
  assert.deepEqual(first.points, points);
  assert.equal(first.color, "#e5484d");
  assert.equal(first.width, 4);
  assert.equal(first.id, routes.normalizeStroke(points, 2).id);
  assert.notEqual(first.id, routes.normalizeStroke(points, 3).id);
  assert.deepEqual(points, [[.1, .2], [.3, .4]]);
});

test("source map and floor scopes roundtrip without mixing", () => {
  const scopes = [
    { source: "tarkov.dev", map_id: "factory", floor_key: "Ground_Floor" },
    { source: "eftarkov", map_id: "factory", floor_key: "1" },
    { source: "tarkov.dev", map_id: "factory", floor_key: "Second_Floor" },
  ];
  assert.equal(new Set(scopes.map(routes.scopeKey)).size, 3);
  for (const scope of scopes) assert.deepEqual(routes.parseScopeKey(routes.scopeKey(scope)), scope);
  assert.deepEqual(routes.parseScopeKey("eftarkov:factory"), { source: "eftarkov", map_id: "factory", floor_key: "" });
  assert.deepEqual(routes.parseScopeKey("factory"), { source: "tarkov.dev", map_id: "factory", floor_key: "" });
});

test("invalid geometry is rejected without changing good lines", () => {
  for (const points of [[[0, 0]], [[NaN, 0], [1, 1]], [[0, 0], [Infinity, 1]], [[0, 0], [2, 1]]]) {
    assert.equal(routes.normalizeStroke(points), null);
  }
  const stroke = { id: "source:stroke.1", points: [[0, 0], [1, 1]], width: 6, color: "#007AFF" };
  assert.deepEqual(routes.normalizeStroke(stroke), { ...stroke, color: "#007aff" });
});

test("desktop and mobile use identical paths colors and widths at unit zoom", () => {
  function svg() {
    return { paths: [], ownerDocument: { createElementNS() { return { dataset: {}, attributes: {}, setAttribute(key, value) { this.attributes[key] = value; } }; } },
      append(element) { this.paths.push(element); }, replaceChildren() { this.paths = []; } };
  }
  const desktop = svg();
  const mobile = svg();
  const strokes = [{ id: "colored", points: [[.2, .3], [.8, .9]], width: 6, color: "#007aff" }];
  routes.render(desktop, strokes);
  routes.render(mobile, strokes);
  assert.deepEqual(desktop.paths.map(path => path.attributes), mobile.paths.map(path => path.attributes));
  assert.equal(desktop.paths[1].attributes.stroke, "#007aff");
  assert.equal(desktop.paths[1].attributes["stroke-width"], "6");
  assert.equal(desktop.paths[1].attributes.d, "M20.000 30.000 L80.000 90.000");
});
