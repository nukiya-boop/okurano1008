#!/usr/bin/env python3
"""大嵓埜 10月「桔梗色コース」焼物 PR リール動画（1080x1920 / 30fps / 30秒）を生成する。

使い方:
  python3 video/make_reel.py --src <素材フォルダ> --fonts <フォントフォルダ> --out video/okurano_kikyo_yakimono_reel.mp4

素材フォルダには cook0025.jpg ... cook0075.jpg, dish0004.jpg, dish0009.jpg を置く
（images/ の「イメージ_調理####」「コース_焼物####」を ASCII 名にしたもの）。
フォント: Shippori Mincho（Medium / Bold）。
"""
import argparse
import math
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, DURATION = 1080, 1920, 30, 30.0
KIKYO = (86, 84, 162)          # 桔梗色 #5654A2
KIKYO_LIGHT = (176, 170, 232)  # 暗い写真の上で読める淡い桔梗色
WASHI = (246, 240, 228)        # 生成り色の文字


# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


# ---------------------------------------------------------------- clips
# (file, start, end, (cx0, cy0, zoom0), (cx1, cy1, zoom1), transition_in)
# cx, cy: 切り出し中心（画像に対する割合）、zoom: 9:16 枠を画像高さいっぱいにしたときを 1.0 とする倍率
CLIPS = [
    ("cook0025", 0.0, 3.2, (0.50, 0.55, 1.18), (0.55, 0.55, 1.05), "fade_black"),
    ("cook0027", 2.8, 5.2, (0.50, 0.62, 1.00), (0.50, 0.55, 1.10), "wipe_up"),
    ("cook0028", 4.8, 7.0, (0.62, 0.62, 1.10), (0.54, 0.62, 1.00), "dissolve"),
    ("cook0029", 6.6, 8.6, (0.62, 0.45, 1.00), (0.62, 0.55, 1.10), "wipe_left"),
    ("cook0033", 8.2, 10.2, (0.30, 0.55, 1.05), (0.42, 0.60, 1.12), "dissolve"),
    ("cook0052", 9.8, 12.0, (0.47, 0.55, 1.20), (0.47, 0.50, 1.02), "zoom_through"),
    ("cook0057", 11.6, 13.6, (0.50, 0.55, 1.00), (0.56, 0.52, 1.10), "dissolve"),
    ("cook0058", 13.2, 15.2, (0.64, 0.50, 1.10), (0.58, 0.52, 1.00), "wipe_left"),
    ("cook0063", 14.8, 17.0, (0.42, 0.65, 1.05), (0.42, 0.60, 1.16), "dip_black"),
    ("cook0066", 16.6, 19.0, (0.50, 0.60, 1.00), (0.50, 0.50, 1.10), "dissolve"),
    ("cook0074", 18.6, 20.8, (0.50, 0.65, 1.15), (0.55, 0.65, 1.02), "wipe_up"),
    ("cook0075", 20.4, 22.6, (0.60, 0.62, 1.00), (0.56, 0.62, 1.10), "dissolve"),
]
# 完成皿（全体が見えるようレイアウト表示）
HERO = ("dish0009", 22.2, 26.6, "flash")
ENDCARD = ("dish0004", 26.2, DURATION, "dissolve")
TRANS = 0.4  # 重なり（トランジション）秒数


def load_sources(src):
    imgs = {}
    for f, *_ in CLIPS + [HERO, ENDCARD]:
        imgs[f] = Image.open(os.path.join(src, f + ".jpg")).convert("RGB")
    return imgs


def kenburns(img, t, a, b):
    """img から 9:16 の枠を切り出して W x H にする。"""
    e = ease_in_out(t)
    cx, cy, z = (lerp(a[i], b[i], e) for i in range(3))
    iw, ih = img.size
    # zoom 1.0 = 画像の高さ（縦長素材なら幅）いっぱいの 9:16 枠
    base_h = min(ih, iw * H / W)
    ch = base_h / z
    cw = ch * W / H
    x0 = clamp(cx * iw - cw / 2, 0, iw - cw)
    y0 = clamp(cy * ih - ch / 2, 0, ih - ch)
    return img.transform((W, H), Image.AFFINE, (cw / W, 0, x0, 0, ch / H, y0), resample=Image.BICUBIC)


_layout_cache = {}


