const fs = require('fs');
const path = require('path');
const { PDFDocument } = require('pdf-lib');

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error('Usage: node merge_pdfs.js <out.pdf> <in1.pdf> <in2.pdf> ...');
    process.exit(2);
  }
  const outPath = path.resolve(args[0]);
  const inPaths = args.slice(1).map(p => path.resolve(p));

  const outDoc = await PDFDocument.create();
  for (const p of inPaths) {
    const bytes = fs.readFileSync(p);
    const doc = await PDFDocument.load(bytes);
    const pages = await outDoc.copyPages(doc, doc.getPageIndices());
    for (const page of pages) outDoc.addPage(page);
  }
  const outBytes = await outDoc.save();
  fs.writeFileSync(outPath, outBytes);
  console.log('Wrote', outPath, 'pages=', outDoc.getPageCount());
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
