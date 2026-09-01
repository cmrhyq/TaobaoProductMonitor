"""
CLI entry point for TaobaoProductMonitor.
Supports scheduling, one-shot monitoring, product management, and web server.
"""

import click
import structlog

from config.settings import get_settings
from config.logging_config import setup_logging

settings = get_settings()
setup_logging(log_level=settings.app.log_level, debug=settings.app.debug)
logger = structlog.get_logger(__name__)


@click.group()
@click.version_option(version="2.0.0", prog_name="TaobaoProductMonitor")
def cli():
    """TaobaoProductMonitor - 淘宝商品价格监控工具"""
    pass


@cli.command()
@click.option("--once", is_flag=True, help="立即执行一轮监控后退出")
@click.option("--schedule", is_flag=True, default=True, help="启动定时调度（默认）")
def run(once, schedule):
    """启动价格监控任务"""
    from data.database import init_db
    init_db()

    if once:
        logger.info("Running one-shot monitor cycle")
        from task.task import product_monitor_task
        product_monitor_task()
        logger.info("One-shot cycle completed")
        return

    import time
    import schedule as sched

    logger.info("Starting scheduled monitoring", app_name=settings.app.app_name)

    from task.task import product_monitor_task

    sched.every().tuesday.at("06:00").do(product_monitor_task)
    sched.every().tuesday.at("20:00").do(product_monitor_task)
    sched.every().thursday.at("06:00").do(product_monitor_task)
    sched.every().thursday.at("20:00").do(product_monitor_task)
    sched.every().friday.at("01:01").do(product_monitor_task)

    logger.info("Scheduler configured, entering main loop")
    while True:
        sched.run_pending()
        time.sleep(1)


@cli.group()
def product():
    """商品管理命令"""
    pass


@product.command("add")
@click.option("--text", prompt="请粘贴淘宝分享文本", help="淘宝分享文本")
@click.option("--email", prompt="通知邮箱", help="降价通知接收邮箱")
def product_add(text, email):
    """添加新的监控商品"""
    from data.database import init_db
    from service.monitor.taobao_monitor import TaobaoMonitor

    init_db()
    monitor = TaobaoMonitor()
    product_id = monitor.save_product_info(text, email)

    if product_id:
        click.echo(click.style(f"商品添加成功，ID: {product_id}", fg="green"))
    else:
        click.echo(click.style("商品添加失败，请检查分享文本格式", fg="red"))


@product.command("list")
def product_list():
    """查看所有监控商品"""
    from data.database import init_db
    from data.repository.product_repo import ProductRepository

    init_db()
    repo = ProductRepository()
    products = repo.get_all_products()

    if not products:
        click.echo("暂无监控商品")
        return

    status_map = {10: "未开始", 11: "监控中", 12: "已结束"}
    click.echo(f"\n{'ID':<5} {'状态':<8} {'当前价':<10} {'商品名称'}")
    click.echo("-" * 70)
    for p in products:
        status = status_map.get(p.monitor_status, "未知")
        price = f"¥{p.current_price}" if p.current_price else "-"
        name = p.product_name[:40] if p.product_name else ""
        click.echo(f"{p.product_id:<5} {status:<8} {price:<10} {name}")
    click.echo(f"\n共 {len(products)} 个商品")


@cli.command("probe-price")
@click.option("--url", "product_url", prompt="请输入商品链接", help="商品链接（支持淘宝短链）")
@click.option("--no-playwright", is_flag=True, help="跳过 Playwright 通道（不启动浏览器）")
def probe_price(product_url, no_playwright):
    """诊断单个商品在三个通道的价格提取结果（排查补贴价问题）"""
    from config.settings import get_settings
    from service.monitor.price_fetcher import PriceFetcherService
    from service.monitor.taobao_h5_api import TaobaoH5Api
    from service.monitor.playwright_fallback import get_price_sync

    fetcher = PriceFetcherService()
    item_id = fetcher.resolve_item_id(product_url)
    if not item_id:
        item_id = fetcher.resolve_short_link(product_url).get("item_id")
    if not item_id:
        click.echo(click.style("无法从链接解析出商品 ID", fg="red"))
        return

    click.echo(f"item_id: {item_id}\n")

    settings = get_settings()
    api = TaobaoH5Api(
        app_key=settings.taobao_api.app_key,
        proxy_url=settings.get_proxy_url(),
        timeout=settings.taobao_api.timeout,
        max_retries=settings.taobao_api.max_retries,
        request_interval=settings.taobao_api.request_interval,
    )

    # 通道 1：mtop JSONP API
    info = api.debug_price_info(item_id)
    jsonp = info["jsonp"]
    click.echo("【通道1 mtop JSONP API】")
    if jsonp.get("success"):
        _echo_prices(jsonp.get("real"), jsonp.get("original"))
        click.echo("  价格相关字段:")
        for path, value in jsonp.get("price_fields", {}).items():
            click.echo(f"    {path} = {value}")
    else:
        click.echo(f"  状态: 失败（{jsonp.get('error') or jsonp.get('ret')}）")
    click.echo("")

    # 通道 2：移动页正则
    mobile = info["mobile_page"]
    click.echo("【通道2 移动页正则】")
    if mobile.get("success"):
        _echo_prices(mobile.get("real"), mobile.get("original"))
    else:
        click.echo(f"  状态: 失败（{mobile.get('error') or '未匹配到价格'}）")
    for label in ("base_matches", "promo_matches"):
        matches = mobile.get(label) or {}
        if matches:
            name = "常规价格" if label == "base_matches" else "补贴/促销价"
            click.echo(f"  {name}原始匹配:")
            for pattern, values in matches.items():
                click.echo(f"    {values}  <- {pattern}")
    click.echo("")

    # 通道 3：Playwright
    if no_playwright:
        click.echo("【通道3 Playwright】已跳过（--no-playwright）")
        return
    click.echo("【通道3 Playwright】启动浏览器，请稍候…")
    try:
        real, original = get_price_sync(
            f"https://h5.m.taobao.com/awp/core/detail.htm?id={item_id}",
            headless=settings.playwright.headless,
            timeout=settings.playwright.timeout,
            proxy_url=settings.get_proxy_url(),
        )
        if real is not None:
            _echo_prices(str(real), str(original) if original is not None else None)
        else:
            click.echo("  状态: 失败（页面未提取到价格）")
    except Exception as exc:
        click.echo(f"  状态: 失败（{exc}）")


def _echo_prices(real, original):
    real_s = f"¥{real}" if real not in (None, "") else "未获取到"
    original_s = f"¥{original}" if original not in (None, "") else "-"
    click.echo(f"  到手价: {real_s}   优惠前价格: {original_s}")


@cli.command()
@click.option("--host", default="0.0.0.0", help="监听地址")
@click.option("--port", default=8000, type=int, help="监听端口")
@click.option("--reload", is_flag=True, help="开启热重载（开发模式）")
def server(host, port, reload):
    """启动 FastAPI Web 服务"""
    import uvicorn

    logger.info("Starting web server", host=host, port=port)
    uvicorn.run(
        "api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    cli()
