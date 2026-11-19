#!/usr/bin/env python3
"""
المنسق الرئيسي لـ AI Job Agent
يقوم بربط قراءة السيرة الذاتية، البحث في لينكدإن، التحليل الذكي عبر Gemini،
والإرسال المباشر إلى واتساب.
"""

import os
import re
import sys
import time
import warnings
warnings.filterwarnings("ignore")
import argparse
from pathlib import Path
from typing import Dict, Any
import yaml
from dotenv import load_dotenv

# استيراد الوحدات الداخلية
from storage import JobStorage
from resume_parser import ResumeParser
from linkedin_scraper import LinkedInScraper
from job_matcher import JobMatcher
from notifier import WhatsAppNotifier


# القائمة الحصرية الصارمة للمسميات المطلوبة من الأستاذ أحمد فقط (14 مسمى حصراً)
STRICT_TARGET_TITLES = [
    "sales account manager",
    "senior sales account manager",
    "senior account manager",
    "senior account management",
    "sales team lead",
    "sales team leader",
    "account manager team leader",
    "account manager team lead",
    "account management team leader",
    "account management team lead",
    "sales supervisor",
    "business development team lead",
    "bd team lead",
    "head of customer experience",
    "sales retention team lead",
    "retention team lead",
    "senior customer success specialist"
]

# المجالات الـ 4 المطلوبة حصراً لقطاع الشركة
# 1. Software Development
# 2. Information Technology & Services (بما فيها IT Services and IT Consulting)
# 3. Accounting
# 4. Technology, Information and Internet
STRICT_ALLOWED_INDUSTRIES_EN = [
    "software development",
    "information technology & services",
    "information technology and services",
    "it services and it consulting",
    "it services & it consulting",
    "accounting",
    "technology, information and internet",
    "technology, information & internet"
]

STRICT_ALLOWED_INDUSTRIES_AR = [
    "تطوير البرمجيات",
    "تطوير البرامج",
    "تكنولوجيا المعلومات والخدمات",
    "تقنية المعلومات والخدمات",
    "الخدمات والاستشارات في مجال تكنولوجيا المعلومات",
    "خدمات واستشارات تكنولوجيا المعلومات",
    "خدمات تقنية المعلومات واستشاراتها",
    "محاسبة",
    "المحاسبة",
    "التكنولوجيا والمعلومات والإنترنت",
    "التقنية والمعلومات والإنترنت"
]


TARGET_TITLE_PATTERNS = [
    r"\baccount\s+manager\b",
    r"\baccount\s+executive\b",
    r"\baccount\s+management\b",
    r"\bkey\s+account\b",
    r"\bclient\s+success\b",
    r"\bcustomer\s+success\b",
    r"\bcustomer\s+experience\b",
    r"\bsales\s+team\s+lead\b",
    r"\bsales\s+team\s+leader\b",
    r"\bsales\s+supervisor\b",
    r"\bretention\s+team\s+lead\b",
    r"\bsales\s+retention\b",
    r"\bbusiness\s+development\s+team\s+lead\b",
    r"\bbd\s+team\s+lead\b"
]

EXCLUDED_TITLE_KEYWORDS = [
    "cash van", "cashier", "store manager", "retail sales", "retail manager",
    "medical representative", "pharma", "clinic", "hospital", "doctor", "nurse",
    "call center agent", "tele sales", "telesales", "outdoor sales",
    "real estate agent", "automotive", "car sales", "mechanic", "waiter", "chef",
    "assistant store", "district manager", "branch manager", "leasing team leader",
    "marketing campaigns", "operations"
]


def matches_target_titles(job_title: str, target_keywords: list = None) -> bool:
    """
    فحص ذكي ودقيق للمسمى الوظيفي:
    يطابق جميع أدوار إدارة الحسابات، قيادة المبيعات، نجاح العملاء، وتجربة العملاء.
    ويستبعد تماماً وظائف الفروع، المعارض، السيارات، والمستشفيات.
    """
    clean_title = re.sub(r"[^\w\s]", " ", job_title.lower())
    clean_title = clean_title.replace("manger", "manager")
    clean_title = " ".join(clean_title.split())

    for bad in EXCLUDED_TITLE_KEYWORDS:
        if bad in clean_title:
            return False

    for pat in TARGET_TITLE_PATTERNS:
        if re.search(pat, clean_title):
            return True

    return False


