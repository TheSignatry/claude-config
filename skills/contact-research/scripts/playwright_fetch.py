#!/usr/bin/env python3
"""Fetch a public web page or run a web search with Playwright (headless Chromium). JSON to stdout.

  python playwright_fetch.py --url https://example.com/about            # page text (truncated)
  python playwright_fetch.py --search "Paul Brown family office Iowa"    # DuckDuckGo HTML results
  python playwright_fetch.py --url ... --max-chars 8000 --timeout 20000

Exit codes / reasons (stderr JSON):
  0 ok
  4 no_browser        – Playwright installed but Chromium missing. Fix: python -m playwright install chromium
  5 not_installed     – pip install playwright --break-system-packages
  6 network_blocked   – DNS/connection refused/timeout; sandbox egress does not allow this host
  7 robots_disallow   – robots.txt disallows the path; do not fetch
  8 login_wall        – page is a sign-in page (LinkedIn etc.); use search snippets and other public sources
On any non-zero exit, the caller should fall back to the web_search / web_fetch tools and record
research.navigation = "web_tools_fallback".

Safety: never types credentials, never clicks sign-in, sends a plain UA, respects robots.txt, truncates output.
"""
import argparse, json, sys, re, urllib.parse, urllib.robotparser

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 contact_research/1.0"
LOGIN_MARKERS = ["sign in to linkedin", "join linkedin", "log in to facebook", "please log in", "sign in to continue"]


def fail(code, reason, detail=""):
    print(json.dumps({"ok": False, "reason": reason, "detail": detail[:300]}), file=sys.stderr)
    sys.exit(code)


def robots_ok(url):
    """Honor robots.txt only when it is actually served (HTTP 200). A proxy 403 or a missing file is not a disallow;
    the page fetch itself will surface a network block."""
    import urllib.request, urllib.error
    try:
        u = urllib.parse.urlparse(url)
        req = urllib.request.Request(f"{u.scheme}://{u.netloc}/robots.txt", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            if r.status != 200:
                return True
            body = r.read(200000).decode("utf-8", "ignore")
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(body.splitlines())
        return rp.can_fetch("*", url)
    except Exception:
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--search")
    ap.add_argument("--max-chars", type=int, default=6000)
    ap.add_argument("--timeout", type=int, default=20000)
    ap.add_argument("--max-results", type=int, default=8)
    a = ap.parse_args()
    if not (a.url or a.search):
        fail(2, "bad_args", "provide --url or --search")

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        fail(5, "not_installed", str(e))

    target = a.url or ("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(a.search))
    if a.url and not robots_ok(a.url):
        fail(7, "robots_disallow", a.url)

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as e:
                fail(4, "no_browser", str(e))
            ctx = browser.new_context(user_agent=UA, java_script_enabled=True)
            page = ctx.new_page()
            try:
                resp = page.goto(target, timeout=a.timeout, wait_until="domcontentloaded")
                status = resp.status if resp else None
                body_probe = (page.evaluate("() => document.body ? document.body.innerText : ''") or "")[:1500].lower()
                if status is None or status >= 400 or any(k in body_probe for k in ("x-deny-reason", "egress", "access denied", "blocked by network policy")):
                    browser.close()
                    fail(6, "network_blocked", f"status={status} body={body_probe[:120]!r}")
            except SystemExit:
                raise
            except Exception as e:
                msg = str(e)
                if any(k in msg for k in ("ERR_NAME_NOT_RESOLVED", "ERR_CONNECTION", "ERR_TUNNEL", "Timeout", "ERR_PROXY", "net::")):
                    fail(6, "network_blocked", msg)
                fail(1, "navigation_error", msg)

            if a.search:
                results = []
                for el in page.query_selector_all("a.result__a")[: a.max_results]:
                    href = el.get_attribute("href") or ""
                    if "uddg=" in href:
                        href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
                    title = el.inner_text().strip()
                    snippet = ""
                    parent = el.evaluate_handle("e => e.closest('.result')")
                    try:
                        sn = parent.as_element().query_selector(".result__snippet")
                        snippet = sn.inner_text().strip() if sn else ""
                    except Exception:
                        pass
                    results.append({"title": title, "url": href, "snippet": snippet[:400]})
                if not results and "duckduckgo" not in (page.title() or "").lower():
                    browser.close()
                    fail(6, "network_blocked", "search page did not load (no results, unexpected title)")
                print(json.dumps({"ok": True, "mode": "search", "query": a.search, "results": results}, ensure_ascii=False))
            else:
                title = page.title()
                text = page.evaluate("() => document.body ? document.body.innerText : ''")
                low = (title + " " + text[:2000]).lower()
                if any(m in low for m in LOGIN_MARKERS):
                    browser.close()
                    fail(8, "login_wall", target)
                text = re.sub(r"\n{3,}", "\n\n", text).strip()
                print(json.dumps({"ok": True, "mode": "page", "url": page.url, "title": title,
                                  "text": text[: a.max_chars], "truncated": len(text) > a.max_chars}, ensure_ascii=False))
            browser.close()
    except SystemExit:
        raise
    except Exception as e:
        fail(1, "error", str(e))


if __name__ == "__main__":
    main()
