"""Render an ICODA motion scene (HTML) to MP4, frame by frame, with its soundtrack.

Every video ships with sound: the scene's cues (M.cue / auto-cues from the kit) and its M.music() grid are read
from the page, audio.py synthesizes the bed + SFX on the same beat grid, and the result is muxed at -14 LUFS.
--music STYLE overrides the scene's style, --track FILE uses a licensed track instead of the synth bed,
--mute skips sound (drafts only).

    python render.py scenes/crypto-pr-reel-9x16.html                 # 60 fps master
    python render.py scenes/x.html --fps 30 --scale 0.5 --out draft  # quick draft
    python render.py scenes/x.html --pace 1.2 --type 1.15 --out ad   # ad cut: slower, bigger text
    python render.py scenes/x.html --stills 1.5,4,9.2                # PNGs for review, no video
    python render.py scenes/x.html --webm                            # + VP9 webm for the website

The scene is a pure function of time, so each frame is captured after seek(t):
no real-time playback, no dropped frames, identical output on every run.
"""
import argparse, asyncio, base64, json, pathlib, subprocess, sys, time

import imageio_ffmpeg
from playwright.async_api import async_playwright

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
ROOT = pathlib.Path(__file__).parent


async def open_page(browser, url, w, h, scale):
    page = await browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
    await page.goto(url)
    await page.wait_for_function("window.READY === true && document.fonts.status === 'loaded'", timeout=30000)
    cdp = await page.context.new_cdp_session(page)
    return page, cdp


async def grab(page, cdp, t, fmt="jpeg"):
    await page.evaluate(f"window.seek({t:.6f})")
    args = {"format": fmt, "optimizeForSpeed": True}
    if fmt == "jpeg":
        args["quality"] = 96
    r = await cdp.send("Page.captureScreenshot", args)
    return base64.b64decode(r["data"])


def report_reading(r, name):
    """Print the per-block reading-speed table (rule lives in lib/motion.js) and flag blocks that are too fast."""
    if not r or not r.get("blocks"):
        return
    rule = r["rule"]
    print(f"reading check  {name}: orient {rule['orient']}s + text at {rule['cps']['caption']} cps "
          f"(headlines {rule['cps']['headline']} cps, numbers {rule['number']}s)")
    bad = 0
    for b in r["blocks"]:
        flag = "" if b["ok"] else "  <-- TOO FAST: needs %.2fs" % b["need"]
        bad += not b["ok"]
        print(f"  {b['t']:6.2f}s  {b['dur']:5.2f}s  {b['chars']:3d} ch  {b['cps']:5.1f} cps  {b['label'][:36]}{flag}")
    print(f"  {'OK: every block can be read' if not bad else f'WARNING: {bad} block(s) too fast to read'}")
    mx = r.get("maxDuration")
    if mx:
        over = r["total"] - mx
        print(f"  total {r['total']:.2f}s / max {mx}s" + (f"  <-- OVER MAX by {over:.2f}s: cut copy or visual density" if over > 0.01 else "  OK"))


