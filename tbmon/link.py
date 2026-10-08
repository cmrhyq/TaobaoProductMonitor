"""分享文本 / 链接 → 商品 ID 解析。

纯解析逻辑，不依赖登录态，可完全离线测试（HTTP 客户端可注入）。
覆盖三类输入：
    1. 纯数字商品 ID                    1050906790941
    2. 含 id 的正式链接                 item.taobao.com/item.htm?id=...
    3. 官方短链（需发一次请求）          e.tb.cn/h.xxx  /  m.tb.cn/h.xxx
淘宝 App 复制出来的分享文本形如：`【淘宝】https://e.tb.cn/h.xxx?tk=yyy CZ028 「标题」`，
因此直接从任意文本里抽取 URL 即可。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

from .config import MOBILE_UA
from .errors import LinkResolveError

# 商品 ID 的查询参数名（不同入口命名不一致）
_ID_KEYS = ("id", "itemId", "item_id", "itemNumId")

# 分享文本里的元信息：`【淘宝】... CZ028 「标题」`
_PLATFORM_RE = re.compile(r"【([^】]{1,20})】")
_TITLE_RE = re.compile(r"「([^」]{1,150})」")
_CANONICAL_ITEM_URL = "https://item.taobao.com/item.htm?id={item_id}"

# 从 HTML 正文里兜底捞 ID 的模式
_BODY_PATTERNS = (
    re.compile(r"[?&](?:id|itemId|item_id)=(\d{6,20})"),
    re.compile(r'"item(?:Num)?[Ii]d"\s*:\s*"?(\d{6,20})"?'),
    re.compile(r"item\.taobao\.com/item\.htm[^\"'\s]*?[?&]id=(\d{6,20})"),
    re.compile(r"detail\.tmall\.com/item\.htm[^\"'\s]*?[?&]id=(\d{6,20})"),
)

_URL_RE = re.compile(r"https?://[^\s\u4e00-\u9fff，。；、！？【】「」]+")
_ID_RE = re.compile(r"^\d{6,20}$")
# 短链域名（需要发请求展开）
_SHORT_HOSTS = ("e.tb.cn", "m.tb.cn", "tb.cn", "tburl.cn", "s.click.taobao.com")


def strip_url_noise(url: str) -> str:
    """去掉粘贴时粘上的尾部标点（如 `。` `)` `,`）。"""
    return url.rstrip(".,;:)]}，。；、）】」\"'")


def extract_urls(text: str) -> list[str]:
    return [strip_url_noise(u) for u in _URL_RE.findall(text or "")]


def item_id_from_url(url: str) -> str | None:
    """从完整 URL 的 query 里取商品 ID。"""
    try:
        query = parse_qs(urlparse(url).query)
    except ValueError:
        return None
    for key in _ID_KEYS:
        for value in query.get(key, []):
            if _ID_RE.match(value):
                return value
    return None


def item_id_from_body(body: str) -> str | None:
    """从 HTML / JS 正文里兜底捞商品 ID。"""
    for pattern in _BODY_PATTERNS:
        match = pattern.search(body)
        if match:
            return match.group(1)
    return None


def item_id_from_text(text: str) -> str | None:
    """纯文本快速通道：数字 ID 或含 id 的链接。"""
    stripped = (text or "").strip()
    if _ID_RE.match(stripped):
        return stripped
    for url in extract_urls(stripped):
        if found := item_id_from_url(url):
            return found
    return None


def is_short_link(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in _SHORT_HOSTS)


# ------------------------------------------------------------- 分享文本元信息
@dataclass(frozen=True, slots=True)
class ShareInfo:
    """分享文本里能直接读出来的信息（不含网络请求）。"""

    platform: str | None = None   # 【淘宝】
    title: str | None = None      # 「MUJI 无印良品 ...」
    url: str | None = None
    tk: str | None = None         # 分享口令参数
    item_id: str | None = None    # 短链此处为 None，需走 LinkResolver 展开

    @property
    def canonical_url(self) -> str | None:
        """可入库、可再次解析的稳定链接（纯 ID 输入也能补出正式链接）。"""
        if self.url:
            return self.url
        if self.item_id:
            return _CANONICAL_ITEM_URL.format(item_id=self.item_id)
        return None


def _first_group(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def parse_share_text(text: str) -> ShareInfo | None:
    """解析淘宝分享文本。

    Args:
        text: 形如 `【淘宝】https://e.tb.cn/h.xxx?tk=yyy CZ028 「商品标题」`

    Returns:
        ShareInfo；**返回 None 表示既无链接也无商品 ID**，不能作为监控对象。
        platform / title 缺失不算失败（淘宝分享格式会变），只影响展示。
    """
    raw = (text or "").strip()
    if not raw:
        return None

    urls = extract_urls(raw)
    url = urls[0] if urls else None
    item_id = item_id_from_text(raw)
    if url is None and item_id is None:
        return None

    tk: str | None = None
    if url:
        try:
            tk = (parse_qs(urlparse(url).query).get("tk") or [None])[0]
        except ValueError:  # pragma: no cover - 畸形 URL
            tk = None

    return ShareInfo(
        platform=_first_group(_PLATFORM_RE, raw),
        title=_first_group(_TITLE_RE, raw),
        url=url,
        tk=tk,
        item_id=item_id,
    )


class LinkResolver:
    """把分享文本解析成商品 ID。

    Args:
        timeout: 单次请求超时（秒）
        proxy: 代理地址
        max_hops: 最多跟随几次跳转，防止短链环路
        client: 可注入的 httpx.Client（测试用）
    """

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        proxy: str | None = None,
        max_hops: int = 6,
        client: httpx.Client | None = None,
    ) -> None:
        self.max_hops = max_hops
        self._owns_client = client is None
        # 空字符串等价于不配置代理；直接透传会让 httpx 抛 ValueError
        proxy = proxy or None
        self._client = client or httpx.Client(
            timeout=timeout,
            proxy=proxy,
            follow_redirects=False,
            headers={"User-Agent": MOBILE_UA, "Accept-Language": "zh-CN,zh;q=0.9"},
        )

    def __enter__(self) -> LinkResolver:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # ------------------------------------------------------------------ 对外
    def resolve(self, text: str) -> str:
        """返回商品 ID；失败抛 LinkResolveError。"""
        text = (text or "").strip()
        if not text:
            raise LinkResolveError("输入为空")

        if direct := item_id_from_text(text):
            return direct

        urls = extract_urls(text)
        if not urls:
            raise LinkResolveError(
                "文本中未找到商品链接。若只有淘口令（形如 ￥xxxx￥），请先粘贴含 e.tb.cn 链接的分享文本",
                detail=text[:80],
            )

        trace: list[str] = []
        for url in urls:
            try:
                found = self._resolve_url(url, trace)
            except httpx.HTTPError as exc:
                trace.append(f"{url} -> 网络错误 {exc.__class__.__name__}")
                continue
            if found:
                return found

        raise LinkResolveError("短链展开后仍未取到商品 ID", detail=" | ".join(trace[-5:]))

    # ------------------------------------------------------------------ 内部
    def _resolve_url(self, url: str, trace: list[str]) -> str | None:
        current = url
        for _ in range(self.max_hops):
            if found := item_id_from_url(current):
                return found

            response = self._client.get(current)
            trace.append(f"{response.status_code} {current[:90]}")
            location = response.headers.get("location")

            if location:
                current = urljoin(str(response.url), location)
                continue

            if response.status_code == 200 and response.text:
                if found := item_id_from_body(response.text):
                    return found

            break
        return None
