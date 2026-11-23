// ConvertiTutto nel browser: trascina → scegli la conversione → scarica.
// Tutte le conversioni avvengono in locale (canvas, ffmpeg.wasm, pdf.js, pdf-lib, SheetJS, mammoth, dxf, JSZip).

const $ = (s) => document.querySelector(s);
const V = "vendor/";

// ------------------------------------------------------------------ librerie (caricate solo quando servono)
const scripts = {};
function loadScript(src, globalName) {
  if (!scripts[src]) {
    scripts[src] = new Promise((ok, ko) => {
      const s = document.createElement("script");
      s.src = src;
      s.onload = () => ok(window[globalName]);
      s.onerror = () => ko(new Error("Non riesco a caricare un componente del sito. Controlla la connessione e riprova."));
      document.head.appendChild(s);
    });
  }
  return scripts[src];
}
const lib = {
  jszip: () => loadScript(V + "jszip.min.js", "JSZip"),
  heic: () => loadScript(V + "heic2any.min.js", "heic2any"),
  mammoth: () => loadScript(V + "mammoth.browser.min.js", "mammoth"),
  xlsx: () => loadScript(V + "xlsx.full.min.js", "XLSX"),
  dxf: () => loadScript(V + "dxf.js", "dxf"),
  pdflib: () => import("./" + V + "pdf-lib.esm.min.js"),
  async pdfjs() {
    const m = await import("./" + V + "pdf.min.mjs");
    m.GlobalWorkerOptions.workerSrc = new URL(V + "pdf.worker.min.mjs", location.href).href;
    return m;
  },
};

let ffmpegPromise = null;
function getFFmpeg(progress) {
  if (!ffmpegPromise) {
    ffmpegPromise = (async () => {
      progress(0, "Preparo il convertitore audio/video (circa 30 MB, solo la prima volta)…");
      const { FFmpeg } = await import("./" + V + "ffmpeg/index.js");
      const ff = new FFmpeg();
      const base = new URL(V + "ffmpeg-core/", location.href).href;
      await ff.load({ coreURL: base + "ffmpeg-core.js", wasmURL: base + "ffmpeg-core.wasm" });
      return ff;
    })();
    ffmpegPromise.catch(() => { ffmpegPromise = null; });
  }
  return ffmpegPromise;
}

// ------------------------------------------------------------------ riconoscimento dei file
const GROUPS = {
  image: { ext: ["jpg", "jpeg", "jfif", "png", "webp", "gif", "bmp", "avif", "heic", "heif", "svg", "ico"], icon: "🖼️", label: "Immagine" },
  video: { ext: ["mp4", "mov", "mkv", "avi", "webm", "wmv", "flv", "3gp", "m4v", "mpg", "mpeg", "ts", "mts", "m2ts", "ogv"], icon: "🎬", label: "Video" },
  audio: { ext: ["mp3", "wav", "m4a", "aac", "ogg", "oga", "opus", "flac", "wma", "aiff", "aif", "amr"], icon: "🎵", label: "Audio" },
  pdf: { ext: ["pdf"], icon: "📕", label: "PDF" },
  word: { ext: ["docx"], icon: "📝", label: "Documento Word" },
  sheet: { ext: ["xlsx", "xlsm", "xls", "ods", "csv"], icon: "📊", label: "Foglio di calcolo" },
  cad: { ext: ["dxf"], icon: "📐", label: "Disegno CAD" },
  zip: { ext: ["zip"], icon: "🗜️", label: "Archivio ZIP" },
  apple: { ext: ["pages", "key", "numbers"], icon: "🍎", label: "Documento Apple" },
};
const NOT_IN_BROWSER = {
  dwg: "I file DWG non si possono leggere nel browser. Salvali come DXF da AutoCAD (Salva con nome → DXF) e trascinali qui.",
  doc: "I documenti Word 97-2003 (.doc) non si possono convertire nel browser: aprili in Word e salvali come .docx, poi trascinali qui.",
  ppt: "Le presentazioni PowerPoint non si possono convertire nel browser: da PowerPoint scegli File → Esporta → PDF.",
  pptx: "Le presentazioni PowerPoint non si possono convertire nel browser: da PowerPoint scegli File → Esporta → PDF.",
  odt: "I documenti OpenOffice non si possono convertire nel browser: da LibreOffice salvali come .docx.",
  rtf: "I file RTF non si possono convertire nel browser: aprili in Word e salvali come .docx.",
  epub: "Gli e-book non si possono convertire nel browser.",
  mobi: "Gli e-book non si possono convertire nel browser.",
  rar: "Gli archivi RAR non si possono aprire nel browser.",
  "7z": "Gli archivi 7Z non si possono aprire nel browser.",
  tif: "Le immagini TIFF non si possono leggere nel browser.",
  tiff: "Le immagini TIFF non si possono leggere nel browser.",
  psd: "I file Photoshop non si possono leggere nel browser: da Photoshop esportali in PNG o JPG.",
};

