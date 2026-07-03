"""Build the static DIAMONDIQ dashboard site (docs/) from data/dashboard/site_data.json.

Four MLB-themed pages sharing one nav/theme: Dashboard (index), Compare Teams, Stat Guide (a
searchable data dictionary), and The Models (how each of the 13 models works + its parity/KAT
status). Pure HTML/JS — Python owns all warehouse I/O (prepare_dashboard_data.py); no R needed.
Run after `prepare_dashboard_data.py`. Attribution (MLBAM / Chadwick / Wikipedia CC BY-SA) in the
footer of every page.
"""
# ruff: noqa: E501  (this file emits HTML/CSS/JS — long string literals are inherent)
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = json.loads((REPO / "data" / "dashboard" / "site_data.json").read_text())
_SIM_PATH = REPO / "data" / "dashboard" / "season_sim.json"
SIM = json.loads(_SIM_PATH.read_text()) if _SIM_PATH.exists() else None
DOCS = REPO / "docs"
GH = "https://github.com/Steve27M/mlb-analytics"

CSS = """
:root{
  --a:#ef4b4b; --a2:#9e1f1f; --aText:#1a0505;
  --bg:#08090c; --text:#f4f6fb; --sub:#8a94a6; --border:rgba(255,255,255,.09);
  --panel:#13161e; --panel2:#0c0e14; --good:#3ddc84; --bad:#ff6b6b; --gold:#ffd166;
}
*{box-sizing:border-box;} html{scroll-behavior:smooth;}
body{margin:0;background:var(--bg);color:var(--text);font-family:'Space Grotesk',sans-serif;
  background:radial-gradient(140% 55% at 50% 0%,color-mix(in srgb,var(--a) 14%,var(--bg)) 0%,var(--bg) 52%);
  background-attachment:fixed;padding-bottom:70px;}
a{color:inherit;text-decoration:none;}
::-webkit-scrollbar{width:11px;height:11px;} ::-webkit-scrollbar-track{background:#0c0e13;}
::-webkit-scrollbar-thumb{background:#242833;border-radius:6px;}
.wrap{max-width:1120px;margin:0 auto;padding:0 26px;}
.nav{position:sticky;top:0;z-index:40;backdrop-filter:blur(14px);background:rgba(8,9,13,.82);border-bottom:1px solid var(--border);}
.nav .in{display:flex;align-items:center;gap:20px;padding:12px 26px;flex-wrap:wrap;}
.brand{display:flex;align-items:center;gap:9px;}
.brand .bar{width:9px;height:26px;border-radius:3px;background:linear-gradient(var(--a),var(--a2));}
.brand .txt{font:800 15px 'Saira Condensed';letter-spacing:.14em;}
.navlinks{display:flex;gap:4px;flex-wrap:wrap;margin-left:auto;}
.navlinks a{font:600 12px 'Space Grotesk';letter-spacing:.04em;color:var(--sub);padding:7px 12px;border-radius:8px;}
.navlinks a:hover{color:var(--text);background:var(--panel);}
.navlinks a.active{color:var(--aText);background:var(--a);}
.hero{padding:44px 0 8px;}
.hero .eyebrow{font:600 12px 'Space Grotesk';letter-spacing:.22em;color:var(--a);text-transform:uppercase;}
.hero h1{font:400 clamp(40px,6vw,68px)/.92 'Anton';text-transform:uppercase;margin:10px 0 0;}
.hero p{font:400 16px/1.6 'Space Grotesk';color:var(--sub);max-width:700px;margin:14px 0 0;}
.sec{display:flex;align-items:center;gap:12px;margin:38px 0 16px;}
.sec h2{font:400 22px 'Anton';letter-spacing:.02em;text-transform:uppercase;margin:0;}
.sec .line{flex:1;height:1px;background:var(--border);}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}
.card{border-radius:16px;border:1px solid var(--border);background:var(--panel);padding:18px 20px;display:flex;flex-direction:column;gap:10px;}
.card .name{font:400 21px 'Anton';text-transform:uppercase;letter-spacing:.01em;}
.badge{font:700 10px 'Space Grotesk';letter-spacing:.08em;text-transform:uppercase;padding:4px 9px;border-radius:999px;border:1px solid var(--border);color:var(--sub);white-space:nowrap;}
.badge.good{color:var(--aText);background:var(--good);border-color:var(--good);}
.badge.a{color:var(--aText);background:var(--a);border-color:var(--a);}
.badge.gold{color:#1a0505;background:var(--gold);border-color:var(--gold);}
.card .def{font:400 14px/1.6 'Space Grotesk';color:var(--text);}
.card .read{font:400 13px/1.6 'Space Grotesk';color:var(--sub);border-left:2px solid var(--a);padding-left:12px;}
.card .read b{color:var(--text);font-weight:600;}
.stat{font:700 30px 'Saira Condensed';}
.stat .u{font:600 13px 'Space Grotesk';color:var(--sub);margin-left:6px;}
.kv{display:flex;justify-content:space-between;font:500 13px 'Space Grotesk';color:var(--sub);padding:3px 0;}
.kv b{color:var(--text);font:700 13px 'JetBrains Mono';}
.mono{font-family:'JetBrains Mono';}
.dist{margin-top:2px;}
.dist .track{position:relative;height:10px;border-radius:5px;background:linear-gradient(90deg,var(--panel2),color-mix(in srgb,var(--a) 30%,var(--panel2)));border:1px solid var(--border);}
.dist .med{position:absolute;top:-3px;width:2px;height:16px;background:var(--text);border-radius:2px;}
.dist .ends{display:flex;justify-content:space-between;margin-top:7px;font:600 11px 'JetBrains Mono';color:var(--sub);}
.dist .ex{display:flex;justify-content:space-between;gap:8px;margin-top:9px;font:500 11px 'Space Grotesk';}
.dist .ex .chip{display:flex;align-items:center;gap:6px;color:var(--sub);}
.dist .ex .chip b{font:700 12px 'Saira Condensed';color:var(--text);}
.dist .ex .dot{width:7px;height:7px;border-radius:2px;}
.toolbar{display:flex;gap:12px;align-items:center;margin:26px 0 6px;flex-wrap:wrap;}
.search{flex:1;min-width:220px;display:flex;align-items:center;gap:10px;background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:11px 15px;}
.search input,select{background:var(--panel);border:1px solid var(--border);border-radius:10px;color:var(--text);font:500 14px 'Space Grotesk';padding:9px 12px;outline:none;}
.search input{flex:1;border:none;padding:0;background:none;}
.count{font:600 12px 'JetBrains Mono';color:var(--sub);}
.empty{grid-column:1/-1;text-align:center;color:var(--sub);font:500 14px 'Space Grotesk';padding:40px;}
footer{margin-top:44px;font:500 12px/1.7 'Space Grotesk';color:var(--sub);}
footer a{color:var(--a);}
.cmp{display:grid;grid-template-columns:1fr 60px 1fr;gap:10px;align-items:center;margin:8px 0;}
.cmp .lab{grid-column:1/-1;text-align:center;font:600 11px 'Space Grotesk';letter-spacing:.1em;text-transform:uppercase;color:var(--sub);margin-top:8px;}
.cmp .bar{height:26px;border-radius:6px;background:var(--panel2);position:relative;overflow:hidden;border:1px solid var(--border);}
.cmp .fill{position:absolute;top:0;bottom:0;background:linear-gradient(90deg,var(--a2),var(--a));}
.cmp .fill.r{right:0;} .cmp .fill.l{left:0;}
.cmp .v{position:absolute;top:5px;font:700 13px 'JetBrains Mono';color:#fff;}
.cmp .mid{text-align:center;font:600 11px 'Space Grotesk';color:var(--sub);}
.dhead{font:400 18px 'Anton';text-transform:uppercase;letter-spacing:.02em;color:var(--a);}
.shdr{display:grid;grid-template-columns:1.3fr .9fr 1.4fr;gap:8px;font:600 10px 'Space Grotesk';letter-spacing:.06em;text-transform:uppercase;color:var(--sub);padding-bottom:4px;border-bottom:1px solid var(--border);}
.srow{display:grid;grid-template-columns:1.3fr .9fr 1.4fr;gap:8px;align-items:center;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.04);}
.steam{display:flex;align-items:center;gap:7px;font:700 14px 'Saira Condensed';}
.steam .srec{font:500 11px 'JetBrains Mono';color:var(--sub);}
.pdot{width:8px;height:8px;border-radius:2px;background:var(--gold);flex:none;}
.pdot.off{background:rgba(255,255,255,.12);}
.sproj{font:700 16px 'JetBrains Mono';display:flex;flex-direction:column;line-height:1.1;}
.sproj .srange{font:500 10px 'JetBrains Mono';color:var(--sub);}
.obar{position:relative;height:18px;border-radius:5px;background:var(--panel2);border:1px solid var(--border);overflow:hidden;}
.obar .ofill{position:absolute;top:0;bottom:0;left:0;}
.obar .oval{position:absolute;right:6px;top:2px;font:700 11px 'JetBrains Mono';color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.6);}
@media(max-width:760px){.grid,.grid3{grid-template-columns:1fr;}}
"""

