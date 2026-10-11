const { checkHealth } = require('./utils/api.js')

App({
  globalData: {
    // 后端模型状态：real / torchhub / mock
    modelMode: '',
    modelLoaded: false,
    classes: []
  },

  onLaunch() {
    this.refreshHealth()
  },

  refreshHealth() {
    checkHealth()
      .then((res) => {
        const data = res.data || {}
        this.globalData.modelMode = data.mode || ''
        this.globalData.modelLoaded = !!data.model_loaded
        this.globalData.classes = data.classes || []
        if (this.healthReady) this.healthReady(data)
      })
      .catch((err) => {
        console.warn('后端健康检查失败', err)
        if (this.healthReady) this.healthReady(null)
      })
  }
})
