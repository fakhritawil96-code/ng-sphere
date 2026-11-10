// Run in the browser pane on https://mybettergirl.en.alibaba.com/productlist-N.html
// (viewport 1366x900, after ~3.5s load). Accumulates products in sessionStorage 'bg'.
await new Promise(r=>setTimeout(r,3500));
for(let i=0;i<6;i++){window.scrollBy(0,1200);await new Promise(r=>setTimeout(r,500));}
const m=JSON.parse(sessionStorage.getItem('bg')||'{}');
document.querySelectorAll('.icbu-product-card.vertical[data-id]').forEach(c=>{
  const a=c.querySelector('a.title-link'); if(!a) return;
  const im=c.querySelector('img'), p=c.querySelector('.price .num'), q=c.querySelector('.moq');
  m[c.dataset.id]={id:c.dataset.id,t:a.title,p:p?p.innerText.trim():'',
    q:q?q.innerText.replace(/Min\. (o|O)rder:?/,'').trim():'',
    img:im?(im.getAttribute('src')||'').replace(/_\d+x\d+\.jpg.*$/,'').replace(/\?.*$/,'').replace(/^\/\//,'https://'):''};
});
sessionStorage.setItem('bg',JSON.stringify(m)); Object.keys(m).length
// Export afterwards with:
// Object.values(JSON.parse(sessionStorage.getItem('bg'))).map(o=>[o.id,o.t,o.p,o.q,o.img.replace('https://s.alicdn.com/@sc04/kf/','')])
