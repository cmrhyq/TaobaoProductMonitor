# TaobaoProductMonitor

淘宝 / 天猫商品价格监控服务 —— 定时抓取商品价格与完整商品信息，命中降价规则时发送邮件通知。

**对外的唯一业务入口是 Web API（FastAPI）**：商品管理、价格历史、快照查询、扫码登录、监控触发都在 HTTP 接口里完成。
定时监控由服务内嵌的调度器驱动，随服务启停。项目不提供任何命令行业务入口。

---

## 功能特性

| 能力 | 说明 |
|------|------|
| 实网验证过的抓取链路 | 独立包 `tbmon`，PC 详情页 SSR（`source=ssr-pc`）为首选，失败自动降级到页面接口截获与 DOM 提取 |
| 富数据落库 | 除价格外还保存标题、副标题、SKU 各规格价与库存、商品参数、店铺、主图（`product_snapshot` 表） |
| 双价格语义 | 实付价（优惠后）与优惠前价（划线价）双轨记录，降价邮件按「优惠前 → 实付」展示 |
| 三种监控规则 | 绝对降额 `absolute_drop`、百分比降幅 `percent_drop`、目标价 `target_price` |
| 扫码登录 API | `POST /session/login` 拉起有头浏览器，扫码后登录态落盘（约 30 天有效期） |
| 内嵌定时监控 | 随服务 lifespan 起停，间隔可配；手动触发与定时调度共用一把轮次互斥锁 |
| 登录态前置体检 | 失效时只提示一次并跳过本轮，不会让 N 个商品各撞一次登录页 |
| 轮次可观测 | `/monitor/status` 看单轮进度与错误，`/monitor/schedule` 看下次执行时间 |
| 多数据库 | SQLAlchemy 2.0 ORM，SQLite（默认）/ MySQL |

---

## 项目结构

```
TaobaoProductMonitor/
├── api/                            # 唯一业务入口：FastAPI
│   ├── app.py                      # 应用实例 + lifespan（init_db、起停内嵌调度器）
│   └── routes/
│       ├── health.py               # 健康检查
│       ├── products.py             # 商品 CRUD + 价格历史 + 最近一次快照
│       ├── monitor.py              # 手动触发 / 轮次状态 / 调度信息
│       └── session.py              # 登录态体检 + 扫码登录
│
├── tbmon/                          # 抓取实现（唯一），可脱离本项目独立使用
│   ├── config.py                   # TB_* 配置（Settings）+ 空串归一化
│   ├── errors.py                   # 异常体系：retryable / needs_human 决定重试策略
│   ├── link.py                     # 分享文本 / 短链 → 商品 ID（含 parse_share_text）
│   ├── service.py                  # ItemService：策略降级 / 重试 / 留痕
│   ├── py.typed                    # PEP 561 类型标记
│   ├── models/                     # 领域模型
│   │   ├── product.py              # Money / SkuInfo / ShopInfo / ProductInfo
│   │   └── report.py               # AttemptRecord / FetchReport / StateStatus
│   ├── parsers/                    # 容错解析（候选路径 + 广度优先兜底）
│   │   ├── values.py               # 通用取值工具（deep_get / find_first / to_decimal…）
│   │   ├── extract.py              # 淘宝字段抽取：价格 / SKU / 商品参数
│   │   └── detail.py               # 装配入口：parse_mtop / parse_dom / parse
│   ├── session/                    # 登录会话
│   │   ├── state.py                # 登录态体检（不依赖 playwright，可离线测）
│   │   ├── session.py              # BrowserSession：playwright 生命周期
│   │   └── login.py                # 扫码登录流程
│   ├── fetchers/                   # 抓取策略
│   │   ├── base.py                 # Fetcher 协议、FetchOutcome、JSONP 剥壳、限速器
│   │   ├── registry.py             # 策略注册表与优先级（新增策略只改这里）
│   │   ├── scripts.py              # 注入浏览器的 JS 片段
│   │   ├── browser.py              # 主力策略：PC 页 SSR → 接口截获 → DOM 提取
│   │   └── mtop_http.py            # 机会性策略：纯 HTTP 直连 mtop（被风控，见 DEVELOPMENT）
│   ├── cli/                        # 开发者排障工具（⚠️ 非业务入口）
│   │   ├── main.py                 # argparse 装配与命令分派
│   │   └── render.py               # 终端渲染
│   └── __main__.py                 # python -m tbmon 入口
│
├── service/monitor.py              # TaobaoMonitor：抓取 → 落价 → 落快照 → 规则判定 → 通知
│
├── task/
│   ├── task.py                     # 单轮监控执行 + RunState + 轮次互斥锁
│   └── scheduler.py                # 内嵌调度器（schedule + 常驻守护线程）
│
├── data/                           # SQLAlchemy ORM + Repository
│   ├── database.py                 # engine / SessionLocal / get_session / init_db（含 _migrate_schema）
│   ├── models.py                   # users / products / price_history /
│   │                               # monitor_rules / notification_log / product_snapshot
│   └── repository/
│       ├── product_repo.py         # 商品（脱管 ORM 对象，只读 + 显式 UPDATE）
│       ├── price_repo.py           # 价格时间序列
│       ├── rule_repo.py            # 监控规则
│       ├── notification_repo.py    # 通知留痕
│       └── snapshot_repo.py        # 商品富数据快照
│
├── config/
│   ├── settings.py                 # 唯一运行时配置入口（app / db / mail / monitor / fetch）
│   └── logging_config.py           # structlog 配置
│
├── utils/email/                    # SMTP 发信 + Jinja2 模板
├── resource/template/              # 降价邮件 HTML 模板
├── db/                             # 建表与迁移脚本、SQLite 数据文件、备份
├── tests/                          # pytest，全离线，共 96 个用例
├── pyproject.toml                  # 打包元数据 + pytest / ruff 配置
├── requirements.txt                # 运行时依赖
├── requirements-dev.txt            # 开发依赖（pytest / ruff）
├── CHANGELOG.md                    # 变更记录
└── DEVELOPMENT.md                  # 抓取方案决策记录：三条路线的证伪证据与取舍
```