const extOf = (name) => (name.includes(".") ? name.split(".").pop().toLowerCase() : "");
const stemOf = (name) => (name.includes(".") ? name.slice(0, name.lastIndexOf(".")) : name);
function groupOf(file) {
  const e = extOf(file.name);
  for (const [g, def] of Object.entries(GROUPS)) if (def.ext.includes(e)) return g;
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";
  if (file.type.startsWith("audio/")) return "audio";
  return null;
}
function humanSize(n) {
  if (n < 1024) return `${n} byte`;
  const u = ["KB", "MB", "GB"];
  let i = -1;
  do { n /= 1024; i++; } while (n >= 1024 && i < u.length - 1);
  return `${n.toLocaleString("it-IT", { maximumFractionDigits: n < 10 ? 1 : 0 })} ${u[i]}`;
}

// ------------------------------------------------------------------ conversioni proposte
// T(id, titolo, descrizione, etichetta)
const T = (id, title, desc, tag) => ({ id, title, desc, tag: tag || title });

function targetsFor(group, files) {
  const e = extOf(files[0].name);
  const many = files.length > 1;
  const rec = [], more = [];
  switch (group) {
    case "image": {
      const all = [T("img-jpg", "JPG", "Il formato più compatibile", "JPG"), T("img-png", "PNG", "Senza perdita di qualità", "PNG"),
        T("img-webp", "WEBP", "Leggero, per il web", "WEBP"), T("img-pdf", "PDF", many ? "Un PDF per ogni immagine" : "Immagine su pagina A4", "PDF"),
        T("img-small", "JPG ridotto", "Massimo 1920 pixel, per email e chat", "JPG"), T("img-ico", "Icona ICO", "256 × 256, per Windows", "ICO"),
        T("img-bmp", "BMP", "Bitmap di Windows", "BMP")];
      const recIds = { heic: ["img-jpg", "img-png", "img-pdf"], heif: ["img-jpg", "img-png", "img-pdf"], png: ["img-jpg", "img-webp", "img-pdf"],
        webp: ["img-jpg", "img-png"], avif: ["img-jpg", "img-png"], svg: ["img-png", "img-jpg", "img-pdf"] }[e] || ["img-png", "img-webp", "img-pdf"];
      if (many) rec.push(T("img-pdf-one", "Un solo PDF", "Tutte le immagini in un PDF, una per pagina", "PDF"));
      for (const t of all) {
        if ((e === "jpg" || e === "jpeg") && t.id === "img-jpg") continue;
        if (e === t.id.slice(4)) continue;
        (recIds.includes(t.id) ? rec : more).push(t);
      }
      break;
    }
    case "video":
      rec.push(T("v-mp4", "MP4", "Si apre ovunque (H.264)"), T("v-whatsapp", "Per WhatsApp", "MP4 leggero, massimo 1280 pixel", "MP4"),
        T("v-mp3", "Solo audio", "Estrae l'audio in MP3", "MP3"));
      more.push(T("v-gif", "GIF animata", "Massimo 480 pixel, 10 fotogrammi al secondo", "GIF"), T("v-webm", "WEBM", "Per il web", "WEBM"),
        T("a-wav", "Audio WAV", "Audio senza compressione", "WAV"));
      if (e === "mp4") rec.shift();
      break;
    case "audio": {
      const all = [T("a-mp3", "MP3", "Il più compatibile"), T("a-m4a", "M4A", "AAC, ottimo su iPhone"), T("a-wav", "WAV", "Senza compressione"),
        T("a-flac", "FLAC", "Senza perdita, compresso"), T("a-ogg", "OGG", "Vorbis"), T("a-opus", "OPUS", "Leggerissimo, per la voce")];
      const recIds = e === "mp3" ? ["a-m4a", "a-wav"] : ["a-mp3", "a-m4a"];
      for (const t of all) {
        if (t.id === "a-" + e || (e === "aac" && t.id === "a-m4a")) continue;
        (recIds.includes(t.id) ? rec : more).push(t);
      }
      break;
    }
    case "pdf":
      if (many) rec.push(T("pdf-merge", "Un solo PDF", "Unisce i PDF nell'ordine in cui li hai scelti", "PDF"));
      rec.push(T("pdf-jpg", "Immagini JPG", "Una immagine per ogni pagina", "JPG"), T("pdf-txt", "Testo", "Solo il testo (non legge le scansioni)", "TXT"));
      more.push(T("pdf-png", "Immagini PNG", "Una immagine per ogni pagina, qualità massima", "PNG"));
      break;
    case "word":
      rec.push(T("doc-pdf", "PDF", "Con la stampa del browser: scegli «Salva come PDF»", "PDF"), T("doc-txt", "Testo", "Solo il testo", "TXT"));
      more.push(T("doc-html", "Pagina web", "HTML con titoli, elenchi, tabelle e immagini", "HTML"));
      break;
    case "sheet": {
      const all = [T("sh-xlsx", "Excel", "Formato moderno (.xlsx)", "XLSX"), T("sh-csv", "CSV", "Un file per ogni foglio", "CSV"),
        T("sh-ods", "OpenOffice", "Foglio di calcolo ODS", "ODS"), T("sh-html", "Pagina web", "Tabelle in HTML", "HTML")];
      const recIds = e === "csv" ? ["sh-xlsx", "sh-ods"] : ["sh-xlsx", "sh-csv"];
      for (const t of all) {
        if (t.id === "sh-" + e) continue;
        (recIds.includes(t.id) ? rec : more).push(t);
      }
      break;
    }
    case "cad":
      rec.push(T("cad-pdf", "PDF", "Disegno adattato a un foglio A3", "PDF"), T("cad-svg", "SVG", "Vettoriale, si ingrandisce senza perdere qualità", "SVG"));
      more.push(T("cad-png", "Immagine PNG", "3000 pixel di larghezza", "PNG"));
      break;
    case "zip":
      rec.push(T("zip-extract", "Estrai", "Scarica i file contenuti nell'archivio", "ESTRAI"));
      break;
    case "apple":
      rec.push(T("apple-preview", "Anteprima", "La prima pagina come PDF o JPG (salvata da Apple nel file)", "PDF/JPG"));
      break;
  }
  if (many || group === null) more.push(T("zip-make", "Comprimi in ZIP", "Tutti i file in un unico archivio", "ZIP"));
  else more.push(T("zip-make", "Comprimi in ZIP", "Il file in un archivio ZIP", "ZIP"));
  return { rec, more };
}

