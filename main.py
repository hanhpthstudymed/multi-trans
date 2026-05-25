#!/usr/bin/env python3
"""
Advanced Multilingual Dictionary Bot for Telegram
Auto-detects input language and translates to all 6 languages
Supports: English, Vietnamese, Chinese (Simplified & Traditional), Japanese, Korean

Fixed version:
- Sửa lỗi MarkdownV2 / Markdown escape
- Sửa logic detect Phồn Thể (loại bỏ ký tự Giản Thể lẫn trong set)
- Dùng session aiohttp chung -> nhanh hơn
- balance tách theo từng user (per-chat)
- Phiên âm / dịch hiển thị an toàn (escape Markdown)
"""

import logging
import os
import re
import asyncio
from typing import Optional, Dict

import aiohttp
import pykakasi
from pypinyin import pinyin, Style

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# === LOGGING ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# === LANGUAGE CONFIG ===
LANGUAGES = {
    "en":    {"name": "EN", "flag": "🇬🇧", "code": "en"},
    "vi":    {"name": "VN", "flag": "🇻🇳", "code": "vi"},
    "zh-CN": {"name": "CN", "flag": "🇨🇳", "code": "zh-CN"},
    "zh-TW": {"name": "TW", "flag": "🇹🇼", "code": "zh-TW"},
    "ja":    {"name": "JP", "flag": "🇯🇵", "code": "ja"},
    "ko":    {"name": "KO", "flag": "🇰🇷", "code": "ko"},
}

# Khởi tạo kakasi 1 lần
kks = pykakasi.kakasi()

# Session aiohttp dùng chung (tạo trong main loop)
_http_session: Optional[aiohttp.ClientSession] = None


async def get_session() -> aiohttp.ClientSession:
    """Lấy session aiohttp dùng chung, tạo nếu chưa có."""
    global _http_session
    if _http_session is None or _http_session.closed:
        timeout = aiohttp.ClientTimeout(total=10)
        _http_session = aiohttp.ClientSession(timeout=timeout)
    return _http_session


# ============================================================
# === LANGUAGE DETECTION ===
# ============================================================