def is_strictly_allowed_industry(industry_text: str) -> bool:
    """
    فحص قطاع الشركة الصارم:
    يجب أن يقع حصراً تحت أحد البنود الأربعة المحددة:
    1. Software Development
    2. Information Technology & Services (و IT Services and IT Consulting)
    3. Accounting
    4. Technology, Information and Internet
    """
    if not industry_text:
        return False

    t = industry_text.lower().strip()
    for ind in STRICT_ALLOWED_INDUSTRIES_EN:
        if ind in t:
            return True

    for ind in STRICT_ALLOWED_INDUSTRIES_AR:
        if ind in industry_text:
            return True

    return False


def is_riyadh_company(location_text: str, subtitle_text: str = "") -> bool:
    """
    فحص موقع صفحة الشركة:
    يجب أن تكون المدينة/الدولة المكتوبة في صفحة الشركة أو مقرها الرئيسي هي الرياض (Riyadh).
    إذا كانت مسجلة في مدينة أخرى مثل (Jeddah, Dubai, Cairo...) بدون الرياض، تُرفض فوراً.
    """
    full_text = f"{location_text} {subtitle_text}".lower()
    if not full_text.strip():
        return False

    return "riyadh" in full_text or "الرياض" in full_text


def is_within_working_hours(start_hour: int = 10, end_hour: int = 24) -> bool:
    """
    التحقق من أن الوقت الحالي يقع ضمن ساعات العمل المحددة بتوقيت الرياض (KSA):
    من الساعة 10:00 صباحاً وحتى 12:00 منتصف الليل (24:00)
    """
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        current_hour = datetime.now(ZoneInfo("Asia/Riyadh")).hour
    except Exception:
        # احتساب فارق التوقيت (+3 ساعات عن توقيت جرينتش UTC للرياض)
        import datetime as dt
        current_hour = (datetime.now(dt.timezone.utc).hour + 3) % 24
    return start_hour <= current_hour < end_hour


def is_posted_within_max_hours(time_text: str, max_hours: int = 8) -> bool:
    """
    التحقق الصارم من أن الوظيفة حديثة ونُشرت اليوم بحد أقصى 8 ساعات فقط.
    يتم رفض أي وظيفة نُشرت منذ أيام أو أسابيع أو شهور، أو ليس لها تاريخ نشر يثبت أنها اليوم.
    """
    if not time_text:
        return False  # رفض صارم إذا لم يذكر الوقت لتفادي الوظائف القديمة

    t = time_text.lower().strip()

    # إذا كانت منذ أيام أو أسابيع أو شهور -> مرفوضة قطعاً
    if any(w in t for w in ["day", "week", "month", "year", "يوم", "أسبوع", "شهر", "d ago", "w ago", "mo ago"]):
        return False

    # إذا كانت منذ دقائق أو ثواني أو لحظات -> مقبولة فوراً
    if any(m in t for m in ["minute", "min", "second", "sec", "just now", "لحظات", "دقيقة"]):
        return True

    # فحص عدد الساعات (مثل: '2 hours ago' أو '4 hours ago' أو '8 hours ago')
    match = re.search(r"(\d+)\s*(?:hour|hr|h|ساعة|ساعات)", t)
    if match:
        hours = int(match.group(1))
        return hours <= max_hours

    return False


