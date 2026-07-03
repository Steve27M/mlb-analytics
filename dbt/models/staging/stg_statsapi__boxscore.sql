-- Team-game boxscore lines, one row per (game_pk, team_id).
-- Dedupes the cross-date duplication of suspended games (same game_pk under two dates), keeping
-- the completion-date row. `pitches` = that team's official numberOfPitches for the game.
select
    game_pk,
    team_id,
    opp_id,
    is_home,
    game_number,
    runs,
    hits,
    pitches
from {{ source('bronze', 'statsapi_boxscore') }}
qualify row_number() over (partition by game_pk, team_id order by game_date desc) = 1
