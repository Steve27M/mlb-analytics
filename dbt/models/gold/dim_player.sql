-- dim_player as SCD2: one row per (player_id, affiliation span). When a player's team_id changes
-- between game-dates (trade / call-up / option), the current span closes and a new one opens,
-- bounded to the observed transition date (valid_from of the next span = valid_to of this one).
--
-- Built analytically (window functions) rather than via ~540 daily dbt-snapshot runs: both key
-- off appearance dates, so the daily-grain SCD2 boundaries are identical, but this is one
-- deterministic single pass. See DECISIONS.md (2026-07-03) for the rationale.
with daily as (
    select player_id, game_date, team_id from {{ ref('player_team_daily') }}
),
marked as (
    -- is_change = 1 when the team differs from the previous game-date (null-safe: the first row
    -- has a null lag and opens a new span). Written as `coalesce(lag = team, false)` rather than
    -- `lag is distinct from team` only because sqlfluff's duckdb dialect can't parse the latter
    -- inside a windowed CASE; the two are equivalent here (team_id is never null in this feed).
    select player_id, game_date, team_id,
        case when coalesce(lag(team_id) over (partition by player_id order by game_date)
                           = team_id, false)
             then 0 else 1 end as is_change
    from daily
),
spans as (
    select player_id, game_date, team_id,
        sum(is_change) over (partition by player_id order by game_date
                             rows between unbounded preceding and current row) as span_id
    from marked
),
agg as (
    select player_id, span_id, team_id,
        min(game_date) as valid_from,
        max(game_date) as last_seen_date
    from spans
    group by player_id, span_id, team_id
),
scd as (
    select player_id, team_id, valid_from, last_seen_date,
        lead(valid_from) over (partition by player_id order by valid_from) as valid_to
    from agg
)
select
    {{ dbt_utils.generate_surrogate_key(['scd.player_id', 'scd.valid_from']) }} as player_version_key,
    scd.player_id,
    coalesce(c.first_name || ' ' || c.last_name, 'Unknown Player') as player_name,
    scd.team_id,
    coalesce(t.team_name, 'Unknown Team') as team_name,
    scd.valid_from,
    scd.valid_to,
    scd.last_seen_date,
    (scd.valid_to is null) as is_current
from scd
left join {{ ref('stg_chadwick__players') }} c on c.player_id = scd.player_id
left join {{ ref('dim_team') }} t on t.team_id = scd.team_id
