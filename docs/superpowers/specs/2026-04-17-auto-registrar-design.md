# Qwen2API 账号自动注册与补齐方案 (Auto-Registrar)

## 1. 概述 (Overview)
本项目旨在为 `qwen2API` 提供一套“三位一体”的千问账号自动注册机制。系统能够使用临时邮箱 API (`tempmail.lol`) 自动完成从获取邮箱、逆向注册、验证邮件到提取可用 Token 的全链路闭环。

该机制支持三种维度的使用场景：
1. **独立外挂脚本**：作为独立的 CLI 工具运行。
2. **后台守护任务 (Daemon)**：在主服务启动后监控可用账号池，低于阈值自动静默补齐。
3. **前端交互 API**：在管理面板提供“一键补号”按钮，供管理员按需生成。

## 2. 核心架构 (Architecture)

### 2.1 底层注册引擎 (`backend/services/auto_registrar.py`)
该模块是一个纯工具类 `QwenAutoRegistrar`，不持有全局状态，专门负责逆向交互与临时邮箱管理。

**工作流：**
1. **邮箱申请**：请求 `https://tempmail.lol/zh/api` 获取一个有效的临时邮箱地址（及其对应的 token/id）。
2. **千问注册请求**：使用 `curl_cffi` 库（带 `impersonate="chrome124"`），携带获取到的邮箱地址，向千问服务器发送注册（或发送验证码）请求。
3. **轮询收件箱**：循环调用 `tempmail.lol` 收件箱接口（最大等待 60 秒），查找来自千问的激活邮件或验证码。
4. **验证与激活**：提取邮件中的验证码或激活链接，提交给千问服务器完成账号激活流程。
5. **提取 Token**：成功激活后，通过千问接口获取 JWT Token，并与邮箱、生成的随机密码封装为 `Account` 对象。

### 2.2 调度层与后台补齐 (Daemon Task)
*   **入口**：在 `backend/main.py` 的 FastAPI `lifespan` 或后台协程中启动。
*   **逻辑**：
    *   定时轮询（如每 10 分钟）。
    *   计算 `AccountPool` 中健康账号（`status_code == 200` 且未被风控）的数量。
    *   当健康数量 `< TARGET_MIN_ACCOUNTS` (如 3 个) 时，触发 `QwenAutoRegistrar.register_account()`。
    *   **容错处理**：如遇滑块验证或 IP 封禁导致注册连续失败，执行指数退避休眠，避免死循环。
    *   **写入池**：成功获取新账号后，调用 `pool.add(acc)` 动态载入内存并持久化到 `data/accounts.json`。

### 2.3 交互层 (API & Frontend)
*   **后端 API (`backend/api/admin.py`)**：
    *   新增 `POST /api/admin/accounts/generate` 端点。
    *   接收请求体 `{ "count": 1 }`。
    *   调用底层引擎并发或顺序注册 `count` 个账号，返回成功列表和错误日志。
*   **前端页面 (`frontend/src/pages/AccountsPage.tsx`)**：
    *   新增“⚡ 自动补号”按钮。
    *   弹出输入框（默认数量 1），点击后显示全局 Loading。
    *   请求完成后提示成功数量，并调用现有接口重新拉取并刷新表格。

## 3. 数据流与异常处理 (Data Flow & Error Handling)

1. **临时邮箱失效/未收到邮件**：
    *   如果超过轮询时间（60s）未收到邮件，抛出 `TimeoutError`，放弃本次注册。
2. **注册端点风控拦截**：
    *   如果 `curl_cffi` 请求千问注册接口返回 `403`、验证码拦截或其他非预期状态，底层引擎抛出 `RegistrationBlockedError`。
3. **并发安全**：
    *   由于注册过程较长（包含轮询），底层方法必须为 `async`。
    *   通过前端触发多个注册时，采用 `asyncio.gather` 并发执行，每个任务申请独立的临时邮箱。

## 4. 依赖项 (Dependencies)
*   `curl_cffi`: 用于逆向千问接口（已存在于项目中）。
*   `httpx`: 用于调用 `tempmail.lol` API 获取临时邮箱（已存在于项目中）。

## 5. 实现步骤 (Implementation Steps)
1. **实现底层引擎**：编写 `auto_registrar.py`，实现获取邮箱、发送注册、轮询邮件、激活和提取 Token 的完整异步方法。
2. **集成后端 API**：在 `admin.py` 中添加 `POST /api/admin/accounts/generate` 路由。
3. **集成前端面板**：在 `AccountsPage.tsx` 中添加一键补号的 UI 和请求逻辑。
4. **集成后台守护进程**：在 `main.py` 中添加 `background_auto_refill_task`，定期检查并调用引擎补齐账号池。
