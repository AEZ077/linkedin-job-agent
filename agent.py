#!/usr/bin/env python3
"""
المنسق الرئيسي لـ AI Job Agent
يربط قراءة السيرة الذاتية، البحث السريع في لينكدإن (sortBy=DD)، الفلترة الصارمة،
أولوية شركات الـ Tech، التقييم الواقعي عبر Gemini، والإرسال الفوري إلى تيليجرام.
"""

import argparse
import os
import random
import re
import subprocess
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv

warnings.filterwarnings("ignore")

from job_matcher import JobMatcher
from linkedin_scraper import LinkedInScraper
from notifier import JobNotifier
from resume_parser import ResumeParser
from storage import JobStorage


STRICT_ALLOWED_INDUSTRIES_EN = [
    "software development",
    "computer software",
    "information technology & services",
    "information technology and services",
    "information technology",
    "it services and it consulting",
    "it services & it consulting",
    "accounting",
    "technology, information and internet",
    "technology, information & internet",
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
    "التقنية والمعلومات والإنترنت",
]

TECH_INDUSTRY_MARKERS = [
    "software",
    "information technology",
    "it services",
    "technology, information",
    "internet",
    "تطوير البرمجيات",
    "تطوير البرامج",
    "تكنولوجيا المعلومات",
    "تقنية المعلومات",
    "التكنولوجيا",
    "التقنية",
]

TARGET_TITLE_PATTERNS = [
    r"\baccount\s+manager\b",
    r"\baccount\s+management\b",
    r"\baccount\s+executive\b",
    r"\bkey\s+account\b",
    r"\baccount\s+director\b",
    r"\bclient\s+success\b",
    r"\bcustomer\s+success\b",
    r"\bcustomer\s+experience\b",
    r"\bhead\s+of\s+cx\b",
    r"\bsales\s+team\s+lead(?:er)?\b",
    r"\bsales\s+supervisor\b",
    r"\bretention\s+team\s+lead(?:er)?\b",
    r"\bsales\s+retention\b",
    r"\bbusiness\s+development\s+team\s+lead(?:er)?\b",
    r"\bbd\s+team\s+lead(?:er)?\b",
]

EXCLUDED_TITLE_KEYWORDS = [
    "intern",
    "internship",
    "trainee",
    "fresh graduate",
    "rotational",
    "associate analyst",
    "cash van",
    "cashier",
    "store manager",
    "retail sales",
    "retail manager",
    "medical representative",
    "pharma",
    "clinic",
    "hospital",
    "doctor",
    "nurse",
    "call center agent",
    "tele sales",
    "telesales",
    "outdoor sales",
    "real estate agent",
    "automotive",
    "car sales",
    "mechanic",
    "waiter",
    "chef",
    "driver",
    "merchandiser",
    "assistant store",
    "district manager",
    "branch manager",
    "leasing team leader",
    "marketing campaigns",
    "operations",
]

SAUDI_NON_RIYADH_CITIES = [
    "jeddah", "جدة", "makkah", "مكة", "dammam", "الدمام",
    "khobar", "الخبر", "dhahran", "الظهران", "jubail", "الجبيل",
    "medina", "المدينة", "yanbu", "ينبع", "tabuk", "تبوك",
    "abha", "أبها", "jizan", "جازان", "taif", "الطائف",
]


def matches_target_titles(job_title: str) -> bool:
    """مطابقة المسميات الـ 14 المطلوبة والقريبة منها واستبعاد الأدوار غير المناسبة."""
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
    """التحقق من أن قطاع الشركة ضمن الـ 4 قطاعات المطلوبة حصراً."""
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


def is_tech_industry(industry_text: str) -> bool:
    """تحديد ما إذا كانت الشركة في مجال التكنولوجيا لإعطائها الأولوية القصوى."""
    if not industry_text:
        return False
    t = industry_text.lower()
    return any(marker in t for marker in TECH_INDUSTRY_MARKERS)


