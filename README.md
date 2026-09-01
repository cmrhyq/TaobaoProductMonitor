# TaobaoProductMonitor

淘宝商品价格监控工具 —— 自动追踪商品价格变动，降价时发送邮件通知。

## 功能特性

- **双重价格获取策略**：优先使用淘宝 H5 API，失败时自动降级为 Playwright 浏览器抓取
- **补贴价/到手价识别**：自动提取补贴、促销后的真实到手价，与优惠前挂牌价双轨记录（issue #5）
- **价格诊断命令**：`probe-price` 逐通道打印价格提取明细，便于排查抓取问题
- **灵活的监控规则**：支持绝对降价、百分比降幅、目标价格等多种规则
- **结构化日志**：使用 structlog 输出 JSON（生产）/ 彩色文本（开发）日志
- **多数据库支持**：SQLAlchemy ORM，同时支持 SQLite（默认）和 MySQL
- **双启动模式**：CLI 命令行管理 + FastAPI Web 服务
- **邮件通知**：降价达标时自动发送 HTML 格式通知邮件（Jinja2 模板）

## 项目结构

```
TaobaoProductMonitor/
├── api/
│   ├── app.py                 # FastAPI 应用实例
│   ├── deps.py                # 依赖注入
│   └── routes/                # REST 路由
├── config/
│   ├── settings.py            # pydantic-settings 配置
│   ├── logging_config.py      # structlog 日志配置
│   └── manager_config.py      # 项目路径管理
├── data/
│   ├── database.py            # SQLAlchemy Engine/Session
│   ├── models.py              # ORM 模型
│   └── repository/            # 数据访问层
├── db/
│   ├── init_sqlite.sql        # SQLite 建表脚本
│   ├── init_mysql.sql         # MySQL 建表脚本
│   ├── migration_v2.sql       # v1 → v2 迁移脚本
│   └── migration_v3.sql       # v2 → v3 迁移脚本（price_history.original_price）
├── domain/
│   ├── entity/                # 数据实体
│   └── enums/                 # 枚举定义
├── resource/
│   └── template/              # 邮件 Jinja2 模板
├── service/
│   └── monitor/
│       ├── taobao_monitor.py  # 核心监控逻辑
│       ├── taobao_h5_api.py   # H5 API 客户端
│       ├── playwright_fallback.py  # Playwright 降级抓取
│       └── price_fetcher.py   # 统一价格获取服务
├── task/
│   └── task.py                # 定时任务入口
├── utils/
│   ├── common.py              # 通用工具函数
│   ├── send_email.py          # 邮件发送服务
│   └── template.py            # Jinja2 模板渲染
├── cli.py                     # CLI 入口（click）
├── main.py                    # 向后兼容入口
├── tests/                     # 单元测试（pytest）
├── requirements.txt           # Python 依赖
├── requirements-dev.txt       # 开发依赖
├── .env.example               # 环境变量模板
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置环境变量

复制模板并填写配置：

```bash
cp .env.example .env
```

关键配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DB_TYPE` | 数据库类型 | `sqlite` |
| `DB_SQLITE_PATH` | SQLite 文件路径 | `db/product_monitor.db` |
| `TAOBAO_APP_KEY` | H5 API AppKey | `12574478` |
| `MAIL_HOST` | SMTP 服务器 | — |
| `MAIL_SENDER` | 发件邮箱 | — |
| `MAIL_LICENSE_KEY` | SMTP 授权码 | — |

### 3. 获取 TAOBAO_APP_KEY

`TAOBAO_APP_KEY` 是淘宝 H5 移动端页面的前端签名密钥，用于调用 `mtop` 接口时生成请求签名。获取方式：

1. **使用默认值**：项目已内置默认 AppKey `12574478`，这是淘宝 H5 公开页面通用的前端密钥，大多数场景下可直接使用，无需额外操作。

