# Changelog

## [3.0.1] - 2026-10-08

### 🐛 Bug Fixes

- **`python -m tbmon` 完全不可用**：`tbmon/__main__.py` 文件缺失，执行时直接报
  `No module named tbmon.__main__; 'tbmon' is a package and cannot be directly executed`。
  README、DEVELOPMENT 与 CLI 帮助里都宣传了这条命令（无桌面环境时生成登录态的唯一途径），
  但入口并不存在 —— 已补回并通过 `--version` / `--help` / `check` 冒烟验证。
- **`TB_DESKTOP_UA` 配置项形同虚设**：`BrowserSession` 用的是模块级常量 `DESKTOP_UA`，
  `Settings.desktop_ua` 从未被读取。已改为读取配置项（有配置却不可改，比缺配置更误导）。

### Changed

- **`tbmon` 包结构按职责重新分层**（行为不变，96 个用例全绿 + 真实抓取端到端逐字段一致）：

  | 调整前 | 调整后 |
  |--------|--------|
  | `models.py` | `models/{product,report}.py`（领域模型 / 过程记录分离） |
  | `parser.py`（490 行） | `parsers/{values,extract,detail}.py`（通用取值 / 淘宝字段抽取 / 装配入口） |
  | `session.py`（273 行） | `session/{state,session,login}.py`（登录态 / 浏览器会话 / 扫码流程） |
  | `cli.py`（241 行） | `cli/{main,render}.py`（命令装配 / 终端渲染） |
  | `fetchers/browser.py` 内嵌 JS | `fetchers/scripts.py` |
  | `service.py` 的 if-else 构造策略 | `fetchers/registry.py` 声明式注册表 |
  | —— | `tbmon/py.typed`（PEP 561 类型标记） |

- **策略注册表取代分支判断**：新增 `fetchers/registry.py`（`StrategyContext` + `REGISTRY` + `STRATEGY_ORDER`），
  新增策略只需实现 `Fetcher` 协议 + 注册一行，`service.py` 不再出现任何策略名；
  并加入「注册表与优先级顺序必须一一对应」的导入期自检，防止"加了策略忘了排序"。
- 子包 `__init__.py` 全部做再导出，`from tbmon.models import X` / `from tbmon.session import validate_state`
  等既有导入路径保持不变；仅 `tbmon.parser` 因改为复数包名而变更为 `tbmon.parsers`（测试同步更新）。
- 各模块补齐 `__all__` 与完整类型标注。

### New Features

- **新增 `pyproject.toml`**：打包元数据 + pytest 配置（`testpaths` / `pythonpath`）+ ruff 配置。
  测试不再依赖 `tests/conftest.py` 里手工插 `sys.path`，且可从任意目录执行。
- **`requirements-dev.txt` 新增 ruff**；`.gitignore` 补充 `.ruff_cache/` 与 `.scratch/`。

### Removed

- 死代码：`ItemService._build_fetcher` 中的策略分支、`service.iter_strategies()`、
  `session.now_utc_iso()`、`fetchers/browser.py:_AUTH_HINTS`（均无任何调用方）。
- 死配置：`TB_RAW_DUMP_DIR`（从未被读取，落盘路径由 `fetch(save_raw=...)` 显式指定）。

### Code Quality

- 全项目接入 ruff（`F` / `E` / `W` / `I` / `UP` / `B`），修复 127 条告警后 **0 告警**
  （119 条语法现代化自动修复 + 8 条手工处理：未使用导入、隐式 Optional、行尾空白）。
- `data/__init__.py` 补 `__all__`，`config/logging_config.py:get_logger` 修正隐式 Optional 标注。

## [3.0.0] - 2026-10-08

### Breaking Changes

- **删除全部命令行入口，只保留 Web API**：`cli.py`（317 行，click）与 `main.py` 已删除。
  启动方式统一为 `python -m uvicorn api.app:app`；`run/probe-price/product/login/server` 六个命令的能力全部迁移到 API 端点。
- **抓取配置前缀变更**：`TAOBAO_*` / `PROXY_*` / `PLAYWRIGHT_*` 三组配置项删除，统一为 `TB_*` 一组。
  注意 `PLAYWRIGHT_HEADLESS=false` 必须显式迁移为 `TB_HEADLESS=false`，否则会静默变回无头模式。
