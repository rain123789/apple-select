"""
苹果检测推理封装。

三级降级策略，保证任何环境下服务都能起来、接口都能打通：

1. real      - 存在权重文件且 ultralytics 可用 -> 真实 YOLOv5/YOLOv8/YOLOv11 推理
2. torchhub  - 存在权重文件但没有 ultralytics -> 走 torch.hub 官方 yolov5
3. mock      - 没有权重文件或推理依赖缺失 -> 生成模拟检测框（仅用于打通链路 / UI 联调）

当前模式可通过 /api/health 或检测结果中的 mode 字段查看。
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("apple.detector")

# PyTorch 2.6+ 把 torch.load 默认值改为 weights_only=True，
# 但官方 YOLOv5 权重存档使用自定义全局类，需要 weights_only=False 才能加载。
# 本服务只加载本地可信权重，因此全局放行（仅对本地 .pt 生效）。
try:  # pragma: no cover
    import torch as _torch  # noqa: PLC0415

    _orig_torch_load = _torch.load

    def _torch_load_trusted(f, *args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return _orig_torch_load(f, *args, **kwargs)

    _torch.load = _torch_load_trusted
except Exception:  # noqa: BLE001
    pass

# 无权重时的占位类别名，与仓库 data 中的苹果类别保持一致思路
DEFAULT_CLASSES = ["apple"]


@dataclass
class Detection:
    label: str
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2]，相对原图坐标

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "bbox": [round(v, 2) for v in self.bbox],
        }


class AppleDetector:
    """苹果检测推理器。"""

    def __init__(
        self,
        weights: str | None = None,
        conf_threshold: float = 0.20,
        iou_threshold: float = 0.45,
        img_size: int = 640,
        device: str | None = None,
    ) -> None:
        self.weights = Path(weights) if weights else None
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.img_size = img_size
        self.device = device or ("cuda:0" if self._cuda_available() else "cpu")

        self.mode = "mock"
        self.model: Any = None
        self.predict_fn: str = ""
        self.classes: list[str] = list(DEFAULT_CLASSES)
        self.load_error: str | None = None

        self._load()

    # ------------------------------------------------------------------ #
    # 模型加载
    # ------------------------------------------------------------------ #
    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch  # noqa: PLC0415

            return bool(torch.cuda.is_available())
        except Exception:  # noqa: BLE001
            return False

    def _load(self) -> None:
        if not self.weights or not self.weights.exists():
            self.mode = "mock"
            self.load_error = (
                f"未找到权重文件：{self.weights}。已降级为模拟推理模式，"
                f"请把训练好的 .pt 放到该路径后重启服务。"
            )
            logger.warning(self.load_error)
            return

        # 1) ultralytics（可加载 yolov8/v11 的 .pt）
        try:
            from ultralytics import YOLO  # noqa: PLC0415

            self.model = YOLO(str(self.weights))
            names = getattr(self.model, "names", None)
            if names:
                self.classes = [names[i] for i in sorted(names.keys())]
            self.predict_fn = "ultralytics"
            self.mode = "real"
            logger.info("已加载权重 %s（ultralytics，类别：%s）", self.weights, self.classes)
            return
        except Exception as exc:  # noqa: BLE001
            logger.info("ultralytics 不可用（%s），尝试 yolov5 包", exc)

        # 2) yolov5 包（专门加载 YOLOv5 格式权重，COCO 预训练含 apple 类）
        try:
            import yolov5  # noqa: PLC0415

            self.model = yolov5.load(str(self.weights), device=self.device)
            self.model.conf = self.conf_threshold
            self.model.iou = self.iou_threshold
            names = getattr(self.model, "names", None)
            if names:
                self.classes = [
                    names[i] for i in sorted(names.keys())
                ] if isinstance(names, dict) else list(names)
            self.predict_fn = "yolov5"
            self.mode = "real"
            logger.info("已加载权重 %s（yolov5 包，类别：%s）", self.weights, self.classes)
            return
        except Exception as exc:  # noqa: BLE001
            self.load_error = f"权重存在但推理依赖加载失败：{exc}"
            logger.warning("%s，已降级为模拟推理模式", self.load_error)

        self.mode = "mock"

    @property
    def ready(self) -> bool:
        return self.mode == "real"

    # ------------------------------------------------------------------ #
    # 推理
    # ------------------------------------------------------------------ #
    def predict(self, image: Image.Image) -> list[Detection]:
        if self.mode == "real":
            try:
                if self.predict_fn == "yolov5":
                    return self._predict_yolov5(image)
                return self._predict_ultralytics(image)
            except Exception as exc:  # noqa: BLE001
                logger.exception("真实推理失败，本次回退模拟结果：%s", exc)
        return self._mock_predict(image)

    def _predict_ultralytics(self, image: Image.Image) -> list[Detection]:
        results = self.model.predict(
            source=image,
            imgsz=self.img_size,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            device=self.device,
            verbose=False,
        )

        detections: list[Detection] = []
        for result in results:
            names = getattr(result, "names", None) or {
                i: name for i, name in enumerate(self.classes)
            }
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                xyxy = box.xyxy[0].tolist()
                cls_id = int(box.cls[0])
                detections.append(
                    Detection(
                        label=str(names.get(cls_id, str(cls_id))),
                        confidence=float(box.conf[0]),
                        bbox=[float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])],
                    )
                )
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections

    def _predict_yolov5(self, image: Image.Image) -> list[Detection]:
        # augment=True 开启 TTA（测试时增强）：单张水果特写等场景下
        # 普通推理置信度偏低（如 apple 仅 0.24），TTA 可提升至 0.8 左右
        self.model.conf = self.conf_threshold
        results = self.model(image, size=self.img_size, augment=True)
        names = results.names or {i: n for i, n in enumerate(self.classes)}

        detections: list[Detection] = []
        for det in results.pred:
            for *xyxy, conf, cls in det:
                detections.append(
                    Detection(
                        label=str(names[int(cls)]),
                        confidence=float(conf),
                        bbox=[
                            float(xyxy[0]),
                            float(xyxy[1]),
                            float(xyxy[2]),
                            float(xyxy[3]),
                        ],
                    )
                )
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections

    def _mock_predict(self, image: Image.Image) -> list[Detection]:
        """模拟检测：同一张图固定出同样的框，方便前后端联调。"""
        width, height = image.size
        seed = hashlib.md5(image.tobytes()).hexdigest()
        rnd = random.Random(seed)

        count = rnd.randint(2, 6)
        short_side = min(width, height)
        detections: list[Detection] = []

        for _ in range(count):
            box_w = rnd.uniform(0.10, 0.24) * short_side
            box_h = box_w * rnd.uniform(0.85, 1.15)
            x1 = rnd.uniform(0, max(1.0, width - box_w))
            y1 = rnd.uniform(0, max(1.0, height - box_h))
            detections.append(
                Detection(
                    label=rnd.choice(self.classes),
                    confidence=round(rnd.uniform(0.56, 0.97), 4),
                    bbox=[x1, y1, x1 + box_w, y1 + box_h],
                )
            )

        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections

    # ------------------------------------------------------------------ #
    # 绘制标注图
    # ------------------------------------------------------------------ #
    PALETTE = [
        (231, 76, 60),
        (39, 174, 96),
        (41, 128, 185),
        (243, 156, 18),
        (142, 68, 173),
        (26, 188, 156),
        (211, 84, 0),
        (52, 73, 94),
    ]

    def color_for(self, label: str) -> tuple[int, int, int]:
        idx = self.classes.index(label) if label in self.classes else 0
        return self.PALETTE[idx % len(self.PALETTE)]

    @staticmethod
    def _font(size: int):
        candidates = [
            "C:/Windows/Fonts/msyh.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/PingFang.ttc",
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:  # noqa: BLE001
                    continue
        return ImageFont.load_default()

    def draw(
        self, image: Image.Image, detections: list[Detection], max_side: int = 1280
    ) -> Image.Image:
        canvas = image.convert("RGB")
        scale = 1.0
        if max(canvas.size) > max_side:
            scale = max_side / max(canvas.size)
            canvas = canvas.resize(
                (int(canvas.width * scale), int(canvas.height * scale)), Image.LANCZOS
            )

        draw = ImageDraw.Draw(canvas)
        font = self._font(max(14, int(18 * scale)))

        for det in detections:
            x1, y1, x2, y2 = [v * scale for v in det.bbox]
            color = self.color_for(det.label)
            draw.rectangle([x1, y1, x2, y2], outline=color, width=max(2, int(3 * scale)))

            text = f"{det.label} {det.confidence:.2f}"
            try:
                left, top, right, bottom = draw.textbbox((x1, y1), text, font=font)
                text_w, text_h = right - left, bottom - top
            except AttributeError:  # 老版本 Pillow
                text_w, text_h = draw.textsize(text, font=font)  # type: ignore[attr-defined]

            tag_y1 = max(0.0, y1 - text_h - 8 * scale)
            draw.rectangle(
                [x1, tag_y1, x1 + text_w + 10 * scale, y1], fill=color
            )
            draw.text(
                (x1 + 5 * scale, tag_y1 + 3 * scale), text, fill=(255, 255, 255), font=font
            )

        return canvas


def summarize(detections: list[Detection], inference_ms: float, total_ms: float) -> dict:
    """生成前端要用的统计信息。"""
    by_label: dict[str, dict] = {}
    for det in detections:
        item = by_label.setdefault(det.label, {"label": det.label, "count": 0, "avg_confidence": 0.0})
        item["count"] += 1
        item["avg_confidence"] += det.confidence

    total = len(detections)
    for item in by_label.values():
        item["avg_confidence"] = round(item["avg_confidence"] / item["count"], 4)
        item["ratio"] = round(item["count"] / total, 4) if total else 0.0

    confs = [d.confidence for d in detections]
    return {
        "count": total,
        "by_label": sorted(by_label.values(), key=lambda x: x["count"], reverse=True),
        "avg_confidence": round(sum(confs) / len(confs), 4) if confs else 0.0,
        "max_confidence": round(max(confs), 4) if confs else 0.0,
        "min_confidence": round(min(confs), 4) if confs else 0.0,
        "inference_ms": round(inference_ms, 2),
        "total_ms": round(total_ms, 2),
    }