**分层方向**（单向依赖，不允许回指）：

```
api/routes  →  task/{task,scheduler}  →  service/monitor.py  →  data/{models,repository}
                                              ↓
                                          tbmon/（抓取）      config/settings.py（配置）
```

---

## 快速开始

### 1. 安装

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows；Linux/macOS 用 source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置

```bash
cp .env.example .env
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `APP_NAME` / `LOG_LEVEL` / `DEBUG` | 应用名 / 日志级别 / 调试开关 | `TaobaoProductMonitor` / `INFO` / `false` |
| `DB_TYPE` | 数据库类型 `sqlite` / `mysql` | `sqlite` |
| `DB_SQLITE_PATH` | SQLite 文件路径（相对项目根） | `db/ProductMonitor.db` |
| `DB_MYSQL_*` | MySQL 连接参数（`DB_TYPE=mysql` 时生效） | — |
| `MAIL_HOST` / `MAIL_PORT` | SMTP 服务器 | `smtp.163.com` / `25` |
| `MAIL_SENDER` / `MAIL_LICENSE_KEY` | 发信邮箱与授权码 | — |
| `TB_STORAGE_STATE` | 登录态文件（相对路径按项目根解析） | `taobao_storage_state.json` |
| `TB_HEADLESS` | 抓取时是否隐藏浏览器窗口；**登录始终有头** | `false` |
| `TB_NAV_TIMEOUT_MS` | 页面导航超时 | `45000` |
| `TB_EVAL_TIMEOUT_MS` | 等待 SSR 数据注入超时 | `15000` |
| `TB_HTTP_TIMEOUT_S` | HTTP 请求超时 | `15` |
| `TB_MAX_ATTEMPTS` | 单策略最大尝试次数 | `3` |
| `TB_MIN_INTERVAL_S` | 同域最小请求间隔（限速） | `1.5` |
| `TB_APP_KEY` | mtop appKey（HTTP 机会性策略用） | `12574478` |
| `TB_PROXY` | 代理；**留空即不使用**（不要写成 `TB_PROXY=`） | — |
| `MONITOR_SCHEDULE_ENABLED` | 是否随服务启用定时监控 | `true` |
| `MONITOR_INTERVAL_MINUTES` | 监控轮次间隔（分钟） | `60` |
| `MONITOR_RUN_ON_STARTUP` | 服务启动后是否立即跑一轮 | `false` |

抓取参数全部收敛在 `TB_*` 一组前缀下（由 `tbmon.config.Settings` 提供），项目中不存在第二处同名配置。

### 3. 启动服务

```bash
python -m uvicorn api.app:app --host 0.0.0.0 --port 8000
```

打开 <http://localhost:8000/docs> 可查看并交互式调用全部API。

> ⚠️ **必须单 worker**（uvicorn 默认即单 worker，**不要加 `--workers`**）。
> SQLite 单文件、进程内轮次锁、进程内调度器、有头浏览器四者都要求单进程；
> 多 worker 会让同一份调度被重复执行 N 次，而轮次锁跨进程无效。
> `--reload` 仅用于开发调试。

### 4. 登录淘宝（首次 / 登录态失效后）

淘宝强制登录，抓取前必须有有效登录态。

```bash
# 体检：只读检查文件与 cookie，不启动浏览器
curl http://127.0.0.1:8000/session/state