// ------------------------------------------------------------------ aiuti
const out = (name, blob) => ({ name, blob });
async function canvasBlob(canvas, type, quality) {
  return new Promise((ok, ko) => canvas.toBlob((b) => (b ? ok(b) : ko(new Error("Il browser non sa creare questo formato."))), type, quality));
}
async function decodeImage(file) {
  let blob = file;
  const e = extOf(file.name);
  if (e === "heic" || e === "heif") {
    const heic2any = await lib.heic();
    const r = await heic2any({ blob: file, toType: "image/png" });
    blob = Array.isArray(r) ? r[0] : r;
  }
  const url = URL.createObjectURL(blob);
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await img.decode().catch(() => { throw new Error("Questa immagine non si apre: il file potrebbe essere danneggiato o in un formato non supportato dal browser."); });
    let w = img.naturalWidth, h = img.naturalHeight;
    if (!w || !h) { w = 1024; h = 1024; } // SVG senza dimensioni
    if (e === "svg" && Math.max(w, h) < 1024) { const k = 2048 / Math.max(w, h); w = Math.round(w * k); h = Math.round(h * k); }
    return { img, w, h };
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }
}
function drawCanvas({ img, w, h }, maxSide = 0, background = null) {
  const k = maxSide && Math.max(w, h) > maxSide ? maxSide / Math.max(w, h) : 1;
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(w * k));
  c.height = Math.max(1, Math.round(h * k));
  const g = c.getContext("2d");
  if (background) { g.fillStyle = background; g.fillRect(0, 0, c.width, c.height); }
  g.imageSmoothingQuality = "high";
  g.drawImage(img, 0, 0, c.width, c.height);
  return c;
}
function bmpFromCanvas(c) {
  const { width: w, height: h } = c;
  const data = c.getContext("2d").getImageData(0, 0, w, h).data;
  const row = Math.ceil((w * 3) / 4) * 4, size = 54 + row * h;
  const buf = new ArrayBuffer(size), v = new DataView(buf);
  v.setUint16(0, 0x4d42, true); v.setUint32(2, size, true); v.setUint32(10, 54, true);
  v.setUint32(14, 40, true); v.setInt32(18, w, true); v.setInt32(22, h, true); v.setUint16(26, 1, true); v.setUint16(28, 24, true);
  v.setUint32(34, row * h, true); v.setInt32(38, 2835, true); v.setInt32(42, 2835, true);
  const px = new Uint8Array(buf);
  for (let y = 0; y < h; y++) {
    let o = 54 + (h - 1 - y) * row;
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      px[o++] = data[i + 2]; px[o++] = data[i + 1]; px[o++] = data[i];
    }
  }
  return new Blob([buf], { type: "image/bmp" });
}
async function icoFromImage(decoded) {
  const side = 256, k = Math.min(side / decoded.w, side / decoded.h);
  const c = document.createElement("canvas");
  c.width = c.height = side;
  const g = c.getContext("2d");
  g.imageSmoothingQuality = "high";
  const w = decoded.w * k, h = decoded.h * k;
  g.drawImage(decoded.img, (side - w) / 2, (side - h) / 2, w, h);
  const png = new Uint8Array(await (await canvasBlob(c, "image/png")).arrayBuffer());
  const head = new DataView(new ArrayBuffer(22));
  head.setUint16(2, 1, true); head.setUint16(4, 1, true);         // tipo icona, 1 immagine
  head.setUint8(6, 0); head.setUint8(7, 0);                         // 0 = 256 pixel
  head.setUint16(10, 1, true); head.setUint16(12, 32, true);
  head.setUint32(14, png.length, true); head.setUint32(18, 22, true);
  return new Blob([head.buffer, png], { type: "image/x-icon" });
}
// pagina A4 (verticale o orizzontale) con l'immagine adattata e margini di 10 mm
async function addImagePage(pdf, jpgBytes, w, h, paper = [595.28, 841.89]) {
  const img = await pdf.embedJpg(jpgBytes);
  let [pw, ph] = paper;
  if (w > h) [pw, ph] = [ph, pw];
  const m = 28.35, k = Math.min((pw - 2 * m) / w, (ph - 2 * m) / h);
  const page = pdf.addPage([pw, ph]);
  page.drawImage(img, { x: (pw - w * k) / 2, y: (ph - h * k) / 2, width: w * k, height: h * k });
}

