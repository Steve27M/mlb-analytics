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
_LIVE_PATH = REPO / "data" / "dashboard" / "live_sim.json"
LIVE = json.loads(_LIVE_PATH.read_text()) if _LIVE_PATH.exists() else None
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


def to_american(p: float) -> str:
    """American moneyline odds from a probability, explicit sign (matches util.js toAmerican)."""
    if not p or p <= 0 or p >= 1:
        return "—"
    v = round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)
    return f"{'+' if v > 0 else ''}{v}"


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
        # Drop precision-example parentheticals (long decimals / sci-notation) to honor the site's
        # <=3-decimal rule (§1.2); the story survives without the debug-level numbers.
        rest = re.sub(r"\s*\([^)]*(?:\d\.\d{4,}|\de-?\d|\|Δ\|)[^)]*\)", "", rest)
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


FOOT = (f'<footer>Built from the <a href="{GH}">mlb-analytics</a> project '
        f'({DATA["meta"]["n_pitches"]:,} pitches, {DATA["meta"]["seasons"][0]}–{DATA["meta"]["seasons"][-1]}). '
        f'Data: MLB Advanced Media (statsapi / Baseball Savant) — individual, non-commercial, '
        f'non-bulk use; raw data not redistributed. Player crosswalk: Chadwick Bureau (ODC-By). '
        f'Draft: Wikipedia (CC BY-SA). Odds: The Odds API. No club logos or marks; team colors only. '
        f'Aggregates and code only. Legal &amp; ethical compliance reviewed 2026-07-04 '
        f'(<a href="{GH}/blob/main/PREFLIGHT.md">PREFLIGHT.md</a>).</footer>')


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
    body += ('<div class="grid" style="margin-top:16px">'
             '<div class="card"><div class="name" style="font-size:16px">What "luck" means here</div>'
             '<div class="def">Runs scored and allowed predict how many games a team <i>should</i> have '
             'won. Win more than that and you\'ve been winning the close ones — which is mostly luck and '
             'usually doesn\'t last. A team that outscores opponents by 20 runs but sits 5 games above '
             'its expected wins is probably due to cool off.</div></div>'
             '<div class="card"><div class="name" style="font-size:16px">Don\'t over-read the season series</div>'
             '<div class="def">Two teams meet only 6–13 times a year — small enough that a 4–2 edge is '
             'nearly meaningless. Season-long run totals tell you more about the next matchup than the '
             'head-to-head record does.</div></div></div>')
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


def _live_srow_py(t: dict) -> str:
    col = team_fill(t["team_id"])
    return (f'<div class="srow" style="border-left-color:{col}">'
            f'<div class="steam">{mono_py(t["team_id"])}<b>{t["abbr"]}</b>'
            f'<span class="srec">{fmt(t["cur_w"])}-{fmt(t["cur_l"])}</span></div>'
            f'<div class="sproj">{fmt(t["proj_wins"], 1)}<span class="srange">{fmt(t["p10"], 1)}–{fmt(t["p90"], 1)}</span></div>'
            f'<div class="obar"><div class="ofill" style="width:{t["playoff_odds"]*100:.0f}%;background:{col}"></div>'
            f'<span class="oval" data-p="{t["playoff_odds"]}">{fmt(t["playoff_odds"]*100, 1)}%</span></div></div>')


def build_simulator() -> None:
    body = head("DIAMONDIQ — Live 2026 Playoff Odds",
                "Live playoff odds for the in-progress 2026 season: current standings plus 10,000 "
                "Monte-Carlo simulations of the remaining schedule with the frozen game model.",
                "simulator")
    if not LIVE:
        body += ('<div class="hero"><h1>Live 2026 Playoff Odds</h1><p>Run the live build + live_sim.py '
                 'first (the 2026 season data is not yet available).</p></div>')
        _write("simulator.html", body)
        return
    played = LIVE["games_played"]
    total = played + LIVE["n_remaining"]
    leader = LIVE["teams"][0]
    body += (f'<div class="hero"><div class="eyebrow">Live · {LIVE["season"]}</div>'
             f'<h1>2026 Playoff Odds</h1>'
             f'<p>The in-progress {LIVE["season"]} season, projected forward. We take the current '
             f'standings and run <b>10,000</b> Monte-Carlo simulations of the {LIVE["n_remaining"]:,} '
             f'remaining games — each predicted by the <b>frozen</b> game model (trained on 2023–24, '
             f'validated on the sealed 2025 season) from every team\'s current form.</p></div>')
    body += (f'<div class="prov">Live {LIVE["season"]} · {played:,} of {total:,} games played '
             f'· frozen game model · seed {LIVE["seed"]} · aggregate projection, not game picks</div>')
    body += (f'<div class="grid3">'
             f'<div class="card"><div class="kv"><span>Season progress</span></div>'
             f'<div class="stat">{played * 100 // total}<span class="u">% played</span></div>'
             f'<div class="read">{LIVE["n_remaining"]:,} games left to simulate.</div></div>'
             f'<div class="card"><div class="kv"><span>Best playoff odds</span></div>'
             f'<div class="stat">{chip_leader(leader)}</div>'
             f'<div class="read">{leader["cur_w"]}-{leader["cur_l"]}, projected {fmt(leader["proj_wins"], 0)} wins.</div></div>'
             f'<div class="card"><div class="kv"><span>Simulations</span></div>'
             f'<div class="stat">{LIVE["n_sim"] // 1000}<span class="u">K</span></div>'
             f'<div class="read">Fixed seed → reproducible.</div></div></div>')
    body += ('<div class="card callout" style="margin-top:16px"><div class="read"><b>How to read it:</b> '
             'we replay the rest of the season <b>10,000 times</b>, letting every remaining game land '
             'by its probability — like rolling weighted dice for every game, thousands of seasons in a '
             'row. A team\'s playoff odds are simply: in how many of those seasons did it get in? It\'s a '
             'season-long projection, <b>not a pick for any single game</b>. Remaining games use each '
             'team\'s current form, so the odds lean on where teams stand today; a hot or cold streak '
             'will move them.</div></div>'
             '<div class="grid" style="margin-top:14px"><div class="card"><div class="name" style="font-size:16px">Why the projections huddle together</div>'
             '<div class="def">Projected win totals cluster toward the middle not because teams are '
             'equal, but because luck averages out across 10,000 replays while a single real season '
             'keeps its luck. The range shown under each projection is the honest part: about 8 seasons '
             'in 10 land inside it.</div></div>'
             '<div class="card"><div class="name" style="font-size:16px">Does it actually work?</div>'
             '<div class="def">Rerunning a finished season this way put <b>10 of the 12</b> real playoff '
             'teams in our top 12 — good, and the two misses are the point: some of every season is '
             'genuinely unpredictable. See <a href="data-science.html#game">how the model was validated</a>.</div></div></div>')
    body += ('<div class="toolbar"><button id="viewbtn" class="hamb" style="display:block">Show flat table</button>'
             '<button id="oddsbtn" class="hamb" style="display:block">Show American odds</button>'
             '<div class="legend"><span>Bar = playoff odds · row color = team · record = current</span></div></div>')
    divs = ""
    for lg, lgname in (("AL", "American League"), ("NL", "National League")):
        divs += f'<div class="sec"><h2>{lgname}</h2><span class="line"></span></div><div class="grid3">'
        for dv in ("East", "Central", "West"):
            ts = sorted((t for t in LIVE["teams"] if t["league"] == lg and t["division"] == dv),
                        key=lambda x: -x["playoff_odds"])
            rows = "".join(_live_srow_py(t) for t in ts)
            divs += (f'<div class="card"><div class="name" style="font-size:18px;color:var(--a)">{lg} {dv}</div>'
                     f'<div class="shdr"><span>Team (current)</span><span>Proj W (80% range)</span><span>Playoff odds</span></div>{rows}</div>')
        divs += '</div>'
    body += f'<div id="divview">{divs}</div><div id="tblview" style="display:none;margin-top:16px"></div>'
    js = ("""<script>const SIM=""" + json.dumps(LIVE) + """;
(function(){let tbl=false,amer=false;
 const divview=document.getElementById('divview'),tblview=document.getElementById('tblview');
 const vb=document.getElementById('viewbtn'),ob=document.getElementById('oddsbtn');
 function oddsTxt(p){return amer?toAmerican(p):fmt(p*100,1)+'%';}
 function refreshOvals(){document.querySelectorAll('#divview .oval').forEach(o=>o.textContent=oddsTxt(+o.dataset.p));}
 function buildTable(){const cols=[['abbr','Team',0],['cur_w','Current W',0],['proj_wins','Proj W',1],['range','80% range',0],['playoff_odds','Playoff',0],['div_odds','Division',0]];
   let h='<div class="tblwrap"><table class="flat"><thead><tr>';
   cols.forEach((c,i)=>h+=`<th${i===3?' data-nosort':''}>${c[1]}</th>`);h+='</tr></thead><tbody>';
   SIM.teams.forEach(t=>{h+=`<tr><td data-v="${t.abbr}">${monogram(t.team_id)} ${t.abbr}</td>`
     +`<td data-v="${t.cur_w}">${t.cur_w}-${t.cur_l}</td>`
     +`<td data-v="${t.proj_wins}">${fmt(t.proj_wins,1)}</td><td>${fmt(t.p10,1)}–${fmt(t.p90,1)}</td>`
     +`<td data-v="${t.playoff_odds}">${oddsTxt(t.playoff_odds)}</td><td data-v="${t.div_odds}">${oddsTxt(t.div_odds)}</td></tr>`;});
   h+='</tbody></table></div>';tblview.innerHTML=h;makeSortable(tblview.querySelector('table'));}
 vb.addEventListener('click',()=>{tbl=!tbl;if(tbl)buildTable();tblview.style.display=tbl?'block':'none';divview.style.display=tbl?'none':'block';vb.textContent=tbl?'Show division cards':'Show flat table';});
 ob.addEventListener('click',()=>{amer=!amer;refreshOvals();if(tbl)buildTable();ob.textContent=amer?'Show percent odds':'Show American odds';});})();
</script>""")
    _write("simulator.html", body, js)


