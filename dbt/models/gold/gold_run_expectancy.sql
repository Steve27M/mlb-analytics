-- RE24: the run-expectancy matrix. For each of the 24 base-out states, the expected number of
-- runs scored from that state to the END of the half-inning, computed per season from our own
-- play-by-play (this also yields the linear weights that seed wOBA — see DECISIONS.md).
--
-- runs_to_end(PA) = (batting team's final score in the half-inning) - (its score at PA start).
-- TRUNCATION GUARD (spec-mandated): exclude the LAST half-inning of each game. Walk-offs and
-- rain-shortened games always end there with < 3 outs; including them biases the matrix. This
-- drops ~1 (unbiased) inning/game while removing every truncated inning. KAT-anchored below.
with pa as (
    select *,
        (inning * 2 + case when inning_topbot = 'Bot' then 1 else 0 end) as half_inning_pos
    from {{ ref('fct_plate_appearance') }}
),
half_inning as (
    select game_pk, inning, inning_topbot,
        max(bat_score_post) as final_bat_score
    from pa
    group by game_pk, inning, inning_topbot
),
game_last as (
    select game_pk, max(half_inning_pos) as last_pos
    from pa
    group by game_pk
),
complete as (
    select
        pa.season,
        pa.outs_start,
        pa.base_state,
        pa.base_label,
        (hi.final_bat_score - pa.bat_score_start) as runs_to_end
    from pa
    join half_inning hi
        on hi.game_pk = pa.game_pk
        and hi.inning = pa.inning
        and hi.inning_topbot = pa.inning_topbot
    join game_last gl on gl.game_pk = pa.game_pk
    where pa.half_inning_pos < gl.last_pos          -- exclude the last (truncation-risk) half-inning
      and pa.outs_start in (0, 1, 2)
)
select
    season,
    outs_start,
    base_state,
    base_label,
    count(*)                       as n_occurrences,
    round(avg(runs_to_end), 4)     as run_expectancy
from complete
group by season, outs_start, base_state, base_label
order by season, outs_start, base_state
