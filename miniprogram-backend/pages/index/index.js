const { checkHealth, detect, absUrl } = require('../../utils/api.js')

const PALETTE = [
  '#e74c3c', '#27ae60', '#2980b9', '#f39c12',
  '#8e44ad', '#1abc9c', '#d35400', '#34495e'
]

const app = getApp()

Page({
  data: {
    originImage: '',
    resultImage: '',
    displayImage: '',
    result: null,
    stats: {},
    byLabel: [],
    detections: [],
    detecting: false,
    canDetect: false,
    isMock: false,
    statusLevel: 'unknown', // ok | warn | error | unknown
    statusText: '正在连接后端…',
    confidenceText: '--'
  },

  onLoad() {
    app.healthReady = (data) => this.applyHealth(data)
    if (app.globalData.modelMode) {
      this.applyHealth({
        mode: app.globalData.modelMode,
        model_loaded: app.globalData.modelLoaded,
        classes: app.globalData.classes
      })
    }
  },

  onUnload() {
    app.healthReady = null
  },

  // ---------------------------------------------------------------- 状态
  applyHealth(data) {
    if (!data) {
      this.setData({
        statusLevel: 'error',
        statusText: '后端未连接，请检查 config.js 中的地址'
      })
      return
    }
    const mode = data.mode
    const text = {
      real: '模型已加载 · 真实推理',
      torchhub: '模型已加载 · torch.hub 推理',
      mock: '未加载权重 · 模拟推理'
    }[mode] || '后端已连接'

    this.setData({
      statusLevel: mode === 'mock' ? 'warn' : 'ok',
      statusText: text,
      isMock: mode === 'mock'
    })
  },

  refreshStatus() {
    this.setData({ statusText: '正在连接后端…', statusLevel: 'unknown' })
    checkHealth()
      .then((res) => this.applyHealth(res.data))
      .catch(() => this.applyHealth(null))
  },

  // ---------------------------------------------------------------- 选图
  chooseImage(sourceType) {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType,
      sizeType: ['compressed'],
      camera: 'back',
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0]
        if (!file) return
        this.setData({
          originImage: file.tempFilePath,
          displayImage: file.tempFilePath,
          resultImage: '',
          result: null,
          stats: {},
          byLabel: [],
          detections: [],
          canDetect: true,
          confidenceText: '--'
        })
      }
    })
  },

  takePhoto() {
    this.chooseImage(['camera'])
  },

  chooseFromAlbum() {
    this.chooseImage(['album'])
  },

  reset() {
    this.setData({
      originImage: '',
      resultImage: '',
      displayImage: '',
      result: null,
      stats: {},
      byLabel: [],
      detections: [],
      canDetect: false,
      confidenceText: '--'
    })
  },

  previewImage() {
    if (!this.data.displayImage) return
    wx.previewImage({ urls: [this.data.displayImage], current: this.data.displayImage })
  },

  // ---------------------------------------------------------------- 检测
  startDetect() {
    if (!this.data.canDetect || this.data.detecting) return
    this.setData({ detecting: true })

    detect(this.data.originImage)
      .then((data) => {
        const classes = (app.globalData.classes && app.globalData.classes.length)
          ? app.globalData.classes
          : uniqueLabels(data.detections)

        const detections = (data.detections || []).map((d, i) => ({
          label: d.label,
          confidence: d.confidence.toFixed(2),
          bboxText: (d.bbox || []).map((v) => Math.round(v)).join(', '),
          color: colorFor(d.label, classes),
          index: i + 1
        }))

        const total = data.stats.count || 0
        const byLabel = (data.stats.by_label || []).map((item) => ({
          label: item.label,
          count: item.count,
          percent: total ? Math.round((item.count / total) * 100) : 0,
          color: colorFor(item.label, classes)
        }))

        // 优先用 inline base64（云托管多实例安全），否则用标注图 URL
        const annotatedSrc = data.annotated_base64 || absUrl(data.annotated_url)

        this.setData({
          result: data,
          stats: data.stats,
          detections,
          byLabel,
          isMock: !!data.is_mock,
          resultImage: annotatedSrc,
          displayImage: annotatedSrc,
          confidenceText: (data.stats.avg_confidence * 100).toFixed(1) + '%'
        })
      })
      .catch((err) => {
        wx.showToast({ title: err.message || '检测失败', icon: 'none', duration: 2600 })
      })
      .finally(() => {
        this.setData({ detecting: false })
      })
  }
})

function uniqueLabels(detections) {
  const seen = []
  ;(detections || []).forEach((d) => {
    if (seen.indexOf(d.label) === -1) seen.push(d.label)
  })
  return seen.length ? seen : ['apple']
}

function colorFor(label, classes) {
  const idx = classes.indexOf(label)
  return PALETTE[(idx < 0 ? 0 : idx) % PALETTE.length]
}
