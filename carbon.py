#!/usr/bin/env python3
"""Estimate the energy, carbon, heat and water footprint of your Claude Code usage.

Reads token counts from ~/.claude/projects/**/*.jsonl and writes an HTML dashboard,
or with --live serves one on localhost that updates while you work.
Every coefficient below is an estimate; SKILL.md lists the sources.
"""
import argparse
import glob
import html
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

# Facility-free Wh per 1k tokens for a Sonnet-class model: (low, central, high).
# Anchors: Epoch AI 2025 (~0.3 Wh per ~500-token GPT-4o reply, ~2.5 Wh with 10k input),
# Google Aug 2025 (0.24 Wh per median Gemini text prompt).
WH_PER_1K = {
    "output": (0.2, 0.6, 2.0),
    "input": (0.05, 0.2, 0.6),  # fresh input + cache writes = full prefill
    # shortcut: cache reads assumed ~10% of prefill (same ratio as list price), upgrade if providers publish real numbers
    "cache_read": (0.005, 0.02, 0.06),
}
# shortcut: model size inferred from relative list price, not published parameters; upgrade if Anthropic publishes energy data
MODEL_SCALE = {"haiku": 0.33, "sonnet": 1.0, "opus": 1.7, "fable": 1.7}
PUE = 1.2  # data-centre overhead (cooling, power conversion); hyperscalers report ~1.1-1.2
CAR_G_PER_KM = 170  # average petrol car, real-world
PHONE_CHARGE_WH = 15
BOTTLE_L = 0.5
# Session name records in the logs: your rename beats Claude's AI title beats the last prompt.
TITLE_FIELDS = {"custom-title": ("customTitle", 3), "ai-title": ("aiTitle", 2), "last-prompt": ("lastPrompt", 1)}
LIVE_WINDOW_S = 300  # "right now" rate = last 5 minutes
HOT_G_PER_MIN = 50  # rate at which the live chip is drawn fully hot


def model_scale(model):
    m = (model or "").lower()
    return next((v for k, v in MODEL_SCALE.items() if k in m), 1.0)


def token_counts(usage):
    g = lambda k: usage.get(k) or 0
    return {
        "output": g("output_tokens"),
        "input": g("input_tokens") + g("cache_creation_input_tokens"),
        "cache_read": g("cache_read_input_tokens"),
    }


def energy_wh(usage, model):
    """(low, central, high) facility Wh for one API response."""
    toks = token_counts(usage)
    s = model_scale(model) * PUE / 1000
    return tuple(sum(toks[k] * WH_PER_1K[k][i] for k in toks) * s for i in range(3))


def _complete_lines(f, pos, offsets, path):
    """Yield whole lines that carry usage; a half-written last line waits for the next poll."""
    for raw in f:
        if not raw.endswith(b"\n"):
            break
        pos += len(raw)
        if b'"usage"' in raw or b'-title"' in raw or b'"last-prompt"' in raw:
            yield raw
    offsets[path] = pos