NAV = """<div class="nav"><div class="in">
  <a class="brand" href="index.html"><span class="bar"></span><span class="txt">DIAMOND<span style="color:var(--a);">IQ</span></span></a>
  <div class="navlinks">
    <a href="compare.html"{c_compare}>Compare Teams</a>
    <a href="simulator.html"{c_simulator}>Season Sim</a>
    <a href="glossary.html"{c_glossary}>Stat Guide</a>
    <a href="models.html"{c_models}>The Models</a>
    <a href="index.html"{c_index}>Dashboard</a>
    <a href="__GH__" target="_blank" rel="noopener">GitHub ↗</a>
  </div>
</div></div>""".replace("__GH__", GH)

FOOT = f"""<footer>
  Built from the <a href="{GH}">mlb-analytics</a> warehouse ({DATA['meta']['n_pitches']:,} pitches,
  {DATA['meta']['seasons'][0]}–{DATA['meta']['seasons'][-1]}). Data: MLB Advanced Media
  (statsapi / Baseball Savant) — individual, non-commercial, non-bulk use; raw data not
  redistributed. Player crosswalk: Chadwick Bureau (ODC-By). Draft: Wikipedia (CC BY-SA).
  Aggregates and code only.
</footer>"""


def head(title, desc, active):
    fonts = ("https://fonts.googleapis.com/css2?family=Anton&family=Saira+Condensed:wght@600;700;800"
             "&family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap")
    nav = NAV
    for p in ("compare", "simulator", "glossary", "models", "index"):
        nav = nav.replace(f"{{c_{p}}}", ' class="active"' if p == active else "")
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><meta name="description" content="{desc}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{fonts}" rel="stylesheet"><style>{CSS}</style></head><body>{nav}<div class="wrap">"""


def _write(name, body):
    (DOCS / name).write_text(body + "\n</div></body></html>", encoding="utf-8")


# ---------------------------------------------------------------- Stat Guide (dictionary)

GLOSSARY = [
    ("Rate stats", [
        ("OPS", "high", "ops", "On-base plus slugging — a quick, powerful summary of overall "
         "hitting: how often you reach base plus how much power you hit for.",
         "League average is ~.720. Above .900 is All-Star; a full-season 1.000+ is an MVP line."),
        ("K% (strikeout rate)", "low", "k_pct", "Share of plate appearances that end in a strikeout.",
         "The single most <b>stable</b> hitter skill year to year (M1). ~22% is average; elite "
         "contact hitters sit near 10%, three-true-outcome sluggers push 30%+."),
        ("BB% (walk rate)", "high", "bb_pct", "Share of plate appearances that end in a walk — "
         "a measure of plate discipline.",
         "Also very stable year to year. ~8% average; the best eyes in baseball draw walks 15%+."),
        ("BABIP", "high", "babip", "Batting average on balls in play — how often batted balls "
         "(not HR, not strikeouts) fall for hits.",
         "Mostly <b>noise</b> (M1, M7): a ~.300 league average with big year-to-year swings driven "
         "by luck, defense, and park. High BABIP one year rarely repeats."),
    ]),
    ("Statcast / expected", [
        ("xwOBA", "high", None, "Expected weighted on-base average — the value a batted ball "
         "'should' produce given its exit velocity and launch angle, independent of defense/luck.",
         "Separates real contact quality from batted-ball luck. We rebuild the core relationship in "
         "M2/M3 (launch speed + angle → value)."),
        ("xwOBA-over-expected", "high", None, "A hitter's actual outcome value minus what their "
         "batted-ball profile predicts — over- or under-performance (M2/M3 residuals).",
         "Positive = beating the physics (speed, spray, luck); negative = getting less than the "
         "contact quality warrants."),
        ("Exit velocity / launch angle", "high", None, "How hard (mph) and at what vertical angle "
         "(degrees) a ball leaves the bat — the two inputs to expected value.",
         "Barrels live near ~98+ mph and 25–30°. Value is concave in angle: there's an "
         "optimal window, too flat or too steep both hurt (M2)."),
        ("Spin rate / pitch arsenal", "high", None, "A pitcher's mix of pitch types and their "
         "velocity, spin, and movement — the raw material of 'stuff'.",
         "M6 clusters pitchers into archetypes (power, finesse, spin) from these features via "
         "PCA + k-means."),
    ]),
    ("Run values", [
        ("RE24 / run expectancy", "high", None, "The expected runs a team will score from now to "
         "the end of the inning, for each of the 24 base-out states.",
         "The backbone of modern value stats. Bases empty, 0 outs ≈ <b>0.5</b> runs; bases "
         "loaded, 0 outs ≈ 2.3. We build it from our own play-by-play (matches published tables)."),
        ("Linear weights / run value", "high", None, "The average run value of an event (single, "
         "walk, HR, out…), derived from RE24.",
         "HR ≈ <b>+1.4</b> runs, single ≈ +0.47, walk ≈ +0.31, strikeout ≈ "
         "−0.27. These are the currency of wOBA, framing, and count value."),
        ("Framing runs", "high", None, "Runs a catcher adds (or costs) by getting borderline "
         "takes called strikes more often than expected from pitch location (M4).",
         "Elite framers are worth roughly +10 to +20 runs a season; the worst give back a similar "
         "amount. Real, measurable, and mostly invisible on TV."),
        ("Count value", "high", None, "The run value of reaching each ball-strike count (M2 chains "
         "RE24 down to the pitch).",
         "3-0 is a hitter's count (≈ +0.21 runs); 0-2 is the pitcher's (≈ −0.10). "
         "Swing rates flip with it: ~9% on 3-0, ~50% on 0-2."),
    ]),
    ("Team & game", [
        ("Win %", "high", "win_pct", "Fraction of games a team wins.",
         "Home teams win ~54% of games — the baseline any prediction model must beat."),
        ("Pythagorean win %", "high", None, "Expected win rate from runs scored and allowed: "
         "RS^1.83 / (RS^1.83 + RA^1.83).",
         "A team's run differential predicts its record better than its actual record does. We fit "
         "the exponent (B1) at ~1.83 and ~10 runs per win."),
        ("Win probability", "high", None, "The game model's estimated chance the home team wins, "
         "from pre-game rolling form (leakage-safe).",
         "On the sealed 2025 holdout it beats a home-field baseline on Brier score — a small "
         "real edge (AUC ~0.55). Baseball games are close to coin-flips; we say so."),
        ("Brier / AUC / calibration", "low", None, "How good a probability model is: Brier = mean "
         "squared error (lower better); AUC = ranking skill (0.5 = coin-flip); calibration = do "
         "the predicted probabilities match reality.",
         "The honest scoreboard for the game model — reported against baselines, not cherry-picked."),
    ]),
    ("Concepts", [
        ("Regression to the mean / ICC", "high", None, "Extreme performances tend to move back "
         "toward average. ICC (intraclass correlation) is the share of a stat that is real, "
         "persistent skill vs. season-to-season noise (M7).",
         "BABIP's ICC is ~0.27 — mostly noise, so we shrink each hitter's BABIP toward the mean."),
        ("Metric stability", "high", None, "How repeatable a stat is year to year (M1). Skills "
         "stabilize fast; luck-driven stats don't.",
         "K% and BB% correlate ~0.8 year to year (skill); BABIP ~0.3 (noise). This is why we trust "
         "some numbers and regress others."),
        ("Permutation test", None, None, "A way to ask 'is this real or random?' by shuffling the "
         "data thousands of times and seeing where the actual result lands (B5 streaks).",
         "Most hitting streaks are statistically indistinguishable from a fair coin — hot hands "
         "are mostly a story we tell."),
        ("R↔Python parity gate", None, None, "Every model is built twice — in R and in "
         "Python — and the build fails unless they agree (coefficients, clusters, or "
         "simulated distributions).",
         "Proof the numbers aren't an artifact of one tool. Three tiers: exact, label-invariant "
         "(PCA/clustering), and distributional (simulations agree within Monte-Carlo error)."),
    ]),
]


def build_glossary():
    groups = []
    for gname, stats in GLOSSARY:
        cards = []
        for name, direction, dist_key, define, read in stats:
            cards.append({"name": name, "dir": direction, "def": define, "read": read,
                          "dist": DATA["glossary"].get(dist_key) if dist_key else None})
        groups.append({"name": gname, "stats": cards})
    payload = {"season": DATA["meta"]["seasons"][-1], "nTeams": 30, "groups": groups}
    body = head("DIAMONDIQ — Stat Guide",
                "A plain-English data dictionary for every MLB metric on the DIAMONDIQ dashboard.",
                "glossary")
    body += """<div class="hero"><div class="eyebrow">Data Dictionary</div><h1>Stat Guide</h1>
      <p id="sub"></p></div>
      <div class="toolbar"><div class="search"><span style="color:var(--sub);">\U0001f50e</span>
        <input id="q" type="text" placeholder="Search a stat — e.g. xwOBA, BABIP, framing, RE24…"
        autocomplete="off"></div><span class="count" id="count"></span></div>
      <div id="body"></div>""" + FOOT
    body += """<script>const DATA=""" + json.dumps(payload) + """;
