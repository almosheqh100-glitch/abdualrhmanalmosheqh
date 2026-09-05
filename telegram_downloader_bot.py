#!/usr/bin/env python3
"""
بوت تلجرام لتحميل فيديوهات من يوتيوب وتيك توك
=================================================

المتطلبات (نزّلها أولاً):
    pip install python-telegram-bot==21.6 yt-dlp

كما تحتاج FFmpeg مثبتاً على جهازك (لدمج الصوت مع الفيديو):
    - ويندوز: نزّل من ffmpeg.org وأضفه إلى PATH
    - لينكس: sudo apt install ffmpeg
    - ماك: brew install ffmpeg

طريقة الحصول على توكن البوت:
    1) افتح تلجرام وابحث عن @BotFather
    2) أرسل /newbot واتبع التعليمات
    3) احصل على التوكن وضعه في المتغير BOT_TOKEN أدناه
       (أو عرّفه كمتغير بيئة TELEGRAM_BOT_TOKEN)

تنبيه مهم:
    احترم حقوق الملكية الفكرية وشروط استخدام المنصات. استخدم هذا
    البوت لتحميل محتواك الخاص أو محتوى مسموح بتحميله فقط.
"""

import os
import re
import logging
import asyncio
from pathlib import Path

from dotenv import load_dotenv
import yt_dlp
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---------------------------------------------------------------------------
# الإعدادات
# ---------------------------------------------------------------------------

# يقرأ المتغيرات من ملف .env المحلي إن وُجد (لا يُرفع على GitHub أبداً)
load_dotenv()

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "ضع_التوكن_هنا")

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# لو ملف cookies.txt موجود بنفس مجلد المشروع، نستخدمه للتحقق مع يوتيوب
# (يقلل من رسائل "سجّل الدخول لتأكيد أنك لست روبوتًا")
COOKIES_FILE = Path("cookies.txt")

# الحد الأقصى لحجم الملف الذي يمكن للبوت إرساله (تلجرام يسمح بـ 50MB للبوتات العادية)
MAX_FILE_SIZE_MB = 50

# قائمة بذاكرة البوت (مو دائمة) بمعرّفات كل مستخدم تفاعل مع البوت،
# تُستخدم لأمر /stats. تتصفّر مع كل إعادة نشر للبوت.
KNOWN_USERS: set[int] = set()


def _track_user(update: Update) -> None:
    """يسجّل معرّف المستخدم في KNOWN_USERS ويطبع سطر بالسجلات لو كان جديداً."""
    user = update.effective_user
    if user is None:
        return
    if user.id not in KNOWN_USERS:
        KNOWN_USERS.add(user.id)
        logger.info(
            "مستخدم جديد انضم ✅ | id: %s | اسم المستخدم: %s | إجمالي المستخدمين: %d",
            user.id, user.username or "-", len(KNOWN_USERS),
        )