def load(root, since, state=None, session=None):
    """One row per unique API response on or after `since` (a date).

    Pass the same `state` dict on every call to read only lines appended since the last call.
    `session` limits the scan to that session's own logs (its file and its subagents' folder)."""
    state = state if state is not None else {}
    seen, offsets, rows = state.setdefault("seen", set()), state.setdefault("offsets", {}), []
    titles = state.setdefault("titles", {})  # session id -> (rank, the name Claude Code shows for it)
    projects = state.setdefault("projects", {})  # session id -> project folder
    cutoff = datetime.combine(since, datetime.min.time()).timestamp()
    for path in glob.iglob(os.path.join(root, "**", "*.jsonl"), recursive=True):
        if session and session not in os.path.relpath(path, root):
            continue
        try:
            st = os.stat(path)
        except OSError:
            continue
        start = offsets.get(path, 0)
        if st.st_mtime < cutoff or st.st_size <= start:
            continue
        with open(path, "rb") as f:
            f.seek(start)
            lines = list(_complete_lines(f, start, offsets, path))
        for raw in lines:
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if d.get("type") in TITLE_FIELDS:
                field, rank = TITLE_FIELDS[d["type"]]
                sid, text = d.get("sessionId"), " ".join((d.get(field) or "").split())
                if rank == 1 and len(text) > 120:  # a last prompt can be a whole pasted document
                    text = text[:119] + "…"
                if sid and text and rank >= titles.get(sid, (0, ""))[0]:
                    titles[sid] = (rank, text)  # the newest name of the best kind wins
                continue
            m = d.get("message")
            if not isinstance(m, dict) or not isinstance(m.get("usage"), dict) or not d.get("timestamp"):
                continue
            # Claude Code logs one line per content block, all carrying the same usage; resumed sessions copy history.
            if m.get("id"):
                key = (m["id"], d.get("requestId"))
                if key in seen:
                    continue
                seen.add(key)
            ts = datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")).astimezone()
            if ts.date() < since:
                continue
            wh = energy_wh(m["usage"], m.get("model"))
            if not wh[1]:
                continue
            sid = d.get("sessionId") or os.path.basename(path).split(".")[0]
            project = os.path.basename((d.get("cwd") or "").rstrip("/")) or "unknown"
            projects.setdefault(sid, project)
            rows.append({
                "ts": ts,
                "day": ts.date(),
                "session": sid,
                "project": project,
                "model": m.get("model") or "unknown",
                "tokens": sum(token_counts(m["usage"]).values()),
                "wh": wh,
            })
    return rows


def summarize(rows):
    total = [0.0, 0.0, 0.0]
    by = {k: defaultdict(lambda: [0.0, 0]) for k in ("day", "session", "project", "model")}
    for r in rows:
        for i in range(3):
            total[i] += r["wh"][i]
        for k in by:
            by[k][r[k]][0] += r["wh"][1]
            by[k][r[k]][1] += r["tokens"]
    return total, by


def fmt_g(g):
    return f"{g / 1000:,.2f} kg" if g >= 1000 else f"{g:,.0f} g"


def fmt_n(n):
    for unit, size in (("B", 1e9), ("M", 1e6), ("k", 1e3)):
        if n >= size:
            return f"{n / size:.1f}{unit}"
    return str(n)


def tile_values(total, since, today, grid, wue):
    """Tile text keyed by data-k; live polls swap these in place so the tile animations never restart."""
    kwh = [w / 1000 for w in total]
    co2 = [k * grid for k in kwh]
    water = [k * wue for k in kwh]
    return {
        "meta": f"Claude Code usage, {since:%d %b} – {today:%d %b %Y} · grid {grid:g} gCO₂e/kWh · PUE {PUE} · water {wue:g} L/kWh",
        "co2": fmt_g(co2[1]) + " CO₂e", "co2-range": f"range {fmt_g(co2[0])} – {fmt_g(co2[2])}",
        "co2-eq": f"≈ {co2[1] / CAR_G_PER_KM:,.0f} km in a petrol car",
        "kwh": f"{kwh[1]:,.2f} kWh", "kwh-range": f"range {kwh[0]:,.2f} – {kwh[2]:,.2f} kWh",
        "kwh-eq": f"≈ {total[1] / PHONE_CHARGE_WH:,.0f} phone charges",
        "water": f"{water[1]:,.1f} L", "water-range": f"range {water[0]:,.1f} – {water[2]:,.1f} L",
        "water-eq": f"≈ {water[1] / BOTTLE_L:,.0f} half-litre bottles",
    }


