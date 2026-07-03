-- Base-out state transitions from play-by-play, for B4's Markov half-inning simulation.
-- State = base_state*3 + outs (0..23); 24 is the absorbing "3 outs" state. Each row is one PA in a
-- COMPLETE half-inning: the state it started in, the state the next batter started in (or 24 if it
-- made the 3rd out), and the runs that scored on the play. Simulating from state 0 must reconcile
-- with gold_run_expectancy (RE(bases empty, 0 outs) ~ 0.5).
with pa as (
    select
        game_pk, inning, inning_topbot, at_bat_number,
        base_state * 3 + outs_start                                       as from_state,
        runs_on_play,
        (inning * 2 + case when inning_topbot = 'Bot' then 1 else 0 end)  as half_pos
    from {{ ref('fct_plate_appearance') }}
    where outs_start in (0, 1, 2)
),
gl as (
    select game_pk, max(half_pos) as last_pos from pa group by game_pk
),
seq as (
    select pa.*, gl.last_pos,
        lead(pa.from_state) over (partition by pa.game_pk, pa.inning, pa.inning_topbot
                                  order by pa.at_bat_number) as next_state
    from pa join gl using (game_pk)
)
select
    from_state,
    coalesce(next_state, 24)  as to_state,   -- null next = made the 3rd out -> absorbing
    runs_on_play              as runs
from seq
where half_pos < last_pos     -- complete half-innings only (matches the RE24 truncation guard)
