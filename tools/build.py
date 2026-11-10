#!/usr/bin/env python3
"""NG SPHERE catalog builder.
Reads raw.json (scraped supplier products) and writes index.html + orders-map.csv.
Usage: python3 build.py [--margin 0.5] [--shipping 12]
"""
import json, re, csv, html, sys, datetime, argparse

CONFIG = {
    "brand": "NG SPHERE",
    "instagram": "ng_sphere1",
    "whatsapp": "962796199881",      # international format, no +
    "whatsapp_display": "0796 199 881",
    "usd_to_jod": 0.709,
}

ap = argparse.ArgumentParser()
ap.add_argument("--margin", type=float, default=None, help="profit margin over supplier price, e.g. 0.5 = 50%%")
ap.add_argument("--shipping", type=float, default=0.0, help="shipping cost per piece in USD, added before margin")
ap.add_argument("--src", default="raw.json")
ap.add_argument("--out", default="index.html")
args = ap.parse_args()
# pricing.json (in the repo) holds the owner's margin/shipping; CLI flags override it
try:
    _pc = json.load(open("pricing.json"))
    if args.margin is None: args.margin = _pc.get("margin")
    if not args.shipping: args.shipping = _pc.get("shipping_usd", 0.0) or 0.0
except FileNotFoundError:
    pass

IMG_BASE = "https://s.alicdn.com/@sc04/kf/"

# ---------- Arabic naming ----------
def has(t, *words):
    return any(w in t for w in words)

def classify(t):
    """returns (arabic type, category key)"""
    if has(t, "jeans"):
        return "بنطلون جينز", "jackets"
    if has(t, "blazer dress", "blazer floor"):
        return ("فستان بليزر", "dresses") if "dress" in t else ("طقم بليزر", "sets")
    if has(t, "two piece", "two-piece", " set", "suit", "top and skirt"):
        return "طقم", "sets"
    if has(t, "blazer"):
        return "بليزر", "jackets"
    if has(t, "fur coat"):
        return "معطف فرو", "jackets"
    if has(t, "wool-blend coat", "wool coat"):
        return "معطف صوف", "jackets"
    if has(t, "down jacket"):
        return "جاكيت شتوي", "jackets"
    if has(t, "trench", "jacket", "coat", "outerwear"):
        return "جاكيت", "jackets"
    if has(t, "sweater", "knitwear"):
        return "كنزة تريكو", "knit"
    if has(t, "gown", "evening", "banquet", "formal", "party", "wedding"):
        return "فستان سهرة", "evening"
    return "فستان", "dresses"

DESCRIPTORS = [
    (("mermaid", "fish tail", "fishtail"), "بقصّة حورية"),
    (("off-shoulder", "off shoulder", "one-shoulder", "one necked"), "أوف شولدر"),
    (("halter",), "رقبة هولتر"),
    (("strapless", "tube-top", "tube top"), "بدون أكتاف"),
    (("sequin",), "بالترتر"),
    (("lace",), "دانتيل"),
    (("rhinestone", "diamond", "bead", "studded", "mirror"), "بالخرز اللامع"),
    (("embroider",), "مطرّز"),
    (("tassel", "fringe"), "بالشراشيب"),
    (("feather",), "بالريش"),
    (("3d floral", "floral", "flower", "rose", "petal"), "بالورود"),
    (("satin",), "ساتان"),
    (("chiffon",), "شيفون"),
    (("tweed",), "تويد"),
    (("leather", " pu "), "جلد"),
    (("denim",), "جينز"),
    (("knit",), "تريكو"),
    (("mesh", "tulle", "sheer"), "تول"),
    (("pleat",), "بليسيه"),
    (("leopard",), "بنقشة نمر"),
    (("polka",), "منقّط"),
    (("stripe",), "مقلّم"),
    (("puff sleeve", "puff-sleeve", "bubble sleeve", "lantern"), "بأكمام منفوخة"),
    (("cape",), "بكاب"),
    (("bow",), "بفيونكة"),
    (("bandage", "bodycon"), "ضيّق"),
]
LENGTH = [(("mini", "short dress", "short elegant"), "ميني"),
          (("maxi", "floor length", "full-length", "full length", "long dress", "long gown"), "ماكسي")]
