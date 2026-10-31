const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1012, height: 900 }, colorScheme: 'dark' });
  await p.goto(process.argv[2], { waitUntil: 'networkidle', timeout: 60000 });
  await p.waitForTimeout(4000); // let banner animation settle
  // top of repo page (file list, about) for first impression
  await p.screenshot({ path: (process.argv[3] || '.') + '/readme-00-repo-top.png', clip: { x: 0, y: 0, width: 1012, height: 1300 }, fullPage: true });
  const box = await (await p.$('article.markdown-body')).boundingBox();
  const H = 1300; let i = 1;
  for (let y = box.y; y < box.y + box.height; y += H, i++) {
    const h = Math.min(H, box.y + box.height - y);
    await p.screenshot({ path: `${process.argv[3] || '.'}/readme-${String(i).padStart(2,'0')}.png`, clip: { x: 0, y, width: 1012, height: h }, fullPage: true });
  }
  console.log('slices', i - 1);
  await b.close();
})();