- **`service/monitor/` 包收敛为 `service/monitor.py` 单模块**；`domain/` 包删除（`EmailSender` 并入 `utils/email/send_email.py`）。
- `/monitor/trigger` 在已有轮次执行时返回 **409**（原为无条件启动新轮次）。

### Changed

- **抓取后端整体替换为 `tbmon`**：删除旧抓取三件套（`taobao_h5_api.py` 755 行、`playwright_fallback.py` 420 行、`price_fetcher.py` 184 行）。
  实网探测结论：纯 HTTP 直连 mtop 接口即使带正确签名与登录态仍被风控 `RGV587` 拦截；H5 详情页链路在真实浏览器下同样被拦并跳 `punish` 页；
  PC 详情页正常渲染且 SSR 数据与标准详情接口同构 —— 因此改为以 PC 页 SSR 为首选通道，失败降级到页面请求截获与 DOM 提取。
- **定时监控内嵌服务生命周期**：新增 `task/scheduler.py`，随 FastAPI lifespan 起停，间隔由 `MONITOR_INTERVAL_MINUTES` 配置；
  `/monitor/trigger` 与调度器共用同一把轮次互斥锁。
- **扫码登录改为 API 端点**：`POST /session/login` 拉起有头浏览器并阻塞至成功或超时（超时 408）；
  `GET /session/state` 提供只读体检。不再自实现 Playwright 登录流程（原约 100 行）。
- **轮次可观测**：新增 `GET /monitor/status`（是否在跑 / 上轮结果 / 上轮错误 / 跳过原因）与 `GET /monitor/schedule`（开关 / 间隔 / 下次执行时间）。
- **登录态前置体检**：单轮监控开始前先体检，失效时只提示一次并跳过本轮，不再让 N 个商品各撞一次登录页、各耗尽一轮重试。
- `TaobaoMonitor` 改为依赖注入 + 上下文管理，浏览器会话在轮次内创建并关闭（Playwright 同步对象禁止跨线程使用）。
- 抓取入参改为 `product_url` 而非存量 `item_id` —— 每次重新解析短链，天然覆盖旧代码「短链改版导致存量 ID 失效后再解析一次」的补丁逻辑。

### New Features

- **`product_snapshot` 表**：保存每次抓取的富数据（标题 / 副标题 / SKU 各规格价与库存 / 商品参数 / 店铺 / 主图 / 数据来源）。
  存量库由 `init_db()` 的 `create_all` 自动建表，不 DROP / 不 ALTER 任何现有表；MySQL 参考脚本 `db/migration_v4.sql`。
- 新增端点：`GET /products/{id}/snapshot`、`GET /products/{id}/history`。
- `tbmon.link.parse_share_text()`：从分享文本一次性解析 platform / title / url / tk / item_id（缺失标题不再导致添加商品失败）。
- 配置新增 `MONITOR_SCHEDULE_ENABLED` / `MONITOR_INTERVAL_MINUTES` / `MONITOR_RUN_ON_STARTUP`。

### Bug Fixes

- **空代理配置导致抓取整体崩溃**：`.env` 中写 `TB_PROXY=`（留空）会被解析为空字符串并透传给 httpx，触发 `ValueError`。
  现在空值等价于未配置（配置层与 `LinkResolver` 双重归一化），并同步修正示例文件写法。
- **失败摘要渲染崩溃**：`AllStrategiesFailed.attempts` 是字符串列表，按对象访问会抛 `AttributeError`，已修正。

### Removed

- 死代码：`domain/`（`entity/product.py`、`entity/price.py`、`entity/email.py`、`enums/base_enums.py`）、
  `utils/common.py`、`utils/id/`、`api/deps.py`、根目录 `OpenAPI.json`（FastAPI 运行时自动生成同等文档）。
- 测试 `tests/test_price_parsing.py`（53 个用例，覆盖的是已失效的旧抓取实现）。

### Tests

- 新增 39 个离线用例：`test_share_text`(6)、`test_snapshot_repo`(4)、`test_monitor_backend`(15)、
  `test_scheduler`(8)、`test_api`(12)；`tests/tbmon` 的 51 个用例（含真实 SSR 数据回归）保持全绿，合计 96 个。

