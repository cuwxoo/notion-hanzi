#!/usr/bin/env python3
"""
Tự động điền cấu trúc chữ Hán vào database Notion "Từ vựng tiếng Trung".

Với mỗi dòng có "Chữ Hán" nhưng chưa có "Cấu trúc", script sẽ điền:
  - Pinyin            (từ Make Me a Hanzi)
  - Cấu trúc          (ký hiệu IDS, ví dụ ⿰日月)
  - Thành phần (Việt) (các thành phần ghép nên chữ, tên tiếng Việt)
  - Bộ thủ            (bộ thủ chính, tên tiếng Việt)
  - Hán Việt          (từ Unihan, trường kVietnamese)
Chỉ điền vào ô còn trống, không ghi đè nội dung bạn đã nhập tay.
Cột "Nghĩa" để trống vì dữ liệu nguồn chỉ có nghĩa tiếng Anh.

Cách dùng:
  pip install requests
  export NOTION_TOKEN="secret_xxx"      (Windows: set NOTION_TOKEN=secret_xxx)
  python notion_hanzi.py            # chạy một lần
  python notion_hanzi.py --watch    # chạy liên tục, kiểm tra mỗi 60 giây
"""

import io
import json
import os
import sys
import time
import zipfile

import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = "f3fcee12842b47f082fd053ff95879a0"
NOTION_VERSION = "2022-06-28"

DICT_URL = "https://raw.githubusercontent.com/skishore/makemeahanzi/master/dictionary.txt"
UNIHAN_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"
DICT_CACHE = "makemeahanzi_dictionary.txt"
HANVIET_CACHE = "hanviet.json"