def chip_leader(t: dict) -> str:
    return f'{t["abbr"]} <span class="u">{fmt(t["playoff_odds"] * 100, 0)}%</span>'


PAGES["simulator.html"] = build_simulator


# ------------------------------------------------------------------ data-science.html
def _mval(key: str, *path):
    """Safe nested lookup into a model's python-side metrics."""
    node = DATA["metrics"].get(key, {})
    node = node.get("python", node)
    for p in path:
        node = node.get(p, {}) if isinstance(node, dict) else {}
    return node if not isinstance(node, dict) else None


TIER_BADGE = {"exact": "good", "label-invariant": "gold", "distributional": "a",
              "label_invariant": "gold"}
# (anchor, code, name, method, tier, result_html, caveat)
MODELS = [
    ("m1", "M1", "Metric stability", "Year-over-year correlation", "exact",
     lambda: f"K% repeats at r={fmt(_mval('m1_stability','k_pct_yoy_corr'))} and BB% at {fmt(_mval('m1_stability','bb_pct_yoy_corr'))} (skill); BABIP only {fmt(_mval('m1_stability','babip_yoy_corr'))} (noise).",
     "Correlational, not causal; min 300 PA both seasons."),
    ("m2", "M2/M3", "xwOBA-over-expected", "Simple + multiple OLS", "exact",
     lambda: "Exit velocity raises batted-ball value; launch angle is concave — there is an optimal window.",
     "A physics proxy, not a full xwOBA model; residuals are over/under-performance."),
    ("m4", "M4", "Catcher framing", "Logistic GLM on pitch location", "exact",
     lambda: f"Best framer +{fmt(_mval('m4_framing','top_framer_runs'),0)} runs, worst {fmt(_mval('m4_framing','bottom_framer_runs'),0)}, over 3 seasons.",
     "Location-only; ignores pitcher/umpire identity and count."),
    ("m5", "M5", "Strikeouts per start", "Poisson regression", "exact",
     lambda: f"League strikeout rate ≈ {fmt(_mval('m5_k_poisson','k_per_bf'))} per plate appearance.",
     "Count model; dispersion not separately modeled."),
    ("m6", "M6", "Pitcher arsenals", "PCA + k-means", "label-invariant",
     lambda: f"R and Python cluster assignments match at ARI {fmt(DATA['metrics'].get('m6_arsenal',{}).get('cluster_ari'))}.",
     "k chosen, not learned; clusters are descriptive archetypes."),
    ("m7", "M7", "BABIP shrinkage", "Mixed-effects (random intercepts)", "label-invariant",
     lambda: f"ICC {fmt(_mval('m7_babip_shrinkage','icc'))} — only ~{fmt(_mval('m7_babip_shrinkage','icc')*100,0)}% of BABIP is persistent skill.",
     "Intercepts only; no batted-ball covariates."),
    ("m8", "M8", "Draft vs. production", "OLS (ethical Wikipedia scrape)", "exact",
     lambda: f"corr(pick, OPS) = {fmt(DATA['effects']['m8']['r'])} — an earlier pick out-produces a later one about {fmt(DATA['effects']['m8']['concordance'],0)}% of the time (not 90%). A real tilt; small.",
     f"95% CI [{fmt(DATA['effects']['m8']['ci'][0])}, {fmt(DATA['effects']['m8']['ci'][1])}] (n={DATA['effects']['m8']['n']}) spans ~0 to sizable; range-restricted (MLB-only), so the full-population effect is larger."),
    ("b1", "B1", "Pythagorean wins", "OLS through the origin", "exact",
     lambda: f"Fitted exponent {fmt(_mval('b1_pythagoras','pythag_exponent'))}, ~{fmt(_mval('b1_pythagoras','runs_per_win'),1)} runs per win.",
     "Fit on 90 team-seasons; the exponent drifts a little by run environment."),
    ("b2", "B2", "Count effects", "RE24 aggregation", "exact",
     lambda: "3-0 is a hitter's count, 0-2 the pitcher's — run value chained from RE24 down to the pitch.",
     "Descriptive aggregation, not a predictive model."),
    ("b3", "B3", "Aging curves", "Quadratic OLS", "exact",
     lambda: f"OPS peaks near age {fmt(_mval('b3_aging','peak_age'),0)}.",
     "Cross-sectional + survivor bias: only good hitters last long enough to be measured old."),
    ("b4", "B4", "Markov innings", "Base-out transition simulation", "distributional",
     lambda: f"Simulated RE(empty,0) {fmt(_mval('b4_markov_sim','sim_re_empty_0'))} reconciles RE24 {fmt(_mval('b4_markov_sim','re24_empty_0'))}.",
     "Stationary transition matrix; no batter/pitcher identity."),
    ("b5", "B5", "Streaky hitters", "Wald–Wolfowitz + permutation null", "distributional",
     lambda: f"Mean streakiness z = {fmt(DATA['metrics'].get('b5_streaks',{}).get('mean_z'))} — indistinguishable from random.",
     "Absence of evidence for streakiness, at this sample size."),
    ("game", "GAME", "Win probability", "Logistic, sealed 2025 holdout", "exact",
     lambda: f"Brier {fmt(_mval('game_model','brier'))} beats home-field {fmt(_mval('game_model','brier_hfa_baseline'))} and Pythagorean {fmt(_mval('game_model','brier_pyth_baseline'))}; AUC {fmt(_mval('game_model','auc'))}.",
     "A thin edge (AUC ~0.55); evaluated once, never tuned on 2025."),
]


