const { chromium } = require('playwright');
(async()=>{
  const b = await chromium.launch(); const p = await b.newPage({viewport:{width:1920,height:1080}});
  await p.goto('file://'+__dirname+'/video.html'); await p.evaluate(()=>window.ready);
  const ts = process.argv.slice(2).map(Number);
  for(const t of ts){ await p.evaluate(t=>render(t),t); await p.screenshot({path:`${__dirname}/stills/s_${t.toFixed(2)}.png`}); }
  await b.close();
})();
