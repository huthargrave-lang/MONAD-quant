// usage: node shot.js <url> <out.png> <w> <h>
const { chromium } = require("playwright");
(async () => {
  const [url, out, w, h] = process.argv.slice(2);
  const b = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
  const p = await b.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: 1 });
  p.on("console", (m) => console.log("page:", m.text())); p.on("pageerror", (e) => console.log("page error:", e.message));
  await p.goto(url); await p.waitForFunction(() => window.DONE === true, null, { timeout: 180000 });
  await p.screenshot({ path: out, omitBackground: true }); await b.close(); console.log("saved", out);
})();