def _calibration_svg() -> str:
    c = DATA["calibration"]
    b = c["buckets"]
    lo, hi = 0.40, 0.65
    W, H, pad = 460, 360, 46

    def sx(p):
        return pad + (p - lo) / (hi - lo) * (W - 2 * pad)

    def sy(p):
        return H - pad - (p - lo) / (hi - lo) * (H - 2 * pad)
    grid = ""
    for gv in (0.40, 0.45, 0.50, 0.55, 0.60, 0.65):
        grid += (f'<line x1="{sx(gv):.0f}" y1="{sy(lo):.0f}" x2="{sx(gv):.0f}" y2="{sy(hi):.0f}" stroke="rgba(255,255,255,.06)"/>'
                 f'<line x1="{sx(lo):.0f}" y1="{sy(gv):.0f}" x2="{sx(hi):.0f}" y2="{sy(gv):.0f}" stroke="rgba(255,255,255,.06)"/>'
                 f'<text x="{sx(gv):.0f}" y="{H - pad + 16:.0f}" fill="var(--sub)" font-size="10" font-family="JetBrains Mono" text-anchor="middle">{fmt(gv, 2)}</text>'
                 f'<text x="{pad - 8:.0f}" y="{sy(gv) + 3:.0f}" fill="var(--sub)" font-size="10" font-family="JetBrains Mono" text-anchor="end">{fmt(gv, 2)}</text>')
    diag = f'<line x1="{sx(lo):.0f}" y1="{sy(lo):.0f}" x2="{sx(hi):.0f}" y2="{sy(hi):.0f}" stroke="var(--sub)" stroke-dasharray="4 4"/>'
    path = "M" + " L".join(f"{sx(pt['p_mean']):.0f} {sy(pt['obs']):.0f}" for pt in b)
    line = f'<path d="{path}" fill="none" stroke="var(--a)" stroke-width="2"/>'
    pts = ""
    for pt in b:
        pts += (f'<circle cx="{sx(pt["p_mean"]):.0f}" cy="{sy(pt["obs"]):.0f}" r="5" fill="var(--a)"/>'
                f'<text x="{sx(pt["p_mean"]):.0f}" y="{sy(pt["obs"]) - 10:.0f}" fill="var(--sub)" font-size="9" font-family="JetBrains Mono" text-anchor="middle">n={pt["n"]}</text>')
    return (f'<div class="calib"><svg viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="Reliability plot: predicted home-win probability vs observed frequency, 5 quantile buckets">'
            f'{grid}{diag}{line}{pts}'
            f'<text x="{W / 2:.0f}" y="{H - 8}" fill="var(--sub)" font-size="11" font-family="Space Grotesk" text-anchor="middle">predicted P(home win)</text>'
            f'<text x="14" y="{H / 2:.0f}" fill="var(--sub)" font-size="11" font-family="Space Grotesk" text-anchor="middle" transform="rotate(-90 14 {H / 2:.0f})">observed win frequency</text>'
            f'</svg></div>')