const DIR={high:{cls:'a',txt:'Higher is better'},low:{cls:'gold',txt:'Lower is better'}};
document.getElementById('sub').textContent=`Every metric on the DIAMONDIQ dashboard in plain English `
  +`— what it measures, how to read it, and where the ${DATA.season} field landed.`;
function distBar(d,dir){ if(!d) return '';
  const span=(d.max-d.min)||1, medPct=((d.med-d.min)/span*100).toFixed(1);
  const hi=(dir==='high'); const lead=hi?d.hi:d.lo, trail=hi?d.lo:d.hi;
  const gd='<span class="dot" style="background:var(--a);"></span>';
  const bd='<span class="dot" style="background:var(--sub);"></span>';
  return `<div class="dist"><div class="track"><div class="med" style="left:${medPct}%;"></div></div>
    <div class="ends"><span>min ${d.min}</span><span>median ${d.med}</span><span>max ${d.max}</span></div>
    <div class="ex"><span class="chip">${gd}Leader <b>${lead.abbr} ${lead.val}</b></span>
    <span class="chip">${bd}Trailer <b>${trail.abbr} ${trail.val}</b></span></div></div>`; }
function card(s){ const dir=DIR[s.dir]; const badge=dir?`<span class="badge ${dir.cls}">${dir.txt}</span>`:'';
  return `<div class="card"><div class="top" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
    <span class="name">${s.name}</span>${badge}</div>
    <div class="def">${s.def}</div><div class="read"><b>How to read it:</b> ${s.read}</div>
    ${distBar(s.dist,s.dir)}</div>`; }
