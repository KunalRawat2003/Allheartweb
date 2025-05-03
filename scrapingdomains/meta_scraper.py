import aiohttp
import asyncio
from bs4 import BeautifulSoup
import csv
import os
from aiohttp import ClientSession, ClientTimeout, DummyCookieJar

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90 Safari/537.36"
}

csv.field_size_limit(2**31 - 1)

BATCH_START = 785000
BATCH_END = 785500
CONCURRENT_REQUESTS = 100
RETRIES = 1
TIMEOUT = ClientTimeout(total=20)

desired_column_order = [
    "Domain", "title", "og:title", "twitter:title",
    "description", "og:description", "twitter:description",
    "keywords", "robots", "viewport", "charset",
    "author", "copyright", "theme-color", "language", "canonical",
    "og:url", "og:type", "og:image", "favicon", "twitter:image", "twitter:card",
    "mobile-web-app-capable", "apple-mobile-web-app-title", "apple-mobile-web-app-status-bar-style",
    "google-site-verification", "msvalidate.01"
]

failed_domains = set()

with open("newdomains.txt", "r") as f:
    all_domains = [d.strip() for d in f if d.strip()]
    domains = all_domains[BATCH_START:BATCH_END]


async def fetch(session: ClientSession, domain: str, retries=RETRIES):
    for protocol in ["https", "http"]:
        url = f"{protocol}://{domain}"
        try:
            async with session.get(url, headers=headers, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    return None

                html = await resp.text(errors="ignore")

                try:
                    soup = BeautifulSoup(html, "lxml")
                except Exception:
                    soup = BeautifulSoup(html, "html.parser")

                values = {}
                meta_tags = {tag: "" for tag in desired_column_order[1:]}

                for tag in soup.find_all("meta"):
                    key = (tag.get("name") or tag.get("property") or tag.get("itemprop") or "").lower().strip()
                    value = tag.get("content", "").strip()
                    if key == "title":
                        values["meta:title"] = (value)

                for tag in soup.find_all("meta"):
                    if tag.get("charset"):
                        meta_tags["charset"] = (tag.get("charset").strip())
                        continue
                    key = (tag.get("name") or tag.get("property") or tag.get("itemprop") or "").lower().strip()
                    value = tag.get("content", "").strip()
                    if not key or not value:
                        continue
                    values[key] = (value)

                canonical = soup.find("link", rel="canonical")
                if canonical and canonical.get("href"):
                    values["canonical"] = (canonical.get("href").strip())

                favicon = soup.find("link", rel="icon") or soup.find("link", rel="shortcut icon")
                if favicon and favicon.get("href"):
                    values["favicon"] = (favicon.get("href").strip())

                for tag in ["og:type", "og:image", "twitter:image", "twitter:card",
                            "theme-color", "mobile-web-app-capable", "apple-mobile-web-app-title",
                            "apple-mobile-web-app-status-bar-style", "google-site-verification", "msvalidate.01"]:
                    meta = soup.find("meta", attrs={"name": tag}) or soup.find("meta", attrs={"property": tag})
                    if meta and meta.get("content"):
                        values[tag] = (meta.get("content").strip())

                def dedup_fields(field_group):
                    seen, final_values = set(), {}
                    for key in field_group:
                        val = values.get(key)
                        if val:
                            if val not in seen:
                                final_values[key] = val
                                seen.add(val)
                            else:
                                final_values[key] = ""
                    return final_values

                title_vals = dedup_fields(["title", "og:title", "twitter:title"])
                desc_vals = dedup_fields(["description", "og:description", "twitter:description"])
                url_vals = dedup_fields(["og:url", "canonical", "favicon"])

                for k, v in {**values, **title_vals, **desc_vals, **url_vals}.items():
                    if k in meta_tags:
                        meta_tags[k] = (v)

                return domain, meta_tags

        except Exception as e:
            
            if retries > 0:
                await asyncio.sleep(0.5)
                return await fetch(session, domain, retries - 1)
            else:
                if domain not in failed_domains:
                    failed_domains.add(domain)
                    with open("failed.txt", "a") as fail_log:
                        fail_log.write(f"{domain}\n")
                return None


async def worker(queue: asyncio.Queue, session: ClientSession, results: list):
    while not queue.empty():
        domain = await queue.get()
        result = await fetch(session, domain)
        if result:
            results.append(result)
        queue.task_done()

async def main():
    queue = asyncio.Queue()
    for domain in domains:
        await queue.put(domain)

    results = []
    connector = aiohttp.TCPConnector(limit=CONCURRENT_REQUESTS, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector, 
                timeout=TIMEOUT,
                cookie_jar=DummyCookieJar()) as session:
        tasks = [worker(queue, session, results) for _ in range(CONCURRENT_REQUESTS)]
        await asyncio.gather(*tasks)

    return results

results = asyncio.run(main())

file_exists = os.path.exists("newdomains_tags.csv") and os.path.getsize("newdomains_tags.csv") > 0
with open("newdomains_tags.csv", "a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=desired_column_order)
    if not file_exists:
        writer.writeheader()
    for result in results:
        if result is None:
            continue
        domain, meta_data = result
        meta_data["Domain"] = domain
        writer.writerow(meta_data)

print(f"Finished scraping batch: {BATCH_START}-{BATCH_END}")
