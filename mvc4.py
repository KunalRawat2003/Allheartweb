import asyncio
import csv
from aiohttp import ClientSession, ClientTimeout
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import re

# --- Settings ---
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive"}

TIMEOUT = ClientTimeout(total=60)
CONCURRENCY = 10
batch_start = 0
batch_end = 200

FRAMEWORK_HINTS = {
    "headers": {
        "x-aspnetmvc-version": "ASP.NET MVC",
        "x-aspnet-version": "ASP.NET",
        "x-powered-by": {
            "laravel": "Laravel",
            "php": "PHP (Laravel/Symfony/Zend/CakePHP)",
            "express": "Express.js",
            "next.js": "Next.js",
            "nestjs": "NestJS",
            "django": "Django",
            "rails": "Ruby on Rails",
            "spring": "Spring MVC",
            "sails": "Sails.js",
            "koa": "Koa.js",
            "hapi": "Hapi.js",
            "hostingerwebsitebuilder": "Zyro",
            "adonis": "AdonisJS",
            "meteor": "Meteor",
            "fastapi": "FastAPI",
            "flask": "Flask",
            "symfony": "Symfony",
            "cakephp": "CakePHP",
            "codeigniter": "CodeIgniter",
            "fuelphp": "FuelPHP",
            "falcon": "Falcon",
            "web2py": "Web2py",
            "play": "Play Framework",
            "phoenix": "Phoenix",
            "rails-api": "Rails API",
            "hanami": "Hanami",
            "sinatra": "Sinatra",
            "pyramid": "Pyramid",
            "grails": "Grails",
            "nancy": "NancyFX",
            "dotnetnuke": "DotNetNuke",
            "vaadin": "Vaadin",
            "revel": "Revel",
            "buffalo": "Buffalo",
            "beego": "Beego",
            "ktor": "Ktor",
            "actix-web": "Actix",
            "rocket": "Rocket",
            "mojolicious": "Mojolicious",
            "catalyst": "Catalyst",
            "fastify": "Fastify",  # Added Fastify
            "micronaut": "Micronaut",  # Added Micronaut
            "quarkus": "Quarkus"  # Added Quarkus
        },
        "x-runtime": "Ruby on Rails",
        "x-rack-cache": "Ruby on Rails",
        "platform": {
            "hostinger": "Zyro"
        },
        "content-security-policy": {
            "zyro.com": "Zyro",
            "zyrosite.com": "Zyro"
        },
        "x-fastify": "Fastify",  # Added Fastify header
        "x-micronaut": "Micronaut"  # Added Micronaut header
    },
    "cookies": {
        "laravel_session": "Laravel",
        "csrftoken": "Django",
        "sessionid": "Django",
        "_session_id": "Ruby on Rails",
        "_myapp_session": "Ruby on Rails",
        "asp.net_sessionid": "ASP.NET MVC",
        ".aspxauth": "ASP.NET",
        "play_session": "Play Framework",
        "ci_session": "CodeIgniter",
        "symfony": "Symfony",
        "adonis_session": "AdonisJS",
        "fuelcid": "FuelPHP",
        "web2py_session": "Web2py",
        "grails_session": "Grails",
        "dotnetnuke_session": "DotNetNuke",
        "vaadin_session": "Vaadin",
        "micronaut_session": "Micronaut"  # Added Micronaut cookie
    },
    "scripts": {
        "rails-ujs": "Ruby on Rails",
        "angular(\\.min)?(\\.\\d+)?\\.js$": "AngularJS",
        "vue(\\.min)?(\\.\\d+)?\\.js$": "Vue.js",
        "react(\\.min)?(\\.\\d+)?\\.js$": "React",
        "next(\\.min)?(\\.\\d+)?\\.js$": "Next.js",
        "nuxt(\\.min)?(\\.\\d+)?\\.js$": "Nuxt.js",
        "svelte(\\.min)?(\\.\\d+)?\\.js$": "Svelte",
        "ember(\\.min)?(\\.\\d+)?\\.js$": "Ember.js",
        "backbone(\\.min)?(\\.\\d+)?\\.js$": "Backbone.js",
        "knockout(\\.min)?(\\.\\d+)?\\.js$": "Knockout.js",
        "blazor(\\.web|\\.server)?(\\.\\d+)?\\.js$": "Blazor",  # Added Blazor
        "gatsby(\\.min)?(\\.\\d+)?\\.js$": "Gatsby"  # Added Gatsby
    },
    "html": {
        "ng-app": "AngularJS",
        "ng-version": "AngularJS",
        "data-turbolinks": "Ruby on Rails",
        "v-bind": "Vue.js",
        "__react_devtools": "React",
        "data-svelte": "Svelte",
        "data-controller": "Stimulus",
        "x-data": "Alpine.js",
        "data-gatsby": "Gatsby",  # Added Gatsby
        "blazor-id": "Blazor"  # Added Blazor
    },
    "paths": {
        "/packs/": "Ruby on Rails",
        "/content/": "ASP.NET",
        "/bundles/": "Spring MVC",
        "/build/": "Next.js/Nuxt.js",
        "/scripts/WebForms.js": "ASP.NET",
        "/scripts/WebResource.axd": "ASP.NET",
        "/js/ember.js": "Ember.js",
        "/js/backbone.js": "Backbone.js",
        "/js/angular.js": "AngularJS",
        "/js/vue.js": "Vue.js",
        "/js/react.js": "React",
        "/js/svelte.js": "Svelte",
        "/js/knockout.js": "Knockout.js",
        "/api/v1/": "FastAPI/NestJS",  # Added API path
        "/graphql/": "FastAPI/NestJS",  # Added GraphQL path
        "/q/health": "Micronaut/Quarkus",  # Added Micronaut/Quarkus health endpoint
        "/.php": "Laravel/Symfony/CodeIgniter",  # Added PHP extension
        "/.aspx": "ASP.NET",  # Added ASPX extension
        "/.erb": "Ruby on Rails"  # Added ERB extension
    },
    "error_snippets": {
        "django.http.http404": "Django",
        "django.urls.exceptions": "Django",
        "actioncontroller::routingerror": "Ruby on Rails",
        "activerecord::": "Ruby on Rails",
        "laravel\\\\framework": "Laravel",
        "illuminate\\\\": "Laravel",
        "org.springframework.web": "Spring MVC",
        "play.exceptions": "Play Framework",
        "cake\\\\controller": "CakePHP",
        "symfony\\\\component": "Symfony",
        "express.static": "Express.js",
        "adonisjs\\\\framework": "AdonisJS",
        "fastapi.exceptions": "FastAPI",
        "flask.wrappers": "Flask",
        "web2py.gluon": "Web2py",
        "fuel\\\\core": "FuelPHP",
        "pyramid.httpexceptions": "Pyramid",
        "phoenix.controller": "Phoenix",
        "org.codehaus.groovy": "Grails",
        "revel.revel": "Revel",
        "beego.context": "Beego",
        "io.ktor": "Ktor",
        "actix_web::error": "Actix",
        "rocket::error": "Rocket",
        "mojolicious::controller": "Mojolicious",
        "catalyst::exception": "Catalyst",
        "yii\\\\base\\\\errorhandler": "Yii",
        "fastify": "Fastify",  # Added Fastify
        "micronaut": "Micronaut",  # Added Micronaut
        "quarkus": "Quarkus"  # Added Quarkus
    },
    "meta": {
        "generator": {
            "gatsby": "Gatsby",
            "hugo": "Hugo",
            "jekyll": "Jekyll"
        }
    }
}

