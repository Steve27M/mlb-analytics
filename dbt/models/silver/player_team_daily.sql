-- Player -> team affiliation per game-date, derived from Statcast appearances.
-- Batting team = away on Top of the inning, home on Bottom; the pitching team is the opposite.
-- A player's team for a date is the one they appeared for most (handles the rare traded-mid-day
-- or two-way-player edge). Feeds the dim_player SCD2 build.
with p as (
    select
        pk.game_date, pk.batter_id, pk.pitcher_id, pk.inning_topbot,
        g.home_team_id, g.away_team_id
    from {{ ref('stg_statcast__pitches') }} pk
    inner join {{ ref('fct_game') }} g on g.game_pk = pk.game_pk
),
batters as (
    select batter_id as player_id, game_date,
           case when inning_topbot = 'Top' then away_team_id else home_team_id end as team_id
    from p
),
pitchers as (
    select pitcher_id as player_id, game_date,
           case when inning_topbot = 'Top' then home_team_id else away_team_id end as team_id
    from p
),
appearances as (
    select * from batters
    union all
    select * from pitchers
),
ranked as (
    select player_id, game_date, team_id, count(*) as appearances,
           row_number() over (partition by player_id, game_date
                              order by count(*) desc, team_id) as rn
    from appearances
    where player_id is not null and team_id is not null
    group by player_id, game_date, team_id
)
select player_id, game_date, team_id, appearances
from ranked
where rn = 1