# 扫码登录：服务所在机器会弹出浏览器窗口，请求阻塞至成功或超时（默认 300s）
curl -X POST http://127.0.0.1:8000/session/login \
  -H "Content-Type: application/json" -d '{"timeout_s": 300}'
```

返回体自带逐步等待日志。登录成功瞬间浏览器会自动续期 cookie 并回写登录态。

**无桌面环境（容器 / 远程服务器）无法弹窗时**，在本机生成登录态文件再复制过去
（这是保留 `python -m tbmon` 的唯一原因）：

```bash
python -m tbmon login      # 本机扫码
python -m tbmon check      # 体检
```

### 5. 添加商品并触发监控

```bash
# 用淘宝 App 复制的分享文本添加（自动解析链接、标题、商品 ID、tk）
curl -X POST http://127.0.0.1:8000/products \
  -H "Content-Type: application/json" \
  -d '{"share_text":"【淘宝】https://e.tb.cn/h.xxx?tk=yyy CZ028 「商品标题」","notify_email":"you@example.com"}'

# 手动触发一轮（后台线程执行，已在跑则返回 409）
curl -X POST http://127.0.0.1:8000/monitor/trigger

# 查看本轮结果
curl http://127.0.0.1:8000/monitor/status

# 查看抓取到的完整商品信息与价格历史
curl http://127.0.0.1:8000/products/1/snapshot
curl http://127.0.0.1:8000/products/1/history
```

若 `MONITOR_SCHEDULE_ENABLED=true`，服务启动后会按 `MONITOR_INTERVAL_MINUTES` 周期自动执行，
下次执行时间见 `GET /monitor/schedule`。

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/products` | 商品列表 |
| POST | `/products` | 添加监控（分享文本，或手填 `product_url` + `product_name`） |
| GET | `/products/{id}` | 单个商品 |
| DELETE | `/products/{id}` | 删除商品 |
| GET | `/products/{id}/history` | 价格历史（默认最近 30 条，倒序） |
| GET | `/products/{id}/snapshot` | 最近一次抓取的完整商品快照 |
| POST | `/monitor/trigger` | 手动触发一轮（已有轮次执行时 **409**） |
| GET | `/monitor/status` | 是否在跑 / 上轮结果 / 上轮错误 / 跳过原因 |
| GET | `/monitor/schedule` | 调度开关 / 间隔 / 下次执行时间 |
| POST | `/session/login` | 扫码登录（阻塞至成功或超时，超时 408） |
| GET | `/session/state` | 登录态体检 |

---

## 数据模型

| 表 | 存什么 | 说明 |
|----|--------|------|
| `users` | 用户 | 当前固定使用 `user_id=1` |
| `products` | 监控中的商品 | 链接、标题、item_id、tk、通知邮箱、当前价/初始价/最低价、监控状态、检查次数/失败次数 |
| `price_history` | **窄时间序列** | 每次抓取一行：实付价 + 优惠前价 + 抓取方式（`fetch_method`） |
| `product_snapshot` | **富数据** | 每次抓取一行：标题、副标题、SKU 各规格价与库存、商品参数、店铺、主图、数据来源 |
| `monitor_rules` | 监控规则 | `absolute_drop` / `percent_drop` / `target_price` |
| `notification_log` | 通知留痕 | 通知类型、目标、内容、成功与否 |