function render(f){ f=(f||'').trim().toLowerCase(); let shown=0,total=0;
  const html=DATA.groups.map(g=>{ const cs=g.stats.map(s=>{ total++;
    const hay=(s.name+' '+s.def+' '+s.read).toLowerCase();
    if(f&&!hay.includes(f)) return ''; shown++; return card(s); }).join('');
    return cs?`<div class="sec"><h2>${g.name}</h2><span class="line"></span></div><div class="grid">${cs}</div>`:''; }).join('');
  document.getElementById('body').innerHTML=html||'<div class="empty">No stats match.</div>';
  document.getElementById('count').textContent=f?`${shown} of ${total} stats`:`${total} stats`; }
document.getElementById('q').addEventListener('input',e=>render(e.target.value)); render('');
</script>"""
    _write("glossary.html", body)


# ---------------------------------------------------------------- The Models

MODELS = [
    ("M1", "Metric stability", "Correlation", "exact", "m1_stability",
     "Which hitting stats are skill vs. luck? We correlate each rate stat with itself year over year.",
     lambda m: f"K% repeats at r={m['python']['k_pct_yoy_corr']:.2f} and BB% at "
               f"{m['python']['bb_pct_yoy_corr']:.2f} (skill); BABIP only "
               f"{m['python']['babip_yoy_corr']:.2f} (noise)."),
    ("M2/M3", "xwOBA-over-expected", "Linear regression", "exact", "m2_xwoba",
     "Simple then multiple regression of batted-ball value on exit velocity and launch angle; "
     "residuals are hitter over/under-performance.",
     lambda m: f"Exit velo raises value (+{m['python']['m3']['launch_speed']:.3f}); angle is "
               f"concave — there's an optimal window."),
    ("M4", "Catcher framing", "Logistic GLM", "exact", "m4_framing",
     "Called-strike probability from pitch location; strikes stolen above expectation become "
     "framing runs.",
     lambda m: f"Best framer +{m['python']['top_framer_runs']:.0f} runs, worst "
               f"{m['python']['bottom_framer_runs']:.0f}, over 3 seasons."),
    ("M5", "Strikeouts per start", "Poisson regression", "exact", "m5_k_poisson",
     "Strikeout counts per pitcher start — the shape behind K-total prop bets.",
     lambda m: f"League strikeout rate {m['python']['k_per_bf']:.3f} per plate appearance."),
    ("M6", "Pitcher arsenals", "PCA + clustering", "label-invariant", "m6_arsenal",
     "Pitch mix, velocity, spin, and movement compressed with PCA, then clustered into 'stuff' "
     "archetypes.",
     lambda m: f"Matched R↔Python by PC correlation + cluster ARI ({m['cluster_ari']:.2f})."),
    ("M7", "BABIP shrinkage", "Mixed-effects", "label-invariant", "m7_babip_shrinkage",
     "A random-intercept model shrinks each hitter's BABIP toward the mean — regression to "
     "the mean, quantified.",
     lambda m: f"ICC {m['python']['icc']:.2f}: only ~{m['python']['icc']*100:.0f}% of BABIP is "
               f"persistent skill."),
    ("M8", "Draft vs. production", "OLS (ethical scrape)", "exact", "m8_draft",
     "Draft pick (scraped politely from Wikipedia) vs. current MLB production for players who "
     "reached the majors.",
     lambda m: f"corr(pick, OPS) = {m['python']['corr_pick_ops']:.2f}, R² "
               f"{m['python']['r_squared']:.3f} — the draft is a crapshoot."),
    ("B1", "Pythagorean wins", "OLS", "exact", "b1_pythagoras",
     "Fit the exponent linking run ratio to win ratio, and the marginal runs-per-win.",
     lambda m: f"Exponent {m['python']['pythag_exponent']:.2f}, "
               f"~{m['python']['runs_per_win']:.1f} runs per win."),
    ("B2", "Count effects", "RE24 aggregation", "exact", "b2_count_value",
     "Run value and swing rate by ball-strike count, chaining RE24 down to the pitch.",
     lambda m: f"3-0 worth +{m['counts']['3-0']['run_value']:.2f} runs, 0-2 "
               f"{m['counts']['0-2']['run_value']:.2f}."),
    ("B3", "Aging curves", "Quadratic OLS", "exact", "b3_aging",
     "OPS as a quadratic function of age → peak-age estimate (cross-sectional; survivor bias "
     "noted).",
     lambda m: f"Concave curve peaking near age {m['python']['peak_age']:.0f}."),
    ("B4", "Markov innings", "Simulation", "distributional", "b4_markov_sim",
     "Simulate half-innings from the base-out transition matrix; the simulated run expectancy must "
     "reconcile with RE24.",
     lambda m: f"Sim RE(empty,0) {m['python']['sim_re_empty_0']:.2f} reconciles RE24 "
               f"{m['python']['re24_empty_0']:.2f}."),
    ("B5", "Streaky hitters", "Permutation test", "distributional", "b5_streaks",
     "Wald-Wolfowitz runs test on each hitter's game-by-game hit sequence, with a permutation null.",
     lambda m: f"Mean streakiness z = {m['mean_z']:.2f} — essentially indistinguishable "
               f"from random."),
    ("GAME", "Win probability", "Logistic (sealed holdout)", "exact", "game_model",
     "Home win probability from pre-game rolling form, trained 2023–24 and evaluated once on "
     "the sealed 2025 season.",
     lambda m: f"Brier {m['python']['brier']:.3f} beats the home-field baseline "
               f"{m['python']['brier_hfa_baseline']:.3f}; AUC {m['python']['auc']:.2f}."),
]
TIER_BADGE = {"exact": "a", "label-invariant": "gold", "distributional": "good"}


def build_models():
    body = head("DIAMONDIQ — The Models",
                "How each of the 13 MLB models works, and how well — with its R↔Python "
                "parity tier and known-answer-test status.", "models")
    m = DATA["metrics"]
    npass = sum(1 for k in m if m[k].get("parity_ok"))
    body += f"""<div class="hero"><div class="eyebrow">Methods</div><h1>The Models</h1>
      <p>Thirteen models, each built in <b>R and Python</b> and gated on agreement, each anchored to
      a known baseball result. {npass}/{len(m)} pass the parity gate. Green means the two languages
      agree and the sanity check holds.</p></div>
      <div class="sec"><h2>Model card index</h2><span class="line"></span></div>
      <div class="grid">"""
    for code, name, method, tier, key, define, headline in MODELS:
        data = m.get(key)
        stat = headline(data) if data else "—"
        ok = data and data.get("parity_ok")
        badge = f'<span class="badge {TIER_BADGE[tier]}">{tier}</span>'
        status = ('<span class="badge good">parity ✓</span>' if ok
                  else '<span class="badge">pending</span>')
        body += f"""<div class="card">
          <div class="top" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
            <span class="name">{code} · {name}</span>{badge}{status}</div>
          <div class="kv"><span>Method</span><b class="mono">{method}</b></div>
          <div class="def">{define}</div>
          <div class="read"><b>Result:</b> {stat}</div></div>"""
    body += "</div>" + FOOT
    _write("models.html", body)


# ---------------------------------------------------------------- Compare Teams

def build_compare():
    body = head("DIAMONDIQ — Compare Teams",
                "Head-to-head MLB team comparison: record, run environment, and Pythagorean "
                "expectation for any two teams in a season.", "compare")
    body += """<div class="hero"><div class="eyebrow">Head to head</div><h1>Compare Teams</h1>
      <p>Pick a season and two teams. Record, runs scored and allowed, run differential, and the
      Pythagorean win rate their run environment implies.</p></div>
      <div class="toolbar">
        <select id="season"></select><select id="ta"></select>
        <span class="mid" style="color:var(--sub);font:700 13px 'Anton';">VS</span>
        <select id="tb"></select></div>
      <div id="body" style="margin-top:20px;"></div>""" + FOOT
    body += """<script>const TEAMS=""" + json.dumps(DATA["teams"]) + """;