def is_riyadh_company(location_text: str, subtitle_text: str = "") -> bool:
    """التحقق الصارم من أن مقر/موقع صفحة الشركة على LinkedIn هو الرياض (Riyadh)."""
    comp_text = f"{location_text} {subtitle_text}".lower()
    if not comp_text.strip():
        return False

    for city in SAUDI_NON_RIYADH_CITIES:
        if city in comp_text and "riyadh" not in comp_text and "الرياض" not in comp_text:
            return False

    return "riyadh" in comp_text or "الرياض" in comp_text


def is_posted_within_max_hours(time_text: str, max_hours: int = 24) -> bool:
    """التحقق من أن الوظيفة منشورة خلال الحد الأقصى للساعات المحدد."""
    if not time_text:
        return False

    t = time_text.lower().strip()
    if any(w in t for w in ["day", "week", "month", "year", "يوم", "أسبوع", "شهر", "d ago", "w ago", "mo ago"]):
        return False

    if any(m in t for m in ["minute", "min", "second", "sec", "just now", "لحظات", "دقيقة", "ثانية"]):
        return True

    match = re.search(r"(\d+)\s*(?:hour|hr|h|ساعة|ساعات)", t)
    if match:
        return int(match.group(1)) <= max_hours

    return False


class JobAgent:
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent
        self._load_environment()
        self.config = self._load_config()
        self.is_github_actions = os.getenv("GITHUB_ACTIONS", "").lower() == "true"

        self.storage = JobStorage(self.base_dir / "jobs.db")
        self.scraper = LinkedInScraper()

        cv_rel_path = self.config.get("cv", {}).get("path", "cv.txt")
        cv_path = self.base_dir / cv_rel_path
        if not cv_path.exists() and (self.base_dir / "cv_sample.txt").exists():
            print(f"ℹ️ لم يتم العثور على '{cv_path.name}'، سيتم استخدام '{'cv_sample.txt'}'.")
            cv_path = self.base_dir / "cv_sample.txt"

        self.resume_parser = ResumeParser(str(cv_path))

        gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        gemini_model = self.config.get("matching", {}).get("gemini_model", "gemini-3.5-flash-lite")
        min_score = self.config.get("matching", {}).get("min_match_score", 65)
        self.gemini_model = gemini_model
        self.matcher = JobMatcher(api_key=gemini_api_key, model_name=gemini_model, min_score=min_score)

        notifier_provider = self.config.get("notifier", {}).get("provider", "telegram")
        self.notifier = JobNotifier(provider=notifier_provider)
        self.candidate_profile = None

    def _load_environment(self):
        env_path = self.base_dir / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
        else:
            load_dotenv()

    def _load_config(self) -> Dict[str, Any]:
        config_path = self.base_dir / "config.yaml"
        if not config_path.exists():
            print(f"⚠️ ملف الإعدادات غير موجود في {config_path}، سيتم استخدام الإعدادات الافتراضية.")
            return {}
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def get_candidate_profile(self) -> Dict[str, Any]:
        if self.candidate_profile is None:
            gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
            self.candidate_profile = self.resume_parser.get_or_parse_profile(
                gemini_key,
                model_name=self.gemini_model,
            )
        return self.candidate_profile

    def _sync_git_pull(self):
        if self.is_github_actions:
            return
        try:
            subprocess.run(
                ["git", "pull", "--rebase", "origin", "main"],
                cwd=str(self.base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
        except Exception:
            pass

    def _sync_git_push(self):
        if self.is_github_actions:
            return
        try:
            subprocess.run(
                ["git", "add", "jobs.db", "cv_profile.json"],
                cwd=str(self.base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            subprocess.run(
                ["git", "commit", "-m", "chore: sync local seen jobs [skip ci]"],
                cwd=str(self.base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=str(self.base_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
        except Exception:
            pass

    def run_cycle(self, include_broad_location: bool = True) -> Dict[str, int]:
        """تنفيذ دورة فحص كاملة مع ترتيب الأولوية لشركات الـ Tech وإرسال الإشعارات الفورية."""
        self._sync_git_pull()

        print("\n" + "=" * 60)
        print(f"🚀 بدء دورة بحث ومطابقة جديدة: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        try:
            profile = self.get_candidate_profile()
            print(f"👤 المرشح: {profile.get('name', 'N/A')} - {profile.get('headline', '')}")
        except Exception as e:
            print(f"❌ خطأ في تحميل السيرة الذاتية: {e}")
            return {"scraped": 0, "new": 0, "matched": 0, "notified": 0}

        search_cfg = self.config.get("search", {})
        keywords = search_cfg.get("keywords", ["Account Manager"])
        locations = list(search_cfg.get("locations", ["Riyadh, Saudi Arabia"]))
        if not include_broad_location and len(locations) > 1:
            locations = [locations[0]]

        time_range = search_cfg.get("time_range", "r86400")
        work_type = search_cfg.get("work_type", "")
        max_jobs = search_cfg.get("max_jobs_per_keyword", 10)
        min_score = int(self.config.get("matching", {}).get("min_match_score", 65))
        max_hours = int(self.config.get("scheduler", {}).get("max_posted_hours", 24))

        total_scraped = 0
        total_new = 0
        cycle_seen_ids = set()
        matched_candidates: List[Dict[str, Any]] = []

        for keyword in keywords:
            for location in locations:
                time.sleep(random.uniform(1.5, 3.0))
                print(f"\n🔍 البحث في LinkedIn عن: '{keyword}' في '{location}'...")
                jobs = self.scraper.search_jobs(
                    keyword=keyword,
                    location=location,
                    time_range=time_range,
                    work_type=work_type,
                    max_jobs=max_jobs,
                    sort_by_recent=True,
                )
                print(f"   ↳ تم العثور على {len(jobs)} وظيفة في القائمة.")

                for job in jobs:
                    total_scraped += 1
                    job_id = job["job_id"]

                    if job_id in cycle_seen_ids:
                        continue
                    cycle_seen_ids.add(job_id)

                    if self.storage.is_seen(job_id) or self.storage.is_already_notified(
                        job_id,
                        company=job.get("company", ""),
                        title=job.get("title", ""),
                    ):
                        continue

                    total_new += 1
                    posted_time = job.get("posted_time", "")

                    # 1. فحص المسمى الوظيفي
                    if not matches_target_titles(job["title"]):
                        self.storage.save_job(
                            job_id=job_id,
                            title=job["title"],
                            company=job["company"],
                            location=job["location"],
                            job_url=job["job_url"],
                            match_score=0,
                            is_match=False,
                            match_summary="المسمى خارج القائمة المطلوبة",
                            notified=False,
                        )
                        continue

                    # 2. فحص حداثة النشر
                    if posted_time and not is_posted_within_max_hours(posted_time, max_hours):
                        print(f"   ⏳ تخطي وظيفة قديمة ({job['title']} - {posted_time})")
                        self.storage.save_job(
                            job_id=job_id,
                            title=job["title"],
                            company=job["company"],
                            location=job["location"],
                            job_url=job["job_url"],
                            match_score=0,
                            is_match=False,
                            match_summary=f"قديمة: {posted_time}",
                            notified=False,
                        )
                        continue

                    print(f"\n✨ وظيفة مرشحة حديثة ({posted_time or 'حديثة'}): {job['title']} @ {job['company']}")

                    # 3. جلب التفاصيل الكاملة للوظيفة
                    job_details = self.scraper.fetch_job_details(job_id)
                    if not job_details.get("ok"):
                        print(f"   ⚠️ تعذر جلب تفاصيل الوظيفة مؤقتاً ({job_id}) - ستُعاد محاولتها في الدورة القادمة.")
                        continue

                    desc = job_details.get("description", "")
                    job_industries = job_details.get("job_industries", [])
                    company_url = job.get("company_url") or job_details.get("company_url", "")
                    time.sleep(1.0)

                    # 4. جلب بيانات صفحة الشركة على LinkedIn
                    company_profile = (
                        self.scraper.fetch_company_profile(company_url)
                        if company_url
                        else {"ok": True, "industry": "", "location": "", "subtitle": ""}
                    )
                    if company_url and not company_profile.get("ok"):
                        print(f"   ⚠️ تعذر فتح صفحة الشركة مؤقتاً ({job['company']}) - ستُعاد محاولتها في الدورة القادمة.")
                        continue

                    comp_industry = company_profile.get("industry", "")
                    comp_location = company_profile.get("location", "")
                    comp_subtitle = company_profile.get("subtitle", "")
                    all_industry_text = f"{comp_industry} {' '.join(job_industries)}".strip()

                    # 5. التحقق الصارم من الـ 4 قطاعات
                    if not is_strictly_allowed_industry(all_industry_text):
                        print(f"   ⏩ تخطي ({job['company']}): القطاع ({all_industry_text or 'غير محدد'}) خارج الـ 4 قطاعات.")
                        self.storage.save_job(
                            job_id=job_id,
                            title=job["title"],
                            company=job["company"],
                            location=job["location"],
                            job_url=job["job_url"],
                            match_score=0,
                            is_match=False,
                            match_summary=f"قطاع خارج الـ 4 مجالات ({all_industry_text})",
                            notified=False,
                        )
                        continue

                    # 6. التحقق الصارم من أن مقر/موقع صفحة الشركة Riyadh
                    if not is_riyadh_company(comp_location, comp_subtitle):
                        print(f"   ⏩ تخطي ({job['company']}): صفحة الشركة ({comp_location or comp_subtitle or 'غير محدد'}) ليست Riyadh.")
                        self.storage.save_job(
                            job_id=job_id,
                            title=job["title"],
                            company=job["company"],
                            location=job["location"],
                            job_url=job["job_url"],
                            match_score=0,
                            is_match=False,
                            match_summary=f"مقر صفحة الشركة ليس الرياض ({comp_location or comp_subtitle})",
                            notified=False,
                        )
                        continue

                    is_tech = is_tech_industry(all_industry_text)
                    job["company_industry"] = comp_industry or (", ".join(job_industries) if job_industries else "Tech")
                    job["company_location"] = comp_location or job.get("location", "Riyadh, Saudi Arabia")
                    job["employment_type"] = job_details.get("employment_type", "")
                    job["seniority_level"] = job_details.get("seniority_level", "")
                    job["description"] = desc
                    job["is_tech"] = is_tech

                    # 7. التقييم الواقعي عبر Gemini ومقارنة الـ CV
                    print("   🤖 تقييم نسبة التوافق مع الـ CV عبر Gemini...")
                    evaluation = self.matcher.evaluate_job(
                        candidate_profile=profile,
                        job_title=job["title"],
                        company=job["company"],
                        location=job["location"],
                        job_description=desc,
                        company_industry=job["company_industry"],
                    )

                    score = int(evaluation.get("match_score", 0))
                    summary = evaluation.get("arabic_summary") or f"توافق الوظيفة مع خبرتك: {job['title']}."
                    matching_skills = ", ".join(evaluation.get("matching_skills", []))
                    missing_skills = ", ".join(evaluation.get("missing_skills", []))

                    if score < min_score:
                        print(f"   📉 نسبة التوافق {score}% أقل من الحد المطلوب ({min_score}%) -> تم الحفظ بدون إرسال.")
                        self.storage.save_job(
                            job_id=job_id,
                            title=job["title"],
                            company=job["company"],
                            location=job["location"],
                            job_url=job["job_url"],
                            match_score=score,
                            is_match=False,
                            match_summary=summary,
                            matching_skills=matching_skills,
                            missing_skills=missing_skills,
                            notified=False,
                        )
                        continue

                    print(f"   📊 نتيجة التقييم الحقيقية: {score}% ({'🔥 Tech Priority' if is_tech else 'Accounting'}) ✅")
                    matched_candidates.append({
                        "job": job,
                        "evaluation": evaluation,
                        "score": score,
                        "is_tech": is_tech,
                        "summary": summary,
                        "matching_skills": matching_skills,
                        "missing_skills": missing_skills,
                    })

        # ترتيب الأولوية: شركات الـ Tech أولاً، ثم أعلى نسبة توافق
        matched_candidates.sort(key=lambda x: (x["is_tech"], x["score"]), reverse=True)

        total_matched = len(matched_candidates)
        total_notified = 0

        for item in matched_candidates:
            job = item["job"]
            evaluation = item["evaluation"]
            msg = self.notifier.format_job_message(job, evaluation)
            sent = self.notifier.send_notification(msg, job_url=job["job_url"])
            notified = bool(sent)
            if sent:
                total_notified += 1

            self.storage.save_job(
                job_id=job["job_id"],
                title=job["title"],
                company=job["company"],
                location=job["location"],
                job_url=job["job_url"],
                match_score=item["score"],
                is_match=True,
                match_summary=item["summary"],
                matching_skills=item["matching_skills"],
                missing_skills=item["missing_skills"],
                notified=notified,
            )

        print("\n" + "=" * 60)
        print("🏁 انتهاء دورة الفحص:")
        print(f"   • إجمالي الوظائف المجلبة: {total_scraped}")
        print(f"   • وظائف جديدة فُحصت: {total_new}")
        print(f"   • وظائف مطابقة للـ CV والشروط: {total_matched}")
        print(f"   • إشعارات أُرسلت لتيليجرام: {total_notified}")
        print("=" * 60 + "\n")

        if total_new > 0:
            self._sync_git_push()

        return {
            "scraped": total_scraped,
            "new": total_new,
            "matched": total_matched,
            "notified": total_notified,
        }

    def run_poll_window(self, poll_minutes: float = 3.0, interval_seconds: int = 90):
        """
        تشغيل دورات فحص متتابعة داخل نافذة زمنية قصيرة (مثلاً كل 90 ثانية لمدة 3 دقائق)
        لاقتناص الوظائف بمجرد نزولها على LinkedIn داخل كل تشغيل لـ GitHub Actions.
        """
        start_ts = time.time()
        end_ts = start_ts + max(0.0, poll_minutes * 60.0)
        cycle_idx = 0

        while True:
            cycle_idx += 1
            include_broad = cycle_idx == 1
            self.run_cycle(include_broad_location=include_broad)

            now = time.time()
            remaining = end_ts - now
            if remaining < interval_seconds:
                break

            print(f"⏳ انتظار {interval_seconds} ثانية قبل الدورة السريعة التالية...")
            time.sleep(interval_seconds)

    def start_scheduler(self):
        """تشغيل محلي مستمر 24/7 كل دقيقة/دقائق حسب الإعدادات."""
        import schedule

        interval = self.config.get("scheduler", {}).get("interval_minutes", 5)
        print(f"⏰ تم تفعيل المجدول المستمر 24/7: فحص LinkedIn كل {interval} دقيقة.")
        print("💡 اضغط Ctrl+C لإيقاف البرنامج.\n")

        self.run_cycle()
        schedule.every(interval).minutes.do(self.run_cycle)

        while True:
            try:
                schedule.run_pending()
                time.sleep(15)
            except KeyboardInterrupt:
                print("\n🛑 تم إيقاف المجدول.")
                break
            except Exception as e:
                print(f"⚠️ خطأ في المجدول: {e}")
                time.sleep(30)

    def test_telegram(self):
        """إرسال رسالة اختبارية إلى تيليجرام للتأكد من الإعدادات والتنسيق."""
        test_job = {
            "title": "Senior Account Management & Customer Success Manager (تجربة)",
            "company": "Saudi Cloud Tech Co.",
            "company_industry": "Software Development",
            "company_location": "Riyadh, Saudi Arabia",
            "location": "Riyadh, Saudi Arabia (Hybrid)",
            "employment_type": "Full-time",
            "seniority_level": "Mid-Senior level",
            "posted_time": "Just now",
            "is_tech": True,
            "description": "Lead key B2B SaaS accounts, manage onboarding, retention, renewals, Zoho/HubSpot CRM, and KPI dashboards.",
            "job_url": "https://www.linkedin.com/jobs",
        }
        test_eval = {
            "match_score": 94,
            "arabic_summary": "رسالة اختبارية تؤكد جاهزية البوت على تيليجرام بالتنسيق الكامل وأولوية شركات الـ Tech.",
            "job_highlights_ar": "• قيادة إدارة حسابات B2B SaaS ورفع نسبة الاحتفاظ بالعملاء.\n• إدارة الـ Onboarding والـ Renewals ومتابعة مؤشرات الأداء.",
            "matching_skills": ["Account Management", "Customer Success", "B2B SaaS", "Zoho CRM", "HubSpot CRM"],
            "missing_skills": [],
        }
        msg = self.notifier.format_job_message(test_job, test_eval)
        print("📲 جاري إرسال رسالة الاختبار إلى تيليجرام...")
        if self.notifier.send_notification(msg, job_url=test_job["job_url"]):
            print("✅ تم إرسال رسالة الاختبار إلى تيليجرام بنجاح!")
        else:
            print("❌ تعذر الإرسال لتيليجرام، راجع TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID.")

    def show_status(self):
        stats = self.storage.get_stats()
        print("\n📊 إحصائيات AI Job Agent:")
        print(f"   • إجمالي الوظائف المفحوصة: {stats['total_seen']}")
        print(f"   • الوظائف المتوافقة: {stats['total_matches']}")
        print(f"   • الإشعارات المرسلة: {stats['total_notified']}\n")

        recent = self.storage.get_recent_matches(5)
        if recent:
            print("📌 آخر الوظائف المتطابقة:")
            for item in recent:
                print(f"   - {item['title']} @ {item['company']} ({item['match_score']}%)")
                print(f"     الرابط: {item['job_url']}")


def main():
    parser = argparse.ArgumentParser(description="LinkedIn AI Job Agent")
    parser.add_argument("--run-once", action="store_true", help="تشغيل دورة فحص واحدة الآن والخروج")
    parser.add_argument("--poll-minutes", type=float, default=0.0, help="تشغيل فحص متكرر لمدة محددة بالدقائق")
    parser.add_argument("--interval-seconds", type=int, default=90, help="الفاصل بالثواني داخل وضع --poll-minutes")
    parser.add_argument("--schedule", action="store_true", help="تشغيل مستمر 24/7 محلياً")
    parser.add_argument("--test-telegram", action="store_true", help="إرسال رسالة اختبارية لتيليجرام")
    parser.add_argument("--test-whatsapp", action="store_true", help="Alias لاختبار الإشعار")
    parser.add_argument("--parse-cv", action="store_true", help="قراءة الـ CV وتحديث البروفايل")
    parser.add_argument("--status", action="store_true", help="عرض إحصائيات قاعدة البيانات")

    args = parser.parse_args()
    agent = JobAgent()

    if args.test_telegram or args.test_whatsapp:
        agent.test_telegram()
    elif args.parse_cv:
        import json
        profile = agent.get_candidate_profile()
        print("\n📋 البروفايل المستخرج من سيرتك الذاتية:")
        print(json.dumps(profile, ensure_ascii=False, indent=2))
    elif args.status:
        agent.show_status()
    elif args.poll_minutes > 0:
        agent.run_poll_window(poll_minutes=args.poll_minutes, interval_seconds=args.interval_seconds)
    elif args.schedule:
        agent.start_scheduler()
    else:
        agent.run_cycle()


if __name__ == "__main__":
    main()