设计上刻意把**窄高频的价格序列**与**宽低频的商品详情**分成两张表：
价格查询只扫窄表，商品详情按需取最近一条，避免时间序列被大字段拖重。

新增表由 `init_db()` 的 `Base.metadata.create_all()` 自动创建，不改动也不 DROP 任何现有表。
MySQL 请参考 `db/migration_v4.sql`。

> ⚠️ 存量库**只能**跑 `db/migration_v4.sql`（或直接 `create_all`），
> **不要**跑 `db/init_sqlite.sql` —— 后者含示例数据 INSERT，会污染真实数据。

---

## 价格语义

| 字段 | 含义 |
|------|------|
| `price_history.price` / `SnapshotResponse.price.current` | **实付价**（店铺优惠后，页面上写的「优惠后」/「到手价」） |
| `price_history.original_price` / `SnapshotResponse.price.original` | **优惠前价 / 划线价** |
| `SnapshotResponse.price.low` / `.high` | 多 SKU 商品的价格区间 |

在 PC 详情页 SSR 数据里：

- `skuCore.sku2info["0"].subPrice` 才是**实付价**；
- `skuCore.sku2info["0"].price` 是**优惠前价**。

搞反会把优惠前价当实付价报出去。老 schema 则相反（`price.price` 即当前价，原价在 `price.extraPrices`），
解析层已同时兼容两套，但**写业务代码时必须按上表语义理解**。

多 SKU 区间价商品常常没有统一实付价（`current` 为空，只有 `low`/`high`）：
监控取**区间最低价**并在日志中标注，否则这类商品会永久失败。

---

## 抓取链路

```
分享文本 / 链接 / 商品 ID
        │  tbmon.link.resolve（短链自动展开、最多 6 跳）
        ▼
    商品 ID ──▶ 浏览器打开 PC 详情页 item.taobao.com/item.htm?id=...
                    │
                    ├─ ① PC 页 SSR 数据 window.__ICE_APP_CONTEXT__      ← 首选，实网验证有效
                    │     .loaderData.home.data.res                    source = ssr-pc
                    ├─ ② 被动截获页面自身的 mtop 响应                   source = mtop-page
                    └─ ③ DOM 文本提取（按 class 语义 + 字号打分）        source = dom-page
        ▼
  tbmon.parser.parse → ProductInfo（Money / SkuInfo / ShopInfo / attributes / images）
        ▼
  TaobaoMonitor：价格落 price_history + 富数据落 product_snapshot
        ▼
  规则判定 → 命中则发邮件 + 记 notification_log + 该商品监控结束
```

**失败语义与重试策略**（`tbmon/errors.py`）：异常自带两个属性，编排层不做错误码 if-else。

- `retryable=True`（`TransportError`）：指数退避重试，最多 `TB_MAX_ATTEMPTS` 次；
- `needs_human=True`（`AuthRequiredError`）：立即停止并提示重新登录；
- `RiskControlError`：**刻意不可重试** —— 原地重试不会让风控消失，还会加重封禁，正确动作是更换策略。

### 为什么不用 H5 / 纯 HTTP

- **纯 HTTP 直连 mtop 接口**：带正确 `_m_h5_tk` 签名与有效登录 cookie，仍返回
  `RGV587_ERROR::SM::哎哟喂,被挤爆啦`。签名算法没写错，是请求指纹 / 运行环境被判定为不可信。
- **淘宝 H5 详情页整条链路**：真实浏览器 + 有效登录态下，页面自身接口同样返回 `RGV587`
  并跳转 `bixi.alicdn.com/punish/...`（页面显示「亲，访问被拒绝」），页内 `lib.mtop` 补发也无意义。
- **PC 详情页**：真实浏览器下正常渲染、页面自身 mtop 调用全部 `SUCCESS`，SSR 数据与标准详情接口同构。
  在 PC 页内用 `lib.mtop` 反调 H5 详情接口会得到 `UNEXCEPT_REQUEST::错误的请求类型`，因此不做补发请求。

