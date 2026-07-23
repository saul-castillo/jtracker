"""Connectors for the public applicant-tracking systems used by configured sources."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class FetchResult:
    jobs: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)


def _session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
            "User-Agent": "jtracker/2.0 public-careers-monitor",
        }
    )
    session.mount("https://", adapter)
    return session


def _text(value: Any) -> str:
    if value is None:
        return ""
    return BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)


def _join(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(_join(item) for item in value if item)
    if isinstance(value, dict):
        return ", ".join(_join(item) for item in value.values() if item)
    return str(value or "").strip()


def _job(
    source: dict[str, Any],
    *,
    source_id: Any,
    title: Any,
    location: Any,
    url: Any,
    description: Any = "",
    posted: Any = "",
    country_code: Any = "",
) -> dict[str, Any]:
    return {
        "company": source["company"],
        "platform": source.get("platform") or source["kind"].title(),
        "source_id": str(source_id or url or title),
        "title": _text(title),
        "location": _text(location) or "Unknown",
        "url": str(url or "").strip(),
        "description": _text(description),
        "posted": str(posted or "").strip(),
        "country_code": str(country_code or source.get("default_country", "")).upper(),
    }


def greenhouse(source: dict[str, Any], session: requests.Session) -> FetchResult:
    url = f"https://boards-api.greenhouse.io/v1/boards/{source['token']}/jobs"
    response = session.get(url, params={"content": "true"}, timeout=60)
    response.raise_for_status()
    jobs = []
    for item in response.json().get("jobs", []):
        jobs.append(
            _job(
                source,
                source_id=item.get("id"),
                title=item.get("title"),
                location=(item.get("location") or {}).get("name"),
                url=item.get("absolute_url"),
                description=item.get("content"),
                posted=item.get("updated_at"),
            )
        )
    return FetchResult(jobs)


def lever(source: dict[str, Any], session: requests.Session) -> FetchResult:
    url = f"https://api.lever.co/v0/postings/{source['token']}"
    response = session.get(url, params={"mode": "json"}, timeout=35)
    response.raise_for_status()
    jobs = []
    for item in response.json():
        categories = item.get("categories") or {}
        jobs.append(
            _job(
                source,
                source_id=item.get("id"),
                title=item.get("text"),
                location=categories.get("location"),
                url=item.get("hostedUrl"),
                description=item.get("descriptionPlain") or item.get("description"),
                posted=item.get("createdAt"),
            )
        )
    return FetchResult(jobs)


def ashby(source: dict[str, Any], session: requests.Session) -> FetchResult:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{source['token']}"
    response = session.get(url, timeout=35)
    response.raise_for_status()
    jobs = []
    for item in response.json().get("jobs", []):
        address = ((item.get("address") or {}).get("postalAddress") or {})
        location = item.get("location")
        secondary = item.get("secondaryLocations") or []
        if secondary:
            location = "; ".join([location, *[_join(value) for value in secondary]])
        country = address.get("addressCountry")
        country_code = "US" if str(country).lower() in {"us", "usa", "united states"} else ""
        jobs.append(
            _job(
                source,
                source_id=item.get("id"),
                title=item.get("title"),
                location=location,
                url=item.get("jobUrl"),
                description=item.get("descriptionPlain") or item.get("descriptionHtml"),
                posted=item.get("publishedAt"),
                country_code=country_code,
            )
        )
    return FetchResult(jobs)


def workday(source: dict[str, Any], session: requests.Session) -> FetchResult:
    endpoint = source["endpoint"].rstrip("/")
    match = re.match(
        r"(?P<host>https://[^/]+)/wday/cxs/[^/]+/(?P<site>[^/]+)/jobs$", endpoint
    )
    if not match:
        raise ValueError(f"invalid Workday endpoint: {endpoint}")

    detail_base = endpoint.rsplit("/jobs", 1)[0]
    public_base = f"{match.group('host')}/{match.group('site')}"
    postings: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    for query in source.get("queries", ["2027"]):
        offset = 0
        while True:
            response = session.post(
                endpoint,
                json={
                    "appliedFacets": {},
                    "limit": 20,
                    "offset": offset,
                    "searchText": query,
                },
                timeout=40,
            )
            response.raise_for_status()
            payload = response.json()
            page = payload.get("jobPostings") or []
            for item in page:
                path = item.get("externalPath")
                if path:
                    postings[path] = item
            offset += len(page)
            if not page or offset >= int(payload.get("total") or 0):
                break

    jobs = []
    for path, summary in postings.items():
        try:
            response = session.get(f"{detail_base}{path}", timeout=35)
            response.raise_for_status()
            info = response.json().get("jobPostingInfo") or {}
        except Exception as exc:  # keep the searchable stub and report degraded detail coverage
            warnings.append(f"{source['company']} detail {path}: {exc}")
            info = {}

        requisition_location = info.get("jobRequisitionLocation") or {}
        country = requisition_location.get("country") or {}
        country_code = country.get("alpha2Code")
        external_url = info.get("externalUrl")
        if not external_url:
            external_url = f"{public_base}{path}"
        jobs.append(
            _job(
                source,
                source_id=info.get("jobReqId") or path,
                title=info.get("title") or summary.get("title"),
                location=info.get("location") or summary.get("locationsText"),
                url=external_url,
                description=info.get("jobDescription"),
                posted=info.get("postedOn") or info.get("startDate"),
                country_code=country_code,
            )
        )
    return FetchResult(jobs, warnings)


def jibe(source: dict[str, Any], session: requests.Session) -> FetchResult:
    endpoint = source["endpoint"]
    records: dict[str, dict[str, Any]] = {}
    for query in source.get("queries", ["2027", "intern"]):
        page = 1
        while True:
            response = session.get(
                endpoint, params={"keywords": query, "page": page}, timeout=40
            )
            response.raise_for_status()
            payload = response.json()
            items = payload.get("jobs") or []
            for wrapper in items:
                item = wrapper.get("data", wrapper)
                source_id = str(item.get("req_id") or item.get("slug") or "")
                if source_id:
                    records[source_id] = item
            count = int(payload.get("count") or len(items))
            total = int(payload.get("totalCount") or len(items))
            if not items or page * max(count, 1) >= total:
                break
            page += 1

    jobs = []
    for source_id, item in records.items():
        jobs.append(
            _job(
                source,
                source_id=source_id,
                title=item.get("title"),
                location=item.get("full_location")
                or item.get("location_name")
                or item.get("city"),
                url=item.get("canonical_url")
                or item.get("apply_url")
                or f"https://careers.amd.com/jobs/{source_id}",
                description=item.get("description") or item.get("responsibilities"),
                posted=item.get("posted_date"),
                country_code=item.get("country_code"),
            )
        )
    return FetchResult(jobs)


def eightfold(source: dict[str, Any], session: requests.Session) -> FetchResult:
    host = source["host"].rstrip("/")
    domain = source["domain"]
    positions: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for query in source.get("queries", ["2027"]):
        start = 0
        while True:
            response = session.get(
                f"{host}/api/pcsx/search",
                params={
                    "domain": domain,
                    "query": query,
                    "location": "",
                    "start": start,
                },
                timeout=40,
            )
            response.raise_for_status()
            data = response.json().get("data") or {}
            page = data.get("positions") or []
            for item in page:
                positions[str(item.get("id"))] = item
            start += len(page)
            if not page or start >= int(data.get("count") or 0):
                break

    jobs = []
    for source_id, summary in positions.items():
        try:
            response = session.get(
                f"{host}/api/pcsx/position_details",
                params={"position_id": source_id, "domain": domain, "hl": "en"},
                timeout=35,
            )
            response.raise_for_status()
            detail = response.json().get("data") or {}
        except Exception as exc:
            warnings.append(f"{source['company']} detail {source_id}: {exc}")
            detail = {}

        locations = detail.get("locations") or summary.get("locations") or []
        standardized = (
            detail.get("standardizedLocations")
            or summary.get("standardizedLocations")
            or []
        )
        location = _join(locations) or _join(standardized)
        country_code = ""
        for value in standardized:
            code_match = re.search(r",\s*([A-Z]{2})$", str(value))
            if code_match:
                country_code = code_match.group(1)
                if country_code == "US":
                    break
        position_url = detail.get("positionUrl") or summary.get("positionUrl") or ""
        jobs.append(
            _job(
                source,
                source_id=detail.get("id") or source_id,
                title=detail.get("name") or summary.get("name"),
                location=location,
                url=urljoin(f"{host}/", position_url),
                description=detail.get("jobDescription"),
                posted=detail.get("postedTs") or summary.get("postedTs"),
                country_code=country_code,
            )
        )
    return FetchResult(jobs, warnings)


def oracle(source: dict[str, Any], session: requests.Session) -> FetchResult:
    host = source["host"].rstrip("/")
    site = source["site"]
    endpoint = f"{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    records: dict[str, dict[str, Any]] = {}
    for query in source.get("queries", ["2027"]):
        offset = 0
        limit = 25
        while True:
            finder = (
                f"findReqs;siteNumber={site},limit={limit},offset={offset},"
                f"keyword={query},sortBy=POSTING_DATES_DESC"
            )
            response = session.get(
                endpoint,
                params={"onlyData": "true", "expand": "requisitionList", "finder": finder},
                timeout=45,
            )
            response.raise_for_status()
            containers = response.json().get("items") or []
            container = containers[0] if containers else {}
            page = container.get("requisitionList") or []
            for item in page:
                records[str(item.get("Id"))] = item
            offset += len(page)
            if not page or offset >= int(container.get("TotalJobsCount") or 0):
                break

    jobs = []
    warnings: list[str] = []
    for source_id, item in records.items():
        public_url = f"{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{source_id}"
        description = item.get("ShortDescription") or ""
        try:
            response = session.get(public_url, timeout=35)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            meta = soup.find("meta", attrs={"property": "og:description"})
            if meta and meta.get("content"):
                description = meta["content"]
        except Exception as exc:
            warnings.append(f"{source['company']} detail {source_id}: {exc}")
        country = item.get("PrimaryLocationCountry") or ""
        jobs.append(
            _job(
                source,
                source_id=source_id,
                title=item.get("Title"),
                location=item.get("PrimaryLocation"),
                url=public_url,
                description=description,
                posted=item.get("PostedDate"),
                country_code="US"
                if str(country).lower() in {"us", "usa", "united states"}
                else "",
            )
        )
    return FetchResult(jobs, warnings)


def smartrecruiters(source: dict[str, Any], session: requests.Session) -> FetchResult:
    company_id = source["token"]
    endpoint = f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings"
    summaries: dict[str, dict[str, Any]] = {}
    for query in source.get("queries", ["2027"]):
        offset = 0
        limit = 100
        while True:
            response = session.get(
                endpoint,
                params={"limit": limit, "offset": offset, "q": query},
                timeout=40,
            )
            response.raise_for_status()
            payload = response.json()
            page = payload.get("content") or []
            for item in page:
                summaries[str(item.get("id"))] = item
            offset += len(page)
            if not page or offset >= int(payload.get("totalFound") or 0):
                break

    jobs = []
    warnings: list[str] = []
    for source_id, summary in summaries.items():
        try:
            response = session.get(f"{endpoint}/{source_id}", timeout=35)
            response.raise_for_status()
            item = response.json()
        except Exception as exc:
            warnings.append(f"{source['company']} detail {source_id}: {exc}")
            item = summary
        sections = ((item.get("jobAd") or {}).get("sections") or {})
        description = " ".join(
            str((sections.get(name) or {}).get("text") or "")
            for name in (
                "companyDescription",
                "jobDescription",
                "qualifications",
                "additionalInformation",
            )
        )
        location = item.get("location") or summary.get("location") or {}
        country = location.get("country") or ""
        jobs.append(
            _job(
                source,
                source_id=source_id,
                title=item.get("name") or summary.get("name"),
                location=location.get("fullLocation"),
                url=item.get("postingUrl")
                or summary.get("postingUrl")
                or f"https://jobs.smartrecruiters.com/{company_id}/{source_id}",
                description=description,
                posted=item.get("releasedDate") or summary.get("releasedDate"),
                country_code="US"
                if str(country).lower() in {"us", "usa", "united states"}
                else country,
            )
        )
    return FetchResult(jobs, warnings)


def talentbrew(source: dict[str, Any], session: requests.Session) -> FetchResult:
    base = source["base_url"].rstrip("/")
    search_url = f"{base}/search-jobs"
    response = session.get(
        search_url,
        params={"k": source.get("query", "2027"), "orgIds": source["org_id"]},
        timeout=40,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    links: dict[str, str] = {}
    for card in soup.select(".search-results-list__list-item, #search-results li"):
        anchor = card.select_one("a.sr-job-link, a[href*='/job/']")
        if anchor and anchor.get("href"):
            detail_url = urljoin(f"{base}/", anchor["href"])
            links[detail_url] = anchor.get_text(" ", strip=True)

    jobs = []
    warnings: list[str] = []
    for detail_url, fallback_title in links.items():
        try:
            response = session.get(detail_url, timeout=35)
            response.raise_for_status()
            detail_soup = BeautifulSoup(response.text, "html.parser")
            posting: dict[str, Any] = {}
            for script in detail_soup.select('script[type="application/ld+json"]'):
                try:
                    candidate = json.loads(script.string or "{}")
                except json.JSONDecodeError:
                    continue
                candidates = candidate if isinstance(candidate, list) else [candidate]
                for value in candidates:
                    if isinstance(value, dict) and value.get("@type") == "JobPosting":
                        posting = value
                        break
                if posting:
                    break
            job_location = posting.get("jobLocation") or {}
            if isinstance(job_location, list):
                job_location = job_location[0] if job_location else {}
            address = job_location.get("address") or {}
            if isinstance(address, str):
                location = address
                country = ""
            else:
                location = ", ".join(
                    str(address.get(key))
                    for key in ("addressLocality", "addressRegion", "addressCountry")
                    if address.get(key)
                )
                country = address.get("addressCountry") or ""
            identifier = posting.get("identifier") or {}
            source_id = (
                identifier.get("value")
                if isinstance(identifier, dict)
                else identifier
            )
            jobs.append(
                _job(
                    source,
                    source_id=source_id or detail_url,
                    title=posting.get("title") or fallback_title,
                    location=location,
                    url=posting.get("url") or detail_url,
                    description=posting.get("description"),
                    posted=posting.get("datePosted"),
                    country_code="US"
                    if str(country).lower()
                    in {"us", "usa", "united states", "united states of america"}
                    else country,
                )
            )
        except Exception as exc:
            warnings.append(f"{source['company']} detail {detail_url}: {exc}")
    return FetchResult(jobs, warnings)


def avature(source: dict[str, Any], session: requests.Session) -> FetchResult:
    base = source["base_url"].rstrip("/")
    next_url = f"{base}/SearchJobs?search={source.get('query', '2027')}"
    detail_links: dict[str, dict[str, str]] = {}
    visited: set[str] = set()

    while next_url and next_url not in visited:
        visited.add(next_url)
        response = session.get(next_url, timeout=40)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for card in soup.select("article.article--result, article.article"):
            anchor = card.select_one(".article__header__text__title a, a[href*='/job/']")
            if not anchor or not anchor.get("href"):
                continue
            detail_url = urljoin(f"{base}/", anchor["href"])
            location_node = card.select_one(".list-item-location")
            id_node = card.select_one(".list-item-jobId")
            detail_links[detail_url] = {
                "title": anchor.get_text(" ", strip=True),
                "location": location_node.get_text(" ", strip=True)
                if location_node
                else "",
                "source_id": id_node.get_text(" ", strip=True) if id_node else detail_url,
            }
        next_anchor = soup.select_one("a.paginationNextLink, a[rel='next']")
        next_url = (
            urljoin(f"{base}/", next_anchor["href"])
            if next_anchor and next_anchor.get("href")
            else ""
        )

    jobs = []
    warnings: list[str] = []
    for detail_url, summary in detail_links.items():
        try:
            response = session.get(detail_url, timeout=35)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            title_node = soup.select_one("h1, .article__header__text__title")
            content = soup.select_one("#section1__content, .article__content")
            jobs.append(
                _job(
                    source,
                    source_id=summary["source_id"],
                    title=title_node.get_text(" ", strip=True)
                    if title_node
                    else summary["title"],
                    location=summary["location"],
                    url=detail_url,
                    description=content.get_text(" ", strip=True) if content else "",
                )
            )
        except Exception as exc:
            warnings.append(f"{source['company']} detail {detail_url}: {exc}")
    return FetchResult(jobs, warnings)


FETCHERS = {
    "ashby": ashby,
    "avature": avature,
    "eightfold": eightfold,
    "greenhouse": greenhouse,
    "jibe": jibe,
    "lever": lever,
    "oracle": oracle,
    "smartrecruiters": smartrecruiters,
    "talentbrew": talentbrew,
    "workday": workday,
}


def fetch(source: dict[str, Any]) -> FetchResult:
    kind = source["kind"]
    if kind not in FETCHERS:
        raise ValueError(f"unsupported source kind: {kind}")
    with _session() as session:
        return FETCHERS[kind](source, session)


def epoch_date(value: Any) -> str:
    """Convert a seconds or milliseconds epoch to an ISO date when useful."""
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if not isinstance(value, (int, float)):
        return str(value or "")
    if value > 10_000_000_000:
        value /= 1000
    return datetime.fromtimestamp(value, timezone.utc).date().isoformat()
