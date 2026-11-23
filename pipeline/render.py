"""Render a branded short from cut.mp4 + timeline.json + plan.json.

Usage: python render.py work_dir brand_dir lang(en|es) out.mp4 [--preview]
Design coordinates are 1080x1920; --preview renders at 540x960 for a fast check.
"""
import json, os, subprocess, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "fonts")
sys.path.insert(0, HERE)

def font(name, size, weight=None):
    path = {"Montserrat": "Montserrat%5Bwght%5D.ttf", "Oswald": "Oswald%5Bwght%5D.ttf",
            "Limelight": "Limelight-Regular.ttf"}[name]
    f = ImageFont.truetype(os.path.join(FONTS, path), int(size))
    if weight:
        try: f.set_variation_by_axes([weight])
        except Exception: pass
    return f

def hexrgb(h, a=255):
    h = h.lstrip("#"); return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)

def ease_out(x): x = min(max(x, 0), 1); return 1 - (1 - x) ** 3
def ease_back(x):
    x = min(max(x, 0), 1); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2

# ---------- caption building ----------
GLUE = {"la", "el", "los", "las", "de", "del", "the", "a", "an", "to", "of", "in", "y", "and", "un", "una", "or", "o", "e", "u", "en", "con", "que", "por", "para", "al"}
def chunk_words(words, max_words=3, max_chars=16):
    chunks, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        txt = " ".join(x["w"] for x in cur)
        last = i + 1 == len(words)
        dangling = w["w"].lower().strip(".,") in GLUE and not last and len(cur) < max_words + 1
        if w.get("brk") or w["w"][-1] in ".,?!" or ((len(cur) >= max_words or len(txt) >= max_chars) and not dangling):
            chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    return chunks

def build_captions(tl, plan, lang):
    words = tl["words"]
    if lang == "en":
        ends = {ph["to"] for ph in plan["phrases"]}
        src = [{"w": w["w"], "s": w["s"], "e": w["e"], "brk": i in ends} for i, w in enumerate(words)]
    else:
        src = []
        for ph in plan["phrases"]:
            s, e = words[ph["from"]]["s"], words[ph["to"]]["e"]
            es_words = ph["es"].split()
            wts = [len(x) + 2 for x in es_words]; tot = sum(wts); t = s
            for x, wt in zip(es_words, wts):
                d = (e - s) * wt / tot; src.append({"w": x, "s": t, "e": t + d}); t += d
    chunks = chunk_words(src)
    out = []
    for i, c in enumerate(chunks):
        start = c[0]["s"]
        nxt = chunks[i + 1][0]["s"] if i + 1 < len(chunks) else c[-1]["e"] + 0.4
        end = min(nxt, c[-1]["e"] + 0.6)
        out.append({"start": start, "end": end, "words": c})
    return out

def draw_caption(img, k, cap, t, brand):
    cfg = brand["captions"]
    f = font(cfg["font"], 92 * k, 900)
    d = ImageDraw.Draw(img)
    words = [w["w"].upper() for w in cap["words"]]
    space = d.textlength(" ", font=f)
    widths = [d.textlength(w, font=f) for w in words]
    total = sum(widths) + space * (len(words) - 1)
    maxw = 820 * k
    lines = [list(range(len(words)))]
    if total > maxw and len(words) > 1:
        lines = [list(range(len(words) - 1)), [len(words) - 1]]
    pop = ease_back((t - cap["start"]) / 0.12)
    yc = 1400 * k
    lh = 110 * k
    for li, line in enumerate(lines):
        lw = sum(widths[i] for i in line) + space * (len(line) - 1)
        x = 540 * k - lw / 2
        y = yc + (li - (len(lines) - 1) / 2) * lh - 55 * k + (1 - pop) * 20 * k
        for i in line:
            w = cap["words"][i]
            active = w["s"] <= t < (cap["words"][i + 1]["s"] if i + 1 < len(cap["words"]) else cap["end"])
            col = hexrgb(cfg["highlight_color"]) if active else hexrgb(cfg["base_color"])
            d.text((x, y), words[i], font=f, fill=col, stroke_width=int(9 * k), stroke_fill=hexrgb(cfg["outline_color"]))
            x += widths[i] + space

# ---------- graphics ----------
def rounded(d, box, r, fill): d.rounded_rectangle(box, radius=r, fill=fill)