# --- Refined WEAK_PATH_DEPENDENCIES ---
WEAK_PATH_DEPENDENCIES = {
    "Ruby on Rails": ["/packs/", "actioncontroller", "rails-ujs", "_session_id", "x-runtime", "/.erb"],
    "Laravel": ["/storage/", "illuminate", "laravel_session", "mix-manifest", "/.php"],
    "ASP.NET": ["/content/", ".aspxauth", "asp.net_sessionid", "/scripts/WebForms.js", "/.aspx"],
    "Django": ["/media/", "django.http", "csrftoken"],
    "Spring MVC": ["/bundles/", "springframework"],
    "Symfony": ["/_profiler/", "symfony\\component", "/.php"],
    "Ember.js": ["/js/ember.js", "ember.debug.js"],
    "Backbone.js": ["/js/backbone.js", "backbone.min.js"],
    "AngularJS": ["/js/angular.js", "angular.module", "ng-app"],
    "Vue.js": ["/js/vue.js", "new Vue", "data-v-"],
    "React": ["/js/react.js", "react.createelement", "__react_devtools"],
    "Svelte": ["/js/svelte.js", "data-svelte"],
    "Knockout.js": ["/js/knockout.js", "ko.observable"],
    "Next.js": ["/_next/", "next.min.js"],
    "Nuxt.js": ["/_nuxt/", "id=\"__nuxt\""],
    "Express.js": ["express.static", "express-session"],
    "AdonisJS": ["adonis_session", "adonisjs\\framework"],
    "Flask": ["flask.wrappers", "__flask__"],
    "FastAPI": ["/docs", "/openapi.json", "fastapi.exceptions"],
    "Phoenix": ["/js/phoenix.js", "phoenix.controller"],
    "Play Framework": ["play.exceptions", "play_session"],
    "CodeIgniter": ["/index.php/", "ci_session", "/.php"],
    "CakePHP": ["/cake/", "cake\\controller", "/.php"],
    "Meteor": ["/meteor.js", "__meteor_runtime_config__"],
    "FuelPHP": ["/fuelphp/", "fuelcid", "/.php"],
    "Web2py": ["/web2py/", "web2py_session"],
    "Vaadin": ["/vaadinServlet", "vaadin_session"],
    "Grails": ["grails_session", "org.codehaus.groovy"],
    "Pyramid": ["pyramid.httpexceptions"],
    "Beego": ["beego.context"],
    "Rocket": ["rocket::error"],
    "Actix": ["actix_web::error"],
    "Mojolicious": ["mojolicious::controller"],
    "Catalyst": ["catalyst::exception"],
    "Hanami": ["/assets/hanami.js"],
    "Sinatra": ["/sinatra/", "rack.errors"],
    "Stimulus": ["data-controller"],
    "Alpine.js": ["x-data"],
    "NestJS": ["nestjs", "/api/v1/"],
    "Fastify": ["fastify", "/api/v1/"],  # Added Fastify
    "Micronaut": ["/q/health", "micronaut"],  # Added Micronaut
    "Quarkus": ["/q/health", "quarkus"],  # Added Quarkus
    "Blazor": ["blazor.web.js", "blazor.server.js"],  # Added Blazor
    "Gatsby": ["data-gatsby", "gatsby.min.js"]  # Added Gatsby
}