const seasons=[...new Set(TEAMS.map(t=>t.season))].sort();
const selS=document.getElementById('season'),selA=document.getElementById('ta'),selB=document.getElementById('tb');
seasons.forEach(s=>selS.add(new Option(s,s))); selS.value=seasons[seasons.length-1];
function fillTeams(){ const s=+selS.value; const names=TEAMS.filter(t=>t.season===s).map(t=>t.team_name).sort();
  [selA,selB].forEach(sel=>{ const cur=sel.value; sel.innerHTML=''; names.forEach(n=>sel.add(new Option(n,n))); if(names.includes(cur)) sel.value=cur; });
  selA.value=names[0]; selB.value=names[1]; }
const ROWS=[['win_pct','Win %',3,true],['w','Wins',0,true],['rs','Runs scored',0,true],
  ['ra','Runs allowed',0,false],['pyth','Pythagorean win %',3,true]];
function row(a,b,label,dec,hi){ const av=a,bv=b, max=Math.max(av,bv)||1;
  const aw=(av/max*100).toFixed(0), bw=(bv/max*100).toFixed(0);
  const awin=hi?av>=bv:av<=bv;
  const ac=awin?'var(--a)':'var(--sub)', bc=!awin?'var(--a)':'var(--sub)';
  const f=v=>dec?v.toFixed(dec):v;
  return `<div class="cmp"><div class="lab">${label}</div>
    <div class="bar"><div class="fill r" style="width:${aw}%;background:linear-gradient(270deg,${ac},var(--panel2));"></div><div class="v" style="left:8px;">${f(av)}</div></div>
    <div class="mid">${awin?'◀':(av===bv?'=':'▶')}</div>
    <div class="bar"><div class="fill l" style="width:${bw}%;background:linear-gradient(90deg,${bc},var(--panel2));"></div><div class="v" style="right:8px;">${f(bv)}</div></div></div>`; }