# Looping graphics for the tiles, each acting out its everyday equivalent.
ART = {
    "co2": """<svg class="art car" viewBox="0 0 120 64" aria-hidden=true><path class=road d="M0 59H120"/>
<g class=puffs><circle cx=24 cy=46 r=4 /><circle cx=24 cy=46 r=4 /><circle cx=24 cy=46 r=4 /></g>
<g class=ride><path class=paint d="M30 50V40q0-4 4-4h10l8-9h26l10 9h8q4 0 4 4v10z"/><path class=glass d="M54 30h10v6H49zM67 30h10l6 6H67z"/>
<circle class=wheel cx=44 cy=50 r=6 /><circle class=wheel cx=84 cy=50 r=6 /></g></svg>""",
    "kwh": """<svg class="art batt" viewBox="0 0 120 64" aria-hidden=true>
<g class=steam><path d="M46 17q-4-4 0-8t0-8"/><path d="M60 17q-4-4 0-8t0-8"/><path d="M74 17q-4-4 0-8t0-8"/></g>
<rect class=shell x=30 y=22 width=58 height=34 rx=7 /><rect class=cap x=90 y=32 width=6 height=14 rx=2 />
<rect class=charge x=35 y=27 width=48 height=24 rx=3 /><path class=bolt d="M62 29l-10 12h7l-4 9 11-13h-7z"/></svg>""",
    "water": """<svg class="art cup" viewBox="0 0 120 64" aria-hidden=true><defs><clipPath id=cup-clip><path d="M42 18h36l-4 42H46z"/></clipPath></defs>
<path class=drop d="M60 0c3 5 5 8 5 11a5 5 0 0 1-10 0c0-3 2-6 5-11z"/>
<g clip-path="url(#cup-clip)"><path class=wave d="M0 40q10-4 20 0t20 0t20 0t20 0t20 0t20 0t20 0V64H0z"/></g>
<path class=rim d="M42 18h36l-4 42H46z"/></svg>""",
}


def tiles_html(v):
    e = html.escape
    t = lambda k: f'<span data-k="{k}">{e(v[k])}</span>'
    cards = [("co2", "Carbon"), ("kwh", "Energy = heat released"), ("water", "Cooling water")]
    return (f'<div class=muted data-k=meta>{e(v["meta"])}</div><div class=tiles>'
            + "".join(f'<div class=tile>{ART[k]}<div class=lbl>{label}</div><div class=big>{t(k)}</div>'
                      f'<div class=eq>{t(k + "-eq")}</div><div class=sub>{t(k + "-range")}</div></div>' for k, label in cards)
            + "</div><p class=note>Ranges are wide on purpose: Anthropic does not publish per-token energy, so these are order-of-magnitude estimates.</p>")


def session_title(state, sid):
    return (state or {}).get("titles", {}).get(sid, (0, "Untitled session"))[1]


