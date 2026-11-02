// REPORT_v4.html -> REPORT_v4.pdf with the pre-installed Chromium (playwright, node)
const { chromium } = require('playwright');
(async () => {
  const [html, pdf] = process.argv.slice(2);
  const browser = await chromium.launch(); const page = await browser.newPage();
  await page.goto('file://' + html, { waitUntil: 'load' });
  await page.pdf({ path: pdf, format: 'A4', landscape: true, printBackground: true, margin: { top: '12mm', bottom: '12mm', left: '12mm', right: '12mm' } });
  await browser.close(); console.log('pdf written');
})();