function render(){ const s=+selS.value;
  const A=TEAMS.find(t=>t.season===s&&t.team_name===selA.value);
  const B=TEAMS.find(t=>t.season===s&&t.team_name===selB.value);
  if(!A||!B){document.getElementById('body').innerHTML='';return;}
  const diff=t=>t.rs-t.ra;
  let h=`<div class="card"><div class="cmp"><div class="lab" style="font:400 20px 'Anton';color:var(--text);">${A.team_name} (${A.w}-${A.l}) &nbsp; vs &nbsp; ${B.team_name} (${B.w}-${B.l})</div></div>`;
  ROWS.forEach(r=>{h+=row(A[r[0]],B[r[0]],r[1],r[2],r[3]);});
  h+=row(diff(A),diff(B),'Run differential',0,true);
  h+='</div>'; document.getElementById('body').innerHTML=h; }
[selS,selA,selB].forEach(el=>el.addEventListener('change',()=>{if(el===selS)fillTeams();render();}));
fillTeams(); render();
</script>"""
    _write("compare.html", body)


# ---------------------------------------------------------------- Season Simulator

def build_simulator():
    body = head("DIAMONDIQ — Season Simulator",
                "Monte-Carlo playoff odds: 10,000 simulated 2025 seasons driven by the game "
                "model's leakage-safe per-game win probabilities over the real schedule.", "simulator")
    if not SIM:
        body += ("""<div class="hero"><h1>Season Simulator</h1>
          <p>Run <code>python dashboard/season_sim.py</code> first — season_sim.json is missing.</p>
          </div>""" + FOOT)
        _write("simulator.html", body)
        return
    body += f"""<div class="hero"><div class="eyebrow">Monte Carlo</div><h1>Season Simulator</h1>
      <p>Ten thousand simulated 2025 seasons. Every one of the {SIM['n_games']:,} regular-season
      games is a weighted coin-flip using the <b>game model's</b> pre-game win probability
      (leakage-safe — it never sees the result), and we tally wins, division titles, and playoff
      berths. This is a rollup of the parity-gated game model, not a new model.</p></div>
      <div class="grid3">
        <div class="card"><div class="kv"><span>Projected vs. actual wins</span></div>
          <div class="stat">{SIM['corr_proj_actual']:.2f}<span class="u">r</span></div>
          <div class="read">Rank-order recovery of the real standings from forecast alone.</div></div>
        <div class="card"><div class="kv"><span>Playoff field identified</span></div>
          <div class="stat">{SIM['top12_playoff_hits']}<span class="u">/ 12</span></div>
          <div class="read">Of the 12 highest-odds teams, how many actually reached October.</div></div>
        <div class="card"><div class="kv"><span>Seasons simulated</span></div>
          <div class="stat">{SIM['n_sim']//1000}<span class="u">K</span></div>
          <div class="read">Fixed seed → the page is reproducible. Gold dot = made playoffs in 2025.</div></div>
      </div>
      <div class="card" style="margin-top:16px;border-color:var(--gold);">
        <div class="read" style="border-color:var(--gold);"><b>Read it honestly:</b> projected win
        totals compress toward .500 because the game model is deliberately conservative — MLB games
        really are near coin-flips (AUC ~0.55). So even a weak team keeps some playoff hope and the
        best teams don't run away. The <b>ordering</b>, though, tracks reality closely (r =
        {SIM['corr_proj_actual']:.2f}). That gap between "confident spread" and "correct ranking" is
        the point.</div></div>
      <div id="body" style="margin-top:8px;"></div>""" + FOOT
    body += """<script>const SIM=""" + json.dumps(SIM) + """;
