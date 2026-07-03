-- One row per batted ball (grain: pitch_key) — the contact pitch of a batted-ball PA.
-- M2/M3 feed: regress outcome value (woba_value) on launch speed + angle. Predicted value is
-- "expected" batted-ball value (xwOBA-on-contact); residuals aggregate to hitter over/under-
-- performance. Statcast's own estimated xwOBA is carried as an external KAT anchor.
-- woba_value is MLBAM's Statcast column (not FanGraphs) — no ToS concern.
select
    pitch_key,
    game_pk,
    at_bat_number,
    batter_id,
    season,
    launch_speed,
    launch_angle,
    woba_value,
    xwoba                               as statcast_xwoba
from {{ ref('stg_statcast__pitches') }}
where launch_speed is not null
  and launch_angle is not null
  and woba_value is not null