def icon(d, kind, cx, cy, s, col, bg):
    if kind == "pin":
        d.ellipse((cx - s * .5, cy - s * .75, cx + s * .5, cy + s * .25), fill=col)
        d.polygon([(cx - s * .42, cy - s * .1), (cx + s * .42, cy - s * .1), (cx, cy + s * .75)], fill=col)
        d.ellipse((cx - s * .2, cy - s * .45, cx + s * .2, cy - s * .05), fill=bg)
    elif kind == "food":
        d.ellipse((cx - s * .42, cy - s * .42, cx + s * .42, cy + s * .42), outline=col, width=max(2, int(s * .09)))
        lw = max(2, int(s * .09))
        d.line((cx - s * .78, cy - s * .5, cx - s * .78, cy + s * .55), fill=col, width=lw)
        for dx in (-.9, -.78, -.66):
            d.line((cx + s * dx, cy - s * .5, cx + s * dx, cy - s * .2), fill=col, width=max(1, lw // 2))
        d.line((cx + s * .75, cy - s * .5, cx + s * .75, cy + s * .55), fill=col, width=lw)
    elif kind == "clock":
        lw = max(2, int(s * .1))
        d.ellipse((cx - s * .55, cy - s * .55, cx + s * .55, cy + s * .55), outline=col, width=lw)
        d.line((cx, cy, cx, cy - s * .35), fill=col, width=lw)
        d.line((cx, cy, cx + s * .28, cy + s * .1), fill=col, width=lw)
    elif kind == "doc":  # checklist / paperwork
        lw = max(2, int(s * .09))
        d.rounded_rectangle((cx - s * .42, cy - s * .58, cx + s * .42, cy + s * .58), radius=s * .08, outline=col, width=lw)
        for i, yy in enumerate((-.28, .02, .32)):
            d.line((cx - s * .26, cy + s * yy, cx - s * .16, cy + s * (yy + .1)), fill=col, width=lw)
            d.line((cx - s * .16, cy + s * (yy + .1), cx - s * .02, cy + s * (yy - .08)), fill=col, width=lw)
            d.line((cx + s * .06, cy + s * yy, cx + s * .28, cy + s * yy), fill=col, width=lw)
    elif kind == "euro":
        lw = max(2, int(s * .1))
        d.arc((cx - s * .5, cy - s * .55, cx + s * .5, cy + s * .55), 40, 320, fill=col, width=lw)
        d.line((cx - s * .65, cy - s * .12, cx + s * .1, cy - s * .12), fill=col, width=lw)
        d.line((cx - s * .65, cy + s * .14, cx + s * .1, cy + s * .14), fill=col, width=lw)
    elif kind == "key":
        lw = max(2, int(s * .11))
        d.ellipse((cx - s * .6, cy - s * .3, cx - s * .0, cy + s * .3), outline=col, width=lw)
        d.line((cx, cy, cx + s * .62, cy), fill=col, width=lw)
        d.line((cx + s * .45, cy, cx + s * .45, cy + s * .25), fill=col, width=lw)
        d.line((cx + s * .28, cy, cx + s * .28, cy + s * .2), fill=col, width=lw)

def draw_graphic(img, k, g, t, brand, lang):
    gc = brand["graphics"]
    p_in = ease_out((t - g["t0"]) / 0.35)
    p_out = ease_out((g["t1"] - t) / 0.3)
    a = min(p_in, p_out)
    if a <= 0: return
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    panel, accent, txtc = hexrgb(gc["panel_color"], 235), hexrgb(gc["accent_color"]), hexrgb(gc["text_color"])
    text = g[lang]
    slide = (1 - p_in) * -500 * k
    x0, y0 = 70 * k + slide, 300 * k
    if g["type"] == "pin":
        f1, f2 = font("Oswald", 84 * k, 700), font("Montserrat", 44 * k, 700)
        w = max(d.textlength(text[0], font=f1), d.textlength(text[1], font=f2)) + 210 * k
        rounded(d, (x0, y0, x0 + w, y0 + 200 * k), 34 * k, panel)
        d.rectangle((x0, y0 + 30 * k, x0 + 12 * k, y0 + 170 * k), fill=accent)
        icon(d, "pin", x0 + 92 * k, y0 + 100 * k, 80 * k, accent, panel)
        d.text((x0 + 165 * k, y0 + 18 * k), text[0], font=f1, fill=txtc)
        d.text((x0 + 167 * k, y0 + 128 * k), text[1], font=f2, fill=accent)
    else:
        f1 = font("Montserrat", 56 * k, 800)
        w = d.textlength(text, font=f1) + 180 * k
        rounded(d, (x0, y0, x0 + w, y0 + 120 * k), 60 * k, panel)
        icon(d, g.get("icon", "food"), x0 + 80 * k, y0 + 60 * k, 62 * k, accent, panel)
        d.text((x0 + 140 * k, y0 + 24 * k), text, font=f1, fill=txtc)
    if a < 1:
        al = layer.getchannel("A").point(lambda v: int(v * a)); layer.putalpha(al)
    img.alpha_composite(layer)

def draw_title(frame_rgb, k, title, t, brand, lang, seg, prev_mask):
    tc = brand["titles"]
    H, W = frame_rgb.shape[:2]
    mask = seg.person(frame_rgb)
    if prev_mask is not None: mask = 0.5 * mask + 0.5 * prev_mask
    a = min(ease_out(t / 0.3), ease_out((title["end"] - t) / 0.3))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    small, big = title[lang]
    fb = font(tc["font"], 330 * k, 700)
    bw = d.textlength(big, font=fb)
    if bw > 1000 * k:
        fb = font(tc["font"], 330 * k * 1000 * k / bw, 700); bw = d.textlength(big, font=fb)
    fs = font("Montserrat", 70 * k, 900)
    sw = d.textlength(small, font=fs)
    sc = 0.85 + 0.15 * ease_back(t / 0.35)
    # big word sits behind the head; small line above it in brand colour
    col = mask[:, int(W * 0.35):int(W * 0.65)].max(axis=1)
    rows = np.where(col > 0.5)[0]
    head_top = rows[0] if len(rows) else 300 * k
    bb = d.textbbox((0, 0), big, font=fb); cap_h = bb[3] - bb[1]
    if title.get("_yb") is None: title["_yb"] = max(190 * k, head_top + 0.5 * cap_h - bb[3])
    yb = title["_yb"]
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ds = ImageDraw.Draw(shadow)
    ds.text(((W - bw) / 2 + 8 * k, yb + 10 * k), big, font=fb, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10 * k))
    lay.alpha_composite(shadow)
    d.text(((W - bw) / 2, yb), big, font=fb, fill=(255, 255, 255, 255))
    d.text(((W - sw) / 2, yb + bb[1] - 95 * k), small, font=fs, fill=hexrgb(tc["color"]), stroke_width=int(6 * k), stroke_fill=(0, 0, 0, 255))
    if sc != 1:
        lay = lay.resize((int(W * sc), int(H * sc)), Image.BILINEAR)
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ox = (W - lay.width) // 2; oy = int((H - lay.height) * 0.15)
        canvas.paste(lay, (ox, oy)); lay = canvas
    if a < 1: lay.putalpha(lay.getchannel("A").point(lambda v: int(v * a)))
    base = Image.fromarray(frame_rgb).convert("RGBA")
    comp = Image.alpha_composite(base, lay)
    m = Image.fromarray((np.clip(mask, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5 * k))
    comp.paste(base, (0, 0), m)
    return comp, mask

def endcard(last_rgb, k, ec, brand, lang, brand_dir, t_rel):
    H, W = last_rgb.shape[:2]
    bg = cv2.GaussianBlur(last_rgb, (0, 0), 25 * k)
    bg = (bg * 0.45).astype(np.uint8)
    img = Image.fromarray(bg).convert("RGBA")
    a = ease_out(t_rel / 0.4)
    logo_file = brand["logo"].get("badge") or brand["logo"].get("white")
    logo = Image.open(os.path.join(brand_dir, logo_file)).convert("RGBA")
    ls = int(420 * k * (0.8 + 0.2 * ease_back(t_rel / 0.5)))
    logo = logo.resize((ls, int(ls * logo.height / logo.width)), Image.LANCZOS)
    img.alpha_composite(logo, ((W - logo.width) // 2, int(470 * k)))
    d = ImageDraw.Draw(img)
    f1 = font(brand["titles"]["font"], 96 * k, 700); f2 = font("Montserrat", 50 * k, 800)
    y = 470 * k + logo.height + 70 * k
    for line in ec[lang]:
        w = d.textlength(line, font=f1); d.text(((W - w) / 2, y), line, font=f1, fill=(255, 255, 255)); y += 115 * k
    w = d.textlength(ec["url"], font=f2)
    d.text(((W - w) / 2, y + 40 * k), ec["url"], font=f2, fill=hexrgb(brand["graphics"]["accent_color"]))
    if a < 1:
        img = Image.blend(Image.fromarray(last_rgb).convert("RGBA"), img, a)
    return img

def main(work, brand_dir, lang, out, preview=False):
    tl = json.load(open(os.path.join(work, "timeline.json")))
    plan = json.load(open(os.path.join(work, "plan.json")))
    brand = json.load(open(os.path.join(brand_dir, "brand.json")))
    W, H = (540, 960) if preview else (1080, 1920); k = W / 1080
    fps = 30
    words = tl["words"]
    caps = build_captions(tl, plan, lang)
    gfx = []
    for g in plan["graphics"]:
        t0 = words[g["at_word"]]["s"]
        t1 = words[g["until_word"]]["e"] + g.get("hold", 0.6)
        gfx.append({**g, "t0": t0, "t1": min(t1, tl["duration"])})
    title = plan["title"]
    ec = plan["endcard"]
    dur = tl["duration"]; total = dur + ec["dur"]
    segs = tl["segments"]
    zooms = [1.0 if i % 2 == 0 else plan.get("punch_in", 1.08) for i in range(len(segs))]
    seg = None
    if title.get("behind_head", True):
        from seg import Seg; seg = Seg()
    rd = subprocess.Popen(["ffmpeg", "-v", "error", "-i", os.path.join(work, "cut.mp4"), "-vf", f"scale={W}:{H}",
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    wr = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
                           "-i", "-", "-i", os.path.join(work, "cut.mp4"), "-map", "0:v", "-map", "1:a",
                           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23" if preview else "18", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-af", "apad", "-t", f"{total:.3f}", "-movflags", "+faststart", out],
                          stdin=subprocess.PIPE)
    brolls = []
    for b in plan.get("broll", []):
        t0 = words[b["at_word"]]["s"] - 0.05
        uw = b.get("until_word")
        t1 = dur if uw is None or uw >= len(words) - 1 else words[uw]["e"] + 0.1
        brolls.append({**b, "t0": t0, "t1": min(t1, dur), "proc": None})
    n = 0; last = None; prev_mask = None
    while True:
        buf = rd.stdout.read(W * H * 3)
        t = n / fps
        if len(buf) < W * H * 3:
            break
        fr = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        si = next((i for i, (a, b) in enumerate(segs) if a <= t < b), len(segs) - 1)
        z = zooms[si]
        if z != 1.0:
            cw, ch = int(W / z), int(H / z); x0 = (W - cw) // 2; y0 = int((H - ch) * 0.35)
            fr = cv2.resize(fr[y0:y0 + ch, x0:x0 + cw], (W, H), interpolation=cv2.INTER_LINEAR)
        for b in brolls:
            if b["t0"] <= t < b["t1"]:
                if b["proc"] is None:
                    b["proc"] = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(b.get("offset", 0)), "-i", b["file"],
                        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
                    b["last"] = fr
                bb = b["proc"].stdout.read(W * H * 3)
                if len(bb) == W * H * 3: b["last"] = np.frombuffer(bb, np.uint8).reshape(H, W, 3)
                fr = b["last"]
        last = fr.copy()
        if seg is not None and t < title["end"]:
            img, prev_mask = draw_title(fr, k, title, t, brand, lang, seg, prev_mask)
        else:
            img = Image.fromarray(fr).convert("RGBA")
        for g in gfx:
            if g["t0"] <= t < g["t1"]: draw_graphic(img, k, g, t, brand, lang)
        for c in caps:
            if c["start"] <= t < c["end"]: draw_caption(img, k, c, t, brand); break
        wr.stdin.write(img.convert("RGB").tobytes()); n += 1
    # end card
    for j in range(int(ec["dur"] * fps)):
        img = endcard(last, k, ec, brand, lang, brand_dir, j / fps)
        wr.stdin.write(img.convert("RGB").tobytes())
    wr.stdin.close(); wr.wait(); rd.wait()
    for b in brolls:
        if b["proc"]: b["proc"].stdout.close(); b["proc"].kill(); b["proc"].wait()
    if seg is not None: seg.s.close()
    print("rendered", out, f"{total:.1f}s")

if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[2], a[3], preview="--preview" in a)
