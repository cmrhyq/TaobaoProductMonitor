"""快照持久化测试。

用临时 SQLite（真正建表），完全不碰 db/ProductMonitor.db——
测试绝不能写用户的真实数据。
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import data.repository.snapshot_repo as snapshot_repo_module
from data.models import Base
from data.repository.snapshot_repo import SnapshotRepository
from tbmon.models import Money, ProductInfo, ShopInfo, SkuInfo


@pytest.fixture()
def session_factory(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'snapshot_test.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    @contextmanager
    def fake_get_session():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # snapshot_repo 导入时把 get_session 绑定进了自己的命名空间，所以要打在它身上
    monkeypatch.setattr(snapshot_repo_module, "get_session", fake_get_session)
    yield factory
    engine.dispose()


def _product(**overrides) -> ProductInfo:
    payload = dict(
        item_id="1050906790941",
        url="https://item.taobao.com/item.htm?id=1050906790941",
        title="MUJI 无印良品 柔软清凉棉多用途靠垫 55×40×20cm",
        subtitle="凉感面料",
        price=Money(
            current=Decimal("382.00"),
            current_text="382起",
            original=Decimal("522.00"),
            original_text="522",
            low=Decimal("382.00"),
            high=Decimal("420.00"),
            promotions=["券后价"],
        ),
        skus=[
            SkuInfo(sku_id="1", props={"颜色": "象牙色"}, price=Decimal("382.00"),
                    original_price=Decimal("522.00"), stock=5),
            SkuInfo(sku_id="2", props={"颜色": "灰色"}, price=Decimal("398.00"),
                    original_price=Decimal("540.00"), stock=6),
        ],
        images=["https://img.alicdn.com/a.jpg"],
        shop=ShopInfo(shop_id="479456214", name="天猫国际全球探物"),
        attributes={"品牌": "MUJI/无印良品", "长度": "55cm"},
        stock_total=17,
        sold_text="已售 4",
        source="ssr-pc",
        fetched_at=datetime(2026, 10, 8, 23, 30),
    )
    payload.update(overrides)
    return ProductInfo(**payload)


def test_insert_and_read_back(session_factory) -> None:
    repo = SnapshotRepository()
    snapshot_id = repo.insert_snapshot(1, _product())

    assert isinstance(snapshot_id, int)

    latest = repo.query_latest_snapshot(1)
    assert latest is not None
    assert latest["snapshot_id"] == snapshot_id
    assert latest["item_id"] == "1050906790941"
    assert latest["title"].startswith("MUJI")
    assert latest["subtitle"] == "凉感面料"
    assert latest["source"] == "ssr-pc"

    # 价格语义：current = 实付价，original = 优惠前价
    assert latest["price"]["current"] == 382.0
    assert latest["price"]["original"] == 522.0
    assert latest["price"]["low"] == 382.0
    assert latest["price"]["high"] == 420.0
    assert latest["price"]["promotions"] == ["券后价"]

    assert latest["shop_name"] == "天猫国际全球探物"
    assert latest["shop"]["shop_id"] == "479456214"
    assert latest["attributes"] == {"品牌": "MUJI/无印良品", "长度": "55cm"}
    assert latest["stock_total"] == 17
    assert latest["sold_text"] == "已售 4"
    assert latest["images"] == ["https://img.alicdn.com/a.jpg"]

    assert len(latest["skus"]) == 2
    first = latest["skus"][0]
    assert first["sku_id"] == "1"
    assert first["props"] == {"颜色": "象牙色"}
    assert float(first["price"]) == 382.0
    assert float(first["original_price"]) == 522.0
    assert first["stock"] == 5


def test_optional_blocks_stay_empty(session_factory) -> None:
    """没有 SKU / 参数 / 店铺时不该写出 "null" 字符串。"""
    repo = SnapshotRepository()
    repo.insert_snapshot(1, _product(skus=[], attributes={}, shop=None, images=[]))

    latest = repo.query_latest_snapshot(1)
    assert latest is not None
    assert latest["skus"] == []
    assert latest["attributes"] == {}
    assert latest["images"] == []
    assert latest["shop"] is None
    assert latest["shop_name"] is None


def test_history_is_newest_first_and_limited(session_factory) -> None:
    repo = SnapshotRepository()
    for idx in range(3):
        repo.insert_snapshot(1, _product(title=f"第 {idx} 次抓取"))

    history = repo.query_snapshot_history(1, limit=2)
    assert [row["title"] for row in history] == ["第 2 次抓取", "第 1 次抓取"]


def test_unknown_product_returns_none(session_factory) -> None:
    repo = SnapshotRepository()
    assert repo.query_latest_snapshot(999) is None
    assert repo.query_snapshot_history(999) == []
