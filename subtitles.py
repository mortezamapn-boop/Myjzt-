"""تولید فایل ASS از کلمات زمان‌بندی‌شده. libass از RTL و فارسی پشتیبانی می‌کند
به شرطی که فونت مناسب (مثل Vazirmatn) در fontsdir باشد."""
from dataclasses import dataclass


@dataclass
class Style:
    font: str = "Vazirmatn"
    size: int = 64
    base_color: str = "#FFFFFF"       # رنگ کلمات عادی
    active_color: str = "#FFD400"     # رنگ کلمه فعال
    outline_color: str = "#000000"
    outline: int = 4
    animation: str = "pop"            # none | karaoke | pop
    margin_v: int = 220               # فاصله از پایین
    width: int = 1080
    height: int = 1920


def _c(hex_color: str) -> str:
    """#RRGGBB -> &H00BBGGRR (فرمت ASS)"""
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def _t(sec: float) -> str:
    cs = int(round(sec * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def group_words(words, max_words=4, max_dur=2.5):
    """words: [{'w','s','e'}] -> لیست خط‌ها (هر خط لیستی از کلمات)"""
    lines, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or w["e"] - cur[0]["s"] > max_dur):
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def words_to_ass(words, st: Style = Style()) -> str:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {st.width}
PlayResY: {st.height}
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,{st.font},{st.size},{_c(st.active_color if st.animation == 'karaoke' else st.base_color)},{_c(st.base_color)},{_c(st.outline_color)},&H80000000,-1,0,0,0,100,100,0,0,1,{st.outline},0,2,60,60,{st.margin_v},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events = []
    for line in group_words(words):
        if st.animation == "karaoke":
            # \kf = پر شدن تدریجی رنگ؛ Primary = رنگ پس از خوانده شدن
            text = " ".join(
                f"{{\\kf{max(1, int((w['e'] - w['s']) * 100))}}}{w['w']}" for w in line
            )
            events.append(f"Dialogue: 0,{_t(line[0]['s'])},{_t(line[-1]['e'])},Default,,0,0,0,,{text}")
        elif st.animation == "pop":
            # یک Event برای هر کلمه؛ کلمه فعال با انیمیشن بزرگ می‌شود
            for i, w in enumerate(line):
                end = line[i + 1]["s"] if i + 1 < len(line) else w["e"]
                parts = []
                for j, x in enumerate(line):
                    if i == j:
                        parts.append(
                            f"{{\\c{_c(st.active_color)}\\fscx80\\fscy80"
                            f"\\t(0,120,\\fscx115\\fscy115)}}{x['w']}{{\\r}}"
                        )
                    else:
                        parts.append(x["w"])
                events.append(f"Dialogue: 0,{_t(w['s'])},{_t(end)},Default,,0,0,0,,{' '.join(parts)}")
        else:
            text = " ".join(w["w"] for w in line)
            events.append(f"Dialogue: 0,{_t(line[0]['s'])},{_t(line[-1]['e'])},Default,,0,0,0,,{text}")
    return header + "\n".join(events) + "\n"
