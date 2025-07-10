import csv
import json
import re
import base64
import time
import threading
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

AB_HINTS = {
    "optimizely": ["optimizely", "_opt_", "cdn.optimizely.com", "optimizelyData"],
    "vwo": ["visualwebsiteoptimizer", "_vwo_", "vwoExperiments", "/vwo"],
    "google_optimize": ["optimize.js", "_gaexp", "dataLayer"],
    "ab_tasty": ["abtasty", "ABTasty", "ABTastyParams"],
    "convert": ["convertexperiments.com", "convert.com"],
    "adobe_target": ["at.js", "mbox"],
    "split": ["split.io", "SplitClient"],
    "launchdarkly": ["ldclient.js", "LDClient", "featureFlags"],
    "instapage": ["instapage.com", "ab_test"],
    "qubit": ["qubit.com", "Qubit", "qubitExperiments"],
    "sitespect": ["sitespect.com"],
    "oracle_maxymiser": ["maxymiser", "oracle.com"],
    "intellimize": ["intellimize", "intellimize.io"],
    "monetate": ["monetate", "monetate_data"],
    "webtrends": ["webtrendsOptimize"],
    "evergage": ["evergage", "SalesforceInteractionStudio"],
    "figpii": ["figpii"],
    "omniConvert": ["omniconvert"],
    "conductrics": ["conductrics"]
}

KNOWN_GLOBALS = [
    "optimizely", "vwoExperiments", "ABTasty", "SplitClient", "LDClient",
    "Qubit", "mbox", "__INITIAL_DATA__", "experiment", "experiments"
]

INPUT_FILE = "newdomains.txt"
OUTPUT_FILE = "ab_test_outputv4.csv"
FAILED_FILE = "failed.txt"
BATCH_START = 200
BATCH_END = 300
THREADS = 5

def get_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=opts)


def detect_platforms(text):
    detected = set()
    for tool, hints in AB_HINTS.items():
        for hint in hints:
            if hint.lower() in text.lower():
                detected.add(tool)
                break
    return detected


def deep_extract(obj, prefix=""):
    kvs = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if "variant" in k.lower():
                kvs.add(f"variant::{full_key}={v}")
            elif any(x in k.lower() for x in ["goal", "metric", "track", "kpi"]):
                kvs.add(f"goal::{full_key}={v}")
            kvs.update(deep_extract(v, full_key))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            kvs.update(deep_extract(item, f"{prefix}[{i}]") if prefix else deep_extract(item))
    return kvs


def extract_ab_data(text):
    results = set()
    try:
        json_blocks = re.findall(r'\{[^\{\}]{20,30000}\}', text)
        for block in json_blocks:
            try:
                obj = json.loads(block)
                results.update(deep_extract(obj))
            except:
                continue
    except:
        pass
    try:
        decoded = base64.b64decode(text).decode("utf-8")
        obj = json.loads(decoded)
        results.update(deep_extract(obj))
    except:
        pass
    return results


def scrape_domain(domain):
    url = f"https://{domain}"
    ab_config, detected, scripts = set(), set(), set()

    for attempt in range(2):
        driver = get_driver()
        try:
            driver.set_page_load_timeout(30)
            driver.get(url)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(5)

            ready_state = driver.execute_script("return document.readyState")
            if ready_state != "complete":
                raise Exception("Page did not load completely")

            soup = BeautifulSoup(driver.page_source, "html.parser")

            for script in soup.find_all("script"):
                if script.string:
                    snippet = script.string[:200].replace("\n", " ")
                    platforms = detect_platforms(script.string)
                    for tool in platforms:
                        scripts.add(f"inline::{tool}::{snippet}")
                    ab_config.update(extract_ab_data(script.string))
                    detected.update(platforms)

            for script in soup.find_all("script", src=True):
                full_url = urljoin(url, script['src'])
                try:
                    r = requests.get(full_url, timeout=5)
                    if r.status_code == 200:
                        body = r.text[:3000]
                        platforms = detect_platforms(body)
                        for tool in platforms:
                            scripts.add(f"external::{tool}::{full_url}")
                        ab_config.update(extract_ab_data(body))
                        detected.update(platforms)
                except:
                    continue

            for c in driver.get_cookies():
                ab_config.update(extract_ab_data(c.get("value", "")))
                detected.update(detect_platforms(c.get("name", "") + c.get("value", "")))

            ls = driver.execute_script("""
                var out = {};
                for (var i = 0; i < localStorage.length; i++) {
                    var k = localStorage.key(i);
                    out[k] = localStorage.getItem(k);
                }
                return out;
            """)
            for k, v in ls.items():
                ab_config.update(extract_ab_data(v))
                detected.update(detect_platforms(k + v))

            ss = driver.execute_script("""
                var out = {};
                for (var i = 0; i < sessionStorage.length; i++) {
                    var k = sessionStorage.key(i);
                    out[k] = sessionStorage.getItem(k);
                }
                return out;
            """)
            for k, v in ss.items():
                ab_config.update(extract_ab_data(v))
                detected.update(detect_platforms(k + v))

            for var in KNOWN_GLOBALS:
                try:
                    val = driver.execute_script(f"return window.{var}")
                    if val:
                        ab_config.update(extract_ab_data(json.dumps(val)))
                        detected.update(detect_platforms(str(val)))
                except:
                    continue

            try:
                dl = driver.execute_script("return window.dataLayer")
                if isinstance(dl, list):
                    for entry in dl:
                        ab_config.update(extract_ab_data(json.dumps(entry)))
                        detected.update(detect_platforms(str(entry)))
            except:
                pass

            try:
                logs = driver.get_log("browser")
                for entry in logs:
                    if 'postMessage' in entry.get("message", ""):
                        msg = entry["message"]
                        detected.update(detect_platforms(msg))
                        ab_config.update(extract_ab_data(msg))
            except:
                pass

            return [
                domain,
                ";".join(sorted(ab_config)),
                ";".join(sorted(detected)),
                ";".join(sorted(scripts))
            ]

        except Exception as e:
            if attempt == 1:
                with open(FAILED_FILE, "a") as ferr:
                    ferr.write(f"{domain}\n")
                return None
        finally:
            driver.quit()

def main():
    with open(INPUT_FILE) as f:
        domains = [line.strip() for line in f if line.strip()]
    domains = domains[BATCH_START - 1:BATCH_END]

    with open(OUTPUT_FILE, "a", newline="") as fout:
        writer = csv.writer(fout)
        writer.writerow(["domain", "ab_configuration", "detected_platforms", "ab_tool_scripts"])

        threads = []
        lock = threading.Lock()

        def process_chunk(chunk):
            for domain in chunk:
                row = scrape_domain(domain)
                if row:
                    with lock:
                        writer.writerow(row)

        chunk_size = max(1, len(domains) // THREADS)
        for i in range(0, len(domains), chunk_size):
            t = threading.Thread(target=process_chunk, args=(domains[i:i + chunk_size],))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()


if __name__ == "__main__":
    main()
