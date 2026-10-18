from tarkov_dev_catalog import _catalog_bundle, _task_details


TASK_ID = "0123456789abcdef01234567"
TRADER_ID = "1123456789abcdef01234567"
KEY_ID = "2123456789abcdef01234567"
MAP_ID = "3123456789abcdef01234567"
OBJECTIVE_ID = "objective-description-key"


def test_catalog_bundle_localizes_task_and_trader():
    task = {
        TASK_ID: {
            "id": TASK_ID,
            "name": f"{TASK_ID} name",
            "trader": TRADER_ID,
            "normalizedName": "test-task",
        }
    }
    traders = {TRADER_ID: {"name": f"{TRADER_ID} Nickname", "normalizedName": "therapist"}}

    bundle = _catalog_bundle(
        "pve",
        task,
        {f"{TASK_ID} name": "测试任务"},
        {},
        traders,
        {f"{TRADER_ID} Nickname": "治疗师"},
        {},
    )

    assert bundle.game_mode == "pve"
    assert bundle.source_version == ""
    assert bundle.tasks[0]["title"] == "测试任务"
    assert bundle.tasks[0]["trader"] == "治疗师"
    assert bundle.tasks[0]["source_task_id"] == TASK_ID
    assert bundle.tasks[0]["source_url"].endswith(f"/task/{TASK_ID}")
    assert bundle.metadata["game_patch_coverage"] == "unknown"
    assert len(bundle.content_sha256) == 64


def test_task_details_normalize_objectives_and_required_keys():
    currency_id = "4123456789abcdef01234567"
    raw_task = {
        "id": TASK_ID,
        "name": f"{TASK_ID} name",
        "normalizedName": "test-task",
        "taskRequirements": [{"task": "5123456789abcdef01234567"}],
        "neededKeys": [{"map": MAP_ID, "keys": [KEY_ID]}],
        "objectives": [
            {
                "description": OBJECTIVE_ID,
                "type": "findItem",
                "count": 3,
                "optional": True,
                "maps": [MAP_ID],
            }
        ],
    }
    traders = {TRADER_ID: {"name": "trader-name", "normalizedName": "therapist"}}
    items = {
        KEY_ID: {
            "id": KEY_ID,
            "name": "key-name",
            "normalizedName": "office-key",
            "types": ["keys"],
            "iconLink": "https://assets.tarkov.dev/key-icon.webp",
            "buyFromTrader": [
                {
                    "trader": TRADER_ID,
                    "priceRUB": 12000,
                    "currencyItem": currency_id,
                    "minTraderLevel": 2,
                }
            ],
        },
        currency_id: {"id": currency_id, "name": "rouble-name", "normalizedName": "roubles"},
    }

    result = _task_details(
        raw_task,
        {OBJECTIVE_ID: "找到三瓶水"},
        {},
        {TASK_ID: raw_task, "5123456789abcdef01234567": {"name": "prerequisite-name"}},
        traders,
        {"trader-name": "治疗师"},
        {},
        items,
        {"key-name": "办公室钥匙", "rouble-name": "卢布"},
        {},
        [],
        [{"id": "map-point"}],
    )

    assert result["objectives"] == [
        {"text": "找到三瓶水", "optional": True, "target_count": 3}
    ]
    assert result["prerequisites"] == [
        {"task_id": "5123456789abcdef01234567", "text": "prerequisite-name"}
    ]
    assert result["key_requirements"][0]["name"] == "办公室钥匙"
    assert result["key_requirements"][0]["map_ids"] == [MAP_ID]
    assert result["key_requirements"][0]["image_url"].endswith("key-icon.webp")
    assert result["key_requirements"][0]["acquisition_methods"][0] == {
        "type": "purchase",
        "trader": "治疗师",
        "loyalty_level": "LL 2",
        "requirements": "购买 12,000 卢布",
    }
    assert result["map_points"] == [{"id": "map-point"}]


def test_task_details_exclude_items_not_categorized_as_keys():
    raw_task = {
        "id": TASK_ID,
        "neededKeys": [{"map": MAP_ID, "keys": [KEY_ID]}],
        "objectives": [{"description": OBJECTIVE_ID, "type": "visit"}],
    }

    result = _task_details(
        raw_task,
        {OBJECTIVE_ID: "前往地点"},
        {},
        {TASK_ID: raw_task},
        {},
        {},
        {},
        {KEY_ID: {"name": "not-a-key", "types": ["magazines"]}},
        {"not-a-key": "弹匣"},
        {},
        [],
        [],
    )

    assert result["key_requirements"] == []
