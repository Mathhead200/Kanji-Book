#!/usr/bin/env python3
import os
import json
import glob
import xml.etree.ElementTree as ET

SVG_NS = "{http://www.w3.org/2000/svg}"
KVG_NS = "{http://kanjivg.tagaini.net}"

DEBUG = False

def debug(*args):
    if DEBUG:
        print("[DEBUG]", *args)

# Kangxi radical symbol → canonical radical form
KANGXI_TO_CANONICAL = {
    "⼀": "一", "⼁": "丨", "⼂": "丶", "⼃": "丿", "⼄": "乙", "⼅": "亅",
    "⼆": "二", "⼇": "亠", "⼈": "人", "⼉": "儿", "⼊": "入", "⼋": "八",
    "⼌": "冂", "⼍": "冖", "⼎": "冫", "⼏": "几", "⼐": "凵", "⼑": "刀",
    "⼒": "力", "⼓": "勹", "⼔": "匕", "⼕": "匚", "⼖": "匸", "⼗": "十",
    "⼘": "卜", "⼙": "卩", "⼚": "厂", "⼛": "厶", "⼜": "又", "⼝": "口",
    "⼞": "囗", "⼟": "土", "⼠": "士", "⼡": "夂", "⼢": "夊", "⼣": "夕",
    "⼤": "大", "⼥": "女", "⼦": "子", "⼧": "宀", "⼨": "寸", "⼩": "小",
    "⼪": "尢", "⼫": "尸", "⼬": "屮", "⼭": "山", "⼮": "巛", "⼯": "工",
    "⼰": "己", "⼱": "巾", "⼲": "干", "⼳": "幺", "⼴": "广", "⼵": "廴",
    "⼶": "廾", "⼷": "弋", "⼸": "弓", "⼹": "彐", "⼺": "彡", "⼻": "彳",
    "⼼": "心", "⼽": "戈", "⼾": "戶", "⼿": "手", "⽀": "支", "⽁": "攴",
    "⽂": "文", "⽃": "斗", "⽄": "斤", "⽅": "方", "⽆": "无", "⽇": "日",
    "⽈": "曰", "⽉": "月", "⽊": "木", "⽋": "欠", "⽌": "止", "⽍": "歹",
    "⽎": "殳", "⽏": "毋", "⽐": "比", "⽑": "毛", "⽒": "氏", "⽓": "气",
    "⽔": "水", "⽕": "火", "⽖": "爪", "⽗": "父", "⽘": "爻", "⽙": "爿",
    "⽚": "片", "⽛": "牙", "⽜": "牛", "⽝": "犬", "⽞": "玄", "⽟": "玉",
    "⽠": "瓜", "⽡": "瓦", "⽢": "甘", "⽣": "生", "⽤": "用", "⽥": "田",
    "⽦": "疋", "⽧": "疒", "⽨": "癶", "⽩": "白", "⽪": "皮", "⽫": "皿",
    "⽬": "目", "⽭": "矛", "⽮": "矢", "⽯": "石", "⽰": "示", "⽱": "禸",
    "⽲": "禾", "⽳": "穴", "⽴": "立", "⽵": "竹", "⽶": "米", "⽷": "糸",
    "⽸": "缶", "⽹": "网", "⽺": "羊", "⽻": "羽", "⽼": "老", "⽽": "而",
    "⽾": "耒", "⽿": "耳", "⾀": "聿", "⾁": "肉", "⾂": "臣", "⾃": "自",
    "⾄": "至", "⾅": "臼", "⾆": "舌", "⾇": "舛", "⾈": "舟", "⾉": "艮",
    "⾊": "色", "⾋": "艸", "⾌": "虍", "⾍": "虫", "⾎": "血", "⾏": "行",
    "⾐": "衣", "⾑": "襾", "⾒": "見", "⾓": "角", "⾔": "言", "⾕": "谷",
    "⾖": "豆", "⾗": "豕", "⾘": "豸", "⾙": "貝", "⾚": "赤", "⾛": "走",
    "⾜": "足", "⾝": "身", "⾞": "車", "⾟": "辛", "⾠": "辰", "⾡": "辵",
    "⾢": "邑", "⾣": "酉", "⾤": "釆", "⾥": "里", "⾦": "金", "⾧": "長",
    "⾨": "門", "⾩": "阜", "⾪": "隶", "⾫": "隹", "⾬": "雨", "⾭": "青",
    "⾮": "非", "⾯": "面", "⾰": "革", "⾱": "韋", "⾲": "韭", "⾳": "音",
    "⾴": "頁", "⾵": "風", "⾶": "飛", "⾷": "食", "⾸": "首", "⾹": "香",
    "⾺": "馬", "⾻": "骨", "⾼": "高", "⾽": "髟", "⾾": "鬥", "⾿": "鬯",
    "⿀": "鬲", "⿁": "鬼", "⿂": "魚", "⿃": "鳥", "⿄": "鹵", "⿅": "鹿",
    "⿆": "麥", "⿇": "麻", "⿈": "黃", "⿉": "黍", "⿊": "黑", "⿋": "黹",
    "⿌": "黽", "⿍": "鼎", "⿎": "鼓", "⿏": "鼠", "⿐": "鼻", "⿑": "齊",
    "⿒": "齒", "⿓": "龍", "⿔": "龜", "⿕": "龠"
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_canonical_to_radnum(radical_data):
    canonical_to_num = {}
    for rad_num_str, info in radical_data.items():
        kangxi = info["radical_char"]
        canonical = KANGXI_TO_CANONICAL.get(kangxi)
        if canonical:
            canonical_to_num[canonical] = int(rad_num_str)
    debug("Canonical→Radical mapping size:", len(canonical_to_num))
    return canonical_to_num


def extract_literal(root):
    for g in root.iter(f"{SVG_NS}g"):
        elem = g.attrib.get(f"{KVG_NS}element")
        if elem:
            return elem
    return None


def extract_components(root):
    comps = []
    for g in root.iter(f"{SVG_NS}g"):
        elem = g.attrib.get(f"{KVG_NS}element")
        if not elem:
            continue

        original = g.attrib.get(f"{KVG_NS}original")
        radical_form = g.attrib.get(f"{KVG_NS}radicalForm")
        trad_form = g.attrib.get(f"{KVG_NS}tradForm")

        if original:
            elem = original
        elif radical_form:
            elem = radical_form
        elif trad_form:
            elem = trad_form

        comps.append(elem)
    return comps


def update_kanji_and_radicals(kanji_data, radical_data, svg_dir):
    canonical_to_radnum = build_canonical_to_radnum(radical_data)

    extracted = {k: set() for k in kanji_data.keys()}

    svg_files = glob.glob(os.path.join(svg_dir, "*.svg"))
    debug("Found SVG files:", len(svg_files))

    for svg_path in svg_files:
        debug("\nParsing SVG:", svg_path)

        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()
        except Exception as e:
            debug("  ERROR parsing:", e)
            continue

        literal = extract_literal(root)
        debug("  Literal extracted:", literal)

        if not literal or literal not in kanji_data:
            debug("  Literal not in kanji_data, skipping")
            continue

        comps = extract_components(root)
        debug("  Components found:", comps)

        for c in comps:
            if c in canonical_to_radnum:
                radnum = canonical_to_radnum[c]
                extracted[literal].add(radnum)
                debug(f"    MATCH: component {c} → radical #{radnum}")

    # Merge radicals
    for kanji, info in kanji_data.items():
        existing = set(info.get("radicals", []))
        merged = sorted(existing | extracted[kanji])
        info["radicals"] = merged

    # Rebuild radical_data["kanji"]
    new_radkan = {int(k): [] for k in radical_data.keys()}

    for kanji, info in kanji_data.items():
        for r in info["radicals"]:
            new_radkan[r].append(kanji)

    for radnum_str, info in radical_data.items():
        info["kanji"] = sorted(new_radkan[int(radnum_str)])

    return kanji_data, radical_data


def main():
    kanji_path = "data/kanji_data.json"
    radical_path = "data/radical_data.json"
    svg_dir = "data-sources/kanjivg"

    kanji_data = load_json(kanji_path)
    radical_data = load_json(radical_path)

    updated_kanji, updated_radicals = update_kanji_and_radicals(
        kanji_data, radical_data, svg_dir
    )

    save_json("data/kanji_data_1.json", updated_kanji)
    save_json("data/radical_data_1.json", updated_radicals)

    print("\nDone. Updated files written to:")
    print("  data/kanji_data_1.json")
    print("  data/radical_data_1.json")


if __name__ == "__main__":
    main()
