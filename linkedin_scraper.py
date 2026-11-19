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
        self._company_cache: Dict[str, Dict[str, Any]] = {}

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
        resp = None

        # محاولة البحث مع إعادة المحاولة في حال ظهور 429
        for attempt in range(2):
            time.sleep(random.uniform(3.0, 5.0))
            try:
                resp = self.session.get(SEARCH_ENDPOINT, params=params, headers=self._get_headers(), timeout=15)
                if resp.status_code == 429:
                    print(f"⏳ تم الوصول لحد الطلبات مؤقتاً (429) للبحث عن '{keyword}' - انتظار 15 ثانية وإعادة المحاولة...")
                    time.sleep(15)
                    continue
                elif resp.status_code != 200:
                    print(f"⚠️ استجابة لينكدإن ({resp.status_code}) للبحث عن: '{keyword}' في '{location}'")
                    return jobs
                break
            except Exception as e:
                if attempt == 0:
                    time.sleep(5)
                    continue
                print(f"❌ خطأ أثناء البحث في لينكدإن ({keyword} - {location}): {e}")
                return jobs

        if not resp or resp.status_code != 200:
            return jobs

        try:
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

                # رابط صفحة الشركة على لينكدإن
                company_link_el = card.select_one("h4.base-search-card__subtitle a")
                company_url = company_link_el.get("href", "") if company_link_el else ""
                if company_url and "?" in company_url:
                    company_url = company_url.split("?")[0].strip()

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
                    "company_url": company_url,
                    "location": loc,
                    "posted_time": posted_time,
                    "job_url": clean_url,
                    "keyword": keyword
                })

        except Exception as e:
            print(f"❌ خطأ أثناء البحث في لينكدإن ({keyword} - {location}): {e}")

        return jobs

    def fetch_job_details(self, job_id: str) -> Dict[str, Any]:
        """
        جلب التفاصيل الكاملة للوظيفة:
        - الوصف الوظيفي الكامل
        - مجالات الصناعة المحددة في الوظيفة (Criteria -> Industries)
        - موقع الوظيفة الدقيق (Topcard flavor)
        - رابط صفحة الشركة على لينكدإن
        """
        url = JOB_DETAIL_ENDPOINT.format(job_id=job_id)
        details = {
            "description": "",
            "job_industries": [],
            "job_location": "",
            "company_url": ""
        }
        try:
            resp = self.session.get(url, headers=self._get_headers(), timeout=15)
            if resp.status_code != 200:
                return details

            soup = BeautifulSoup(resp.text, "html.parser")

            # 1. الوصف الوظيفي
            desc_el = soup.select_one(".show-more-less-html__markup")
            if desc_el:
                for br in desc_el.find_all("br"):
                    br.replace_with("\n")
                details["description"] = desc_el.get_text(separator="\n").strip()
            else:
                fallback_el = soup.select_one(".description__text")
                if fallback_el:
                    details["description"] = fallback_el.get_text(separator="\n").strip()

            # 2. قطاعات الصناعة المحددة للوظيفة (Criteria -> Industries)
            for item in soup.select(".description__job-criteria-item"):
                sub = item.select_one(".description__job-criteria-subheader")
                txt = item.select_one(".description__job-criteria-text")
                if sub and txt:
                    sub_clean = sub.get_text(strip=True).lower()
                    if "industr" in sub_clean or "مجال" in sub_clean:
                        details["job_industries"].append(txt.get_text(strip=True))

            # 3. موقع الوظيفة وموقع الشركة من الـ topcard
            flavors = [f.get_text(strip=True) for f in soup.select(".topcard__flavor")]
            if len(flavors) >= 2:
                details["job_location"] = flavors[1]
            elif flavors:
                details["job_location"] = flavors[0]

            # 4. رابط صفحة الشركة
            comp_link = soup.select_one("a.topcard__org-name-link, .topcard__flavor--black-link")
            if comp_link and comp_link.get("href"):
                c_url = comp_link.get("href")
                if "?" in c_url:
                    c_url = c_url.split("?")[0].strip()
                details["company_url"] = c_url

        except Exception as e:
            print(f"⚠️ تعذر جلب تفاصيل الوظيفة {job_id}: {e}")

        return details

    def fetch_job_description(self, job_id: str) -> str:
        """جلب النص الكامل لوصف الوظيفة (للتوافق القديم)"""
        return self.fetch_job_details(job_id).get("description", "")

    def fetch_company_profile(self, company_url: str) -> Dict[str, str]:
        """
        جلب وتصنيف بيانات الشركة من صفحتها على لينكدإن:
        - مجال وتصنيف الشركة (Industry)
        - المقر الرئيسي أو دولة/مدينة الصفحة (Headquarters)
        - العنوان الفرعي (Subtitle)
        """
        if not company_url:
            return {"industry": "", "location": "", "subtitle": ""}

        clean_url = company_url.split("?")[0].rstrip("/")
        if clean_url in self._company_cache:
            return self._company_cache[clean_url]

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8"
        }

        profile = {"industry": "", "location": "", "subtitle": ""}

        try:
            r = requests.get(clean_url, headers=headers, timeout=8)
            if r.status_code != 200:
                self._company_cache[clean_url] = profile
                return profile

            soup = BeautifulSoup(r.text, "html.parser")

            # 1. فحص قائمة التعريفات dt / dd (تتضمن Industry و Headquarters بدقة)
            dts = soup.select("dt")
            dds = soup.select("dd")
            for dt, dd in zip(dts, dds):
                dt_txt = dt.get_text(strip=True).lower()
                dd_txt = dd.get_text(strip=True)
                if any(k in dt_txt for k in ["industry", "مجال"]):
                    profile["industry"] = dd_txt
                elif any(k in dt_txt for k in ["headquarters", "المقر الرئيسي"]):
                    profile["location"] = dd_txt

            # 2. فحص العنوان الرئيسي (Headline)
            if not profile["industry"]:
                h2 = soup.select_one("h2.top-card-layout__headline")
                if h2:
                    profile["industry"] = h2.get_text(strip=True)

            # 3. فحص العنوان الفرعي والملخص (Subtitle)
            subtitle_el = soup.select_one(".org-top-card-summary-info-list, .top-card-layout__entity-info")
            if subtitle_el:
                profile["subtitle"] = subtitle_el.get_text(" · ", strip=True)

            # 4. إذا لم يظهر الموقع في dt/dd، نبحث في قسم locations أو subtitle
            if not profile["location"]:
                loc_sec = soup.select_one("section.locations")
                if loc_sec:
                    profile["location"] = loc_sec.get_text(separator=" ", strip=True)
                elif profile["subtitle"]:
                    profile["location"] = profile["subtitle"]

        except Exception as e:
            # في حال حدوث أي خطأ بالشبكة، لا نوقف النظام
            pass

        self._company_cache[clean_url] = profile
        return profile
