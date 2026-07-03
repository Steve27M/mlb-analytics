-- Pitch-level count feed for B2 count effects. Each pitch is tagged with (a) whether the batter
-- swung and (b) its plate appearance's RE24 run value (chaining RE24 down to the count). R and
-- Python each aggregate to run-value-by-count + swing-rate-by-count tables (exact-tier parity):
-- counts a hitter reaches (3-0) carry higher PA run value than pitcher's counts (0-2).
select
    s.balls,
    s.strikes,
    cast(s.description in ('swinging_strike', 'swinging_strike_blocked', 'foul', 'foul_tip',
                           'hit_into_play', 'foul_bunt', 'missed_bunt', 'bunt_foul_tip')
         as int)                                as is_swing,
    rv.run_value                                as pa_run_value
from {{ ref('stg_statcast__pitches') }} s
join {{ ref('pa_run_value') }} rv
    on rv.game_pk = s.game_pk and rv.at_bat_number = s.at_bat_number
where s.balls between 0 and 3
  and s.strikes between 0 and 2
