"""分享文本解析测试（全离线）。

真实分享文本来自淘宝 App 复制，格式一旦变化（例如去掉「」标题）这些断言会立刻失败。
"""

from __future__ import annotations

from tbmon.link import ShareInfo, parse_share_text

SHARE_TEXT = (
    "【淘宝】https://e.tb.cn/h.jZFrbZq1TUvRKLb?tk=0ePNTqqrdlY CZ028 "
    "「MUJI 无印良品 柔软清凉棉多用途靠垫 554020cm」"
)
EXPECTED_ID = "1050906790941"


def test_real_share_text() -> None:
    info = parse_share_text(SHARE_TEXT)

    assert info is not None
    assert info.platform == "淘宝"
    assert info.title == "MUJI 无印良品 柔软清凉棉多用途靠垫 554020cm"
    assert info.url == "https://e.tb.cn/h.jZFrbZq1TUvRKLb?tk=0ePNTqqrdlY"
    assert info.tk == "0ePNTqqrdlY"
    # 短链不含 id，必须留给 LinkResolver 走网络展开
    assert info.item_id is None
    assert info.canonical_url == info.url


def test_branded_link_carries_item_id() -> None:
    info = parse_share_text(f"【天猫】https://detail.tmall.com/item.htm?id={EXPECTED_ID} 「某商品」")

    assert info is not None
    assert info.platform == "天猫"
    assert info.title == "某商品"
    assert info.item_id == EXPECTED_ID
    assert info.tk is None


def test_missing_title_and_platform_are_tolerated() -> None:
    """淘宝分享格式会变；缺标题不该让整条解析失败。"""
    info = parse_share_text("https://e.tb.cn/h.jZFrbZq1TUvRKLb?tk=abc")

    assert info is not None
    assert info.platform is None
    assert info.title is None
    assert info.tk == "abc"


def test_pure_item_id_synthesises_canonical_url() -> None:
    """纯 ID 没有链接，但仍要能入库（products.product_url 非空）。"""
    info = parse_share_text(EXPECTED_ID)

    assert info is not None
    assert info.item_id == EXPECTED_ID
    assert info.url is None
    assert info.canonical_url == f"https://item.taobao.com/item.htm?id={EXPECTED_ID}"


def test_text_without_link_or_id_returns_none() -> None:
    """空文本 / 淘口令 / 闲聊都视为无效输入。"""
    assert parse_share_text("") is None
    assert parse_share_text("   ") is None
    assert parse_share_text("￥CZ028abcdef￥") is None
    assert parse_share_text("今天天气不错") is None


def test_share_info_is_frozen() -> None:
    info = ShareInfo(platform="淘宝", item_id=EXPECTED_ID)
    try:
        info.item_id = "1"  # type: ignore[misc]
    except Exception as exc:
        assert "frozen" in str(exc).lower() or "cannot assign" in str(exc).lower()
    else:  # pragma: no cover - 冻结语义被破坏
        raise AssertionError("ShareInfo 应为不可变对象")
