// Generates assets/icon.png — a tiny tray icon in the peacock palette.
// Dependency-free PNG (RGBA) encoder using Node's zlib. Run: npm run genicon.

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const SIZE = 32;

// CRC32 (PNG spec).
const crcTable = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = crcTable[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const typeBuf = Buffer.from(type, 'ascii');
  const body = Buffer.concat([typeBuf, data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body), 0);
  return Buffer.concat([len, body, crc]);
}

// Build RGBA pixels: a teal disc, a gold ring, an indigo outline, transparent
// elsewhere — a small nod to the pet's palette.
const raw = Buffer.alloc(SIZE * (1 + SIZE * 4));
const cx = (SIZE - 1) / 2;
const cy = (SIZE - 1) / 2;
for (let y = 0; y < SIZE; y++) {
  const rowStart = y * (1 + SIZE * 4);
  raw[rowStart] = 0; // PNG filter type: none
  for (let x = 0; x < SIZE; x++) {
    const d = Math.hypot(x - cx, y - cy);
    let r = 0;
    let g = 0;
    let b = 0;
    let a = 0;
    if (d < 9) {
      [r, g, b, a] = [0x14, 0xb8, 0xa6, 255]; // teal
    } else if (d < 12) {
      [r, g, b, a] = [0xf5, 0xb3, 0x01, 255]; // gold
    } else if (d < 13.5) {
      [r, g, b, a] = [0x31, 0x2e, 0x81, 255]; // indigo
    }
    const o = rowStart + 1 + x * 4;
    raw[o] = r;
    raw[o + 1] = g;
    raw[o + 2] = b;
    raw[o + 3] = a;
  }
}

const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const ihdr = Buffer.alloc(13);
ihdr.writeUInt32BE(SIZE, 0);
ihdr.writeUInt32BE(SIZE, 4);
ihdr[8] = 8; // bit depth
ihdr[9] = 6; // color type: RGBA
ihdr[10] = 0; // compression
ihdr[11] = 0; // filter
ihdr[12] = 0; // interlace

const png = Buffer.concat([
  sig,
  chunk('IHDR', ihdr),
  chunk('IDAT', zlib.deflateSync(raw)),
  chunk('IEND', Buffer.alloc(0)),
]);

const outDir = path.join(__dirname, 'assets');
fs.mkdirSync(outDir, { recursive: true });
const outPath = path.join(outDir, 'icon.png');
fs.writeFileSync(outPath, png);
console.log(`wrote ${outPath} (${png.length} bytes)`);