COMMON_PATHS = ["/login", "/admin", "/dashboard", "/user"]

failed_domains = []

def extract_snippet(tag: str, html: str, max_len: int = 150) -> str:
    for line in html.splitlines():
        if tag in line:
            return line.strip()[:max_len]
    return ""

async def detect_with_playwright(url):
    frameworks = {}
    signals = {}
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            # Capture network responses
            async def handle_response(response):
                headers = {k.lower(): v.lower() for k, v in response.headers.items()}
                for key, fw in FRAMEWORK_HINTS.get("headers", {}).items():
                    if key in headers:
                        if isinstance(fw, dict):
                            for hint, name in fw.items():
                                if hint in headers[key]:
                                    signals.setdefault(name, []).append(f"playwright:header:{key},line:{headers[key]}")
                        else:
                            signals.setdefault(fw, []).append(f"playwright:header:{key}")
            
            page.on("response", handle_response)
            
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            content = await page.content()
            body = content.lower()
            scripts = await page.query_selector_all('script')

            # DOM-based detection
            for tag, fw in [
                ("data-reactroot", "React"),
                ("__react_devtools", "React"),
                ("data-v-", "Vue.js"),
                ("vue-component", "Vue.js"),
                ("ng-app", "AngularJS"),
                ("ng-version", "AngularJS"),
                ("data-svelte", "Svelte"),
                ("id=\"__nuxt\"", "Nuxt.js"),
                ("data-gatsby", "Gatsby"),  # Added Gatsby
                ("blazor-id", "Blazor")  # Added Blazor
            ]:
                if tag in body:
                    signals.setdefault(fw, []).append(f"playwright:dom,line:{extract_snippet(tag, content)}")

            # Script-based検出
            for s in scripts:
                src = await s.get_attribute("src") or ""
                src = src.lower()
                text = (await s.inner_text() or "").lower()

                if any(x in src for x in ["google", "gstatic", "googletagmanager", "doubleclick", "akamai", "fonts"]):
                    continue
                if src.startswith("data:") or "base64" in src:
                    continue

                for key, fw in [
                    ("react", "React"),
                    ("vue", "Vue.js"),
                    ("angular", "AngularJS"),
                    ("svelte", "Svelte"),
                    ("next", "Next.js"),
                    ("nuxt", "Nuxt.js"),
                    ("blazor", "Blazor"),  # Added Blazor
                    ("gatsby", "Gatsby"),  # Added Gatsby
                    ("phoenix", "Phoenix"),
                    ("rails-ujs", "Ruby on Rails")
                ]:
                    if re.search(rf"\\b{key}[\\./-]", src) or re.search(rf"\\b{key}[\\(\s]", text):
                        signals.setdefault(fw, []).append(f"playwright:script,line:{(src or text)[:80]}")

            # Console log detection
            async def handle_console(msg):
                text = msg.text.lower()
                for fw, hints in WEAK_PATH_DEPENDENCIES.items():
                    for hint in hints:
                        if hint in text:
                            signals.setdefault(fw, []).append(f"playwright:console,line:{text[:80]}")

            page.on("console", handle_console)
            await page.evaluate("console.log('Checking for framework errors')")

            for fw, s_list in signals.items():
                if len(s_list) >= 1:
                    frameworks[fw] = ";".join(s_list)

            await browser.close()
    except Exception as e:
        failed_domains.append((url, f"Playwright error: {repr(e)}"))
    return frameworks