URL_PATTERN = re.compile(
    r"(https?://)?(www\.)?"
    r"(youtube\.com|youtu\.be|tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)"
    r"/\S+",
    re.IGNORECASE,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# دوال مساعدة
# ---------------------------------------------------------------------------

def extract_url(text: str) -> str | None:
    """يستخرج أول رابط يوتيوب/تيك توك من نص الرسالة."""
    match = URL_PATTERN.search(text)
    return match.group(0) if match else None


# ترتيب المحاولات: أول شي أعلى جودة متوفرة، وبعدين نزول تدريجي بالجودة
# لو الملف طلع أكبر من الحد المسموح. القيمة None تعني "بدون تحديد ارتفاع"
# (أعلى جودة ممكنة).
QUALITY_LADDER = [None, 720, 480, 360]


def _format_for_height(height: int | None) -> str:
    if height is None:
        return "bestvideo+bestaudio/best"
    return (
        f"bestvideo[height<={height}]+bestaudio/"
        f"best[height<={height}]"
    )


def download_video(url: str, unique_id: str, height: int | None = None) -> Path:
    """
    يحمّل الفيديو باستخدام yt-dlp ويعيد مسار الملف الناتج.
    يتم تشغيلها في خيط منفصل (بما أنها عملية متزامنة/بطيئة).
    """
    output_template = str(DOWNLOAD_DIR / f"{unique_id}.%(ext)s")

    ydl_opts = {
        "format": _format_for_height(height),
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # ملاحظة: ما نحط حد أقصى للحجم هنا (max_filesize) لأنه يخلي yt-dlp
        # يفشل باختيار الصيغة المناسبة لبعض الفيديوهات. الفحص الفعلي
        # لحجم الملف يصير بعد التحميل في handle_message، مع إعادة محاولة
        # بجودة أقل عبر QUALITY_LADDER لو الملف كبير.
    }

    if COOKIES_FILE.exists():
        ydl_opts["cookiefile"] = str(COOKIES_FILE)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    # بعد الدمج (merge) قد يتغيّر امتداد الملف النهائي (مثلاً .mkv بدل .mp4)
    # عن الاسم اللي رجعه prepare_filename قبل الدمج، فنبحث عن الملف الفعلي.
    expected = Path(filename)
    if expected.exists():
        return expected

    for candidate in DOWNLOAD_DIR.glob(f"{unique_id}.*"):
        return candidate

    return expected


# ---------------------------------------------------------------------------
# معالجات الأوامر والرسائل
# ---------------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _track_user(update)
    await update.message.reply_text(
        "👋 أهلاً بك!\n\n"
        "أرسل لي رابط فيديو من *يوتيوب* أو *تيك توك* وسأقوم بتحميله لك.\n\n"
        "مثال:\n"
        "https://www.tiktok.com/@user/video/1234567890\n"
        "https://www.youtube.com/watch?v=xxxxxxxx\n\n"
        f"👥 عدد المستخدمين الحالي: {len(KNOWN_USERS)}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _track_user(update)
    await update.message.reply_text(
        "الأوامر المتاحة:\n"
        "/start - رسالة الترحيب\n"
        "/help - عرض هذه الرسالة\n"
        "/stats - عدد المستخدمين الحاليين\n\n"
        "فقط أرسل رابط فيديو من يوتيوب أو تيك توك وسأتولى الباقي."
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _track_user(update)
    await update.message.reply_text(
        f"👥 عدد المستخدمين الحالي: {len(KNOWN_USERS)}\n\n"
        "(هذا العدد يُحسب منذ آخر تشغيل للبوت، ويتصفّر مع كل تحديث جديد له)"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _track_user(update)
    text = update.message.text or ""
    url = extract_url(text)

    if not url:
        await update.message.reply_text(
            "لم أجد رابط يوتيوب أو تيك توك صالح في رسالتك. حاول مرة أخرى."
        )
        return

    status_msg = await update.message.reply_text("⏳ جاري التحميل، الرجاء الانتظار...")

    unique_id = f"{update.effective_user.id}_{update.message.message_id}"
    file_path: Path | None = None

    try:
        # نجرب من أعلى جودة لأقل جودة (QUALITY_LADDER) لين ما نلقى حجم
        # يصير تحت الحد المسموح لإرساله عبر البوت.
        for attempt_index, height in enumerate(QUALITY_LADDER):
            # نحذف نتيجة المحاولة السابقة (لو كانت كبيرة) قبل إعادة المحاولة
            if file_path is not None:
                file_path.unlink(missing_ok=True)
                await status_msg.edit_text(
                    f"⏳ الفيديو كبير، جاري إعادة التحميل بجودة أقل "
                    f"({height}p)..."
                )

            # تشغيل التحميل في خيط منفصل حتى لا يتوقف البوت عن العمل أثناءه
            file_path = await asyncio.to_thread(download_video, url, unique_id, height)

            if not file_path.exists():
                await status_msg.edit_text("❌ فشل التحميل. تأكد من صحة الرابط.")
                return

            file_size_mb = file_path.stat().st_size / (1024 * 1024)

            if file_size_mb <= MAX_FILE_SIZE_MB:
                break  # الحجم مناسب، نكمل للإرسال

            is_last_attempt = attempt_index == len(QUALITY_LADDER) - 1
            if is_last_attempt:
                await status_msg.edit_text(
                    f"⚠️ حجم الفيديو ({file_size_mb:.1f}MB) أكبر من الحد المسموح "
                    f"({MAX_FILE_SIZE_MB}MB) لإرساله عبر البوت، حتى بعد تقليل "
                    f"الجودة لأقل مستوى ({QUALITY_LADDER[-1]}p)."
                )
                file_path.unlink(missing_ok=True)
                return

        await status_msg.edit_text("📤 جاري الإرسال...")

        with open(file_path, "rb") as video_file:
            await update.message.reply_video(
                video=video_file,
                caption="✅ تم التحميل بنجاح",
                supports_streaming=True,
            )

        await status_msg.delete()

    except yt_dlp.utils.DownloadError as e:
        logger.error("خطأ تحميل: %s", e)
        await status_msg.edit_text(
            "❌ تعذّر تحميل هذا الفيديو. قد يكون الرابط خاطئاً أو المحتوى محمياً/محذوفاً."
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("خطأ غير متوقع")
        await status_msg.edit_text(f"❌ حدث خطأ غير متوقع: {e}")
    finally:
        # تنظيف الملف بعد الإرسال
        try:
            if file_path is not None and file_path.exists():
                file_path.unlink()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# نقطة التشغيل
# ---------------------------------------------------------------------------

def main() -> None:
    if BOT_TOKEN == "ضع_التوكن_هنا":
        raise SystemExit(
            "الرجاء وضع توكن البوت في المتغير BOT_TOKEN أو في متغير البيئة "
            "TELEGRAM_BOT_TOKEN قبل التشغيل."
        )

    # تشخيص: نتأكد من وجود ملف الكوكيز ونطبع تفاصيله بالسجلات لتشخيص
    # مشاكل التحقق من يوتيوب بسهولة (بدون الحاجة لفتح وحدة التحكم).
    if COOKIES_FILE.exists():
        size = COOKIES_FILE.stat().st_size
        with open(COOKIES_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        non_comment_lines = [ln for ln in lines if ln.strip() and not ln.startswith("#")]
        logger.info(
            "cookies.txt موجود ✅ | الحجم: %d بايت | عدد الأسطر الكلي: %d | "
            "عدد أسطر الكوكيز الفعلية: %d",
            size, len(lines), len(non_comment_lines),
        )
    else:
        logger.warning("cookies.txt غير موجود ❌ (البحث في: %s)", COOKIES_FILE.resolve())

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("البوت يعمل الآن...")
    app.run_polling()


if __name__ == "__main__":
    main()
