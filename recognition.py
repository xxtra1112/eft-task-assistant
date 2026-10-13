from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from diagnostics import log_event


class ScreenKind(str, Enum):
    UNKNOWN = "未识别"
    EQUIPMENT = "角色装备"
    TRADER_TASKS = "商人任务"


@dataclass(frozen=True)
class OCRLine:
    text: str
    confidence: float
    bounds: tuple[int, int, int, int]
    region: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text[:100],
            "confidence": round(self.confidence, 3),
            "bounds": list(self.bounds),
            "region": self.region,
        }


@dataclass(frozen=True)
class ScreenAnalysis:
    kind: ScreenKind
    trader: str | None
    text_lines: list[str]
    task_page_confident: bool = False
    warning: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)


MERCHANT_CARD_ORDER = (
    "Prapor",
    "Therapist",
    "Fence",
    "Skier",
    "Peacekeeper",
    "Mechanic",
    "Ragman",
    "Jaeger",
    "Ref",
)

MERCHANT_ALIASES = {
    "Prapor": ("prapor", "прапор", "普拉波尔", "普里波尔", "帕拉波尔"),
    "Therapist": ("therapist", "терапевт", "治疗师", "药剂师", "塔拉皮斯特"),
    "Fence": ("fence", "фенс", "黑商"),
    "Skier": ("skier", "лыжник", "滑雪者"),
    "Peacekeeper": ("peacekeeper", "миротворец", "和平使者"),
    "Mechanic": ("mechanic", "механик", "机械师"),
    "Ragman": ("ragman", "рагман", "拉格曼"),
    "Jaeger": ("jaeger", "jager", "егерь", "猎人"),
    "Ref": ("ref", "реф", "裁判"),
}

TASK_TAB_TERMS = ("任务", "tasks", "missions")
EQUIPMENT_TAB_TERMS = ("装备", "equipment", "gear")

TRADER_TASK_TAB_REGION = (0.0, 0.01, 0.18, 0.06)
TASK_LIST_REGION = (0.0, 0.25, 0.30, 0.99)
CARD_X_START = 0.005
CARD_X_STEP = 0.066
CARD_WIDTH = 0.062
CARD_LABEL_REGION = (0.14, 0.207)
TRADER_NAME_LABEL_REGION = (0.135, 0.163)
OCR_REFERENCE_HEIGHT = 1440
OCR_MIN_SCALE = 0.5
OCR_MAX_SCALE = 2.0


def _normalize(value: str) -> str:
    return "".join(character.casefold() for character in value if character.isalnum())


def _matches_term(text: str, term: str) -> bool:
    if term.isascii():
        tokens = re.findall(r"[a-z0-9]+", text.casefold())
        return term.casefold() in tokens
    return _normalize(term) in _normalize(text)


