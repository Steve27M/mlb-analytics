
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
