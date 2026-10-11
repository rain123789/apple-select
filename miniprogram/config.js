/**
 * 小程序要打开的 H5 页面地址（纯前端推理，零后端）。
 *
 * 这个 H5 就是 frontend-only/index.html，已经部署在你的静态站
 * https://liubojun.52byte.com/ 上。它在手机浏览器里用 onnxruntime-web
 * 跑 YOLOv5s.onnx，图片与模型都不离开设备，不需要任何服务器。
 *
 * 部署到微信时必须把该域名加入「业务域名」白名单（见部署说明文档）。
 */
const USE_DEV = false

// 生产：你的静态站（已上线纯前端 H5）
const PROD_URL = 'https://liubojun.52byte.com/'

// 本地调试：本机用 `python -m http.server 8080` 托管 frontend-only/ 后即为该地址
// （开发者工具需勾选「不校验合法域名 / web-view（业务域名）」）
const DEV_URL = 'http://localhost:8080/'

module.exports = {
  H5_URL: USE_DEV ? DEV_URL : PROD_URL
}