class PageAnalyzer:
    def __init__(self) -> None:
        self._ocr: Any = None

    def _get_ocr(self) -> Any:
        if self._ocr is None:
            from rapidocr_onnxruntime import RapidOCR

            self._ocr = RapidOCR()
        return self._ocr

    @staticmethod
    def _ocr_scale(image_height: int) -> float:
        if image_height <= 0:
            raise ValueError("image height must be positive")
        return max(OCR_MIN_SCALE, min(OCR_MAX_SCALE, OCR_REFERENCE_HEIGHT / image_height))

    @staticmethod
    def _crop_bounds(
        image: np.ndarray, bounds: tuple[float, float, float, float]
    ) -> tuple[np.ndarray, tuple[int, int, int, int]]:
        height, width = image.shape[:2]
        left = max(0, min(width - 1, round(bounds[0] * width)))
        top = max(0, min(height - 1, round(bounds[1] * height)))
        right = max(left + 1, min(width, round(bounds[2] * width)))
        bottom = max(top + 1, min(height, round(bounds[3] * height)))
        return image[top:bottom, left:right], (left, top, right, bottom)

    def _ocr_region(
        self,
        image: np.ndarray,
        bounds: tuple[float, float, float, float],
        region: str,
    ) -> list[OCRLine]:
        crop, (left, top, _, _) = self._crop_bounds(image, bounds)
        scale = self._ocr_scale(image.shape[0])
        scale_x = scale_y = 1.0
        if scale != 1.0:
            import cv2

            interpolation = cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA
            original_height, original_width = crop.shape[:2]
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=interpolation)
            scale_x = crop.shape[1] / original_width
            scale_y = crop.shape[0] / original_height
        variants = [crop]
        if region == "task_list":
            import cv2

            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            enhanced = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
            variants.append(cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR))
        lines_by_text: dict[str, OCRLine] = {}
        for variant in variants:
            result, _ = self._get_ocr()(variant)
            for row in result or []:
                if len(row) < 2 or not row[1]:
                    continue
                text = str(row[1]).strip()
                if not text:
                    continue
                try:
                    points = np.asarray(row[0], dtype=float).reshape(-1, 2)
                    x0 = int(round(float(points[:, 0].min()) / scale_x)) + left
                    y0 = int(round(float(points[:, 1].min()) / scale_y)) + top
                    x1 = int(round(float(points[:, 0].max()) / scale_x)) + left
                    y1 = int(round(float(points[:, 1].max()) / scale_y)) + top
                    confidence = float(row[2]) if len(row) > 2 else 0.0
                except (TypeError, ValueError, IndexError):
                    continue
                line = OCRLine(text, confidence, (x0, y0, x1, y1), region)
                key = _normalize(text)
                previous = lines_by_text.get(key)
                if previous is None or line.confidence > previous.confidence:
                    lines_by_text[key] = line
        return list(lines_by_text.values())

    @staticmethod
    def _line_background_mean(image: np.ndarray, line: OCRLine) -> float:
        import cv2

        height, width = image.shape[:2]
        x0, y0, x1, y1 = line.bounds
        pad_x = max(12, round(width * 0.01))
        pad_y = max(7, round(height * 0.006))
        left = max(0, x0 - pad_x)
        top = max(0, y0 - pad_y)
        right = min(width, x1 + pad_x)
        bottom = min(height, y1 + pad_y)
        patch = image[top:bottom, left:right, :3]
        if patch.size == 0:
            return 0.0
        return float(cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY).mean())

    def _selected_tab(
        self,
        image: np.ndarray,
        lines: list[OCRLine],
        terms: tuple[str, ...],
    ) -> tuple[bool, list[dict[str, Any]]]:
        measured = [
            {
                "text": line.text,
                "bounds": list(line.bounds),
                "confidence": round(line.confidence, 3),
                "background_mean": round(self._line_background_mean(image, line), 1),
                "matches": [term for term in terms if _matches_term(line.text, term)],
            }
            for line in lines
        ]
        target_values = [entry["background_mean"] for entry in measured if entry["matches"]]
        other_values = [entry["background_mean"] for entry in measured if not entry["matches"]]
        if not target_values:
            return False, measured
        target_mean = max(target_values)
        competitor_mean = max(other_values, default=0.0)
        selected = target_mean >= 80.0 and target_mean - competitor_mean >= 18.0
        return selected, measured

    @staticmethod
    def _detect_active_trader(image: np.ndarray) -> tuple[str | None, list[dict[str, Any]], str]:
        import cv2

        image_bgr = image[:, :, :3]
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        y0 = round(CARD_LABEL_REGION[0] * height)
        y1 = round(CARD_LABEL_REGION[1] * height)
        results: list[dict[str, Any]] = []
        for index, trader in enumerate(MERCHANT_CARD_ORDER):
            x0 = round((CARD_X_START + index * CARD_X_STEP) * width)
            x1 = round((CARD_X_START + index * CARD_X_STEP + CARD_WIDTH) * width)
            x1 = min(width, x1)
            patch = gray[y0:y1, x0:x1]
            if patch.size == 0:
                continue
            results.append(
                {
                    "trader": trader,
                    "bounds": [x0, y0, x1, y1],
                    "mean_luminance": round(float(patch.mean()), 1),
                    "bright_fraction": round(float(np.count_nonzero(patch >= 110) / patch.size), 3),
                }
            )
        ranked = sorted(results, key=lambda entry: entry["mean_luminance"], reverse=True)
        if not ranked:
            return None, results, "trader card strip unavailable"
        first = ranked[0]
        second_score = ranked[1]["mean_luminance"] if len(ranked) > 1 else 0.0
        margin = first["mean_luminance"] - second_score
        if first["mean_luminance"] < 75.0:
            return None, results, "no selected trader card exceeded luminance threshold"
        if margin < 30.0:
            return None, results, f"selected trader card is ambiguous (margin={margin:.1f})"
        return first["trader"], results, f"selected card luminance={first['mean_luminance']:.1f}, margin={margin:.1f}"

    def _confirm_active_trader(
        self,
        image: np.ndarray,
        visual_trader: str,
        card_scores: list[dict[str, Any]],
    ) -> tuple[str | None, list[OCRLine], str]:
        selected_card = next(
            (entry for entry in card_scores if entry["trader"] == visual_trader), None
        )
        if selected_card is None:
            return None, [], "merchant card bounds unavailable"

        height, width = image.shape[:2]
        left, _, right, _ = selected_card["bounds"]
        padding = max(2, round(width * 0.004))
        top = round(TRADER_NAME_LABEL_REGION[0] * height)
        bottom = round(TRADER_NAME_LABEL_REGION[1] * height)
        lines = self._ocr_region(
            image,
            (
                max(0, left - padding) / width,
                top / height,
                min(width, right + padding) / width,
                bottom / height,
            ),
            "trader_label",
        )

        matches: dict[str, float] = {}
        for line in lines:
            if line.confidence < 0.55:
                continue
            for trader, aliases in MERCHANT_ALIASES.items():
                if any(_matches_term(line.text, alias) for alias in aliases):
                    matches[trader] = max(matches.get(trader, 0.0), line.confidence)

        if len(matches) != 1:
            if matches:
                return None, lines, f"merchant label OCR is ambiguous: {', '.join(sorted(matches))}"
            return None, lines, "merchant label OCR found no known alias"

        identified_trader, confidence = next(iter(matches.items()))
        if identified_trader != visual_trader:
            return (
                identified_trader,
                lines,
                f"merchant label OCR corrected visual slot from {visual_trader} to {identified_trader} "
                f"(confidence={confidence:.3f})",
            )
        return identified_trader, lines, f"merchant label OCR confirmed {identified_trader} (confidence={confidence:.3f})"

    @staticmethod
    def _unique_texts(lines: list[OCRLine]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for line in lines:
            key = _normalize(line.text)
            if key and key not in seen:
                result.append(line.text)
                seen.add(key)
        return result

    def analyze(
        self,
        image_bgra: np.ndarray,
        capture_id: str | None = None,
    ) -> ScreenAnalysis:
        image_bgr = image_bgra[:, :, :3]
        height, width = image_bgr.shape[:2]
        active_trader, card_scores, card_reason = self._detect_active_trader(image_bgr)
        visual_trader = active_trader
        trader_label_lines: list[OCRLine] = []
        trader_label_decision = "skipped: no unique highlighted card"
        diagnostics: dict[str, Any] = {
            "capture_id": capture_id,
            "image_size": {"width": width, "height": height},
            "regions": {
                "top_tabs": list(TRADER_TASK_TAB_REGION),
                "task_list": list(TASK_LIST_REGION),
            },
            "ocr_normalization": {
                "reference_height": OCR_REFERENCE_HEIGHT,
                "scale": round(self._ocr_scale(height), 4),
                "minimum_scale": OCR_MIN_SCALE,
                "maximum_scale": OCR_MAX_SCALE,
            },
            "trader_card_scores": card_scores,
            "trader_card_decision": card_reason,
            "trader_card_visual_candidate": visual_trader,
        }

        if visual_trader:
            try:
                active_trader, trader_label_lines, trader_label_decision = self._confirm_active_trader(
                    image_bgr, visual_trader, card_scores
                )
            except Exception as error:
                active_trader = None
                trader_label_decision = "merchant label OCR failed"
                log_event(
                    "screen_analysis_failed",
                    level=logging.ERROR,
                    capture_id=capture_id,
                    stage="trader_label_ocr",
                    visual_trader=visual_trader,
                    error=repr(error),
                )
        diagnostics["trader_label_ocr"] = [line.as_dict() for line in trader_label_lines]
        diagnostics["trader_label_decision"] = trader_label_decision
        diagnostics["trader_card_decision"] = f"{card_reason}; {trader_label_decision}"

        try:
            top_lines = self._ocr_region(image_bgr, TRADER_TASK_TAB_REGION, "top_tabs")
            task_tab_selected, task_tab_scores = self._selected_tab(image_bgr, top_lines, TASK_TAB_TERMS)
            equipment_tab_selected, equipment_tab_scores = self._selected_tab(
                image_bgr, top_lines, EQUIPMENT_TAB_TERMS
            )
            diagnostics["top_tab_ocr"] = [line.as_dict() for line in top_lines]
            diagnostics["task_tab_scores"] = task_tab_scores
            diagnostics["equipment_tab_scores"] = equipment_tab_scores
            diagnostics["task_tab_selected"] = task_tab_selected
            diagnostics["equipment_tab_selected"] = equipment_tab_selected
        except Exception as error:
            log_event(
                "screen_analysis_failed",
                level=logging.ERROR,
                capture_id=capture_id,
                stage="top_tab_ocr",
                error=repr(error),
            )
            return ScreenAnalysis(
                kind=ScreenKind.UNKNOWN,
                trader=None,
                text_lines=[],
                warning=f"顶部页签识别失败：{error}",
                diagnostics=diagnostics,
            )

        if equipment_tab_selected:
            diagnostics["page_decision"] = "active equipment tab in top navigation"
            analysis = ScreenAnalysis(
                kind=ScreenKind.EQUIPMENT,
                trader=None,
                text_lines=[],
                warning="已识别角色装备页；容器黄勾检测暂不启用。",
                diagnostics=diagnostics,
            )
            log_event(
                "screen_analysis",
                capture_id=capture_id,
                page_kind=analysis.kind.value,
                trader=None,
                task_page_confident=False,
                diagnostics=diagnostics,
            )
            return analysis

        if active_trader and task_tab_selected:
            try:
                task_lines = self._ocr_region(image_bgr, TASK_LIST_REGION, "task_list")
            except Exception as error:
                log_event(
                    "screen_analysis_failed",
                    level=logging.ERROR,
                    capture_id=capture_id,
                    stage="task_list_ocr",
                    trader=active_trader,
                    error=repr(error),
                )
                return ScreenAnalysis(
                    kind=ScreenKind.UNKNOWN,
                    trader=active_trader,
                    text_lines=[],
                    warning=f"{active_trader} 任务列表 OCR 失败：{error}",
                    diagnostics=diagnostics,
                )
            text_lines = self._unique_texts(task_lines)
            confident = len(text_lines) >= 3
            warning = "" if confident else "任务列表区域文字过少，本次不会更新任务状态。"
            diagnostics["task_list_ocr"] = [line.as_dict() for line in task_lines]
            diagnostics["task_list_line_count"] = len(text_lines)
            diagnostics["page_decision"] = "selected trader card plus selected Tasks tab"
            analysis = ScreenAnalysis(
                kind=ScreenKind.TRADER_TASKS,
                trader=active_trader,
                text_lines=text_lines,
                task_page_confident=confident,
                warning=warning,
                diagnostics=diagnostics,
            )
            log_event(
                "screen_analysis",
                capture_id=capture_id,
                page_kind=analysis.kind.value,
                trader=active_trader,
                task_page_confident=confident,
                task_line_count=len(text_lines),
                warning=warning,
                diagnostics=diagnostics,
            )
            return analysis

        if active_trader and not task_tab_selected:
            warning = "识别到商人卡片，但顶部‘任务’页签未确认选中；未执行任务差分。"
        elif task_tab_selected and not active_trader:
            if visual_trader:
                warning = f"检测到高亮商人卡片，但无法核实卡片名称（{trader_label_decision}）；未执行任务差分。"
            else:
                warning = "任务页签已选中，但未检测到唯一高亮商人卡片；未执行任务差分。"
        else:
            warning = "未识别到商人任务页或角色装备页；未修改任务状态。"
        diagnostics["page_decision"] = warning
        analysis = ScreenAnalysis(
            kind=ScreenKind.UNKNOWN,
            trader=active_trader,
            text_lines=[],
            warning=warning,
            diagnostics=diagnostics,
        )
        log_event(
            "screen_analysis",
            capture_id=capture_id,
            page_kind=analysis.kind.value,
            trader=active_trader,
            task_page_confident=False,
            warning=warning,
            diagnostics=diagnostics,
        )
        return analysis
