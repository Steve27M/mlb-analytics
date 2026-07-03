-- Placeholder-usage guard: the -1 "Unknown Team" member should almost never be used. If real
-- join regressions creep in, placeholder usage rises and this surfaces it. Fails if > 0.5% of
-- team-game rows resolved to the placeholder.
with tg as (
    select
        count(*)                                          as total_rows,
        count(*) filter (where team_id = -1 or opp_id = -1) as placeholder_rows
    from {{ ref('fct_team_game') }}
)
select total_rows, placeholder_rows,
       round(100.0 * placeholder_rows / nullif(total_rows, 0), 3) as pct
from tg
where placeholder_rows > 0.005 * total_rows
