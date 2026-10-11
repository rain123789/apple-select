// 纯前端小程序：整个小程序只是一个 web-view 壳，
// 真正的苹果检测在 H5 页面里用 onnxruntime-web 跑，无需后端。
App({
  globalData: {
    h5Url: ''
  }
})