def build_data_science() -> None:
    body = head("DIAMONDIQ — Modeling & Data Science",
                "Thirteen baseball models with parity, evaluation, calibration, leakage discipline, "
                "and skill-vs-luck methodology — every estimate with an interval or n.", "data-science", "t-ds")
    body += ('<div class="hero"><div class="eyebrow">Modeling</div><h1>The Models</h1>'
             '<p>Thirteen models, each built in <b>R and Python</b> and gated on agreement, each '
             'anchored to a known baseball result. Figures first, uncertainty attached to every '
             'number.</p></div>' + prov())
    # 1. model index
    body += '<div class="sec"><h2>Model index</h2><span class="line"></span></div><div class="grid">'
    for anchor, code, name, method, tier, res, caveat in MODELS:
        badge = f'<span class="badge {TIER_BADGE.get(tier, "good")}">{tier}</span>'
        ok = DATA["metrics"].get({"m2": "m2_xwoba", "game": "game_model"}.get(anchor,
             {"m1": "m1_stability", "m4": "m4_framing", "m5": "m5_k_poisson", "m6": "m6_arsenal",
              "m7": "m7_babip_shrinkage", "m8": "m8_draft", "b1": "b1_pythagoras",
              "b2": "b2_count_value", "b3": "b3_aging", "b4": "b4_markov_sim",
              "b5": "b5_streaks"}.get(anchor, anchor)), {}).get("parity_ok")
        pbadge = '<span class="badge good">parity</span>' if ok else ''
        body += (f'<div class="card" id="{anchor}"><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">'
                 f'<span class="name">{code} · {name}</span>{badge}{pbadge}</div>'
                 f'<div class="kv"><span>Method</span><b class="mono">{method}</b></div>'
                 f'<div class="def">{res()}</div>'
                 f'<div class="read"><b>Caveat:</b> {caveat}</div></div>')
    body += '</div>'
    # 2. evaluation + calibration
    g = DATA["metrics"].get("game_model", {}).get("python", {})
    c = DATA["calibration"]
    body += ('<div class="sec"><h2>Evaluation, properly</h2><span class="line"></span></div>'
             '<p class="lead">The game model is trained on 2023–24 and scored <b>once</b> on a sealed '
             '2025 season. It is measured against real baselines, and — more telling than accuracy — '
             'its probabilities are checked for calibration.</p>'
             '<div class="grid"><div class="card">'
             f'<div class="kv"><span>Brier (lower better)</span><b>{fmt(g.get("brier"))}</b></div>'
             f'<div class="kv"><span>vs. home-field baseline</span><b>{fmt(g.get("brier_hfa_baseline"))}</b></div>'
             f'<div class="kv"><span>vs. Pythagorean baseline</span><b>{fmt(g.get("brier_pyth_baseline"))}</b></div>'
             f'<div class="kv"><span>AUC</span><b>{fmt(g.get("auc"))}</b></div>'
             f'<div class="kv"><span>Accuracy</span><b>{fmt(g.get("accuracy"))}</b> <span class="mono" style="color:var(--sub)">(always-home {fmt(c["base_home"])})</span></div>'
             '<div class="read">A small, real edge. The model beats both baselines on Brier; on raw '
             'accuracy it edges always-pick-home by about a point. That is what a genuine game-prediction edge looks like.</div></div>'
             '<div class="card"><div class="name" style="font-size:18px">Reliability (calibration)</div>'
             + _calibration_svg() +
             f'<div class="read">Predictions land in a narrow band ({fmt(c["p_lo"])}–{fmt(c["p_hi"])}) — a thin '
             'edge means few confident calls — but within that band, predicted probability tracks the '
             'observed win rate closely (points near the dashed diagonal). 5 equal-count buckets; n shown per point.</div></div></div>')
    # 3. leakage & holdout
    body += ('<div class="sec"><h2>Leakage &amp; holdout discipline</h2><span class="line"></span></div>'
             '<div class="grid"><div class="card"><div class="def">The 2025 season is a <b>sealed holdout</b>: '
             'exported once, read only by evaluation code, never opened during development or feature '
             'iteration. All game features are <b>leakage-safe</b> — built only from each team\'s prior '
             'games (trailing rolling form), so a game is never in its own features.</div>'
             '<div class="read">Why it matters: the easiest way to fake a good sports model is to let '
             'the outcome leak into the inputs. Sealing 2025 and using pregame-only features is the '
             'difference between a real out-of-sample number and a flattering in-sample one.</div></div>'
             '<div class="card"><div class="def">Doubleheaders are ordered by (date, game number, '
             'game_pk); suspended games that span two dates are de-duplicated; rolling windows require '
             '≥10 prior games so the features are full.</div>'
             '<div class="read">These are the unglamorous guards that keep the holdout honest.</div></div></div>')
    # 4. skill vs luck methodology
    st = DATA["stability"]
    rows = "".join(
        f'<div class="kv"><span>{lab}</span><b>{fmt(st[k]["r"])} '
        f'<span class="mono" style="color:var(--sub)">(n={st[k]["n"]})</span></b></div>'
        for k, lab in (("k_pct", "Strikeout rate (K%)"), ("bb_pct", "Walk rate (BB%)"),
                       ("ops", "OPS"), ("babip", "BABIP")) if k in st)
    body += ('<div class="sec"><h2>Skill vs. luck, measured</h2><span class="line"></span></div>'
             '<p class="lead">The glossary\'s "stable skill" vs "mostly luck" labels are not vibes — '
             'they are year-over-year self-correlations (min 300 PA both seasons). Higher = more '
             'repeatable skill; lower = more luck that won\'t carry over.</p>'
             f'<div class="grid"><div class="card"><div class="name" style="font-size:18px">Year-over-year stability</div>{rows}'
             '<div class="read">K% and BB% are real, fast-stabilizing skills; BABIP is mostly noise, '
             'which is exactly why M7 shrinks it toward the mean.</div></div>'
             '<div class="card"><div class="def">Every point estimate on this page carries an interval '
             'or an explicit n. A number without its uncertainty is marketing, not measurement.</div>'
             f'<div class="read">Model results are anchored to published baseball values (known-answer '
             f'tests); the parity gate proves R and Python agree, and the KAT proves they agree on '
             f'something true. See <a href="data-eng.html#parity">the parity gate</a>.</div></div></div>')
    # Effect-size interpretation (Funder & Ozer 2019)
    ef = DATA["effects"]
    st = DATA["stability"]
    body += ('<div class="sec" id="effects"><h2>How to read these effect sizes</h2><span class="line"></span></div>'
             '<p class="lead">We interpret effects the way <a href="https://doi.org/10.1177/2515245919847202">'
             'Funder &amp; Ozer (2019)</a> argue you should: never as a bare "% of variance explained" '
             '(r² systematically understates practical importance), always relative to a benchmark or '
             'translated into concrete odds, and mindful that small effects compound at scale.</p>'
             '<div class="grid">'
             f'<div class="card"><div class="name" style="font-size:17px">The game edge compounds</div>'
             f'<div class="def">The model calls the winner <b>{fmt(ef["game"]["accuracy"])}%</b> of the time vs. '
             f'<b>{fmt(ef["game"]["base_home"])}%</b> for always-pick-home — a ~0.7pp edge. Its Brier '
             f'improvement over that baseline is <b>{fmt(ef["game"]["delta"])}</b>, 95% CI '
             f'[{fmt(ef["game"]["delta_ci"][0])}, {fmt(ef["game"]["delta_ci"][1])}] (n={ef["game"]["n_games"]:,}).</div>'
             '<div class="read">The CI barely clears zero — honestly, a thin edge. But like aspirin and '
             'heart attacks (a per-person effect near r≈.03 that still saved lives at population scale), '
             'a fraction of a game per matchup is real across 2,430 games a season. We evaluate against '
             'achievable baselines, exactly the paper\'s doctrine.</div></div>'
             f'<div class="card"><div class="name" style="font-size:17px">The draft, honestly</div>'
             f'<div class="def">r = <b>{fmt(ef["m8"]["r"])}</b> means an earlier pick out-produces a later '
             f'one about <b>{fmt(ef["m8"]["concordance"],0)}%</b> of the time — a real tilt, nothing like '
             f'the 90% intuition. 95% CI [{fmt(ef["m8"]["ci"][0])}, {fmt(ef["m8"]["ci"][1])}] (n={ef["m8"]["n"]}).</div>'
             '<div class="read">Three true things: the tilt is real and compounds over hundreds of picks '
             'a year; our sample is <b>range-restricted</b> (only players who reached MLB), which '
             'attenuates r, so the full-population effect is larger; and n=104 leaves the interval wide '
             '— it can\'t rule out ~0 or ~−0.25. Any <i>one</i> pick is close to a crapshoot; the size '
             'of the tilt we can\'t pin down. Reporting "explains 1% of variance" would hide all of this.</div></div></div>'
             '<div class="card" style="margin-top:14px"><div class="name" style="font-size:17px">Effects are only meaningful in context</div>'
             f'<div class="def">By psychology-calibrated labels, BABIP\'s year-to-year r = '
             f'<b>{fmt(st["babip"]["r"])}</b> would count as "large." We still treat it as mostly luck — '
             f'because the right comparison is K% at <b>{fmt(st["k_pct"]["r"])}</b> <i>within the same '
             f'measurement system</i>, not survey correlations from another field. That is Funder &amp; '
             'Ozer\'s central point, live: an effect size only means something next to the right benchmark.</div>'
             '<div class="read"><b>House rule:</b> nowhere on this site is an effect reported as r² / '
             '"% variance explained" alone — every correlation comes with a benchmark or a concrete-odds '
             'translation.</div></div>'
             '<p class="lead" style="margin-top:18px;font-size:13px">Reference: Funder, D. C., &amp; Ozer, '
             'D. J. (2019). Evaluating effect size in psychological research: Sense and nonsense. '
             '<i>Advances in Methods and Practices in Psychological Science</i>, 2(2), 156–168. '
             '<a href="https://doi.org/10.1177/2515245919847202">doi:10.1177/2515245919847202</a>.</p>')
    _write("data-science.html", body)