def layout_frame(img, key, t, zoom0=1.0, zoom1=1.06):
    """完成皿用: ぼかした背景 + 皿全体を見せる横長写真。"""
    if key not in _layout_cache:
        bg = kenburns(img, 0, (0.5, 0.5, 1.0), (0.5, 0.5, 1.0))
        bg = bg.filter(ImageFilter.GaussianBlur(40))
        bg = Image.blend(bg, Image.new("RGB", (W, H), (16, 12, 10)), 0.62)
        _layout_cache[key] = bg
    frame = _layout_cache[key].copy()
    z = lerp(zoom0, zoom1, ease_in_out(t))
    pw = W - 72
    ph = int(pw * img.size[1] / img.size[0])
    iw, ih = img.size
    cw, ch = iw / z, ih / z
    photo = img.transform((pw, ph), Image.AFFINE,
                          ((cw / pw), 0, (iw - cw) / 2, 0, (ch / ph), (ih - ch) / 2),
                          resample=Image.BICUBIC)
    py = 470
    frame.paste(photo, (36, py))
    d = ImageDraw.Draw(frame)
    d.rectangle([36, py, 36 + pw - 1, py + ph - 1], outline=(*KIKYO_LIGHT,), width=2)
    return frame


# ---------------------------------------------------------------- text
class Fonts:
    def __init__(self, folder):
        self.folder = folder
        self.cache = {}

    def get(self, weight, size):
        key = (weight, size)
        if key not in self.cache:
            name = {"bold": "ShipporiMincho-Bold.ttf", "medium": "ShipporiMincho-Medium.ttf"}[weight]
            self.cache[key] = ImageFont.truetype(os.path.join(self.folder, name), size)
        return self.cache[key]


def glyph(ch, font, color, shadow=True, vertical=False):
    """1 文字ぶんの RGBA 画像（影つき）を作る。"""
    size = font.size
    pad = int(size * 0.5)
    canvas = (size + pad * 2, size + pad * 2)
    txt = Image.new("RGBA", canvas, (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    d.text((pad + size / 2, pad + size / 2), ch, font=font, fill=(*color, 255), anchor="mm")
    if vertical and ch in "ー―〜":
        txt = txt.rotate(-90, resample=Image.BICUBIC)
    if not shadow:
        return txt
    a = txt.getchannel("A")
    out = Image.new("RGBA", canvas, (0, 0, 0, 0))
    # 広めの柔らかい影（明るい背景でも読めるように）+ 締まった影
    glow = Image.new("RGBA", canvas, (10, 6, 4, 0))
    glow.putalpha(a.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(size * 0.22)).point(lambda v: min(255, int(v * 1.1))))
    out.alpha_composite(glow)
    sh = Image.new("RGBA", canvas, (0, 0, 0, 0))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(size * 0.07)).point(lambda v: int(v * 0.9)))
    out.alpha_composite(sh, (int(size * 0.03), int(size * 0.05)))
    out.alpha_composite(txt)
    return out


class Telop:
    """文字ごとに出現タイミングをずらして描くテロップ。"""

    def __init__(self, start, end, fade_out=0.45):
        self.start, self.end, self.fade_out = start, end, fade_out
        self.items = []  # (img, x, y, appear_t, style)
        self.shapes = []  # (callable(draw_layer, progress, alpha))

    def add_vertical(self, text, x, y, font, color, t0, step, style="rise", spacing=1.08):
        size = font.size
        cy = y
        for i, ch in enumerate(text):
            if ch == " ":
                cy += size * 0.5
                continue
            g = glyph(ch, font, color, vertical=True)
            gx, gy = x - g.width / 2, cy - g.height / 2 + size / 2
            if ch in "、。":
                gx += size * 0.55
                gy -= size * 0.55
            self.items.append((g, gx, gy, t0 + i * step, style))
            cy += size * spacing

    def add_horizontal(self, text, x, y, font, color, t0, step, style="rise", tracking=0.06, anchor="center"):
        size = font.size
        widths = [font.getlength(ch) + size * tracking for ch in text]
        total = sum(widths) - size * tracking
        cx = x - total / 2 if anchor == "center" else x
        for i, ch in enumerate(text):
            if ch != " " and ch != "　":
                g = glyph(ch, font, color)
                self.items.append((g, cx + widths[i] / 2 - g.width / 2 - size * tracking / 2,
                                   y - g.height / 2, t0 + i * step, style))
            cx += widths[i]

    def add_line(self, x0, y0, x1, y1, color, width, t0, dur):
        self.shapes.append((x0, y0, x1, y1, color, width, t0, dur))

    def render(self, frame, t):
        if t < self.start or t > self.end:
            return
        out_a = 1.0 - ease_in_out((t - (self.end - self.fade_out)) / self.fade_out)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for (x0, y0, x1, y1, color, width, t0, dur) in self.shapes:
            p = ease_out((t - t0) / dur)
            if p <= 0:
                continue
            d.line([(x0, y0), (lerp(x0, x1, p), lerp(y0, y1, p))],
                   fill=(*color, int(255 * out_a)), width=width)
        for g, gx, gy, ta, style in self.items:
            p = (t - ta) / 0.55
            if p <= 0:
                continue
            e = ease_out(p)
            a = e * out_a
            if a <= 0.003:
                continue
            ox = oy = 0
            gi = g
            if style == "rise":
                oy = (1 - e) * 26
            elif style == "drop":
                oy = -(1 - e) * 26
            elif style == "slide":
                ox = -(1 - e) * 30
            elif style == "focus":  # ぼけから焦点が合う
                r = (1 - e) * 10
                if r > 0.3:
                    gi = g.filter(ImageFilter.GaussianBlur(r))
            if a < 0.999:
                gi = gi.copy()
                gi.putalpha(gi.getchannel("A").point(lambda v, a=a: int(v * a)))
            layer.alpha_composite(gi, (int(gx + ox), int(gy + oy)))
        frame.alpha_composite(layer)


