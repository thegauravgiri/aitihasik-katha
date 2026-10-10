"""Pull performance insights for every Instagram reel and build a report.

    python scripts/instagram_insights.py               # all reels
    python scripts/instagram_insights.py --limit 20    # newest 20
    python scripts/instagram_insights.py --since 2026-09-01

Writes reports/instagram/<date>/insights.json, insights.csv and report.html.

The Graph API does not expose Instagram's per-second retention curve. The report plots
the points it does expose: everyone at 0s, the share still watching after the first 3s
(from reels_skip_rate) and the average watch position (from ig_reels_avg_watch_time and
the reel's length).
"""
import argparse
import csv
import html
import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import imageio_ffmpeg
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aitihasik_katha.core.settings import settings  # noqa: E402

BASE_URL = "https://graph.facebook.com/v25.0"
METRICS = [
    "views", "reach", "likes", "comments", "shares", "saved", "reposts", "total_interactions",
    "ig_reels_avg_watch_time", "ig_reels_video_view_total_time", "reels_skip_rate",
]
MEDIA_FIELDS = "id,caption,timestamp,permalink,media_type,media_product_type,media_url,thumbnail_url"
DURATION_CACHE = ROOT / "reports" / "instagram" / "durations.json"


def _get(url: str, params: dict, attempts: int = 4) -> dict:
    """GET a Graph API URL. Network errors are retried and re-raised without the request URL,
    because that URL contains the access token."""
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, params={**params, "access_token": settings.INSTAGRAM_PAGE_ACCESS_TOKEN}, timeout=30)
            break
        except requests.RequestException as exc:
            if attempt == attempts:
                raise RuntimeError(f"Could not reach the Instagram API ({type(exc).__name__}) after {attempts} tries") from None
            time.sleep(3 * attempt)
    data = response.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", "Graph API error"))
    return data


def fetch_media(limit: int | None, since: str | None) -> list[dict]:
    settings.require("INSTAGRAM_USER_ID", "INSTAGRAM_PAGE_ACCESS_TOKEN")
    url, params, media = f"{BASE_URL}/{settings.INSTAGRAM_USER_ID}/media", {"fields": MEDIA_FIELDS, "limit": 50}, []
    while url:
        page = _get(url, params)
        for item in page.get("data", []):
            if since and item["timestamp"][:10] < since:
                return media
            media.append(item)
            if limit and len(media) >= limit:
                return media
        url, params = page.get("paging", {}).get("next"), {}
    return media


def fetch_insights(media_id: str) -> dict:
    """All metrics in one call; if the media type rejects one, fetch them one by one."""
    def _values(data: dict) -> dict:
        return {d["name"]: (d.get("values") or [{}])[0].get("value") for d in data.get("data", [])}

    try:
        return _values(_get(f"{BASE_URL}/{media_id}/insights", {"metric": ",".join(METRICS)}))
    except RuntimeError:
        values = {}
        for metric in METRICS:
            try:
                values.update(_values(_get(f"{BASE_URL}/{media_id}/insights", {"metric": metric})))
            except RuntimeError:
                values[metric] = None
        return values


def video_seconds(media: dict, cache: dict) -> float | None:
    """Reel length, read from the video header with the ffmpeg bundled with MoviePy."""
    if media["id"] in cache:
        return cache[media["id"]]
    if not media.get("media_url"):
        return None
    probe = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", media["media_url"]],
                           capture_output=True, text=True, timeout=120)
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe.stderr)
    seconds = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3]) if match else None
    cache[media["id"]] = seconds
    return seconds


