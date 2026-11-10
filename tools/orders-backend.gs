/**
 * NG SPHERE — wholesale orders (Google Apps Script, bound to the "NG SPHERE Orders" sheet).
 * Deploy > New deployment > Web app: Execute as "Me", Who has access "Anyone".
 *  - POST from the website  -> doPost appends one order row (public; only creates).
 *  - Open the /exec URL      -> doGet shows the orders dashboard, only to the sheet's owner
 *                               while signed in to that Google account; everyone else gets a blank notice.
 */
const SHEET = "Orders";
const COLS = ["id", "receivedAt", "shop", "city", "phone", "models", "pieces", "items", "customerNotes",
              "status", "replied", "repliedAt", "followUp", "quote", "notes", "updatedAt", "log",
              "supplyStage", "cost", "sale"];
const JSON_COLS = {items: 1, log: 1};
const STATUSES = ["new", "waiting", "confirmed", "processing", "delivered", "cancelled"];
const STAGES = ["", "ordered", "shipped", "arrived"];
const STATS = "Stats";

function sheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet() || SpreadsheetApp.openById("1lVug4nLQ4928YfQF_XE33Ngq31XfACeJGpSW7bAoTqE");
  let sh = ss.getSheetByName(SHEET);
  if (!sh) { sh = ss.insertSheet(SHEET, 0); sh.appendRow(COLS); sh.setFrozenRows(1); }
  else if (sh.getLastColumn() < COLS.length) sh.getRange(1, 1, 1, COLS.length).setValues([COLS]);
  return sh;
}
function isOwner_() {
  const me = Session.getEffectiveUser().getEmail(), you = Session.getActiveUser().getEmail();
  return !!me && !!you && me.toLowerCase() === you.toLowerCase();
}
function guard_() { if (!isOwner_()) throw new Error("unauthorized"); }
function str_(v, n) { return String(v == null ? "" : v).slice(0, n || 200); }
function rowToObj_(r) {
  const o = {};
  COLS.forEach((c, i) => { let v = r[i];
    if (JSON_COLS[c]) { try { v = JSON.parse(v || "[]"); } catch (e) { v = []; } }
    if (v instanceof Date) v = v.toISOString();
    o[c] = v; });
  o.replied = o.replied === true || o.replied === "TRUE" || o.replied === "true";
  o.models = +o.models || 0; o.pieces = +o.pieces || 0;
  o.cost = o.cost === "" || o.cost == null ? "" : +o.cost || 0; o.sale = o.sale === "" || o.sale == null ? "" : +o.sale || 0;
  o.supplyStage = String(o.supplyStage || "");
  o.phone = String(o.phone || ""); if (/^7\d{8}$/.test(o.phone)) o.phone = "0" + o.phone;
  return o;
}
function objToRow_(o) { return COLS.map(c => JSON_COLS[c] ? JSON.stringify(o[c] || []) : c === "phone" && o[c] ? "'" + String(o[c]).replace(/^'/, "") : (o[c] == null ? "" : o[c])); }
function rows_(sh) { const last = sh.getLastRow(); return last > 1 ? sh.getRange(2, 1, last - 1, COLS.length).getValues() : []; }

// ---------- dashboard (owner only) ----------
function doGet() {
  if (!isOwner_()) return HtmlService.createHtmlOutput("<p style='font-family:sans-serif;padding:24px'>NG SPHERE</p>");
  return HtmlService.createHtmlOutputFromFile("Dashboard").setTitle("NG SPHERE · الطلبات")
    .addMetaTag("viewport", "width=device-width, initial-scale=1");
}
function listOrders() { guard_(); return JSON.stringify(rows_(sheet_()).map(rowToObj_)); }
function updateOrder(id, patch) {
  guard_();
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    const sh = sheet_(), rows = rows_(sh), idx = rows.findIndex(r => r[0] === id);
    if (idx < 0) throw new Error("not_found");
    const o = rowToObj_(rows[idx]), p = patch || {};
    ["shop", "city", "phone", "followUp", "quote", "notes", "repliedAt", "receivedAt"].forEach(k => { if (k in p) o[k] = str_(p[k], k === "notes" ? 2000 : 200); });
    if ("replied" in p) o.replied = !!p.replied;
    if ("supplyStage" in p && STAGES.indexOf(p.supplyStage) >= 0) o.supplyStage = p.supplyStage;
    ["cost", "sale"].forEach(k => { if (k in p) o[k] = p[k] === "" || p[k] == null ? "" : Math.max(0, +p[k] || 0); });
    if ("status" in p && STATUSES.indexOf(p.status) >= 0) o.status = p.status;
    if (p.logText) o.log = (o.log || []).concat([{t: new Date().toISOString(), text: str_(p.logText, 200)}]).slice(-30);
    o.updatedAt = new Date().toISOString();
    sh.getRange(idx + 2, 1, 1, COLS.length).setValues([objToRow_(o)]);
    return JSON.stringify(o);
  } finally { lock.releaseLock(); }
}
function deleteOrder(id) {
  guard_();
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try { const sh = sheet_(), idx = rows_(sh).findIndex(r => r[0] === id); if (idx >= 0) sh.deleteRow(idx + 2); return true; }
  finally { lock.releaseLock(); }
}

// ---------- model stats (views / adds from the website, orders from the sheet) ----------
function statsSheet_() {
  const ss = sheet_().getParent(); let sh = ss.getSheetByName(STATS);
  if (!sh) { sh = ss.insertSheet(STATS); sh.appendRow(["code", "views", "adds"]); sh.setFrozenRows(1); }
  return sh;
}
function recordEvents_(counts) {
  const keys = Object.keys(counts || {}).filter(k => /^NG-[0-9A-Z]{3,10}$/.test(k)).slice(0, 300);
  if (!keys.length) return;
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    const sh = statsSheet_(), last = sh.getLastRow();
    const vals = last > 1 ? sh.getRange(2, 1, last - 1, 3).getValues() : [];
    const at = {}; vals.forEach((r, i) => at[r[0]] = i);
    keys.forEach(k => { const c = counts[k] || {}, v = Math.min(50, +c.v || 0), a = Math.min(50, +c.a || 0);
      if (k in at) { vals[at[k]][1] = (+vals[at[k]][1] || 0) + v; vals[at[k]][2] = (+vals[at[k]][2] || 0) + a; }
      else { at[k] = vals.length; vals.push([k, v, a]); } });
    if (vals.length) sh.getRange(2, 1, vals.length, 3).setValues(vals);
  } finally { lock.releaseLock(); }
}
function listStats() {
  guard_();
  const sh = statsSheet_(), last = sh.getLastRow(), out = {};
  (last > 1 ? sh.getRange(2, 1, last - 1, 3).getValues() : []).forEach(r => out[r[0]] = {views: +r[1] || 0, adds: +r[2] || 0, orders: 0, pieces: 0});
  rows_(sheet_()).map(rowToObj_).forEach(o => { if (o.status === "cancelled") return;
    (o.items || []).forEach(i => { const s = out[i.code] = out[i.code] || {views: 0, adds: 0, orders: 0, pieces: 0}; s.orders++; s.pieces += +i.total || 0; s.name = i.name; s.img = i.img; }); });
  return JSON.stringify(out);
}

// ---------- intake from the website (public, create only) ----------
function out_(obj) { return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON); }
function doPost(e) {
  let body;
  try { body = JSON.parse(e.postData.contents); } catch (err) { return out_({ok: false, error: "bad_json"}); }
  const cache = CacheService.getScriptCache();
  if (body.action === "events") {
    const m = +(cache.get("erate") || 0); if (m > 300) return out_({ok: false, error: "busy"});
    cache.put("erate", String(m + 1), 60);
    recordEvents_(body.counts); return out_({ok: true});
  }
  if (body.action !== "create") return out_({ok: false, error: "unknown_action"});
  const n = +(cache.get("rate") || 0); if (n > 60) return out_({ok: false, error: "busy"});
  cache.put("rate", String(n + 1), 60);
  const o = body.order || {};
  const items = (Array.isArray(o.items) ? o.items : []).slice(0, 200).map(i => {
    const sizes = {};
    Object.keys(i.sizes || {}).slice(0, 80).forEach(s => { const q = Math.max(0, Math.min(9999, parseInt(i.sizes[s], 10) || 0)); if (q) sizes[str_(s, 30)] = q; });
    return {code: str_(i.code, 20), name: str_(i.name, 120), note: str_(i.note, 200), img: /^[A-Za-z0-9]+\.(jpg|jpeg|png)$/.test(i.img || "") ? i.img : "", sizes: sizes,
            total: Object.keys(sizes).reduce((a, k) => a + sizes[k], 0)};
  }).filter(i => i.total > 0);
  if (!items.length) return out_({ok: false, error: "empty"});
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
    const sh = sheet_();
    const id = /^NG-O-[0-9A-Z]{4,12}$/.test(o.id || "") ? o.id : "NG-O-" + Utilities.getUuid().slice(0, 6).toUpperCase();
    if (rows_(sh).some(r => r[0] === id)) return out_({ok: true, id: id, duplicate: true});
    const now = new Date().toISOString();
    sh.appendRow(objToRow_({id: id, receivedAt: now, shop: str_(o.shop, 120), city: str_(o.city, 80), phone: str_(o.phone, 30),
      models: items.length, pieces: items.reduce((a, i) => a + i.total, 0), items: items, customerNotes: str_(o.notes, 500),
      status: "new", replied: false, repliedAt: "", followUp: "", quote: "", notes: "", updatedAt: now,
      log: [{t: now, text: "وصل الطلب من الموقع"}], supplyStage: "", cost: "", sale: ""}));
    return out_({ok: true, id: id});
  } finally { lock.releaseLock(); }
}