class BrushWipeTelop(Telop):
    """左から筆で書くように現れる横書きテロップ（グラデーションマスク）。"""

    def __init__(self, start, end, wipe_t0, wipe_dur, **kw):
        super().__init__(start, end, **kw)
        self.wipe_t0, self.wipe_dur = wipe_t0, wipe_dur
        self.static = None

    def render(self, frame, t):
        if t < self.start or t > self.end:
            return
        if self.static is None:
            self.static = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            for g, gx, gy, _, _ in self.items:
                self.static.alpha_composite(g, (int(gx), int(gy)))
            xs = [gx for _, gx, _, _, _ in self.items] + [s[0] for s in self.shapes]
            xe = [gx + g.width for g, gx, _, _, _ in self.items] + [s[2] for s in self.shapes]
            self.x_min, self.x_max = min(xs), max(xe)
            d = ImageDraw.Draw(self.static)
            for (x0, y0, x1, y1, color, width, *_r) in self.shapes:
                d.line([(x0, y0), (x1, y1)], fill=(*color, 255), width=width)
        p = ease_in_out((t - self.wipe_t0) / self.wipe_dur)
        out_a = 1.0 - ease_in_out((t - (self.end - self.fade_out)) / self.fade_out)
        soft = 140
        edge = lerp(self.x_min - soft, self.x_max + soft, p)
        xs = np.arange(W, dtype=np.float32)
        ramp = np.clip((edge - xs) / soft, 0, 1) * out_a
        arr = np.array(self.static)
        arr[..., 3] = (arr[..., 3].astype(np.float32) * ramp[None, :]).astype(np.uint8)
        frame.alpha_composite(Image.fromarray(arr))