## [2.0.2] - 2026-09-03

### Changed

- **抓取通道现状适配（issue #5 跟进）**：2026 年淘宝改版后移动/PC 详情页均为纯 JS 渲染壳（HTML 不再内嵌价格字段），且 mtop JSONP 端点在风控期被 x5sec WAF 挑战拦截（仅 x5referer cookie 握手无法通过，必须真实浏览器执行 JS）
- **Playwright 新增最高优先级策略**：拦截页面自身发起的 mtop detail 请求（`mtop.taobao.detail*` / `pcdetail` / `wdetail`），直接解析真实 payload——页面自带签名与 Cookie，最抗改版与风控，且能拿到页面渠道下发的最新补贴/促销字段
- **payload 双轨解析抽为共享函数** `parse_prices_from_mtop_response`（`taobao_h5_api.py` 模块级），JSONP 通道与 Playwright 拦截通道共用同一套「到手价 / 优惠前价」解析逻辑
- **mtop JSONP 通道快速降级**：识别 x5referer 反爬跳转后单次种 cookie 重试；仍被拦截则明确告警并让位 Playwright（不再空转 3 次）
- **短链 item_id 解析加固**：支持 e.tb.cn 新式分享链（`shareDetailItemId` 优先），拒绝 `id=NN` 跟踪参数误判；监控抓取失败时用重新解析的 id 重试一次
- 新增 13 个单元测试（JSONP 解包、x5referer 识别、mtop URL 过滤、共享 payload 解析、短链解析），全量 45 个通过

### Changed (2.0.2 补充，2026-09-04 实测)

- **详情页登录墙适配**：实测淘宝 H5/Web 详情页已强制登录——匿名访问跳转 `login.m.taobao.com`，mtop 详情只返回「打开 App」壳子（`data` 仅含 `url/h5url/dialogSize`），补贴价只在登录态下返回
  - 新增 `python cli.py login`：弹出浏览器登录淘宝（扫码/账密），校验不再跳登录页后保存 Playwright `storage_state`（默认 `taobao_storage_state.json`）
  - 新增 `PLAYWRIGHT_STORAGE_STATE` 配置；监控链路与 `probe-price` 的 Playwright 通道自动携带登录态
  - 触发登录墙时给出明确提示（运行 `cli.py login`），不再静默失败
- 新增 8 个单元测试（登录墙识别、storage_state 加载容错），全量 53 个通过
- **修复 `cli.py login` 导航竞争**：登录成功瞬间登录页仍在自动跳转（"欢迎回来"页），此时直接 `goto` 商品页会被 Playwright 判为 navigation interrupted。改为：先等登录跳转稳定 → 新开页面校验（导航中断自动重试一次）→ 以会话 Cookie（`cookie2`/`_tb_token_`/`unb`）为准判定登录成功
- `taobao_storage_state.json` 加入 `.gitignore`（含会话凭证，禁止入库）

## [2.0.1] - 2026-09-02

### Bug Fixes

- **补贴后价格无法获取（issue #5）**：重写价格提取为双价格通道——
  - mtop JSONP API：解析 `promotionPrice`/`promoPrice`/`extraPrices`/`skuCore.sku2info` 等补贴价字段（此前 `data.item.price` 挂牌价最先命中即返回，促销价字段从未进入结构化解析）
  - 移动页/整页正则：`promotionPrice`/`skuPromoPrice` 等模式与常规价格分开扫描，检测到补贴价时优先生效（此前 `promotionPrice` 排在常规 `price` 之后，首次命中循环永远轮不到）
  - Playwright：新增 `PROMO_SELECTORS`（`tm-promo-price` 等），促销价先于挂牌价提取（此前 `span.tm-promo-price` 排在所有选择器最后）
  - 字符串价格值容忍货币符号前缀（`"¥299.00"` 此前无法匹配正则）

### New Features

- `price_history` 表新增 `original_price` 列记录优惠前挂牌价；旧库由 `init_db()` 自动迁移，MySQL 手动脚本见 `db/migration_v3.sql`
- 降价邮件新增「优惠前价格 → 到手价（补贴后）」展示（检测到补贴价时）
- 新增 `python cli.py probe-price` 价格诊断命令：逐通道打印到手价/优惠前价格及响应中的原始价格字段，便于排查抓取问题
- 新增单元测试 `tests/test_price_parsing.py`（22 个用例）与 `requirements-dev.txt`

