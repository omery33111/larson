// Builds every raster the site needs, from the one SVG that `render-mark.mjs` produced.
//
//   node tools/render-mark.mjs && node tools/make-icons.mjs
//
// **Rasterised by the browser that is already on the machine**, driven headless. Nothing is
// installed for this: Chrome renders the same vector the site renders, so the icon in the tab
// and the figure in the navbar cannot drift apart.

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { decode, encode, resize } from "./png.mjs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const publicDir = join(root, "public");
const work = join(tmpdir(), "larson-icons");

const CHROME = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].find(existsSync);

if (!CHROME) throw new Error("No Chrome or Edge found to rasterise with.");

mkdirSync(publicDir, { recursive: true });
rmSync(work, { recursive: true, force: true });
mkdirSync(work, { recursive: true });

const GROUND = "#12151b";


// ------------------------- THE RASTERISER -------------------------
// A page of its own rather than the SVG straight: an image stretched to the viewport scales
// exactly to the size asked for, where the bare file would render at its own 200px and leave
// the rest of the frame empty.

function shot(html, width, height, outFile, { transparent = false, dir = publicDir } = {}) {
  const page = join(work, `page-${outFile}.html`);
  writeFileSync(page, html, "utf8");

  execFileSync(CHROME, [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--force-device-scale-factor=1",
    // Chrome paints white behind a page unless told otherwise, and white behind a figure
    // meant to float is indistinguishable from a white tile until it lands on a dark surface.
    ...(transparent ? ["--default-background-color=00000000"] : []),
    // Its own profile, so this never collides with the browser the user has open.
    `--user-data-dir=${join(work, "profile")}`,
    // Long enough for the webfont on the share card. Everything else is local and instant.
    "--virtual-time-budget=8000",
    `--window-size=${width},${height}`,
    `--screenshot=${join(dir, outFile)}`,
    `file:///${page.replace(/\\/g, "/")}`,
  ], { stdio: "ignore" });

  const bytes = readFileSync(join(dir, outFile)).length;
  console.log(`  ${outFile.padEnd(24)} ${width}x${height}  ${(bytes / 1024).toFixed(1)} KB`);
}

const markPage = (inset = 0) => `<!doctype html><meta charset="utf-8">
<style>
  html, body { margin: 0; height: 100%; background: ${GROUND}; }
  img { position: absolute; inset: ${inset}%; width: ${100 - inset * 2}%; height: ${100 - inset * 2}%; }
</style>
<img src="file:///${join(publicDir, "favicon.svg").replace(/\\/g, "/")}">`;

// The consent tile: the ground, rounded, and nothing outside it.
//
// **Rounded is safe whichever way Google draws it.** If their dialog masks the logo to a
// circle the corners are cropped away and the radius costs nothing; if it shows the file as
// it is, a hard-cornered square reads as raw beside their own rounded surfaces. The corners
// themselves are transparent rather than white, so the tile keeps its shape on a dark dialog
// as well as a light one.
const consentPage = () => `<!doctype html><meta charset="utf-8">
<style>
  html, body { margin: 0; height: 100%; background: transparent; }
  .tile { position: absolute; inset: 0; background: ${GROUND}; border-radius: 22%; overflow: hidden; }
  img { position: absolute; inset: 0; width: 100%; height: 100%; }
</style>
<div class="tile"><img src="file:///${join(publicDir, "mark-transparent.svg").replace(/\\/g, "/")}"></div>`;

// The same page with no ground, for the one icon that must float rather than sit on a tile.
const barePage = () => `<!doctype html><meta charset="utf-8">
<style>
  html, body { margin: 0; height: 100%; background: transparent; }
  img { position: absolute; inset: 0; width: 100%; height: 100%; }
</style>
<img src="file:///${join(publicDir, "mark-transparent.svg").replace(/\\/g, "/")}">`;


// ------------------------- THE SIZES, AND WHY EACH ONE -------------------------
// **Everything small is reduced rather than rendered.** Chrome will not open a window
// narrower than about 500px, so a 32px screenshot comes back as a 32px crop of a 500px page
// instead of the figure at 32px. The full size is rendered once and `resize` does the rest,
// which is also the better picture: a real area filter keeps the hair as tone where a
// screenshot at that size would keep every fortieth pixel of it and drop the others.
console.log("icons:");

shot(markPage(), 512, 512, "icon-512.png");

// Maskable: Android crops this to whatever shape the launcher uses, so the figure is pulled
// in to sit inside the safe circle rather than being cut at the ears.
shot(markPage(18), 512, 512, "icon-maskable-512.png");

const master = decode(readFileSync(join(publicDir, "icon-512.png")));

