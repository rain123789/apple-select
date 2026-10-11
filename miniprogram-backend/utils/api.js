const { BASE_URL, TIMEOUT, COMPRESS_UPLOAD, COMPRESS_QUALITY, INLINE_RESULT } = require('../config.js')

function request(options) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE_URL + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      header: options.header || { 'content-type': 'application/json' },
      timeout: options.timeout || TIMEOUT,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) return resolve(res)
        reject(new Error(`请求失败(${res.statusCode})：${JSON.stringify(res.data)}`))
      },
      fail: (err) => reject(new Error(`网络异常：${err.errMsg || '未知错误'}`))
    })
  })
}

/** 后端与模型状态 */
function checkHealth() {
  return request({ url: '/api/health', timeout: 8000 })
}

/** 压缩图片，减少上传体积 */
function compress(filePath) {
  if (!COMPRESS_UPLOAD) return Promise.resolve(filePath)
  return new Promise((resolve) => {
    wx.compressImage({
      src: filePath,
      quality: COMPRESS_QUALITY,
      success: (res) => resolve(res.tempFilePath || filePath),
      fail: () => resolve(filePath)
    })
  })
}

/**
 * 上传图片并检测
 * @param {string} filePath 本地临时文件路径
 * @returns {Promise<object>} 检测结果（含 annotated_url 或 annotated_base64）
 */
function detect(filePath) {
  return compress(filePath).then((path) => {
    return new Promise((resolve, reject) => {
      const formData = {}
      if (INLINE_RESULT) formData.inline = 'true'
      wx.uploadFile({
        url: `${BASE_URL}/api/detect`,
        filePath: path,
        name: 'file',
        formData,
        timeout: TIMEOUT,
        success: (res) => {
          if (res.statusCode < 200 || res.statusCode >= 300) {
            return reject(new Error(`检测失败(${res.statusCode})：${res.data}`))
          }
          let data = res.data
          if (typeof data === 'string') {
            try {
              data = JSON.parse(data)
            } catch (e) {
              return reject(new Error('返回结果解析失败：' + res.data))
            }
          }
          if (!data || data.success === false) {
            return reject(new Error((data && data.detail) || '检测失败'))
          }
          resolve(data)
        },
        fail: (err) => reject(new Error(`上传失败：${err.errMsg || '未知错误'}`))
      })
    })
  })
}

/** 把相对路径拼成完整可访问地址（inline 模式下一般不会用到） */
function absUrl(path) {
  if (!path) return ''
  if (path.indexOf('http') === 0) return path
  return BASE_URL + path
}

module.exports = { request, checkHealth, detect, absUrl }
