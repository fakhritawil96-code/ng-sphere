#!/usr/bin/env python3
"""NG SPHERE catalog builder (v2 — full supplier catalog).

Inputs (repo root):
  all.json        new scrape: [[id, title, price, moq, groupId, [imgHash.ext, ...]], ...]   (gitignored, private)
  products.json   current public catalog (kept so product codes stay stable between runs)
  pricing.json    {"margin": 0.5, "shipping_usd": 12}  — margin null => "price on WhatsApp"

Outputs:
  products.json   public catalog: {"updated": "...", "items": [[code, name, cat, color, jod, [imgs]], ...]}
  index.html      the site (loads products.json)
  orders-map.csv  PRIVATE: code -> supplier link, supplier price, MOQ (gitignored)

Modes:
  python3 tools/build.py              full rebuild from all.json (replaces the catalog)
  python3 tools/build.py --add new.json   weekly: prepend only new items (same row format) to products.json
"""
import json, re, csv, os, sys, datetime, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = {
    "instagram": "ng_sphere1",
    "whatsapp": "962796199881",
    "whatsapp_display": "0796 199 881",
    "orders_url": "https://script.google.com/macros/s/AKfycbyWc9hvmPFmyvvELwOOo1lKAMs3MVk1dpHNuId3ENC1XouhGDqfO9G5vMJGGnMJYNGX/exec",  # Apps Script web app /exec URL
    "usd_to_jod": 0.709,
}

ap = argparse.ArgumentParser()
ap.add_argument("--src", default="all.json")
ap.add_argument("--add", default=None, help="weekly mode: file with only newly found rows")
ap.add_argument("--margin", type=float, default=None)
ap.add_argument("--shipping", type=float, default=None)
args = ap.parse_args()

try:
    pc = json.load(open("pricing.json"))
except FileNotFoundError:
    pc = {}
margin = args.margin if args.margin is not None else pc.get("margin")
shipping = args.shipping if args.shipping is not None else (pc.get("shipping_usd") or 0.0)

# ---------- Arabic naming ----------
def has(t, *words):
    return any(w in t for w in words)

def classify(t):
    if has(t, "abaya", "kaftan", "caftan", "muslim", "jalabiya", "hijab", "modest"):
        return "عباية" if "abaya" in t else ("قفطان" if has(t, "kaftan", "caftan") else "فستان محتشم"), "modest"
    if has(t, "jumpsuit", "romper", "playsuit", "overalls"):
        return "جمبسوت", "sets"
    if has(t, "jeans"):
        return "بنطلون جينز", "bottoms"
    if has(t, "blazer dress", "blazer floor"):
        return ("فستان بليزر", "dresses") if "dress" in t else ("طقم بليزر", "sets")
    if has(t, "two piece", "two-piece", "2 piece", "three-piece", "three piece", " set ", " sets ", "suit", "top and skirt", "outfit"):
        return "طقم", "sets"
    if has(t, "blazer"):
        return "بليزر", "jackets"
    if has(t, "fur coat"):
        return "معطف فرو", "jackets"
    if has(t, "wool coat", "wool-blend coat", "woolen coat"):
        return "معطف صوف", "jackets"
    if has(t, "down jacket", "puffer", "parka"):
        return "جاكيت شتوي", "jackets"
    if has(t, "trench", "jacket", "coat", "outerwear", "vest ", "waistcoat", "windbreaker"):
        return "جاكيت", "jackets"
    if has(t, " dress", "gown", "dresses"):
        if has(t, "evening", "banquet", "formal", "party", "wedding", "prom", "cocktail", "gala"):
            return "فستان سهرة", "evening"
        return "فستان", "dresses"
    if has(t, "sweater", "knitwear", "cardigan", "pullover", "jumper"):
        return "كنزة تريكو", "knit"
    if has(t, "pants", "trousers", "leggings", "shorts"):
        return "بنطلون" if "shorts" not in t else "شورت", "bottoms"
    if has(t, "skirt"):
        return "تنورة", "bottoms"
    if has(t, "blouse", "shirt", " top", "tops", "camisole", "t-shirt", "tee", "corset", "bodysuit"):
        return ("قميص" if "shirt" in t and "t-shirt" not in t else "بلوزة"), "tops"
    return "قطعة", "dresses"