// ------------------------------------------------------------------ motore
async function convertImage(file, t, progress) {
  const stem = stemOf(file.name);
  progress(0.2, "Apro l'immagine…");
  const d = await decodeImage(file);
  progress(0.6, "Converto…");
  switch (t) {
    case "img-jpg": return [out(stem + ".jpg", await canvasBlob(drawCanvas(d, 0, "#fff"), "image/jpeg", 0.92))];
    case "img-small": return [out(stem + "_ridotto.jpg", await canvasBlob(drawCanvas(d, 1920, "#fff"), "image/jpeg", 0.85))];
    case "img-png": return [out(stem + ".png", await canvasBlob(drawCanvas(d), "image/png"))];
    case "img-webp": {
      const b = await canvasBlob(drawCanvas(d), "image/webp", 0.9);
      if (b.type !== "image/webp") throw new Error("Questo browser non sa creare immagini WEBP: prova con Chrome, Edge o Firefox.");
      return [out(stem + ".webp", b)];
    }
    case "img-bmp": return [out(stem + ".bmp", bmpFromCanvas(drawCanvas(d, 0, "#fff")))];
    case "img-ico": return [out(stem + ".ico", await icoFromImage(d))];
    case "img-pdf": {
      const { PDFDocument } = await lib.pdflib();
      const pdf = await PDFDocument.create();
      const c = drawCanvas(d, 4000, "#fff");
      await addImagePage(pdf, await (await canvasBlob(c, "image/jpeg", 0.92)).arrayBuffer(), c.width, c.height);
      return [out(stem + ".pdf", new Blob([await pdf.save()], { type: "application/pdf" }))];
    }
  }
  throw new Error("Conversione non disponibile.");
}

async function imagesToOnePdf(files, progress) {
  const { PDFDocument } = await lib.pdflib();
  const pdf = await PDFDocument.create();
  for (let i = 0; i < files.length; i++) {
    progress(i / files.length, `Immagine ${i + 1} di ${files.length}…`);
    const c = drawCanvas(await decodeImage(files[i]), 4000, "#fff");
    await addImagePage(pdf, await (await canvasBlob(c, "image/jpeg", 0.92)).arrayBuffer(), c.width, c.height);
  }
  return [out(stemOf(files[0].name) + "_e_altre.pdf", new Blob([await pdf.save()], { type: "application/pdf" }))];
}

