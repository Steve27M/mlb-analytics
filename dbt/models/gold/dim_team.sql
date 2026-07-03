-- Team dimension, one row per team_id. Includes an "Unknown Team" placeholder (-1) so fact
-- rows that fail a team join COALESCE to it instead of dropping (tested < 0.5% in _gold.yml).
with observed as (
    select home_id as team_id, home_name as team_name from {{ ref('stg_statsapi__schedule') }}
    union
    select away_id as team_id, away_name as team_name from {{ ref('stg_statsapi__schedule') }}
),
teams as (
    select team_id, max(team_name) as team_name
    from observed
    where team_id is not null
    group by team_id
)
select team_id, team_name from teams
union all
select -1 as team_id, 'Unknown Team' as team_name