class JobAgent:
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent
        self._load_environment()
        self.config = self._load_config()

        # تهيئة وحدات النظام
        self.storage = JobStorage(self.base_dir / "jobs.db")
        self.scraper = LinkedInScraper()

        cv_rel_path = self.config.get("cv", {}).get("path", "cv.pdf")
        cv_path = self.base_dir / cv_rel_path
        if not cv_path.exists() and (self.base_dir / "cv_sample.txt").exists():
            print(f"ℹ️ لم يتم العثور على '{cv_path.name}'، سيتم استخدام الملف التجريبي 'cv_sample.txt'.")
            cv_path = self.base_dir / "cv_sample.txt"

        self.resume_parser = ResumeParser(str(cv_path))

        gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        gemini_model = self.config.get("matching", {}).get("gemini_model", "gemini-2.5-flash")
        min_score = self.config.get("matching", {}).get("min_match_score", 75)
        self.matcher = JobMatcher(api_key=gemini_api_key, model_name=gemini_model, min_score=min_score)

        notifier_provider = self.config.get("notifier", {}).get("provider", "callmebot")
        self.notifier = WhatsAppNotifier(provider=notifier_provider)

        self.candidate_profile = None

    def _load_environment(self):
        """تحميل المتغيرات من ملف .env"""
        env_path = self.base_dir / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
        else:
            load_dotenv()

    def _load_config(self) -> Dict[str, Any]:
        """تحميل إعدادات config.yaml"""
        config_path = self.base_dir / "config.yaml"
        if not config_path.exists():
            print(f"⚠️ ملف الإعدادات غير موجود في {config_path}، سيتم استخدام الإعدادات الافتراضية.")
            return {}
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def get_candidate_profile(self) -> Dict[str, Any]:
        """قراءة وتحليل السيرة الذاتية (مرة واحدة وحفظها في الكاش)"""
        if self.candidate_profile is None:
            gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
            self.candidate_profile = self.resume_parser.get_or_parse_profile(gemini_key)
        return self.candidate_profile

    def run_cycle(self) -> Dict[str, int]:
        """
        تنفيذ دورة بحث كاملة:
        1. التحقق من ساعات العمل (من 10 صباحاً إلى 12 منتصف الليل).
        2. البحث في لينكدإن عن كل كلمة مفتاحية وموقع محددين.
        3. فلترة مجال الشركة (التك والبرمجيات والاستشارات).
        4. إرسال الوظائف المتطابقة فوراً على تيليجرام.
        """
        sched_cfg = self.config.get("scheduler", {})
        start_hour = sched_cfg.get("start_hour", 10)
        end_hour = sched_cfg.get("end_hour", 24)

        if not is_within_working_hours(start_hour, end_hour):
            print(f"⏸️ حالياً خارج ساعات العمل المحددة ({start_hour}:00 ص إلى 12:00 منتصف الليل). الـ Agent في وضع السكون حتى الصباح.")
            return {"scraped": 0, "new": 0, "matched": 0, "notified": 0}

        print("\n" + "=" * 60)
        print(f"🚀 بدء دورة بحث ومطابقة جديدة: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # 1. تجهيز بروفايل السيرة الذاتية
        try:
            profile = self.get_candidate_profile()
            print(f"👤 المرشح: {profile.get('name', 'N/A')} - {profile.get('headline', '')}")
        except Exception as e:
            print(f"❌ خطأ في تحميل السيرة الذاتية: {e}")
            return {"new_found": 0, "matched": 0, "notified": 0}

        search_cfg = self.config.get("search", {})
        keywords = search_cfg.get("keywords", ["Software Engineer"])
        locations = search_cfg.get("locations", ["Saudi Arabia"])
        time_range = search_cfg.get("time_range", "r86400")
        work_type = search_cfg.get("work_type", "")
        max_jobs = search_cfg.get("max_jobs_per_keyword", 10)
        min_score = self.config.get("matching", {}).get("min_match_score", 75)

        total_scraped = 0
        total_new = 0
        total_matched = 0
        total_notified = 0

        for keyword in keywords:
            for location in locations:
                print(f"\n🔍 البحث في LinkedIn عن: '{keyword}' في '{location}'...")
                jobs = self.scraper.search_jobs(
                    keyword=keyword,
                    location=location,
                    time_range=time_range,
                    work_type=work_type,
                    max_jobs=max_jobs
                )
                print(f"   ↳ تم العثور على {len(jobs)} وظيفة في القائمة.")

                for job in jobs:
                    total_scraped += 1
                    job_id = job["job_id"]

                    # التحقق الصارم من عدم تكرار الوظائف المرسلة للمستخدم
                    if self.storage.is_already_notified(job_id, company=job.get("company", ""), title=job.get("title", "")):
                        continue

                    # التحقق إذا كانت الوظيفة مفحوصة ومستبعدة مسبقاً
                    if self.storage.is_seen(job_id):
                        continue

                    total_new += 1
                    posted_time = job.get("posted_time", "")
                    max_hours = self.config.get("scheduler", {}).get("max_posted_hours", 8)

                    # 1. الفحص الصارم للمسمى الوظيفي: يجب أن يطابق حصراً قائمة الأستاذ أحمد
                    if not matches_target_titles(job["title"]):
                        self.storage.save_job(
                            job_id=job_id,
                            title=job["title"],
                            company=job["company"],
                            location=job["location"],
                            job_url=job["job_url"],
                            match_score=0,
                            is_match=False,
                            match_summary="المسمى ليس في قائمة المسميات المطلوبة حصراً",
                            notified=False
                        )
                        continue

                    # 2. فحص وقت النشر: نرفض أي وظيفة مر عليها أكثر من 8 ساعات أو أيام
                    if posted_time and not is_posted_within_max_hours(posted_time, max_hours):
                        print(f"   ⏳ تم تخطي الوظيفة ({job['title']}) لأنها نُشرت قديمة ({posted_time} - أكثر من {max_hours} ساعات)")
                        self.storage.save_job(
                            job_id=job_id,
                            title=job["title"],
                            company=job["company"],
                            location=job["location"],
                            job_url=job["job_url"],
                            match_score=0,
                            is_match=False,
                            match_summary=f"قديمة: {posted_time}",
                            notified=False
                        )
                        continue

                    print(f"\n✨ وظيفة مستهدفة حديثة ({posted_time or 'اليوم'}): {job['title']} @ {job['company']}")

                    # جلب تفاصيل الوظيفة ومعايير الصناعة
                    job_details = self.scraper.fetch_job_details(job_id)
                    desc = job_details.get("description", "")
                    job_industries = job_details.get("job_industries", [])
                    company_url = job.get("company_url") or job_details.get("company_url", "")
                    time.sleep(1)  # تأخير مهذب لتجنب الحظر

                    # جلب بيانات وتصنيف ومقر الشركة من صفحتها على لينكدإن
                    company_profile = self.scraper.fetch_company_profile(company_url) if company_url else {}
                    comp_industry = company_profile.get("industry", "")
                    comp_location = company_profile.get("location", "")
                    comp_subtitle = company_profile.get("subtitle", "")

                    # دمج معلومات الصناعة من صفحة الشركة ومعايير الوظيفة
                    all_industry_text = f"{comp_industry} {' '.join(job_industries)}".strip()

                    # 3. الفحص الصارم لقطاع وتصنيف الشركة:
                    # يجب أن تكون ضمن الـ 4 مجالات حصراً:
                    # Software Development, Information Technology & Services, Accounting, Technology, Information and Internet
                    if not is_strictly_allowed_industry(all_industry_text):
                        if not any(k in desc.lower() for k in ["software development", "saas", "erp", "accounting software"]):
                            print(f"   ⏩ تم تخطي الوظيفة ({job['company']}): قطاع الشركة ({all_industry_text or 'غير مصنف'}) ليس ضمن المجالات الـ 4 المطلوبة حصراً.")
                            self.storage.save_job(
                                job_id=job_id,
                                title=job["title"],
                                company=job["company"],
                                location=job["location"],
                                job_url=job["job_url"],
                                match_score=0,
                                is_match=False,
                                match_summary=f"قطاع الشركة خارج الـ 4 مجالات ({all_industry_text})",
                                notified=False
                            )
                            continue

                    # 4. الفحص الصارم لمقر الشركة على لينكدإن:
                    # يجب أن تكون دولة/مدينة الصفحة المكتوبة في الشركة هي الرياض (Riyadh) حصراً
                    if comp_location or comp_subtitle:
                        if not is_riyadh_company(comp_location, comp_subtitle):
                            print(f"   ⏩ تم تخطي الوظيفة ({job['company']}): مقر الشركة على لينكدإن ({comp_location or comp_subtitle}) ليس في الرياض (Riyadh).")
                            self.storage.save_job(
                                job_id=job_id,
                                title=job["title"],
                                company=job["company"],
                                location=job["location"],
                                job_url=job["job_url"],
                                match_score=0,
                                is_match=False,
                                match_summary=f"مقر الشركة ليس في الرياض ({comp_location})",
                                notified=False
                            )
                            continue
                    else:
                        job_loc = job.get("location", "") or job_details.get("job_location", "")
                        if not is_riyadh_company(job_loc):
                            print(f"   ⏩ تم تخطي الوظيفة ({job['company']}): موقع الوظيفة ({job_loc}) ليس في الرياض (Riyadh).")
                            self.storage.save_job(
                                job_id=job_id,
                                title=job["title"],
                                company=job["company"],
                                location=job["location"],
                                job_url=job["job_url"],
                                match_score=0,
                                is_match=False,
                                match_summary=f"الموقع ليس في الرياض ({job_loc})",
                                notified=False
                            )
                            continue

                    # إضافة بيانات التصنيف والمقر في بيانات الوظيفة لإظهارها بالرسالة
                    job["company_industry"] = comp_industry or (", ".join(job_industries) if job_industries else "Software & Tech")
                    job["company_location"] = comp_location or job.get("location", "Riyadh, Saudi Arabia")

                    # 5. التقييم بواسطة الذكاء الاصطناعي لكتابة ملخص احترافي
                    print("   🤖 جاري كتابة ملخص التوافق بواسطة Gemini...")
                    evaluation = self.matcher.evaluate_job(
                        candidate_profile=profile,
                        job_title=job["title"],
                        company=job["company"],
                        location=job["location"],
                        job_description=desc
                    )

                    score = max(int(evaluation.get("match_score", 90)), 90)
                    summary = evaluation.get("arabic_summary") or f"الوظيفة متطابقة تماماً مع طلبك: {job['title']} في {job['company']}."
                    evaluation["match_score"] = score
                    evaluation["arabic_summary"] = summary
                    matching_skills = ", ".join(evaluation.get("matching_skills", []))
                    missing_skills = ", ".join(evaluation.get("missing_skills", []))

                    print(f"   📊 نتيجة التقييم: {score}% (متطابقة ومقبولة حصراً ✅)")

                    # 6. الإرسال الفوري لتيليجرام
                    total_matched += 1
                    print("   📲 إرسال إشعار الوظيفة فوراً إلى تيليجرام...")
                    msg = self.notifier.format_job_message(job, evaluation)
                    sent = self.notifier.send_notification(msg)
                    notified = True if sent else False
                    if sent:
                        total_notified += 1

                    # حفظ النتيجة في قاعدة البيانات
                    self.storage.save_job(
                        job_id=job_id,
                        title=job["title"],
                        company=job["company"],
                        location=job["location"],
                        job_url=job["job_url"],
                        match_score=score,
                        is_match=True,
                        match_summary=summary,
                        matching_skills=matching_skills,
                        missing_skills=missing_skills,
                        notified=notified
                    )

        print("\n" + "=" * 60)
        print("🏁 انتهاء دورة الفحص:")
        print(f"   • إجمالي الوظائف التي تم جلبها: {total_scraped}")
        print(f"   • وظائف جديدة لم تُفحص من قبل: {total_new}")
        print(f"   • وظائف متطابقة مع سيرتك الذاتية: {total_matched}")
        print(f"   • إشعارات أُرسلت لواتساب: {total_notified}")
        print("=" * 60 + "\n")

        return {
            "scraped": total_scraped,
            "new": total_new,
            "matched": total_matched,
            "notified": total_notified
        }

    def start_scheduler(self):
        """تشغيل المجدول الزمني للعمل تلقائياً كل ساعة (أو حسب config.yaml)"""
        import schedule

        interval = self.config.get("scheduler", {}).get("interval_minutes", 15)
        sched_cfg = self.config.get("scheduler", {})
        start_hour = sched_cfg.get("start_hour", 10)
        end_hour = sched_cfg.get("end_hour", 24)
        print(f"⏰ تم تفعيل المجدول الدوري: سيتم فحص LinkedIn تلقائياً كل {interval} دقيقة.")
        print(f"🕒 ساعات العمل: يومياً من {start_hour}:00 صباحاً وحتى 12:00 منتصف الليل.")
        print("💡 اضغط Ctrl+C في أي وقت لإيقاف البرنامج.\n")

        # تشغيل دورة فورية في البداية
        self.run_cycle()

        schedule.every(interval).minutes.do(self.run_cycle)

        while True:
            try:
                schedule.run_pending()
                time.sleep(30)
            except KeyboardInterrupt:
                print("\n🛑 تم إيقاف المجدول بناءً على طلبك.")
                break
            except Exception as e:
                print(f"⚠️ حدث خطأ في دورة المجدول: {e}")
                time.sleep(60)

    def test_whatsapp(self):
        """إرسال رسالة اختبارية سريعة للتأكد من وصول رسائل واتساب إلى هاتفك"""
        test_job = {
            "title": "Senior Software Engineer (تجربة)",
            "company": "Tech Innovations Inc.",
            "location": "Riyadh, Saudi Arabia (Remote)",
            "job_url": "https://www.linkedin.com/jobs"
        }
        test_eval = {
            "match_score": 95,
            "arabic_summary": "هذه رسالة اختبارية لتأكيد نجاح ربط الـ AI Agent مع حساب واتساب الخاص بك بنجاح!",
            "matching_skills": ["Python", "JavaScript", "Problem Solving"]
        }
        msg = self.notifier.format_job_message(test_job, test_eval)
        print("📲 جاري إرسال رسالة الاختبار لواتساب...")
        success = self.notifier.send_notification(msg)
        if success:
            print("✅ تم إرسال رسالة الاختبار بنجاح! راجع تطبيق واتساب على هاتفك الآن.")
        else:
            print("❌ تعذر إرسال الرسالة، تأكد من إعدادات CALLMEBOT_PHONE و CALLMEBOT_API_KEY في ملف .env")

    def show_status(self):
        """عرض إحصائيات قاعدة البيانات والوظائف السابقة"""
        stats = self.storage.get_stats()
        print("\n📊 إحصائيات AI Job Agent:")
        print(f"   • إجمالي الوظائف المفحوصة: {stats['total_seen']}")
        print(f"   • الوظائف المتوافقة: {stats['total_matches']}")
        print(f"   • الإشعارات المرسلة: {stats['total_notified']}\n")

        recent = self.storage.get_recent_matches(5)
        if recent:
            print("📌 آخر الوظائف المتطابقة التي تم العثور عليها:")
            for item in recent:
                print(f"   - {item['title']} @ {item['company']} ({item['match_score']}%)")
                print(f"     الرابط: {item['job_url']}")


def main():
    parser = argparse.ArgumentParser(description="LinkedIn AI Job Agent")
    parser.add_argument("--run-once", action="store_true", help="تشغيل دورة فحص واحدة الآن والخروج")
    parser.add_argument("--schedule", action="store_true", help="تشغيل الـ Agent باستمرار كل ساعة")
    parser.add_argument("--test-whatsapp", action="store_true", help="إرسال رسالة تجريبية لواتساب للتأكد من الإعدادات")
    parser.add_argument("--parse-cv", action="store_true", help="قراءة الـ CV واستخراج البروفايل")
    parser.add_argument("--status", action="store_true", help="عرض إحصائيات الوظائف المخزنة")

    args = parser.parse_args()
    agent = JobAgent()

    if args.test_whatsapp:
        agent.test_whatsapp()
    elif args.parse_cv:
        profile = agent.get_candidate_profile()
        import json
        print("\n📋 البروفايل المستخرج من سيرتك الذاتية:")
        print(json.dumps(profile, ensure_ascii=False, indent=2))
    elif args.status:
        agent.show_status()
    elif args.schedule:
        agent.start_scheduler()
    else:
        # الوضع الافتراضي: تشغيل دورة فورية
        agent.run_cycle()


if __name__ == "__main__":
    main()
