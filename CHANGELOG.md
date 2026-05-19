# Changelog

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
