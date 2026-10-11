"""
后端冒烟测试：生成一张测试图，调用 /api/health 与 /api/detect，验证返回结构。

用法：
    python server/app.py          # 另开一个终端先启动服务
    python scripts/smoke_test.py  # 再跑这个脚本
"""

import io
import json
import sys
import urllib.error
import urllib.request
import uuid

from PIL import Image, ImageDraw

BASE_URL = "http://127.0.0.1:8000"


def make_test_image(path: str = "test_apple.jpg", size: int = 640) -> str:
    """画一张带几个红色/绿色圆球的测试图。"""
    img = Image.new("RGB", (size, size), (246, 248, 244))
    draw = ImageDraw.Draw(img)
    spots = [(120, 150), (330, 220), (220, 420), (470, 400), (520, 130)]
    colors = [(214, 62, 51), (72, 168, 84), (226, 88, 60), (60, 150, 76), (232, 70, 58)]
    for (cx, cy), color in zip(spots, colors):
        r = 45
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    img.save(path, "JPEG", quality=90)
    return path


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_file(url: str, file_path: str) -> dict:
    boundary = uuid.uuid4().hex
    with open(file_path, "rb") as fh:
        content = fh.read()

    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write(
        f'Content-Disposition: form-data; name="file"; filename="{file_path}"\r\n'.encode()
    )
    body.write(b"Content-Type: image/jpeg\r\n\r\n")
    body.write(content)
    body.write(f"\r\n--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        url,
        data=body.getvalue(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    print(f"目标服务：{BASE_URL}")

    try:
        health = get(f"{BASE_URL}/api/health")
    except urllib.error.URLError as exc:
        print(f"[FAIL] 无法连接后端，请先启动：python server/app.py  ({exc})")
        return 1

    print(f"[OK] /api/health  mode={health['mode']} loaded={health['model_loaded']} "
          f"classes={health['classes']}")

    img_path = make_test_image()
    result = post_file(f"{BASE_URL}/api/detect", img_path)
    print(f"[OK] /api/detect  mode={result['mode']} count={result['stats']['count']} "
          f"annotated={result['annotated_url']}")

    assert result["success"] is True, "success 字段应为 True"
    assert "detections" in result and "stats" in result, "返回缺少 detections / stats"
    assert result["image"]["width"] == 640, "图片尺寸回传不正确"

    for det in result["detections"][:3]:
        print(f"     - {det['label']}  {det['confidence']:.2f}  bbox={det['bbox']}")

    print("\n统计：", json.dumps(result["stats"], ensure_ascii=False))
    print("\n全部断言通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
