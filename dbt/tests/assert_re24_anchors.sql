-- Known-answer test for the RE24 matrix (gold_run_expectancy), anchored to published
-- run-expectancy references (Tango tables). Fails (returns rows) if, for any season:
--   (a) RE(bases empty, 0 outs) falls outside the published ~0.48-0.54 band (allow [0.45, 0.56]);
--   (b) run expectancy is not strictly decreasing in outs (0 > 1 > 2) for every base state;
--   (c) the bases-loaded/0-out state is not the maximum, or bases-empty/2-out not the minimum.
-- A plausible-but-wrong RE construction (e.g. failing to exclude truncated innings) trips this.
with re as (
    select * from {{ ref('gold_run_expectancy') }}
),
empty_band as (
    select season, 'RE(empty,0out) out of [0.45,0.56]' as violation
    from re
    where base_state = 0 and outs_start = 0
      and (run_expectancy < 0.45 or run_expectancy > 0.56)
),
by_state as (
    select season, base_state,
        max(run_expectancy) filter (where outs_start = 0) as o0,
        max(run_expectancy) filter (where outs_start = 1) as o1,
        max(run_expectancy) filter (where outs_start = 2) as o2
    from re group by season, base_state
),
monotonic as (
    select season, 'RE not monotonic in outs' as violation
    from by_state
    where not (o0 > o1 and o1 > o2)
),
extremes as (
    select season, 'loaded/0out not max or empty/2out not min' as violation
    from re
    group by season
    having max(run_expectancy) <> max(run_expectancy) filter (where base_state = 7 and outs_start = 0)
        or min(run_expectancy) <> min(run_expectancy) filter (where base_state = 0 and outs_start = 2)
)
select season, violation from empty_band
union all select season, violation from monotonic
union all select season, violation from extremes