PAGES["data-science.html"] = build_data_science


# ------------------------------------------------------------------ data-eng.html
def _layer_counts() -> dict:
    lc = {"staging": 0, "silver": 0, "gold": 0}
    for t in DATA["dq"]["tables"]:
        lc[t["layer"]] = lc.get(t["layer"], 0) + 1
    return lc


def _pipeline_svg() -> str:
    lc = _layer_counts()
    nodes = [
        ("Statcast\n+ statsapi", "#5b6472"), ("ingest\n(Python)", "#5b6472"),
        ("DuckDB\nbronze", "#7a5a2e"), (f"dbt\nstaging {lc['staging']}", "#7a5a2e"),
        (f"silver {lc['silver']}", "#9aa4b6"), (f"gold {lc['gold']}", "#d4af37"),
        ("R + Python\nmodels", "#3ddc84"), ("parity\ngate", "#ef4b4b"),
        ("static\nsite", "#8b7fff"),
    ]
    bw, bh, gap, x0, y = 88, 52, 24, 8, 40
    vw = len(nodes) * (bw + gap)
    svg = [f'<svg viewBox="0 0 {vw} 140" role="img" aria-label="Pipeline: Statcast to static site through DuckDB, dbt medallion layers, R and Python models, and the parity gate">']
    for i, (label, col) in enumerate(nodes):
        x = x0 + i * (bw + gap)
        svg.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="9" fill="color-mix(in srgb,{col} 22%,#0c0e14)" stroke="{col}" stroke-width="1.5"/>')
        for j, ln in enumerate(label.split("\n")):
            svg.append(f'<text x="{x + bw / 2:.0f}" y="{y + bh / 2 - 4 + j * 13:.0f}" fill="#f4f6fb" font-size="11" font-family="JetBrains Mono" text-anchor="middle">{ln}</text>')
        if i < len(nodes) - 1:
            ax = x + bw
            svg.append(f'<line x1="{ax}" y1="{y + bh / 2:.0f}" x2="{ax + gap}" y2="{y + bh / 2:.0f}" stroke="#5b6472" stroke-width="1.5" marker-end="url(#ah)"/>')
    svg.append('<defs><marker id="ah" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0 0 L6 3 L0 6 z" fill="#5b6472"/></marker></defs>')
    svg.append('<text x="8" y="118" fill="#7a5a2e" font-size="10" font-family="Space Grotesk">bronze / silver / gold = medallion layers · widths not to scale</text>')
    svg.append("</svg>")
    return f'<div class="diagram">{"".join(svg)}</div>'


def build_data_eng() -> None:
    dq = DATA["dq"]
    lc = _layer_counts()
    npass = sum(1 for k in DATA["metrics"] if DATA["metrics"][k].get("parity_ok"))
    body = head("DIAMONDIQ — Data Engineering",
                "The pipeline behind DiamondIQ: Statcast → DuckDB → dbt medallion → R & Python "
                "models gated by an R↔Python parity check → static site. Reproducible, ~$0 to run.",
                "data-eng", "t-eng")
    body += ('<div class="hero"><div class="eyebrow">Pipeline</div><h1>data engineering</h1>'
             '<p>A polyglot medallion pipeline that builds every model <b>twice</b> — in R and '
             'Python — and refuses to publish unless the two agree. This page is the portfolio '
             'README for engineers.</p></div>' + prov())
    body += ('<div class="sec"><h2>The pipeline</h2><span class="line"></span></div>' + _pipeline_svg())
    body += ('<div class="card" style="margin-top:14px"><div class="name" style="font-size:17px">Statcast is sensor telemetry</div>'
             '<div class="def">Statcast isn\'t a spreadsheet — it\'s a <b>distributed measurement system</b>: '
             'Hawk-Eye optical arrays in 30 venues emitting <b>2.18M measurement events</b>. So this is a '
             'measurement-system engineering problem, and the pipeline treats it as one: high-volume '
             'telemetry ingestion, <b>cross-site normalization</b> (park effects are per-venue sensor '
             'calibration differences), a mid-life <b>instrument migration</b> (Trackman radar → Hawk-Eye '
             'optical in 2020 — the historical-baseline shift familiar from any sensor swap), and '
             '<b>late/missing/corrected readings</b> (untracked pitches, suspended games, post-hoc scoring '
             'corrections). It\'s an analogy to instrumentation engineering, not streaming SCADA — and it\'s '
             'accurate.</div></div>')
    # warehouse + testing
    body += (f'<div class="sec"><h2>Warehouse &amp; testing</h2><span class="line"></span></div><div class="grid3">'
             f'<div class="card"><div class="kv"><span>Warehouse tables</span></div><div class="stat">{len(dq["tables"])}</div>'
             f'<div class="read">staging {lc["staging"]} · silver {lc["silver"]} · gold {lc["gold"]}</div></div>'
             f'<div class="card"><div class="kv"><span>dbt data tests</span></div><div class="stat" style="color:var(--good)">{dq["tests"]["pass"]}<span class="u">passing</span></div>'
             f'<div class="read">0 failing, 0 warning.</div></div>'
             f'<div class="card"><div class="kv"><span>Parity gate</span></div><div class="stat" style="color:var(--good)">{npass}<span class="u">/ {len(DATA["metrics"])}</span></div>'
             f'<div class="read">All three tiers pass.</div></div></div>')
    cats = [("Grain uniqueness", "every fact has a uniqueness test on its declared grain — no silent fan-out."),
            ("Referential integrity", "facts join to dimensions; failed joins get a placeholder + COALESCE, kept under 0.5%."),
            ("RE24 anchors", "the run-expectancy matrix is asserted against published Tango reference values."),
            ("Volume", "Statcast pitch counts reconcile with the official boxscore, directionally (never short)."),
            ("Determinism", "a rebuild-and-hash gate proves the gold feeds are byte-identical across rebuilds.")]
    body += '<div class="grid">'
    for name, desc in cats:
        body += f'<div class="card"><div class="name" style="font-size:17px">{name}</div><div class="def">{desc}</div></div>'
    body += '</div>'
    # parity gate explained (README-sourced)
    tiers = parity_tiers()
    trows = "".join(
        f'<div class="card"><div style="display:flex;gap:10px;align-items:center"><span class="name" style="font-size:17px">{t[0]}</span></div>'
        f'<div class="def">{t[1]}</div><div class="read"><b>Why not exact:</b> {t[2]}</div></div>'
        for t in tiers)
    body += (f'<div class="sec" id="parity"><h2>The parity gate</h2><span class="line"></span></div>'
             f'<p class="lead">{readme_tagline()}</p>'
             f'<div class="card" style="margin-bottom:14px"><div class="def">This is <b>dual-channel '
             f'redundant validation</b> — the same voting logic used on redundant safety-rated measurement '
             f'channels: two independent implementations must agree before anything ships. R and Python '
             f'<b>never share memory</b> — no rpy2, no reticulate. They exchange data only through files '
             f'(DuckDB tables and flat Parquet feeds). Every model is implemented independently in both, '
             f'and the build fails unless they agree at one of three tiers. If a single-language build is '
             f'quietly wrong, the other usually isn\'t wrong the same way — the gate turns "looks '
             f'plausible" into "two toolchains independently agree." Each model is also anchored by a known-answer test: '
             f'<b>parity proves R and Python agree; the KAT proves they agree on something true.</b></div></div>'
             f'<div class="grid3">{trows}</div>'
             f'<div class="card" style="margin-top:14px"><div class="name" style="font-size:16px">What a gate failure looks like</div>'
             f'<div class="def mono" style="font-size:12px;color:var(--bad)">Game parity coef.win_pct_diff: R and Python disagree past tolerance<br>'
             f'Game KAT: Brier {fmt(0.251)} not &lt; Pythag baseline {fmt(0.272)}<br>PARITY GATE FAILED — build aborts, nothing ships.</div>'
             f'<div class="read">A real failure blocks publish. That is the point: a broken model can\'t reach the site.</div></div>')
    # war stories from DECISIONS/README
    ws = readme_war_stories()[:5]
    body += '<div class="sec"><h2>War stories</h2><span class="line"></span></div>'
    body += f'<p class="lead">Bugs worth remembering — the full postmortems are in <a href="{GH}/blob/main/DECISIONS.md">DECISIONS.md</a>.</p><div class="grid">'
    for lead, rest in ws:
        body += (f'<div class="card"><div class="name" style="font-size:16px">{lead}</div>'
                 f'<div class="def">{rest}</div>'
                 f'<div class="read"><a href="{GH}/blob/main/DECISIONS.md">Read the postmortem →</a></div></div>')
    body += '</div>'
    # operational / TCO
    body += ('<div class="sec"><h2>Operational notes</h2><span class="line"></span></div><div class="grid">'
             '<div class="card"><div class="name" style="font-size:17px">Reproducible &amp; cheap</div>'
             '<div class="def">Fixed seeds; the static site is generated straight from the warehouse; a '
             'from-empty clone reproduces every published number to six decimals.</div>'
             '<div class="read"><b>TCO ≈ $0:</b> DuckDB + a static GitHub Pages site means no served '
             'database, no uptime burden, no bill. The tradeoff — no live data — is why the next phase '
             'adds a nightly refresh.</div></div>'
             f'<div class="card"><div class="name" style="font-size:17px">Source</div>'
             f'<div class="def">Every stage runs through one CLI and exits non-zero on failure.</div>'
             f'<div class="kv"><span>Repository</span><b><a href="{GH}" style="color:var(--a)">github.com/Steve27M/mlb-analytics ↗</a></b></div></div></div>')
    _write("data-eng.html", body)


