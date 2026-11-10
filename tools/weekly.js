// Weekly new-arrivals pull. Run with javascript_tool in the browser pane while the tab is on
// https://mybettergirl.en.alibaba.com/productlist-1.html (any viewport).
// Reads the live catalog to know what is already on the site, then walks the supplier's
// product list (newest first) until two pages in a row bring nothing new.
// Returns {newRows, pagesRead, stoppedBy}; newRows use the build.py row format:
// [id, title, price, moq, groupId, [imgHash.ext, ...]]
(async () => {
  const known = new Set();
  try {
    const d = await (await fetch('https://fakhritawil96-code.github.io/ng-sphere/products.json?t=' + Date.now())).json();
    d.items.forEach(it => it[5] && it[5][0] && known.add(it[5][0]));
  } catch (e) { return {error: 'could not read products.json: ' + e.message}; }
  const hashOf = u => { const m = (u||'').match(/\/kf\/([A-Za-z0-9]+)\/[^/]*?\.(jpg|jpeg|png)/i) || (u||'').match(/\/kf\/([A-Za-z0-9]+)\.(jpg|jpeg|png)/i); return m ? m[1] + '.' + m[2].toLowerCase() : null; };
  const newRows = []; let quiet = 0, p = 0, stoppedBy = 'quiet pages';
  while (quiet < 2 && p < 60) {
    p++;
    const h = await (await fetch('/productlist-' + p + '.html', {credentials: 'include'})).text();
    const d = new DOMParser().parseFromString(h, 'text/html');
    const el = d.querySelector('[module-title="productListPc"]');
    if (!el) { stoppedBy = /captcha|punish|slide/i.test(h.slice(0, 5000)) ? 'captcha' : 'page format changed'; break; }
    const list = JSON.parse(decodeURIComponent(el.getAttribute('module-data'))).mds.moduleData.data.productList || [];
    if (!list.length) { stoppedBy = 'end of catalog'; break; }
    let fresh = 0;
    for (const x of list) {
      const imgs = [...new Set((x.imageUrlList || []).map(o => hashOf(o.x350 || o.x120 || Object.values(o)[0])).filter(Boolean))];
      if (!imgs.length || known.has(imgs[0])) continue;
      known.add(imgs[0]); fresh++;
      newRows.push([String(x.id), x.subject, x.fobPriceWithoutUnit || '', x.moq || '', x.groupId || 0, imgs]);
    }
    quiet = fresh ? 0 : quiet + 1;
    await new Promise(r => setTimeout(r, 2500 + Math.random() * 1500));
  }
  return {newRows, pagesRead: p, stoppedBy};
})()