def build_telops(F):
    T = []

    # A: オープニング（縦書き・一文字ずつ浮かび上がる）
    a = Telop(0.4, 3.0)
    a.add_horizontal("北新地　大嵓埜", W / 2, 250, F.get("medium", 40), WASHI, 0.5, 0.05, style="focus", tracking=0.35)
    a.add_line(W / 2 - 150, 300, W / 2 + 150, 300, KIKYO_LIGHT, 2, 0.8, 0.8)
    a.add_vertical("桔梗色コース", 820, 520, F.get("bold", 104), WASHI, 0.9, 0.12, style="rise")
    a.add_vertical("十月 神無月の献立", 680, 560, F.get("medium", 46), WASHI, 1.3, 0.06, style="rise")
    T.append(a)

    # B: いちぼ（縦書き・上から降りる）
    b = Telop(3.1, 6.4)
    b.add_vertical("黒毛和牛", 900, 380, F.get("bold", 96), WASHI, 3.25, 0.1, style="drop")
    b.add_vertical("いちぼ", 770, 540, F.get("bold", 96), WASHI, 3.55, 0.12, style="drop")
    b.add_line(660, 560, 660, 960, KIKYO_LIGHT, 3, 3.9, 0.7)
    b.add_vertical("厳選の希少部位", 600, 560, F.get("medium", 40), WASHI, 4.1, 0.06, style="drop")
    T.append(b)

    # C: 下ごしらえ（ぼけから焦点）
    c = Telop(6.8, 9.8)
    c.add_vertical("ひと振りに、", 880, 420, F.get("bold", 88), WASHI, 6.9, 0.1, style="focus")
    c.add_vertical("真心を込めて", 760, 520, F.get("bold", 88), WASHI, 7.4, 0.1, style="focus")
    T.append(c)

    # D: 炭火（筆で書くようなワイプ・横書き）
    d = BrushWipeTelop(10.2, 14.6, wipe_t0=10.4, wipe_dur=1.4)
    d.add_horizontal("炭火で、", W / 2, 1180, F.get("bold", 96), WASHI, 0, 0, tracking=0.12)
    d.add_horizontal("じっくりと炙る", W / 2, 1310, F.get("bold", 96), WASHI, 0, 0, tracking=0.12)
    d.add_line(W / 2 - 240, 1405, W / 2 + 240, 1405, KIKYO_LIGHT, 3, 0, 0)
    T.append(d)

    # E: 香り（一文字ずつ浮かび上がる・縦書き）
    e = Telop(15.2, 18.8)
    e.add_vertical("立ちのぼる、", 880, 360, F.get("bold", 92), WASHI, 15.4, 0.11, style="rise")
    e.add_vertical("秋の香り", 755, 470, F.get("bold", 92), WASHI, 16.1, 0.13, style="rise")
    T.append(e)

    # F: 根菜（左から滑り込む・横書き）
    f = Telop(19.0, 22.2)
    f.add_horizontal("彩り豊かな", W / 2, 330, F.get("medium", 52), KIKYO_LIGHT, 19.1, 0.05, style="slide", tracking=0.2)
    f.add_horizontal("秋の根菜を添えて", W / 2, 440, F.get("bold", 92), WASHI, 19.4, 0.07, style="slide", tracking=0.08)
    T.append(f)

    # G: 料理名（完成皿）
    g = Telop(22.5, 26.6)
    g.add_horizontal("十月 桔梗色コースより", W / 2, 260, F.get("medium", 42), KIKYO_LIGHT, 22.6, 0.03, style="focus", tracking=0.2)
    g.add_horizontal("〈焼物〉", W / 2, 360, F.get("bold", 56), WASHI, 22.9, 0.06, style="rise", tracking=0.1)
    g.add_horizontal("黒毛和牛いちぼと午房の炙り", W / 2, 1290, F.get("bold", 70), WASHI, 23.3, 0.06, style="rise", tracking=0.04)
    g.add_line(W / 2 - 300, 1365, W / 2 + 300, 1365, KIKYO_LIGHT, 2, 24.1, 0.8)
    g.add_horizontal("午房ソース　午房唐揚げ", W / 2, 1435, F.get("medium", 46), WASHI, 24.4, 0.04, style="rise", tracking=0.1)
    g.add_horizontal("秋の根菜添え", W / 2, 1505, F.get("medium", 46), WASHI, 24.7, 0.04, style="rise", tracking=0.1)
    T.append(g)

    # H: エンドカード
    h = Telop(26.5, DURATION + 1, fade_out=0.01)
    h.add_horizontal("北新地 懐石料理", W / 2, 215, F.get("medium", 40), KIKYO_LIGHT, 26.7, 0.04, style="focus", tracking=0.3)
    h.add_horizontal("大嵓埜", W / 2, 340, F.get("bold", 120), WASHI, 26.9, 0.18, style="focus", tracking=0.35)
    h.add_horizontal("十月「桔梗色コース」", W / 2, 1290, F.get("bold", 64), WASHI, 27.3, 0.04, style="rise", tracking=0.06)
    h.add_line(W / 2 - 300, 1360, W / 2 + 300, 1360, KIKYO_LIGHT, 2, 27.8, 0.8)
    h.add_horizontal("ご予約・ご相談", W / 2, 1430, F.get("medium", 40), WASHI, 28.0, 0.03, style="rise", tracking=0.2)
    h.add_horizontal("06-6341-3535", W / 2, 1500, F.get("bold", 56), WASHI, 28.2, 0.03, style="rise", tracking=0.06)
    h.add_horizontal("JR北新地駅より徒歩2分", W / 2, 1580, F.get("medium", 36), KIKYO_LIGHT, 28.5, 0.02, style="rise", tracking=0.1)
    T.append(h)
    return T


# ---------------------------------------------------------------- transitions
def blend(a, b, p):
    return Image.blend(a, b, clamp(p))


def mask_blend(a, b, mask):
    return Image.composite(b, a, Image.fromarray((np.clip(mask, 0, 1) * 255).astype(np.uint8)))


