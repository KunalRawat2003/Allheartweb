import asyncio
import aiohttp
from bs4 import BeautifulSoup, Doctype
import csv
import time
from urllib.parse import urlparse
import random
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
import warnings
warnings.filterwarnings("ignore")

# Add these to your configuration section
SELENIUM_RETRIES = 0
SELENIUM_TIMEOUT = 30  # seconds
HEADLESS = True  # Run browser in headless mode

# Configuration
INPUT_FILE = 'newdomains.txt'
OUTPUT_FILE = 'technical_details.csv'
FAILED_DOMAINS_FILE = 'failed_domains.txt'
CONCURRENT_REQUESTS = 80
TIMEOUT = aiohttp.ClientTimeout(total=30)
RETRIES = 2
BATCH_START = 10100
BATCH_END = 11000
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
]


# Define the desired column order for CSV
DESIRED_COLUMNS = [
    "domain",
    "doctype", "html_dir",
    # ARIA Attributes
    "aria_labels", "aria_labelledby", "aria_describedby", "aria_hidden", "aria_live",
    # SVG Elements
    "svg_ids", "svg_classes", "svg_data_attrs",
    # Canvas Elements
    "canvas_ids", "canvas_classes", "canvas_data_attrs",
    # Web Components
    "web_component_tags", "web_component_ids", "web_component_classes",
    # Embedded Content
    "iframe_srcs", "iframe_loading", "object_data", "embed_src",
    # PWA Features
    "service_worker", "manifest_link",
    # Structured Data
    "structured_data",
    # Data Attributes
    "data_attributes",
    # HTTP/Network
    "http_version", "compression", "cdn_usage",
    # Security Headers
    "content_security_policy", "strict_transport_security", "x_frame_options",
    # CORS
    "access_control_allow_origin",
    # Lazy Loading
    "lazy_loading_images", "lazy_loading_iframes",
    # Fonts
    "font_files",
    # Print Styles
    "print_stylesheets",
    # Conditional Comments
    "conditional_comments"
]

# Initialize Selenium (do this once at startup)
def init_selenium():
    chrome_options = Options()
    if HEADLESS:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    
    service = Service(executable_path=r"C:\Users\HP\Downloads\chromedriver-win32\chromedriver-win32\chromedriver.exe")  # Update this path
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(SELENIUM_TIMEOUT)
    return driver

async def fetch_with_selenium(driver, url):
    try:
        driver.get(url)
        # Wait for page to load (simple wait, you could enhance this)
        time.sleep(2)
        html = driver.page_source
        if len(html) < 100 or '<html' not in html.lower():
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Prepare response headers (simulated for Selenium)
        response_headers = {
            'http_version': 'HTTP/1.1',  # Selenium doesn't expose this
            'content_encoding': '',
            'content-security-policy': '',
            'strict-transport-security': '',
            'x-frame-options': '',
            'access-control-allow-origin': ''
        }
        
        details = extract_technical_details(soup, response_headers)
        details['domain'] = extract_domain(url)
        return details
    except Exception as e:
        print(f"Selenium failed for {url}: {str(e)}")
        return None



def get_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive'
    }

def clean_value(val):
    if val is None:
        return ''
    if isinstance(val, list):
        val = ' '.join(val)
    return str(val).replace('\n', ' ')

