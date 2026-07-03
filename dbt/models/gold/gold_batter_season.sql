-- Per-batter-season rate stats (grain: batter_id, season). The M1 metric-stability feed:
-- year-over-year correlation of these rates separates skill (K%, BB% stabilize fast) from
-- noise (BABIP). Derived from plate-appearance outcomes; the model applies the min-PA filter.
with pa as (
    select batter_id, season, events from {{ ref('fct_plate_appearance') }}
),
agg as (
    select
        batter_id,
        season,
        count(*)                                                          as pa,
        count(*) filter (where events in ('strikeout', 'strikeout_double_play')) as k,
        count(*) filter (where events in ('walk', 'intent_walk'))         as bb,
        count(*) filter (where events = 'hit_by_pitch')                   as hbp,
        count(*) filter (where events = 'sac_fly')                        as sf,
        count(*) filter (where events = 'sac_bunt')                       as sh,
        count(*) filter (where events = 'single')                         as singles,
        count(*) filter (where events = 'double')                         as doubles,
        count(*) filter (where events = 'triple')                         as triples,
        count(*) filter (where events = 'home_run')                       as hr
    from pa
    group by batter_id, season
)
select
    batter_id,
    season,
    pa,
    (pa - bb - hbp - sf - sh)                                             as ab,
    (singles + doubles + triples + hr)                                    as h,
    round(k::double / nullif(pa, 0), 6)                                   as k_pct,
    round(bb::double / nullif(pa, 0), 6)                                  as bb_pct,
    -- BABIP = (H - HR) / (AB - K - HR + SF)
    round((singles + doubles + triples)::double
          / nullif((pa - bb - hbp - sf - sh) - k - hr + sf, 0), 6)        as babip,
    -- OPS = OBP + SLG (overall offensive rate; feeds B3 aging curves)
    round((singles + doubles + triples + hr + bb + hbp)::double
          / nullif(pa - sh, 0)                                            -- OBP
          + (singles + 2*doubles + 3*triples + 4*hr)::double
          / nullif(pa - bb - hbp - sf - sh, 0), 6)                        as ops
from agg
