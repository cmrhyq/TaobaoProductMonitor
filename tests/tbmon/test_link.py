"""链接解析回归测试（全离线）。

fixture 里保存的是一次**真实抓取**的 e.tb.cn 短链页面，因此这个测试能真实反映
淘宝短链页面的结构变化：一旦 `var url = '...'` 这类特征消失，测试立刻失败。
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from tbmon.errors import LinkResolveError
from tbmon.link import (
    LinkResolver,
    extract_urls,
    is_short_link,
    item_id_from_body,
    item_id_from_text,
    item_id_from_url,
    strip_url_noise,
)

FIXTURES = Path(__file__).parent / "fixtures"
SHORT_LINK_HTML = (FIXTURES / "e_tb_cn_shortlink.html").read_text(encoding="utf-8")
SHARE_TEXT = (
    "【淘宝】https://e.tb.cn/h.jZFrbZq1TUvRKLb?tk=0ePNTqqrdlY CZ028 "
    "「MUJI 无印良品 柔软清凉棉多用途靠垫 554020cm」"
)
EXPECTED_ID = "1050906790941"


@pytest.fixture()
def resolver() -> LinkResolver:
    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host == "e.tb.cn":
            return httpx.Response(200, text=SHORT_LINK_HTML)
        if host == "m.tb.cn":
            return httpx.Response(
                302, headers={"location": f"https://item.taobao.com/item.htm?id={EXPECTED_ID}"}
            )
        if host == "loop.tb.cn":
            return httpx.Response(302, headers={"location": "https://loop.tb.cn/h.same"})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    return LinkResolver(client=client)


# ------------------------------------------------------------------ 纯文本解析
def test_numeric_id() -> None:
    assert item_id_from_text("  1050906790941  ") == EXPECTED_ID


def test_url_with_id_param() -> None:
    url = f"https://item.taobao.com/item.htm?spm=a1z10&id={EXPECTED_ID}&sourceType=item"
    assert item_id_from_url(url) == EXPECTED_ID
    assert item_id_from_text(url) == EXPECTED_ID


def test_extract_urls_drops_trailing_punctuation() -> None:
    urls = extract_urls("看这个 https://item.taobao.com/item.htm?id=1050906790941。 还有吗")
    assert urls == ["https://item.taobao.com/item.htm?id=1050906790941"]
    assert strip_url_noise("https://x.com/a)") == "https://x.com/a"


def test_text_without_link_returns_none() -> None:
    assert item_id_from_text("") is None
    assert item_id_from_text("随便一句话，没有链接") is None


def test_short_link_detection() -> None:
    assert is_short_link("https://e.tb.cn/h.jZFrbZq1TUvRKLb")
    assert is_short_link("https://m.tb.cn/h.abc")
    assert not is_short_link("https://item.taobao.com/item.htm?id=1")


@pytest.mark.parametrize(
    "body",
    [
        '<script>var url = "https://item.taobao.com/item.htm?id=123456789012";</script>',
        '{"itemId":"123456789012"}',
        "https://detail.tmall.com/item.htm?spm=a&id=123456789012",
    ],
)
def test_item_id_from_body_variants(body: str) -> None:
    assert item_id_from_body(body) == "123456789012"


# ------------------------------------------------------------------ 端到端解析
def test_resolve_real_share_text(resolver: LinkResolver) -> None:
    # fixture 自身必须先包含目标 ID，否则说明 fixture 过期，测试应立刻失败
    assert EXPECTED_ID in SHORT_LINK_HTML
    assert resolver.resolve(SHARE_TEXT) == EXPECTED_ID


def test_resolve_short_link_with_302_redirect(resolver: LinkResolver) -> None:
    assert resolver.resolve("https://m.tb.cn/h.abcdEFG") == EXPECTED_ID


def test_resolve_redirect_loop_is_bounded(resolver: LinkResolver) -> None:
    with pytest.raises(LinkResolveError):
        resolver.resolve("https://loop.tb.cn/h.same")


def test_tpwd_only_text_gives_actionable_error(resolver: LinkResolver) -> None:
    with pytest.raises(LinkResolveError) as excinfo:
        resolver.resolve("￥CZ028abcdef￥")
    assert "淘口令" in str(excinfo.value)


def test_resolve_empty_input(resolver: LinkResolver) -> None:
    with pytest.raises(LinkResolveError):
        resolver.resolve("   ")
