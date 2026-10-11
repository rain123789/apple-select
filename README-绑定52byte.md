# 绑定到 https://liubojun.52byte.com/

## ⚠️ 先说前提（重要）

`liubojun.52byte.com` 目前返回的是一个**静态页面**（扫雷小游戏），说明 `52byte.com` 是**纯静态托管空间**——
只能放 HTML/CSS/JS，**跑不了 Python + PyTorch + YOLOv5 权重（约 1GB）的后端推理**。

因此本项目要"绑"到这个域名，必须**前后端分离**：

```
┌─────────────────────────┐         HTTPS           ┌──────────────────────────┐
│ liubojun.52byte.com      │  ────────调用────────►  │ 推理后端（独立部署）       │
│  （静态托管：网页前端）    │  ◄──────返回 JSON─────  │ FastAPI + YOLOv5 + 权重    │
│  server/web/index.html   │                        │ 云托管 / 自有服务器         │
└─────────────────────────┘                        └──────────────────────────┘
```

- 网页前端 → 静态托管到 `liubojun.52byte.com`（单文件上传即可）
- 推理后端 → 部署到能跑容器的地方，获得独立 HTTPS 域名（如 `apple-xxx.run.tcloudbase.com`）
- 前端通过 `API_BASE` 配置指向后端域名（后端已开启 CORS，跨域调用没问题）

## 部署步骤

### 1. 部署后端，拿到 HTTPS 域名
任选其一（详见各文档）：
- **微信云托管**：`README-云托管部署.md`，用现有 `server/Dockerfile` 推镜像，绑你已备案的自定义域名或平台默认域名
- **自有服务器**：`README.md` 里的 Nginx + Docker 部署，配 HTTPS
- 得到后端域名，记为 `BACKEND`（形如 `https://xxx`）
- 💡 **网页版不受微信"合法域名"限制**：小程序需在 mp.weixin.qq.com 登记合法域名，但浏览器网页直接 `fetch` 任意 HTTPS 域名（只要后端 CORS 允许，本项目已 `allow_origins=*`）即可。因此**云托管的默认公网域名（如 `xxx.run.tcloudbase.com`）就能直接填进前端，无需 ICP 备案自定义域名**。

### 2. 前端填入后端域名
编辑 `server/web/index.html` 顶部一行：
```js
const API_BASE = "https://你的后端域名"   // 例如 "https://apple-xxxx.run.tcloudbase.com"
// 同源部署（本机 /demo、或后端与网站同域）则留空 ""
```
> 当前文件默认 `API_BASE = ""`（同源），本机 `http://127.0.0.1:8000/` 直接可用。

### 3. 上传前端到 52byte.com
把 `server/web/index.html` 作为网站根文件上传到 `liubojun.52byte.com`（覆盖现有扫雷页）。
该文件是**单文件、无外部 CDN 依赖**，直接传这一个文件即可。

### 4. 验证
浏览器打开 `https://liubojun.52byte.com/` → 顶部状态条应显示「模型已加载 · 真实推理」，上传苹果图即可检测。

## 我（AI）无法替你完成的操作
- 登录 `52byte.com` 后台上传文件 / 改 DNS / 绑域名（需你的账号凭证）
- 登录云托管 / 服务器控制台执行部署
- 购买 / 备案域名

这些需要你本人在对应平台控制台操作；代码与配置文件我已准备好。

## 如果你其实想"整个项目在同一个域名下"
那就不能只用 52byte.com 的静态空间，需要：
- 后端也部署到某个**支持容器的平台并绑 `52byte.com` 子域**（如 52byte 提供容器服务），或
- 把 `liubojun.52byte.com` 的解析指向你自己的服务器（服务器上 Nginx 同时托管前端静态页 + 反代后端）
取决于 52byte.com 是否提供后端/容器能力。
