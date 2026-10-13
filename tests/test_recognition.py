import unittest

import numpy as np

from recognition import PageAnalyzer


class FixedResultOCR:
    def __init__(self):
        self.image_shapes = []

    def __call__(self, image):
        self.image_shapes.append(image.shape[:2])
        points = [[10, 20], [30, 20], [30, 40], [10, 40]]
        return [[points, "Tasks", 0.95]], None


class PageAnalyzerResolutionTests(unittest.TestCase):
    def test_ocr_region_normalizes_common_16_9_resolutions(self):
        resolutions = [
            (1280, 720, 2.0),
            (1600, 900, 1.6),
            (1920, 1080, 4 / 3),
            (2560, 1440, 1.0),
            (3200, 1800, 0.8),
            (3840, 2160, 2 / 3),
            (5120, 2880, 0.5),
        ]

        for width, height, expected_scale in resolutions:
            with self.subTest(resolution=f"{width}x{height}"):
                analyzer = PageAnalyzer()
                ocr = FixedResultOCR()
                analyzer._ocr = ocr
                image = np.zeros((height, width, 3), dtype=np.uint8)

                lines = analyzer._ocr_region(
                    image, (0.0, 0.25, 0.30, 0.99), "test"
                )

                self.assertAlmostEqual(analyzer._ocr_scale(height), expected_scale)
                self.assertEqual(len(lines), 1)
                self.assertEqual(lines[0].text, "Tasks")
                self.assertEqual(len(ocr.image_shapes), 1)
                working_height, working_width = ocr.image_shapes[0]
                self.assertLessEqual(abs(working_width - 768), 2)
                self.assertLessEqual(abs(working_height - 0.74 * 1440), 2)
                x0, y0, x1, y1 = lines[0].bounds
                self.assertAlmostEqual(x0 / width, 10 / 2560, delta=0.001)
                self.assertAlmostEqual(x1 / width, 30 / 2560, delta=0.001)
                self.assertAlmostEqual(
                    y0 / height, 0.25 + 20 / 1440, delta=0.001
                )
                self.assertAlmostEqual(
                    y1 / height, 0.25 + 40 / 1440, delta=0.001
                )

    def test_ocr_scale_is_clamped(self):
        self.assertEqual(PageAnalyzer._ocr_scale(360), 2.0)
        self.assertEqual(PageAnalyzer._ocr_scale(2880), 0.5)

    def test_ocr_scale_rejects_nonpositive_image_height(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            PageAnalyzer._ocr_scale(0)