# ---------------------------------------------------------------------------
# Tên tiếng Việt của 214 bộ thủ Khang Hy và các dạng biến thể thường gặp
# ---------------------------------------------------------------------------
RADICALS = {
    # 1 nét
    "一": "nhất (một)", "丨": "cổn (nét sổ)", "丶": "chủ (chấm)", "丿": "phiệt (nét phẩy)",
    "乙": "ất (can ất)", "亅": "quyết (nét móc)",
    # 2 nét
    "二": "nhị (hai)", "亠": "đầu (nắp)", "人": "nhân (người)", "儿": "nhân (chân người)",
    "入": "nhập (vào)", "八": "bát (tám)", "冂": "quynh (vùng biên giới)", "冖": "mịch (trùm khăn)",
    "冫": "băng (băng giá)", "几": "kỷ (ghế)", "凵": "khảm (há miệng)", "刀": "đao (dao)",
    "力": "lực (sức)", "勹": "bao (bọc)", "匕": "chủy (thìa)", "匚": "phương (cái hộp)",
    "匸": "hệ (che đậy)", "十": "thập (mười)", "卜": "bốc (bói)", "卩": "tiết (đốt tre)",
    "厂": "hán (sườn núi)", "厶": "tư (riêng tư)", "又": "hựu (lại nữa)",
    # 3 nét
    "口": "khẩu (miệng)", "囗": "vi (vây quanh)", "土": "thổ (đất)", "士": "sĩ (kẻ sĩ)",
    "夂": "trĩ (đi chậm)", "夊": "tuy (đi chậm)", "夕": "tịch (buổi tối)", "大": "đại (to)",
    "女": "nữ (phụ nữ)", "子": "tử (con)", "宀": "miên (mái nhà)", "寸": "thốn (tấc)",
    "小": "tiểu (nhỏ)", "尢": "uông (yếu)", "尸": "thi (xác chết)", "屮": "triệt (mầm cây)",
    "山": "sơn (núi)", "巛": "xuyên (sông)", "工": "công (thợ)", "己": "kỷ (mình)",
    "巾": "cân (khăn)", "干": "can (khô)", "幺": "yêu (nhỏ nhắn)", "广": "nghiễm (mái nhà)",
    "廴": "dẫn (bước dài)", "廾": "củng (chắp tay)", "弋": "dặc (bắn)", "弓": "cung (cái cung)",
    "彐": "ký (đầu con nhím)", "彡": "sam (lông)", "彳": "xích (bước chân trái)",
    # 4 nét
    "心": "tâm (tim)", "戈": "qua (cây giáo)", "戶": "hộ (cửa)", "户": "hộ (cửa)",
    "手": "thủ (tay)", "支": "chi (cành)", "攴": "phộc (đánh khẽ)", "文": "văn (chữ, văn)",
    "斗": "đẩu (cái đấu)", "斤": "cân (cái rìu)", "方": "phương (vuông)", "无": "vô (không)",
    "日": "nhật (mặt trời)", "曰": "viết (nói rằng)", "月": "nguyệt (mặt trăng)", "木": "mộc (cây)",
    "欠": "khiếm (thiếu)", "止": "chỉ (dừng)", "歹": "đãi (xấu)", "殳": "thù (binh khí)",
    "毋": "vô (đừng)", "比": "tỷ (so sánh)", "毛": "mao (lông)", "氏": "thị (họ)",
    "气": "khí (hơi)", "水": "thủy (nước)", "火": "hỏa (lửa)", "爪": "trảo (móng vuốt)",
    "父": "phụ (cha)", "爻": "hào (hào âm dương)", "爿": "tường (mảnh gỗ)", "片": "phiến (mảnh)",
    "牙": "nha (răng)", "牛": "ngưu (trâu bò)", "犬": "khuyển (chó)",
    # 5 nét
    "玄": "huyền (màu đen huyền)", "玉": "ngọc (đá quý)", "瓜": "qua (dưa)", "瓦": "ngõa (ngói)",
    "甘": "cam (ngọt)", "生": "sinh (sống, sinh)", "用": "dụng (dùng)", "田": "điền (ruộng)",
    "疋": "thất (đơn vị vải)", "疒": "nạch (bệnh tật)", "癶": "bát (gạt ngược)", "白": "bạch (trắng)",
    "皮": "bì (da)", "皿": "mãnh (đồ đựng)", "目": "mục (mắt)", "矛": "mâu (cây giáo)",
    "矢": "thỉ (mũi tên)", "石": "thạch (đá)", "示": "thị (chỉ thị, thần)", "禸": "nhữu (vết chân)",
    "禾": "hòa (lúa)", "穴": "huyệt (hang)", "立": "lập (đứng)",
    # 6 nét
    "竹": "trúc (tre)", "米": "mễ (gạo)", "糸": "mịch (sợi tơ)", "缶": "phẫu (vại sành)",
    "网": "võng (lưới)", "羊": "dương (dê)", "羽": "vũ (lông vũ)", "老": "lão (già)",
    "而": "nhi (mà)", "耒": "lỗi (cái cày)", "耳": "nhĩ (tai)", "聿": "duật (cây bút)",
    "肉": "nhục (thịt)", "臣": "thần (bề tôi)", "自": "tự (tự mình)", "至": "chí (đến)",
    "臼": "cữu (cái cối)", "舌": "thiệt (lưỡi)", "舛": "suyễn (trái ngược)", "舟": "chu (thuyền)",
    "艮": "cấn (quẻ cấn)", "色": "sắc (màu)", "艸": "thảo (cỏ)", "虍": "hô (vằn hổ)",
    "虫": "trùng (sâu bọ)", "血": "huyết (máu)", "行": "hành (đi)", "衣": "y (áo)",
    "襾": "á (che đậy)",
    # 7 nét
    "見": "kiến (thấy)", "角": "giác (sừng)", "言": "ngôn (lời nói)", "谷": "cốc (thung lũng)",
    "豆": "đậu (hạt đậu)", "豕": "thỉ (con lợn)", "豸": "trãi (loài thú không chân)",
    "貝": "bối (vỏ sò, tiền)", "赤": "xích (đỏ)", "走": "tẩu (chạy)", "足": "túc (chân)",
    "身": "thân (thân mình)", "車": "xa (xe)", "辛": "tân (cay)", "辰": "thần (thìn)",
    "辵": "sước (chợt bước đi)", "邑": "ấp (làng)", "酉": "dậu (rượu)", "釆": "biện (phân biệt)",
    "里": "lý (dặm, làng)",
    # 8 nét
    "金": "kim (vàng, kim loại)", "長": "trường (dài)", "門": "môn (cửa)", "阜": "phụ (gò đất)",
    "隶": "đãi (kịp)", "隹": "chuy (chim đuôi ngắn)", "雨": "vũ (mưa)", "青": "thanh (xanh)",
    "非": "phi (không)",
    # 9 nét
    "面": "diện (mặt)", "革": "cách (da thuộc)", "韋": "vi (da mềm)", "韭": "phỉ (rau hẹ)",
    "音": "âm (âm thanh)", "頁": "hiệt (đầu)", "風": "phong (gió)", "飛": "phi (bay)",
    "食": "thực (ăn)", "首": "thủ (cái đầu)", "香": "hương (thơm)",
    # 10 nét trở lên
    "馬": "mã (ngựa)", "骨": "cốt (xương)", "高": "cao (cao)", "髟": "tiêu (tóc dài)",
    "鬥": "đấu (chiến đấu)", "鬯": "sưởng (rượu nếp)", "鬲": "cách (cái đỉnh)", "鬼": "quỷ (ma)",
    "魚": "ngư (cá)", "鳥": "điểu (chim)", "鹵": "lỗ (đất mặn)", "鹿": "lộc (hươu)",
    "麥": "mạch (lúa mạch)", "麻": "ma (cây gai)", "黃": "hoàng (vàng)", "黍": "thử (lúa nếp)",
    "黑": "hắc (đen)", "黹": "chỉ (thêu)", "黽": "mãnh (con ếch)", "鼎": "đỉnh (cái đỉnh)",
    "鼓": "cổ (cái trống)", "鼠": "thử (chuột)", "鼻": "tỵ (mũi)", "齊": "tề (đều)",
    "齒": "xỉ (răng)", "龍": "long (rồng)", "龜": "quy (rùa)", "龠": "dược (ống sáo)",
    # Dạng biến thể của bộ thủ
    "亻": "nhân (người, đứng)", "氵": "thủy (nước, ba chấm)", "扌": "thủ (tay)",
    "艹": "thảo (cỏ)", "忄": "tâm (tim, đứng)", "讠": "ngôn (lời nói)", "灬": "hỏa (lửa, bốn chấm)",
    "辶": "sước (bước đi)", "刂": "đao (dao, đứng)", "礻": "thị (thị, thần)", "衤": "y (áo)",
    "犭": "khuyển (chó)", "钅": "kim (kim loại)", "饣": "thực (ăn)", "纟": "mịch (sợi tơ)",
    "阝": "phụ/ấp (gò đất hoặc làng)", "罒": "võng (lưới)", "牜": "ngưu (trâu bò)",
    "攵": "phộc (đánh khẽ)", "糹": "mịch (sợi tơ)", "⺼": "nhục (thịt)", "爫": "trảo (móng vuốt)",
    "龰": "chỉ (chân)", "丷": "hai chấm", "𠂉": "nét phẩy ngang",
    # Dạng giản thể thường gặp
    "门": "môn (cửa)", "见": "kiến (thấy)", "贝": "bối (vỏ sò, tiền)", "车": "xa (xe)",
    "马": "mã (ngựa)", "鸟": "điểu (chim)", "鱼": "ngư (cá)", "长": "trường (dài)",
    "页": "hiệt (đầu)", "风": "phong (gió)", "飞": "phi (bay)", "齿": "xỉ (răng)",
    "龙": "long (rồng)", "龟": "quy (rùa)",
}

