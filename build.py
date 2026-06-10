#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汽车情报雷达 - 构建脚本
从现有项目读取数据，生成静态 HTML 产物到 dist/ 目录
不修改现有项目任何文件
"""

import os
import re
import sys
import json
import shutil
from pathlib import Path
from datetime import date, timedelta
from html import escape as html_escape

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# ── 路径配置 ──────────────────────────────────────────────

# 项目源数据（只读）
PROJECT_DIR = Path(r"D:\YB 2026\Claude Code\☆ We-Media")
AGENT_DIR = PROJECT_DIR / "情报收集Agent"
CALENDAR_DIR = AGENT_DIR / "汽车事件日历"
LOGO_DIR = AGENT_DIR / "01-输入" / "汽车品牌 Logo"
GENERATOR_SCRIPT = AGENT_DIR / "03-基座" / "infra" / "scripts" / "generate_calendar_html.py"
CSS_TEMPLATE = AGENT_DIR / "03-基座" / "infra" / "templates" / "calendar_styles.css"
JS_TEMPLATE = AGENT_DIR / "03-基座" / "infra" / "templates" / "calendar_scripts.js"

# 输出目录
DIST_DIR = Path(r"D:\car-radar-site")
ASSETS_DIR = DIST_DIR / "assets"

# 站点配置
SITE_NAME = "汽车情报雷达"
SITE_URL = "https://yb313729711.github.io/car-radar-site"


# ── 工具函数 ─────────────────────────────────────────────

def load_calendar_events():
    """读取所有月度日历 MD 文件，解析事件"""
    events = []
    for md_file in sorted(CALENDAR_DIR.glob("*.md")):
        if not re.match(r"\d{4}-\d{2}\.md$", md_file.name):
            continue
        content = md_file.read_text(encoding="utf-8")
        for line in content.split("\n"):
            line = line.strip()
            if not line.startswith("|") or "---" in line or "日期" in line:
                continue
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) < 4:
                continue
            raw_date = re.sub(r"\*\*(.+?)\*\*", r"\1", cells[0])
            event_type = re.sub(r"\*\*(.+?)\*\*", r"\1", cells[1])
            car_name = re.sub(r"\*\*(.+?)\*\*", r"\1", cells[2])
            importance = re.sub(r"\*\*(.+?)\*\*", r"\1", cells[3]) if len(cells) > 3 else "B级"
            status = re.sub(r"\*\*(.+?)\*\*", r"\1", cells[4]) if len(cells) > 4 else ""
            note = re.sub(r"\*\*(.+?)\*\*", r"\1", cells[5]) if len(cells) > 5 else ""

            is_s = "S级" in importance
            is_completed = "已完成" in status

            events.append({
                "raw_date": raw_date,
                "event_type": event_type,
                "car_name": car_name,
                "importance": importance,
                "status": status,
                "note": note,
                "is_s": is_s,
                "is_completed": is_completed,
                "source_file": md_file.stem,
            })
    return events


def parse_date(raw_date: str, default_year_month: str = "2026-06"):
    """解析中文日期"""
    raw = raw_date.strip()
    try:
        year, month = int(default_year_month[:4]), int(default_year_month[5:7])
    except (ValueError, IndexError):
        return None

    m = re.match(r"(\d{1,2})月(\d{1,2})日", raw)
    if m:
        try:
            return date(year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None

    m = re.match(r"(\d{1,2})月(\d{1,2})日\s*[-~—]\s*(\d{1,2})日?", raw)
    if m:
        try:
            return date(year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None

    return None


def get_brand_logo_url(car_name: str) -> str:
    """根据车型名匹配品牌Logo"""
    brand_map = {
        "比亚迪": "比亚迪_BYD", "比亚迪/": "比亚迪_BYD",
        "小鹏": "小鹏_XPeng", "蔚来": "蔚来_NIO", "蔚来/": "蔚来_NIO",
        "理想": "理想", "零跑": "零跑_Leapmotor",
        "极氪": "极氪_Zeekr", "吉利": "吉利_Geely", "领克": "领克",
        "岚图": "岚图_Voyah", "智己": "智己", "奇瑞": "奇瑞_Chery",
        "哈弗": "哈弗_Haval", "坦克": "坦克_Tank",
        "长安": "长安_Changan", "广汽": "广汽_GAC",
        "问界": "问界", "智界": "智界", "尚界": "尚界",
        "腾势": "腾势", "方程豹": "方程豹",
    }
    for brand, logo_name in brand_map.items():
        if brand in car_name:
            logo_path = LOGO_DIR / f"{logo_name}.png"
            if logo_path.exists():
                return f"assets/logos/{logo_name}.png"
    return ""


# ── 导航栏生成 ───────────────────────────────────────────

NAV_HTML = """
<div class="site-nav">
    <a class="nav-logo" href="index.html">{site_name}</a>
    <div class="nav-links">
        <a class="nav-link{active_calendar}" href="index.html">日历</a>
        <a class="nav-link{active_hot}" href="hot-ranking.html">热点</a>
        <a class="nav-link{active_price}" href="price-tracker.html">价格</a>
    </div>
    <a class="nav-subscribe-btn" href="subscribe.html">订阅日报</a>
