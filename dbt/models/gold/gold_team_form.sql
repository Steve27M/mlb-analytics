-- Rolling team-form features, one row per (game_pk, team_id). LEAKAGE-SAFE: every feature is a
-- trailing average over the team's PRIOR up-to-10 games (window ends at "1 preceding", so the
-- current game is never in its own features). Games are ordered by (game_date, game_number,
-- game_pk) — game_number is the doubleheader tiebreaker and game_pk makes the order TOTAL, so the
-- feed is byte-identical across rebuilds (guarded by assert_team_form_order_is_total).
-- Run values are summed as scaled INTEGERS (micro-runs). Integer addition is associative, so the
-- sum is identical regardless of DuckDB's parallel execution order — this is what makes the feed
-- deterministic (float sums varied by ~1e-15 across rebuilds; rounding alone can't fix boundary
-- flips). Converted back to runs (/1e6) at the end.
with rv_off as (
    select game_pk, bat_team_id as team_id,
           sum(cast(round(run_value * 1000000) as bigint)) as off_rv_micro
    from {{ ref('pa_run_value') }} group by game_pk, bat_team_id
),
rv_def as (
    select game_pk, fld_team_id as team_id,
           sum(cast(round(run_value * 1000000) as bigint)) as def_rv_micro
    from {{ ref('pa_run_value') }} group by game_pk, fld_team_id
),
team_game as (
    select
        tg.game_pk, tg.team_id, tg.season, tg.game_date,
        g.game_number,
        tg.runs_for, tg.runs_against,
        case when tg.is_win then 1.0 else 0.0 end as win,
        o.off_rv_micro, d.def_rv_micro
    from {{ ref('fct_team_game') }} tg
    join {{ ref('fct_game') }} g on g.game_pk = tg.game_pk
    left join rv_off o on o.game_pk = tg.game_pk and o.team_id = tg.team_id
    left join rv_def d on d.game_pk = tg.game_pk and d.team_id = tg.team_id
)
select
    game_pk,
    team_id,
    season,
    game_date,
    game_number,
    row_number() over w                            as game_seq,
    count(*)                       over w_prior     as prior_games,
    -- Round all rolling outputs to 6 dp. The float run-value averages otherwise vary by ~1e-15
    -- across rebuilds (DuckDB parallel float summation is non-associative); rounding 9 orders of
    -- magnitude above that noise floor makes the feed byte-identical (see run.py determinism).
    round(avg(runs_for)      over w_prior, 6)         as roll_runs_for,
    round(avg(runs_against)  over w_prior, 6)         as roll_runs_against,
    round(avg(win)           over w_prior, 6)         as roll_win_pct,
    -- avg of exact integer micro-sums / 1e6 -> deterministic run-value rate
    round(avg(off_rv_micro)  over w_prior / 1000000.0, 6) as roll_off_run_value,
    round(avg(def_rv_micro)  over w_prior / 1000000.0, 6) as roll_def_run_value
from team_game
window
    w as (partition by team_id, season order by game_date, game_number, game_pk),
    w_prior as (partition by team_id, season order by game_date, game_number, game_pk
                rows between 10 preceding and 1 preceding)
