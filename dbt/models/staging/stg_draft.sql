-- MLB draft picks (Wikipedia). Cleans the player name (drops "*"/refs), flags pitchers, and
-- builds a normalized name (accent-stripped, alpha-only) for matching to the Chadwick crosswalk.
select
    draft_year,
    pick,
    trim(regexp_replace(player, '\*', '', 'g'))                             as player,
    position,
    (position ilike '%pitcher%')                                           as is_pitcher,
    trim(regexp_replace(lower(strip_accents(player)), '[^a-z ]', '', 'g'))  as norm_name
from {{ source('bronze', 'draft') }}
