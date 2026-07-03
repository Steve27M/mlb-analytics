-- One row per pitcher start (grain: game_pk, pitcher_id). M5 feed: Poisson regression of
-- strikeout count on batters faced -> expected K totals (prop-bet framing). BF >= 15 filters to
-- starters (relievers rarely face 15+); documented proxy for "start" without a role table.
select
    game_pk,
    pitcher_id,
    season,
    count(*)                                                             as bf,
    count(*) filter (where events in ('strikeout', 'strikeout_double_play')) as k
from {{ ref('fct_plate_appearance') }}
group by game_pk, pitcher_id, season
having count(*) >= 15
