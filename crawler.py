#!/usr/bin/env python3
"""OpenClaw 社区知识爬虫 — GitHub Actions 运行"""
import json, os, re, time
from datetime import datetime, timezone
from urllib.request import Request, urlopen, build_opener, install_opener
from urllib.error import HTTPError
from pathlib import Path

OUT = Path("output")
# 模拟真实浏览器 UA，防止被反爬
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

def fetch(url, retries=3, extra_headers=None):
    h = {"User-Agent": UA, "Accept": "text/html,application/json,*/*"}
    if extra_headers:
        h.update(extra_headers)
    for i in range(retries):
        try:
            req = Request(url, headers=h)
            with urlopen(req, timeout=25) as r:
                return r.status, r.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  fetch retry {i+1}: {e}")
            if i == retries - 1:
                return 0, str(e)
            time.sleep(3)
    return 0, "failed"

def scrape_reddit():
    d = OUT / "reddit"
    d.mkdir(parents=True, exist_ok=True)
    after, total = None, 0
    for page in range(100):
        url = "https://old.reddit.com/r/openclaw/new.json?limit=100&raw_json=1"
        if after:
            url += "&after=" + after
        status, body = fetch(url, extra_headers={"Accept": "application/json"})
        if status != 200:
            print(f"[Reddit] page {page}: HTTP {status}")
            break
        try:
            data = json.loads(body)
        except:
            print(f"[Reddit] page {page}: JSON parse error")
            break
        children = data.get("data", {}).get("children", [])
        if not children:
            break
        for child in children:
            p = child["data"]
            pid = p.get("id", "unknown")
            title = p.get("title", "")[:100]
            text = p.get("selftext", "") or ""
            author = p.get("author", "[deleted]")
            ts = datetime.fromtimestamp(p.get("created_utc", 0), tz=timezone.utc).isoformat()
            score = p.get("score", 0)
            num_comments = p.get("num_comments", 0)
            permalink = p.get("permalink", "")
            url_p = "https://old.reddit.com" + permalink

            # 取评论
            comments_text = ""
            time.sleep(0.3)
            cstatus, cbody = fetch(url_p + ".json", extra_headers={"Accept": "application/json"})
            if cstatus == 200:
                try:
                    cdata = json.loads(cbody)
                    comments_list = cdata[1]["data"]["children"] if len(cdata) > 1 else []
                    for c in comments_list[:10]:
                        if c["kind"] == "t1":
                            cbody_text = c["data"].get("body", "")
                            cauthor = c["data"].get("author", "[deleted]")
                            cscore = c["data"].get("score", 0)
                            comments_text += f"\n> **u/{cauthor}** ({cscore}): {cbody_text[:500]}\n"
                except:
                    pass

            md = f"# {title}\n\n"
            md += f"**作者**: u/{author} | **评分**: {score} | **评论**: {num_comments}\n"
            md += f"**时间**: {ts}\n**URL**: {url_p}\n\n"
            md += text[:10000] + "\n\n"
            if comments_text:
                md += f"## 热门评论\n{comments_text}\n"
            md += "---\n"

            safe_title = title[:40].replace("/", "_").replace(":", "_").replace("?", "").replace('"', "")
            fname = f"{ts[:10]}_{pid}_{safe_title}.md"
            try:
                (d / fname).write_text(md, encoding="utf-8")
            except:
                (d / f"{pid}.md").write_text(md, encoding="utf-8")
            total += 1
            if total % 10 == 0:
                print(f"[Reddit] {total} posts")

        after = data.get("data", {}).get("after")
        if not after:
            break
        time.sleep(2)

    (d / "_INDEX.md").write_text(f"# Reddit r/openclaw\n\n{total} posts\n{datetime.now().isoformat()}\n")
    print(f"[Reddit] DONE: {total} posts")
    return total

def scrape_moltbook():
    d = OUT / "moltbook"
    d.mkdir(parents=True, exist_ok=True)
    communities = ["openclaw-explorers", "bughunter", "ponderings", "bestpractices", "skill-showcase", "builds", "general"]
    search_terms = ["openclaw", "skill", "memory", "configuration", "security"]
    urls = [f"https://www.moltbook.com/m/{c}" for c in communities]
    urls += [f"https://www.moltbook.com/search?q={t}" for t in search_terms]

    post_ids = set()
    for url in urls:
        status, body = fetch(url)
        if status == 200:
            pattern = r'/post/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
            found = set(re.findall(pattern, body))
            post_ids.update(found)
            print(f"  {url.split('/')[-1]}: found {len(found)} posts")
        else:
            print(f"  {url}: HTTP {status}")
        time.sleep(0.5)

    print(f"[Moltbook] Total unique posts: {len(post_ids)}")
    total = 0
    for pid in sorted(post_ids):
        url = f"https://www.moltbook.com/post/{pid}"
        status, body = fetch(url)
        if status != 200:
            continue
        # 提取纯文本
        body_clean = body
        body_clean = re.sub(r'<script[^>]*>.*?</script>', '', body_clean, flags=re.DOTALL | re.IGNORECASE)
        body_clean = re.sub(r'<style[^>]*>.*?</style>', '', body_clean, flags=re.DOTALL | re.IGNORECASE)
        body_clean = re.sub(r'<[^>]+>', '\n', body_clean)
        body_clean = re.sub(r'&[a-z]+;', ' ', body_clean)  # HTML entities
        body_clean = re.sub(r'\n{3,}', '\n\n', body_clean).strip()
        title_m = re.search(r'<title[^>]*>(.*?)</title>', body, re.IGNORECASE)
        title = title_m.group(1).strip()[:100] if title_m else pid[:8]
        md = f"# {title}\n\n**URL**: {url}\n**抓取**: {datetime.now().isoformat()}\n\n{body_clean[:8000]}\n\n---\n"
        (d / f"{pid[:12]}.md").write_text(md, encoding="utf-8")
        total += 1
        if total % 5 == 0:
            print(f"[Moltbook] {total}/{len(post_ids)}")
        time.sleep(0.4)

    (d / "_INDEX.md").write_text(f"# Moltbook\n\n{total} posts\n{datetime.now().isoformat()}\n")
    print(f"[Moltbook] DONE: {total} posts")
    return total

if __name__ == "__main__":
    t0 = time.time()
    r1 = scrape_reddit()
    r2 = scrape_moltbook()
    elapsed = time.time() - t0
    summary = f"# 抓取报告\n\n**时间**: {datetime.now().isoformat()}\n**耗时**: {elapsed:.0f}s\n\n| 来源 | 条数 |\n|:---|---:|\n| Reddit | {r1} |\n| Moltbook | {r2} |\n"
    (OUT / "_SUMMARY.md").write_text(summary)
    print(f"\nDONE in {elapsed:.0f}s. Reddit={r1}, Moltbook={r2}")
