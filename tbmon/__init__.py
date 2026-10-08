"""tbmon —— 淘宝商品信息抓取（价格 / 规格 / 店铺 / 参数）。

快速上手：
    python -m tbmon login                                   # 首次：扫码登录
    python -m tbmon fetch "https://e.tb.cn/h.xxxx?tk=yyyy"   # 抓取商品信息

代码里使用：
    from tbmon import ItemService, Settings

    with ItemService(Settings()) as service:
        report = service.fetch("https://e.tb.cn/h.xxxx?tk=yyyy")
        print(report.product.price.current)

包结构：
    config.py      运行时配置（TB_* 环境变量）
    errors.py      异常体系（retryable / needs_human 决定重试策略）
    link.py        分享文本 / 短链 → 商品 ID
    models/        领域模型（商品）与过程记录（抓取报告 / 登录态）
    parsers/       容错解析（值工具 → 字段抽取 → 装配入口）
    session/       登录态体检、浏览器会话、扫码登录
    fetchers/      抓取策略与注册表（新增策略只改 registry.py）
    service.py     编排：解析链接 → 多策略抓取 → 解析成模型
    cli/           开发者排障命令行
"""

from .config import Settings
from .errors import (
    AllStrategiesFailed,
    AuthRequiredError,
    LinkResolveError,
    ParseError,
    RiskControlError,
    TbMonError,
    TransportError,
)
from .fetchers import available_strategies
from .link import ShareInfo, parse_share_text
from .models import FetchReport, Money, ProductInfo, ShopInfo, SkuInfo, StateStatus
from .service import ItemService, fetch_one

__version__ = "1.0.0"

__all__ = [
    "AllStrategiesFailed",
    "AuthRequiredError",
    "FetchReport",
    "ItemService",
    "LinkResolveError",
    "Money",
    "ParseError",
    "ProductInfo",
    "RiskControlError",
    "Settings",
    "ShareInfo",
    "ShopInfo",
    "SkuInfo",
    "StateStatus",
    "TbMonError",
    "TransportError",
    "__version__",
    "available_strategies",
    "fetch_one",
    "parse_share_text",
]