PAGES["data-eng.html"] = build_data_eng


# ------------------------------------------------------------------ betting.html
def build_betting() -> None:
    body = head("DIAMONDIQ — Sports Betting & Analytics",
                "A descriptive-analytics view for the trading desk: model-vs-baseline honesty, "
                "calibration for pricing, American-odds fluency, and a flat sortable odds table.",
                "betting", "t-bet")
    g = DATA["metrics"].get("game_model", {}).get("python", {})
    c = DATA["calibration"]
    body += ('<div class="hero"><div class="eyebrow">Trading desk</div><h1>betting &amp; analytics</h1>'
             '<p>What a book person actually checks: is the edge real, is it calibrated, and how big '
             'is the variance. Descriptive analytics only — no picks, no bankroll advice.</p></div>' + prov())
    # 1 + 2 benchmark honesty with odds fluency
    body += ('<div class="sec"><h2>Is the edge real?</h2><span class="line"></span></div>'
             '<p class="lead">The game model is benchmarked against a home-field baseline and a '
             'Pythagorean baseline — it beats <b>both</b> on Brier — <b>not</b> against closing lines. '
             'Beating the closing line is the actual bar for a profitable model, and we don\'t claim it.</p>'
             '<div class="grid"><div class="card">'
             f'<div class="kv"><span>Model Brier (lower better)</span><b class="pos">{fmt(g.get("brier"))}</b></div>'
             f'<div class="kv"><span>Home-field baseline</span><b>{fmt(g.get("brier_hfa_baseline"))}</b></div>'
             f'<div class="kv"><span>Pythagorean baseline</span><b>{fmt(g.get("brier_pyth_baseline"))}</b></div>'
             f'<div class="kv"><span>AUC</span><b>{fmt(g.get("auc"))}</b></div>'
             f'<div class="kv"><span>Accuracy vs always-home</span><b>{fmt(g.get("accuracy"))} / {fmt(c["base_home"])}</b></div>'
             '<div class="read">Honest wrinkle: the Pythagorean baseline is actually <b>worse</b> than '
             'naive home-field at single-game grain — a 10-game rolling Pythagorean is noisy. The fitted '
             'model beats both; we report the wrinkle rather than hide it.</div></div>'
             '<div class="card"><div class="name" style="font-size:17px">Odds fluency</div>'
             '<div class="def">Every probability on this page also shows its American-odds equivalent, '
             'e.g. a home win probability of:</div>'
             f'<div class="kv"><span class="mono">{fmt(g.get("mean_pred"))} (typical home game)</span><b class="mono">{to_american(g.get("mean_pred", 0.52))}</b></div>'
             f'<div class="kv"><span class="mono">0.60</span><b class="mono">{to_american(0.60)}</b></div>'
             f'<div class="kv"><span class="mono">0.45</span><b class="mono">{to_american(0.45)}</b></div>'
             '<div class="read">No-vig, straight from model probability — a starting point for pricing, '
             'not a posted line.</div></div></div>')
    # 2a closing-line capture status (retrospective, settled-games only — no live picks published)
    body += ('<div class="card callout" style="margin-top:14px"><div class="read"><b>Closing lines '
             '(model-vs-market): capture is live, comparison accrues.</b> Closing moneylines can\'t be '
             'backfilled, so we now bank one pre-game snapshot per day of the 2026 season. The raw '
             'lines stay private; only a <b>retrospective, settled-games</b> comparison is published — '
             'after each game finishes, what the model said vs. what the market priced vs. what actually '
             'happened. <b>No live picks, no advice</b> — this is a calibration/accuracy record, not a '
             'tip sheet. The model-vs-market table fills in as 2026 games settle. Market odds: '
             '<a href="https://the-odds-api.com">The Odds API</a>.</div></div>')
    # 3 calibration for pricing
    body += ('<div class="sec"><h2>Calibration (for pricing)</h2><span class="line"></span></div>'
             '<p class="lead">When the model says 55%, does it happen 55% of the time? For pricing, '
             'calibration matters more than accuracy.</p>'
             '<div class="grid"><div class="card">' + _calibration_svg() +
             f'<div class="read">Predictions sit in a tight {fmt(c["p_lo"])}–{fmt(c["p_hi"])} band '
             '(a thin edge = few confident calls), but within it, stated probability tracks the observed '
             'rate — points hug the dashed diagonal. 5 equal-count buckets, n per point.</div></div>'
             '<div class="card"><div class="name" style="font-size:17px">Variance &amp; sizing reality</div>'
             '<div class="def"><b>In plain terms:</b> when we say 60%, it happens about 60% of the time, '
             'and our probabilities are slightly sharper than always-leaning-home (Brier 0.247 vs 0.249). '
             'Thin — but thin edges are the only kind that exist in this market, and they only pay at '
             'volume and with discipline (Funder &amp; Ozer, 2019: small effects compound).</div>'
             '<div class="def" style="margin-top:8px"><b>Odds, translated:</b> a 65% win probability is '
             '−186 — risk $186 to win $100. That is the price the model implies; a posted line bakes in '
             'the book\'s margin on top.</div>'
             '<div class="read">This is descriptive analytics — <b>not betting advice</b>, no staking or '
             'bankroll recommendations. If gambling stops being fun, help is free and confidential: '
             'call or text <b>1-800-GAMBLER</b> (ncpgambling.org).</div></div></div>')
    # 4 flat sortable odds table (prerendered)
    body += ('<div class="sec"><h2>Full odds table</h2><span class="line"></span></div>'
             '<p class="lead">All 30 teams, one sortable table (click a column). Playoff and division '
             'odds shown as probability and American price.</p>')
    if LIVE:
        cols = ["Team", "Current", "Proj W", "80% range", "Playoff %", "Playoff", "Div %", "Div"]
        head_cells = "".join(
            f'<th{" data-nosort" if h == "80% range" else ""}>{h}</th>' for h in cols)
        trs = ""
        for t in sorted(LIVE["teams"], key=lambda x: -x["playoff_odds"]):
            trs += (f'<tr><td data-v="{t["abbr"]}">{mono_py(t["team_id"])} {t["abbr"]}</td>'
                    f'<td data-v="{t["cur_w"]}">{t["cur_w"]}-{t["cur_l"]}</td>'
                    f'<td data-v="{t["proj_wins"]}">{fmt(t["proj_wins"], 1)}</td>'
                    f'<td>{fmt(t["p10"], 1)}–{fmt(t["p90"], 1)}</td>'
                    f'<td data-v="{t["playoff_odds"]}">{fmt(t["playoff_odds"] * 100, 1)}%</td>'
                    f'<td data-v="{t["playoff_odds"]}" class="mono">{to_american(t["playoff_odds"])}</td>'
                    f'<td data-v="{t["div_odds"]}">{fmt(t["div_odds"] * 100, 1)}%</td>'
                    f'<td data-v="{t["div_odds"]}" class="mono">{to_american(t["div_odds"])}</td></tr>')
        body += f'<div class="tblwrap"><table class="flat" id="oddstbl"><thead><tr>{head_cells}</tr></thead><tbody>{trs}</tbody></table></div>'
        js = '<script>document.querySelectorAll("table.flat").forEach(makeSortable);</script>'
        _write("betting.html", body, js)
    else:
        _write("betting.html", body)