DESCRIPTORS = [
    (("mermaid", "fish tail", "fishtail"), "بقصّة حورية"),
    (("off-shoulder", "off shoulder", "one-shoulder", "one shoulder", "one necked"), "أوف شولدر"),
    (("halter",), "رقبة هولتر"),
    (("strapless", "tube-top", "tube top"), "بدون أكتاف"),
    (("sequin",), "بالترتر"),
    (("lace",), "دانتيل"),
    (("rhinestone", "diamond", "bead", "studded", "mirror", "crystal"), "بالخرز اللامع"),
    (("embroider",), "مطرّز"),
    (("tassel", "fringe"), "بالشراشيب"),
    (("feather",), "بالريش"),
    (("3d floral", "floral", "flower", "rose", "petal"), "بالورود"),
    (("satin", "silk"), "ساتان"),
    (("chiffon",), "شيفون"),
    (("velvet",), "مخمل"),
    (("tweed",), "تويد"),
    (("leather", " pu "), "جلد"),
    (("denim",), "جينز"),
    (("linen",), "كتان"),
    (("knit",), "تريكو"),
    (("mesh", "tulle", "sheer"), "تول"),
    (("pleat",), "بليسيه"),
    (("leopard",), "بنقشة نمر"),
    (("polka",), "منقّط"),
    (("plaid", "check"), "كاروهات"),
    (("stripe",), "مقلّم"),
    (("puff sleeve", "puff-sleeve", "bubble sleeve", "lantern"), "بأكمام منفوخة"),
    (("cape",), "بكاب"),
    (("bow",), "بفيونكة"),
    (("bandage", "bodycon"), "ضيّق"),
    (("wide leg", "wide-leg"), "واسع"),
]
LENGTH = [(("mini", "short dress", "short elegant"), "ميني"),
          (("midi",), "ميدي"),
          (("maxi", "floor length", "full-length", "full length", "long dress", "long gown"), "ماكسي")]
COLORS = [("burgundy", "خمري"), ("wine", "خمري"), ("mint", "نعناعي"), ("apricot", "مشمشي"), ("champagne", "شمباني"),
          ("navy", "كحلي"), ("khaki", "كاكي"), ("red", "أحمر"), ("pink", "زهري"), ("black", "أسود"), ("white", "أبيض"),
          ("green", "أخضر"), ("yellow", "أصفر"), ("brown", "بني"), ("beige", "بيج"), ("silver", "فضي"), ("gold", "ذهبي"),
          ("blue", "أزرق"), ("purple", "بنفسجي"), ("grey", "رمادي"), ("gray", "رمادي"), ("orange", "برتقالي")]

def arabic_name(title):
    t = " " + title.lower().replace("&#39;", "'") + " "
    typ, cat = classify(t)
    parts = [typ]
    for keys, word in DESCRIPTORS:
        if len(parts) >= 3:
            break
        if word in typ:
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

def parse_usd(p):
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", p or "")]
    return max(nums) if nums else None

def jod_price(p):
    if margin is None:
        return None
    usd = parse_usd(p)
    if usd is None:
        return None
    return int(round((usd + shipping) * (1 + margin) * CONFIG["usd_to_jod"]))

# ---------- stable codes ----------
def load_public():
    try:
        d = json.load(open("products.json"))
        return d.get("items", [])
    except FileNotFoundError:
        return []

def make_code(pid, used):
    base = "NG-" + pid[-6:]
    code, k = base, 0
    while code in used:
        k += 1
        code = base + "ABCDEFGHJK"[k % 10]
    used.add(code)
    return code

def to_item(row, used, keep_code=None):
    pid, title, price, moq, _gid, imgs = row
    name, cat, color = arabic_name(title)
    code = keep_code or make_code(pid, used)
    return [code, name, cat, color, jod_price(price), imgs[:8]]

old = load_public()
old_by_img = {it[5][0]: it for it in old if it[5]}
used = {it[0] for it in old}
private_rows = []

if args.add:
    rows = json.load(open(args.add))
    new_items = []
    for r in rows:
        if not r[5] or r[5][0] in old_by_img:
            continue
        it = to_item(r, used)
        new_items.append(it)
        private_rows.append((it, r))
    items = new_items + old
    print(f"added {len(new_items)} new; total {len(items)}")
else:
    rows = json.load(open(args.src))
    items = []
    seen = set()
    for r in rows:
        if not r[5] or r[5][0] in seen:
            continue
        seen.add(r[5][0])
        prev = old_by_img.get(r[5][0])
        it = to_item(r, used, keep_code=prev[0] if prev else None)
        items.append(it)
        private_rows.append((it, r))
    print(f"full rebuild: {len(items)} items")

# private order map (only rows touched this run)
with open("orders-map.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["code", "arabic_name", "supplier_price_usd", "min_order", "site_price_jod", "supplier_title", "supplier_link"])
    for it, r in private_rows:
        w.writerow([it[0], it[1] + (" – " + it[3] if it[3] else ""), r[2], r[3], it[4] or "", r[1],
                    f"https://www.alibaba.com/product-detail/_{r[0]}.html"])

today = datetime.date.today()
months = ["كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران", "تموز", "آب", "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول"]
updated = f"{today.day} {months[today.month-1]} {today.year}"

json.dump({"updated": updated, "items": items}, open("products.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))

tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
out = (tpl.replace("__WA__", CONFIG["whatsapp"])
          .replace("__WA_DISPLAY__", CONFIG["whatsapp_display"])
          .replace("__IG__", CONFIG["instagram"])
          .replace("__ORDERS_URL__", CONFIG["orders_url"])
          .replace("__VER__", str(int(datetime.datetime.now().timestamp()))))
open("index.html", "w", encoding="utf-8").write(out)

from collections import Counter
print(dict(Counter(it[2] for it in items)))