IDS_OPERATORS = {chr(c) for c in range(0x2FF0, 0x2FFC)}

unknown_components = set()


# ---------------------------------------------------------------------------
# Tải dữ liệu
# ---------------------------------------------------------------------------
def load_hanzi_dict():
    """Make Me a Hanzi: mỗi dòng là một JSON, có character/decomposition/radical/pinyin."""
    if not os.path.exists(DICT_CACHE):
        print("Đang tải dữ liệu Make Me a Hanzi...")
        r = requests.get(DICT_URL, timeout=60)
        r.raise_for_status()
        with open(DICT_CACHE, "w", encoding="utf-8") as f:
            f.write(r.text)
    data = {}
    with open(DICT_CACHE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            data[entry["character"]] = entry
    return data


def load_hanviet():
    """Unihan kVietnamese: âm Hán Việt của từng chữ. Nếu tải lỗi thì bỏ qua cột Hán Việt."""
    if os.path.exists(HANVIET_CACHE):
        with open(HANVIET_CACHE, encoding="utf-8") as f:
            return json.load(f)
    try:
        print("Đang tải Unihan để lấy âm Hán Việt...")
        r = requests.get(UNIHAN_URL, timeout=120)
        r.raise_for_status()
        out = {}
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            with z.open("Unihan_Readings.txt") as f:
                for raw in io.TextIOWrapper(f, encoding="utf-8"):
                    if raw.startswith("#"):
                        continue
                    parts = raw.rstrip("\n").split("\t")
                    if len(parts) == 3 and parts[1] == "kVietnamese":
                        out[chr(int(parts[0][2:], 16))] = parts[2].split()[0]
        with open(HANVIET_CACHE, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        return out
    except Exception as e:  # noqa: BLE001
        print(f"Không tải được Unihan ({e}). Bỏ qua cột Hán Việt.")
        return {}


# ---------------------------------------------------------------------------
# Phân tích chữ
# ---------------------------------------------------------------------------
def name_of(ch, hanviet):
    """Tên tiếng Việt của một thành phần."""
    if ch in RADICALS:
        return f"{ch} {RADICALS[ch]}"
    unknown_components.add(ch)
    hv = hanviet.get(ch)
    return f"{ch} ({hv})" if hv else ch


def leaves_of(decomposition):
    return [c for c in decomposition if c not in IDS_OPERATORS and c != "？"]


def analyze(text, hanzi, hanviet):
    chars = []
    for c in text:
        if c in hanzi and c not in chars:
            chars.append(c)
    if not chars:
        return None

    multi = len(chars) > 1

    def tag(c, value):
        return f"{c}: {value}" if multi else value

    pinyin, ids, comps, radicals, hv = [], [], [], [], []
    for c in chars:
        e = hanzi[c]
        pinyin.append((e.get("pinyin") or [""])[0])

        dec = e.get("decomposition", "")
        ids.append(tag(c, dec if dec and dec != "？" else c))

        leaves = leaves_of(dec) or [c]
        comps.append(tag(c, " + ".join(name_of(x, hanviet) for x in leaves)))

        rad = e.get("radical")
        if rad:
            radicals.append(tag(c, name_of(rad, hanviet)))

        hv.append(hanviet.get(c, "?"))

    result = {
        "Pinyin": " ".join(p for p in pinyin if p),
        "Cấu trúc": "\n".join(ids),
        "Thành phần (Việt)": "\n".join(comps),
        "Bộ thủ": "\n".join(radicals),
    }
    if any(x != "?" for x in hv):
        result["Hán Việt"] = " ".join(hv)
    return result


# ---------------------------------------------------------------------------
# Notion API
# ---------------------------------------------------------------------------
def headers():
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def query_pending_pages():
    """Các dòng có Chữ Hán nhưng chưa có Cấu trúc."""
    pages, cursor = [], None
    while True:
        body = {
            "filter": {
                "and": [
                    {"property": "Chữ Hán", "title": {"is_not_empty": True}},
                    {"property": "Cấu trúc", "rich_text": {"is_empty": True}},
                ]
            },
            "page_size": 100,
        }
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers=headers(), json=body, timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        pages.extend(data["results"])
        if not data.get("has_more"):
            return pages
        cursor = data["next_cursor"]


def is_empty(page, prop):
    return not page["properties"].get(prop, {}).get("rich_text")


def rich_text(value):
    return {"rich_text": [{"text": {"content": value[:2000]}}]}


def update_page(page, values):
    props = {k: rich_text(v) for k, v in values.items() if v and is_empty(page, k)}
    # "Cấu trúc" luôn được ghi để dòng không bị xử lý lại
    props["Cấu trúc"] = rich_text(values["Cấu trúc"])
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page['id']}",
        headers=headers(), json={"properties": props}, timeout=30,
    )
    r.raise_for_status()


