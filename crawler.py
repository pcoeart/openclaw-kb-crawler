#!/usr/bin/env python3
"""OpenClaw 社区知识爬虫 — GitHub Actions 运行（美国 IP，无 GFW）"""
import json, os, re, time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from pathlib import Path

OUT = Path("output")
UA = "KB-Crawler/1.0 (community archive)"

def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = Request(url, headers={"User-Agent": UA})
            with urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8", errors="replace")
        except Exception as e:
            if i == retries - 1:
                return 0, str(e)
            time.sleep(2 ** i)
    return 0, "failed"

def scrape_reddit():
    d = OUT / "reddit"
    d.mkdir(parents=True, exist_ok=True)
    after, total = None, 0
    for page in range(200):
        url = "https://www.reddit.com/r/openclaw/new.json?limit=100&raw_json=1"
        if after:
            url += "&after=" + after
        status, body = fetch(url)
        if status != 200:
            break
        data = json.loads(body)
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
            url_p = "https://reddit.com" + p.get("permalink", "")
            md = "# " + title + "\n\n"
            md += "**作者**: u/" + author + " | **评分**: " + str(score) + "\n"
            md += "**时间**: " + ts + "\n**URL**: " + url_p + "\n\n"
            md += text[:10000] + "\n\n---\n"
            safe_title = title[:40].replace("/", "_").replace(":", "_")
            fname = ts[:10] + "_" + pid + "_" + safe_title + ".md"
            (d / fname).write_text(md, encoding="utf-8")
            total += 1
            if total % 20 == 0:
                print("[Reddit] " + str(total) + " posts")
        after = data.get("data", {}).get("after")
        if not after:
            break
        time.sleep(2)
    (d / "_INDEX.md").write_text("# Reddit r/openclaw\n\n" + str(total) + " posts\n" + datetime.now().isoformat() + "\n")
    print("[Reddit] DONE: " + str(total) + " posts")
    return total

def scrape_moltbook():
    d = OUT / "moltbook"
    d.mkdir(parents=True, exist_ok=True)
    communities = ["openclaw-explorers","bughunter","ponderings","bestpractices","skill-showcase","builds","general"]
    search_terms = ["openclaw","skill","memory","configuration","security","workflow"]
    urls = []
    for c in communities:
        urls.append("https://www.moltbook.com/m/" + c)
    for t in search_terms:
        urls.append("https://www.moltbook.com/search?q=" + t)
    post_ids = set()
    for url in urls:
        status, body = fetch(url)
        if status == 200:
            pattern = r'/post/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
            for pid in set(re.findall(pattern, body)):
                post_ids.add(pid)
        time.sleep(0.5)
    print("[Moltbook] Found " + str(len(post_ids)) + " unique posts")
    total = 0
    for pid in sorted(post_ids):
        url = "https://www.moltbook.com/post/" + pid
        status, body = fetch(url)
        if status != 200:
            continue
        body_clean = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL)
        body_clean = re.sub(r'<style[^>]*>.*?</style>', '', body_clean, flags=re.DOTALL)
        body_clean = re.sub(r'<[^>]+>', '\n', body_clean)
        body_clean = re.sub(r'\n{3,}', '\n\n', body_clean).strip()
        title_m = re.search(r'<title[^>]*>(.*?)</title>', body_clean, re.I)
        title = title_m.group(1).strip()[:100] if title_m else pid[:8]
        md = "# " + title + "\n\n"
        md += "**URL**: " + url + "\n"
        md += "**抓取**: " + datetime.now().isoformat() + "\n\n"
        md += body_clean[:8000] + "\n\n---\n"
        (d / (pid[:8] + ".md")).write_text(md, encoding="utf-8")
        total += 1
        if total % 10 == 0:
            print("[Moltbook] " + str(total) + "/" + str(len(post_ids)))
        time.sleep(0.5)
    (d / "_INDEX.md").write_text("# Moltbook\n\n" + str(total) + " posts\n" + datetime.now().isoformat() + "\n")
    print("[Moltbook] DONE: " + str(total) + " posts")
    return total

if __name__ == "__main__":
    t0 = time.time()
    r1 = scrape_reddit()
    r2 = scrape_moltbook()
    elapsed = time.time() - t0
    summary = "# 抓取报告\n\n**时间**: " + datetime.now().isoformat() + "\n**耗时**: " + str(int(elapsed)) + "s\n\n| 来源 | 条数 |\n|:---|---:|\n| Reddit | " + str(r1) + " |\n| Moltbook | " + str(r2) + " |\n"
    (OUT / "_SUMMARY.md").write_text(summary)
    print("\nAll done. Reddit=" + str(r1) + ", Moltbook=" + str(r2))
