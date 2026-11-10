// Full supplier catalog crawl. Run with javascript_tool in the browser pane while the tab is on
// https://mybettergirl.en.alibaba.com/productlist-1.html. Starts in the background and returns at once;
// poll window.__CR for progress, then read window.__CR_DUMP in 200,000-character slices.
// Row format (build.py v3): [id, title, price, moq, groupId, [imgHash...], sold180, orders, [[hex, imgHash]...], freightUSD, rank]
(() => {
  const hashOf = u => { const m = (u || '').match(/\/kf\/([A-Za-z0-9]+)\/[^/]*?\.(jpg|jpeg|png)/i) || (u || '').match(/\/kf\/([A-Za-z0-9]+)\.(jpg|jpeg|png)/i); return m ? m[1] + '.' + m[2].toLowerCase() : null; };
  const num = s => { const m = String(s || '').match(/[\d.]+/); return m ? +m[0] : 0; };
  const ALL = {}; let rank = 0;
  const S = window.__CR = {phase: 'list', page: 0, group: 0, groups: 0, rows: 0, err: null, running: true, startedAt: Date.now()};
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  async function readPage(url) {
    for (let a = 0; a < 3; a++) {
      try {
        const h = await (await fetch(url, {credentials: 'include'})).text();
        const d = new DOMParser().parseFromString(h, 'text/html');
        const el = d.querySelector('[module-title="productListPc"]');
        if (!el) { if (/captcha|punish|slide to verify/i.test(h.slice(0, 6000))) return {captcha: true}; throw new Error('no list'); }
        const D = JSON.parse(decodeURIComponent(el.getAttribute('module-data'))).mds.moduleData.data;
        return {list: D.productList || [], nav: D.pageNavView};
      } catch (e) { await sleep(5000); }
    }
    return {list: null};
  }
  function take(x) {
    if (ALL[x.id]) return 0;
    const imgs = [...new Set((x.imageUrlList || []).map(o => hashOf(o.x350 || o.x120 || Object.values(o)[0])).filter(Boolean))];
    if (!imgs.length) return 0;
    const colors = (x.skuColorRGB || []).map((hex, i) => [hex, hashOf((x.skuImg || [])[i]) || '']).slice(0, 12);
    ALL[x.id] = [String(x.id), x.subject, x.fobPriceWithoutUnit || '', x.moq || '', x.groupId || 0, imgs.slice(0, 8),
                 +x.prodSold180 || 0, +x.prodOrdCnt || 0, colors, num(x.localFreightStr), rank++];
    return 1;
  }
  (async () => {
    // 1) main list, newest first, until it runs dry
    for (let p = 1; p <= 400; p++) {
      S.page = p;
      const r = await readPage('/productlist-' + p + '.html');
      if (r.captcha) { S.err = 'captcha (list page ' + p + ')'; break; }
      if (!r.list || !r.list.length) break;
      r.list.forEach(take); S.rows = Object.keys(ALL).length;
      await sleep(2000 + Math.random() * 1500);
    }
    // 2) every category list, to reach models the main list stops showing
    if (!S.err) {
      S.phase = 'groups';
      const groups = [...new Set(Object.values(ALL).map(r => String(r[4])).filter(g => g && g !== '0'))];
      S.groups = groups.length;
      for (let gi = 0; gi < groups.length && !S.err; gi++) {
        S.group = gi; let maxP = 60;
        for (let p = 1; p <= maxP; p++) {
          S.page = p;
          const r = await readPage('/productgrouplist-' + groups[gi] + '-' + p + '/x.html');
          if (r.captcha) { S.err = 'captcha (group ' + gi + ' page ' + p + ')'; break; }
          if (!r.list || !r.list.length) break;
          if (p === 1 && r.nav && r.nav.totalLines) maxP = Math.min(60, Math.ceil(r.nav.totalLines / (r.nav.pageLines || 16)));
          r.list.forEach(take); S.rows = Object.keys(ALL).length;
          await sleep(2000 + Math.random() * 1500);
        }
      }
    }
    window.__CR_DUMP = JSON.stringify(Object.values(ALL));
    S.chunks = Math.ceil(window.__CR_DUMP.length / 200000);
    S.running = false; S.secs = Math.round((Date.now() - S.startedAt) / 1000);
  })();
  return 'started';
})()
