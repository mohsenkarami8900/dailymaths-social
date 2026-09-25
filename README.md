# Daily Maths UK – ربات اینستاگرام و فیسبوک

ساعت **۴ عصر به وقت انگلستان** این‌ها خودکار منتشر می‌شن:

| روز | چی |
|---|---|
| هر روز | استوری ویدیویی (سؤال، شمارش معکوس، جواب و جشن) |
| دوشنبه، چهارشنبه، جمعه | پست ۶ صفحه‌ای: ۵ معما (KS1 تا GCSE Higher) و صفحه‌ی جواب‌ها |
| سه‌شنبه، پنج‌شنبه، شنبه | Reel (همون ویدیوی شمارش معکوس) |

**ربات کامنت** هر ۳۰ دقیقه کامنت‌ها رو بررسی می‌کنه:
- جواب درست: لایک و 👏
- جواب اشتباه: «Have another go 💪»
- کامنت نامربوط: کاری نمی‌کنه

**هشدارها** توی تلگرام به خود شما می‌رسه: اگه انتشار خطا داشت، یا کلید Meta نیاز به تمدید داشت.

---

## راه‌اندازی (یک بار)
1. **آپلود فایل‌ها** در مخزن عمومی `dailymaths-social`: همه‌ی فایل‌ها و پوشه‌های `fonts`، `assets` و `data` رو آپلود کنید (پوشه‌ی `workflows-for-github` لازم نیست).
2. **فایل‌های زمان‌بندی:** دو فایل بسازید با **Add file ← Create new file**:
   - `.github/workflows/publish.yml` با محتوای `workflows-for-github/publish.yml`
   - `.github/workflows/comments.yml` با محتوای `workflows-for-github/comments.yml`
3. **Settings ← Pages ← Build and deployment ← Source:** گزینه‌ی **GitHub Actions** رو انتخاب کنید.
4. **Secrets** (Settings ← Secrets and variables ← Actions): `META_PAGE_TOKEN`، `TELEGRAM_BOT_TOKEN` و `TELEGRAM_ALERT_CHAT_ID`.
5. **Settings ← Actions ← General ← Workflow permissions:** گزینه‌ی **Read and write permissions**.

## تست
- **پیش‌نمایش (چیزی منتشر نمی‌شه):** Actions ← **Publish to Instagram & Facebook** ← Run workflow. تیک **dry_run** روشن باشه. نمونه‌ها توی تلگرام برای شما میاد.
- **انتشار واقعی:** همین کار، ولی **dry_run** خاموش و `kinds` = `story`.

## تمدید کلید (هر ۳ ماه، ربات دو هفته قبلش خبر می‌ده)
1. Graph API Explorer ← **User Token** ← Generate Access Token
2. ⓘ ← Open in Access Token Tool ← **Extend Access Token** ← کلید تمدیدشده رو توی Explorer بذارید.
3. User or Page ← **Daily Maths UK** ← کلید رو کپی کنید.
4. توی Debugger چک کنید: Type = Page و Expires = Never.
5. گیت‌هاب ← `META_PAGE_TOKEN` ← ✏️ ← paste ← Update secret

## فایل‌ها
- `content.py`: بانک سؤال‌ها (جواب‌ها رو خود برنامه حساب می‌کنه) و کپشن‌ها و هشتگ‌ها
- `render.py`: ساخت ویدیو و اسلایدها
- `run_publish.py`: انتشار روزانه
- `run_comments.py` و `checker.py`: ربات کامنت
- `meta.py`: ارتباط با اینستاگرام، فیسبوک و تلگرام
- `data/`: وضعیت ربات. خودکار به‌روز می‌شه، دست نزنید.
