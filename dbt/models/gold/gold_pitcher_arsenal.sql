-- Per-pitcher-season arsenal features (grain: pitcher_id, season). M6 feed: PCA + clustering
-- into pitch-mix / stuff archetypes. Requires >= 500 pitches for stable features.
with p as (
    select pitcher_id, season, pitch_type, release_speed, release_spin_rate, pfx_x, pfx_z
    from {{ ref('stg_statcast__pitches') }}
    where release_speed is not null
),
agg as (
    select
        pitcher_id,
        season,
        count(*)                                                          as pitches,
        avg(release_speed)                                                as velo,
        avg(release_spin_rate)                                            as spin,
        avg(abs(pfx_x))                                                   as h_move,
        avg(pfx_z)                                                        as v_move,
        count(*) filter (where pitch_type in ('FF', 'SI', 'FC'))::double
            / count(*)                                                    as fastball_pct,
        count(*) filter (where pitch_type in ('SL', 'CU', 'KC', 'ST', 'SV', 'CS'))::double
            / count(*)                                                    as breaking_pct,
        count(distinct pitch_type)                                        as n_pitch_types
    from p
    group by pitcher_id, season
)
select *
from agg
where pitches >= 500
  and spin is not null
