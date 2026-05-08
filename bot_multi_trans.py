#!/usr/bin/env python3
"""
Advanced Multilingual Dictionary Bot for Telegram
Auto-detects input language and translates to all 6 languages
Supports: English, Vietnamese, Chinese (Simplified & Traditional), Japanese, Korean
"""

import logging
import asyncio
import aiohttp
import re
import pykakasi
from pypinyin import pinyin, Style
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# === LOGGING ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === LANGUAGE CONFIG ===
LANGUAGES = {
    'en': {'name': 'EN', 'flag': '🇬🇧', 'code': 'en'},
    'vi': {'name': 'VN', 'flag': '🇻🇳', 'code': 'vi'},
    'zh-CN': {'name': 'CN', 'flag': '🇨🇳', 'code': 'zh-CN'},
    'zh-TW': {'name': 'TW', 'flag': '🇹🇼', 'code': 'zh-TW'},
    'ja': {'name': 'JP', 'flag': '🇯🇵', 'code': 'ja'},
    'ko': {'name': 'KO', 'flag': '🇰🇷', 'code': 'ko'}
}

# Initialize kakasi once
kks = pykakasi.kakasi()


# === LANGUAGE DETECTION ===

def detect_language(text: str) -> str:
    """Auto-detect input language"""
    text = text.strip()

    vietnamese_chars = r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]'
    if re.search(vietnamese_chars, text.lower()):
        return 'vi'

    japanese_chars = r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]'
    if re.search(japanese_chars, text):
        return 'ja'

    korean_chars = r'[\uAC00-\uD7AF]'
    if re.search(korean_chars, text):
        return 'ko'

    simplified_chars = r'[\u4E00-\u9FFF]'
    traditional_chars = r'[經議調確總資國學鄰將報過進軍區劃應選國]'

    if re.search(simplified_chars, text):
        if re.search(traditional_chars, text):
            return 'zh-TW'
        else:
            return 'zh-CN'

    return 'en'


# === PHONETICS ===

