# بوت تلجرام لتحميل فيديوهات يوتيوب وتيك توك

## المتطلبات
- Python 3.10+
- FFmpeg مثبت على الجهاز

## التثبيت

```bash
git clone <رابط_المستودع>
cd <اسم_المجلد>
pip install -r requirements.txt
```

## إعداد التوكن (بدون كشفه على GitHub)

1. انسخ ملف `.env.example` إلى ملف جديد اسمه `.env`:
```bash
cp .env.example .env
```

2. افتح ملف `.env` وضع توكنك الحقيقي بدل النص التجريبي:
```
TELEGRAM_BOT_TOKEN=123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
```

3. ملف `.env` مُستثنى تلقائياً في `.gitignore`، يعني حتى لو نسيت ما راح يترفع مع الكود على GitHub.

> ملاحظة: طريقة `export TELEGRAM_BOT_TOKEN="..."` في التيرمنال ما زالت تشتغل أيضاً إذا ما تبي تستخدم ملف `.env` — البوت يقرأ من متغيرات البيئة بأي الحالتين.

## التشغيل

```bash
python telegram_downloader_bot.py
```

## رفع المشروع على GitHub

```bash
git init
git add .
git commit -m "أول نسخة من البوت"
git branch -M main
git remote add origin <رابط_مستودعك_على_GitHub>
git push -u origin main
```

تأكد قبل الـ push إن `.env` غير موجود ضمن الملفات اللي بترفعها:
```bash
git status
```
لو ظهر `.env` في القائمة، يعني `.gitignore` ما اشتغل صح — تأكد إن اسمه بالضبط `.gitignore` وموجود بنفس مجلد المشروع.

## تنبيه
احترم حقوق الملكية الفكرية وشروط استخدام المنصات عند استخدام هذا البوت.
