// A PNG reader, writer and downscaler, in the standard library.
//
// **Why this exists at all.** Chrome refuses to open a window narrower than about 500px, so
// asking it for a 32px screenshot gives back a 32px crop of a 500px page rather than the
// figure at 32px. Everything small is therefore rendered once at 512 and reduced here.
//
// Scope is deliberately tiny: 8-bit, non-interlaced, truecolour with or without alpha, which
// is what Chrome writes. Anything else is refused loudly rather than half-read.

import { deflateSync, inflateSync } from "node:zlib";

const SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);


// ------------------------- READ -------------------------

export function decode(buffer) {
  if (!buffer.subarray(0, 8).equals(SIGNATURE)) throw new Error("Not a PNG.");

  let width = 0, height = 0, depth = 0, colour = 0;
  const parts = [];

  for (let at = 8; at < buffer.length;) {
    const length = buffer.readUInt32BE(at);
    const type = buffer.toString("ascii", at + 4, at + 8);
    const body = buffer.subarray(at + 8, at + 8 + length);

    if (type === "IHDR") {
      width = body.readUInt32BE(0);
      height = body.readUInt32BE(4);
      depth = body[8];
      colour = body[9];
      if (depth !== 8 || (colour !== 2 && colour !== 6) || body[12] !== 0) {
        throw new Error(`Unsupported PNG: depth ${depth}, colour ${colour}, interlace ${body[12]}.`);
      }
    } else if (type === "IDAT") {
      parts.push(body);
    } else if (type === "IEND") {
      break;
    }

    at += 12 + length;
  }

  const channels = colour === 6 ? 4 : 3;
  const stride = width * channels;
  const raw = inflateSync(Buffer.concat(parts));
  const out = Buffer.alloc(height * stride);

  // Undo the per-row filters. Each row names its own, and every one of them refers to the
  // pixel to the left and the row above, which is why this cannot be done in parallel.
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)];
    const from = y * (stride + 1) + 1;
    const to = y * stride;

    for (let x = 0; x < stride; x++) {
      const value = raw[from + x];
      const left = x >= channels ? out[to + x - channels] : 0;
      const up = y > 0 ? out[to - stride + x] : 0;
      const upLeft = x >= channels && y > 0 ? out[to - stride + x - channels] : 0;

      let add = 0;
      if (filter === 1) add = left;
      else if (filter === 2) add = up;
      else if (filter === 3) add = (left + up) >> 1;
      else if (filter === 4) {
        const p = left + up - upLeft;
        const dl = Math.abs(p - left), du = Math.abs(p - up), dul = Math.abs(p - upLeft);
        add = dl <= du && dl <= dul ? left : du <= dul ? up : upLeft;
      } else if (filter !== 0) {
        throw new Error(`Unknown PNG row filter ${filter}.`);
      }

      out[to + x] = (value + add) & 0xff;
    }
  }

  return { width, height, channels, data: out };
}


// ------------------------- WRITE -------------------------

function chunk(type, body) {
  const head = Buffer.alloc(8);
  head.writeUInt32BE(body.length, 0);
  head.write(type, 4, "ascii");

  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([head.subarray(4), body])), 0);

  return Buffer.concat([head, body, crc]);
}

const CRC_TABLE = (() => {
  const table = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c;
  }
  return table;
})();

function crc32(buffer) {
  let c = 0xffffffff;
  for (const byte of buffer) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

export function encode({ width, height, channels, data }) {
  const stride = width * channels;
  const raw = Buffer.alloc(height * (stride + 1));

  // Filter 0 throughout. These are icons of a few hundred pixels; choosing a filter per row
  // would save bytes nobody is counting and add a page of code that could be wrong.
  for (let y = 0; y < height; y++) {
    raw[y * (stride + 1)] = 0;
    data.copy(raw, y * (stride + 1) + 1, y * stride, (y + 1) * stride);
  }

  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = channels === 4 ? 6 : 2;

  return Buffer.concat([
    SIGNATURE,
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}


// ------------------------- DOWNSCALE -------------------------
// Area averaging, with the edge pixels weighted by how much of them the target pixel actually
// covers. **Nearest-neighbour is what makes a shrunken icon look broken**: at 32px it would
// keep every fortieth pixel of the hair and throw the rest away, so a strand either survives
// whole or vanishes, and the mark reads as speckle.

export function resize(image, size) {
  const { width, height, channels, data } = image;
  const out = Buffer.alloc(size * size * channels);
  const scaleX = width / size;
  const scaleY = height / size;

  for (let y = 0; y < size; y++) {
    const y0 = y * scaleY, y1 = (y + 1) * scaleY;

    for (let x = 0; x < size; x++) {
      const x0 = x * scaleX, x1 = (x + 1) * scaleX;
      const sums = new Float64Array(channels);
      let weight = 0;

      for (let sy = Math.floor(y0); sy < Math.ceil(y1); sy++) {
        const wy = Math.min(sy + 1, y1) - Math.max(sy, y0);

        for (let sx = Math.floor(x0); sx < Math.ceil(x1); sx++) {
          const w = wy * (Math.min(sx + 1, x1) - Math.max(sx, x0));
          const at = (sy * width + sx) * channels;

          for (let c = 0; c < channels; c++) sums[c] += data[at + c] * w;
          weight += w;
        }
      }

      const at = (y * size + x) * channels;
      for (let c = 0; c < channels; c++) out[at + c] = Math.round(sums[c] / weight);
    }
  }

  return { width: size, height: size, channels, data: out };
}