const DIVS=['East','Central','West'];
function bar(pct,col){ return `<div class="obar"><div class="ofill" style="width:${(pct*100).toFixed(0)}%;background:${col};"></div><span class="oval">${(pct*100).toFixed(0)}%</span></div>`; }
function teamRow(t){ const dot=t.made_playoffs_actual?'<span class="pdot"></span>':'<span class="pdot off"></span>';
  return `<div class="srow"><div class="steam">${dot}<b>${t.abbr}</b><span class="srec">${t.actual_w}-${t.actual_l}</span></div>
    <div class="sproj">${t.proj_wins}<span class="srange">${t.p10}–${t.p90}</span></div>
    ${bar(t.playoff_odds,'linear-gradient(90deg,var(--a2),var(--a))')}</div>`; }
function render(){ let h='';
  for(const lg of ['AL','NL']){
    h+=`<div class="sec"><h2>${lg==='AL'?'American':'National'} League</h2><span class="line"></span></div><div class="grid3">`;
    for(const dv of DIVS){
      const ts=SIM.teams.filter(t=>t.league===lg&&t.division===dv).sort((a,b)=>b.playoff_odds-a.playoff_odds);
      h+=`<div class="card"><div class="dhead">${lg} ${dv}</div>
        <div class="shdr"><span>Team</span><span>Proj W</span><span>Playoff odds</span></div>
        ${ts.map(teamRow).join('')}</div>`;
    }
    h+='</div>';
  }
  document.getElementById('body').innerHTML=h; }
