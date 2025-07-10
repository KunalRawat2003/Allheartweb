import re
import csv
import json
import time
import os 
import base64
import requests
import threading
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor

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
}

KNOWN_GLOBALS = [
    "optimizely", "vwoExperiments", "ABTasty", "SplitClient", "LDClient",
    "Qubit", "mbox", "__INITIAL_DATA__", "experiment", "experiments"
]

INPUT_FILE = "newdomains.txt"
OUTPUT_FILE = "ab_test_outputv2.csv"
MAX_WORKERS = 5

lock = threading.Lock()

def get_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=opts)

def extract_ab_data(text):
    results = []
    try:
        json_blocks = re.findall(r'\{[^{}]{20,30000}\}', text)
        for block in json_blocks:
            try:
                obj = json.loads(block)
                results.extend(deep_extract(obj))
            except:
                continue
    except:
        pass
    try:
        decoded = base64.b64decode(text).decode("utf-8")
        obj = json.loads(decoded)
        results.extend(deep_extract(obj))
    except:
        pass
    return results

def deep_extract(obj, prefix=""):
    kvs = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if "variant" in k.lower():
                kvs.append(f"variant::{full_key}={v}")
            elif "goal" in k.lower():
                kvs.append(f"goal::{full_key}={v}")
            kvs.extend(deep_extract(v, full_key))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            kvs.extend(deep_extract(item, f"{prefix}[{idx}]"))
    return kvs

def detect_platforms(text):
    detected = set()
    for tool, hints in AB_HINTS.items():
        for hint in hints:
            if hint.lower() in text.lower():
                detected.add(tool)
                break
    return detected

BATCH_START = 1
BATCH_END = 20

def scrape_domain(domain):
    attempts = 2
    for attempt in range(attempts):
        driver = get_driver()
        url = f"https://{domain}"
        ab_config, detected, scripts = set(), set(), set()

        try:
            driver.set_page_load_timeout(30)
            driver.get(url)
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(5)

            # Validate page status
            ready_state = driver.execute_script("return document.readyState")
            if ready_state != "complete":
                raise Exception("Page did not load completely.")

            soup = BeautifulSoup(driver.page_source, "html.parser")

            # Inline scripts
            for script in soup.find_all("script"):
                if script.string:
                    snip = script.string[:200].replace("\n", "")
                    platforms = detect_platforms(script.string)
                    for tool in platforms:
                        scripts.add(f"inline::{tool}::{snip}")
                    ab_config.update(extract_ab_data(script.string))
                    detected.update(platforms)

            # External scripts
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

            # Cookies
            for c in driver.get_cookies():
                ab_config.update(extract_ab_data(c.get("value", "")))
                detected.update(detect_platforms(c.get("name", "") + c.get("value", "")))

            # Local storage
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

            # Session storage
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

            # Known window globals
            for var in KNOWN_GLOBALS:
                try:
                    val = driver.execute_script(f"return window.{var}")
                    if val:
                        if var == "__INITIAL_STATE__":
                            if "optimist" in str(val) or "variationId" in str(val):
                                ab_config.update(extract_ab_data(json.dumps(val)))
                                detected.add("optimizely")
                        else:
                            ab_config.update(extract_ab_data(json.dumps(val)))
                except:
                    continue

            # DataLayer
            try:
                dl = driver.execute_script("return window.dataLayer")
                if isinstance(dl, list):
                    for entry in dl:
                        ab_config.update(extract_ab_data(json.dumps(entry)))
            except:
                pass

            # postMessage sniffing
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
            if attempt == attempts - 1:
                print(f"[ERROR] {domain} failed after {attempts} attempts: {e}")
                os.makedirs("screenshots", exist_ok=True)
                try:
                    driver.save_screenshot(f"screenshots/{domain}.png")
                except:
                    pass
                return [domain, "", "", ""]
        finally:
            driver.quit()

def main():
    with open(INPUT_FILE, "r") as f:
        domains = [line.strip() for line in f if line.strip()]

    domains = domains[BATCH_START - 1:BATCH_END]

    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["domain", "ab_configuration", "detected_platforms", "ab_tool_scripts"])

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(scrape_domain, domain): domain for domain in domains}
            for future in futures:
                try:
                    result = future.result()
                    with lock:
                        writer.writerow(result)
                except Exception as e:
                    print(f"[Thread ERROR] {futures[future]}: {e}")

if __name__ == "__main__":
    main()