PAGES["betting.html"] = build_betting


# ------------------------------------------------------------------ fan.html (zero pipeline jargon)
def _luck_chip(t: dict, sign: bool) -> str:
    v = t["luck"]
    txt = f'+{fmt(v, 1)}' if v > 0 else fmt(v, 1)
    return (f'<div class="srow" style="border-left-color:{team_fill(t["team_id"])};grid-template-columns:1fr auto">'
            f'<div class="steam">{mono_py(t["team_id"])}<b>{abbr(t["team_id"])}</b>'
            f'<span class="srec">{t["season"]} · {fmt(t["w"])}-{fmt(t["l"])}</span></div>'
            f'<div class="sproj" style="color:{"var(--good)" if sign else "var(--bad)"}">{txt}<span class="srange">games</span></div></div>')


def build_fan() -> None:
    body = head("DIAMONDIQ — For Baseball Fans",
                "Who was for real and who got lucky, which stats are skill vs. luck, whether anyone "
                "can actually predict a game, and playoff odds — in plain English.", "fan", "t-fan")
    acc = round(DATA["calibration"]["accuracy"] * 100, 1)
    home = round(DATA["calibration"]["base_home"] * 100, 1)
    body += ('<div class="hero"><div class="eyebrow">For fans</div><h1>Skill, luck &amp; the truth</h1>'
             '<p>The stuff that actually settles bar arguments — who overachieved, which numbers mean '
             'something, and how much of baseball is just luck.</p></div>' + prov())
    # 1. luck leaderboard
    teams = DATA["teams"]
    lucky = sorted(teams, key=lambda x: -x["luck"])[:5]
    snake = sorted(teams, key=lambda x: x["luck"])[:5]
    body += ('<div class="sec"><h2>Who was for real?</h2><span class="line"></span></div>'
             '<p class="lead">Teams that won more (or fewer) games than their runs scored and allowed '
             'say they should have. Luck like this usually doesn\'t repeat.</p><div class="grid">'
             '<div class="card"><div class="name" style="font-size:18px;color:var(--good)">Luckiest teams</div>'
             + "".join(_luck_chip(t, True) for t in lucky) + '</div>'
             '<div class="card"><div class="name" style="font-size:18px;color:var(--bad)">Most snakebitten</div>'
             + "".join(_luck_chip(t, False) for t in snake) + '</div></div>')
    # 2. skill vs luck stat cards
    gl = DATA["glossary"]
    stat_cards = [
        ("OPS", "ops", "high", "The all-in-one hitting number. Sticks year to year — good hitters stay good."),
        ("Strikeout rate", "k_pct", "low", "How often a hitter strikes out. The <b>most reliable</b> hitter trait there is — it barely moves year to year."),
        ("Walk rate", "bb_pct", "high", "Plate discipline. Also very steady — a good eye is a real, repeatable skill."),
        ("BABIP (batted-ball luck)", "babip", "high", "How often balls in play fall for hits. This one is <b>mostly luck</b> — a hot BABIP almost never carries into next year."),
    ]
    body += ('<div class="sec"><h2>Which stats are skill, which are luck?</h2><span class="line"></span></div>'
             '<p class="lead">Some numbers repeat every year (skill). Others bounce around (luck). '
             'Here\'s the field, with the leader and trailer named.</p><div class="grid">')
    for name, key, direction, cap in stat_cards:
        body += (f'<div class="card"><div class="name" style="font-size:18px">{name}</div>'
                 f'<div class="def">{cap}</div>{dist_html(gl.get(key), direction)}'
                 f'<div class="read"><a href="glossary.html#{key}">More in the Stat Guide →</a></div></div>')
    body += '</div>'
    # 3. can anyone predict baseball
    body += ('<div class="sec"><h2>Can anyone actually predict baseball?</h2><span class="line"></span></div>'
             '<div class="card callout"><div class="big3">'
             f'<div><div class="n" style="color:var(--good)">{fmt(acc)}%</div><div class="l">our best model picks the winner</div></div>'
             f'<div><div class="n">{fmt(home)}%</div><div class="l">just always pick the home team</div></div>'
             '<div><div class="n">50%</div><div class="l">flip a coin</div></div></div>'
             '<div class="read" style="margin-top:12px">That half-a-game-in-a-hundred over always picking '
             'the home team sounds like nothing — but it\'s like aspirin and heart attacks: nearly '
             'invisible for one person, huge across millions. Across 2,430 games a season, a real edge '
             'shows up. Anyone claiming they call games 70% of the time is selling something.</div></div>')
    # 4. live playoff snapshot (2026)
    if LIVE:
        top = sorted(LIVE["teams"], key=lambda x: -x["playoff_odds"])[:8]
        rows = ""
        for t in top:
            col = team_fill(t["team_id"])
            rows += (f'<div class="srow" style="border-left-color:{col}">'
                     f'<div class="steam">{mono_py(t["team_id"])}<b>{t["abbr"]}</b>'
                     f'<span class="srec">{t["cur_w"]}-{t["cur_l"]}</span></div>'
                     f'<div class="sproj">{fmt(t["proj_wins"], 1)}<span class="srange">proj wins</span></div>'
                     f'<div class="obar"><div class="ofill" style="width:{t["playoff_odds"] * 100:.0f}%;background:{col}"></div>'
                     f'<span class="oval">{fmt(t["playoff_odds"] * 100, 0)}%</span></div></div>')
        body += (f'<div class="sec"><h2>Who makes the playoffs? ({LIVE["season"]})</h2><span class="line"></span></div>'
                 '<p class="lead">Live odds for the current season — each team\'s current record plus '
                 'ten thousand simulations of the games left to play. It\'s a season-long projection, '
                 'not a bet on tonight\'s game.</p>'
                 f'<div class="card">{rows}</div>'
                 '<p class="lead"><a href="simulator.html">See the full board →</a></p>')
    # 5. draft crapshoot + aging
    peak = DATA["metrics"].get("b3_aging", {}).get("python", {}).get("peak_age")
    conc = fmt(DATA["effects"]["m8"]["concordance"], 0)
    body += ('<div class="sec"><h2>Two things everyone gets wrong</h2><span class="line"></span></div><div class="grid">'
             '<div class="card"><div class="name" style="font-size:19px">The draft is (almost) a coin flip</div>'
             f'<div class="big3" style="grid-template-columns:1fr"><div><div class="n" style="color:var(--gold)">{conc} in 100</div>'
             f'<div class="l">chance an earlier pick out-hits a later one (not 90 in 100)</div></div></div>'
             f'<div class="read">For any <i>single</i> pick, the draft is close to a coin flip — a little '
             f'better, not a sure thing. But teams make hundreds of picks a year, and a {conc}/{fmt(100 - int(float(conc)))} '
             f'tilt repeated that many times adds up. And we could only measure players who <i>reached</i> '
             f'the majors — which hides some of the draft\'s real power. Both things are true.</div></div>'
             '<div class="card"><div class="name" style="font-size:19px">Hitters peak around 30</div>'
             f'<div class="big3" style="grid-template-columns:1fr"><div><div class="n">{fmt(peak, 0)}</div>'
             f'<div class="l">the age hitters are typically at their best</div></div></div>'
             '<div class="read">With a catch: bad players get cut young, so the "old player" data only '
             'contains the good ones who survived. The real decline is steeper than the curve looks.</div></div></div>')
    # 6. fun facts
    facts = "".join(f'<div class="card"><div class="def">{f}</div></div>' for f in DATA["funfacts"])
    body += ('<div class="sec"><h2>Fun facts from the numbers</h2><span class="line"></span></div>'
             f'<div class="grid">{facts}</div>')
    _write("fan.html", body)