async def get_english_ipa(word: str) -> str:
    """Get IPA pronunciation for English word via Free Dictionary API"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.strip()}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and len(data) > 0:
                        phonetics = data[0].get('phonetics', [])
                        for p in phonetics:
                            if p.get('text'):
                                return p['text']
    except Exception as e:
        logger.error(f"IPA fetch error: {e}")
    return None


def get_pinyin_text(text: str) -> str:
    """Get Pinyin romanization for Chinese text"""
    try:
        result = pinyin(text, style=Style.TONE)
        return ' '.join([''.join(syllables) for syllables in result])
    except Exception:
        return None


def get_romaji_text(text: str) -> str:
    """Get Romaji romanization for Japanese text"""
    try:
        result = kks.convert(text)
        romaji = ''.join([item['hepburn'] for item in result])
        return romaji if romaji.strip() else None
    except Exception:
        return None


def get_korean_romanization(text: str) -> str:
    """Get Revised Romanization for Korean text"""
    # Basic Revised Romanization of Korean mapping
    cho = ['g', 'gg', 'n', 'd', 'dd', 'r', 'm', 'b', 'bb', 's', 'ss', '', 'j', 'jj', 'ch', 'k', 't', 'p', 'h']
    jung = ['a', 'ae', 'ya', 'yae', 'eo', 'e', 'yeo', 'ye', 'o', 'wa', 'wae', 'oe', 'yo', 'u', 'wo', 'we', 'wi', 'yu', 'eu', 'ui', 'i']
    jong = ['', 'g', 'gg', 'gs', 'n', 'nj', 'nh', 'd', 'l', 'lg', 'lm', 'lb', 'ls', 'lt', 'lp', 'lh', 'm', 'b', 'bs', 's', 'ss', 'ng', 'j', 'ch', 'k', 't', 'p', 'h']

    result = []
    for char in text:
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            offset = code - 0xAC00
            cho_idx = offset // (21 * 28)
            jung_idx = (offset % (21 * 28)) // 28
            jong_idx = offset % 28
            result.append(cho[cho_idx] + jung[jung_idx] + jong[jong_idx])
        else:
            result.append(char)

    return ''.join(result) if result else None


async def get_phonetics(text: str, lang: str) -> str:
    """Get phonetics/romanization for a given language"""
    if lang == 'en':
        return await get_english_ipa(text)
    elif lang in ('zh-CN', 'zh-TW'):
        return get_pinyin_text(text)
    elif lang == 'ja':
        return get_romaji_text(text)
    elif lang == 'ko':
        return get_korean_romanization(text)
    return None


# === TRANSLATION ENGINE ===

async def translate_google(text: str, source_lang: str, target_lang: str) -> str:
    """Translate using Google Translate"""
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                'client': 'gtx',
                'sl': source_lang,
                'tl': target_lang,
                'dt': 't',
                'q': text
            }

            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and data[0]:
                        result = ''.join([seg[0] for seg in data[0] if seg[0]])
                        return result
    except Exception as e:
        logger.error(f"Google Translate error: {e}")

    return None


async def translate_mymemory(text: str, source_lang: str, target_lang: str) -> str:
    """Translate using MyMemory API (fallback)"""
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.mymemory.translated.net/get"
            params = {
                'q': text,
                'langpair': f'{source_lang}|{target_lang}'
            }

            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('responseStatus') == 200:
                        return data.get('responseData', {}).get('translatedText')
    except Exception as e:
        logger.error(f"MyMemory error: {e}")

    return None


async def translate_word(text: str, source_lang: str, target_lang: str) -> str:
    """Translate word with fallback mechanism"""
    if source_lang == target_lang:
        return text

    api_lang_map = {
        'vi': 'vi', 'en': 'en',
        'zh-CN': 'zh-CN', 'zh-TW': 'zh-TW',
        'ja': 'ja', 'ko': 'ko'
    }

    src = api_lang_map.get(source_lang, source_lang)
    tgt = api_lang_map.get(target_lang, target_lang)

    result = await translate_google(text, src, tgt)
    if not result:
        result = await translate_mymemory(text, src, tgt)

    return result or "—"


async def get_all_translations(text: str, source_lang: str) -> dict:
    """Get translations to all languages except source"""
    translations = {source_lang: text}
    target_langs = [lang for lang in LANGUAGES.keys() if lang != source_lang]

    tasks = [translate_word(text, source_lang, target_lang) for target_lang in target_langs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for target_lang, result in zip(target_langs, results):
        if isinstance(result, Exception):
            translations[target_lang] = "—"
        else:
            translations[target_lang] = result or "—"

    return translations


async def get_all_phonetics(translations: dict) -> dict:
    """Get phonetics for all languages"""
    phonetics = {}
    langs_needing_phonetics = ['en', 'zh-CN', 'zh-TW', 'ja', 'ko']

    tasks = []
    langs = []
    for lang in langs_needing_phonetics:
        text = translations.get(lang)
        if text and text != "—":
            tasks.append(get_phonetics(text, lang))
            langs.append(lang)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for lang, result in zip(langs, results):
        if not isinstance(result, Exception) and result:
            phonetics[lang] = result
            logger.info(f"Phonetic [{lang}]: {result}")
        else:
            logger.info(f"Phonetic [{lang}]: None or error — {result}")

    return phonetics


# === COMMAND HANDLERS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command"""
    welcome_text = """
🌐 *Advanced Dictionary Bot - Từ Điển Thông Minh*

Xin chào! Tôi là bot từ điển tự động dịch hỗ trợ:

🇬🇧 English \+ IPA phát âm
🇻🇳 Tiếng Việt
🇨🇳 中文简体 \+ Pinyin
🇹🇼 中文繁體 \+ Pinyin
🇯🇵 日本語 \+ Romaji
🇰🇷 한국어 \+ Romanization

*Cách sử dụng:*
Gõ từ bằng *bất kỳ ngôn ngữ nào* trên
→ Tôi sẽ tự động detect và dịch \+ phiên âm

*Ví dụ:*
📝 Gõ: `diabetes` → dịch 5 ngôn ngữ \+ IPA
📝 Gõ: `bệnh tiểu đường` → dịch sang 5 ngôn ngữ
📝 Gõ: `神经网络` → dịch \+ Pinyin
📝 Gõ: `ニューラルネットワーク` → dịch \+ Romaji
📝 Gõ: `신경망` → dịch \+ Romanization

Bắt đầu bằng cách gõ một từ\! 😊
"""
    await update.message.reply_text(welcome_text, parse_mode='MarkdownV2')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help command"""
    help_text = """
*📖 Hướng Dẫn Sử Dụng*

*Tôi tự động detect ngôn ngữ bạn nhập:*

🇻🇳 Tiếng Việt: `bánh mì`, `bệnh tiểu đường`
🇬🇧 English: `bread`, `diabetes`, `hospital`
🇨🇳 简体中文: `面包`, `糖尿病`, `医院`
🇹🇼 繁體中文: `麵包`, `糖尿病`, `醫院`
🇯🇵 日本語: `パン`, `糖尿病`, `病院`
🇰🇷 한국어: `빵`, `당뇨병`, `병원`

*Phiên âm được thêm tự động:*
🇬🇧 IPA: /breɪn/, /daɪəˈbiːtɪs/
🇨🇳 Pinyin: miàn bāo, táng niào bìng
🇯🇵 Romaji: pan, tounyoubyou
🇰🇷 RR: ppang, dangnyo-byeong

