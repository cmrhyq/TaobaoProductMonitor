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