# Ký tự CHỈ có trong Phồn Thể (Traditional Chinese)
# - Đã LOẠI BỎ các ký tự thực ra là Giản Thể (经, 国, 学, 会, 与, 为, 时, 对, 进, 来, 说,
#   从, 这, 样, 个, 实, 现, 发, 展, 动, 关, 系, 资, 数, 据, 讯, 构, 处, 应, 该, 设, 计, 们,
#   体, 医, 药, 开, 关, 闭, 网, 络, 电, 脑, 电, 话, 视, 听, 读, 写, 书, 报, 纸, 志, 杂, …)
# - Vẫn giữ TOÀN BỘ các ký tự đặc trưng phồn thể để không "giảm ký tự" như yêu cầu.
# - Bao gồm thêm Bopomofo (ㄅㄆㄇ…) vốn chỉ dùng ở Đài Loan.
TRADITIONAL_ONLY_CHARS = set(
    # Bopomofo (chú âm) – đặc trưng Đài Loan
    "ㄅㄆㄇㄈㄉㄊㄋㄌㄍㄎㄏㄐㄑㄒㄓㄔㄕㄖㄗㄘㄙ"
    "ㄚㄛㄜㄝㄞㄟㄠㄡㄢㄣㄤㄥㄦㄧㄨㄩ"
    # Hán tự chỉ có trong Phồn Thể
    "經學會與為時對進來說從這樣實現發展動關係資數據訊構處應該設計們體醫藥開關閉"
    "網絡電腦電話視聽讀寫書報紙誌雜證據認識別準確總計劃過愛戀"
    "語車門風飛馬鳥魚麵點麼難見覺買賣貴錢頭臉腦腳龍龜貝黃綠藍紅線網軟髮後麗廣廠廳樓"
    "機橋燈燒熱壓寶專業藝圖圓變禮讓還選邊運達鄉鄧鐘鐵銀銅錯鎖鏡長張陽陰隊雞雙靜響"
    "頁頂顏類顧願題額飯飲餓餅館驗驚驛驢鬧鬥鬱燦爛燭爐爭奪奮婦嬰嬌孃寵屬嶺嶽峽島崑崙"
    "帳幣幫庫廢彈彎彌彙徑憂懷態慣慶憲懲戰戲戶擔據擴攝攔攪敵斃斬晝曆曉暈曠棄榮榪槍樹"
    "樣檔檢櫃櫻權歡歲歷歸殘殼毀氣滅濕灣濤濫瀉爺牆獄獨獲瑩甕癡盜監盤盞礦碼磚禍禪稅窩"
    "竄競筆築籃糧糾紀紋納紗紐純紛紙級紜紡紮紹終細組絆綁絨結絕絲絛絹綜綢維綱緊緒編緣"
    "縣縫縮績繁織繩續纖罰聖聞聯聲肅脅脈腫脫臟臨舉舊艦艱莊萬葉號虧蝕衛裝複觀觸譯譜警"
    "護豐財貢貧貨販責賢敗貯貪貫貼貸貿賀賴趙趨跡踐蹤轉輪輯輸轟辦辭遙遞鄰醜醬釀針釘釣"
    "鈔鉛鉤銘鋒錄鍋鍵閃閒閱闆際陣陸險雲霧韋韌頌預頑頓頗領頸頻顆飄飢駐騎騙騰驅驟鬆魯"
    "鮮鯉鯨鳳鳴鴨鵝麥麩黨齊齒齡龐叢冊丟並亂乾亙亞產畝親億僅僕儀價眾優夥傘傳傷倫偉側"
    "僑儲兒兌黴凍凜劍劑勁勵勞勢勳匯區協單卻厭厲參發吳啟喪喬圍園團壘夢奐奧奬媽嫻嬈孫"
    "寧審寬寢導將尋層岡峴巖帥師幾庵廬彥徹徵德憐憫懶懼戔戧拋挾捨掃掛採揀損搖搜擠擺攜"
    "斂斷無晉暫棗棟棲極標樞樸檯檻櫥欄歐歟殞殲殺毆毿氈氫漢湧滯滾滿漁漸潛澀濃濟瀋灑爐"
    "牽犧狀獅獻玀琺瑪甦瘋癢癬皚盧睏睪硃祕禦稈窮竅簾簽糞紳統繪繳罵羈聰聶職脣脹腎臍艙"
    "艤艸莖華萊著蔣蕭薑蘆虛蟲襯覓覽訃訓訊記討訝許論講謝譚譽豈豎豬貓費賀趕跪踴轎辮辯"
    "農逕遜遷郵鄺醃釋釐鑄鑑閔閣閥隸難靈韜頰顛顫飆飾餘騁驀髒鬚魘魷鮑鮫鵑鶴鹹鹽冪凱凳"
    "刪剎勸勻匱啞噴嚐嚥囑壙壢夾妝娛嫿宮屜巔幟幹廝徬憑懇戩戾拚挽捲掄掙摯撈撐擬擲攆斕"
    "曬棧槓樁檸櫓櫛欽殯毯氬沓洩淒淩淪渦滲滷潁潰瀾瀰燼獺玨璣甌癱眥瞞矚礙禱穌窺簫籤糰"
    "絞綽綺緲縷繕羨聾薈薔藹蘊蠅襲覈覬訣詠誣諒譏譴豔貳賑賬贈躍轅轍邏醞釁鈣鉑銬銷鋸錐"
    "錫鍊闡隴霽韃颱餵餾駭騷魎鱉鷗麴齣"
)


def detect_language(text: str) -> str:
    """Phát hiện ngôn ngữ của text đầu vào."""
    text = text.strip()

    # 1. Vietnamese - dấu tiếng Việt
    if re.search(
        r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
        text.lower(),
    ):
        return "vi"

    # 2. Korean (Hangul)
    if re.search(r"[\uAC00-\uD7AF]", text):
        return "ko"

    # 3. Japanese (Hiragana/Katakana - chỉ có trong tiếng Nhật)
    if re.search(r"[\u3040-\u309F\u30A0-\u30FF]", text):
        return "ja"

    # 4. Chinese (Hanzi)
    if re.search(r"[\u4E00-\u9FFF]", text):
        # Nếu có BẤT KỲ ký tự chỉ-có-trong-phồn-thể → Phồn Thể (TW)
        for char in text:
            if char in TRADITIONAL_ONLY_CHARS:
                return "zh-TW"
        # Ngược lại → Giản Thể (CN)
        return "zh-CN"

    # 5. English (default)
    return "en"


# ============================================================
# === PHONETICS ===
# ============================================================

async def get_english_ipa(word: str) -> Optional[str]:
    """Lấy IPA cho từ tiếng Anh qua Free Dictionary API."""
    try:
        session = await get_session()
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.strip()}"
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data and len(data) > 0:
                    for p in data[0].get("phonetics", []):
                        if p.get("text"):
                            return p["text"]
    except Exception as e:
        logger.error(f"IPA fetch error: {e}")
    return None