2. **手动抓取获取最新值**（当默认值失效时）：
   - 打开浏览器，访问任意淘宝商品 H5 页面（如 `https://h5.m.taobao.com/`）
   - 打开开发者工具 (F12) → Network 面板
   - 筛选包含 `mtop` 的请求
   - 查看请求 URL 中的 `appKey` 参数值，即为当前有效的 AppKey
   - 将该值填入 `.env` 文件的 `TAOBAO_APP_KEY` 字段

3. **注意事项**：
   - 该 Key 是淘宝前端公开参数，非开放平台的 Secret，不涉及账户安全
   - 淘宝可能周期性更换该值，如果价格获取持续失败可尝试重新抓取
   - 即使 H5 API 失效，系统会自动降级到 Playwright 浏览器抓取

### 4. 初始化数据库

首次运行时 SQLAlchemy 会自动创建所有表结构，通常无需手动操作。如需手动初始化或重置 SQLite 数据库：

```bash
# 自动初始化（推荐）：首次执行任意 CLI 命令即可
python cli.py product list

# 手动初始化：使用 SQL 脚本
sqlite3 db/product_monitor.db < db/init_sqlite.sql

# 从 v1 迁移到 v2
sqlite3 db/product_monitor.db < db/migration_v2.sql
```

数据库文件默认路径为 `db/product_monitor.db`，可通过 `.env` 中的 `DB_SQLITE_PATH` 修改。

### 5. 启动方式

CLI 模式（推荐），立即执行一轮监控
```bash
python cli.py run --once
```

启动定时调度
```bash
python cli.py run --schedule
```

添加监控商品
```bash
python cli.py product add
```

查看商品列表
```bash
python cli.py product list
```

诊断价格提取（排查补贴价/到手价抓取问题）
```bash
python cli.py probe-price --url "商品链接"
```

启动 Web API 服务
```bash
python cli.py server
```

兼容模式，等同于 run --schedule
```bash
python main.py
```

### 5. Web API

启动后访问 `http://localhost:8000/docs` 查看 Swagger 文档。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/products` | GET | 商品列表 |
| `/products` | POST | 添加商品 |
| `/products/{id}` | DELETE | 删除商品 |
| `/monitor/trigger` | POST | 手动触发监控 |

## 价格获取策略

### 双价格语义

淘宝商品页面通常同时存在「优惠前价格」和「补贴/促销后价格」。本项目采用双价格语义：

- **到手价（price）**：检测到补贴/促销价（`promotionPrice`、`promoPrice`、`skuPromoPrice`、`extraPrices` 等字段）时取其最低值，否则取页面展示价。降价监控、规则比较均基于到手价
- **优惠前价格（original_price）**：仅在检测到真实优惠差价时记录（`price_history.original_price` 列），降价邮件中会以「优惠前价格 → 到手价（补贴后）」的样式展示

### 提取链路

```
┌─────────────────┐
│  PriceFetcher   │
└────────┬────────┘
         │
    ┌────▼────┐     成功
    │ H5 API  │──────────▶ 返回 (到手价, 优惠前价格)
    └────┬────┘
         │ 失败
    ┌────▼────────┐  成功
    │ Playwright  │──────────▶ 返回 (到手价, 优惠前价格)
    └────┬────────┘
         │ 失败
         ▼
    返回获取失败
```

### 价格诊断

当某个商品抓取不到价格或补贴价时，使用诊断命令逐通道查看提取明细：

```bash
python cli.py probe-price --url "https://item.taobao.com/item.htm?id=xxxx"
```

输出内容包括：mtop JSONP API 解析结果与响应中的价格相关字段、移动页正则的原始匹配、Playwright 页面提取结果。淘宝字段结构变更时，可依据此输出快速定位问题。

### 运行测试

```bash
pip install -r requirements-dev.txt
python -m pytest tests/
```

## 技术栈

| 组件 | 技术 |
|------|------|
| HTTP 客户端 | httpx |
| 浏览器自动化 | Playwright |
| 配置管理 | pydantic-settings |
| 结构化日志 | structlog |
| 任务调度 | schedule |
| 数据库 | SQLite / MySQL |

## 许可证

MIT License
