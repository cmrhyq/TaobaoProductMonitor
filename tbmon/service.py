"""编排层：把「解析链接 → 多策略抓取 → 解析成模型」串起来。

职责边界：
- 只做流程编排、重试/降级决策、结果校验；
- 不碰 HTTP 细节（`fetchers` 负责），不碰字段映射（`parsers` 负责），
  不碰登录态格式（`session` 负责），不认识任何具体策略名（`fetchers.registry` 负责）。

⚠️ 本类会缓存浏览器会话，而 playwright 的同步对象**禁止跨线程使用**：
必须在同一个线程内创建、使用并关闭，不要做成进程级单例给多个请求共享。
"""

from __future__ import annotations

import json
import logging
import random
import time
from collections.abc import Sequence
from pathlib import Path

from .config import Settings
from .errors import AllStrategiesFailed, AuthRequiredError, TbMonError
from .fetchers import StrategyContext, available_strategies, build_fetcher
from .link import LinkResolver
from .models import AttemptRecord, FetchReport, StateStatus
from .parsers import parse
from .session import BrowserSession, validate_state
from .session import login as do_login

log = logging.getLogger(__name__)

#: 策略优先级（唯一真值在 `fetchers.registry`，此处仅作对外别名，避免调用方多一层导入）
STRATEGY_ORDER: tuple[str, ...] = available_strategies()


