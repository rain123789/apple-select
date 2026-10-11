"""
苹果检测识别 - FastAPI 推理服务。

接口：
    GET  /api/health   服务与模型状态
    GET  /api/classes  当前模型的类别列表
    POST /api/detect   上传图片 -> 返回检测明细、统计信息、标注图

启动：
    python app.py
    # 或
    uvicorn app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import io
import logging
import os
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from detector import AppleDetector, summarize

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("apple.server")

# ---------------------------------------------------------------- 配置
BASE_DIR = Path(__file__).resolve().parent
RESULT_DIR = Path(os.getenv("RESULT_DIR", BASE_DIR / "static" / "results"))
RESULT_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "12"))
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024)
RESULT_TTL = int(os.getenv("RESULT_TTL", "600"))  # 结果图保留时间（秒）
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/webp", "image/bmp"}

DETECTOR = AppleDetector(
    weights=os.getenv("APPLE_WEIGHTS", str(BASE_DIR / "weights" / "best.pt")),
    conf_threshold=float(os.getenv("CONF_THRESHOLD", "0.20")),
    iou_threshold=float(os.getenv("IOU_THRESHOLD", "0.45")),
    img_size=int(os.getenv("IMG_SIZE", "640")),
    device=os.getenv("DEVICE") or None,
)

# ---------------------------------------------------------------- 应用
app = FastAPI(
    title="苹果检测识别服务",
    description="YOLOv5 苹果水果检测识别 - 微信小程序后端",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(RESULT_DIR.parent)), name="static")


def get_detector() -> AppleDetector:
    return DETECTOR


# ---------------------------------------------------------------- 网页版
@app.get("/", include_in_schema=False)
@app.get("/demo", include_in_schema=False)
def web_page():
    """网页版网站（与小程序共用同一套后端接口）。部署到云托管后，绑定域名访问 `/` 即网站。"""
    page = BASE_DIR / "web" / "index.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail="web/index.html 不存在")
    return FileResponse(str(page))


@app.get("/api/health")
def health(detector: AppleDetector = Depends(get_detector)):
    return {
        "status": "ok",
        "mode": detector.mode,  # real | torchhub | mock
        "model_loaded": detector.ready,
        "weights": str(detector.weights) if detector.weights else None,
        "weights_exists": bool(detector.weights and detector.weights.exists()),
        "classes": detector.classes,
        "device": detector.device,
        "conf_threshold": detector.conf_threshold,
        "iou_threshold": detector.iou_threshold,
        "img_size": detector.img_size,
        "message": detector.load_error or "",
    }


@app.get("/api/classes")
def classes(detector: AppleDetector = Depends(get_detector)):
    return {"mode": detector.mode, "classes": detector.classes}


@app.post("/api/detect")
async def detect(
    file: UploadFile = File(..., description="待检测的图片"),
    inline: str = Form("false"),
    conf: float | None = None,
    detector: AppleDetector = Depends(get_detector),
):
    inline_result = str(inline).lower() in ("1", "true", "yes", "y")
    if file.content_type and file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail=f"不支持的图片类型：{file.content_type}")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="上传内容为空")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail=f"图片过大，请控制在 {MAX_UPLOAD_MB:.0f}MB 以内"
        )

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"图片解析失败：{exc}") from exc

    # 推理
    old_conf = detector.conf_threshold
    if conf is not None:
        detector.conf_threshold = max(0.01, min(0.99, conf))
    try:
        t0 = time.perf_counter()
        detections = detector.predict(image)
        inference_ms = (time.perf_counter() - t0) * 1000
    finally:
        detector.conf_threshold = old_conf

    # 绘制标注图
    t1 = time.perf_counter()
    annotated = detector.draw(image, detections)
    total_ms = (time.perf_counter() - t1) * 1000 + inference_ms

    name = f"{uuid.uuid4().hex}.jpg"
    out_path = RESULT_DIR / name
    annotated.save(out_path, "JPEG", quality=88)

    payload: dict = {
        "success": True,
        "mode": detector.mode,
        "is_mock": detector.mode == "mock",
        "image": {"width": image.width, "height": image.height},
        "detections": [d.to_dict() for d in detections],
        "stats": summarize(detections, inference_ms, total_ms),
        "annotated_url": f"/static/results/{name}",
    }
    if inline_result:
        buf = io.BytesIO()
        annotated.save(buf, "JPEG", quality=88)
        import base64  # noqa: PLC0415

        payload["annotated_base64"] = "data:image/jpeg;base64," + base64.b64encode(
            buf.getvalue()
        ).decode("ascii")

    logger.info(
        "detect mode=%s file=%s size=%sx%s count=%d %.1fms",
        detector.mode,
        file.filename,
        image.width,
        image.height,
        len(detections),
        inference_ms,
    )
    return JSONResponse(payload)


@app.delete("/api/results")
def clear_results():
    """清理过期的标注结果图。"""
    removed = 0
    now = time.time()
    for path in RESULT_DIR.glob("*.jpg"):
        if now - path.stat().st_mtime > RESULT_TTL:
            path.unlink(missing_ok=True)
            removed += 1
    return {"removed": removed}


if __name__ == "__main__":
    import uvicorn  # noqa: PLC0415

    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