/start - Bắt đầu
/help - Trợ giúp
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text input"""
    user_input = update.message.text.strip()

    if len(user_input) < 1:
        await update.message.reply_text("⚠️ Vui lòng nhập từ hoặc cụm từ")
        return

    if len(user_input) > 200:
        await update.message.reply_text("⚠️ Quá dài, vui lòng nhập ngắn hơn (dưới 200 ký tự)")
        return

    loading_msg = await update.message.reply_text("⏳ Đang tra cứu...")

    try:
        source_lang = detect_language(user_input)
        logger.info(f"Detected language: {source_lang}")

        translations = await get_all_translations(user_input, source_lang)
        phonetics = await get_all_phonetics(translations)

        response = format_translation(user_input, source_lang, translations, phonetics)

        await loading_msg.delete()
        await update.message.reply_text(response, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error: {e}")
        await loading_msg.delete()
        await update.message.reply_text(
            f"❌ Lỗi khi tra cứu: {str(e)[:100]}\n\nVui lòng thử lại hoặc gõ /help"
        )


def format_translation(word: str, source_lang: str, translations: dict, phonetics: dict) -> str:
    """Format translation result with phonetics"""
    lines = [f"*📖 {word}*"]
    lines.append(f"_Ngôn ngữ gốc: {LANGUAGES[source_lang]['name']}_\n")

    lang_order = [source_lang] + [lang for lang in LANGUAGES.keys() if lang != source_lang]

    for i, lang in enumerate(lang_order):
        if lang not in LANGUAGES:
            continue

        lang_info = LANGUAGES[lang]
        flag = lang_info['flag']
        name = lang_info['name']
        text = translations.get(lang, '—')
        phonetic = phonetics.get(lang)

        if lang == source_lang:
            line = f"{flag} *{name}* (Gốc): *{text}*"
        else:
            line = f"{flag} *{name}*: {text}"

        if phonetic:
            line += f"\n    `{phonetic}`"

        lines.append(line)

        if i == 0:
            lines.append("")

    lines.append("\n_Powered by Google Translate_")
    return "\n".join(lines)


# ============================================================
# === MONEY CALCULATOR (bổ sung từ botstc.py) ===
# ============================================================

balance = 0


def format_money(x):
    """Format số tiền theo kiểu Việt Nam: 1000000 -> 1.000.000"""
    return format(int(x), ",").replace(",", ".")


def parse_money(text):
    """Parse chuỗi số tiền, loại bỏ dấu chấm/phẩy"""
    return float(text.replace(".", "").replace(",", "").strip())


async def handle_money(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler tính tiền: cộng (+), trừ (-), reset (#dcsd)"""
    global balance

    # Lấy text hoặc caption (hỗ trợ cả ảnh có caption)
    text = ""
    if update.message.text:
        text = update.message.text.strip()
    elif update.message.caption:
        text = update.message.caption.strip()
    else:
        return

    try:
        # Chỉ lấy dòng đầu tiên
        first_line = text.split("\n")[0].strip()

        # ➕ Cộng tiền
        if first_line.startswith("+"):
            amount = parse_money(first_line.replace("+", "").strip())
            balance += amount
            await update.message.reply_text(
                f"➕ +{format_money(amount)}\n💰 Số dư: {format_money(balance)}"
            )

        # ➖ Trừ tiền
        elif first_line.startswith("-"):
            amount = parse_money(first_line.replace("-", "").strip())
            balance -= amount
            await update.message.reply_text(
                f"➖ -{format_money(amount)}\n💰 Số dư: {format_money(balance)}"
            )

        # 🔄 Reset / đặt lại số dư: #dcsd <số>
        elif first_line.startswith("#dcsd"):
            parts = first_line.split()
            if len(parts) == 2:
                balance = parse_money(parts[1])
                await update.message.reply_text(
                    f"🔄 Reset số dư: {format_money(balance)}"
                )
            else:
                await update.message.reply_text("❌ Dùng đúng: #dcsd 100")

    except Exception as e:
        logger.error(f"Money handler error: {e}")
        await update.message.reply_text("❌ Sai định dạng tiền")


def main() -> None:
    """Start the bot"""
    TOKEN = "8639657231:AAGUn7LpYe5AHOVTKiRiFV-1CKgZaR4pPt0"

    if not TOKEN or TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Vui lòng đặt Telegram bot token!")
        return

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # === Handler tính tiền (đăng ký TRƯỚC handler dịch) ===
    # Chỉ bắt tin nhắn (text hoặc caption) bắt đầu bằng +, -, hoặc #dcsd
    money_pattern = r'^\s*([+\-]|#dcsd)'
    money_filter = (
        filters.Regex(money_pattern)
        | filters.CaptionRegex(money_pattern)
    )
    application.add_handler(
        MessageHandler(money_filter & ~filters.COMMAND, handle_money)
    )

    # Handler dịch — chạy SAU money_filter, chỉ áp dụng cho text còn lại
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Bot is running...")
    print("💡 Nhập /start để test bot dịch")
    print("💡 Gõ +1000 / -500 / #dcsd 0 để dùng bot tính tiền")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
