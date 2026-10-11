# 微信云托管（CloudBase Run）部署指南

把苹果检测后端部署到**微信云托管**（容器服务），小程序通过 `wx.uploadFile` 直连云托管提供的
HTTPS 域名。无需自建服务器、无需 Nginx，平台自带弹性伸缩与 HTTPS。

> 为什么不用云函数（SCF）？云函数代码包限制几十 MB，而 PyTorch + YOLOv5 权重要 1GB+，
> 装不下。云托管是容器服务，镜像可到数 GB，正好合适。

---

## 一、准备后端镜像

### 1. 确认权重已在镜像构建上下文里
云托管镜像会把 `server/weights/best.pt` 烤进镜像，所以构建前必须存在：

```bash
# 你自己的苹果专用模型，直接覆盖即可（类别名权重自带，无需改代码）
cp /path/to/your_best.pt server/weights/best.pt

# 若还没有，可用 COCO 预训练版（已包含 apple 类，能真实检测苹果）：
# 下载 yolov5s.pt 并改名为 best.pt（见 README.md「接真实权重」一节）
```

### 2. 构建镜像（两种方式任选）

**方式 A：本地构建后推到云托管镜像仓库（推荐，可控）**
```bash
cd server
docker build -t apple-detection:latest .
# 推送到云托管「镜像仓库」（控制台 → 云托管 → 我的镜像 → 推送指引里给你仓库地址）
docker tag apple-detection:latest <你的镜像仓库地址>/apple-detection:latest
docker push <你的镜像仓库地址>/apple-detection:latest
```

**方式 B：直接在云托管控制台从源码构建**
控制台新建服务时选「本地代码 / 代码仓库」，目录指向 `server/`，平台读 `server/Dockerfile` 自动构建。
构建环境联网正常，会自动从 pytorch.org 拉 CPU 版 torch。

> 镜像较大（约 1.5~2GB），首次构建/推送较慢，属正常。

---

## 二、在微信开发者工具里创建云托管服务

1. 微信开发者工具 → 顶部「云开发」→ 开通云开发环境（记录 **环境 ID**）。
2. 左侧「云托管」→「新建服务」→ 服务名称 `apple-detection`。
3. 服务来源：
   - 若用方式 A：选「我的镜像」，填上面 push 的镜像地址。
   - 若用方式 B：选「代码 / 本地代码」，目录 `server/`，Dockerfile `Dockerfile`。
4. 服务设置：
   - 监听端口：`8000`
   - 健康检查路径：`/api/health`
   - 实例规格：CPU 1 核 / 内存 2GB（PyTorch 推理够用）
   - **最小副本数设为 1**：PyTorch 加载较重，设为 0 时冷启动可能 20~40s
   - 最大副本数：4（按需）
5. 部署后等待「实例就绪」，在「服务配置 → 公网访问」里能看到一个 `*.apigw.run.tcloudbase.com`
   这样的**默认公网域名**，以及一个「调用信息」。

---

## 三、绑定已备案自定义域名（上线必须）

> 云托管默认公网域名**只能用于接口自测**，且**无法在小程序后台登记为合法域名**，
> 因此不能用于正式版。正式上线必须绑定你自己的**已 ICP 备案**的自定义域名。

1. 云托管 → 服务设置 → 自定义域名 → 添加域名（如 `apple-api.your-domain.com`）。
2. 按提示在你域名解析处添加平台给的 **CNAME** 记录，等待生效（平台会自动签发 HTTPS 证书）。
3. 拿到形如 `https://apple-api.your-domain.com` 的 HTTPS 域名。

---

## 四、配置小程序

### 1. 填后端地址
编辑 `miniprogram/config.js`：

```js
const USE_DEV = false
const PROD_URL = 'https://apple-api.your-domain.com'  // ← 换成你上一步的域名
const INLINE_RESULT = true                             // 云托管多实例必须 true
```

> `INLINE_RESULT=true` 让后端直接把标注图以 base64 返回，规避云托管多实例磁盘不共享导致的 404。

### 2. 登记合法域名（微信公众平台）
登录 https://mp.weixin.qq.com → 开发管理 → 开发设置 → 服务器域名，加入：
- **request 合法域名**：`https://apple-api.your-domain.com`
- **uploadFile 合法域名**：`https://apple-api.your-domain.com`
（downloadFile 不用，结果图走 base64 内联，不触发下载）

> 域名必须是**已备案**的；保存后约 5 分钟生效。

### 3. 填 AppID
编辑 `miniprogram/project.config.json`，把 `"appid": "请填写你的AppID"` 换成你的小程序 AppID。

### 4. 上传 & 发布
微信开发者工具 → 右上「上传」→ 填版本号与备注 → 到 mp 后台「版本管理」提交**审核** → 审核通过**发布**。

---

## 五、自测（不开通合法域名也能验证）

开发阶段想先验证，可用云托管的**默认公网域名** + 开发者工具勾选「不校验合法域名」：
1. `config.js` 里 `PROD_URL` 临时填默认公网域名（`*.apigw.run.tcloudbase.com`）。
2. 开发者工具 → 详情 → 本地设置 → 勾选「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」。
3. 真机/模拟器跑检测，确认链路通、苹果能框出，再切回自定义域名走正式流程。

---

## 六、常见问题

- **健康检查一直失败**：确认服务能监听 `0.0.0.0:$PORT`（本项目已读 `PORT` 环境变量）；
  权重 `best.pt` 是否真的烤进了镜像（构建日志里应有 `COPY . .` 包含 weights）。
- **检测超时**：云托管 CallContainer 有 15s 上限，但本方案用公网域名 `wx.uploadFile` 不受此限；
  CPU 推理单张约 0.3~1s，正常。
- **冷启动慢**：把最小副本数设为 1。
- **想换成自己的苹果模型**：覆盖 `server/weights/best.pt` 重新构建部署即可，类别名权重自带。
- **不想备案域名**：可改走 CallContainer + 微信云存储（先传图到云存储拿 fileID，再 callContainer 传 fileID，
  后端从云存储下载）。本工程未内置该路径（Python 容器读云存储 fileID 较繁琐），可按需扩展。
