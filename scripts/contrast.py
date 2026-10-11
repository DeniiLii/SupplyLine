"""WCAG 2.1 и APCA (W3 0.0.98G) для пар токенов."""
import sys


def lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def hexrgb(h):
    h = h.lstrip("#"); return [int(h[i:i + 2], 16) for i in (0, 2, 4)]

def wcag(fg, bg):
    L = lambda h: sum(w * lin(v) for w, v in zip((0.2126, 0.7152, 0.0722), hexrgb(h)))
    a, b = sorted((L(fg), L(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)

def apca(fg, bg):
    Y = lambda h: sum(w * (v / 255) ** 2.4 for w, v in zip((0.2126729, 0.7151522, 0.0721750), hexrgb(h)))
    t, b = Y(fg), Y(bg)
    clamp = lambda y: y if y > 0.022 else y + (0.022 - y) ** 1.414
    t, b = clamp(t), clamp(b)
    if b > t:
        s = (b ** 0.56 - t ** 0.57) * 1.14
        return 0 if s < 0.1 else (s - 0.027) * 100
    s = (b ** 0.65 - t ** 0.62) * 1.14
    return 0 if s > -0.1 else (s + 0.027) * 100

PAIRS = [l.split() for l in sys.stdin if l.strip() and not l.startswith("#")]
for name, fg, bg in PAIRS:
    print(f"{name:34s} {fg} on {bg}  WCAG {wcag(fg,bg):5.2f}  APCA Lc {abs(apca(fg,bg)):5.1f}")
