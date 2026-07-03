-- Volume test (Phase 1/2 GATE): every played game must have Statcast pitch data, and Statcast
-- must not be SHORT of the official boxscore pitch count (the dangerous direction = missing
-- pitches). Statcast running a few over is expected (extra tracked pitch-events) and allowed.
-- Fails (returns rows) if any game is missing from Statcast or has fewer pitches than official.
with box as (
    select game_pk, sum(pitches) as box_pitches
    from {{ ref('stg_statsapi__boxscore') }}
    group by game_pk
),
sc as (
    select game_pk, count(*) as statcast_pitches
    from {{ ref('stg_statcast__pitches') }}
    group by game_pk
)
select
    b.game_pk,
    b.box_pitches,
    coalesce(s.statcast_pitches, 0) as statcast_pitches
from box b
left join sc s on s.game_pk = b.game_pk
where s.statcast_pitches is null            -- missing from Statcast
   or s.statcast_pitches < b.box_pitches    -- Statcast short on pitches