async def main(a):
    scene = pathlib.Path(a.scene).resolve()
    q = f"?render&pace={a.pace}&fmt={a.fmt}&hook={a.hook}" + (f"&type={a.type}" if a.type else "") + ("&guides" if a.guides else "")
    url = scene.as_uri() + q
    out_dir = pathlib.Path(a.out_dir) if a.out_dir else ROOT / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = a.out or (f"{scene.stem}_{a.fmt}_{a.hook}" if scene.stem.startswith("ad-") else scene.stem)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--force-color-profile=srgb", "--disable-lcd-text", "--font-render-hinting=none"])
        probe = await browser.new_page()
        await probe.goto(url)
        await probe.wait_for_function("window.READY === true", timeout=30000)
        w, h = await probe.evaluate("[document.querySelector('.stage').offsetWidth, document.querySelector('.stage').offsetHeight]")
        dur = await probe.evaluate("window.DURATION")
        score = {"duration": dur, "cues": await probe.evaluate("window.CUES || []"), "music": await probe.evaluate("window.MUSIC || null")}
        reading = await probe.evaluate("window.READING || null")
        report_reading(reading, scene.stem)
        if a.check:
            await probe.close(); await browser.close()
            return
        if score["music"] and score["music"].get("bpm") and a.pace != 1:   # --pace stretches the beat grid too
            score["music"]["bpm"] /= a.pace; score["music"]["offset"] = score["music"].get("offset", 0) * a.pace
        if a.cues:
            cues = score["cues"]
            pathlib.Path(a.cues).write_text(json.dumps(score, indent=1))
            print(a.cues, len(cues), "cues")
            await probe.close(); await browser.close()
            return
        await probe.close()

        if a.stills:
            page, cdp = await open_page(browser, url, w, h, 1)
            for t in [float(x) for x in a.stills.split(",")]:
                p = out_dir / f"{stem}_t{t:05.2f}.png"
                p.write_bytes(await grab(page, cdp, t, "png"))
                print(p)
            await browser.close()
            return

        n = int(round(dur * a.fps)) + 1
        W, H = int(w * a.scale) // 2 * 2, int(h * a.scale) // 2 * 2
        mp4 = out_dir / f"{stem}.mp4"
        silent = mp4 if a.mute else mp4.with_name(stem + ".video.mp4")
        ff = subprocess.Popen(
            [FFMPEG, "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(a.fps), "-i", "-",
             # screenshots arrive as full-range BT.601 JPEG; ad platforms expect limited-range BT.709
             "-vf", f"scale={W}:{H}:flags=lanczos:in_range=pc:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p,setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709",
             "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
             "-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf), "-profile:v", "high",
             "-movflags", "+faststart", str(silent)],
            stdin=subprocess.PIPE)

        pages = [await open_page(browser, url, w, h, 1) for _ in range(a.workers)]
        frames, nxt, t0 = {}, 0, time.time()

        async def worker(k):
            page, cdp = pages[k]
            for i in range(k, n, a.workers):
                while i - nxt > a.workers * 8:  # keep memory bounded
                    await asyncio.sleep(0.005)
                frames[i] = await grab(page, cdp, i / a.fps)

        async def writer():
            nonlocal nxt
            while nxt < n:
                if nxt in frames:
                    ff.stdin.write(frames.pop(nxt))
                    nxt += 1
                    if nxt % 60 == 0:
                        el = time.time() - t0
                        print(f"\r  {nxt}/{n} frames  {nxt / el:.1f} fps", end="", flush=True)
                else:
                    await asyncio.sleep(0.002)

        await asyncio.gather(writer(), *[worker(k) for k in range(a.workers)])
        ff.stdin.close()
        ff.wait()
        await browser.close()
        if not a.mute:
            import audio
            adir = out_dir / "_audio"; adir.mkdir(exist_ok=True)
            (adir / f"{stem}.cues.json").write_text(json.dumps(score, indent=1))   # kept for re-scoring without re-rendering
            wav = adir / f"{stem}.wav"
            style = a.music or (score["music"] or {}).get("style") or "clean"
            audio.write_wav(audio.build(score, style, a.track), str(wav))
            audio.mux(silent, wav, mp4, a.abr, a.lufs)
            silent.unlink(); wav.unlink()
            print(f"\n  sound: {a.track or style}, {len(score['cues'])} cues")
        print(f"\n{mp4}  {W}x{H} @{a.fps}fps  {dur:.2f}s  ({time.time() - t0:.0f}s render)")

        if a.webm:
            webm = mp4.with_suffix(".webm")
            subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(mp4), "-c:v", "libvpx-vp9", "-b:v", "0",
                            "-crf", "34", "-row-mt", "1", *(["-an"] if a.mute else ["-c:a", "libopus", "-b:a", "64k"]), str(webm)], check=True)
            print(webm)
        if a.poster is not None:
            jpg = mp4.with_name(mp4.stem + "_poster.jpg")
            pt = a.poster
            if pt == "intro":   # the moment the first slide is complete: intro end minus its exit and a margin
                blk = next((b for b in (reading or {}).get("blocks", []) if b["label"] == "intro"), None)
                pt = (blk["t"] + blk["dur"] - 0.6) if blk else 3.0
            subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", str(pt), "-i", str(mp4), "-frames:v", "1",
                            "-q:v", "2", str(jpg)], check=True)
            print(jpg)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--scale", type=float, default=1.0, help="output scale, 0.5 for drafts")
    ap.add_argument("--crf", type=int, default=17)
    ap.add_argument("--pace", type=float, default=1.0, help=">1 slows the whole timeline (ads: 1.15-1.25)")
    ap.add_argument("--type", type=float, default=None, help="global text scale override (ad scenes default to 1.15 in ad.css)")
    ap.add_argument("--fmt", default="9x16", choices=["9x16", "4x5", "16x9"], help="ad scenes: output format")
    ap.add_argument("--hook", default="a", help="ad scenes: hook variant")
    ap.add_argument("--guides", action="store_true", help="draw platform safe zones (review stills only)")
    ap.add_argument("--music", help="override the scene's music style (clean, terminal, tabloid, riso, keynote)")
    ap.add_argument("--track", help="licensed audio file to use as the bed instead of the synth (SFX still synthesized)")
    ap.add_argument("--abr", default="192k", help="AAC bitrate (ads 192k; article embeds 96k)")
    ap.add_argument("--lufs", type=float, default=-14, help="integrated loudness target (ads -14; article embeds -18)")
    ap.add_argument("--mute", action="store_true", help="no soundtrack (drafts only; every delivered video has sound)")
    ap.add_argument("--out-dir", help="output directory (default engine/out)")
    ap.add_argument("--cues", help="write the scene's sound cues + duration to this JSON file and exit")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", help="output file stem")
    ap.add_argument("--stills", help="comma-separated times; write PNGs instead of video")
    ap.add_argument("--check", action="store_true", help="print the reading-speed report and exit (no render)")
    ap.add_argument("--webm", action="store_true", help="also write a VP9 .webm for web embeds")
    ap.add_argument("--poster", help="also write a poster JPG: a time in seconds, or 'intro' = the finished intro just before it leaves")
    asyncio.run(main(ap.parse_args()))
