# نقشه راه و معماری — اپ زیرنویس خودکار (مشابه Capzy)

## ۱. استک پیشنهادی
| لایه | انتخاب | دلیل |
|---|---|---|
| موبایل | React Native + Expo (یا Flutter) | یک کدبیس برای iOS/Android، `expo-av` برای پخش، `expo-camera` برای ضبط |
| وب (اختیاری) | Next.js + Remotion/Canvas برای پیش‌نمایش | اشتراک منطق استایل با موبایل |
| بک‌اند API | FastAPI (Python) | اکوسیستم AI پایتون |
| صف کار | Celery/RQ + Redis | پردازش سنگین نباید در request باشد |
| Speech-to-Text | **faster-whisper (large-v3)** روی GPU | دقت بالا، فارسی، word timestamps |
| همگام‌سازی دقیق‌تر | WhisperX (wav2vec2 forced alignment) | دقت زمانی کلمه‌ها بهتر؛ برای فارسی مدل alignment موجود است |
| رندر ویدیو | FFmpeg + libass (فایل ASS) | سریع، پایدار، انیمیشن و RTL |
| ذخیره‌سازی | S3 / R2 + CDN، Postgres برای متادیتا | |
| GPU | RunPod / Modal / AWS g5 | پرداخت به‌ازای مصرف |
| API جایگزین STT | OpenAI/Deepgram/AssemblyAI | شروع سریع بدون مدیریت GPU |

## ۲. پردازش: کلاینت یا سرور؟
**ترکیبی (پیشنهاد):**
- **سرور:** تشخیص گفتار + رندر نهایی (Whisper و FFmpeg روی موبایل سنگین/کند هستند).
- **کلاینت:** پیش‌نمایش زنده زیرنویس (overlay روی پلیر)، ویرایش متن و استایل؛ فقط `captions.json` + `style.json` رد و بدل می‌شود.
- **بهینه‌سازی:** قبل از آپلود، ویدیو را روی موبایل فشرده کنید یا فقط صوت (۱۶kHz mono) را برای STT بفرستید؛ ویدیوی اصلی جداگانه آپلود شود.
- **آینده:** رندر محلی با `ffmpeg-kit` یا Skia برای حالت آفلاین.

## ۳. جریان داده
```
Upload → S3 → Job(extract audio) → Whisper(word timestamps) → captions.json
   → Editor (edit text/style, live preview) → Export job → ASS + FFmpeg burn → mp4 → CDN
```

## ۴. مدل داده (خلاصه)
`users`, `videos(id, user_id, src_url, duration, lang)`, `caption_sets(video_id, words_json, version)`,
`style_presets(user_id, json)`, `jobs(type, status, progress, error)`.

## ۵. نکات مهم فارسی
- فونت‌های دارای پشتیبانی فارسی (Vazirmatn، Shabnam، Estedad) را در `fonts/` بگذارید.
- libass شکل‌دهی حروف و RTL را انجام می‌دهد؛ کلمات را به ترتیب **منطقی** بدهید (نه معکوس).
- افکت `\kf` (کارائوکه) در RTL ممکن است جهت پر شدن را معکوس نشان دهد؛ برای فارسی انیمیشن `pop` امن‌تر است یا باید تگ‌ها را برای RTL تنظیم کنید.
- مدل Whisper گاهی نیم‌فاصله و ویرایش نگارشی را درست نمی‌گذارد؛ یک مرحله پس‌پردازش (نرمال‌سازی با `hazm`) اضافه کنید.
- `vad_filter=True` توهم‌های مدل (متن در سکوت) را کم می‌کند.

## ۶. مراحل اجرا
**فاز ۰ (۱ هفته):** راه‌اندازی ریپو، FastAPI، تست Whisper روی چند ویدیوی فارسی، سنجش WER و دقت زمان‌بندی.
**فاز ۱ — MVP (۳–۴ هفته):** آپلود، تشخیص گفتار، ویرایش متن، یک استایل، خروجی hardcoded (کدهای همین پوشه).
**فاز ۲ (۳ هفته):** استایل‌ها و انیمیشن‌ها (کارائوکه، پاپ‌آپ)، پریست، تغییر فونت/رنگ/موقعیت، ایموجی، highlight کلمات کلیدی.
**فاز ۳ (۳ هفته):** احراز هویت، پروژه‌ها، پرداخت/اشتراک (Stripe/زرین‌پال)، صف و پیشرفت لحظه‌ای (WebSocket/SSE)، نوتیفیکیشن.
**فاز ۴:** ترجمه زیرنویس (LLM)، حذف سکوت (auto-cut)، B-roll، دوبله، برندینگ، اپ وب، تحلیلات.
**زیرساخت:** Docker، CI/CD، مانیتورینگ (Sentry)، محدودیت طول ویدیو، پاک‌سازی خودکار فایل‌ها، رعایت حریم خصوصی.

## ۷. اجرای کد نمونه
```bash
cd backend
pip install fastapi uvicorn python-multipart faster-whisper
# ffmpeg را نصب کنید و فونت Vazirmatn را در backend/fonts قرار دهید
uvicorn main:app --host 0.0.0.0 --port 8000
```
موبایل: `npx create-expo-app app`، سپس `SubtitleEditor.tsx` را در `App.tsx` import کنید و آدرس `API` را عوض کنید.

## ۸. ریسک‌ها
- هزینه GPU → صف، batching، مدل `medium`/`turbo` برای کاربران رایگان.
- تأخیر آپلود ویدیوهای بزرگ → آپلود chunked/resumable (tus).
- دقت زمان‌بندی فارسی → WhisperX + ویرایش دستی روی تایم‌لاین.
- مجوزها: فونت‌ها و مدل‌ها را از نظر لایسنس بررسی کنید.