# --- Updated fetch() Function ---
async def fetch(session: ClientSession, domain: str) -> tuple:
    fw_signals = {}
    base_urls = [f"https://{domain}", f"http://{domain}"] if not domain.startswith("http") else [domain]

    for url in base_urls:
        try:
            async with session.get(url, headers=HEADERS) as res:
                text = await res.text()
                headers = {k.lower(): v.lower() for k, v in res.headers.items()}

                # Header detection
                for key, fw in FRAMEWORK_HINTS.get("headers", {}).items():
                    if key in headers:
                        if isinstance(fw, dict):
                            for hint, name in fw.items():
                                if hint in headers[key]:
                                    fw_signals.setdefault(name, []).append(f"header:{key},line:{headers[key]}")
                        else:
                            fw_signals.setdefault(fw, []).append(f"header:{key}")

                # Cookie detection
                for cookie in res.cookies.values():
                    try:
                        ck = cookie.key.lower()
                        for name, fw in FRAMEWORK_HINTS.get("cookies", {}).items():
                            if name in ck:
                                fw_signals.setdefault(fw, []).append(f"cookie:{name},line:{cookie.key}={cookie.value}")
                    except AttributeError:
                        continue

                soup = BeautifulSoup(text, "html.parser")
                body = text.lower()

                # Meta tag detection
                for meta in soup.find_all("meta"):
                    if meta.get("name") == "generator":
                        content = meta.get("content", "").lower()
                        for key, fw in FRAMEWORK_HINTS.get("meta", {}).get("generator", {}).items():
                            if key in content:
                                fw_signals.setdefault(fw, []).append(f"meta:generator,line:{content}")

                # HTML hints
                for tag, fw in FRAMEWORK_HINTS.get("html", {}).items():
                    if tag in body:
                        fw_signals.setdefault(fw, []).append(f"html:{tag},line:{extract_snippet(tag, text)}")

                # Script tags
                for script in soup.find_all("script"):
                    src = script.get("src", "").lower()
                    script_text = script.string or ""
                    if src:
                        for pattern, fw in FRAMEWORK_HINTS.get("scripts", {}).items():
                            if re.search(pattern, src):
                                fw_signals.setdefault(fw, []).append(f"script:{pattern},line:{src}")
                    else:
                        lowered = script_text.lower()
                        if "react.createelement" in lowered:
                            fw_signals.setdefault("React", []).append(f"script:inline,line:{script_text.strip()[:80]}")
                        elif "new vue" in lowered or "vue(" in lowered:
                            fw_signals.setdefault("Vue.js", []).append(f"script:inline,line:{script_text.strip()[:80]}")
                        elif "angular.module" in lowered:
                            fw_signals.setdefault("Angular", []).append(f"script:inline,line:{script_text.strip()[:80]}")

                # Path hints
                for tag in soup.find_all(["script", "link", "img"]):
                    for attr in ["src", "href"]:
                        val = tag.get(attr, "")
                        if val:
                            for path, fw in FRAMEWORK_HINTS.get("paths", {}).items():
                                if path in val:
                                    fw_signals.setdefault(fw, []).append(f"path:{path},line:{val}")

                # Weak paths (if path OR matching weak hints in body)
                for path, fw in FRAMEWORK_HINTS.get("paths", {}).items():
                    if path in body:
                        hints = WEAK_PATH_DEPENDENCIES.get(fw, [])
                        if not hints or any(h in body for h in hints):
                            fw_signals.setdefault(fw, []).append(f"weak-path:{path},line:{extract_snippet(path, text)}")

                # Error page detection
                try:
                    async with session.get(url + "/__nonexistent__", headers=HEADERS) as err_res:
                        err_text = await err_res.text()
                        for snippet, fw in FRAMEWORK_HINTS.get("error_snippets", {}).items():
                            if snippet in err_text.lower():
                                fw_signals.setdefault(fw, []).append(f"error:{snippet}")
                except:
                    pass

                # Try common paths
                for path in COMMON_PATHS:
                    try:
                        async with session.get(url + path, headers=HEADERS) as r:
                            if r.status == 200:
                                extra_body = await r.text()
                                for tag, fw in FRAMEWORK_HINTS.get("html", {}).items():
                                    if tag in extra_body:
                                        fw_signals.setdefault(fw, []).append(f"html:{tag},line:{extract_snippet(tag, extra_body)}")
                    except:
                        continue

                # Always run Playwright
                extra = await detect_with_playwright(url)
                for fw, val in extra.items():
                    fw_signals.setdefault(fw, []).append(val)

                strong_frameworks = {}
                medium_frameworks = {}
                weak_frameworks = {}

                for fw, signals in fw_signals.items():
                    if any(s.startswith("header") or s.startswith("cookie") or s.startswith("error") or "playwright" in s for s in signals):
                        strong_frameworks[fw] = "high:" + ";".join(signals)
                    elif any(s.startswith("html") or s.startswith("script") or s.startswith("meta") for s in signals):
                        medium_frameworks[fw] = "medium:" + ";".join(signals)
                    elif any(s.startswith("weak-path") or s.startswith("path") for s in signals):
                        weak_frameworks[fw] = "low:" + ";".join(signals)

                # Prioritize strongest available detection
                if strong_frameworks:
                    final_frameworks = strong_frameworks
                    status = "Framework confidently detected"
                elif medium_frameworks:
                    final_frameworks = medium_frameworks
                    status = "Framework moderately detected"
                elif weak_frameworks:
                    final_frameworks = weak_frameworks
                    status = "Framework weakly inferred from paths"
                else:
                    final_frameworks = {}
                    status = "No framework confidently detected"

                # Set status
                if final_frameworks:
                    status = "Framework detected"
                else:
                    status = "No framework detected"

                frameworks_str = ";".join(final_frameworks.keys())
                sources_str = ";".join(final_frameworks.values())
                return domain, frameworks_str, sources_str, status

        except Exception as e:
            failed_domains.append((domain, f"Fetch Error: {repr(e)}"))
            return domain, "", "", "Fetch Error"

    failed_domains.append((domain, f"All URL variants failed"))
    return domain, "", "", "Fetch Error"

