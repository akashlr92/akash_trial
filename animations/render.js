#!/usr/bin/env node
// Render a code-animated scene to MP4, frame by frame.
//
//   node render.js <scene-folder> <output.mp4> [--fps 30] [--audio file.wav] [--from 0] [--to 20] [--still 9.5]
//
// The scene's index.html must define window.renderFrame(t) (returns a Promise),
// window.DURATION (seconds) and set window.ready = true when loaded.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('playwright');

const args = process.argv.slice(2);
const opt = (name, def) => { const i = args.indexOf('--' + name); return i >= 0 ? args[i + 1] : def; };
const [sceneDir, output] = args;
if (!sceneDir || !output) { console.error('usage: node render.js <scene-folder> <output> [--fps 30] [--audio a.wav] [--from s] [--to s] [--still s]'); process.exit(1); }
const fps = +opt('fps', 30), audio = opt('audio'), still = opt('still');
const root = __dirname;
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.jpg': 'image/jpeg', '.json': 'application/json', '.woff2': 'font/woff2', '.ttf': 'font/ttf' };

(async () => {
  const server = http.createServer((req, res) => {
    const file = path.join(root, decodeURIComponent(req.url.split('?')[0]));
    if (!file.startsWith(root) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  }).listen(0);
  const port = server.address().port;

  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => { console.error('Page error:', e.message); process.exit(1); });
  const rel = path.relative(root, path.resolve(sceneDir)).split(path.sep).join('/');
  await page.goto(`http://127.0.0.1:${port}/${rel}/index.html`);
  await page.waitForFunction('window.ready === true', null, { timeout: 60000 });
  const duration = await page.evaluate('window.DURATION');

  if (still !== undefined) {           // single preview frame
    await page.evaluate(t => window.renderFrame(t), +still);
    await page.screenshot({ path: output });
    console.log('Saved', output);
  } else {
    const from = +opt('from', 0), to = +opt('to', duration);
    const ffArgs = ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-'];
    if (audio) ffArgs.push('-i', audio, '-c:a', 'aac', '-b:a', '192k', '-shortest');
    ffArgs.push('-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', output);
    const ff = spawn('ffmpeg', ffArgs, { stdio: ['pipe', 'inherit', 'inherit'] });
    const first = Math.round(from * fps), last = Math.round(to * fps), t0 = Date.now();
    for (let f = first; f < last; f++) {
      await page.evaluate(t => window.renderFrame(t), f / fps);
      const buf = await page.screenshot({ type: 'jpeg', quality: 96 });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if ((f - first) % 30 === 0) console.log(`frame ${f - first}/${last - first}  (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    console.log('Saved', output);
  }
  await browser.close(); server.close();
})();