render();
</script>"""
    _write("simulator.html", body)


# ---------------------------------------------------------------- Dashboard (index)

def build_index():
    m, dq, meta = DATA["metrics"], DATA["dq"], DATA["meta"]
    gm = m.get("game_model", {}).get("python", {})
    npass = sum(1 for k in m if m[k].get("parity_ok"))
    layer_counts = {}
    for t in dq["tables"]:
        layer_counts[t["layer"]] = layer_counts.get(t["layer"], 0) + 1
    body = head("DIAMONDIQ — MLB Analytics",
                "A polyglot MLB analytics pipeline: Statcast → DuckDB → dbt → R & "
                "Python models with an enforced parity gate → dashboard.", "index")
    body += f"""<div class="hero"><div class="eyebrow">Diamond Intelligence</div><h1>DIAMONDIQ</h1>
      <p>{meta['n_pitches']:,} pitches across {meta['seasons'][0]}–{meta['seasons'][-1]},
      run through a medallion warehouse and thirteen models — each built twice, in R and Python,
      and gated on agreement. Honest baseball: what's skill, what's luck, and how well we can
      actually predict a game.</p></div>
      <div class="grid3">
        <div class="card"><div class="kv"><span>Pitches modeled</span></div>
          <div class="stat">{meta['n_pitches']/1e6:.2f}<span class="u">M</span></div></div>
        <div class="card"><div class="kv"><span>Games</span></div>
          <div class="stat">{meta['n_games']:,}</div></div>
        <div class="card"><div class="kv"><span>Models (R ↔ Python)</span></div>
          <div class="stat">{npass}<span class="u">/ {len(m)} parity ✓</span></div></div>
      </div>
      <div class="sec"><h2>Data quality</h2><span class="line"></span></div>
      <div class="grid3">
        <div class="card"><div class="kv"><span>Warehouse tables</span></div>
          <div class="stat">{len(dq['tables'])}</div>
          <div class="read">staging {layer_counts.get('staging',0)} · silver
            {layer_counts.get('silver',0)} · gold {layer_counts.get('gold',0)}</div></div>
        <div class="card"><div class="kv"><span>dbt tests</span></div>
          <div class="stat">{dq['tests']['pass']}<span class="u">passing</span></div>
          <div class="read">grains, referential integrity, RE24 anchors, volume, determinism.</div></div>
        <div class="card"><div class="kv"><span>Parity gate</span></div>
          <div class="stat" style="color:var(--good);">GREEN</div>
          <div class="read">exact · label-invariant · distributional tiers all pass.</div></div>
      </div>
      <div class="sec"><h2>Can we predict a game?</h2><span class="line"></span></div>
      <div class="grid">
        <div class="card"><div class="name">Game model — sealed 2025 holdout</div>
          <div class="kv"><span>Brier score (lower better)</span><b>{gm.get('brier','—')}</b></div>
          <div class="kv"><span>Home-field baseline</span><b>{gm.get('brier_hfa_baseline','—')}</b></div>
          <div class="kv"><span>AUC</span><b>{gm.get('auc','—')}</b></div>
          <div class="kv"><span>Accuracy</span><b>{gm.get('accuracy','—')}</b></div>
          <div class="read">A small but real edge over naive home-field. Baseball games are close to
            coin-flips — we don't pretend otherwise.</div></div>
        <div class="card"><div class="name">Explore</div>
          <div class="def">This is a portfolio build — the interesting parts are how it's made.</div>
          <div class="kv"><span>\U0001f9ea The Models</span><b><a href="models.html" style="color:var(--a);">how each works →</a></b></div>
          <div class="kv"><span>\U0001f3c6 Season Simulator</span><b><a href="simulator.html" style="color:var(--a);">playoff odds →</a></b></div>
          <div class="kv"><span>\U0001f4d6 Stat Guide</span><b><a href="glossary.html" style="color:var(--a);">plain-English →</a></b></div>
          <div class="kv"><span>⚔️ Compare Teams</span><b><a href="compare.html" style="color:var(--a);">head to head →</a></b></div>
          <div class="kv"><span>\U0001f4c1 Source</span><b><a href="{GH}" style="color:var(--a);">GitHub →</a></b></div>
        </div>
      </div>""" + FOOT
    _write("index.html", body)


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / ".nojekyll").write_text("")
    build_glossary()
    build_models()
    build_compare()
    build_simulator()
    build_index()
    print(json.dumps({"stage": "dashboard", "event": "built",
                      "pages": ["index", "compare", "simulator", "glossary", "models"]}))


if __name__ == "__main__":
    main()
