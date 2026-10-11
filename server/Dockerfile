# 微信云托管（CloudBase Run）部署镜像
# 说明：
#   - 微信云托管是容器服务，支持几 GB 镜像，因此可以完整装下 PyTorch + YOLOv5 权重
#   - 容器必须只监听一个端口（PORT 由平台注入，默认 8000）
#   - 容器不支持持久化存储，标注结果图通过 inline base64 直接返回，不依赖磁盘
#   - 权重 best.pt 已烤进镜像，重启/扩缩容都不会丢
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# 先装系统依赖（部分 wheel 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY . .

# 烤入权重（请保证 server/weights/best.pt 存在；没有可先用 COCO 预训练 yolov5s.pt 改名）
RUN mkdir -p /app/weights /app/static/results

EXPOSE 8000

# 云托管通过 PORT 环境变量传入监听端口；uvicorn 已读取该变量
CMD ["python", "app.py"]
