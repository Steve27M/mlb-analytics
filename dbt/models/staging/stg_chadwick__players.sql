-- Player-id crosswalk, one row per MLBAM id.
-- Drops the key_mlbam = -1 sentinel (pre-integration / Negro Leagues players with no MLBAM id),
-- which is the only source of key_mlbam non-uniqueness in the register.
select
    key_mlbam       as player_id,
    key_retro       as retrosheet_id,
    key_bbref       as bbref_id,
    key_fangraphs   as fangraphs_id,
    name_first      as first_name,
    name_last       as last_name,
    mlb_played_first,
    mlb_played_last
from {{ source('bronze', 'chadwick_register') }}
where key_mlbam is not null
  and key_mlbam > 0
