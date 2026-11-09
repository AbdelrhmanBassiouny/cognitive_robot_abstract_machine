// Render the worksheet HTML to two PDFs: the worksheet and the worksheet with solutions.
// Usage: node render_pdf.js <worksheet.html> <output directory>
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const [source, outputDirectory] = process.argv.slice(2);
  const base = path.basename(source, '.html');
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + path.resolve(source));
  const footer = (label) => `<div style="width:100%; text-align:center; font-family:'Liberation Serif',serif;
    font-size:9pt; color:#777;">Advanced Methods of AI · ${label} · page <span class="pageNumber"></span></div>`;
  const variants = [
    { bodyClass: 'worksheet', file: `${base}.pdf` },
    { bodyClass: 'with-solutions', file: `${base}_solution.pdf` },
  ];
  for (const variant of variants) {
    await page.evaluate((bodyClass) => { document.body.className = bodyClass; }, variant.bodyClass);
    await page.pdf({
      path: path.join(outputDirectory, variant.file),
      format: 'A4',
      printBackground: true,
      displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: footer('Worksheet 3'),
      margin: { top: '20mm', bottom: '20mm', left: '21mm', right: '21mm' },
    });
  }
  await browser.close();
})();
