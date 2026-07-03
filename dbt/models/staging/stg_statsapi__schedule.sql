-- Game spine, one row per game_pk.
-- Suspended/resumed games appear in bronze under >1 game_date; keep the latest (completion)
-- date so downstream facts have exactly one row per game.
select
    game_pk,
    game_date,
    game_number,
    game_type,
    status,
    home_id,
    home_name,
    away_id,
    away_name,
    cast(left(cast(game_date as varchar), 4) as integer) as season
from {{ source('bronze', 'statsapi_schedule') }}
qualify row_number() over (partition by game_pk order by game_date desc) = 1
