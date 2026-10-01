// Renders LarsonMark to a standalone SVG file.
//
// **The figure is never redrawn by hand.** `LarsonMark.tsx` is the one place the character
// lives, so the icon is produced by rendering that component rather than by copying its
// shapes into a second file that would drift the first time the hair changes.
//
//   node tools/render-mark.mjs
//
// esbuild and react-dom/server are already here as part of Vite and React, so this costs
// no dependency of its own.

import { build } from "esbuild";
import { writeFileSync, unlinkSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");

const ENTRY = `
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import LarsonMark from "../src/features/larson/LarsonMark.tsx";

export const markup = renderToStaticMarkup(React.createElement(LarsonMark, { state: "idle" }));
`;

const entryFile = join(here, ".entry.tsx");
const bundleFile = join(here, ".bundle.mjs");

writeFileSync(entryFile, ENTRY, "utf8");

await build({
  entryPoints: [entryFile],
  outfile: bundleFile,
  bundle: true,
  format: "esm",
  platform: "node",
  jsx: "automatic",
  // React resolves from node_modules at run time; only the component and its data are bundled.
  external: ["react", "react-dom", "react/jsx-runtime"],
  // The component imports no stylesheet today. If one is ever added, it must not stop this.
  loader: { ".css": "empty", ".png": "empty" },
  logLevel: "silent",
});

const { markup } = await import(pathToFileURL(bundleFile).href);

unlinkSync(entryFile);
unlinkSync(bundleFile);

// ------------------------- IDS -------------------------
// `useId` gives every instance its own gradient ids, which is what stops several marks on one
// page from all pointing at the first one's gradients. In a file of its own there is exactly
// one instance, and React's generated ids carry punctuation that has no business in an asset
// meant to survive being pasted anywhere. They are renamed, references and all.
const ids = new Map();
let n = 0;

let svg = markup.replace(/id="([^"]+)"/g, (_, id) => {
  if (!ids.has(id)) ids.set(id, "lm" + (n += 1));
  return `id="${ids.get(id)}"`;
});

for (const [from, to] of ids) {
  svg = svg.split(`url(#${from})`).join(`url(#${to})`);
  svg = svg.split(`href="#${from}"`).join(`href="#${to}"`);
  svg = svg.split(`xlink:href="#${from}"`).join(`xlink:href="#${to}"`);
}

// A file has to declare the namespace that a React tree inherited from the document, and an
// asset with no intrinsic size is scaled differently by everything that opens it.
if (!svg.includes("xmlns=")) {
  svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"');
}
svg = svg.replace("<svg", '<svg width="200" height="200"');

mkdirSync(join(root, "public"), { recursive: true });

// **Two files, because the figure needs a ground in some places and must not have one in
// others.** Google's consent dialog is white and draws the logo itself, so the dark ground
// below reads there as a black tile rather than as a mark. Rendered bare on white it is the
// dark contour around each strand that carries it - checked by rendering both side by side
// rather than assumed, because the pale end of the mane looked like it would disappear.
writeFileSync(join(root, "public", "mark-transparent.svg"), svg + "\n", "utf8");

// The ground the product puts him on. Without it the steel head sits on whatever colour the
// browser paints behind a tab, which is the one place the figure was never designed for.
svg = svg.replace(/(<svg[^>]*>)/, '$1<rect width="200" height="200" fill="#12151b"/>');
writeFileSync(join(root, "public", "favicon.svg"), svg + "\n", "utf8");

console.log("public/favicon.svg written,", svg.length, "chars");
