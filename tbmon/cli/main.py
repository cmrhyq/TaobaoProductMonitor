"""命令行入口：login / check / resolve / fetch。

⚠️ 这是**开发者排障工具**，不是业务入口：业务侧请使用 Web API
（`api/routes/session.py` 等）。保留它的唯一理由是 ——
服务跑在无桌面环境时，需要在本机生成登录态文件再复制过去。
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .. import __version__
from ..config import Settings
from ..errors import AuthRequiredError, RiskControlError, TbMonError
from ..fetchers import available_strategies
from ..service import ItemService
from .render import print_diagnostics, print_product

#: 进程退出码：调用方（脚本 / CI）据此判断失败类型
EXIT_OK = 0
EXIT_FAIL = 1
EXIT_AUTH = 2
EXIT_RISK = 3

#: 这些第三方库逐条打印 HTTP 请求，对本程序没有价值
_NOISY_LOGGERS = ("httpx", "httpcore", "asyncio")


# ------------------------------------------------------------------ 子命令
def _cmd_login(settings: Settings, timeout: int | None) -> int:
    with ItemService(settings) as service:
        path = service.login(timeout_s=timeout)
    print(f"登录态已写入：{path}")
    return EXIT_OK


def _cmd_check(settings: Settings) -> int:
    with ItemService(settings) as service:
        status = service.login_state()
    print(f"登录态文件：{settings.storage_state}")
    print(f"结论      ：{'✅ 可用' if status.ok else '❌ 不可用'} — {status.reason}")
    print(f"cookie 数 ：{status.cookie_count}")
    if status.age_days is not None:
        print(f"保存时长  ：{status.age_days} 天")
    if status.expires_in_days is not None:
        print(f"剩余有效期：{status.expires_in_days} 天")
    return EXIT_OK if status.ok else EXIT_AUTH


def _cmd_resolve(settings: Settings, source: str, as_json: bool) -> int:
    with ItemService(settings) as service:
        item_id = service.resolve(source)
    if as_json:
        print(json.dumps({"ok": True, "item_id": item_id}, ensure_ascii=False))
    else:
        print(item_id)
    return EXIT_OK


def _cmd_fetch(args: argparse.Namespace, settings: Settings) -> int:
    strategies = [s.strip() for s in args.strategy.split(",") if s.strip()]
    with ItemService(settings) as service:
        report = service.fetch(args.source, strategies=strategies, save_raw=args.save_raw)

    if args.as_json:
        print(json.dumps(report.to_json_obj(), ensure_ascii=False, indent=2))
    else:
        assert report.product is not None
        print_product(report.product, report)
        print_diagnostics(report)
    return EXIT_OK


# ------------------------------------------------------------------ 参数装配
def _add_common_options(parser: argparse.ArgumentParser, *, suppress_defaults: bool) -> None:
    """全局选项在子命令前后都能写。

    子命令侧用 SUPPRESS 作为默认值，避免子解析器把主解析器已解析到的值覆盖掉
    （argparse 的经典坑：子命令默认值会无条件覆盖同名的全局参数）。
    """
    default = argparse.SUPPRESS if suppress_defaults else None
    parser.add_argument(
        "--storage-state", default=default, help="登录态文件路径（默认 taobao_storage_state.json）"
    )
    parser.add_argument("--proxy", default=default, help="代理地址，如 http://127.0.0.1:7890")
    parser.add_argument("-v", "--verbose", action="count", default=default, help="输出调试日志")


def build_parser() -> argparse.ArgumentParser:
    """构造命令行解析器。"""
    strategies = ",".join(available_strategies())
    parser = argparse.ArgumentParser(
        prog="tbmon",
        description="淘宝商品信息抓取（价格 / 规格 / 店铺 / 参数）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python -m tbmon login\n"
            "  python -m tbmon fetch \"https://e.tb.cn/h.jZFrbZq1TUvRKLb?tk=0ePNTqqrdlY\"\n"
            f"  python -m tbmon fetch 1050906790941 --strategy {strategies} --save-raw ./.scratch\n"
        ),
    )
    _add_common_options(parser, suppress_defaults=False)
    parser.add_argument("--version", action="version", version=f"tbmon {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="扫码登录并保存登录态")
    _add_common_options(login, suppress_defaults=True)
    login.add_argument("--timeout", type=int, default=None, help="等待扫码的秒数")

    check = sub.add_parser("check", help="体检登录态是否可用")
    _add_common_options(check, suppress_defaults=True)

    resolve = sub.add_parser("resolve", help="只解析商品 ID（不发抓取请求）")
    _add_common_options(resolve, suppress_defaults=True)
    resolve.add_argument("source", help="分享文本 / 链接 / 商品 ID")
    resolve.add_argument("--json", action="store_true", dest="as_json")

    fetch = sub.add_parser("fetch", help="抓取商品信息")
    _add_common_options(fetch, suppress_defaults=True)
    fetch.add_argument("source", help="分享文本 / 链接 / 商品 ID")
    fetch.add_argument("--strategy", default=strategies, help=f"策略子集，默认 {strategies}")
    fetch.add_argument("--json", action="store_true", dest="as_json", help="以 JSON 输出")
    fetch.add_argument("--save-raw", default=None, help="保存原始响应的文件或目录")
    fetch.add_argument("--headed", action="store_true", help="浏览器有头模式（排障用）")

    return parser


# ------------------------------------------------------------------ 入口
def _build_settings(args: argparse.Namespace) -> Settings:
    """命令行参数 → 运行时配置（只覆盖显式传入的项）。"""
    overrides: dict[str, object] = {}
    if args.storage_state:
        overrides["storage_state"] = Path(args.storage_state)
    if args.proxy:
        overrides["proxy"] = args.proxy
    if getattr(args, "headed", False):
        overrides["headless"] = False
    if args.verbose:
        overrides["log_level"] = "DEBUG"
    return Settings(**overrides)


def _configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=getattr(logging, str(settings.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in _NOISY_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    """命令行主入口，返回进程退出码。"""
    args = build_parser().parse_args(argv)
    settings = _build_settings(args)
    _configure_logging(settings)

    try:
        if args.command == "login":
            return _cmd_login(settings, args.timeout)
        if args.command == "check":
            return _cmd_check(settings)
        if args.command == "resolve":
            return _cmd_resolve(settings, args.source, args.as_json)
        return _cmd_fetch(args, settings)
    except AuthRequiredError as exc:
        print(f"❌ 需要登录：{exc}", file=sys.stderr)
        print("   执行：python -m tbmon login", file=sys.stderr)
        return EXIT_AUTH
    except RiskControlError as exc:
        print(f"❌ 命中风控：{exc}", file=sys.stderr)
        return EXIT_RISK
    except TbMonError as exc:
        print(f"❌ 抓取失败：{exc}", file=sys.stderr)
        return EXIT_FAIL
    except KeyboardInterrupt:  # pragma: no cover
        print("\n已中断", file=sys.stderr)
        return 130


__all__ = ["EXIT_AUTH", "EXIT_FAIL", "EXIT_OK", "EXIT_RISK", "build_parser", "main"]
