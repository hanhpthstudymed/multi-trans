# 🤖 HƯỚNG DẪN DEPLOY TELEGRAM BOT TRÊN REPLIT

## 📋 BƯỚC 1: TẠO EMPTY PROJECT TRÊN REPLIT

1. Vào https://replit.com
2. Nhấn **"Create empty project"** (nút xanh dương)
3. Chọn **Python** → Project tự động tạo

## 📋 BƯỚC 2: TẠO FILE TẢI LÊN

### Tạo file `main.py`
1. Click **"New file"** (góc trái)
2. Đặt tên: `main.py`
3. Copy toàn bộ code bot vào (xem phần TELEGRAM BOT CODE bên dưới)

### Tạo file `requirements.txt`
1. Click **"New file"** → Đặt tên: `requirements.txt`
2. Dán nội dung:
```
python-telegram-bot>=20.0
aiohttp>=3.8.0
```

### Tạo file `.env`
1. Click **"New file"** → Đặt tên: `.env`
2. Dán nội dung (thay TOKEN của bạn):
```
TELEGRAM_BOT_TOKEN=123456789:ABCDEFGHIJKLMNOPQRSTUVwxyz
```

## 📋 BƯỚC 3: CHỈNH SỬA CODE

Trong file `main.py`, tìm dòng:
```python
TOKEN = "YOUR_BOT_TOKEN_HERE"
```

Thay thành:
```python
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
```

## 📋 BƯỚC 4: THÊM dotenv

1. Click **".replit"** file (nếu có)
2. Hoặc thêm vào `requirements.txt`:
```
python-telegram-bot>=20.0
aiohttp>=3.8.0
python-dotenv>=0.19.0
```

## 📋 BƯỚC 5: CHẠY BOT

1. Nhấn nút **"RUN"** (xanh dương, góc trên)
2. Chờ tải dependencies (~30 giây)
3. Console hiện: `🤖 Bot is running...`
4. ✅ Bot chạy thành công!

## 📋 BƯỚC 6: TEST BOT

1. Mở Telegram
2. Tìm bot của bạn (username bot)
3. Gõ `/start` 
4. Thử: `bread`, `diabetes`, `bánh mì`

## 🔧 TROUBLESHOOTING

### Lỗi: "ModuleNotFoundError: No module named 'telegram'"
→ Chờ dependencies cài xong (30 giây), rồi click RUN lại

### Lỗi: "TELEGRAM_BOT_TOKEN is not set"
→ Kiểm tra file `.env` có đúng format không

### Bot không response
→ Kiểm tra console có lỗi gì không

## 💡 LƯU Ý

- Replit bot chạy **24/7 miễn phí**
- Nếu máy ngủ 1 tiếng, Replit sẽ pause bot → nhấn RUN lại
- Để bot chạy luôn, upgrade Replit Core ($7/tháng) hoặc keep tab open

## 📱 SAU KHI DEPLOY THÀNH CÔNG

Bot sẽ:
- ✅ Nhập tiếng Anh → dịch 5 ngôn ngữ
- ✅ Nhập tiếng Việt → dịch 5 ngôn ngữ
- ✅ Nhập tiếng Trung → dịch 5 ngôn ngữ
- ✅ Nhập tiếng Nhật → dịch 5 ngôn ngữ
- ✅ Nhập tiếng Hàn → dịch 5 ngôn ngữ

---

# 🤖 TELEGRAM BOT CODE

Copy toàn bộ code này vào file `main.py`:

```python
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
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables
load_dotenv()

# === LOGGING ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === LANGUAGE CONFIG ===
LANGUAGES = {
    'en': {'name': 'English', 'flag': '🇬🇧', 'code': 'en'},
    'vi': {'name': 'Tiếng Việt', 'flag': '🇻🇳', 'code': 'vi'},
    'zh-CN': {'name': '简体中文', 'flag': '🇨🇳', 'code': 'zh-CN'},
    'zh-TW': {'name': '繁體中文', 'flag': '🇹🇼', 'code': 'zh-TW'},
    'ja': {'name': '日本語', 'flag': '🇯🇵', 'code': 'ja'},
    'ko': {'name': '한국어', 'flag': '🇰🇷', 'code': 'ko'}
}

# === LANGUAGE DETECTION ===

def detect_language(text: str) -> str:
    """Auto-detect input language"""
    text = text.strip()
    
    # Vietnamese detection - check for Vietnamese diacritics
    vietnamese_chars = r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]'
    if re.search(vietnamese_chars, text.lower()):
        return 'vi'
    
    # Japanese detection - Hiragana, Katakana, Kanji
    japanese_chars = r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]'
    if re.search(japanese_chars, text):
        return 'ja'
    
    # Korean detection - Hangul
    korean_chars = r'[\uAC00-\uD7AF]'
    if re.search(korean_chars, text):
        return 'ko'
    
    # Simplified Chinese detection
    simplified_chars = r'[\u4E00-\u9FFF]'
    traditional_chars = r'[經議調確總資國學鄰將報過進軍區劃應選國]'
    
    if re.search(simplified_chars, text):
        # Try to distinguish between Simplified and Traditional
        if re.search(traditional_chars, text):
            return 'zh-TW'
        else:
            return 'zh-CN'
    
    # English detection (default fallback)
    return 'en'


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
    # Skip if source and target are same
    if source_lang == target_lang:
        return text
    
    # Map language codes for APIs
    api_lang_map = {
        'vi': 'vi',
        'en': 'en',
        'zh-CN': 'zh-CN',
        'zh-TW': 'zh-TW',
        'ja': 'ja',
        'ko': 'ko'
    }
    
    src = api_lang_map.get(source_lang, source_lang)
    tgt = api_lang_map.get(target_lang, target_lang)
    
    # Try Google Translate first
    result = await translate_google(text, src, tgt)
    
    # Fallback to MyMemory
    if not result:
        result = await translate_mymemory(text, src, tgt)
    
    return result or "—"


async def get_all_translations(text: str, source_lang: str) -> dict:
    """Get translations to all languages except source"""
    translations = {source_lang: text}
    
    # Translate to all other languages
    tasks = []
    target_langs = [lang for lang in LANGUAGES.keys() if lang != source_lang]
    
    for target_lang in target_langs:
        task = translate_word(text, source_lang, target_lang)
        tasks.append((target_lang, task))
    
    # Run all translations concurrently
    for target_lang, task in tasks:
        try:
            result = await task
            translations[target_lang] = result
        except Exception as e:
            logger.error(f"Translation error for {target_lang}: {e}")
            translations[target_lang] = "—"
    
    return translations


# === COMMAND HANDLERS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command"""
    welcome_text = """
🌐 *Advanced Dictionary Bot - Từ Điển Thông Minh*

Xin chào! Tôi là bot từ điển tự động dịch hỗ trợ:

🇬🇧 English
🇻🇳 Tiếng Việt
🇨🇳 中文简体 (Simplified Chinese)
🇹🇼 中文繁體 (Traditional Chinese)
🇯🇵 日本語 (Japanese)
🇰🇷 한국어 (Korean)

*Cách sử dụng:*
Gõ từ bằng *bất kỳ ngôn ngữ nào* trên
→ Tôi sẽ tự động detect và dịch sang 5 ngôn ngữ còn lại

*Ví dụ:*
📝 Gõ: `diabetes` (Tiếng Anh)
📝 Gõ: `bệnh tiểu đường` (Tiếng Việt)
📝 Gõ: `神经网络` (Tiếng Trung)
📝 Gõ: `ニューラルネットワーク` (Tiếng Nhật)
📝 Gõ: `신경망` (Tiếng Hàn)

*Tính năng:*
✅ Tự động detect ngôn ngữ input
✅ Dịch sang 5 ngôn ngữ khác
✅ Dùng Google Translate - chính xác cao
✅ Nhanh và thông minh

Bắt đầu bằng cách gõ một từ! 😊
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')


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

*Kết quả tra cứu:*
Tôi sẽ hiển thị dịch sang 5 ngôn ngữ còn lại

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
    
    # Show loading
    loading_msg = await update.message.reply_text("⏳ Đang tra cứu...")
    
    try:
        # Detect source language
        source_lang = detect_language(user_input)
        logger.info(f"Detected language: {source_lang}")
        
        # Get all translations
        translations = await get_all_translations(user_input, source_lang)
        
        # Format response
        response = format_translation(user_input, source_lang, translations)
        
        # Delete loading message and send result
        await loading_msg.delete()
        await update.message.reply_text(response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await loading_msg.delete()
        await update.message.reply_text(
            f"❌ Lỗi khi tra cứu: {str(e)[:100]}\n\n"
            f"Vui lòng thử lại hoặc gõ /help",
            parse_mode='Markdown'
        )


def format_translation(word: str, source_lang: str, translations: dict) -> str:
    """Format translation result"""
    lines = [f"*📖 {word}*"]
    lines.append(f"_Ngôn ngữ gốc: {LANGUAGES[source_lang]['name']}_\n")
    
    # Order: source first, then all others
    lang_order = [source_lang] + [lang for lang in LANGUAGES.keys() if lang != source_lang]
    
    for i, lang in enumerate(lang_order):
        if lang not in LANGUAGES:
            continue
        
        lang_info = LANGUAGES[lang]
        flag = lang_info['flag']
        name = lang_info['name']
        text = translations.get(lang, '—')
        
        # Mark source language
        if lang == source_lang:
            lines.append(f"{flag} *{name}* (Gốc): *{text}*")
        else:
            lines.append(f"{flag} *{name}*: {text}")
        
        if i == 0:  # Add separator after source language
            lines.append("")
    
    # Add footer
    lines.append("\n_Powered by Google Translate_")
    
    return "\n".join(lines)


def main() -> None:
    """Start the bot"""
    # Get token from environment variable
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not TOKEN:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN environment variable not set!")
        print("Please set it in .env file")
        return
    
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Run the bot
    print("🤖 Bot is running...")
    print("💡 Send /start to test the bot")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
```

---

## ✅ XÓA BƯỚC HOÀN THÀNH

1. ✅ Tạo 3 file: `main.py`, `requirements.txt`, `.env`
2. ✅ Copy code vào `main.py`
3. ✅ Thêm token vào `.env`
4. ✅ Nhấn RUN → Bot chạy!

## 🎉 HOÀN THÀNH!

Bot của bạn sẽ chạy **24/7 miễn phí trên Replit**!