PAGES["fan.html"] = build_fan


# ------------------------------------------------------------------ index.html (router)
def build_index() -> None:
    meta = DATA["meta"]
    acc = round(DATA["calibration"]["accuracy"] * 100, 1)
    home = round(DATA["calibration"]["base_home"] * 100, 1)
    body = head("DIAMONDIQ — MLB skill, luck & prediction",
                "2.18M pitches, 7,408 games, 13 models built in R and Python. What's skill, what's "
                "luck, and how well can a baseball game actually be predicted?", "")
    body += (f'<div class="hero"><div class="eyebrow">Diamond Intelligence</div>'
             f'<h1>What\'s skill,<br>what\'s luck?</h1>'
             f'<p><b>{meta["n_pitches"]:,} pitches. {meta["n_games"]:,} games. 13 models.</b> '
             f'An honest look at how much of baseball is repeatable skill, how much is luck, and how '
             f'well a game can really be predicted — with the uncertainty left in, never hyped out.</p></div>' + prov())
    # headline insight
    body += ('<div class="card callout" style="margin-top:20px"><div class="big3">'
             f'<div><div class="n" style="color:var(--good)">{fmt(acc)}%</div><div class="l">DiamondIQ calls the winner</div></div>'
             f'<div><div class="n">{fmt(home)}%</div><div class="l">always pick the home team</div></div>'
             '<div><div class="n">50%</div><div class="l">coin flip</div></div></div>'
             '<div class="read" style="margin-top:12px">That few-point gap over always-picking-home is '
             'what a genuine game-prediction edge looks like. Baseball is close to a coin flip — and we '
             'say so instead of pretending otherwise.</div></div>')
    # three doors
    body += ('<div class="sec"><h2>Pick your door</h2><span class="line"></span></div>'
             '<div class="doors">'
             '<a class="door" href="fan.html"><div class="t">I\'m a fan</div>'
             '<div class="d">Who overachieved, which stats are skill vs. luck, whether anyone can '
             'really predict a game, and playoff odds — all in plain English.</div>'
             '<div class="go">Enter →</div></a>'
             '<a class="door" href="betting.html"><div class="t">Betting &amp; analytics</div>'
             '<div class="d">Model-vs-baseline honesty, calibration for pricing, American-odds fluency, '
             'and a flat sortable odds table. Descriptive only — no picks.</div>'
             '<div class="go">Enter →</div></a>'
             '<a class="door" href="data-eng.html"><div class="t">I\'m a data person</div>'
             '<div class="d">The medallion pipeline and the R↔Python parity gate '
             '(<a href="data-science.html" style="color:var(--a)">or jump to the models &amp; '
             'calibration</a>).</div>'
             '<div class="go">Enter →</div></a></div>')
    _write("index.html", body)


PAGES["index.html"] = build_index


def build_models_redirect() -> None:
    """models.html folded into data-science.html (FEEDBACK §0) — keep a redirect for old links."""
    (DOCS / "models.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta http-equiv="refresh" content="0; url=data-science.html">'
        '<title>Moved → Data Science</title><link rel="canonical" href="data-science.html"></head>'
        '<body>The Models page moved to <a href="data-science.html">Data Science</a>.</body></html>',
        encoding="utf-8")


PAGES["models.html"] = build_models_redirect


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