class ItemService:
    """商品信息抓取服务。可复用（浏览器会话会被缓存），用完请 close()。

    典型用法：
        with ItemService(Settings()) as service:
            report = service.fetch("https://e.tb.cn/h.xxx?tk=yyy")
            print(report.product.price.current)
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self._ctx = StrategyContext(self.settings)
        self._resolver: LinkResolver | None = None

    # ------------------------------------------------------------ 资源管理
    def __enter__(self) -> ItemService:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        """释放浏览器与 HTTP 连接；幂等。"""
        self._ctx.close()
        if self._resolver is not None:
            try:
                self._resolver.close()
            except Exception:  # pragma: no cover
                pass
            self._resolver = None

    @property
    def _session(self) -> BrowserSession | None:
        """已启动的浏览器会话（未启动为 None）。私有属性，仅供本类与测试观测。"""
        return self._ctx.session

    # ------------------------------------------------------------ 登录态
    def login_state(self) -> StateStatus:
        """登录态体检，不启动浏览器。"""
        return validate_state(self.settings.storage_state, stale_days=self.settings.state_stale_days)

    def login(self, *, timeout_s: int | None = None, on_event=print) -> Path:
        """打开浏览器扫码登录并保存登录态。"""
        self.close()  # 避免与已有浏览器会话争抢登录态文件
        return do_login(self.settings, timeout_s=timeout_s, on_event=on_event)

    # ------------------------------------------------------------ 链接解析
    def resolve(self, text: str) -> str:
        """分享文本 / 链接 / 商品 ID → 商品 ID。"""
        if self._resolver is None:
            self._resolver = LinkResolver(
                timeout=self.settings.http_timeout_s, proxy=self.settings.proxy
            )
        return self._resolver.resolve(text)

    # ------------------------------------------------------------ 抓取主流程
    def fetch(
        self,
        text: str,
        *,
        strategies: Sequence[str] | None = None,
        save_raw: str | Path | None = None,
    ) -> FetchReport:
        """抓取商品详情。

        Args:
            text: 分享文本 / 链接 / 商品 ID
            strategies: 允许使用的策略子集，实际顺序始终按优先级执行
            save_raw: 把原始响应落盘到该路径（文件或目录），便于排查字段变化

        Raises:
            AllStrategiesFailed: 所有策略均失败，异常体内含每次尝试的摘要。
        """
        started = time.perf_counter()
        attempts: list[AttemptRecord] = []
        warnings: list[str] = []

        item_id = self.resolve(text)
        url = f"https://item.taobao.com/item.htm?id={item_id}"
        order = self._normalize_strategies(strategies)
        log.info("开始抓取 item_id=%s 策略=%s", item_id, ",".join(order))

        last_error: TbMonError | None = None

        for strategy in order:
            try:
                fetcher = self._build_fetcher(strategy)
            except AuthRequiredError as exc:
                warnings.append(f"[{strategy}] 跳过：{exc}")
                attempts.append(
                    AttemptRecord(strategy=strategy, ok=False, elapsed_ms=0, error=str(exc))
                )
                continue

            for round_no in range(1, self.settings.max_attempts + 1):
                attempt_started = time.perf_counter()
                try:
                    outcome = fetcher.fetch(item_id)
                    product = parse(
                        outcome.payload, source=outcome.source, item_id=item_id, url=url
                    )

                    elapsed = int((time.perf_counter() - attempt_started) * 1000)
                    attempts.append(AttemptRecord(strategy=strategy, ok=True, elapsed_ms=elapsed))
                    if product.price.current is None and product.price.low is None:
                        warnings.append(
                            "未解析到价格：可能是多 SKU 区间价、需登录查看，或字段结构已变"
                        )
                    if outcome.source.startswith("dom"):
                        warnings.append("数据来自 DOM 兜底，字段完整度低于接口数据")

                    raw_path = self._dump_raw(outcome.payload, save_raw, item_id)
                    log.info(
                        "抓取成功 item_id=%s 策略=%s 来源=%s", item_id, strategy, outcome.source
                    )
                    return FetchReport(
                        ok=True,
                        item_id=item_id,
                        product=product,
                        attempts=attempts,
                        warnings=warnings,
                        elapsed_ms=int((time.perf_counter() - started) * 1000),
                        raw_path=str(raw_path) if raw_path else None,
                    )
                except TbMonError as exc:
                    last_error = exc
                    elapsed = int((time.perf_counter() - attempt_started) * 1000)
                    attempts.append(
                        AttemptRecord(strategy=strategy, ok=False, elapsed_ms=elapsed, error=str(exc))
                    )
                    log.warning("策略 %s 第 %d 次失败：%s", strategy, round_no, exc)

                    if exc.needs_human:
                        warnings.append(f"[{strategy}] 需要人工处理：{exc}")
                        break
                    if not exc.retryable:
                        break
                    if round_no < self.settings.max_attempts:
                        self._sleep_backoff(round_no)
                except Exception as exc:  # 非预期异常：不重试，记录后换策略
                    last_error = TbMonError(f"{exc.__class__.__name__}: {exc}")
                    attempts.append(
                        AttemptRecord(
                            strategy=strategy, ok=False,
                            elapsed_ms=int((time.perf_counter() - attempt_started) * 1000),
                            error=str(last_error),
                        )
                    )
                    log.exception("策略 %s 出现非预期异常", strategy)
                    break

        summary = [f"{a.strategy}: {'成功' if a.ok else a.error}" for a in attempts]
        raise AllStrategiesFailed(
            f"抓取失败（item_id={item_id}，共尝试 {len(attempts)} 次）：{last_error}",
            attempts=summary,
        )

    # ------------------------------------------------------------ 内部工具
    def _normalize_strategies(self, strategies: Sequence[str] | None) -> list[str]:
        """校验并归一策略子集。

        始终按既定优先级执行，避免调用方传入顺序导致「先开浏览器再试接口」这类劣化。
        """
        if not strategies:
            return list(STRATEGY_ORDER)
        unknown = [s for s in strategies if s not in STRATEGY_ORDER]
        if unknown:
            raise ValueError(f"未知策略 {unknown}，可选：{list(STRATEGY_ORDER)}")
        return [s for s in STRATEGY_ORDER if s in strategies]

    def _build_fetcher(self, strategy: str):
        """构造抓取器（委托给注册表）。测试通过替换本方法注入假策略。"""
        return build_fetcher(strategy, self.settings, self._ctx)

    def _sleep_backoff(self, round_no: int) -> None:
        """指数退避 + 抖动，避免多个商品同步重试形成尖峰。"""
        delay = self.settings.backoff_base_s * (2 ** (round_no - 1)) * (1 + random.random() * 0.3)
        log.info("退避 %.1fs 后重试", delay)
        time.sleep(delay)

    @staticmethod
    def _dump_raw(payload: object, target: str | Path | None, item_id: str) -> Path | None:
        """把原始响应落盘（便于淘宝改版时对比字段结构）。"""
        if not target:
            return None
        path = Path(target)
        if path.is_dir():
            path = path / f"{item_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def fetch_one(text: str, settings: Settings | None = None, **kwargs: object) -> FetchReport:
    """一次性抓取的语法糖（内部管理资源生命周期）。"""
    with ItemService(settings) as service:
        return service.fetch(text, **kwargs)  # type: ignore[arg-type]


__all__ = ["ItemService", "STRATEGY_ORDER", "fetch_one"]