def transition(kind, prev, nxt, p):
    p = ease_in_out(p)
    if kind == "dissolve":
        return blend(prev, nxt, p)
    if kind in ("wipe_left", "wipe_up"):
        soft = 260.0
        if kind == "wipe_left":
            coord = np.arange(W, dtype=np.float32)[None, :].repeat(H, 0)
            span = W
        else:
            coord = (H - np.arange(H, dtype=np.float32))[:, None].repeat(W, 1)
            span = H
        edge = lerp(-soft, span + soft, p)
        m = (edge - (span - coord)) / soft if kind == "wipe_left" else (edge - coord) / soft
        return mask_blend(prev, nxt, m)
    if kind == "zoom_through":
        s = 1 + 0.25 * p
        zw, zh = int(W * s), int(H * s)
        z = prev.resize((zw, zh), Image.BILINEAR).crop(((zw - W) // 2, (zh - H) // 2, (zw - W) // 2 + W, (zh - H) // 2 + H))
        return blend(z, nxt, p)
    if kind == "dip_black":
        black = Image.new("RGB", (W, H), (0, 0, 0))
        return blend(prev, black, p * 2) if p < 0.5 else blend(black, nxt, (p - 0.5) * 2)
    if kind == "flash":
        white = Image.new("RGB", (W, H), (255, 250, 240))
        return blend(prev, white, p * 2 * 0.85) if p < 0.5 else blend(white, nxt, 0.15 + (p - 0.5) * 2 * 0.85)
    return nxt


# ---------------------------------------------------------------- main
def vignette():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((x - W / 2) / (W * 0.75)) ** 2 + ((y - H / 2) / (H * 0.7)) ** 2)
    v = np.clip(1.0 - (r - 0.55) * 0.9, 0.55, 1.0)
    return v[..., None]


def clip_frame(imgs, clip, t):
    f, s, e, a, b, _ = clip
    return kenburns(imgs[f], (t - s) / (e - s), a, b)


def special_frame(imgs, spec, t):
    f, s, e, _ = spec
    return layout_frame(imgs[f], f, (t - s) / (e - s))


def scene_at(imgs, t):
    """時刻 t の背景（トランジション込み）を返す。"""
    seq = [("clip", c) for c in CLIPS] + [("special", HERO), ("special", ENDCARD)]

    def render(item, t):
        kind, spec = item
        return clip_frame(imgs, spec, t) if kind == "clip" else special_frame(imgs, spec, t)

    def bounds(item):
        return item[1][1], item[1][2]

    def trans_kind(item):
        return item[1][-1]

    active = [it for it in seq if bounds(it)[0] <= t < bounds(it)[1]]
    if not active:
        active = [seq[-1]]
    if len(active) == 1:
        it = active[0]
        fr = render(it, t)
        if trans_kind(it) == "fade_black" and t < bounds(it)[0] + 0.8:
            fr = blend(Image.new("RGB", (W, H), (0, 0, 0)), fr, ease_in_out(t / 0.8))
        return fr
    prev, nxt = active[0], active[-1]
    p = (t - bounds(nxt)[0]) / (bounds(prev)[1] - bounds(nxt)[0])
    return transition(trans_kind(nxt), render(prev, t), render(nxt, t), p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview", type=float, nargs="*", help="指定秒の静止画だけ書き出す")
    args = ap.parse_args()

    imgs = load_sources(args.src)
    telops = build_telops(Fonts(args.fonts))
    vig = vignette()

    def frame_at(t):
        bg = scene_at(imgs, t)
        arr = (np.asarray(bg, dtype=np.float32) * vig).clip(0, 255).astype(np.uint8)
        fr = Image.fromarray(arr).convert("RGBA")
        for tl in telops:
            tl.render(fr, t)
        return fr.convert("RGB")

    if args.preview:
        base = os.path.splitext(args.out)[0]
        for t in args.preview:
            frame_at(t).save(f"{base}_t{t:05.2f}.jpg", quality=88)
        return

    n = int(DURATION * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
           "-map", "0:v", "-map", "1:a", "-shortest",
           "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-level", "4.1", "-c:a", "aac", "-b:a", "128k",
           "-movflags", "+faststart", args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        proc.stdin.write(frame_at(i / FPS).tobytes())
        if i % 60 == 0:
            print(f"frame {i}/{n}", flush=True)
    proc.stdin.close()
    proc.wait()
    if proc.returncode:
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