---

## 运行测试

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q          # 96 个用例，全绿
```

pytest 配置在 `pyproject.toml`（`testpaths` / `pythonpath`），因此在任何目录下执行都能正确导入
`tbmon` 与业务包，不需要手工设置 `PYTHONPATH`。

测试**全离线**，不碰网络、不写真实数据库：

| 测试文件 | 覆盖内容 |
|----------|----------|
| `tests/tbmon/test_parser_real_data.py` | 用真实 SSR 数据做回归 —— 淘宝改版时这里最先报警 |
| `tests/tbmon/`（其余） | 链接解析、容错解析、会话体检、策略降级编排 |
| `tests/test_share_text.py` | 分享文本解析 |
| `tests/test_monitor_backend.py` | 业务编排（注入假抓取服务与假仓储） |
| `tests/test_snapshot_repo.py` | 快照落库 |
| `tests/test_scheduler.py` | 调度器（注入假轮次函数） |
| `tests/test_api.py` | API 契约 |

---

## 代码规范

静态检查用 ruff，配置在 `pyproject.toml`：

```bash
ruff check .          # 全项目检查（当前 0 告警）
ruff check . --fix    # 自动修复可修复项
```

启用的规则集刻意收敛为「一定有问题」的几类，不做风格洁癖：

| 规则 | 作用 |
|------|------|
| `F` | pyflakes：未使用导入、未定义名字等真实缺陷 |
| `E` / `W` | pycodestyle：缩进、空白、行尾 |
| `I` | isort：导入顺序（`tbmon` / `api` 等本仓库包归为 first-party） |
| `UP` | pyupgrade：过时写法（如 `Optional[X]` → `X \| None`） |
| `B` | flake8-bugbear：易错写法 |

工程约定：

- 所有模块使用 `from __future__ import annotations` + 完整类型标注，`tbmon` 带 `py.typed` 标记
- 每个模块定义 `__all__`，包的 `__init__.py` 只做再导出，不放实现
- 临时排障脚本放 `.scratch/`（已 gitignore），**不要用标准库同名文件名**
- 新增抓取策略：实现 `Fetcher` 协议 + 在 `tbmon/fetchers/registry.py` 注册一行，
  编排层（`service.py`）不需要改动

---

## 开发者排障

`tbmon` 自带命令行**仅作开发者工具**，不承接业务逻辑：

```bash
python -m tbmon login                                        # 扫码登录
python -m tbmon check                                        # 登录态体检
python -m tbmon resolve "分享文本"                            # 只解析商品 ID，不发抓取请求
python -m tbmon fetch "分享文本" -v --save-raw ./.scratch     # 单商品试抓，原始响应落盘
python -m tbmon fetch 1050906790941 --json                    # 结构化输出
```

`--save-raw` 用来在淘宝改版时对比字段结构。临时脚本请放在 `.scratch/`
（**别用标准库同名文件名**，脚本目录处于 `sys.path[0]` 会污染导入）。

---

## 已知限制

- **不支持淘口令**（形如 `￥xxxx￥`）：只支持含链接的分享文本，纯口令会返回 400
- **不做分享页价格兜底**：抓取失败即计失败，不会用分享链接页面上的价格快照顶替
- **扫码登录需要桌面环境**：容器部署请在本机执行 `python -m tbmon login` 后复制登录态文件
- **登录态约 30 天失效**：建议监控 `GET /session/state` 的 `expires_in_days`
- **App 专属活动价拿不到**：部分补贴价只在淘宝 App 原生渠道下发，网页渠道无此数据（平台限制，非解析问题）
- **必须单进程运行**：见上文启动章节的说明

---

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI + uvicorn |
| HTTP 客户端 | httpx |
| 浏览器自动化 | Playwright (Chromium) |
| 数据库 | SQLAlchemy 2.0 ORM（SQLite / MySQL） |
| 配置 | pydantic v2 + pydantic-settings |
| 日志 | structlog |
| 调度 | schedule（服务内嵌守护线程） |
| 邮件 | smtplib + Jinja2 |
| 测试 | pytest |

---

## 许可证

MIT License
