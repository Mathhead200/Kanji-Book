import json
import gzip
from collections import defaultdict
from lxml import etree

INPUT_FILE = r"C:\Users\mathh\Downloads\kanjidic2.xml.gz"

KANJI_JSON = "kanji_data.json"
RADICAL_JSON = "radical_data.json"

# Unicode Kangxi radicals (1–214)
# These are the standard Kangxi radical characters.
KANGXI_RADICALS = {
    i + 1: chr(0x2F00 + i) for i in range(214)
}


def parse_xml(path):
    with gzip.open(path, "rb") as f:
        parser = etree.XMLParser(load_dtd=False, resolve_entities=False)
        tree = etree.parse(f, parser)
    return tree.getroot()


def extract_character_data(ch):
    """Extract all information for a single <character> entry."""
    data = {}

    # Literal (the kanji itself)
    literal = ch.findtext("literal")
    data["literal"] = literal

    # Codepoints
    data["codepoints"] = {
        cp.get("cp_type"): cp.text
        for cp in ch.findall("codepoint/cp_value")
    }

    # Radicals
    data["radicals"] = [
        int(rv.text)
        for rv in ch.findall("radical/rad_value")
        if rv.get("rad_type") == "classical"
    ]

    # Misc info
    misc = ch.find("misc")
    if misc is not None:
        data["stroke_count"] = int(misc.findtext("stroke_count", default="0"))
        data["variants"] = {
            v.get("var_type"): v.text
            for v in misc.findall("variant")
        }
    else:
        data["stroke_count"] = None
        data["variants"] = {}

    # Dictionary references
    data["dictionary_refs"] = {
        dr.get("dr_type"): dr.text
        for dr in ch.findall("dic_number/dic_ref")
    }

    # Query codes (SKIP, Four-corner, etc.)
    data["query_codes"] = {
        qc.get("qc_type"): qc.text
        for qc in ch.findall("query_code/q_code")
    }

    # Readings + meanings
    readings = defaultdict(list)
    meanings = []

    for rm in ch.findall("reading_meaning/rmgroup"):
        for r in rm.findall("reading"):
            readings[r.get("r_type")].append(r.text)
        for m in rm.findall("meaning"):
            meanings.append(m.text)

    data["readings"] = dict(readings)
    data["meanings"] = meanings

    return literal, data


def build_radical_mapping(kanji_data):
    """Aggregate kanji by radical and attach Unicode radical characters."""
    radical_map = defaultdict(lambda: {
        "radical_char": None,
        "kanji": [],
        "stroke_count": None,
        "count": 0
    })

    for kanji, info in kanji_data.items():
        for rad in info["radicals"]:
            entry = radical_map[rad]
            entry["kanji"].append(kanji)
            entry["count"] += 1

            # Attach Unicode radical character
            entry["radical_char"] = KANGXI_RADICALS.get(rad)

            # Attach stroke count of the radical (optional)
            # KANJIDIC2 does not include radical stroke counts directly,
            # but Kangxi radicals have known stroke counts.
            # If you want, I can add a full stroke-count table here.

    return radical_map


def main():
    root = parse_xml(INPUT_FILE)

    kanji_data = {}

    for ch in root.findall("character"):
        literal, data = extract_character_data(ch)
        kanji_data[literal] = data

    radical_map = build_radical_mapping(kanji_data)

    with open(KANJI_JSON, "w", encoding="utf-8") as f:
        json.dump(kanji_data, f, ensure_ascii=False, indent=2)

    with open(RADICAL_JSON, "w", encoding="utf-8") as f:
        json.dump(radical_map, f, ensure_ascii=False, indent=2)

    print("Done.")


if __name__ == "__main__":
    main()