def extract_domain(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        return domain.split(':')[0].split('/')[0].lower()
    except:
        return url.strip()

def extract_technical_details(soup, response_headers):
    details = {col: '' for col in DESIRED_COLUMNS[1:]}  # Skip domain column
    
    # HTML Document Attributes
    for item in soup.contents:
        if isinstance(item, Doctype):
            details['doctype'] = clean_value(str(item))
            break
    
    html_tag = soup.find('html')
    if html_tag:
        details['html_dir'] = clean_value(html_tag.get('dir', ''))
    
    # ARIA Attributes
    aria_attrs = {
        'aria-label': 'aria_labels',
        'aria-labelledby': 'aria_labelledby',
        'aria-describedby': 'aria_describedby',
        'aria-hidden': 'aria_hidden',
        'aria-live': 'aria_live'
    }
    for attr, col in aria_attrs.items():
        values = [clean_value(tag.get(attr, '')) for tag in soup.find_all(attrs={attr: True})]
        details[col] = ';'.join(v for v in values if v)
    
    # SVG Elements
    svgs = soup.find_all('svg')
    details['svg_ids'] = ';'.join(clean_value(svg.get('id', '')) for svg in svgs if svg.get('id'))
    details['svg_classes'] = ';'.join(clean_value(svg.get('class', '')) for svg in svgs if svg.get('class'))
    details['svg_data_attrs'] = ';'.join(
        f"{k}={clean_value(v)}" for svg in svgs 
        for k, v in svg.attrs.items() 
        if k.startswith('data-')
    )
    
    # Canvas Elements
    canvases = soup.find_all('canvas')
    details['canvas_ids'] = ';'.join(clean_value(c.get('id', '')) for c in canvases if c.get('id'))
    details['canvas_classes'] = ';'.join(clean_value(c.get('class', '')) for c in canvases if c.get('class'))
    details['canvas_data_attrs'] = ';'.join(
        f"{k}={clean_value(v)}" for c in canvases 
        for k, v in c.attrs.items() 
        if k.startswith('data-')
    )
        
    # Web Components
    wc_tags = [tag.name for tag in soup.find_all() if '-' in tag.name]
    details['web_component_tags'] = ';'.join(wc_tags)
    details['web_component_ids'] = ';'.join(
        clean_value(tag.get('id', '')) for tag in soup.find_all() 
        if '-' in tag.name and tag.get('id')
    )
    details['web_component_classes'] = ';'.join(
        clean_value(tag.get('class', '')) for tag in soup.find_all() 
        if '-' in tag.name and tag.get('class')
    )
    
    # Embedded Content
    iframes = soup.find_all('iframe')
    details['iframe_srcs'] = ';'.join(clean_value(i.get('src', '')) for i in iframes if i.get('src'))
    details['iframe_loading'] = ';'.join(clean_value(i.get('loading', '')) for i in iframes if i.get('loading'))
    details['lazy_loading_iframes'] = 'yes' if any(i.get('loading') == 'lazy' for i in iframes) else 'no'
    
    objects = soup.find_all('object')
    details['object_data'] = ';'.join(clean_value(o.get('data', '')) for o in objects if o.get('data'))
    
    embeds = soup.find_all('embed')
    details['embed_src'] = ';'.join(clean_value(e.get('src', '')) for e in embeds if e.get('src'))
    
    # PWA Features
    for script in soup.find_all('script'):
        if script.string and 'serviceWorker.register' in script.string:
            details['service_worker'] = 'yes'
            break
    
    manifest = soup.find('link', rel='manifest')
    if manifest:
        details['manifest_link'] = clean_value(manifest.get('href', ''))
    
    # Structured Data
    jsonld = [clean_value(tag.string) for tag in soup.find_all('script', type='application/ld+json') if tag.string]
    details['structured_data'] = ';'.join(jsonld)
    
    # Data Attributes
    data_attrs = set()
    for tag in soup.find_all(True):
        for attr in tag.attrs:
            if attr.startswith('data-'):
                data_attrs.add(attr)
    details['data_attributes'] = ';'.join(data_attrs)
    
    # Lazy Loading Images
    images = soup.find_all('img')
    details['lazy_loading_images'] = 'yes' if any(img.get('loading') == 'lazy' for img in images) else 'no'
    
    # Font Files
    font_exts = ('.woff', '.woff2', '.ttf', '.otf')
    fonts = [
        link['href'] for link in soup.find_all('link', rel='stylesheet') 
        if any(link.get('href', '').endswith(ext) for ext in font_exts)
    ]
    details['font_files'] = ';'.join(clean_value(f) for f in fonts)
    
    # Print Stylesheets
    print_styles = [
        link['href'] for link in soup.find_all('link', rel='stylesheet')
        if link.get('media') == 'print'
    ]
    details['print_stylesheets'] = ';'.join(clean_value(s) for s in print_styles)
    
    # Conditional Comments
    conditional_comments = [
        comment for comment in soup.find_all(string=lambda text: isinstance(text, str)) 
        if '<!--[if' in comment and ']>' in comment
    ]
    details['conditional_comments'] = ';'.join(clean_value(c) for c in conditional_comments)
    
    # HTTP/Network Info
    details['http_version'] = response_headers.get('http_version', '')
    details['compression'] = response_headers.get('content_encoding', '')
    
    # CDN Detection
    cdn_domains = {'cloudflare', 'akamai', 'fastly', 'cloudfront', 'azureedge'}
    resource_urls = [
        link.get('href', '') for link in soup.find_all(['link', 'script', 'img', 'iframe'])
    ]
    details['cdn_usage'] = 'yes' if any(
        any(cdn in url.lower() for cdn in cdn_domains)
        for url in resource_urls
    ) else 'no'
    
    # Security Headers
    details['content_security_policy'] = response_headers.get('content-security-policy', '')
    details['strict_transport_security'] = response_headers.get('strict-transport-security', '')
    details['x_frame_options'] = response_headers.get('x-frame-options', '')
    
    # CORS
    details['access_control_allow_origin'] = response_headers.get('access-control-allow-origin', '')
    
    return details

async def fetch_url(session, url, selenium_driver=None):
    domain = extract_domain(url)
    
    # First try with aiohttp (fast)
    for attempt in range(RETRIES + 1):
        try:
            async with session.get(url, timeout=TIMEOUT, headers=get_headers()) as response:
                if response.status >= 400:
                    continue
                
                content_type = response.headers.get('Content-Type', '').lower()
                if 'text/html' not in content_type:
                    continue
                
                html = await response.text(errors='ignore')
                if len(html) < 100 or '<html' not in html.lower():
                    continue
                
                soup = BeautifulSoup(html, 'html.parser')
                
                response_headers = {
                    'http_version': f"HTTP/{response.version.major}.{response.version.minor}",
                    'content_encoding': response.headers.get('Content-Encoding', ''),
                    'content-security-policy': response.headers.get('Content-Security-Policy', ''),
                    'strict-transport-security': response.headers.get('Strict-Transport-Security', ''),
                    'x-frame-options': response.headers.get('X-Frame-Options', ''),
                    'access-control-allow-origin': response.headers.get('Access-Control-Allow-Origin', '')
                }
                
                details = extract_technical_details(soup, response_headers)
                details['domain'] = domain
                return details
                
        except Exception:
            if attempt == RETRIES:
                break
            await asyncio.sleep(1 + attempt)
    
    # If aiohttp failed, try with Selenium if available
    if selenium_driver is not None:
        for attempt in range(SELENIUM_RETRIES + 1):
            try:
                details = await fetch_with_selenium(selenium_driver, url)
                if details is not None:
                    return details
            except Exception:
                if attempt == SELENIUM_RETRIES:
                    break
                time.sleep(1 + attempt)
    
    return None


async def process_batch(batch_urls):
    connector = aiohttp.TCPConnector(limit=CONCURRENT_REQUESTS)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Initialize Selenium driver once per batch
        selenium_driver = init_selenium()
        
        tasks = [fetch_url(session, url, selenium_driver) for url in batch_urls]
        results = await asyncio.gather(*tasks)
        
        successful = [r for r in results if r is not None]
        failed = [extract_domain(url) for url, result in zip(batch_urls, results) if result is None]
        
        # Clean up Selenium
        try:
            selenium_driver.quit()
        except Exception:
            pass
        
        return successful, failed

async def main(batch_start, batch_end):
    with open(INPUT_FILE) as f:
        urls = [line.strip() for line in f if line.strip()]
        urls = [url if url.startswith(('http://', 'https://')) else f'http://{url}' for url in urls]
    
    batch_urls = urls[batch_start:batch_end]
    if not batch_urls:
        print("No URLs in batch range")
        return

    start_time = time.time()
    successful, failed = await process_batch(batch_urls)
    
    # Write successful results
    if successful:
        file_exists = os.path.exists(OUTPUT_FILE) and os.path.getsize(OUTPUT_FILE) > 0
        with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=DESIRED_COLUMNS)
            if not file_exists:
                writer.writeheader()
            writer.writerows(successful)
    
    # Write failed domains
    if failed:
        file_exists = os.path.exists(FAILED_DOMAINS_FILE) and os.path.getsize(FAILED_DOMAINS_FILE) > 0
        with open(FAILED_DOMAINS_FILE, 'a') as f:
            if not file_exists:
                f.write('domain\n')
            f.write('\n'.join(failed) + '\n')
    
    elapsed = time.time() - start_time
    print(f"Processed {len(batch_urls)} domains in {elapsed:.2f}s")
    print(f"Success: {len(successful)}, Failed: {len(failed)}")

if __name__ == '__main__':
    
    try:
        asyncio.run(main(BATCH_START, BATCH_END))
    except KeyboardInterrupt:
        print("\nStopped by user")