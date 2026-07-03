-- Player birth years (grain: player_id). Source of age for B3 aging curves.
select
    player_id,
    birth_year
from {{ source('bronze', 'people') }}
where birth_year is not null
