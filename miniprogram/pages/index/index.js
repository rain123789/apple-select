const { H5_URL } = require('../../config.js')

Page({
  data: {
    url: H5_URL
  },
  onLoad() {
    // web-view 的 src 不能是空；这里直接用配置里的 H5 地址
    this.setData({ url: H5_URL })
  }
})
