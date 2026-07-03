-- One row per team per game (grain: game_pk, team_id). The team-level game fact:
-- runs for/against, win flag, pitches. Feeds rolling-form features and the game model.
select
    b.game_pk,
    coalesce(b.team_id, -1)     as team_id,
    coalesce(b.opp_id, -1)      as opp_id,
    g.game_date,
    g.season,
    g.game_type,
    b.is_home,
    b.runs                      as runs_for,
    case when b.is_home then g.away_runs else g.home_runs end as runs_against,
    (g.winner_team_id = b.team_id) as is_win,
    b.hits,
    b.pitches
from {{ ref('stg_statsapi__boxscore') }} b
inner join {{ ref('fct_game') }} g on g.game_pk = b.game_pk