const FF_ARGS = {
  "v-mp4": ["mp4", ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"]],
  "v-whatsapp": ["mp4", ["-vf", "scale='min(1280,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-maxrate", "1500k", "-bufsize", "3000k",
    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart"], "_whatsapp"],
  "v-gif": ["gif", ["-an", "-vf", "fps=10,scale='min(480,iw)':-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse", "-loop", "0"]],
  "v-webm": ["webm", ["-c:v", "libvpx", "-b:v", "1500k", "-deadline", "realtime", "-cpu-used", "8", "-c:a", "libopus", "-b:a", "128k"]],
  "v-mp3": ["mp3", ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]],
  "a-mp3": ["mp3", ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]],
  "a-m4a": ["m4a", ["-vn", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]],
  "a-wav": ["wav", ["-vn", "-c:a", "pcm_s16le"]],
  "a-flac": ["flac", ["-vn", "-c:a", "flac"]],
  "a-ogg": ["ogg", ["-vn", "-c:a", "libvorbis", "-q:a", "5"]],
  "a-opus": ["opus", ["-vn", "-c:a", "libopus", "-b:a", "128k"]],
};
async function convertMedia(file, t, progress) {
  if (file.size > 1.8 * 1024 ** 3) throw new Error("Il file è troppo grande per il browser (massimo circa 1,8 GB).");
  const ff = await getFFmpeg(progress);
  const [ext, args, suffix = ""] = FF_ARGS[t];
  const input = "input." + (extOf(file.name) || "bin"), output = "output." + ext;
  progress(0.02, "Leggo il file…");
  await ff.writeFile(input, new Uint8Array(await file.arrayBuffer()));
  const onProgress = ({ progress: p }) => { if (p >= 0 && p <= 1) progress(p, `Converto… ${Math.round(p * 100)}%`); };
  let log = [];
  const onLog = ({ message }) => { log.push(message); if (log.length > 30) log.shift(); };
  ff.on("progress", onProgress);
  ff.on("log", onLog);
  try {
    const code = await ff.exec(["-i", input, ...args, "-y", output]);
    if (code !== 0) {
      const noAudio = log.some((l) => /does not contain any stream|Output file .* does not contain|matches no streams/i.test(l));
      throw new Error(noAudio ? "Questo file non contiene audio." : "La conversione non è riuscita: il file potrebbe essere danneggiato o in un formato non supportato.");
    }
    const data = await ff.readFile(output);
    const mime = { mp4: "video/mp4", gif: "image/gif", webm: "video/webm", mp3: "audio/mpeg", m4a: "audio/mp4", wav: "audio/wav", flac: "audio/flac", ogg: "audio/ogg", opus: "audio/ogg" }[ext];
    return [out(stemOf(file.name) + suffix + "." + ext, new Blob([data.buffer], { type: mime }))];
  } finally {
    ff.off("progress", onProgress);
    ff.off("log", onLog);
    await ff.deleteFile(input).catch(() => {});
    await ff.deleteFile(output).catch(() => {});
  }
}

async function openPdf(file) {
  const pdfjs = await lib.pdfjs();
  try {
    return await pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()), isEvalSupported: false }).promise;
  } catch (e) {
    if (e && e.name === "PasswordException") throw new Error("Il PDF è protetto da password.");
    throw new Error("Questo PDF non si apre: potrebbe essere danneggiato.");
  }
}
async function convertPdf(file, t, progress) {
  const stem = stemOf(file.name);
  progress(0.05, "Apro il PDF…");
  const doc = await openPdf(file);
  const n = doc.numPages;
  if (t === "pdf-txt") {
    const parts = [];
    for (let i = 1; i <= n; i++) {
      progress(i / n, `Pagina ${i} di ${n}…`);
      const tc = await (await doc.getPage(i)).getTextContent();
      let s = "";
      for (const it of tc.items) s += (it.str || "") + (it.hasEOL ? "\n" : "");
      parts.push(s.replace(/[ \t]+\n/g, "\n").trim());
    }
    const text = parts.join("\n\n\f").trim();
    if (!text.replace(/\f/g, "").trim()) throw new Error("Non ho trovato testo: probabilmente è una scansione. Puoi convertirlo in immagini JPG.");
    return [out(stem + ".txt", new Blob(["﻿" + text + "\n"], { type: "text/plain;charset=utf-8" }))];
  }
  const fmt = t === "pdf-png" ? ["png", "image/png", undefined] : ["jpg", "image/jpeg", 0.9];
  const res = [];
  for (let i = 1; i <= n; i++) {
    progress((i - 1) / n, `Pagina ${i} di ${n}…`);
    const page = await doc.getPage(i);
    const base = page.getViewport({ scale: 1 });
    const scale = Math.min(200 / 72, 5000 / Math.max(base.width, base.height));  // 200 dpi, massimo 5000 pixel
    const vp = page.getViewport({ scale });
    const c = document.createElement("canvas");
    c.width = Math.round(vp.width); c.height = Math.round(vp.height);
    const g = c.getContext("2d");
    g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height);
    await page.render({ canvasContext: g, canvas: c, viewport: vp }).promise;
    const name = n === 1 ? `${stem}.${fmt[0]}` : `${stem}_pagina_${String(i).padStart(String(n).length, "0")}.${fmt[0]}`;
    res.push(out(name, await canvasBlob(c, fmt[1], fmt[2])));
    page.cleanup();
  }
  return res;
}
async function mergePdfs(files, progress) {
  const { PDFDocument } = await lib.pdflib();
  const merged = await PDFDocument.create();
  for (let i = 0; i < files.length; i++) {
    progress(i / files.length, `Aggiungo ${files[i].name}…`);
    let src;
    try { src = await PDFDocument.load(await files[i].arrayBuffer(), { ignoreEncryption: true }); }
    catch { throw new Error(`«${files[i].name}» non si apre: potrebbe essere danneggiato o protetto.`); }
    for (const p of await merged.copyPages(src, src.getPageIndices())) merged.addPage(p);
  }
  return [out(stemOf(files[0].name) + "_unito.pdf", new Blob([await merged.save()], { type: "application/pdf" }))];
}

const HTML_STYLE = `body{font:12pt/1.45 Calibri,"Segoe UI",Arial,sans-serif;max-width:820px;margin:2em auto;padding:0 1em;color:#111}
table{border-collapse:collapse;margin:1em 0}td,th{border:1px solid #999;padding:4px 8px;vertical-align:top}img{max-width:100%}
@media print{body{margin:0;max-width:none}}`;
function htmlPage(title, body) {
  const esc = title.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  return `<!doctype html><html lang="it"><head><meta charset="utf-8"><title>${esc}</title><style>${HTML_STYLE}</style></head><body>${body}</body></html>`;
}
async function convertWord(file, t, progress) {
  const mammoth = await lib.mammoth();
  const stem = stemOf(file.name);
  progress(0.3, "Leggo il documento…");
  const arrayBuffer = await file.arrayBuffer();
  try {
    if (t === "doc-txt") {
      const r = await mammoth.extractRawText({ arrayBuffer });
      return [out(stem + ".txt", new Blob(["﻿" + r.value.replace(/\n{3,}/g, "\n\n").trim() + "\n"], { type: "text/plain;charset=utf-8" }))];
    }
    const r = await mammoth.convertToHtml({ arrayBuffer });
    const html = htmlPage(stem, r.value);
    if (t === "doc-html") return [out(stem + ".html", new Blob([html], { type: "text/html;charset=utf-8" }))];
    return [{ name: stem + ".pdf", print: html }];
  } catch (e) {
    throw new Error("Questo documento Word non si apre: potrebbe essere danneggiato o protetto da password.");
  }
}

