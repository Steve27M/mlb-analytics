-- One row per played game (grain: game_pk). Final reg/post games only.
-- Winner derived from boxscore runs; team ids COALESCE to the -1 placeholder on any join miss.
with sched as (
    select * from {{ ref('stg_statsapi__schedule') }} where status = 'Final'
),
home_box as (
    select game_pk, runs, pitches from {{ ref('stg_statsapi__boxscore') }} where is_home
),
away_box as (
    select game_pk, runs, pitches from {{ ref('stg_statsapi__boxscore') }} where not is_home
)
select
    s.game_pk,
    s.game_date,
    s.season,
    s.game_type,
    s.game_number,
    coalesce(s.home_id, -1)                                  as home_team_id,
    coalesce(s.away_id, -1)                                  as away_team_id,
    hb.runs                                                  as home_runs,
    ab.runs                                                  as away_runs,
    case
        when hb.runs > ab.runs then coalesce(s.home_id, -1)
        when ab.runs > hb.runs then coalesce(s.away_id, -1)
    end                                                      as winner_team_id,
    (hb.runs > ab.runs)                                     as home_win,
    coalesce(hb.pitches, 0) + coalesce(ab.pitches, 0)       as total_pitches
from sched s
left join home_box hb on hb.game_pk = s.game_pk
left join away_box ab on ab.game_pk = s.game_pk
