"""
وحدة جلب وبحث الوظائف من لينكدإن (LinkedIn Scraper)
تعتمد على واجهة البحث المباشرة العامة في لينكدإن (LinkedIn Guest Jobs API).
- لا تحتاج إلى تسجيل الدخول أو إدخال حسابك الشخصي (آمنة تماماً وخالية من مخاطر حظر الحساب).
- تجلب أحدث الوظائف المنشورة مع الروابط المباشرة وتفاصيل الوصف الوظيفي.
"""

import re
import time
import random
import urllib.parse
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

SEARCH_ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
JOB_DETAIL_ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"


class LinkedInScraper:
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()

    def _get_headers(self) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            "Referer": "https://www.linkedin.com/jobs",
        }

    def search_jobs(
        self,
        keyword: str,
        location: str = "Saudi Arabia",
        time_range: str = "r86400",
        work_type: str = "",
        max_jobs: int = 15
    ) -> List[Dict[str, Any]]:
        """
        البحث عن الوظائف في لينكدإن بناءً على الكلمة المفتاحية والموقع ونطاق الوقت
        """
        params = {
            "keywords": keyword,
            "location": location,
            "f_TPR": time_range,
            "start": 0
        }

        if work_type.lower() == "remote":
            params["f_WT"] = "2"
        elif work_type.lower() == "onsite":
            params["f_WT"] = "1"
        elif work_type.lower() == "hybrid":
            params["f_WT"] = "3"

        jobs = []
        # تأخير مهذب وعشوائي بين الطلبات لمنع الـ 429
        time.sleep(random.uniform(2.0, 3.5))

        try:
            resp = self.session.get(SEARCH_ENDPOINT, params=params, headers=self._get_headers(), timeout=15)
            if resp.status_code == 429:
                print(f"⏳ تم الوصول لحد الطلبات مؤقتاً (429) - سيتم الانتظار قليلاً...")
                time.sleep(10)
                return jobs
            elif resp.status_code != 200:
                print(f"⚠️ استجابة لينكدإن ({resp.status_code}) للبحث عن: '{keyword}' في '{location}'")
                return jobs

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("li div.base-card")

            for card in cards:
                if len(jobs) >= max_jobs:
                    break

                job_id = None
                urn = card.get("data-entity-urn", "")
                if urn and "jobPosting:" in urn:
                    job_id = urn.split("jobPosting:")[-1].strip()

                title_el = card.select_one("h3.base-search-card__title, .sr-only")
                title = title_el.get_text(strip=True) if title_el else ""

                company_el = card.select_one("h4.base-search-card__subtitle a, h4.base-search-card__subtitle")
                company = company_el.get_text(strip=True) if company_el else "Unknown Company"

                loc_el = card.select_one(".job-search-card__location")
                loc = loc_el.get_text(strip=True) if loc_el else location

                time_el = card.select_one("time")
                posted_time = time_el.get_text(strip=True) if time_el else ""

                link_el = card.select_one("a.base-card__full-link, a")
                raw_url = link_el.get("href", "") if link_el else ""

                if not job_id and raw_url:
                    match = re.search(r"-(\d+)\?", raw_url) or re.search(r"/view/(\d+)", raw_url)
                    if match:
                        job_id = match.group(1)

                if not job_id:
                    continue

                clean_url = f"https://www.linkedin.com/jobs/view/{job_id}"

                jobs.append({
                    "job_id": job_id,
                    "title": title,
                    "company": company,
                    "location": loc,
                    "posted_time": posted_time,
                    "job_url": clean_url,
                    "keyword": keyword
                })

        except Exception as e:
            print(f"❌ خطأ أثناء البحث في لينكدإن ({keyword} - {location}): {e}")

        return jobs

    def fetch_job_description(self, job_id: str) -> str:
        """
        جلب النص الكامل لتفاصيل ووصف الوظيفة المطلوبة عبر معرفها
        """
        url = JOB_DETAIL_ENDPOINT.format(job_id=job_id)
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return ""

            soup = BeautifulSoup(resp.text, "html.parser")
            desc_el = soup.select_one(".show-more-less-html__markup")
            if desc_el:
                # استبدال الـ <br> بأسطر جديدة للحفاظ على التنسيق
                for br in desc_el.find_all("br"):
                    br.replace_with("\n")
                return desc_el.get_text(separator="\n").strip()

            # محاولة احتياطية
            fallback_el = soup.select_one(".description__text")
            if fallback_el:
                return fallback_el.get_text(separator="\n").strip()

        except Exception as e:
            print(f"⚠️ تعذر جلب تفاصيل الوظيفة {job_id}: {e}")

        return ""
