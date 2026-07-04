"""Build the static DIAMONDIQ site (docs/) from data/dashboard/*.json + README/DECISIONS.

Audience-oriented information architecture (FEEDBACK.md): a landing router plus fan / data-eng /
data-science / betting pages, and the kept compare / simulator / glossary pages. ALL of docs/ is a
build artifact of THIS script — never hand-edit docs/. One shared stylesheet (assets/site.css), one
shared JS util (assets/util.js), and a team-color map (assets/teams.js). Pure HTML/JS, no framework,
no CDN beyond Google Fonts. Run after prepare_dashboard_data.py + season_sim.py.

Design system (FEEDBACK §1): one dark theme with per-audience motifs. Red = brand/nav ONLY, never
"better/winner" (that is --good/--gold or team colors). <=3 decimals everywhere; no 'x.0' integers.
12px type floor; visible focus; labels on inputs; no emojis; a data-provenance strip per page.
"""
# ruff: noqa: E501  (this file emits HTML/CSS/JS — long string literals are inherent)
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = json.loads((REPO / "data" / "dashboard" / "site_data.json").read_text())
_SIM_PATH = REPO / "data" / "dashboard" / "season_sim.json"
SIM = json.loads(_SIM_PATH.read_text()) if _SIM_PATH.exists() else None
DOCS = REPO / "docs"
ASSETS = DOCS / "assets"
GH = "https://github.com/Steve27M/mlb-analytics"

# ------------------------------------------------------------------ team identity (colors, no logos)
# Widely published primary/secondary hex (teamcolorcodes-style). No club marks — see FEEDBACK §2.
TEAM_META = {
    108: ("LAA", "Los Angeles Angels", "#BA0021", "#003263"),
    109: ("ARI", "Arizona Diamondbacks", "#A71930", "#E3D4AD"),
    110: ("BAL", "Baltimore Orioles", "#DF4601", "#FCB826"),
    111: ("BOS", "Boston Red Sox", "#BD3039", "#0C2340"),
    112: ("CHC", "Chicago Cubs", "#0E3386", "#CC3433"),
    113: ("CIN", "Cincinnati Reds", "#C6011F", "#BC9A6C"),
    114: ("CLE", "Cleveland Guardians", "#00385D", "#E50022"),
    115: ("COL", "Colorado Rockies", "#333366", "#C4CED4"),
    116: ("DET", "Detroit Tigers", "#0C2340", "#FA4616"),
    117: ("HOU", "Houston Astros", "#002D62", "#EB6E1F"),
    118: ("KC", "Kansas City Royals", "#004687", "#BD9B60"),
    119: ("LAD", "Los Angeles Dodgers", "#005A9C", "#EF3E42"),
    120: ("WSH", "Washington Nationals", "#AB0003", "#14225A"),
    121: ("NYM", "New York Mets", "#002D72", "#FF5910"),
    133: ("ATH", "Athletics", "#003831", "#EFB21E"),
    134: ("PIT", "Pittsburgh Pirates", "#27251F", "#FDB827"),
    135: ("SD", "San Diego Padres", "#2F241D", "#FFC425"),
    136: ("SEA", "Seattle Mariners", "#0C2C56", "#005C5C"),
    137: ("SF", "San Francisco Giants", "#FD5A1E", "#C4CED4"),
    138: ("STL", "St. Louis Cardinals", "#C41E3A", "#0C2340"),
    139: ("TB", "Tampa Bay Rays", "#092C5C", "#8FBCE6"),
    140: ("TEX", "Texas Rangers", "#003278", "#C0111F"),
    141: ("TOR", "Toronto Blue Jays", "#134A8E", "#E8291C"),
    142: ("MIN", "Minnesota Twins", "#002B5C", "#D31145"),
    143: ("PHI", "Philadelphia Phillies", "#E81828", "#284898"),
    144: ("ATL", "Atlanta Braves", "#CE1141", "#13274F"),
    145: ("CWS", "Chicago White Sox", "#27251F", "#C4CED4"),
    146: ("MIA", "Miami Marlins", "#00A3E0", "#EF3340"),
    147: ("NYY", "New York Yankees", "#0C2340", "#C4CED3"),
    158: ("MIL", "Milwaukee Brewers", "#12284B", "#FFC52F"),
}
PANEL = "#13161e"  # --panel; team primary must clear ~1.6:1 contrast against it or fall back


def _luminance(hexc: str) -> float:
    """WCAG relative luminance of an sRGB hex color."""
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


_PANEL_L = _luminance(PANEL)


