# 🤖 LinkedIn AI Job Hunter Agent (وكيل التوظيف الذكي على تيليجرام)

وكيل ذكاء اصطناعي يعمل **24 ساعة يومياً** عبر **GitHub Actions (مجاناً 100%)** للبحث عن أحدث الوظائف على **LinkedIn** فور نزولها (`sortBy=DD`)، وفلترتها بدقة حسب المسميات الـ 14 والقطاعات الـ 4 ومقر الشركة في **الرياض**، مع إعطاء **الأولوية القصوى لشركات الـ Tech**، وحساب **نسبة التوافق الحقيقية مع الـ CV** عبر Gemini، وإرسال تفاصيل الوظيفة كاملة مباشرة إلى **تيليجرام**.

---

## 🎯 معايير الفلترة والمطابقة

1. **المسميات المستهدفة (والقريبة منها):**
   - Senior Account Management & Customer Success Manager
   - Senior Sales Account Manager / Senior Account Manager / Senior Account Management
   - Sales Team Lead / Sales Team Leader / Sales Supervisor
   - Account Manager Team Leader / Account Manager Team Lead / Account Management Team Lead
   - Business Development Team Lead
   - Head of Customer Experience
   - Sales Retention Team Lead
   - Senior Customer Success Specialist
2. **القطاعات الـ 4 المسموحة حصراً (مع أولوية قصوى للـ Tech):**
   - 🔥 **Tech Priority:** `Software Development`, `Information Technology & Services`, `Technology, Information and Internet`
   - 📊 `Accounting`
3. **مقر صفحة الشركة على LinkedIn:** `Riyadh` حصراً.
4. **محتوى رسالة تيليجرام:** اسم الوظيفة، الشركة، القطاع، مقر الشركة، موقع الوظيفة، نوع الدوام والمستوى، نسبة التوافق الحقيقية مع الـ CV، المهارات المتطابقة، تحليل الذكاء الاصطناعي، الوصف الوظيفي الكامل، وزر التقديم المباشر.

---

## ⚡ التشغيل على GitHub كل دقائق بدون تأخير 24/7 (مجاني)

> **ملاحظة مهمة حول GitHub Actions `schedule`:**
> جداول `cron` المدمجة في GitHub Actions قد تتأخر من 15 دقيقة إلى عدة ساعات أحياناً وقت الضغط.
> لذلك يدعم الـ Workflow التشغيل عبر `repository_dispatch` + فحص سريع متتابع كل **90 ثانية** (`--poll-minutes 3 --interval-seconds 90`).

### لتشغيله بشكل منتظم كل 5 دقائق 24/7 مجاناً (بدون أي تأخير من GitHub):
استخدم ملف [`cloudflare_worker.js`](cloudflare_worker.js) على حساب Cloudflare المجاني (100,000 تشغيل/يوم مجاناً):
1. أنشئ Worker جديد على [Cloudflare Dashboard](https://dash.cloudflare.com) والصق كود `cloudflare_worker.js`.
2. أضف متغير سري (Secret) باسم `GITHUB_TOKEN` (GitHub Personal Access Token بصلاحية `repo`).
3. من **Settings → Triggers → Cron Triggers** أضف الجدول: `*/5 * * * *`.
4. تأكد من وجود الأسرار الآتية في إعدادات مستودع GitHub (`Settings → Secrets and variables → Actions`):
   - `GEMINI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

---

## 💻 أوامر التشغيل المحلي

```bash
# 1. اختبار رسالة تيليجرام الآن
./run.sh --test-telegram

# 2. تحديث قراءة السيرة الذاتية
./run.sh --parse-cv

# 3. تشغيل دورة فحص واحدة الآن
./run.sh --run-once

# 4. تشغيل فحص سريع متكرر كل 90 ثانية لمدة 3 دقائق
./run.sh --poll-minutes 3 --interval-seconds 90

# 5. تشغيل مستمر 24/7 على جهازك
./run.sh --schedule

# 6. عرض الإحصائيات
./run.sh --status
```
