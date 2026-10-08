"""注入到浏览器的 JavaScript 片段。

单独成模块的理由：这些是**前端运行时契约**（页面对象结构变了就得改它们），
和策略的编排逻辑（降级顺序、异常分类）完全是两类知识，混在一个文件里
既难读也难在淘宝改版时快速定位。

⚠️ `READ_SSR_JS` 里的取值路径必须逐层显式书写。曾用字符串替换拼路径
（`"a.b.c".replace(".", " && ctx.")`），结果把 `ctx.loaderData.home` 拼成了
`ctx.home`，导致 SSR 恒为 null —— 这类"聪明"写法在 JS 路径上一定会出错。
"""

from __future__ import annotations

#: SSR 数据在页面全局对象里的位置（淘宝 PC 详情页为 ICE 框架 SSR）
SSR_PATH = "loaderData.home.data.res"

#: 轮询等待 SSR 数据就绪（纯布尔判断，失败即超时，不抛错）
SSR_READY_JS = (
    "() => !!(window.__ICE_APP_CONTEXT__ && window.__ICE_APP_CONTEXT__.loaderData"
    " && window.__ICE_APP_CONTEXT__.loaderData.home && window.__ICE_APP_CONTEXT__.loaderData.home.data"
    " && window.__ICE_APP_CONTEXT__.loaderData.home.data.res)"
)

#: 读取整份 SSR 商品数据
READ_SSR_JS = """
() => {
  const ctx = window.__ICE_APP_CONTEXT__;
  if (!ctx || !ctx.loaderData) return null;
  const home = ctx.loaderData.home;
  if (!home || !home.data) return null;
  const res = home.data.res || home.data;
  if (!res || typeof res !== 'object') return null;
  return {res: res, keys: Object.keys(res)};
}
"""

#: DOM 兜底提取。
#: 不要求元素是叶子节点（PC 页价格被拆成多层 span），改按 class 语义 + 字号打分；
#: 「优惠后」类文案优先于「优惠前」类文案作为当前价。
EXTRACT_DOM_JS = r"""
() => {
  const clean = (s) => String(s || '').replace(/\s+/g, ' ').trim();
  const out = {title: null, price_text: null, original_text: null,
               shop_name: null, images: [], attributes: {}, price_candidates: []};
  out.title = clean(document.title).replace(/[-_—|]\s*(淘宝网?|天猫|Taobao|tmall\.com).*$/i, '') || null;
  const h1 = document.querySelector('h1');
  if (h1 && clean(h1.innerText)) out.title = clean(h1.innerText);
  const og = document.querySelector('meta[property="og:image"]');
  if (og && og.content) out.images.push(og.content);

  const seen = new Set();
  const cands = [];
  document.querySelectorAll('[class*="price" i],[id*="price" i]').forEach((el) => {
    const t = clean(el.innerText);
    if (!t || t.length > 60 || !/\d/.test(t) || seen.has(t)) return;
    seen.add(t);
    const cls = (String(el.className || '') + ' ' + String(el.id || '')).toLowerCase();
    const fs = parseFloat(getComputedStyle(el).fontSize) || 0;
    let score = fs / 4;
    if (/highlight|main|cur|sale|final/.test(cls)) score += 6;
    if (/origin|subprice|sub-|del|through|line/.test(cls)) score -= 4;
    cands.push({text: t, cls: cls, score: score});
  });
  cands.sort((a, b) => b.score - a.score);
  out.price_candidates = cands.slice(0, 8);
  const CUR_RE = /优惠后|券后|到手|实付|秒杀价|活动价/;
  const ORIG_RE = /优惠前|原价|划线价|专柜价|吊牌价/;
  const cur = cands.find((c) => CUR_RE.test(c.text)) || cands[0];
  const orig = cands.find((c) => ORIG_RE.test(c.text));
  if (cur) out.price_text = cur.text;
  if (orig) out.original_text = orig.text;

  const shop = document.querySelector('[class*="shopName"],[class*="ShopName"],[class*="shop-name"],[class*="seller-name"]');
  if (shop) out.shop_name = clean(shop.innerText);
  return out;
}
"""

#: 读取正文文本（用于识别 punish 等风控拒绝页）
PAGE_TEXT_JS = "() => (document.body && document.body.innerText) || ''"


__all__ = [
    "EXTRACT_DOM_JS",
    "PAGE_TEXT_JS",
    "READ_SSR_JS",
    "SSR_PATH",
    "SSR_READY_JS",
]
