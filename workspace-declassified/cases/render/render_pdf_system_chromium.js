const path = require('path');
const puppeteer = require('puppeteer');

async function main() {
  const [,, inHtml, outPdf] = process.argv;
  if (!inHtml || !outPdf) {
    console.error('Usage: node render_pdf_system_chromium.js <in.html> <out.pdf>');
    process.exit(2);
  }
  const absHtml = path.resolve(inHtml);
  const absPdf = path.resolve(outPdf);
  const htmlUrl = 'file://' + absHtml;

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/usr/bin/chromium-browser',
    args: ['--no-sandbox','--disable-setuid-sandbox','--allow-file-access-from-files']
  });
  const page = await browser.newPage();
  await page.goto(htmlUrl, { waitUntil: 'networkidle0' });
  await page.emulateMediaType('print');
  await page.pdf({
    path: absPdf,
    format: 'Letter',
    printBackground: true,
    margin: { top: '18mm', right: '16mm', bottom: '18mm', left: '16mm' }
  });
  await browser.close();
  console.log('Wrote PDF:', absPdf);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
