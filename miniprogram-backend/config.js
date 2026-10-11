/**
 * 后端服务地址配置。
 *
 * 三种用法（按部署方式选一种）：
 *
 * 1) 本地/局域网开发调试
 *    USE_DEV = true，DEV_URL 填你电脑的局域网 IP（开发者工具需勾选「不校验合法域名」）
 *
 * 2) 微信云托管（容器，推荐，本工程默认部署方式）
 *    USE_DEV = false，PROD_URL 填你在云托管绑定的【已备案自定义 HTTPS 域名】。
 *    域名请在 mp.weixin.qq.com → 开发设置 → 服务器域名 里加入
 *    request 合法域名 与 uploadFile 合法域名。
 *    ⚠️ 云托管多实例下磁盘不共享，所以结果图走 inline base64 返回（见 INLINE_RESULT）。
 *
 * 3) 云托管 CallContainer（无需域名、无需备案）
 *    需先把图片上传到微信云存储拿到 fileID，再 callContainer 传 fileID 给后端下载。
 *    本工程未内置该路径（Python 容器读取云存储 fileID 较繁琐），如需要可在此基础上扩展。
 */

const USE_DEV = false

// 微信云托管：填你绑定的已备案自定义域名（例如 https://apple-api.your-domain.com）
const PROD_URL = 'https://apple-api.your-domain.com'

// 本地调试用
const DEV_URL = 'http://192.168.1.100:8000'

// 结果标注图是否以内联 base64 返回（云托管/多实例务必 true，避免跨实例 404）
const INLINE_RESULT = true

module.exports = {
  USE_DEV,
  BASE_URL: USE_DEV ? DEV_URL : PROD_URL,
  INLINE_RESULT,
  // 单次上传前是否压缩图片（可显著减少上传耗时）
  COMPRESS_UPLOAD: true,
  // 压缩质量 0-100
  COMPRESS_QUALITY: 80,
  // 请求超时（毫秒）
  TIMEOUT: 30000
}