async function convertSheet(file, t, progress) {
  const XLSX = await lib.xlsx();
  const stem = stemOf(file.name);
  progress(0.3, "Leggo il foglio di calcolo…");
  let wb;
  try {
    wb = extOf(file.name) === "csv"
      ? XLSX.read(await file.text(), { type: "string", raw: false })
      : XLSX.read(new Uint8Array(await file.arrayBuffer()), { type: "array", cellDates: true });
  } catch {
    throw new Error("Questo foglio di calcolo non si apre: potrebbe essere danneggiato o protetto da password.");
  }
  progress(0.7, "Converto…");
  if (t === "sh-csv") {
    return wb.SheetNames.map((s) => {
      const csv = XLSX.utils.sheet_to_csv(wb.Sheets[s], { FS: ";", blankrows: false });
      const name = wb.SheetNames.length === 1 ? `${stem}.csv` : `${stem}_${s.replace(/[\\/:*?"<>|]/g, "_")}.csv`;
      return out(name, new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
    });
  }
  if (t === "sh-html") {
    const body = wb.SheetNames.map((s) => `<h2>${s.replace(/</g, "&lt;")}</h2>` + XLSX.utils.sheet_to_html(wb.Sheets[s], { header: "", footer: "" })).join("\n");
    return [out(stem + ".html", new Blob([htmlPage(stem, body)], { type: "text/html;charset=utf-8" }))];
  }
  const bookType = t === "sh-ods" ? "ods" : "xlsx";
  const data = XLSX.write(wb, { bookType, type: "array", compression: true });
  const mime = bookType === "ods" ? "application/vnd.oasis.opendocument.spreadsheet" : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  return [out(`${stem}.${bookType}`, new Blob([data], { type: mime }))];
}

async function convertCad(file, t, progress) {
  const dxf = await lib.dxf();
  const stem = stemOf(file.name);
  progress(0.2, "Leggo il disegno…");
  let svg;
  try {
    svg = new dxf.Helper(await file.text()).toSVG();
  } catch {
    throw new Error("Questo DXF non si apre: potrebbe essere danneggiato o in una versione non supportata.");
  }
  // linee ben visibili e sfondo bianco: i colori «bianco» di AutoCAD diventano neri
  svg = svg.replace(/stroke="rgb\(255,\s*255,\s*255\)"/g, 'stroke="rgb(0,0,0)"').replace(/fill="rgb\(255,\s*255,\s*255\)"/g, 'fill="rgb(0,0,0)"');
  const vb = (svg.match(/viewBox="([^"]+)"/) || [])[1];
  if (!vb || vb.split(/[\s,]+/).map(Number).slice(2).some((x) => !(x > 0))) throw new Error("Il disegno è vuoto: non c'è niente da convertire.");
  if (t === "cad-svg") return [out(stem + ".svg", new Blob([svg], { type: "image/svg+xml" }))];
  progress(0.5, "Disegno…");
  const [, , vw, vh] = vb.split(/[\s,]+/).map(Number);
  const W = 3000, H = Math.max(1, Math.round((W * vh) / vw));
  const sized = svg.replace(/<svg([^>]*)>/, (m, a) => `<svg${a.replace(/\s(width|height)="[^"]*"/g, "")} width="${W}" height="${H}">`);
  const d = await decodeImage(new File([sized], "disegno.svg", { type: "image/svg+xml" }));
  d.w = W; d.h = H;
  const c = drawCanvas(d, 0, "#fff");
  if (t === "cad-png") return [out(stem + ".png", await canvasBlob(c, "image/png"))];
  const { PDFDocument } = await lib.pdflib();
  const pdf = await PDFDocument.create();
  const png = await pdf.embedPng(await (await canvasBlob(c, "image/png")).arrayBuffer());
  let [pw, ph] = [841.89, 1190.55];               // A3
  if (W > H) [pw, ph] = [ph, pw];
  const m = 28.35, k = Math.min((pw - 2 * m) / W, (ph - 2 * m) / H);
  pdf.addPage([pw, ph]).drawImage(png, { x: (pw - W * k) / 2, y: (ph - H * k) / 2, width: W * k, height: H * k });
  return [out(stem + ".pdf", new Blob([await pdf.save()], { type: "application/pdf" }))];
}

async function extractZip(file, progress) {
  const JSZip = await lib.jszip();
  progress(0.1, "Apro l'archivio…");
  let zip;
  try { zip = await JSZip.loadAsync(file); }
  catch { throw new Error("Questo archivio non si apre: potrebbe essere danneggiato o protetto da password."); }
  const entries = Object.values(zip.files).filter((f) => !f.dir && !f.name.startsWith("__MACOSX/") && !/(^|\/)\.DS_Store$/.test(f.name));
  if (!entries.length) throw new Error("L'archivio è vuoto.");
  const res = [];
  for (let i = 0; i < entries.length; i++) {
    progress(i / entries.length, `Estraggo ${entries[i].name}…`);
    try { res.push(out(entries[i].name, await entries[i].async("blob"))); }
    catch { throw new Error("Non riesco a estrarre i file: l'archivio potrebbe essere protetto da password."); }
  }
  return res;
}
async function makeZip(files, progress) {
  const JSZip = await lib.jszip();
  const zip = new JSZip();
  for (const f of files) zip.file(f.webkitRelativePath || f.name, f);
  const blob = await zip.generateAsync({ type: "blob", compression: "DEFLATE", compressionOptions: { level: 6 } },
    (m) => progress(m.percent / 100, `Comprimo… ${Math.round(m.percent)}%`));
  return [out((files.length === 1 ? stemOf(files[0].name) : "archivio") + ".zip", blob)];
}
async function applePreview(file, progress) {
  const JSZip = await lib.jszip();
  progress(0.2, "Apro il documento…");
  let zip;
  try { zip = await JSZip.loadAsync(file); }
  catch { throw new Error("Questo documento Apple non si apre. Se è una cartella (versioni vecchie di Pages), comprimila in ZIP e riprova."); }
  const stem = stemOf(file.name);
  const pdf = zip.file("QuickLook/Preview.pdf");
  if (pdf) return [out(stem + "_anteprima.pdf", new Blob([await pdf.async("arraybuffer")], { type: "application/pdf" }))];
  const jpg = zip.file("preview.jpg") || zip.file("QuickLook/Thumbnail.jpg") || zip.file("preview-web.jpg");
  if (jpg) return [out(stem + "_anteprima.jpg", new Blob([await jpg.async("arraybuffer")], { type: "image/jpeg" }))];
  throw new Error("Il documento non contiene un'anteprima. Da Pages, Keynote o Numbers scegli File → Esporta per convertirlo tutto.");
}

// esegue una conversione su tutti i file scelti; ogni file può riuscire o fallire da solo
async function runConversion(files, t, progress) {
  const results = [], errors = [];
  if (t === "img-pdf-one") return { results: await imagesToOnePdf(files, progress), errors };
  if (t === "pdf-merge") return { results: await mergePdfs(files, progress), errors };
  if (t === "zip-make") return { results: await makeZip(files, progress), errors };
  for (let i = 0; i < files.length; i++) {
    const f = files[i];
    const p = (frac, msg) => progress((i + Math.max(0, Math.min(1, frac))) / files.length, (files.length > 1 ? `${f.name}: ` : "") + msg);
    try {
      let r;
      if (t.startsWith("img-")) r = await convertImage(f, t, p);
      else if (t.startsWith("v-") || t.startsWith("a-")) r = await convertMedia(f, t, p);
      else if (t.startsWith("pdf-")) r = await convertPdf(f, t, p);
      else if (t.startsWith("doc-")) r = await convertWord(f, t, p);
      else if (t.startsWith("sh-")) r = await convertSheet(f, t, p);
      else if (t.startsWith("cad-")) r = await convertCad(f, t, p);
      else if (t === "zip-extract") r = await extractZip(f, p);
      else if (t === "apple-preview") r = await applePreview(f, p);
      results.push(...r);
    } catch (e) {
      console.error(e);
      errors.push({ name: f.name, message: (e && e.message) || String(e) });
    }
  }
  return { results, errors };
}

// ------------------------------------------------------------------ interfaccia
let current = { files: [], group: null };
let lastResults = [];
const urls = [];

function show(page) {
  for (const p of ["file", "scegli", "fatto"]) $("#pag-" + p).hidden = p !== page;
  const step = { file: 1, scegli: 2, fatto: 3 }[page];
  document.querySelectorAll(".steps li").forEach((li) => li.classList.toggle("on", Number(li.dataset.step) <= step));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function card(t) {
  const b = document.createElement("button");
  b.className = "card";
  b.innerHTML = `<span class="tag"></span><span class="t"></span><span class="d"></span>`;
  b.querySelector(".tag").textContent = t.tag !== t.title ? t.tag : "";
  b.querySelector(".t").textContent = t.title;
  b.querySelector(".d").textContent = t.desc;
  b.addEventListener("click", () => start(t));
  return b;
}

function loadFiles(list) {
  const files = [...list].filter((f) => f.size > 0 || groupOf(f));
  if (!files.length) return;
  const groups = new Set(files.map(groupOf));
  const group = groups.size === 1 ? [...groups][0] : null;
  current = { files, group };

  const def = GROUPS[group];
  $("#file-icon").textContent = def ? def.icon : "📁";
  $("#file-name").textContent = files.length === 1 ? files[0].name : `${files.length} file`;
  const total = files.reduce((s, f) => s + f.size, 0);
  $("#file-info").textContent = (def ? def.label : files.length > 1 ? "File di tipo diverso" : "Tipo di file sconosciuto") + " · " + humanSize(total);

  const avviso = $("#avviso");
  avviso.hidden = true;
  let reason = null;
  if (!group) {
    const e = extOf(files[0].name);
    if (files.length === 1) reason = NOT_IN_BROWSER[e] || "Questo tipo di file non si può convertire nel browser.";
    else reason = "Hai scelto file di tipo diverso: posso solo metterli in un archivio ZIP. Per convertirli, sceglili un tipo alla volta.";
  }
  if (reason) { avviso.textContent = reason; avviso.hidden = false; }

  const { rec, more } = targetsFor(group, files);
  const boxRec = $("#consigliate"), boxMore = $("#altri");
  boxRec.replaceChildren(...rec.map(card));
  boxMore.replaceChildren(...more.map(card));
  $("#titolo-consigliate").hidden = rec.length === 0;
  boxMore.hidden = rec.length > 0;
  $("#btn-altri").hidden = rec.length === 0 || more.length === 0;
  $("#btn-altri").textContent = "Altri formati ▾";
  show("scegli");
}

function progress(frac, msg) {
  $("#barra").style.width = `${Math.round(Math.max(0, Math.min(1, frac)) * 100)}%`;
  if (msg) $("#dettaglio").textContent = msg;
}

async function start(t) {
  show("fatto");
  $("#lavoro").hidden = false;
  $("#risultati").hidden = true;
  $("#stato").textContent = `Converto in ${t.title}…`;
  progress(0, "");
  urls.splice(0).forEach((u) => URL.revokeObjectURL(u));
  let results = [], errors = [];
  try {
    ({ results, errors } = await runConversion(current.files, t.id, progress));
  } catch (e) {
    console.error(e);
    errors = [{ name: current.files.length === 1 ? current.files[0].name : `${current.files.length} file`, message: (e && e.message) || String(e) }];
  }
  lastResults = results;
  showResults(results, errors);
}

function showResults(results, errors) {
  $("#lavoro").hidden = true;
  $("#risultati").hidden = false;
  $("#titolo-risultati").textContent = !results.length ? "La conversione non è riuscita" : errors.length ? "Fatto, ma con qualche problema" : "Fatto!";
  const items = [];
  for (const r of results) {
    const li = document.createElement("li");
    if (r.print) {
      li.innerHTML = `<span class="nome"></span><button class="btn piccolo">Salva come PDF</button>`;
      li.querySelector(".nome").textContent = r.name + " — nella finestra di stampa scegli «Salva come PDF»";
      li.querySelector("button").addEventListener("click", () => printHtml(r.print));
    } else {
      const url = URL.createObjectURL(r.blob);
      urls.push(url);
      li.innerHTML = `<span class="nome"></span><span class="peso"></span><a class="btn piccolo">Scarica</a>`;
      if (r.blob.type.startsWith("image/") && results.length <= 60) {
        const img = document.createElement("img");
        img.className = "anteprima"; img.alt = ""; img.src = url;
        li.prepend(img);
      }
      li.querySelector(".nome").textContent = r.name;
      li.querySelector(".peso").textContent = humanSize(r.blob.size);
      const a = li.querySelector("a");
      a.href = url;
      a.download = r.name.split("/").pop();
    }
    items.push(li);
  }
  for (const e of errors) {
    const li = document.createElement("li");
    li.innerHTML = `<span class="nome"></span><span class="errore"></span>`;
    li.querySelector(".nome").textContent = e.name;
    li.querySelector(".errore").textContent = e.message;
    items.push(li);
  }
  $("#lista").replaceChildren(...items);
  $("#btn-zip").hidden = results.filter((r) => r.blob).length < 2;
  // un solo file: lo scarico subito
  if (results.length === 1 && results[0].blob && !errors.length) $("#lista a")?.click();
}

function printHtml(html) {
  const frame = $("#stampa");
  frame.onload = () => {
    frame.onload = null;
    setTimeout(() => frame.contentWindow.print(), 200);
  };
  frame.srcdoc = html;
}

async function downloadAllZip() {
  const btn = $("#btn-zip");
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = "Preparo lo ZIP…";
  try {
    const JSZip = await lib.jszip();
    const zip = new JSZip();
    for (const r of lastResults) if (r.blob) zip.file(r.name, r.blob);
    const blob = await zip.generateAsync({ type: "blob" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (current.files.length === 1 ? stemOf(current.files[0].name) : "convertiti") + ".zip";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 60000);
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}

// eventi
const drop = $("#drop"), input = $("#input");
input.addEventListener("change", () => { loadFiles(input.files); input.value = ""; });
drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
["dragenter", "dragover"].forEach((ev) => document.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => document.addEventListener(ev, (e) => { e.preventDefault(); if (ev === "drop" || !e.relatedTarget) drop.classList.remove("over"); }));
document.addEventListener("drop", (e) => { if (e.dataTransfer?.files?.length) loadFiles(e.dataTransfer.files); });
document.addEventListener("paste", (e) => { if (e.clipboardData?.files?.length) loadFiles(e.clipboardData.files); });
$("#btn-altri").addEventListener("click", () => {
  const box = $("#altri");
  box.hidden = !box.hidden;
  $("#btn-altri").textContent = box.hidden ? "Altri formati ▾" : "Meno formati ▴";
});
$("#btn-zip").addEventListener("click", downloadAllZip);
document.querySelectorAll("[data-azione]").forEach((b) => b.addEventListener("click", () => {
  if (b.dataset.azione === "indietro" && current.files.length) loadFiles(current.files);
  else { current = { files: [], group: null }; show("file"); }
}));

// per i test automatici
window.ConvertiTutto = { runConversion, targetsFor, groupOf };