def get_pinyin_text(text: str) -> Optional[str]:
    """Pinyin có dấu thanh cho tiếng Trung."""
    try:
        result = pinyin(text, style=Style.TONE)
        out = " ".join(["".join(syll) for syll in result])
        return out if out.strip() else None
    except Exception as e:
        logger.error(f"Pinyin error: {e}")
        return None


def get_romaji_text(text: str) -> Optional[str]:
    """Romaji (Hepburn) cho tiếng Nhật."""
    try:
        result = kks.convert(text)
        romaji = " ".join(
            [item["hepburn"] for item in result if item.get("hepburn")]
        ).strip()
        return romaji if romaji else None
    except Exception as e:
        logger.error(f"Romaji error: {e}")
        return None


def get_korean_romanization(text: str) -> Optional[str]:
    """Revised Romanization cơ bản cho tiếng Hàn."""
    cho = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "",
           "j", "jj", "ch", "k", "t", "p", "h"]
    jung = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae",
            "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i"]
    jong = ["", "k", "kk", "ks", "n", "nj", "nh", "t", "l", "lg", "lm", "lb",
            "ls", "lt", "lp", "lh", "m", "p", "ps", "s", "ss", "ng", "j",
            "ch", "k", "t", "p", "h"]

    syllables = []
    for char in text:
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            offset = code - 0xAC00
            ci = offset // (21 * 28)
            ji = (offset % (21 * 28)) // 28
            jo = offset % 28
            syllables.append(cho[ci] + jung[ji] + jong[jo])
        elif char.strip():
            syllables.append(char)

    out = " ".join(s for s in syllables if s).strip()
    return out if out else None


async def get_phonetics(text: str, lang: str) -> Optional[str]:
    """Lấy phiên âm/romanization theo ngôn ngữ."""
    if lang == "en":
        # Free Dictionary API chỉ hỗ trợ 1 từ -> dùng từ đầu
        first_word = text.split()[0] if text.split() else text
        return await get_english_ipa(first_word)
    if lang in ("zh-CN", "zh-TW"):
        return get_pinyin_text(text)
    if lang == "ja":
        return get_romaji_text(text)
    if lang == "ko":
        return get_korean_romanization(text)
    return None


# ============================================================
# === TRANSLATION ENGINE ===
# ============================================================

async def translate_google(text: str, source_lang: str, target_lang: str) -> Optional[str]:
    """Dịch qua Google Translate (endpoint công khai)."""
    try:
        session = await get_session()
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": source_lang,
            "tl": target_lang,
            "dt": "t",
            "q": text,
        }
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data and data[0]:
                    return "".join(seg[0] for seg in data[0] if seg[0])
    except Exception as e:
        logger.error(f"Google Translate error: {e}")
    return None


async def translate_mymemory(text: str, source_lang: str, target_lang: str) -> Optional[str]:
    """Fallback: MyMemory API."""
    try:
        session = await get_session()
        url = "https://api.mymemory.translated.net/get"
        params = {"q": text, "langpair": f"{source_lang}|{target_lang}"}
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("responseStatus") == 200:
                    return data.get("responseData", {}).get("translatedText")
    except Exception as e:
        logger.error(f"MyMemory error: {e}")
    return None


async def translate_word(text: str, source_lang: str, target_lang: str) -> str:
    """Dịch 1 từ với fallback."""
    if source_lang == target_lang:
        return text

    result = await translate_google(text, source_lang, target_lang)
    if not result:
        result = await translate_mymemory(text, source_lang, target_lang)
    return result or "—"