## [2.0.0] - 2026-05-19

### Breaking Changes

- 数据访问层从手写 SQL (`dao/`) 全面迁移到 SQLAlchemy ORM (`data/`)，原 `dao/` 包已移除
- 启动入口从 `main.py` 变更为 `cli.py`（`main.py` 保留为向后兼容入口）
- 邮件模板从位置占位符 `{0},{1}` 改为 Jinja2 命名变量，`EmailParams` dataclass 已移除
- Selenium 及相关依赖完全移除，改用 Playwright 作为浏览器自动化方案

### New Features

- **CLI 命令行工具**：基于 click，支持 `run --once/--schedule`、`product add/list`、`server` 子命令
- **FastAPI Web 服务**：REST API 支持商品 CRUD、手动触发监控、健康检查，内置 Swagger 文档
- **SQLAlchemy ORM**：声明式模型定义，支持 SQLite/MySQL，自动建表，Session 上下文管理
- **Jinja2 模板引擎**：命名变量、自定义过滤器（currency/percent）、条件渲染支持
- **OpenAPI 规范文件**：`docs/openapi.json` 提供完整接口定义
- **淘宝 H5 API 逆向**：直接调用 mtop 接口获取价格，减少对页面渲染的依赖
- **双重价格获取策略**：H5 API 优先，失败自动降级 Playwright 浏览器抓取
- **灵活监控规则**：支持绝对降价、百分比降幅、目标价格三种规则类型
- **pydantic-settings 配置**：类型安全的环境变量加载与校验

### Improvements

- **数据库层**：ORM 替代手写 SQL，Repository 模式，事务自动管理，连接池 pool_pre_ping
- **邮件模板系统**：单例 Environment，currency 过滤器保留两位小数，自动计算降幅百分比
- **邮件 UI 重设计**：电商收据风格（暖白底 + 淘宝橙 + 虚线票据 + 方角按钮），移除所有外部 CDN 图片
- **配置系统**：Settings 新增 database_url 属性，直接生成 SQLAlchemy DSN
- **日志系统**：全面迁移到 structlog 结构化日志，JSON（生产）/ 彩色文本（开发）双输出
- **README 更新**：新项目结构、启动方式、API 端点文档、TAOBAO_APP_KEY 获取说明

### Refactoring

- 删除 Selenium 相关代码：`common/selenium_service.py`、`domain/entity/selenium.py`、`utils/selenium/`
- 删除旧 Cookie 管理：`service/cookie/`、`resource/cookie_pickle/`
- 删除旧配置系统：`config/read_conf.py`
- 删除冗余工具代码：`utils/internet_utils.py`（677 行）、`utils/time_utils.py`
- 删除废弃代码：`service/monitor/taobao_old.py`、`test/`、`db/init_database.cmd`
- 清理枚举：移除 `LocateElementMethod`（Selenium 专用）
- 统一日志：`send_email.py`、`template.py` 从 loguru/print 迁移到 structlog
- 移除旧 DAO 层：整个 `dao/` 目录（6 个文件）替换为 `data/`

### Dependencies

新增：

- `sqlalchemy>=2.0`
- `click>=8.1`
- `fastapi>=0.111`
- `uvicorn[standard]>=0.29`
- `Jinja2>=3.1`
- `httpx>=0.27.0`
- `playwright>=1.44.0`
- `pydantic>=2.7.0`
- `pydantic-settings>=2.3.0`
- `structlog>=24.1.0`

移除：

- `selenium`
- `webdriver-manager`
- `loguru`
- `Flask`
- `pyperclip`

变更：

- `PyMySQL==1.1.1` → `pymysql>=1.1`
- `schedule==1.2.2` → `schedule>=1.2.0`

### Bug Fixes

- 修复 structlog 使用 PrintLoggerFactory 导致 add_logger_name 崩溃
- 修复 requirements.txt 中 schedule>=2.1 版本不存在的问题
- 修复旧 send_email.py 中 `open('image_path', 'rb')` 硬编码字符串 bug
