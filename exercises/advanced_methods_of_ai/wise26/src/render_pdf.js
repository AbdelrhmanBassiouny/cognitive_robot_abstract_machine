// Render the HTML sources to PDF.
// Usage: node render_pdf.js <worksheet.html> <output directory>   -> the worksheet and the worksheet with solutions
//        node render_pdf.js <slides.html> <output directory> --slides   -> one PDF, one slide per page
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const [source, outputDirectory, mode] = process.argv.slice(2);
  const base = path.basename(source, '.html');
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + path.resolve(source));
  if (mode === '--slides') {
    await page.pdf({ path: path.join(outputDirectory, `${base}.pdf`), preferCSSPageSize: true, printBackground: true });
    await browser.close();
    return;
  }
  const footer = (label) => `<div style="width:100%; text-align:center; font-family:'Liberation Serif',serif;
    font-size:9pt; color:#000;">Advanced Methods of AI · ${label} · page <span class="pageNumber"></span></div>`;
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