def build_rows(media: list[dict]) -> list[dict]:
    cache = json.loads(DURATION_CACHE.read_text()) if DURATION_CACHE.exists() else {}
    rows = []
    for i, item in enumerate(media, 1):
        print(f"[{i}/{len(media)}] {item['permalink']}", file=sys.stderr)
        metrics = fetch_insights(item["id"])
        length = video_seconds(item, cache)
        avg_watch = (metrics.get("ig_reels_avg_watch_time") or 0) / 1000
        skip = metrics.get("reels_skip_rate")
        views = metrics.get("views") or 0
        rows.append({
            "date": item["timestamp"][:10],
            "permalink": item["permalink"],
            "hook": (item.get("caption") or "").split("\n")[0].strip(),
            "length_s": round(length, 1) if length else None,
            **{k: metrics.get(k) for k in METRICS},
            "avg_watch_s": round(avg_watch, 1),
            "watched_past_3s_pct": round(100 - skip, 1) if skip is not None else None,
            "avg_watch_pct_of_length": round(100 * avg_watch / length, 1) if length else None,
            "like_rate_pct": round(100 * (metrics.get("likes") or 0) / views, 2) if views else None,
            "share_rate_pct": round(100 * (metrics.get("shares") or 0) / views, 2) if views else None,
        })
    DURATION_CACHE.parent.mkdir(parents=True, exist_ok=True)
    DURATION_CACHE.write_text(json.dumps(cache, indent=1))
    return rows


# ---------- report ----------

def _bar_chart(rows: list[dict]) -> str:
    """Views per reel, oldest to newest."""
    data = sorted(rows, key=lambda r: r["date"])
    w, h, pad = 900, 260, 40
    top = max((r["views"] or 0) for r in data) or 1
    bw = (w - 2 * pad) / len(data)
    bars = []
    for i, r in enumerate(data):
        v = r["views"] or 0
        bh = (h - 2 * pad) * v / top
        x, y = pad + i * bw + 2, h - pad - bh
        bars.append(f'<a href="{html.escape(r["permalink"])}"><rect x="{x:.1f}" y="{y:.1f}" width="{bw - 4:.1f}" '
                    f'height="{bh:.1f}" class="bar"><title>{html.escape(r["date"])}: {v:,} views\n'
                    f'{html.escape(r["hook"][:90])}</title></rect></a>')
    labels = f'<text x="{pad}" y="{h - 12}" class="ax">{data[0]["date"]}</text>' \
             f'<text x="{w - pad}" y="{h - 12}" class="ax" text-anchor="end">{data[-1]["date"]}</text>' \
             f'<text x="{pad}" y="{pad - 10}" class="ax">{top:,} views</text>'
    return f'<svg viewBox="0 0 {w} {h}" class="chart">{"".join(bars)}{labels}' \
           f'<line x1="{pad}" y1="{h - pad}" x2="{w - pad}" y2="{h - pad}" class="axis"/></svg>'


def _retention_chart(r: dict) -> str:
    """The retention points the API exposes: 100% at 0s, % past 3s, and the average watch position."""
    w, h, pad = 320, 150, 28
    length = r["length_s"] or max(r["avg_watch_s"] * 2, 10)
    sx = lambda s: pad + (w - 2 * pad) * min(s, length) / length  # noqa: E731
    sy = lambda p: h - pad - (h - 2 * pad) * p / 100  # noqa: E731
    past3 = r["watched_past_3s_pct"]
    parts = [f'<line x1="{pad}" y1="{h - pad}" x2="{w - pad}" y2="{h - pad}" class="axis"/>',
             f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h - pad}" class="axis"/>',
             f'<text x="{pad}" y="{h - 10}" class="ax">0s</text>',
             f'<text x="{w - pad}" y="{h - 10}" class="ax" text-anchor="end">{length:.0f}s</text>',
             f'<text x="{pad - 4}" y="{pad + 4}" class="ax" text-anchor="end">100%</text>']
    if past3 is not None:
        parts.append(f'<polyline points="{sx(0)},{sy(100)} {sx(3)},{sy(past3)}" class="line"/>')
        parts.append(f'<circle cx="{sx(3)}" cy="{sy(past3)}" r="4" class="dot"><title>{past3}% still watching after 3s</title></circle>')
        parts.append(f'<text x="{sx(3) + 7}" y="{sy(past3) + 4}" class="lbl">{past3:.0f}% past 3s</text>')
    avg = r["avg_watch_s"]
    parts.append(f'<line x1="{sx(avg)}" y1="{pad}" x2="{sx(avg)}" y2="{h - pad}" class="avg"/>')
    pct = f' ({r["avg_watch_pct_of_length"]:.0f}% of reel)' if r["avg_watch_pct_of_length"] else ""
    parts.append(f'<text x="{min(sx(avg) + 5, w - 120)}" y="{pad + 12}" class="lbl">avg watch {avg:.0f}s{pct}</text>')
    return f'<svg viewBox="0 0 {w} {h}" class="mini">{"".join(parts)}</svg>'