async def run_detection(domains):
    sem = asyncio.Semaphore(CONCURRENCY)
    async with ClientSession(timeout=TIMEOUT) as session:
        async def bounded(domain):
            async with sem:
                print(f"Checking: {domain}")
                return await fetch(session, domain)
        tasks = [bounded(domain) for domain in domains]
        return await asyncio.gather(*tasks)

def load_domains(filename):
    with open(filename, "r", encoding= "utf-8") as f:
        return [line.strip() for line in f if line.strip()][batch_start:batch_end]
    
def save_to_csv(results, filename="mvc_frameworks7.csv"):
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Domain", "Frameworks", "Sources"])
        for domain, frameworks, sources, status in results:
            if "Fetch Error" in status:
                continue  # Don't store fetch errors in CSV
            writer.writerow([domain, frameworks or "", sources or ""])

def save_failed(filename="failed.txt"):
    if failed_domains:
        seen = set()
        with open(filename, "a") as f:
            for domain, reason in failed_domains:
                if domain not in seen:
                    f.write(f"{domain},{reason}\n")
                    seen.add(domain)

if __name__ == "__main__":
    domains = load_domains("newdomains.txt")
    results = asyncio.run(run_detection(domains))
    save_to_csv(results)
    save_failed()
    print("\n✅ Results saved to mvc_frameworks4.csv")
    if failed_domains:
        print(f"❌ {len(failed_domains)} domains failed. Saved to failed.txt.")
