// Copia in vendor/ i file delle librerie usate dal sito (dopo "npm ci").
// Tutto viene servito dallo stesso sito: niente CDN, i file restano sul computer di chi converte.
import { cpSync, mkdirSync, rmSync } from "node:fs";

const files = {
  "@ffmpeg/ffmpeg/dist/esm": "ffmpeg",              // cartella intera (worker.js, classes.js…)
  "@ffmpeg/util/dist/esm": "ffmpeg-util",
  "@ffmpeg/core/dist/esm/ffmpeg-core.js": "ffmpeg-core/ffmpeg-core.js",
  "@ffmpeg/core/dist/esm/ffmpeg-core.wasm": "ffmpeg-core/ffmpeg-core.wasm",
  "pdfjs-dist/build/pdf.min.mjs": "pdf.min.mjs",
  "pdfjs-dist/build/pdf.worker.min.mjs": "pdf.worker.min.mjs",
  "pdf-lib/dist/pdf-lib.esm.min.js": "pdf-lib.esm.min.js",
  "jszip/dist/jszip.min.js": "jszip.min.js",
  "heic2any/dist/heic2any.min.js": "heic2any.min.js",
  "mammoth/mammoth.browser.min.js": "mammoth.browser.min.js",
  "xlsx/dist/xlsx.full.min.js": "xlsx.full.min.js",
  "dxf/dist/dxf.js": "dxf.js",
};

rmSync("vendor", { recursive: true, force: true });
for (const [src, dst] of Object.entries(files)) {
  const to = `vendor/${dst}`;
  mkdirSync(to.substring(0, to.lastIndexOf("/")) || "vendor", { recursive: true });
  cpSync(`node_modules/${src}`, to, { recursive: true, filter: (p) => !p.endsWith(".d.ts") && !p.endsWith(".d.mts") });
  console.log("vendor/" + dst);
}