def write_report(rows: list[dict], out_dir: Path) -> Path:
    views = sum(r["views"] or 0 for r in rows)
    n = len(rows) or 1
    cards = [("Reels", f"{len(rows)}"), ("Total views", f"{views:,}"), ("Avg views / reel", f"{views // n:,}"),
             ("Avg watch", f'{sum(r["avg_watch_s"] for r in rows) / n:.1f}s'),
             ("Watched past 3s", f'{sum(r["watched_past_3s_pct"] or 0 for r in rows) / n:.0f}%'),
             ("Shares", f'{sum(r["shares"] or 0 for r in rows):,}')]
    card_html = "".join(f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in cards)
    reels = "".join(
        f'<div class="reel"><a href="{html.escape(r["permalink"])}">{html.escape(r["hook"][:80]) or "(no caption)"}</a>'
        f'<div class="meta">{r["date"]} · {r["views"] or 0:,} views · {r["likes"] or 0} likes · {r["shares"] or 0} shares · '
        f'{r["saved"] or 0} saves · {r["comments"] or 0} comments</div>{_retention_chart(r)}</div>'
        for r in sorted(rows, key=lambda r: -(r["views"] or 0)))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Reel insights {date.today()}</title>
<style>
:root{{--bg:#f6f3ee;--fg:#1d1b18;--mut:#6b655c;--acc:#b8913f;--line:#7f2a1d;--card:#fff}}
@media (prefers-color-scheme: dark){{:root{{--bg:#16140f;--fg:#f1ece3;--mut:#a59d90;--card:#221f19}}}}
body{{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:960px;margin:0 auto}} h1{{font-size:22px;margin:0 0 4px}} p.note{{color:var(--mut);margin:0 0 20px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:24px}}
.card{{background:var(--card);border-radius:10px;padding:12px 14px}} .k{{color:var(--mut);font-size:13px}} .v{{font-size:22px;font-weight:600}}
.chart{{width:100%;background:var(--card);border-radius:10px}} .bar{{fill:var(--acc)}} .bar:hover{{fill:var(--line)}}
.axis{{stroke:var(--mut);stroke-width:1}} .ax{{fill:var(--mut);font-size:11px}} .lbl{{fill:var(--fg);font-size:11px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;margin-top:24px}}
.reel{{background:var(--card);border-radius:10px;padding:12px}} .reel a{{color:var(--fg);font-weight:600;text-decoration:none}}
.meta{{color:var(--mut);font-size:12px;margin:4px 0 6px}} .mini{{width:100%}}
.line{{fill:none;stroke:var(--line);stroke-width:2.5}} .dot{{fill:var(--line)}} .avg{{stroke:var(--acc);stroke-width:2;stroke-dasharray:4 3}}
</style></head><body><main>
<h1>Reel insights</h1><p class="note">Pulled {date.today()}. Retention charts show the points Instagram's API exposes:
everyone at 0s, the share still watching after 3s, and the average watch position (dashed). The full per-second curve is only in the Instagram app.</p>
<div class="cards">{card_html}</div><h2>Views per reel</h2>{_bar_chart(rows)}
<h2>Reels by views</h2><div class="grid">{reels}</div></main></body></html>"""
    path = out_dir / "report.html"
    path.write_text(page, encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, help="only the newest N reels")
    parser.add_argument("--since", help="only reels posted on or after YYYY-MM-DD")
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "instagram" / str(date.today()))
    args = parser.parse_args()

    rows = build_rows([m for m in fetch_media(args.limit, args.since) if m.get("media_product_type") == "REELS"])
    if not rows:
        sys.exit("No reels found.")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "insights.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(args.out / "insights.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = write_report(rows, args.out)
    print(f"{len(rows)} reels -> {args.out}\nOpen {report}")


if __name__ == "__main__":
    main()