</div>
""".strip()


def render_nav(active_page: str) -> str:
    return NAV_HTML.format(
        site_name=SITE_NAME,
        active_calendar=' active' if active_page == 'calendar' else '',
        active_hot=' active' if active_page == 'hot' else '',
        active_price=' active' if active_page == 'price' else '',
    )


# ── CSS / JS ─────────────────────────────────────────────

SITE_CSS = """
/* === Site Nav === */
.site-nav {
    display: flex; align-items: center; gap: 16px;
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; padding: 10px 20px; margin-bottom: 20px;
}
.nav-logo {
    font-size: 1.1rem; font-weight: 800; color: var(--accent);
    text-decoration: none; white-space: nowrap;
}
.nav-links { display: flex; gap: 4px; flex: 1; }
.nav-link {
    padding: 4px 14px; border-radius: 6px; font-size: 0.82rem;
    color: var(--muted); text-decoration: none; transition: all 0.15s;
}
.nav-link:hover { color: var(--text); background: rgba(255,255,255,0.05); }
.nav-link.active { color: var(--accent); background: rgba(56,189,248,0.1); }
.nav-subscribe-btn {
    padding: 5px 14px; border-radius: 6px; font-size: 0.78rem;
    background: rgba(56,189,248,0.15); color: var(--accent);
    text-decoration: none; border: 1px solid rgba(56,189,248,0.3);
    white-space: nowrap; transition: all 0.15s;
}
.nav-subscribe-btn:hover { background: rgba(56,189,248,0.25); }
@media (max-width: 600px) {
    .site-nav { flex-wrap: wrap; gap: 8px; padding: 8px 12px; }
    .nav-links { order: 3; width: 100%; }
}
"""


# ── 热点排行页 ───────────────────────────────────────────

def build_hot_ranking(events: list) -> str:
    today = date.today()
    upcoming = []
    for ev in events:
        if ev["is_completed"]:
            continue
        d = parse_date(ev["raw_date"], "2026-06" if "06" in ev.get("source_file", "") else "2026-05")
        if not d:
            upcoming.append((999, ev))
        else:
            delta = (d - today).days
            upcoming.append((delta, ev))

    upcoming.sort(key=lambda x: (x[0], 0 if x[1]["is_s"] else 1))

    cards_html = ""
    for i, (delta, ev) in enumerate(upcoming[:20], 1):
        level_cls = "level-s" if ev["is_s"] else "level-a" if "A级" in ev["importance"] else "level-b"
        card_cls = "rank-card rank-s" if ev["is_s"] else "rank-card"
        countdown = f"{delta}天后" if delta < 999 else "待定"
        date_label = ev["raw_date"] if delta >= 999 else f"{ev['raw_date']}"
        logo = get_brand_logo_url(ev["car_name"])
        logo_html = f'<img class="rank-logo" src="{logo}" alt="" />' if logo else ""

        cards_html += f"""
        <div class="{card_cls}">
            <div class="rank-num">{i}</div>
            <div class="rank-logo-wrap">{logo_html}</div>
            <div class="rank-body">
                <div class="rank-title">
                    <span class="level-badge {level_cls}">{html_escape(ev['importance'])}</span>
                    {html_escape(ev['car_name'])}
                </div>
                <div class="rank-meta">
                    <span class="rank-date">{html_escape(date_label)} · {html_escape(ev['event_type'])}</span>
                    <span class="rank-countdown">{countdown}</span>
                </div>
                <div class="rank-note">{html_escape(ev['note'][:80])}</div>
            </div>
        </div>"""

    hot_css = SITE_CSS + """
    .ranking-list { display: flex; flex-direction: column; gap: 8px; }
    .rank-card {
        display: flex; align-items: center; gap: 12px;
        background: var(--card); border: 1px solid var(--border);
        border-radius: 10px; padding: 12px 16px; transition: border-color 0.15s;
    }
    .rank-card:hover { border-color: var(--accent); }
    .rank-card.rank-s { border-left: 3px solid var(--s-color); }
    .rank-num { font-size: 1.2rem; font-weight: 800; color: var(--muted); min-width: 28px; text-align: center; }
    .rank-s .rank-num { color: var(--s-color); }
    .rank-logo-wrap { width: 36px; height: 36px; flex-shrink: 0; }
    .rank-logo { width: 36px; height: 36px; object-fit: contain; border-radius: 6px; }
    .rank-body { flex: 1; min-width: 0; }
    .rank-title { font-size: 0.9rem; font-weight: 600; margin-bottom: 2px; word-break: break-word; }
    .rank-meta { font-size: 0.75rem; color: var(--muted); display: flex; gap: 12px; margin-bottom: 2px; }
    .rank-countdown { color: var(--accent); font-weight: 600; }
    .rank-note { font-size: 0.72rem; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    """

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>热点排行 - {SITE_NAME}</title>
<style>
:root {{--bg:#0f172a;--card:#1e293b;--text:#e2e8f0;--muted:#94a3b8;--accent:#38bdf8;--s-color:#ef4444;--a-color:#f59e0b;--b-color:#10b981;--border:#334155;}}
*{{box-sizing:border-box;margin:0;}}
html{{scroll-behavior:smooth;}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans SC",sans-serif;background:var(--bg);color:var(--text);line-height:1.5;overflow-x:hidden;}}
.container{{width:100%;margin:0 auto;padding:16px;max-width:1200px;}}
@media(min-width:768px){{.container{{padding:16px 24px;}}}}
h2{{margin:20px 0 12px;font-size:1.1rem;border-left:3px solid var(--accent);padding-left:10px;}}
.level-badge{{display:inline-block;padding:1px 7px;border-radius:3px;font-size:0.7rem;font-weight:600;margin-right:5px;white-space:nowrap;}}
.level-s{{background:rgba(239,68,68,0.2);color:#fca5a5;}}
.level-a{{background:rgba(245,158,11,0.2);color:#fcd34d;}}
.level-b{{background:rgba(16,185,129,0.2);color:#6ee7b7;}}
.footer{{margin-top:24px;color:var(--muted);font-size:0.75rem;text-align:center;}}
{hot_css}
</style>
</head>
<body>
<div class="container">
{render_nav('hot')}
<h2>热点车型排行 TOP 20</h2>
<p style="color:var(--muted);font-size:0.82rem;margin-bottom:16px;">基于上市节点、事件等级、时间紧迫度综合排序 · 更新于 {today.isoformat()}</p>
<div class="ranking-list">
{cards_html}
</div>
<div class="footer">由汽车情报雷达自动生成 · 数据来源：公开信息整理</div>
</div>
</body>
</html>"""


# ── 订阅页 ───────────────────────────────────────────────

def build_subscribe_page() -> str:
    sub_css = SITE_CSS + """
    .subscribe-box {
        background: var(--card); border: 1px solid var(--border);
        border-radius: 14px; padding: 32px; max-width: 520px; margin: 40px auto;
        text-align: center;
    }
    .subscribe-box h2 { border: none; padding: 0; margin: 0 0 8px; font-size: 1.3rem; }
    .subscribe-box p { color: var(--muted); font-size: 0.88rem; margin-bottom: 20px; }
    .subscribe-form { display: flex; gap: 8px; }
    .subscribe-input {
        flex: 1; padding: 10px 14px; border-radius: 8px;
        border: 1px solid var(--border); background: var(--bg);
        color: var(--text); font-size: 0.9rem; outline: none;
    }
    .subscribe-input:focus { border-color: var(--accent); }
    .subscribe-btn {
        padding: 10px 20px; border-radius: 8px; border: none;
        background: var(--accent); color: #0f172a; font-weight: 700;
        font-size: 0.9rem; cursor: pointer; white-space: nowrap;
    }
    .subscribe-btn:hover { opacity: 0.9; }
    .subscribe-features {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px; margin: 32px 0; text-align: left;
    }
    .sub-feature {
        background: rgba(255,255,255,0.03); border: 1px solid var(--border);
        border-radius: 8px; padding: 14px;
    }
    .sub-feature h4 { font-size: 0.88rem; margin-bottom: 4px; }
    .sub-feature p { font-size: 0.78rem; color: var(--muted); }
    @media(max-width:500px){ .subscribe-form{flex-direction:column;} }
    """
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>订阅日报 - {SITE_NAME}</title>
<style>
:root {{--bg:#0f172a;--card:#1e293b;--text:#e2e8f0;--muted:#94a3b8;--accent:#38bdf8;--border:#334155;}}
*{{box-sizing:border-box;margin:0;}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans SC",sans-serif;background:var(--bg);color:var(--text);line-height:1.5;overflow-x:hidden;}}
.container{{width:100%;margin:0 auto;padding:16px;max-width:800px;}}
{sub_css}
</style>
</head>
<body>
<div class="container">
{render_nav('')}
<div class="subscribe-box">
    <h2>订阅汽车情报日报</h2>
    <p>每日 8:00 邮件推送：新车上市动态、价格变动、热点排行</p>
    <div class="subscribe-features">
        <div class="sub-feature"><h4>新车上市日历</h4><p>S/A/B级事件提前3天提醒，不错过任何重磅发布</p></div>
        <div class="sub-feature"><h4>价格变动追踪</h4><p>热门车型价格/配置变化实时追踪</p></div>
        <div class="sub-feature"><h4>热点车型排行</h4><p>AI综合热度评分，快速锁定选题方向</p></div>
    </div>
    <form class="subscribe-form" action="#" method="GET">
        <input class="subscribe-input" type="email" placeholder="输入你的邮箱地址" required />
        <button class="subscribe-btn" type="submit">免费订阅</button>
    </form>
    <p style="margin-top:12px;font-size:0.72rem;color:var(--muted);">完全免费，随时退订。我们不会发送垃圾邮件。</p>
</div>
</div>
</body>
</html>"""


# ── 日历页注入导航 ───────────────────────────────────────

def build_calendar_page() -> str:
    """运行现有生成脚本，然后注入站点导航"""
    import subprocess
    result = subprocess.run(
        [sys.executable, str(GENERATOR_SCRIPT)],
        cwd=str(AGENT_DIR),
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        print(f"[ERROR] 日历生成失败: {result.stderr}")
        return ""

    html_path = CALENDAR_DIR / "index.html"
    if not html_path.exists():
        print("[ERROR] 日历 HTML 未生成")
        return ""

    html = html_path.read_text(encoding="utf-8")

    # 注入站点 CSS
    html = html.replace("</style>", SITE_CSS + "\n</style>", 1)

    # 注入导航栏（在 header 之前）
    nav = render_nav("calendar")
    html = html.replace('<div class="container">', '<div class="container">\n' + nav, 1)

    return html


# ── 主构建流程 ───────────────────────────────────────────

def main():
    print("=" * 60)
    print(f"汽车情报雷达 - 构建开始")
    print(f"时间: {date.today().isoformat()}")
    print("=" * 60)

    # Step 1: 读取数据
    print("\n[1/5] 读取日历数据...")
    events = load_calendar_events()
    print(f"  读取 {len(events)} 个事件")

    # Step 2: 复制资源文件
    print("\n[2/5] 复制资源文件...")
    if ASSETS_DIR.exists():
        shutil.rmtree(ASSETS_DIR)
    ASSETS_DIR.mkdir(parents=True)

    (ASSETS_DIR / "css").mkdir(exist_ok=True)
    (ASSETS_DIR / "js").mkdir(exist_ok=True)
    (ASSETS_DIR / "logos").mkdir(exist_ok=True)

    # 复制Logo
    if LOGO_DIR.exists():
        for logo in LOGO_DIR.glob("*.png"):
            shutil.copy2(logo, ASSETS_DIR / "logos" / logo.name)
        print(f"  复制 {len(list((ASSETS_DIR / 'logos').glob('*.png')))} 个品牌Logo")

    # Step 3: 生成日历页
    print("\n[3/5] 生成日历页...")
    calendar_html = build_calendar_page()
    if calendar_html:
        # 修正资源路径（Logo 从相对路径改为 assets/ 路径）
        calendar_html = calendar_html.replace("汽车事件日历/", "")
        (DIST_DIR / "index.html").write_text(calendar_html, encoding="utf-8")
        print("  index.html 生成完成")

    # Step 4: 生成热点排行页
    print("\n[4/5] 生成热点排行页...")
    hot_html = build_hot_ranking(events)
    (DIST_DIR / "hot-ranking.html").write_text(hot_html, encoding="utf-8")
    print("  hot-ranking.html 生成完成")

    # Step 5: 生成订阅页
    print("\n[5/5] 生成订阅页...")
    sub_html = build_subscribe_page()
    (DIST_DIR / "subscribe.html").write_text(sub_html, encoding="utf-8")
    print("  subscribe.html 生成完成")

    print("\n" + "=" * 60)
    print("构建完成！产物目录：", DIST_DIR)
    print("文件列表：")
    for f in sorted(DIST_DIR.rglob("*")):
        if f.is_file() and ".git" not in str(f):
            rel = f.relative_to(DIST_DIR)
            size = f.stat().st_size
            print(f"  {rel} ({size // 1024}KB)")
    print("=" * 60)


if __name__ == "__main__":
    main()