def run_once(hanzi, hanviet, skipped):
    count = 0
    for page in query_pending_pages():
        if page["id"] in skipped:
            continue
        title = "".join(t["plain_text"] for t in page["properties"]["Chữ Hán"]["title"]).strip()
        values = analyze(title, hanzi, hanviet)
        if not values:
            print(f"Bỏ qua '{title}': không tìm thấy trong dữ liệu.")
            skipped.add(page["id"])
            continue
        update_page(page, values)
        print(f"Đã điền: {title}")
        count += 1
        time.sleep(0.4)  # Notion giới hạn khoảng 3 request/giây
    return count


def main():
    if not NOTION_TOKEN:
        sys.exit("Thiếu biến môi trường NOTION_TOKEN.")

    hanzi = load_hanzi_dict()
    hanviet = load_hanviet()
    skipped = set()

    if "--watch" in sys.argv:
        print("Đang theo dõi database (Ctrl+C để dừng)...")
        while True:
            try:
                run_once(hanzi, hanviet, skipped)
            except requests.RequestException as e:
                print(f"Lỗi mạng hoặc Notion: {e}")
            time.sleep(60)
    else:
        n = run_once(hanzi, hanviet, skipped)
        print(f"Xong, đã cập nhật {n} dòng.")

    if unknown_components:
        print("Thành phần chưa có tên tiếng Việt (có thể thêm vào RADICALS):",
              " ".join(sorted(unknown_components)))


if __name__ == "__main__":
    main()
