-- Taken pitches (batter did not swing) with location, for M4 catcher framing.
-- Logistic P(called strike | location); called strikes above the location-expected rate, summed
-- per catcher and valued at ~0.125 runs/strike, are framing runs. Grain: pitch_key.
select
    pitch_key,
    season,
    catcher_id,
    plate_x,
    plate_z,
    plate_x * plate_x                        as plate_x_sq,
    plate_z * plate_z                        as plate_z_sq,
    cast(description = 'called_strike' as int) as is_called_strike
from {{ ref('stg_statcast__pitches') }}
where description in ('ball', 'called_strike', 'blocked_ball')
  and plate_x is not null
  and plate_z is not null
  and catcher_id is not null
