-- One row per team-season (grain: team_id, season). B1 Pythagorean feed: wins/losses and
-- runs scored/allowed -> fit the Pythagorean exponent and marginal runs-per-win.
select
    team_id,
    season,
    count(*)                                  as games,
    sum(case when is_win then 1 else 0 end)   as w,
    sum(case when is_win then 0 else 1 end)   as l,
    sum(runs_for)                             as rs,
    sum(runs_against)                         as ra
from {{ ref('fct_team_game') }}
where team_id <> -1
  and game_type = 'R'   -- Pythagorean is a regular-season relationship; exclude postseason
group by team_id, season
