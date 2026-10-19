import xml.etree.ElementTree as ET

import tarkov_dev_maps


MAP_ID = "3123456789abcdef01234567"
TASK_ID = "0123456789abcdef01234567"


def _map_context():
    viewer = {
        "projection": "interactive",
        "transform": [1, 0, 1, 0],
        "coordinateRotation": 0,
        "bounds": [[0, 0], [100, 100]],
        "svgPath": "https://assets.tarkov.dev/maps/svg/Test.svg",
        "svgLayer": "Ground_Level",
        "heightRange": [-10, 10],
        "layers": [
            {
                "name": "Upper Floor",
                "svgLayer": "Second_Floor",
                "extents": [{"height": [1, 5], "bounds": [[[0, 0], [100, 100]]]}],
            }
        ],
        "labels": [{"position": [15, 25, 2], "text": "test-location"}],
        "author": "Map author",
        "authorLink": "https://example.com/author",
    }
    map_record = {
        "map_id": MAP_ID,
        "name": "测试地图",
        "name_en": "Test Map",
        "normalized_name": "test-map",
        "source_url": "https://tarkov.dev/map/test-map",
        "map_author": "Map author",
        "map_author_url": "https://example.com/author",
        "map_license": "CC BY-NC-SA 4.0",
        "map_license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    }
    raw_map = {
        "extracts": [
            {
                "id": "extract-1",
                "name": "test-extract",
                "description": "extract-description",
                "faction": "pmc",
                "position": {"x": 15, "y": 2, "z": 25},
            },
            {
                "id": "extract-2",
                "name": "test-shared-extract",
                "faction": "shared",
                "position": {"x": 40, "y": 0, "z": 50},
            },
            {
                "id": "extract-3",
                "name": "unknown-extract",
                "position": {"x": 80, "y": 0, "z": 80},
            },
            {
                "id": "extract-out-of-bounds",
                "name": "outside-extract",
                "faction": "pmc",
                "position": {"x": 250, "y": 0, "z": 250},
            }
        ],
        "transits": [
            {
                "id": "transit-1",
                "description": "transit-description",
                "map": MAP_ID,
                "position": {"x": 60, "y": 0, "z": 70},
            }
        ],
    }
    return {
        "maps_by_id": {
            MAP_ID: {
                "raw": raw_map,
                "metadata": {"entry": {"normalizedName": "test-map"}, "viewer": viewer},
                "index": map_record,
            }
        },
        "map_index": [map_record],
        "translations_zh": {
            "test-location": "医疗区",
            "test-extract": "撤离点甲",
            "extract-description": "撤离点描述",
            "test-shared-extract": "共同撤离点",
            "unknown-extract": "其他撤离点",
            "transit-description": "转移点描述",
        },
        "translations_en": {
            "test-location": "Medical Area",
            "test-extract": "Extract Alpha",
            "extract-description": "Extract description",
            "test-shared-extract": "Shared Extract",
            "unknown-extract": "Other Extract",
            "outside-extract": "Outside Extract",
            "transit-description": "Transit description",
        },
    }


def test_project_map_position_applies_transform_and_normalizes_to_bounds():
    viewer = {"transform": [1, 0, 1, 0], "coordinateRotation": 0, "bounds": [[0, 0], [100, 100]]}

    assert tarkov_dev_maps.project_map_position({"x": 20, "y": 99, "z": 30}, viewer) == (20, 70)


def test_task_map_points_include_zones_and_possible_locations(monkeypatch):
    monkeypatch.setattr(tarkov_dev_maps, "_map_context", lambda _mode: _map_context())
    task = {
        "id": TASK_ID,
        "normalizedName": "sample-task",
        "objectives": [
            {
                "id": "objective-1",
                "description": "objective-text",
                "zones": [
                    {
                        "id": "zone-a",
                        "map": MAP_ID,
                        "position": {"x": 20, "y": 2, "z": 30},
                    }
                ],
                "possibleLocations": [
                    {
                        "map": MAP_ID,
                        "positions": [
                            {"x": 20, "y": 2, "z": 30},
                            {"x": 70, "y": 0, "z": 80},
                        ],
                    }
                ],
            }
        ],
    }

    points = tarkov_dev_maps.fetch_tarkov_dev_task_map_points(
        task,
        {"objective-text": "前往医疗区"},
        {"objective-text": "Visit the medical area"},
    )

    assert len(points) == 2
    assert points[0]["source_provider"] == "tarkov.dev"
    assert points[0]["title"] == "前往医疗区"
    assert points[0]["title_en"] == "Visit the medical area"
    assert points[0]["floor_key"] == "Second_Floor"
    assert points[0]["floor_name_en"] == "Upper Floor"
    assert points[0]["x_percent"] == 20
    assert points[0]["y_percent"] == 70
    assert points[1]["x_percent"] == 70


def test_map_data_includes_localized_annotations_and_artwork_attribution(monkeypatch):
    monkeypatch.setattr(tarkov_dev_maps, "_map_context", lambda _mode: _map_context())

    result = tarkov_dev_maps.fetch_tarkov_dev_map_data(MAP_ID)

    assert result["name"] == "测试地图"
    assert result["name_en"] == "Test Map"
    assert result["map_author"] == "Map author"
    assert result["map_license"] == "CC BY-NC-SA 4.0"
    assert result["unplaced_annotation_count"] == 1
    annotations = result["annotations"]
    location = next(item for item in annotations if "location" in item["categories"])
    assert location["title"] == "医疗区"
    assert location["title_en"] == "Medical Area"
    extract = next(item for item in annotations if "pmc-exit" in item["categories"])
    assert extract["title_en"] == "Extract Alpha"
    assert extract["description_en"] == "Extract description"
    unknown_extract = next(item for item in annotations if "unknown-exit" in item["categories"])
    assert unknown_extract["title_en"] == "Other Extract"
    assert unknown_extract["annotation_label_en"] == "Faction unconfirmed extract"
    assert unknown_extract["annotation_label"] == "阵营未确认的撤离点"
    transit = next(item for item in annotations if "transfer" in item["categories"])
    assert transit["title_en"] == "Transit description"


def test_selected_floor_svg_removes_other_floors_and_external_content():
    map_data = {
        "viewer": {"svgLayer": "Ground_Level"},
        "svg_layer": "Ground_Level",
    }
    floor = {"svg_layer": "Second_Floor"}
    source = b'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">
      <g id="Ground_Level"><rect onclick="alert(1)" width="1" height="1"/></g>
      <g id="Second_Floor"><image href="https://example.com/image.png"/></g>
      <g id="Other_Floor"><rect width="1" height="1"/></g>
      <foreignObject><div xmlns="http://www.w3.org/1999/xhtml">unsafe</div></foreignObject>
    </svg>'''

    output = tarkov_dev_maps._selected_floor_svg(source, map_data, floor)
    root = ET.fromstring(output)
    groups = {child.get("id"): child for child in root if child.tag.endswith("}g")}
    rendered = output.decode("utf-8")

    assert set(groups) == {"Ground_Level", "Second_Floor"}
    assert "onclick" not in rendered
    assert "https://example.com/image.png" not in rendered
    assert "foreignObject" not in rendered
    assert groups["Ground_Level"].get("opacity") == "0.32"