def render_body(total, by, since, today, grid, wue, state=None, live=()):
    """Daily chart and tables: the part that is re-rendered on every live poll.

    `state` is the dict load() filled (session names and projects); `live` holds the session ids active now."""
    e = html.escape

    days = [since + timedelta(n) for n in range((today - since).days + 1)]
    vals = [by["day"][d][0] / 1000 * grid for d in days]
    W, H, L, B, T = 720, 220, 48, 24, 10
    top = max(vals + [1])
    step = 10 ** len(str(int(top))) / 10
    top = step * (int(top / step) + 1)
    bw = (W - L) / len(days)
    y = lambda v: T + (H - T - B) * (1 - v / top)
    svg = []
    for i in range(5):
        v = top * i / 4
        svg.append(f'<line x1="{L}" x2="{W}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
                   f'<text x="{L - 6}" y="{y(v) + 4:.1f}" class="ax" text-anchor="end">{e(fmt_g(v))}</text>')
    label_every = max(1, len(days) // 6)
    for i, (d, v) in enumerate(zip(days, vals)):
        x, w = L + i * bw + 1, max(bw - 2, 1)  # 2px surface gap between bars
        if v:
            r = min(4, w / 2, H - B - y(v))
            svg.append(f'<path class="bar" d="M{x:.1f},{H - B} V{y(v) + r:.1f} Q{x:.1f},{y(v):.1f} {x + r:.1f},{y(v):.1f} '
                       f'H{x + w - r:.1f} Q{x + w:.1f},{y(v):.1f} {x + w:.1f},{y(v) + r:.1f} V{H - B} Z"/>')
        tip = f"{fmt_g(v)} CO₂e · {d:%a %d %b}"
        svg.append(f'<rect class="hit" x="{L + i * bw:.1f}" y="{T}" width="{bw:.1f}" height="{H - T - B}" '
                   f'tabindex="0" data-tip="{e(tip)}" aria-label="{e(tip)}"/>')
        if i % label_every == 0:
            svg.append(f'<text x="{x + w / 2:.1f}" y="{H - 6}" class="ax" text-anchor="middle">{d:%d %b}</text>')

    def table(group, head, name):
        """`name(key)` returns the cell's HTML, already escaped."""
        items = [(name(k), v) for k, v in sorted(by[group].items(), key=lambda kv: -kv[1][0])]
        if len(items) > 11:
            rest = items[10:]
            items = items[:10] + [(f"Other ({len(rest)})", [sum(v[0] for _, v in rest), sum(v[1] for _, v in rest)])]
        body = "".join(
            f"<tr><td>{k}</td><td>{fmt_n(t)}</td><td>{fmt_g(wh / 1000 * grid)}</td>"
            f"<td><span class=meter style='width:{100 * wh / max(total[1], 1e-9):.1f}%'></span></td></tr>"
            for k, (wh, t) in items)
        return f"<table><thead><tr><th>{head}</th><th>Tokens</th><th>CO₂e</th><th>Share</th></tr></thead><tbody>{body}</tbody></table>"

    daily_rows = "".join(f"<tr><td>{d:%a %d %b}</td><td>{fmt_g(v)}</td></tr>" for d, v in zip(days, vals))
    return f"""<h2>Daily CO₂e</h2><svg viewBox="0 0 {W} {H}" role=img aria-label="Daily grams of CO2e">{''.join(svg)}</svg>
<details><summary>Table view</summary><table><thead><tr><th>Day</th><th>CO₂e</th></tr></thead><tbody>{daily_rows}</tbody></table></details>
<h2>By session</h2>{table("session", "Session", lambda s: e(session_title(state, s)) + (" <span class=live>● live</span>" if s in live else "")
    + f"<div class=sub>{e((state or {}).get('projects', {}).get(s, ''))} · {e(s[:8])}</div>")}
<h2>By project</h2>{table("project", "Project", lambda p: e(p))}
<h2>By model</h2>{table("model", "Model", lambda m: e(m))}"""


# The live hero: an AI chip whose core heats from blue to red and gives off heat waves as the token rate rises.
HERO = """<section class=hero aria-labelledby=hero-h>
<svg class=chip viewBox="0 0 200 190" aria-hidden=true>
 <g class=waves><path d="M78 74q-8-10 0-20t0-20"/><path d="M100 74q-8-10 0-20t0-20"/><path d="M122 74q-8-10 0-20t0-20"/></g>
 <g class=pins><path d="M76 164v14M92 164v14M108 164v14M124 164v14M48 104h-14M48 120h-14M48 136h-14M152 104h14M152 120h14M152 136h14"/></g>
 <rect class=body x=48 y=84 width=104 height=80 rx=14 />
 <rect class=core x=72 y=100 width=56 height=48 rx=8 />
 <text x=100 y=131 text-anchor=middle>AI</text>
</svg>
<div><div class=lbl id=hero-h>Today, live</div><div class=hero-big><span id=today>–</span> CO₂e</div>
<div class=sub><span id=rate>–</span> · updated <span id=ago>–</span></div>
<ul class=active id=active aria-label="Sessions active in the last 5 minutes"></ul>
<div class=sr id=status role=status aria-atomic=true></div></div></section>"""

LIVE_JS = """
const hero=document.querySelector('.hero'),reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
const C=[[42,120,214],[235,104,52],[227,73,72]]; // cool blue -> orange -> red
const heat=l=>{const s=l<.5?0:1,t=l<.5?l*2:(l-.5)*2,a=C[s],b=C[s+1];return `rgb(${a.map((v,i)=>Math.round(v+(b[i]-v)*t))})`};
const fmt=g=>g>=1000?(g/1000).toFixed(2)+' kg':Math.round(g)+' g';
let shown=0,from=0,to=0,t0=0,last=null,lastState='';
function tick(now){const k=reduce?1:Math.min(1,(now-t0)/POLL_MS);shown=from+(to-from)*k;
 document.getElementById('today').textContent=fmt(shown);
 if(last)document.getElementById('ago').textContent=Math.max(0,Math.round((Date.now()-last)/1000))+'s ago';
 requestAnimationFrame(tick)}
async function poll(){
 if(document.hidden)return;
 try{const d=await (await fetch('data.json',{cache:'no-store'})).json();
  document.getElementById('body').innerHTML=d.html; // server-rendered, names escaped there
  for(const [k,v] of Object.entries(d.tiles))document.querySelectorAll(`[data-k="${k}"]`).forEach(el=>{if(el.textContent!==v)el.textContent=v});
  from=shown;to=d.today_g;t0=performance.now();last=Date.now();
  const lvl=Math.min(1,d.rate_g_min/HOT);
  hero.style.setProperty('--lvl',lvl.toFixed(3));hero.style.setProperty('--heat',heat(lvl));
  hero.classList.toggle('idle',d.rate_g_min===0);
  const ul=document.getElementById('active');ul.textContent=''; // titles are user text: textContent only
  d.active.forEach(s=>{const li=document.createElement('li'),b=document.createElement('b');b.textContent=s.rate_g_min.toFixed(1)+' g/min';
   li.append(b,document.createTextNode(s.title+' · '+fmt(s.today_g)+' today'));ul.append(li)});
  document.getElementById('rate').textContent=d.rate_g_min?`${d.rate_g_min.toFixed(1)} g/min right now`:'idle: no AI calls in the last 5 min';
  const st=d.rate_g_min?'AI is running, '+fmt(d.today_g)+' CO2e so far today':'AI idle';
  if(st.split(',')[0]!==lastState){lastState=st.split(',')[0];document.getElementById('status').textContent=st}
 }catch(e){document.getElementById('rate').textContent='live server stopped'}}
poll();setInterval(poll,POLL_MS);document.addEventListener('visibilitychange',poll);requestAnimationFrame(tick);
"""


def page(body, tiles, live=False):
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>TokenToll</title><style>
:root{{color-scheme:light;--surface:#fcfcfb;--card:#fff;--line:#e4e3df;--t1:#0b0b0b;--t2:#52514e;--t3:#7a7975;--bar:#2a78d6;--amber:#eda100}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{color-scheme:dark;--surface:#1a1a19;--card:#222221;--line:#383835;--t1:#f0efec;--t2:#c3c2b7;--t3:#8f8e87;--bar:#3987e5;--amber:#c98500}}}}
:root[data-theme=dark]{{color-scheme:dark;--surface:#1a1a19;--card:#222221;--line:#383835;--t1:#f0efec;--t2:#c3c2b7;--t3:#8f8e87;--bar:#3987e5;--amber:#c98500}}
body{{margin:0;background:var(--surface);color:var(--t1);font:14px/1.45 system-ui,-apple-system,sans-serif}}
main{{max-width:760px;margin:0 auto;padding:24px 16px 48px}}h1{{font-size:22px;margin:0 0 4px}}h2{{font-size:15px;margin:28px 0 8px}}
.muted{{color:var(--t2)}}.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:18px}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}}.lbl{{color:var(--t2);font-size:12px}}
.big{{font-size:24px;font-weight:600;margin:2px 0}}.sub{{color:var(--t3);font-size:12px}}
svg{{width:100%;height:auto;display:block}}.grid{{stroke:var(--line);stroke-width:1}}.ax{{fill:var(--t3);font-size:10px}}
.bar{{fill:var(--bar)}}.hit{{fill:transparent;outline:none}}.hit:hover,.hit:focus{{fill:var(--t1);fill-opacity:.06}}
table{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}}th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}}
th{{color:var(--t2);font-weight:500;font-size:12px}}td:nth-child(2),td:nth-child(3){{white-space:nowrap}}
.meter{{display:inline-block;height:8px;border-radius:0 4px 4px 0;background:var(--bar);min-width:1px}}
#tip{{position:absolute;transform:translate(-50%,-100%);background:var(--t1);color:var(--surface);padding:4px 8px;border-radius:6px;font-size:12px;font-weight:600;pointer-events:none;white-space:nowrap}}
details{{margin-top:8px}}summary{{cursor:pointer;color:var(--t2)}}.note{{color:var(--t2);font-size:12px}}
.hero{{--lvl:0;--heat:rgb(42,120,214);display:flex;align-items:center;gap:20px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 20px;margin:16px 0 4px}}
.hero .chip{{width:120px;flex:none;overflow:visible}}.hero-big{{font-size:32px;font-weight:700;font-variant-numeric:tabular-nums}}
.chip .body{{fill:var(--surface);stroke:var(--t3);stroke-width:2}}.chip .pins{{stroke:var(--t3);stroke-width:4;stroke-linecap:round}}
.chip .core{{fill:var(--heat);transition:fill 1s;filter:drop-shadow(0 0 calc(4px + 16px * var(--lvl)) var(--heat));animation:pulse calc(2.6s - 1.8s * var(--lvl)) ease-in-out infinite;transform-origin:100px 124px}}
.chip text{{fill:#fff;font:700 20px system-ui;pointer-events:none}}
.chip .waves path{{fill:none;stroke:var(--heat);stroke-width:4;stroke-linecap:round;opacity:0;animation:rise calc(2.4s - 1.2s * var(--lvl)) ease-out infinite}}
.chip .waves path:nth-child(2){{animation-delay:.4s}}.chip .waves path:nth-child(3){{animation-delay:.8s}}
@keyframes rise{{from{{transform:translateY(8px);opacity:0}}40%{{opacity:calc(.25 + .75 * var(--lvl))}}to{{transform:translateY(-16px);opacity:0}}}}
@keyframes pulse{{50%{{transform:scale(calc(1 + .06 * var(--lvl)))}}}}
.hero.idle .waves path{{animation:none}}.hero.idle .core{{animation:none}}
@media (prefers-reduced-motion:reduce){{.chip .core,.chip .waves path{{animation:none}}.chip .waves path{{opacity:calc(.8 * var(--lvl))}}}}
.live{{color:#0ca30c;font-size:11px;font-weight:600;white-space:nowrap}}
.active{{list-style:none;margin:8px 0 0;padding:0;font-size:12px;color:var(--t2)}}.active li{{display:flex;gap:8px;min-width:0}}
.active b{{color:var(--t1);font-variant-numeric:tabular-nums;white-space:nowrap}}
.sr{{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}}
.tile svg.art{{width:120px;height:64px;margin:0 0 8px -4px;overflow:visible}}.eq{{font-size:13px;margin-bottom:2px}}
.car .road{{stroke:var(--t3);stroke-width:2;stroke-dasharray:10 8;animation:road .6s linear infinite}}
.car .paint{{fill:var(--bar)}}.car .glass{{fill:var(--card)}}.car .wheel{{fill:var(--t1);stroke:var(--card);stroke-width:2}}
.car .ride{{animation:bump .45s ease-in-out infinite alternate}}
.car .puffs circle{{fill:var(--t3);opacity:0;transform-box:fill-box;transform-origin:center;animation:puff 1.8s ease-out infinite}}
.car .puffs circle:nth-child(2){{animation-delay:.6s}}.car .puffs circle:nth-child(3){{animation-delay:1.2s}}
.batt .shell{{fill:none;stroke:var(--t3);stroke-width:3}}.batt .cap{{fill:var(--t3)}}.batt .bolt{{fill:var(--card)}}
.batt .charge{{fill:var(--amber);transform-box:fill-box;transform-origin:left;animation:charge 2.4s ease-out infinite}}
.batt .steam path{{fill:none;stroke:var(--amber);stroke-width:2.5;stroke-linecap:round;opacity:0;animation:steam 2.1s ease-out infinite}}
.batt .steam path:nth-child(2){{animation-delay:.7s}}.batt .steam path:nth-child(3){{animation-delay:1.4s}}
.cup .rim{{fill:none;stroke:var(--t3);stroke-width:3;stroke-linejoin:round}}
.cup .wave{{fill:var(--bar);opacity:.75;animation:wave 2.4s linear infinite}}
.cup .drop{{fill:var(--bar);opacity:0;animation:drop 1.6s ease-in infinite}}
@keyframes road{{to{{stroke-dashoffset:18}}}}@keyframes bump{{to{{transform:translateY(-1.5px)}}}}
@keyframes puff{{from{{opacity:.6;transform:translate(0,0) scale(.6)}}to{{opacity:0;transform:translate(-18px,-16px) scale(2.2)}}}}
@keyframes charge{{from{{transform:scaleX(.08)}}85%,to{{transform:scaleX(1)}}}}
@keyframes steam{{from{{transform:translateY(6px);opacity:0}}40%{{opacity:.85}}to{{transform:translateY(-8px);opacity:0}}}}
@keyframes wave{{to{{transform:translateX(-40px)}}}}
@keyframes drop{{from{{transform:translateY(0);opacity:0}}15%{{opacity:1}}80%{{transform:translateY(24px);opacity:1}}to{{transform:translateY(26px);opacity:0}}}}
@media (prefers-reduced-motion:reduce){{.art *{{animation:none!important}}.car .puffs circle{{opacity:.35}}.batt .steam path{{opacity:.6}}}}
</style></head><body><main>
<h1>Your AI coding footprint</h1>{HERO if live else ""}
{tiles_html(tiles)}
<div id=body>{body}</div>
<h2>Cut it</h2><ul class=muted><li>Output tokens cost ~3× input and ~30× cached input: ask for diffs, not whole files.</li>
<li>Keep sessions warm so context is a cache read, not a fresh prefill; /clear between unrelated tasks.</li>
<li>Use a smaller model for search, summaries and subagents.</li></ul>
<p class=note>Method: tokens × Wh per token (Epoch AI 2025, Google 2025 anchors) × model size × PUE → kWh. kWh × grid intensity → CO₂e. All electricity becomes heat, so heat ≈ kWh. Excludes embodied hardware carbon and training.</p>
</main><div id=tip hidden></div><script>
const tip=document.getElementById('tip');
const show=e=>{{const el=e.target.closest&&e.target.closest('[data-tip]');if(!el)return;tip.textContent=el.dataset.tip;tip.hidden=false;
 const r=el.getBoundingClientRect();tip.style.left=(r.left+r.width/2+scrollX)+'px';tip.style.top=(r.top+scrollY-6)+'px'}};
document.addEventListener('pointerover',show);document.addEventListener('focusin',show);
document.addEventListener('pointerout',()=>tip.hidden=true);document.addEventListener('focusout',()=>tip.hidden=true);
{"const POLL_MS=5000,HOT=" + str(HOT_G_PER_MIN) + ";" + LIVE_JS if live else ""}
</script></body></html>"""


def serve(a):
    state, rows = {}, []
    try:
        srv = HTTPServer(("127.0.0.1", a.port), None)  # localhost only: the page shows your project names
    except OSError:
        raise SystemExit(f"Port {a.port} is busy: a live dashboard may already be running at http://127.0.0.1:{a.port}/ "
                         f"(open that), or pick another with --port.")
    print("Scanning logs (first run reads everything in the window)…", flush=True)

    def snapshot():
        today = date.today()
        since = today - timedelta(days=a.days - 1)
        rows.extend(load(a.root, since, state))
        rows[:] = [r for r in rows if r["day"] >= since]  # drop days that slid out of the window
        total, by = summarize(rows)
        now = datetime.now().astimezone()
        recent, today_by = defaultdict(float), defaultdict(float)  # Wh per session
        for r in rows:
            if r["day"] == today:
                today_by[r["session"]] += r["wh"][1]
            if (now - r["ts"]).total_seconds() < LIVE_WINDOW_S:
                recent[r["session"]] += r["wh"][1]
        g = lambda wh: wh / 1000 * a.grid
        per_min = lambda wh: round(g(wh) / (LIVE_WINDOW_S / 60), 2)
        return {
            "html": render_body(total, by, since, today, a.grid, a.wue, state, recent),
            "tiles": tile_values(total, since, today, a.grid, a.wue),
            "today_g": g(by["day"][today][0]),
            "rate_g_min": per_min(sum(recent.values())),
            "active": [{"title": session_title(state, s), "rate_g_min": per_min(wh), "today_g": g(today_by[s])}
                       for s, wh in sorted(recent.items(), key=lambda kv: -kv[1])],
        }

    first = snapshot()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Another host name means DNS rebinding: a web page reaching this server to read your session titles.
            if self.headers.get("Host") not in (f"127.0.0.1:{a.port}", f"localhost:{a.port}"):
                return self.send_error(403)
            if self.path == "/":
                body, ctype = page(first["html"], first["tiles"], live=True), "text/html; charset=utf-8"
            elif self.path == "/data.json":
                body, ctype = json.dumps(snapshot()), "application/json"
            else:
                return self.send_error(404)
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    srv.RequestHandlerClass = Handler
    print(f"Live dashboard: http://127.0.0.1:{a.port}/  (Ctrl+C to stop)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def json_summary(a):
    """Today's totals across all sessions, and one session's over the window: central g CO2e, kWh, litres."""
    today = date.today()
    figures = lambda wh: {"g": round(wh / 1000 * a.grid, 2), "kwh": round(wh / 1000, 4), "water_l": round(wh / 1000 * a.wue, 3)}
    out = {"today": figures(summarize(load(a.root, today))[0][1])}
    if a.session:
        rows = load(a.root, today - timedelta(days=a.days - 1), session=a.session)
        out["session"] = {**figures(summarize(rows)[0][1]), "tokens": sum(r["tokens"] for r in rows)}
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=30, help="how many days back (default 30)")
    p.add_argument("--grid", type=float, default=400, help="grid carbon intensity, gCO2e/kWh (default 400)")
    p.add_argument("--wue", type=float, default=1.0, help="water per kWh, litres (default 1.0)")
    p.add_argument("--root", default=os.path.expanduser("~/.claude/projects"))
    p.add_argument("--out", default=os.path.expanduser("~/.claude/tokentoll-report.html"))
    p.add_argument("--live", action="store_true", help="serve a live dashboard on localhost instead of writing a file")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--json", action="store_true", help="print today's and one session's totals as JSON (for the chat band)")
    p.add_argument("--session", help="with --json: the session id to total")
    a = p.parse_args()
    if a.days < 1:
        p.error("--days must be 1 or more")
    if a.grid < 0 or a.wue < 0:
        p.error("--grid and --wue cannot be negative")
    if a.live:
        return serve(a)
    if a.json:
        return print(json.dumps(json_summary(a)))

    today = date.today()
    since = today - timedelta(days=a.days - 1)
    state = {}
    total, by = summarize(load(a.root, since, state))
    with open(a.out, "w") as f:
        f.write(page(render_body(total, by, since, today, a.grid, a.wue, state), tile_values(total, since, today, a.grid, a.wue)))

    kwh = total[1] / 1000
    print(f"Last {a.days} days: {fmt_g(kwh * a.grid)} CO2e (range {fmt_g(total[0] / 1000 * a.grid)}-{fmt_g(total[2] / 1000 * a.grid)}), "
          f"{kwh:.2f} kWh energy/heat, {kwh * a.wue:.1f} L water")
    for name, (wh, _) in sorted(by["project"].items(), key=lambda kv: -kv[1][0])[:5]:
        print(f"  {name}: {fmt_g(wh / 1000 * a.grid)}")
    print(f"Dashboard: {a.out}")


if __name__ == "__main__":
    main()