function reduce(size, name, from = master) {
  const bytes = encode(resize(from, size));
  writeFileSync(join(publicDir, name), bytes);
  console.log(`  ${name.padEnd(24)} ${size}x${size}  ${(bytes.length / 1024).toFixed(1)} KB`);
}

// The tab, at the three sizes Windows and the browsers actually ask for.
reduce(16, "favicon-16.png");
reduce(32, "favicon-32.png");
reduce(48, "favicon-48.png");

// iOS home screen. It has no transparency of its own, so the ground has to be in the file.
reduce(180, "apple-touch-icon.png");

// The smaller of the two the manifest asks for by name.
reduce(192, "icon-192.png");

// Google's OAuth consent screen: 120x120 square, shown beside the app name when somebody signs
// in with Google. **It keeps the ground, and that was decided rather than inherited.** A
// transparent mark has to hold up on whatever surface Google paints behind it, and that
// surface is white for some users and dark for others; the tile looks identical in both. It
// is also the same image the trader already met in the tab and the navbar, instead of a
// second version of the figure to keep in step. Rendered at 512 and reduced, because Chrome
// will not open a window small enough to screenshot 120 directly.
shot(consentPage(), 512, 512, "consent-master.png", { transparent: true, dir: work });
reduce(120, "google-consent-120.png", decode(readFileSync(join(work, "consent-master.png"))));


// ------------------------- FAVICON.ICO -------------------------
// Old browsers and Windows itself still ask for /favicon.ico by name. PNG payloads inside an
// ICO are read by everything current, so the three files above are simply carried in.

const entries = [16, 32, 48].map((size) => ({
  size,
  data: readFileSync(join(publicDir, `favicon-${size}.png`)),
}));

const header = Buffer.alloc(6 + entries.length * 16);
header.writeUInt16LE(0, 0);
header.writeUInt16LE(1, 2);
header.writeUInt16LE(entries.length, 4);

let offset = header.length;

entries.forEach((entry, i) => {
  const at = 6 + i * 16;
  header.writeUInt8(entry.size, at);
  header.writeUInt8(entry.size, at + 1);
  header.writeUInt8(0, at + 2);            // palette colours: none, this is truecolour
  header.writeUInt8(0, at + 3);            // reserved
  header.writeUInt16LE(1, at + 4);         // colour planes
  header.writeUInt16LE(32, at + 6);        // bits per pixel
  header.writeUInt32LE(entry.data.length, at + 8);
  header.writeUInt32LE(offset, at + 12);
  offset += entry.data.length;
});

const ico = Buffer.concat([header, ...entries.map((e) => e.data)]);
writeFileSync(join(publicDir, "favicon.ico"), ico);
console.log(`  ${"favicon.ico".padEnd(24)} 16/32/48   ${(ico.length / 1024).toFixed(1)} KB`);


// ------------------------- THE SHARE CARD -------------------------
// What WhatsApp, Twitter and LinkedIn draw when somebody pastes the link. Today they draw an
// empty white box.
//
// The words are drawn here rather than left to the meta tags alone, because the image is the
// part that survives being screenshotted and forwarded.

const card = `<!doctype html><html lang="he" dir="rtl"><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;700&display=swap">
<style>
  html, body { margin: 0; height: 100%; }

  body {
    background: radial-gradient(120% 140% at 50% 0%, #1a1f28 0%, #0f1115 62%);
    color: #e8e8e8;
    font-family: "Rubik", system-ui, "Segoe UI", sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 34px;
  }

  /* The same thin gold line the product puts at the top of a card. */
  .rule {
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, transparent, #f0b90b 22%, #ffd34d 50%, #f0b90b 78%, transparent);
  }

  .mark {
    width: 240px;
    height: 240px;
    border-radius: 50%;
    /* The aura the chat gives him, so he reads as lit rather than pasted on. */
    box-shadow: 0 0 90px 20px rgba(240, 185, 11, .13);
  }

  .word {
    font-size: 78px;
    font-weight: 700;
    letter-spacing: .01em;
    line-height: 1;
    direction: ltr;
  }

  .tagline {
    font-size: 31px;
    font-weight: 400;
    color: #9aa0ab;
    margin-top: -14px;
  }
</style>
<div class="rule"></div>
<img class="mark" src="file:///${join(publicDir, "favicon.svg").replace(/\\/g, "/")}">
<div class="word">Larson</div>
<div class="tagline">המנטור שמבין את המסחר שלך</div>
</html>`;

console.log("share card:");
shot(card, 1200, 630, "og.png");

rmSync(work, { recursive: true, force: true });
