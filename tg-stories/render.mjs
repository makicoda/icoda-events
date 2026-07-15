import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { readFileSync } from 'fs';

const html = readFileSync('/home/user/icoda-events/tg-stories/tg-q-presale-meta-ads.html', 'utf8');
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', headless: true });

for (let i = 0; i < 4; i++) {
  const page = await browser.newPage({ viewport: { width: 360, height: 640 }, deviceScaleFactor: 3 });
  const patched = html.replace('</style>', `
    body { padding:0!important; gap:0!important; background:#FAFBFD!important; }
    .slide { display:none!important; border-radius:0!important; width:360px!important; height:640px!important; }
    .slide:nth-child(${i + 1}) { display:flex!important; }
  </style>`);
  await page.setContent(patched, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => document.fonts.ready);
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: `/home/user/icoda-events/tg-stories/output/q-slide-${i + 1}.png` });
  await page.close();
}
await browser.close();
console.log('done');
