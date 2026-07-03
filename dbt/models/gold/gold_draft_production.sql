-- Drafted position players matched to their CURRENT (2023-2025) MLB production (grain: player_id).
-- M8 feed: does draft pick predict production among players who reached the majors? (Only current
-- production is available in a 2023-2025 warehouse — full career would need Lahman; see PREFLIGHT.)
-- Name-matched to the Chadwick crosswalk on a normalized (accent-stripped) name.
with draft as (
    select * from {{ ref('stg_draft') }} where not is_pitcher
),
ch as (
    select
        player_id,
        trim(regexp_replace(lower(strip_accents(first_name || ' ' || last_name)),
                            '[^a-z ]', '', 'g')) as norm_name
    from {{ ref('stg_chadwick__players') }}
    where mlb_played_last is not null
),
prod as (
    select batter_id, sum(pa) as pa, sum(ops * pa) / nullif(sum(pa), 0) as ops
    from {{ ref('gold_batter_season') }}
    group by batter_id
)
select player_id, draft_year, pick, player, pa, round(ops, 6) as ops
from (
    select ch.player_id, d.draft_year, d.pick, d.player, prod.pa, prod.ops
    from draft d
    join ch on ch.norm_name = d.norm_name
    join prod on prod.batter_id = ch.player_id
    where prod.pa >= 200
)
qualify row_number() over (partition by player_id order by draft_year, pick) = 1
