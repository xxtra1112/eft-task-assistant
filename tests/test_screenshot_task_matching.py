import threading
import unittest
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from recognition import ScreenAnalysis, ScreenKind
from web_server import AssistantState, _match_screenshot_task_candidates


class ScreenshotTaskMatchingTests(unittest.TestCase):
    def setUp(self):
        self.catalog_task = {
            "snapshot_id": 2,
            "source_task_id": "5a68665c86f774255929b4c7",
            "trader": "Therapist",
            "title": "医疗隐私 - 3",
            "source_url": "https://www.eftarkov.com/task/5a68665c86f774255929b4c7",
            "source_version": "1.1.5.1",
        }
        self.analysis = ScreenAnalysis(
            kind=ScreenKind.TRADER_TASKS,
            trader="Therapist",
            text_lines=["医疗隐私-3"],
            task_page_confident=True,
            diagnostics={
                "task_list_ocr": [
                    {
                        "text": "医疗隐私-3",
                        "confidence": 0.973,
                        "bounds": [117, 1194, 260, 1221],
                    }
                ]
            },
        )

    def test_tracked_task_is_reported_as_recognized_without_becoming_new(self):
        tracked_task = SimpleNamespace(
            trader="Therapist",
            title="医疗隐私 - 3",
            source_task_id=self.catalog_task["source_task_id"],
        )

        matches = _match_screenshot_task_candidates(
            self.analysis,
            [self.catalog_task],
            [tracked_task],
            "capture-1",
            2,
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["title"], "医疗隐私 - 3")
        self.assertTrue(matches[0]["already_tracked"])
        self.assertEqual(matches[0]["recognized_text"], "医疗隐私-3")

    def test_untracked_task_remains_eligible_for_auto_import(self):
        matches = _match_screenshot_task_candidates(
            self.analysis,
            [self.catalog_task],
            [],
            "capture-2",
            2,
        )

        self.assertEqual(len(matches), 1)
        self.assertFalse(matches[0]["already_tracked"])

    def test_capture_reports_tracked_match_without_queuing_import(self):
        candidate = {
            "source_task_id": self.catalog_task["source_task_id"],
            "title": "医疗隐私 - 3",
            "trader": "Therapist",
            "recognized_text": "医疗隐私-3",
            "image_order": 1,
            "match_score": 1.0,
            "ocr_confidence": 0.973,
            "already_tracked": True,
        }
        record = {"id": "capture-3", "state": "queued", "task_candidates": []}
        assistant = object.__new__(AssistantState)
        assistant.lock = threading.RLock()
        assistant.capture_records = OrderedDict([("capture-3", record)])
        assistant.analyzer = SimpleNamespace(
            analyze=lambda image, capture_id: self.analysis
        )
        assistant.screenshot_task_candidates = lambda analysis, profile_id, capture_id: [candidate]
        assistant.store = SimpleNamespace(save_pending_task_candidates=lambda candidates: setattr(
            assistant.store, "saved_pending", list(candidates)
        ))
        assistant._persist_capture_locked = lambda capture: None
        assistant._prune_capture_records_locked = lambda: None

        with patch("web_server.log_event"):
            assistant._capture_and_analyze("capture-3", 2, np.zeros((1, 1, 3), dtype=np.uint8))

        self.assertEqual(record["state"], "done")
        self.assertEqual(record["task_candidates"][0]["notification_status"], "already_tracked")
        self.assertEqual(
            record["analysis"].warning.encode("unicode_escape").decode("ascii"),
            r"\u53e6\u5916\u8bc6\u522b\u5230 1 \u4e2a\u5df2\u5728\u6e05\u5355\u7684\u4efb\u52a1\uff0c\u4e0d\u4f1a\u91cd\u590d\u6dfb\u52a0\u3002",
        )
        self.assertEqual(assistant.store.saved_pending, [])

    def test_capture_keeps_catalogless_screenshot_queued_for_matching(self):
        record = {"id": "capture-pending", "state": "queued", "task_candidates": []}
        assistant = object.__new__(AssistantState)
        assistant.lock = threading.RLock()
        assistant.capture_records = OrderedDict([("capture-pending", record)])
        assistant.catalog_pending_captures = {("capture-pending", 2)}
        assistant.analyzer = SimpleNamespace(analyze=lambda image, capture_id: self.analysis)
        assistant.screenshot_task_candidates = lambda analysis, profile_id, capture_id: []
        assistant.store = SimpleNamespace(save_pending_task_candidates=lambda candidates: setattr(
            assistant.store, "saved_pending", list(candidates)
        ))
        assistant._persist_capture_locked = lambda capture: None
        assistant._prune_capture_records_locked = lambda: None

        with patch("web_server.log_event"):
            assistant._capture_and_analyze(
                "capture-pending", 2, np.zeros((1, 1, 3), dtype=np.uint8)
            )

        self.assertEqual(record["state"], "done")
        self.assertTrue(record["analysis"].diagnostics["catalog_match_pending"])
        self.assertIn("目录尚未就绪", record["analysis"].warning)
        self.assertEqual(record["task_candidates"], [])

    def test_catalog_sync_retries_and_queues_matching_screenshot(self):
        candidate = {
            "source_task_id": self.catalog_task["source_task_id"],
            "title": self.catalog_task["title"],
            "trader": self.catalog_task["trader"],
            "recognized_text": "医疗隐私-3",
            "image_order": 1,
            "match_score": 1.0,
            "ocr_confidence": 0.973,
        }
        analysis = ScreenAnalysis(
            kind=ScreenKind.TRADER_TASKS,
            trader="Therapist",
            text_lines=["医疗隐私-3"],
            task_page_confident=True,
            warning="目录尚未就绪；截图已保存，目录同步后会自动补匹配。",
            diagnostics={"catalog_match_pending": True},
        )
        record = {
            "id": "capture-retry",
            "profile_id": 2,
            "analysis": analysis,
            "task_candidates": [],
        }
        assistant = object.__new__(AssistantState)
        assistant.lock = threading.RLock()
        assistant.catalog_pending_captures = {("capture-retry", 2)}
        assistant.capture_records = OrderedDict([("capture-retry", record)])
        assistant.profiles = lambda: [SimpleNamespace(id=2, game_mode="pve")]
        assistant.screenshot_task_candidates = lambda analysis, profile_id, capture_id: [
            dict(candidate)
        ]
        assistant.store = SimpleNamespace(save_pending_task_candidates=lambda candidates: setattr(
            assistant.store, "saved_pending", list(candidates)
        ))
        assistant._persist_capture_locked = lambda capture: None
        assistant.catalog_executor = SimpleNamespace(
            submit=lambda function, *args: setattr(
                assistant, "submitted_details", (function.__name__, args)
            )
        )
        assistant._load_screenshot_candidate_details = lambda *args: None

        with patch("web_server.log_event"):
            assistant._retry_catalog_pending_captures("pve")

        self.assertEqual(len(record["task_candidates"]), 1)
        self.assertEqual(record["task_candidates"][0]["notification_status"], "processing")
        self.assertNotIn("catalog_match_pending", record["analysis"].diagnostics)
        self.assertIn("正在自动加入清单", record["analysis"].warning)
        self.assertEqual(assistant.catalog_pending_captures, set())
        self.assertEqual(assistant.store.saved_pending[0]["source_task_id"], candidate["source_task_id"])
        self.assertEqual(assistant.submitted_details[1], ("capture-retry", 2))

    def test_non_task_capture_completes_without_candidates(self):
        analysis = ScreenAnalysis(
            kind=ScreenKind.EQUIPMENT,
            trader=None,
            text_lines=[],
        )
        record = {"id": "capture-4", "state": "queued", "task_candidates": []}
        assistant = object.__new__(AssistantState)
        assistant.lock = threading.RLock()
        assistant.capture_records = OrderedDict([("capture-4", record)])
        assistant.analyzer = SimpleNamespace(analyze=lambda image, capture_id: analysis)
        assistant.store = SimpleNamespace(save_pending_task_candidates=lambda candidates: setattr(
            assistant.store, "saved_pending", list(candidates)
        ))
        assistant._persist_capture_locked = lambda capture: None
        assistant._prune_capture_records_locked = lambda: None

        with patch("web_server.log_event"):
            assistant._capture_and_analyze("capture-4", 2, np.zeros((1, 1, 3), dtype=np.uint8))

        self.assertEqual(record["state"], "done")
        self.assertEqual(record["task_candidates"], [])
        self.assertEqual(assistant.store.saved_pending, [])


if __name__ == "__main__":
    unittest.main()