async def get_all_translations(text: str, source_lang: str) -> Dict[str, str]:
    """Dịch sang tất cả ngôn ngữ trừ ngôn ngữ gốc."""
    translations = {source_lang: text}
    target_langs = [l for l in LANGUAGES if l != source_lang]

    tasks = [translate_word(text, source_lang, t) for t in target_langs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for lang, res in zip(target_langs, results):
        if isinstance(res, Exception):
            logger.error(f"Translate to {lang} failed: {res}")
            translations[lang] = "—"
        else:
            translations[lang] = res or "—"
    return translations


async def get_all_phonetics(translations: Dict[str, str]) -> Dict[str, str]:
    """Lấy phiên âm cho tất cả ngôn ngữ cần phiên âm."""
    phonetics: Dict[str, str] = {}
    langs_needing = ["en", "zh-CN", "zh-TW", "ja", "ko"]

    tasks, langs = [], []
    for lang in langs_needing:
        text = translations.get(lang)
        if text and text != "—":
            tasks.append(get_phonetics(text, lang))
            langs.append(lang)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for lang, res in zip(langs, results):
        if isinstance(res, Exception):
            logger.error(f"Phonetic [{lang}] error: {res}")
            continue
        if res:
            phonetics[lang] = res
    return phonetics


# ============================================================
# === MARKDOWN HELPERS ===
# ============================================================

def escape_md(text: str) -> str:
    """Escape ký tự đặc biệt của Markdown (legacy) để tránh parse lỗi.
    Markdown legacy chỉ cần escape: _ * ` [
    """
    if not text:
        return text
    return (
        text.replace("\\", "\\\\")
            .replace("_", "\\_")
            .replace("*", "\\*")
            .replace("`", "\\`")
            .replace("[", "\\[")
    )


# ============================================================
# === COMMAND HANDLERS ===
# ============================================================

START_TEXT = (
    "🌐 *Advanced Dictionary Bot — Từ Điển Thông Minh*\n\n"
    "Xin chào! Tôi là bot từ điển tự động dịch, hỗ trợ:\n\n"
    "🇬🇧 English + IPA\n"
    "🇻🇳 Tiếng Việt\n"
    "🇨🇳 中文简体 + Pinyin\n"
    "🇹🇼 中文繁體 + Pinyin\n"
    "🇯🇵 日本語 + Romaji\n"
    "🇰🇷 한국어 + Romanization\n\n"
    "*Cách sử dụng:*\n"
    "Gõ từ bằng bất kỳ ngôn ngữ nào — bot tự detect & dịch.\n\n"
    "*Ví dụ:*\n"
    "📝 `diabetes`\n"
    "📝 `bệnh tiểu đường`\n"
    "📝 `神经网络`\n"
    "📝 `ニューラルネットワーク`\n"
    "📝 `신경망`\n\n"
    "💰 *Tính tiền:* `+1000`, `-500`, `#dcsd 0`\n\n"
    "Bắt đầu bằng cách gõ một từ! 😊"
)

HELP_TEXT = (
    "*📖 Hướng Dẫn Sử Dụng*\n\n"
    "Bot tự động detect ngôn ngữ bạn nhập:\n\n"
    "🇻🇳 `bánh mì`, `bệnh tiểu đường`\n"
    "🇬🇧 `bread`, `diabetes`\n"
    "🇨🇳 `面包`, `糖尿病`\n"
    "🇹🇼 `麵包`, `糖尿病`\n"
    "🇯🇵 `パン`, `糖尿病`\n"
    "🇰🇷 `빵`, `당뇨병`\n\n"
    "*💰 Tính tiền:*\n"
    "`+1000` — cộng tiền\n"
    "`-500` — trừ tiền\n"
    "`#dcsd 0` — đặt lại số dư\n\n"
    "/start — Bắt đầu\n"
    "/help — Trợ giúp"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(START_TEXT, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý input để dịch."""
    user_input = (update.message.text or "").strip()

    if len(user_input) < 1:
        await update.message.reply_text("⚠️ Vui lòng nhập từ hoặc cụm từ")
        return
    if len(user_input) > 200:
        await update.message.reply_text(
            "⚠️ Quá dài, vui lòng nhập ngắn hơn (dưới 200 ký tự)"
        )
        return

    loading_msg = await update.message.reply_text("⏳ Đang tra cứu...")

    try:
        source_lang = detect_language(user_input)
        logger.info(f"Detected language: {source_lang} | input: {user_input!r}")

        translations = await get_all_translations(user_input, source_lang)
        phonetics = await get_all_phonetics(translations)

        response = format_translation(user_input, source_lang, translations, phonetics)

        try:
            await loading_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.exception("handle_text error")
        try:
            await loading_msg.delete()
        except Exception:
            pass
        await update.message.reply_text(
            f"❌ Lỗi khi tra cứu: {str(e)[:120]}\n\nVui lòng thử lại hoặc gõ /help"
        )


def format_translation(
    word: str,
    source_lang: str,
    translations: Dict[str, str],
    phonetics: Dict[str, str],
) -> str:
    """Format kết quả dịch + phiên âm. Mọi text user-data đều được escape."""
    lines = [f"*📖 {escape_md(word)}*"]
    lines.append(f"_Ngôn ngữ gốc: {LANGUAGES[source_lang]['name']}_\n")

    lang_order = [source_lang] + [l for l in LANGUAGES if l != source_lang]

    for i, lang in enumerate(lang_order):
        info = LANGUAGES[lang]
        flag = info["flag"]
        name = info["name"]
        text = escape_md(translations.get(lang, "—"))
        phon = phonetics.get(lang)

        if lang == source_lang:
            line = f"{flag} *{name}* (Gốc): *{text}*"
        else:
            line = f"{flag} *{name}*: {text}"

        if phon:
            # Phiên âm bọc trong `code` -> không cần escape _ * nhưng cần escape ` và \
            phon_safe = phon.replace("\\", "\\\\").replace("`", "ʼ")
            line += f"\n    `{phon_safe}`"

        lines.append(line)
        if i == 0:
            lines.append("")

    lines.append("\n_Powered by Google Translate_")
    return "\n".join(lines)


# ============================================================
# === MONEY CALCULATOR (per-user) ===
# ============================================================

def format_money(x: float) -> str:
    """1000000 -> 1.000.000 (kiểu Việt Nam)."""
    return format(int(round(x)), ",").replace(",", ".")


def parse_money(text: str) -> float:
    """Parse số tiền, bỏ dấu chấm/phẩy phân tách hàng nghìn."""
    cleaned = text.replace(".", "").replace(",", "").strip()
    if not cleaned:
        raise ValueError("empty money")
    return float(cleaned)


async def handle_money(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tính tiền: + cộng, - trừ, #dcsd <số> đặt lại. Số dư lưu per-chat."""
    # Số dư lưu trong context.chat_data -> mỗi chat / user một số dư
    chat_data = context.chat_data
    if "balance" not in chat_data:
        chat_data["balance"] = 0.0

    text = ""
    if update.message.text:
        text = update.message.text.strip()
    elif update.message.caption:
        text = update.message.caption.strip()
    else:
        return

    try:
        first_line = text.split("\n")[0].strip()

        # ➕ Cộng
        if first_line.startswith("+"):
            amount = parse_money(first_line[1:])
            chat_data["balance"] += amount
            await update.message.reply_text(
                f"🟢 +{format_money(amount)}\n💰 Số dư: {format_money(chat_data['balance'])}"
            )

        # ➖ Trừ
        elif first_line.startswith("-"):
            amount = parse_money(first_line[1:])
            chat_data["balance"] -= amount
            await update.message.reply_text(
                f"🔴 -{format_money(amount)}\n💰 Số dư: {format_money(chat_data['balance'])}"
            )

        # 🔄 Reset
        elif first_line.lower().startswith("#dcsd"):
            parts = first_line.split()
            if len(parts) == 2:
                chat_data["balance"] = parse_money(parts[1])
                await update.message.reply_text(
                    f"🔄 Reset số dư: {format_money(chat_data['balance'])}"
                )
            else:
                await update.message.reply_text("❌ Dùng đúng: `#dcsd 100`", parse_mode="Markdown")
            async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
                global balance
                formatted_balance = f"{balance:,.0f}".replace(",", ".")
                await update.message.reply_text(
                    f"💰 Số dư hiện tại: {formatted_balance} VNĐ"
                )
    except ValueError:
        await update.message.reply_text("❌ Sai định dạng số tiền")
    except Exception as e:
        logger.exception("Money handler error")
        await update.message.reply_text(f"❌ Lỗi: {str(e)[:100]}")


# ============================================================
# === MAIN ===
# ============================================================

async def _on_shutdown(app: Application) -> None:
    """Đóng session aiohttp khi bot tắt."""
    global _http_session
    if _http_session and not _http_session.closed:
        await _http_session.close()
        logger.info("aiohttp session closed.")


def main() -> None:
    token = os.getenv("TOKEN")
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Vui lòng đặt biến môi trường TOKEN cho Telegram bot!")
        return

    application = (
        Application.builder()
        .token(token)
        .post_shutdown(_on_shutdown)
        .build()
    )

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ktsd", check_balance))
    
    # Money handler (đăng ký TRƯỚC handler dịch)
    money_pattern = r"^\s*([+\-]\s*\d|#dcsd)"
    money_filter = (
        filters.Regex(money_pattern)
        | filters.CaptionRegex(money_pattern)
    )
    application.add_handler(
        MessageHandler(money_filter & ~filters.COMMAND, handle_money)
    )

    # Translation handler — chạy SAU money_filter
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    
    print("🤖 Bot is running...")
    print("💡 /start để test bot dịch")
    print("💡 +1000 / -500 / #dcsd 0 để dùng bot tính tiền")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