def _contrast(hexc: str) -> float:
    la, lb = sorted((_luminance(hexc), _PANEL_L), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def team_fill(team_id: int) -> str:
    """Primary team color for a fill on the dark panel — falls back to secondary when the primary
    is too dark to read against --panel (many primaries are navy). Same rule lives in util.js."""
    m = TEAM_META.get(int(team_id))
    if not m:
        return "var(--a)"
    primary, secondary = m[2], m[3]
    return primary if _contrast(primary) >= 1.6 else secondary


def abbr(team_id: int) -> str:
    m = TEAM_META.get(int(team_id))
    return m[0] if m else "?"


def fmt(v, dec: int = 3) -> str:
    """<=3 decimals; strip trailing zeros/'.0'; ints render clean (FEEDBACK §1.2)."""
    if v is None:
        return "—"
    if isinstance(v, int) or (isinstance(v, float) and v.is_integer()):
        return str(int(v))
    return f"{round(float(v), min(dec, 3)):.{min(dec, 3)}f}".rstrip("0").rstrip(".")


# ------------------------------------------------------------------ README / DECISIONS extraction
# Single source of truth (FEEDBACK §5.1-3, Q7): read the docs at build time; don't paraphrase.
_README = (REPO / "README.md").read_text(encoding="utf-8")


def _md_section(text: str, title_startswith: str) -> str:
    """Return the body under the first '## <title...>' heading, up to the next '## '."""
    lines = text.splitlines()
    out, grab = [], False
    for ln in lines:
        if ln.startswith("## "):
            if grab:
                break
            grab = ln[3:].strip().startswith(title_startswith)
            continue
        if grab:
            out.append(ln)
    return "\n".join(out).strip()


def readme_tagline() -> str:
    m = re.search(r"\*\*(.+?builds every.+?agree.*?)\*\*", _README, re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else "Every model built twice — R and Python — and gated on agreement."


def readme_war_stories() -> list[tuple[str, str]]:
    """The curated case-study bullets from the README (already the best 4-5). Returns (lead, rest)."""
    sec = _md_section(_README, "Case study")
    items = []
    for m in re.finditer(r"^- \*\*(.+?)\*\*(.*?)(?=^\- \*\*|\Z)", sec, re.S | re.M):
        lead = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".")
        rest = re.sub(r"\s+", " ", m.group(2)).strip()
        rest = re.sub(r"`([^`]+)`", r"<code>\1</code>", rest)
        items.append((lead, rest))
    return items


def parity_tiers() -> list[tuple[str, str, str]]:
    """(tier, what-matches, why) rows from the README parity table."""
    sec = _md_section(_README, "The parity contract")
    rows = []
    for m in re.finditer(r"^\| \*\*(.+?)\*\* \| (.+?) \| (.+?) \|", sec, re.M):
        rows.append(tuple(re.sub(r"\\\|", "|", c).strip() for c in m.groups()))
    return rows


# ------------------------------------------------------------------ shared assets (written to docs/)
FONTS = ("https://fonts.googleapis.com/css2?family=Anton&family=Saira+Condensed:wght@600;700;800"
         "&family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap")

CSS = r"""
:root{
  --a:#ef4b4b; --a2:#9e1f1f; --aText:#1a0505;
  --bg:#08090c; --text:#f4f6fb; --sub:#9aa4b6; --border:rgba(255,255,255,.10);
  --panel:#13161e; --panel2:#0c0e14; --panelHi:#1b1f2a; --good:#3ddc84; --bad:#ff6b6b; --gold:#ffd166;
}
*{box-sizing:border-box;} html{scroll-behavior:smooth;}
body{margin:0;background:var(--bg);color:var(--text);font-family:'Space Grotesk',sans-serif;
  background:radial-gradient(140% 55% at 50% 0%,color-mix(in srgb,var(--a) 12%,var(--bg)) 0%,var(--bg) 52%);
  background-attachment:fixed;padding-bottom:70px;font-size:16px;}
a{color:inherit;text-decoration:none;}
::-webkit-scrollbar{width:11px;height:11px;} ::-webkit-scrollbar-track{background:#0c0e13;}
::-webkit-scrollbar-thumb{background:#242833;border-radius:6px;}
.wrap{max-width:1120px;margin:0 auto;padding:0 26px;}
/* ---- focus (a11y §1.4): visible everywhere, never outline:none ---- */
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,[tabindex]:focus-visible{
  outline:2px solid var(--gold);outline-offset:2px;border-radius:6px;}
.vh{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0;}
/* ---- nav ---- */
.nav{position:sticky;top:0;z-index:40;backdrop-filter:blur(14px);background:rgba(8,9,13,.85);border-bottom:1px solid var(--border);}
.nav .in{display:flex;align-items:center;gap:14px;padding:11px 26px;}
.brand{display:flex;align-items:center;gap:9px;}
.brand .bar{width:9px;height:26px;border-radius:3px;background:linear-gradient(var(--a),var(--a2));}
.brand .txt{font:800 15px 'Saira Condensed';letter-spacing:.14em;}
.navlinks{display:flex;gap:2px;flex-wrap:wrap;margin-left:auto;align-items:center;}
.navlinks a{font:600 12.5px 'Space Grotesk';letter-spacing:.03em;color:var(--sub);padding:7px 11px;border-radius:8px;white-space:nowrap;}
.navlinks a:hover{color:var(--text);background:var(--panel);}
.navlinks a.active{color:var(--aText);background:var(--a);}
.navlinks a.ext{color:var(--sub);border:1px solid var(--border);}
.hamb{display:none;margin-left:auto;background:var(--panel);border:1px solid var(--border);color:var(--text);border-radius:8px;padding:8px 11px;font:700 13px 'Space Grotesk';cursor:pointer;}
@media(max-width:760px){
  .hamb{display:block;}
  .navlinks{display:none;position:absolute;top:100%;left:0;right:0;flex-direction:column;background:rgba(8,9,13,.97);border-bottom:1px solid var(--border);padding:8px 20px 14px;gap:2px;}
  .navlinks.open{display:flex;} .navlinks a{margin-left:0;padding:11px 12px;}
}
/* ---- hero + sections ---- */
.hero{padding:42px 0 6px;} .hero .eyebrow{font:600 12px 'Space Grotesk';letter-spacing:.22em;color:var(--a);text-transform:uppercase;}
.hero h1{font:400 clamp(38px,6vw,66px)/.92 'Anton';text-transform:uppercase;margin:10px 0 0;}
.hero p{font:400 16px/1.6 'Space Grotesk';color:var(--sub);max-width:720px;margin:14px 0 0;}
.hero p b{color:var(--text);}
.prov{margin:16px 0 0;font:500 12px/1.5 'JetBrains Mono';color:var(--sub);border-left:2px solid var(--border);padding:6px 0 6px 12px;}
.sec{display:flex;align-items:center;gap:12px;margin:40px 0 16px;}
.sec h2{font:400 22px 'Anton';letter-spacing:.02em;text-transform:uppercase;margin:0;}
.sec .line{flex:1;height:1px;background:var(--border);}
.lead{font:400 15px/1.65 'Space Grotesk';color:var(--sub);max-width:760px;margin:-4px 0 8px;}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;} .grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}
.card{border-radius:16px;border:1px solid var(--border);background:var(--panel);padding:18px 20px;display:flex;flex-direction:column;gap:10px;}
.card .name{font:400 21px 'Anton';text-transform:uppercase;letter-spacing:.01em;}
.card .def{font:400 14px/1.6 'Space Grotesk';color:var(--text);} .card .read{font:400 13px/1.6 'Space Grotesk';color:var(--sub);border-left:2px solid var(--a);padding-left:12px;}
.card .read b{color:var(--text);font-weight:600;}
.badge{font:700 11px 'Space Grotesk';letter-spacing:.06em;text-transform:uppercase;padding:4px 9px;border-radius:999px;border:1px solid var(--border);color:var(--sub);white-space:nowrap;}
.badge.good{color:var(--aText);background:var(--good);border-color:var(--good);} .badge.gold{color:#1a0505;background:var(--gold);border-color:var(--gold);} .badge.a{color:var(--aText);background:var(--a);border-color:var(--a);}
.stat{font:700 30px 'Saira Condensed';} .stat .u{font:600 13px 'Space Grotesk';color:var(--sub);margin-left:6px;}
.kv{display:flex;justify-content:space-between;gap:12px;font:500 13px 'Space Grotesk';color:var(--sub);padding:3px 0;} .kv b{color:var(--text);font:700 13px 'JetBrains Mono';}
.mono{font-family:'JetBrains Mono';}
/* ---- team chip / monogram ---- */
.chip{display:inline-flex;align-items:center;gap:7px;} .mono-chip{width:30px;height:30px;border-radius:8px;display:inline-flex;align-items:center;justify-content:center;font:700 12px 'Saira Condensed';color:#fff;flex:none;text-shadow:0 1px 2px rgba(0,0,0,.5);border:1px solid rgba(255,255,255,.14);}
/* ---- distribution bar (glossary/fan) ---- */
.dist{margin-top:2px;} .dist .track{position:relative;height:10px;border-radius:5px;background:linear-gradient(90deg,var(--panel2),var(--panelHi));border:1px solid var(--border);}
.dist .med{position:absolute;top:-3px;width:2px;height:16px;background:var(--text);border-radius:2px;}
.dist .ends{display:flex;justify-content:space-between;margin-top:7px;font:600 12px 'JetBrains Mono';color:var(--sub);}
.dist .ex{display:flex;justify-content:space-between;gap:8px;margin-top:9px;font:500 12px 'Space Grotesk';}
.dist .ex .chip{color:var(--sub);} .dist .ex .chip b{font:700 13px 'Saira Condensed';color:var(--text);} .dist .dot{width:8px;height:8px;border-radius:2px;}
/* ---- toolbar / inputs ---- */
.toolbar{display:flex;gap:12px;align-items:center;margin:24px 0 6px;flex-wrap:wrap;}
.search{flex:1;min-width:220px;display:flex;align-items:center;gap:10px;background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:11px 15px;}
.search input,select{background:var(--panel);border:1px solid var(--border);border-radius:10px;color:var(--text);font:500 14px 'Space Grotesk';padding:9px 12px;}
.search input{flex:1;border:none;padding:0;background:none;} .count{font:600 12px 'JetBrains Mono';color:var(--sub);}
.empty{grid-column:1/-1;text-align:center;color:var(--sub);font:500 14px 'Space Grotesk';padding:40px;}
/* ---- compare bars ---- */
.cmp{display:grid;grid-template-columns:1fr 60px 1fr;gap:10px;align-items:center;margin:8px 0;}
.cmp .lab{grid-column:1/-1;text-align:center;font:600 12px 'Space Grotesk';letter-spacing:.1em;text-transform:uppercase;color:var(--sub);margin-top:8px;}
.cmp .bar{height:26px;border-radius:6px;background:var(--panel2);position:relative;overflow:hidden;border:1px solid var(--border);}
.cmp .fill{position:absolute;top:0;bottom:0;} .cmp .fill.r{right:0;} .cmp .fill.l{left:0;}
.cmp .v{position:absolute;top:5px;font:700 13px 'JetBrains Mono';color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.6);} .cmp .v.win{color:var(--gold);}
.cmp .mid{text-align:center;font:700 12px 'Space Grotesk';color:var(--sub);}
@media(max-width:560px){.cmp{grid-template-columns:1fr;} .cmp .mid{display:none;}}
/* ---- standings rows (simulator/fan) ---- */
.srow{display:grid;grid-template-columns:1.4fr .9fr 1.5fr;gap:8px;align-items:center;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.05);border-left:3px solid transparent;padding-left:9px;}
.shdr{display:grid;grid-template-columns:1.4fr .9fr 1.5fr;gap:8px;font:600 11px 'Space Grotesk';letter-spacing:.05em;text-transform:uppercase;color:var(--sub);padding:0 0 4px 9px;border-bottom:1px solid var(--border);}
.steam{display:flex;align-items:center;gap:7px;font:700 14px 'Saira Condensed';} .steam .srec{font:500 12px 'JetBrains Mono';color:var(--sub);}
.pdot{width:9px;height:9px;border-radius:2px;background:var(--gold);flex:none;} .pdot.off{background:rgba(255,255,255,.14);}
.sproj{font:700 16px 'JetBrains Mono';display:flex;flex-direction:column;line-height:1.1;} .sproj .srange{font:500 11px 'JetBrains Mono';color:var(--sub);}
.obar{position:relative;height:18px;border-radius:5px;background:var(--panel2);border:1px solid var(--border);overflow:hidden;} .obar .ofill{position:absolute;top:0;bottom:0;left:0;} .obar .oval{position:absolute;right:6px;top:1px;font:700 12px 'JetBrains Mono';color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.7);}
.legend{display:flex;gap:16px;flex-wrap:wrap;font:500 12px 'Space Grotesk';color:var(--sub);margin:6px 0 2px;} .legend span{display:flex;align-items:center;gap:6px;}
/* ---- flat sortable table (betting/simulator) ---- */
.tblwrap{overflow-x:auto;border:1px solid var(--border);border-radius:14px;} table.flat{border-collapse:collapse;width:100%;min-width:640px;font:500 13px 'JetBrains Mono';}
table.flat th{position:sticky;top:0;background:var(--panelHi);color:var(--sub);font:600 11px 'Space Grotesk';letter-spacing:.05em;text-transform:uppercase;text-align:right;padding:10px 12px;cursor:pointer;white-space:nowrap;border-bottom:1px solid var(--border);}
table.flat th:first-child,table.flat td:first-child{text-align:left;} table.flat th.sorted::after{content:" \25BE";color:var(--gold);} table.flat th.asc::after{content:" \25B4";color:var(--gold);}
table.flat td{padding:8px 12px;text-align:right;border-bottom:1px solid rgba(255,255,255,.05);} table.flat tr:hover td{background:rgba(255,255,255,.02);}
.pos{color:var(--good);} .neg{color:var(--bad);}
/* ---- calibration plot ---- */
.calib{max-width:520px;} .calib svg{width:100%;height:auto;display:block;}
/* ---- pipeline / svg diagram ---- */
.diagram{overflow-x:auto;border:1px solid var(--border);border-radius:14px;background:var(--panel2);padding:14px;} .diagram svg{display:block;min-width:720px;}
/* ---- doors (index) ---- */
.doors{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:8px;} .door{border-radius:16px;border:1px solid var(--border);background:var(--panel);padding:22px;display:flex;flex-direction:column;gap:8px;transition:border-color .15s,transform .15s;} .door:hover{border-color:var(--a);transform:translateY(-2px);} .door .t{font:400 26px 'Anton';text-transform:uppercase;} .door .d{font:400 13px/1.55 'Space Grotesk';color:var(--sub);} .door .go{margin-top:auto;font:700 12px 'Space Grotesk';color:var(--a);letter-spacing:.04em;text-transform:uppercase;}
.big3{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;text-align:center;} .big3 .n{font:700 40px 'Saira Condensed';line-height:1;} .big3 .l{font:500 12px 'Space Grotesk';color:var(--sub);margin-top:4px;}
.callout{border:1px solid var(--gold);border-radius:14px;background:color-mix(in srgb,var(--gold) 6%,var(--panel));padding:16px 18px;} .callout .read{border-color:var(--gold);}
footer{margin-top:44px;font:500 12px/1.7 'Space Grotesk';color:var(--sub);} footer a{color:var(--a);}
/* ---- per-audience motifs (one dark system, distinct accents/texture) ---- */
body.t-eng{--a:#3ddc84;--a2:#1f7a49;--aText:#04120a;background:radial-gradient(140% 55% at 50% 0%,color-mix(in srgb,#3ddc84 8%,var(--bg)) 0%,var(--bg) 50%),repeating-linear-gradient(0deg,transparent 0 27px,rgba(255,255,255,.02) 27px 28px),repeating-linear-gradient(90deg,transparent 0 27px,rgba(255,255,255,.02) 27px 28px);background-attachment:fixed;}
body.t-eng .hero h1,body.t-eng .sec h2{font-family:'JetBrains Mono';font-weight:700;text-transform:none;letter-spacing:-.02em;}
body.t-ds{--a:#8b7fff;--a2:#4b3fb0;--aText:#0b081c;--panel:#171826;--panelHi:#20223a;background:radial-gradient(140% 55% at 50% 0%,color-mix(in srgb,#8b7fff 10%,var(--bg)) 0%,var(--bg) 52%);background-attachment:fixed;}
body.t-bet{--a:#f0b429;--a2:#9c7414;--aText:#1a1204;--panel:#12140f;--panel2:#0b0d08;--panelHi:#1a1d12;background:var(--bg);}
body.t-bet .hero h1{font-family:'JetBrains Mono';font-weight:700;text-transform:none;}
body.t-fan .hero h1{font-size:clamp(46px,8vw,84px);}
@media(max-width:760px){.grid,.grid3,.doors,.big3{grid-template-columns:1fr;}}
"""

UTIL_JS = r"""
'use strict';
// Shared client helpers (FEEDBACK §9). No dependencies.
function fmt(v, dec){ if(v===null||v===undefined||v==='') return '—';
  if(typeof v!=='number') v=Number(v); if(!isFinite(v)) return '—';
  dec = Math.min(dec===undefined?3:dec, 3);
  if(Number.isInteger(v)) return String(v);
  return v.toFixed(dec).replace(/\.?0+$/,''); }
function pct(v, dec){ return fmt(v*100, dec===undefined?1:dec)+'%'; }
// American odds from a probability (FEEDBACK §5.3-1). Explicit sign.
function toAmerican(p){ if(p<=0||p>=1) return '—';
  const v = p>=0.5 ? Math.round(-100*p/(1-p)) : Math.round(100*(1-p)/p);
  return (v>0?'+':'')+v; }
// team color with the SAME contrast fallback as build_site.py team_fill()
const _PANEL_L = 0.006; // luminance of #13161e (precomputed; overridden per theme is not needed for fills)
function _lum(hex){ const c=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(x=>x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4)); return 0.2126*c[0]+0.7152*c[1]+0.0722*c[2]; }
function _contrast(hex){ const a=Math.max(_lum(hex),_PANEL_L), b=Math.min(_lum(hex),_PANEL_L); return (a+0.05)/(b+0.05); }
function teamFill(id){ const m=(typeof TEAM_META!=='undefined')&&TEAM_META[id]; if(!m) return 'var(--a)'; return _contrast(m.primary)>=1.6 ? m.primary : m.secondary; }
function teamAbbr(id){ const m=(typeof TEAM_META!=='undefined')&&TEAM_META[id]; return m?m.abbr:'?'; }
function teamName(id){ const m=(typeof TEAM_META!=='undefined')&&TEAM_META[id]; return m?m.name:''; }
function monogram(id){ const m=(typeof TEAM_META!=='undefined')&&TEAM_META[id]; const bg=m?m.primary:'#333'; const ab=m?m.abbr:'?';
  return `<span class="mono-chip" style="background:${bg}" title="${m?m.name:''}">${ab}</span>`; }
// hamburger
function toggleNav(btn){ const l=document.getElementById('navlinks'); if(l) l.classList.toggle('open'); }
// generic click-to-sort for table.flat (data-sort attr = numeric value; default sort desc, toggles)
function makeSortable(table){
  const ths=[...table.tHead.rows[0].cells];
  ths.forEach((th,ci)=>{ if(th.dataset.nosort!==undefined) return; th.tabIndex=0; th.setAttribute('role','button');
    const go=()=>{ const asc=th.classList.contains('sorted')&&!th.classList.contains('asc');
      ths.forEach(t=>t.classList.remove('sorted','asc'));
      th.classList.add('sorted'); if(asc) th.classList.add('asc');
      const rows=[...table.tBodies[0].rows];
      rows.sort((r1,r2)=>{ const a=parseFloat(r1.cells[ci].dataset.v??r1.cells[ci].textContent), b=parseFloat(r2.cells[ci].dataset.v??r2.cells[ci].textContent);
        const av=isNaN(a)?r1.cells[ci].textContent:a, bv=isNaN(b)?r2.cells[ci].textContent:b;
        return (av<bv?-1:av>bv?1:0)*(asc?1:-1); });
      rows.forEach(r=>table.tBodies[0].appendChild(r)); };
    th.addEventListener('click',go); th.addEventListener('keydown',e=>{ if(e.key==='Enter'||e.key===' '){e.preventDefault();go();} }); });
}
"""


def teams_js() -> str:
    rows = [f'  {tid}:{{abbr:"{m[0]}",name:"{m[1]}",primary:"{m[2]}",secondary:"{m[3]}"}}'
            for tid, m in sorted(TEAM_META.items())]
    return "'use strict';\nconst TEAM_META = {\n" + ",\n".join(rows) + "\n};\n"


# ------------------------------------------------------------------ shared chrome
NAVITEMS = [("fan", "Fans"), ("betting", "Betting"), ("data-eng", "Data Eng"),
            ("data-science", "Data Science"), ("compare", "Compare"),
            ("simulator", "Simulator"), ("glossary", "Stat Guide")]


def nav(active: str) -> str:
    def link(p: str, label: str) -> str:
        cls = ' class="active"' if p == active else ""
        return f'<a href="{p}.html"{cls}>{label}</a>'
    links = "".join(link(p, label) for p, label in NAVITEMS)
    return (f'<div class="nav"><div class="in">'
            f'<a class="brand" href="index.html"><span class="bar"></span>'
            f'<span class="txt">DIAMOND<span style="color:var(--a);">IQ</span></span></a>'
            f'<button class="hamb" aria-label="Menu" aria-expanded="false" '
            f'onclick="this.setAttribute(\'aria-expanded\',this.getAttribute(\'aria-expanded\')===\'true\'?\'false\':\'true\');toggleNav(this)">Menu</button>'
            f'<div class="navlinks" id="navlinks">{links}'
            f'<a class="ext" href="{GH}" target="_blank" rel="noopener">GitHub ↗</a>'
            f'</div></div></div>')


def head(title: str, desc: str, active: str, theme: str = "") -> str:
    body_cls = f' class="{theme}"' if theme else ""
    return (f'<!doctype html><html lang="en"><head>'
            f'<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{title}</title><meta name="description" content="{desc}">'
            f'<meta property="og:title" content="{title}"><meta property="og:description" content="{desc}">'
            f'<meta property="og:type" content="website"><meta name="twitter:card" content="summary">'
            f'<link rel="preconnect" href="https://fonts.googleapis.com">'
            f'<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            f'<link href="{FONTS}" rel="stylesheet"><link href="assets/site.css" rel="stylesheet">'
            f'</head><body{body_cls}>{nav(active)}<div class="wrap">')


def prov() -> str:
    p = DATA["provenance"]
    return (f'<div class="prov">Data: {p["seasons"][0]}–{p["seasons"][-1]} regular seasons '
            f'· final (through {p["through"]}) · Pythagorean exponent {fmt(p["pythag_exp"])} '
            f'(fitted) · seed {p["seed"]} where simulated</div>')


FOOT = (f'<footer>Built from the <a href="{GH}">mlb-analytics</a> warehouse '
        f'({DATA["meta"]["n_pitches"]:,} pitches, {DATA["meta"]["seasons"][0]}–{DATA["meta"]["seasons"][-1]}). '
        f'Data: MLB Advanced Media (statsapi / Baseball Savant) — individual, non-commercial, '
        f'non-bulk use; raw data not redistributed. Player crosswalk: Chadwick Bureau (ODC-By). '
        f'Draft: Wikipedia (CC BY-SA). Aggregates and code only.</footer>')


def scripts(*extra: str) -> str:
    """Shared JS includes + optional page inline scripts."""
    tags = '<script src="assets/teams.js"></script><script src="assets/util.js"></script>'
    return tags + "".join(extra)


def _write(name: str, body: str, *js: str) -> None:
    (DOCS / name).write_text(body + FOOT + scripts(*js) + "\n</div></body></html>", encoding="utf-8")


# ------------------------------------------------------------------ pages
PAGES: dict = {}  # page filename -> builder fn; filled as builders are defined below


def mono_py(team_id: int) -> str:
    """Server-side team monogram chip (for no-JS prerender)."""
    m = TEAM_META.get(int(team_id))
    bg, ab, nm = (m[2], m[0], m[1]) if m else ("#333", "?", "")
    return f'<span class="mono-chip" style="background:{bg}" title="{nm}">{ab}</span>'


def dist_html(d: dict, direction: str) -> str:
    """Server-rendered distribution bar with named leader/trailer (leader=green, not red)."""
    if not d:
        return ""
    span = (d["max"] - d["min"]) or 1
    med_pct = (d["med"] - d["min"]) / span * 100
    hi = direction == "high"
    lead, trail = (d["hi"], d["lo"]) if hi else (d["lo"], d["hi"])
    return (f'<div class="dist"><div class="track"><div class="med" style="left:{med_pct:.1f}%"></div></div>'
            f'<div class="ends"><span>min {fmt(d["min"])}</span><span>median {fmt(d["med"])}</span><span>max {fmt(d["max"])}</span></div>'
            f'<div class="ex"><span class="chip"><span class="dot" style="background:var(--good)"></span>'
            f'Leader <b>{lead["abbr"]} {fmt(lead["val"])}</b></span>'
            f'<span class="chip"><span class="dot" style="background:var(--sub)"></span>'
            f'Trailer <b>{trail["abbr"]} {fmt(trail["val"])}</b></span></div></div>')


# (anchor, name, direction, dist_key, definition, how-to-read). Model refs -> data-science anchors.
GLOSSARY = [
    ("Rate stats", [
        ("ops", "OPS", "high", "ops", "On-base plus slugging — how often you reach base plus how much power you hit for.",
         "League average is ~.720; .900+ is All-Star, a full-season 1.000+ is an MVP line."),
        ("k_pct", "K% (strikeout rate)", "low", "k_pct", "Share of plate appearances ending in a strikeout.",
         'The single most <b>stable</b> hitter skill year to year (<a href="data-science.html#m1">M1</a>). ~22% is average; elite contact hitters near 10%, sluggers push 30%+.'),
        ("bb_pct", "BB% (walk rate)", "high", "bb_pct", "Share of plate appearances ending in a walk — plate discipline.",
         'Also very stable year to year (<a href="data-science.html#m1">M1</a>). ~8% average; the best eyes draw walks 15%+.'),
        ("babip", "BABIP", "high", "babip", "Batting average on balls in play — how often batted balls (not HR, not strikeouts) fall for hits.",
         'Mostly <b>noise</b> (<a href="data-science.html#m1">M1</a>, <a href="data-science.html#m7">M7</a>): ~.300 average with big luck-driven swings. A high BABIP rarely repeats.'),
    ]),
    ("Statcast / expected", [
        ("xwoba", "xwOBA", "high", None, "Expected weighted on-base average — the value a batted ball 'should' produce given exit velocity and launch angle.",
         'Separates real contact quality from batted-ball luck; we rebuild the core relationship in <a href="data-science.html#m2">M2/M3</a>.'),
        ("exitangle", "Exit velocity / launch angle", "high", None, "How hard (mph) and at what vertical angle (degrees) a ball leaves the bat.",
         'Barrels live near ~98+ mph and 25–30°. Value is concave in angle — an optimal window (<a href="data-science.html#m2">M2</a>).'),
        ("arsenal", "Pitch arsenal / stuff", "high", None, "A pitcher's mix of pitch types and their velocity, spin, and movement.",
         '<a href="data-science.html#m6">M6</a> clusters pitchers into archetypes (power, finesse, spin) from these features.'),
    ]),
    ("Run values", [
        ("re24", "RE24 / run expectancy", "high", None, "Expected runs from now to the end of the inning, for each of the 24 base-out states.",
         'The backbone of modern value stats. Bases empty, 0 outs ≈ <b>0.5</b> runs; loaded, 0 outs ≈ 2.3. Built from our own play-by-play.'),
        ("linweights", "Linear weights / run value", "high", None, "The average run value of an event (single, walk, HR, out…), derived from RE24.",
         "HR ≈ <b>+1.4</b> runs, single ≈ +0.47, walk ≈ +0.31, strikeout ≈ −0.27 — the currency of wOBA, framing, and count value."),
        ("framing", "Framing runs", "high", None, "Runs a catcher adds by getting borderline takes called strikes more than expected from location.",
         'Elite framers ≈ +10 to +20 runs a season (<a href="data-science.html#m4">M4</a>); real, measurable, invisible on TV.'),
    ]),
    ("Team & game", [
        ("win_pct", "Win %", "high", "win_pct", "Fraction of games a team wins.",
         "Home teams win ~54% of games — the baseline any prediction model must beat."),
        ("pythag", "Pythagorean win %", "high", None, "Expected win rate from runs scored and allowed: RS^k / (RS^k + RA^k).",
         'Run differential predicts a team\'s record better than its actual record does. We fit the exponent (<a href="data-science.html#b1">B1</a>) at ~1.73.'),
        ("luck", "Luck (W − pythW)", None, None, "Actual wins minus Pythagorean-expected wins — over/under-performance vs. run differential.",
         "Big luck rarely repeats — it's the gap between a team's record and what its runs earned."),
        ("winprob", "Win probability", "high", None, "The game model's estimated chance the home team wins, from leakage-safe pre-game form.",
         'On the sealed 2025 holdout it beats a home-field baseline on Brier — a small real edge (<a href="data-science.html#game">the game model</a>).'),
    ]),
    ("Concepts", [
        ("stability", "Metric stability", "high", None, "How repeatable a stat is year to year. Skills stabilize fast; luck-driven stats don't.",
         'K% and BB% correlate ~0.8 year to year (skill); BABIP ~0.3 (noise) — <a href="data-science.html#m1">M1</a>.'),
        ("shrinkage", "Regression to the mean / ICC", "high", None, "Extreme performances move back toward average; ICC is the share of a stat that is real skill vs. noise.",
         'BABIP\'s ICC is ~0.27 (<a href="data-science.html#m7">M7</a>) — mostly noise, so we shrink each hitter\'s BABIP toward the mean.'),
        ("parity", "R↔Python parity gate", None, None, "Every model is built twice — R and Python — and the build fails unless they agree.",
         'Proof the numbers aren\'t a one-tool artifact. Three tiers (<a href="data-eng.html#parity">exact / label-invariant / distributional</a>).'),
    ]),
]


def build_glossary() -> None:
    cards_html = []
    for gname, stats in GLOSSARY:
        cs = []
        for anchor, name, direction, dkey, define, read in stats:
            dbadge = ('<span class="badge good">Higher is better</span>' if direction == "high"
                      else '<span class="badge gold">Lower is better</span>' if direction == "low" else "")
            dist = dist_html(DATA["glossary"].get(dkey), direction) if dkey else ""
            hay = f"{name} {define} {read}".lower().replace('"', "")
            cs.append(f'<div class="card gstat" id="{anchor}" data-hay="{hay}">'
                      f'<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">'
                      f'<span class="name">{name}</span>{dbadge}</div>'
                      f'<div class="def">{define}</div>'
                      f'<div class="read"><b>How to read it:</b> {read}</div>{dist}</div>')
        cards_html.append(f'<div class="sec" data-group><h2>{gname}</h2><span class="line"></span></div>'
                          f'<div class="grid" data-group>{"".join(cs)}</div>')
    body = head("DIAMONDIQ — Stat Guide",
                "A plain-English data dictionary for every MLB metric on the DIAMONDIQ dashboard.",
                "glossary")
    body += ('<div class="hero"><div class="eyebrow">Data Dictionary</div><h1>Stat Guide</h1>'
             '<p>Every metric on the dashboard in plain English — what it measures, how to read it, '
             'and where the field landed.</p></div>' + prov())
    body += ('<div class="toolbar"><label class="search" for="q"><span aria-hidden="true">Search</span>'
             '<span class="vh">Search stats</span>'
             '<input id="q" type="text" placeholder="Search a stat — xwOBA, BABIP, framing, RE24…" autocomplete="off"></label>'
             '<span class="count" id="count" aria-live="polite"></span></div>')
    body += f'<div id="glossary">{"".join(cards_html)}</div>'
    js = """<script>
(function(){const q=document.getElementById('q'),count=document.getElementById('count');
 const cards=[...document.querySelectorAll('.gstat')];
 function run(f){f=(f||'').trim().toLowerCase();let shown=0;
   cards.forEach(c=>{const ok=!f||c.dataset.hay.includes(f);c.style.display=ok?'':'none';if(ok)shown++;});
   document.querySelectorAll('[data-group]').forEach(g=>{});
   count.textContent=f?shown+' of '+cards.length+' stats':cards.length+' stats';}
 q.addEventListener('input',e=>run(e.target.value));run('');
 if(location.hash){const el=document.querySelector(location.hash);if(el)el.scrollIntoView();}})();
</script>"""
    _write("glossary.html", body, js)


PAGES["glossary.html"] = build_glossary


# rows: (key, label, decimals, higher_is_better). rundiff computed on the fly.
CMP_ROWS = [("win_pct", "Win %", 3, True), ("w", "Wins", 0, True), ("rs", "Runs scored", 0, True),
            ("ra", "Runs allowed", 0, False), ("rundiff", "Run differential", 0, True),
            ("pyth", "Pythagorean win %", 3, True), ("luck", "Luck (W − pythW)", 1, True)]


def _cmp_val(t: dict, key: str):
    return t["rs"] - t["ra"] if key == "rundiff" else t[key]


def _cmp_row_py(a: dict, b: dict, key: str, label: str, dec: int, hi: bool) -> str:
    av, bv = _cmp_val(a, key), _cmp_val(b, key)
    mx = max(abs(av), abs(bv)) or 1
    aw = "win" if (av > bv if hi else av < bv) else ""
    bw = "win" if (bv > av if hi else bv < av) else ""
    ca, cb = team_fill(a["team_id"]), team_fill(b["team_id"])
    arrow = "◀" if aw else ("▶" if bw else "=")
    return (f'<div class="cmp"><div class="lab">{label}</div>'
            f'<div class="bar"><div class="fill r" style="width:{abs(av)/mx*100:.0f}%;background:linear-gradient(270deg,{ca},var(--panel2))"></div>'
            f'<div class="v {aw}" style="left:8px">{fmt(av, dec)}</div></div>'
            f'<div class="mid">{arrow}</div>'
            f'<div class="bar"><div class="fill l" style="width:{abs(bv)/mx*100:.0f}%;background:linear-gradient(90deg,{cb},var(--panel2))"></div>'
            f'<div class="v {bw}" style="right:8px">{fmt(bv, dec)}</div></div></div>')


def _h2h_line(a: dict, b: dict) -> str:
    season = str(a["season"])
    lo, hi_ = sorted((int(a["team_id"]), int(b["team_id"])))
    rec = DATA["h2h"].get(season, {}).get(f"{lo}-{hi_}")
    if not rec:
        return '<div class="kv" style="justify-content:center"><span>These teams did not meet this season.</span></div>'
    lo_w, hi_w = rec["aw"], rec["bw"]
    aw, bw = (lo_w, hi_w) if int(a["team_id"]) == lo else (hi_w, lo_w)
    lead = a if aw > bw else b if bw > aw else None
    tag = f'{abbr(lead["team_id"])} won the series {max(aw, bw)}–{min(aw, bw)}' if lead else f'split {aw}–{bw}'
    return f'<div class="kv" style="justify-content:center"><span>Season series ({season}): <b>{tag}</b> ({aw + bw} games)</span></div>'


def _matchup_html(a: dict, b: dict) -> str:
    header = (f'<div class="cmp"><div class="lab" style="font:400 20px \'Anton\';color:var(--text)">'
              f'{mono_py(a["team_id"])} {a["team_name"]} ({fmt(a["w"])}-{fmt(a["l"])}) '
              f'&nbsp;vs&nbsp; {b["team_name"]} ({fmt(b["w"])}-{fmt(b["l"])}) {mono_py(b["team_id"])}</div></div>')
    rows = "".join(_cmp_row_py(a, b, *r) for r in CMP_ROWS)
    return f'<div class="card">{header}{rows}{_h2h_line(a, b)}</div>'


def build_compare() -> None:
    teams = DATA["teams"]
    seasons = sorted({t["season"] for t in teams})
    latest = [t for t in teams if t["season"] == seasons[-1]]
    a0, b0 = latest[0], latest[1]
    body = head("DIAMONDIQ — Compare Teams",
                "Side-by-side MLB team comparison: record, run environment, Pythagorean luck, and "
                "head-to-head series for any two teams in a season.", "compare")
    body += ('<div class="hero"><div class="eyebrow">Side by side</div><h1>Compare Teams</h1>'
             '<p>Pick a season and two teams. Record, runs, run differential, the Pythagorean win '
             'rate their runs imply, luck (wins above/below that), and their head-to-head series. '
             'Each team fills its bar in its own colors; the better value is highlighted gold.</p></div>' + prov())
    body += ('<div class="toolbar">'
             '<label class="vh" for="season">Season</label><select id="season"></select>'
             '<label class="vh" for="ta">First team</label><select id="ta"></select>'
             '<span class="mid" style="color:var(--sub);font:700 13px \'Anton\'">VS</span>'
             '<label class="vh" for="tb">Second team</label><select id="tb"></select></div>')
    body += f'<div id="body" style="margin-top:16px">{_matchup_html(a0, b0)}</div>'
    js = ("""<script>const TEAMS=""" + json.dumps(teams) + """;const H2H=""" + json.dumps(DATA["h2h"]) + """;
(function(){const ROWS=[['win_pct','Win %',3,true],['w','Wins',0,true],['rs','Runs scored',0,true],
 ['ra','Runs allowed',0,false],['rundiff','Run differential',0,true],['pyth','Pythagorean win %',3,true],
 ['luck','Luck (W − pythW)',1,true]];
 const val=(t,k)=>k==='rundiff'?t.rs-t.ra:t[k];
 const selS=document.getElementById('season'),selA=document.getElementById('ta'),selB=document.getElementById('tb'),out=document.getElementById('body');
 const seasons=[...new Set(TEAMS.map(t=>t.season))].sort((a,b)=>a-b);
 seasons.forEach(s=>selS.add(new Option(s,s)));selS.value=seasons[seasons.length-1];
 function fill(){const s=+selS.value;const ts=TEAMS.filter(t=>t.season===s).sort((a,b)=>a.team_name.localeCompare(b.team_name));
   [selA,selB].forEach(sel=>{const cur=sel.value;sel.innerHTML='';ts.forEach(t=>sel.add(new Option(t.team_name,t.team_name)));if([...sel.options].some(o=>o.value===cur))sel.value=cur;});
   selA.value=ts[0].team_name;selB.value=ts[1].team_name;}
 function row(a,b,k,label,dec,hi){const av=val(a,k),bv=val(b,k),mx=Math.max(Math.abs(av),Math.abs(bv))||1;
   const aw=(hi?av>bv:av<bv)?'win':'',bw=(hi?bv>av:bv<av)?'win':'';const ca=teamFill(a.team_id),cb=teamFill(b.team_id);
   const arr=aw?'◀':(bw?'▶':'=');
   return `<div class="cmp"><div class="lab">${label}</div>
     <div class="bar"><div class="fill r" style="width:${Math.abs(av)/mx*100}%;background:linear-gradient(270deg,${ca},var(--panel2))"></div><div class="v ${aw}" style="left:8px">${fmt(av,dec)}</div></div>
     <div class="mid">${arr}</div>
     <div class="bar"><div class="fill l" style="width:${Math.abs(bv)/mx*100}%;background:linear-gradient(90deg,${cb},var(--panel2))"></div><div class="v ${bw}" style="right:8px">${fmt(bv,dec)}</div></div></div>`;}
 function h2h(a,b){const s=String(a.season);const lo=Math.min(a.team_id,b.team_id),hi=Math.max(a.team_id,b.team_id);
   const r=(H2H[s]||{})[lo+'-'+hi];if(!r)return '<div class="kv" style="justify-content:center"><span>These teams did not meet this season.</span></div>';
   const aw=a.team_id===lo?r.aw:r.bw,bw=a.team_id===lo?r.bw:r.aw;const lead=aw>bw?a:bw>aw?b:null;
   const tag=lead?`${teamAbbr(lead.team_id)} won the series ${Math.max(aw,bw)}–${Math.min(aw,bw)}`:`split ${aw}–${bw}`;
   return `<div class="kv" style="justify-content:center"><span>Season series (${s}): <b>${tag}</b> (${aw+bw} games)</span></div>`;}
 function render(){const s=+selS.value;const A=TEAMS.find(t=>t.season===s&&t.team_name===selA.value),B=TEAMS.find(t=>t.season===s&&t.team_name===selB.value);
   if(!A||!B){out.innerHTML='';return;}
   let h=`<div class="card"><div class="cmp"><div class="lab" style="font:400 20px 'Anton';color:var(--text)">${monogram(A.team_id)} ${A.team_name} (${A.w}-${A.l}) &nbsp;vs&nbsp; ${B.team_name} (${B.w}-${B.l}) ${monogram(B.team_id)}</div></div>`;
   ROWS.forEach(r=>h+=row(A,B,...r));h+=h2h(A,B)+'</div>';out.innerHTML=h;}
 [selS,selA,selB].forEach(el=>el.addEventListener('change',()=>{if(el===selS)fill();render();}));
 fill();render();})();
</script>""")
    _write("compare.html", body, js)


PAGES["compare.html"] = build_compare


def _sim_srow_py(t: dict) -> str:
    col = team_fill(t["team_id"])
    dot = ('<span class="pdot" title="Made the 2025 playoffs"></span>' if t["made_playoffs_actual"]
           else '<span class="pdot off" title="Missed the 2025 playoffs"></span>')
    return (f'<div class="srow" style="border-left-color:{col}">'
            f'<div class="steam">{dot}{mono_py(t["team_id"])}<b>{t["abbr"]}</b>'
            f'<span class="srec">{fmt(t["actual_w"])}-{fmt(t["actual_l"])}</span></div>'
            f'<div class="sproj">{fmt(t["proj_wins"], 1)}<span class="srange">{fmt(t["p10"], 1)}–{fmt(t["p90"], 1)}</span></div>'
            f'<div class="obar"><div class="ofill" style="width:{t["playoff_odds"]*100:.0f}%;background:{col}"></div>'
            f'<span class="oval" data-p="{t["playoff_odds"]}">{fmt(t["playoff_odds"]*100, 1)}%</span></div></div>')


def build_simulator() -> None:
    body = head("DIAMONDIQ — Season Simulator",
                "Monte-Carlo playoff odds: 10,000 simulated 2025 seasons from the game model's "
                "leakage-safe per-game win probabilities over the real schedule.", "simulator")
    if not SIM:
        body += '<div class="hero"><h1>Season Simulator</h1><p>Run season_sim.py first.</p></div>'
        _write("simulator.html", body)
        return
    body += (f'<div class="hero"><div class="eyebrow">Monte Carlo</div><h1>Season Simulator</h1>'
             f'<p>Ten thousand simulated 2025 seasons. Every one of the {SIM["n_games"]:,} games is a '
             f'weighted coin-flip using the game model\'s leakage-safe win probability, and we tally '
             f'wins, division titles, and playoff berths.</p></div>' + prov())
    body += (f'<div class="grid3">'
             f'<div class="card"><div class="kv"><span>Projected vs. actual wins</span></div>'
             f'<div class="stat">{fmt(SIM["corr_proj_actual"])}<span class="u">r</span></div>'
             f'<div class="read">Rank-order recovery of the real standings from forecast alone.</div></div>'
             f'<div class="card"><div class="kv"><span>Playoff field identified</span></div>'
             f'<div class="stat">{SIM["top12_playoff_hits"]}<span class="u">/ 12</span></div>'
             f'<div class="read">Of the 12 highest-odds teams, how many actually reached October.</div></div>'
             f'<div class="card"><div class="kv"><span>Seasons simulated</span></div>'
             f'<div class="stat">{SIM["n_sim"] // 1000}<span class="u">K</span></div>'
             f'<div class="read">Fixed seed so the page is reproducible.</div></div></div>')
    body += (f'<div class="card callout" style="margin-top:16px"><div class="read"><b>Read it honestly:</b> '
             f'projected win totals compress toward .500 because the game model is deliberately '
             f'conservative — MLB games really are near coin-flips (AUC ~0.55). So even a weak team '
             f'keeps some playoff hope and the best teams don\'t run away. The <b>ordering</b>, though, '
             f'tracks reality closely (r = {fmt(SIM["corr_proj_actual"])}). That gap between "confident '
             f'spread" and "correct ranking" is the point.</div></div>')
    body += ('<div class="toolbar"><button id="viewbtn" class="hamb" style="display:block">Show flat table</button>'
             '<button id="oddsbtn" class="hamb" style="display:block">Show American odds</button>'
             '<div class="legend"><span><span class="pdot"></span>Made 2025 playoffs</span>'
             '<span><span class="pdot off"></span>Missed</span>'
             '<span>Bar = playoff odds · row color = team</span></div></div>')
    # prerendered division cards (default, no-JS)
    divs = ""
    for lg, lgname in (("AL", "American League"), ("NL", "National League")):
        divs += f'<div class="sec"><h2>{lgname}</h2><span class="line"></span></div><div class="grid3">'
        for dv in ("East", "Central", "West"):
            ts = sorted((t for t in SIM["teams"] if t["league"] == lg and t["division"] == dv),
                        key=lambda x: -x["playoff_odds"])
            rows = "".join(_sim_srow_py(t) for t in ts)
            divs += (f'<div class="card"><div class="name" style="font-size:18px;color:var(--a)">{lg} {dv}</div>'
                     f'<div class="shdr"><span>Team</span><span>Proj W (80% range)</span><span>Playoff odds</span></div>{rows}</div>')
        divs += '</div>'
    body += f'<div id="divview">{divs}</div><div id="tblview" style="display:none;margin-top:16px"></div>'
    js = ("""<script>const SIM=""" + json.dumps(SIM) + """;
(function(){let tbl=false,amer=false;
 const divview=document.getElementById('divview'),tblview=document.getElementById('tblview');
 const vb=document.getElementById('viewbtn'),ob=document.getElementById('oddsbtn');
 function oddsTxt(p){return amer?toAmerican(p):fmt(p*100,1)+'%';}
 function refreshOvals(){document.querySelectorAll('#divview .oval').forEach(o=>o.textContent=oddsTxt(+o.dataset.p));}
 function buildTable(){const cols=[['abbr','Team',0],['proj_wins','Proj W',1],['range','80% range',0],['playoff_odds','Playoff',0],['div_odds','Division',0],['actual_w','Actual W',0]];
   let h='<div class="tblwrap"><table class="flat"><thead><tr>';
   cols.forEach((c,i)=>h+=`<th${i===2?' data-nosort':''}>${c[1]}</th>`);h+='</tr></thead><tbody>';
   SIM.teams.forEach(t=>{h+=`<tr><td data-v="${t.abbr}">${monogram(t.team_id)} ${t.abbr}${t.made_playoffs_actual?' <span class="pdot" title="made playoffs"></span>':''}</td>`
     +`<td data-v="${t.proj_wins}">${fmt(t.proj_wins,1)}</td><td>${fmt(t.p10,1)}–${fmt(t.p90,1)}</td>`
     +`<td data-v="${t.playoff_odds}">${oddsTxt(t.playoff_odds)}</td><td data-v="${t.div_odds}">${oddsTxt(t.div_odds)}</td>`
     +`<td data-v="${t.actual_w}">${t.actual_w}-${t.actual_l}</td></tr>`;});
   h+='</tbody></table></div>';tblview.innerHTML=h;makeSortable(tblview.querySelector('table'));}
 vb.addEventListener('click',()=>{tbl=!tbl;if(tbl)buildTable();tblview.style.display=tbl?'block':'none';divview.style.display=tbl?'none':'block';vb.textContent=tbl?'Show division cards':'Show flat table';});
 ob.addEventListener('click',()=>{amer=!amer;refreshOvals();if(tbl)buildTable();ob.textContent=amer?'Show percent odds':'Show American odds';});})();
</script>""")
    _write("simulator.html", body, js)


PAGES["simulator.html"] = build_simulator


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    (DOCS / ".nojekyll").write_text("")
    (ASSETS / "site.css").write_text(CSS, encoding="utf-8")
    (ASSETS / "util.js").write_text(UTIL_JS, encoding="utf-8")
    (ASSETS / "teams.js").write_text(teams_js(), encoding="utf-8")
    built = []
    for name, fn in PAGES.items():
        fn()
        built.append(name)
    print(json.dumps({"stage": "dashboard", "event": "built", "pages": built}))


if __name__ == "__main__":
    main()
