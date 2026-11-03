"""Render the motion clips (slides-src/m7-*, m8-*, m9-*.html) to video, plus a matching still.

    python3 slides-src/render_motion.py              # every clip
    python3 slides-src/render_motion.py m7-b4        # only clips whose name starts with these prefixes
    python3 slides-src/render_motion.py --still m7-b2  # stills only (fast)

Each clip is a 1920x1080 page whose CSS animations are positioned by motion.js::__seek(t); the clip length is the
page's <body data-duration>. Frames are captured one by one at 30 fps (deterministic: no wall clock, no dropped
frames, text stays sharp), then encoded twice:
  motion/<name>.webm  VP9, with the ffmpeg build Playwright ships (~/Library/Caches/ms-playwright/ffmpeg-*)
  motion/<name>.mp4   H.264, with AVFoundation via slides-src/jpegs2mp4.swift (macOS only; skipped elsewhere)
The still is the clip's last frame at device scale 2: scenes/<name>.png (3840x2160), like the other frames.
Every scenes-data/*.json is injected as window.DATA["<stem>"], as in render.py. Network is blocked.
"""
import glob
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright
from render import CHECK

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
CLIPS = ROOT / 'motion'
STILLS = ROOT / 'scenes'
DATA_DIR = ROOT / 'scenes-data'
BUILD = ROOT / '.motion-build'
FPS = 30
# Extra stills cut from a clip at a given second (name -> (clip, seconds)). The thumbnail is beat 1 at 11.6 s (v10 timing):
# both wrong figures beside the 354 passed checks, before "Neither was right" strikes them.
EXTRA_STILLS = {'m9-thumbnail': ('m9-b1-hook', 11.6)}


def ffmpeg():
    found = sorted(glob.glob(str(pathlib.Path.home() / 'Library/Caches/ms-playwright/ffmpeg-*/ffmpeg-*')))
    return found[-1] if found else shutil.which('ffmpeg')


def mp4_encoder():
    if sys.platform != 'darwin' or not shutil.which('swiftc'):
        return None
    exe = BUILD / 'jpegs2mp4'
    src = HERE / 'jpegs2mp4.swift'
    if not exe.exists() or exe.stat().st_mtime < src.stat().st_mtime:
        BUILD.mkdir(exist_ok=True)
        subprocess.run(['swiftc', '-O', str(src), '-o', str(exe)], check=True)
    return exe


def open_page(browser, path, data, scale):
    pg = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=scale)
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
    pg.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file://') else r.abort())
    pg.add_init_script(f'window.DATA = {json.dumps(data)};')
    pg.goto(path.as_uri() + '?render')
    pg.evaluate('document.fonts.ready')
    pg.wait_for_timeout(200)
    return pg, errs


def main(argv):
    still_only = '--still' in argv
    argv = [a for a in argv if a != '--still']
    data = {p.stem: json.loads(p.read_text()) for p in sorted(DATA_DIR.glob('*.json'))}
    pages = sorted([*HERE.glob('m[789]-*.html'), *HERE.glob('m10-*.html')])
    if argv:
        pages = [p for p in pages if any(p.stem.startswith(a) for a in argv)]
    if not pages:
        sys.exit(f'no clip matches {argv}')
    CLIPS.mkdir(exist_ok=True)
    ff, mp4 = ffmpeg(), (None if still_only else mp4_encoder())
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for path in pages:
            name = path.stem
            # the still: last frame at 2x
            pg, errs = open_page(browser, path, data, 2)
            dur = pg.evaluate('window.DURATION')
            for extra, (clip, at) in EXTRA_STILLS.items():
                if clip == name:
                    pg.evaluate(f'window.__seek({at})')
                    pg.screenshot(path=str(STILLS / f'{extra}.png'))
            pg.evaluate(f'window.__seek({dur})')
            problems = pg.evaluate(CHECK)
            pg.screenshot(path=str(STILLS / f'{name}.png'))
            pg.close()
            line = f'{name}: {dur:g}s errors={errs or "none"} layout={problems or "ok"}'
            if still_only:
                print(line)
                continue
            # the clip: every frame at 1x
            pg, errs = open_page(browser, path, data, 1)
            frames = pathlib.Path(tempfile.mkdtemp(prefix=f'{name}-'))
            n = int(round(dur * FPS)) + 1
            for i in range(n):
                pg.evaluate(f'window.__seek({i / FPS})')
                pg.screenshot(path=str(frames / f'f{i:05d}.jpg'), type='jpeg', quality=95)
            pg.close()
            webm = CLIPS / f'{name}.webm'
            # Playwright's ffmpeg has no image2 file demuxer, only image2pipe: stream the JPEGs in on stdin
            enc = subprocess.Popen([ff, '-y', '-loglevel', 'error', '-f', 'image2pipe', '-c:v', 'mjpeg',
                                    '-framerate', str(FPS), '-i', 'pipe:0',
                                    '-vf', 'scale=in_range=pc:out_range=tv,format=yuv420p', '-c:v', 'libvpx-vp9',
                                    '-b:v', '0', '-crf', '20', '-deadline', 'good', '-cpu-used', '2', '-row-mt', '1',
                                    str(webm)], stdin=subprocess.PIPE)
            for f in sorted(frames.glob('f*.jpg')):
                enc.stdin.write(f.read_bytes())
            enc.stdin.close()
            if enc.wait():
                sys.exit(f'{name}: webm encode failed')
            line += f' webm={webm.stat().st_size // 1024}KB'
            if mp4:
                out = CLIPS / f'{name}.mp4'
                subprocess.run([str(mp4), str(frames), str(FPS), str(out)], check=True, capture_output=True)
                line += f' mp4={out.stat().st_size // 1024}KB'
            shutil.rmtree(frames)
            print(line + (f' clip-errors={errs}' if errs else ''))
        browser.close()


if __name__ == '__main__':
    main(sys.argv[1:])
