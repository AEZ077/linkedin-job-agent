"""
وحدة جلب وبحث الوظائف من لينكدإن (LinkedIn Scraper)
تعتمد على واجهة البحث المباشرة العامة في لينكدإن (LinkedIn Guest Jobs API).
- لا تحتاج إلى تسجيل الدخول أو إدخال حسابك الشخصي (آمنة تماماً وخالية من مخاطر حظر الحساب).
- تجلب أحدث الوظائف المنشورة (sortBy=DD) مع الروابط المباشرة وتفاصيل الوصف الوظيفي.
"""

import re
import time
import random
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
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
        location: str = "Riyadh, Saudi Arabia",
        time_range: str = "r86400",
        work_type: str = "",
        max_jobs: int = 10,
        sort_by_recent: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        البحث عن الوظائف في لينكدإن بناءً على الكلمة المفتاحية والموقع ونطاق الوقت.
        يستخدم sortBy=DD افتراضياً لجلب أحدث الوظائف المنشورة فور نزولها.
        """
        jobs: List[Dict[str, Any]] = []
        seen_job_ids = set()
        offsets = [0, 25] if max_jobs > 10 else [0]

        for offset in offsets:
            if len(jobs) >= max_jobs:
                break

            params: Dict[str, Any] = {
                "keywords": keyword,
                "location": location,
                "f_TPR": time_range,
                "start": offset,
            }
            if sort_by_recent:
                params["sortBy"] = "DD"

            wt = work_type.lower()
            if wt == "remote":
                params["f_WT"] = "2"
            elif wt == "onsite":
                params["f_WT"] = "1"
            elif wt == "hybrid":
                params["f_WT"] = "3"

            resp = None
            for attempt in range(3):
                time.sleep(random.uniform(2.0, 3.8))
                try:
                    resp = self.session.get(
                        SEARCH_ENDPOINT,
                        params=params,
                        headers=self._get_headers(),
                        timeout=15,
                    )
                    if resp.status_code == 429:
                        wait_sec = 12 * (attempt + 1)
                        print(f"⏳ حد الطلبات مؤقتاً (429) لـ '{keyword}' - انتظار {wait_sec}ث...")
                        time.sleep(wait_sec)
                        continue
                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep(4)
                        continue
                    print(f"❌ خطأ أثناء البحث في لينكدإن ({keyword} - {location}): {e}")
                    break

            if not resp or resp.status_code != 200:
                continue

            try:
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("li div.base-card")
                if not cards:
                    break

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

                    if not job_id or job_id in seen_job_ids:
                        continue
                    seen_job_ids.add(job_id)

                    jobs.append({
                        "job_id": job_id,
                        "title": title,
                        "company": company,
                        "company_url": company_url,
                        "location": loc,
                        "posted_time": posted_time,
                        "job_url": f"https://www.linkedin.com/jobs/view/{job_id}",
                        "keyword": keyword,
                    })
            except Exception as e:
                print(f"⚠️ خطأ أثناء قراءة قائمة وظائف لينكدإن ({keyword}): {e}")

        return jobs

    def fetch_job_details(self, job_id: str) -> Dict[str, Any]:
        """
        جلب التفاصيل الكاملة للوظيفة: الوصف الوظيفي، القطاعات، نوع الدوام، المستوى الوظيفي، وموقع الوظيفة.
        """
        url = JOB_DETAIL_ENDPOINT.format(job_id=job_id)
        details: Dict[str, Any] = {
            "ok": False,
            "description": "",
            "job_industries": [],
            "job_location": "",
            "seniority_level": "",
            "employment_type": "",
            "company_url": "",
        }
        try:
            resp = self.session.get(url, headers=self._get_headers(), timeout=15)
            if resp.status_code == 429:
                time.sleep(10)
                resp = self.session.get(url, headers=self._get_headers(), timeout=15)
            if resp.status_code != 200:
                return details

            soup = BeautifulSoup(resp.text, "html.parser")
            details["ok"] = True

            desc_el = soup.select_one(".show-more-less-html__markup")
            if desc_el:
                for br in desc_el.find_all("br"):
                    br.replace_with("\n")
                for li in desc_el.find_all("li"):
                    li.insert(0, "• ")
                details["description"] = desc_el.get_text(separator="\n").strip()
            else:
                fallback_el = soup.select_one(".description__text")
                if fallback_el:
                    details["description"] = fallback_el.get_text(separator="\n").strip()

            for item in soup.select(".description__job-criteria-item"):
                sub = item.select_one(".description__job-criteria-subheader")
                txt = item.select_one(".description__job-criteria-text")
                if not (sub and txt):
                    continue
                sub_clean = sub.get_text(strip=True).lower()
                val = txt.get_text(strip=True)
                if "industr" in sub_clean or "مجال" in sub_clean:
                    details["job_industries"].append(val)
                elif "seniority" in sub_clean or "مستوى" in sub_clean:
                    details["seniority_level"] = val
                elif "employment" in sub_clean or "نوع التوظيف" in sub_clean:
                    details["employment_type"] = val

            flavors = [f.get_text(strip=True) for f in soup.select(".topcard__flavor")]
            if len(flavors) >= 2:
                details["job_location"] = flavors[1]
            elif flavors:
                details["job_location"] = flavors[0]

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

    def fetch_company_profile(self, company_url: str) -> Dict[str, Any]:
        """
        جلب بيانات الشركة من صفحتها على لينكدإن (Industry, Headquarters, Subtitle).
        لا يخزن النتائج الفاشلة مؤقتاً حتى لا يضيع فحص شركة بسبب حظر لحظي.
        """
        if not company_url:
            return {"ok": False, "industry": "", "location": "", "subtitle": ""}

        clean_url = company_url.split("?")[0].rstrip("/")
        if clean_url in self._company_cache:
            return self._company_cache[clean_url]

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        }

        profile: Dict[str, Any] = {"ok": False, "industry": "", "location": "", "subtitle": ""}

        try:
            r = requests.get(clean_url, headers=headers, timeout=10)
            if r.status_code != 200:
                return profile

            soup = BeautifulSoup(r.text, "html.parser")
            profile["ok"] = True

            dts = soup.select("dt")
            dds = soup.select("dd")
            for dt, dd in zip(dts, dds):
                dt_txt = dt.get_text(strip=True).lower()
                dd_txt = dd.get_text(strip=True)
                if any(k in dt_txt for k in ["industry", "مجال"]):
                    profile["industry"] = dd_txt
                elif any(k in dt_txt for k in ["headquarters", "المقر الرئيسي"]):
                    profile["location"] = dd_txt

            if not profile["industry"]:
                h2 = soup.select_one("h2.top-card-layout__headline")
                if h2:
                    profile["industry"] = h2.get_text(strip=True)

            subtitle_el = soup.select_one(".org-top-card-summary-info-list, .top-card-layout__entity-info")
            if subtitle_el:
                profile["subtitle"] = subtitle_el.get_text(" · ", strip=True)

            if not profile["location"]:
                loc_sec = soup.select_one("section.locations")
                if loc_sec:
                    profile["location"] = loc_sec.get_text(separator=" ", strip=True)
                elif profile["subtitle"]:
                    profile["location"] = profile["subtitle"]

            self._company_cache[clean_url] = profile
        except Exception:
            pass

        return profile