COLORS = [("burgundy", "خمري"), ("mint", "نعناعي"), ("apricot", "مشمشي"), ("red", "أحمر"), ("pink", "زهري"),
          ("black", "أسود"), ("white", "أبيض"), ("green", "أخضر"), ("yellow", "أصفر"), ("brown", "بني"),
          ("beige", "بيج"), ("silver", "فضي")]

def arabic_name(title):
    t = " " + title.lower().replace("&#39;", "'") + " "
    typ, cat = classify(t)
    parts = [typ]
    for keys, word in DESCRIPTORS:
        if len(parts) >= 3:
            break
        if word in typ:          # don't repeat "تريكو" in "كنزة تريكو", "جينز" in jeans
            continue
        if has(t, *keys):
            parts.append(word)
    if typ.startswith("فستان") and len(parts) < 3:
        for keys, word in LENGTH:
            if has(t, *keys):
                parts.append(word)
                break
    color = next((ar for en, ar in COLORS if re.search(r"\b" + en + r"\b", t)), "")
    return " ".join(parts), cat, color

# ---------- pricing ----------
def parse_usd(p):
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", p)]
    return max(nums) if nums else None

def jod_price(p):
    if args.margin is None:
        return None
    usd = parse_usd(p)
    if usd is None:
        return None
    jod = (usd + args.shipping) * (1 + args.margin) * CONFIG["usd_to_jod"]
    return int(round(jod))

# ---------- build ----------
raw = json.load(open(args.src))
# gallery.json: {product_id: ["Hxxxx.jpg", ...]} pulled from each product page (optional)
try:
    GAL = json.load(open("gallery.json"))
except FileNotFoundError:
    GAL = {}
products = []
for pid, title, price, moq, img in raw:
    name, cat, color = arabic_name(title)
    code = "NG-" + pid[-5:]
    products.append({
        "code": code, "name": name, "cat": cat, "color": color,
        "img": IMG_BASE + img, "jod": jod_price(price),
        "gal": [IMG_BASE + g for g in GAL.get(pid, [])],
        "_title": title, "_price": price, "_moq": moq,
        "_url": f"https://www.alibaba.com/product-detail/_{pid}.html",
    })

# private order map for the owner (supplier link + cost) — never published
with open("orders-map.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["code", "arabic_name", "supplier_price_usd", "min_order", "site_price_jod", "supplier_title", "supplier_link"])
    for p in products:
        w.writerow([p["code"], p["name"] + (" – " + p["color"] if p["color"] else ""), p["_price"], p["_moq"],
                    p["jod"] or "", p["_title"], p["_url"]])

public = [{k: v for k, v in p.items() if not k.startswith("_")} for p in products]
today = datetime.date.today()
months = ["كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران", "تموز", "آب", "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول"]
updated = f"{today.day} {months[today.month-1]} {today.year}"

tpl = open(__import__("os").path.join(__import__("os").path.dirname(__file__),"template.html"), encoding="utf-8").read()
out = (tpl.replace("__PRODUCTS__", json.dumps(public, ensure_ascii=False))
          .replace("__WA__", CONFIG["whatsapp"])
          .replace("__WA_DISPLAY__", CONFIG["whatsapp_display"])
          .replace("__IG__", CONFIG["instagram"])
          .replace("__UPDATED__", updated)
          .replace("__COUNT__", str(len(public))))
open(args.out, "w", encoding="utf-8").write(out)

from collections import Counter
print(len(public), "products", dict(Counter(p["cat"] for p in public)))
for p in public[:12]:
    print(p["code"], p["name"], p["color"], p["jod"])
