-- One row per batter per game (grain: batter_id, game_pk). B5 streaks feed: the ordered
-- game-by-game hit/no-hit sequence per batter-season drives a Wald-Wolfowitz runs test and a
-- permutation test for whether specific hitters are unusually streaky.
select
    batter_id,
    season,
    game_pk,
    game_date,
    max(cast(events in ('single', 'double', 'triple', 'home_run') as int)) as got_hit
from {{ ref('fct_plate_appearance') }}
group by batter_id, season, game_pk, game_date
