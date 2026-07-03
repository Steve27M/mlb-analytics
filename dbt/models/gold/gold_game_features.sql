-- One row per game (grain: game_pk). Game-model design matrix: home-minus-away differences of
-- LEAKAGE-SAFE pre-game rolling form (from gold_team_form, which excludes the current game).
-- Both teams must have >= 10 prior games so the rolling windows are full. Trained on 2023-2024;
-- 2025 is the SEALED holdout (split by season downstream). Features chosen to avoid collinearity
-- (win% is not a linear combination of the RE24 run-value rates); a rank check runs in the model.
with tf as (
    select game_pk, team_id, roll_off_run_value, roll_def_run_value, roll_win_pct,
           roll_runs_for, roll_runs_against, prior_games
    from {{ ref('gold_team_form') }}
),
g as (
    select game_pk, season, home_team_id, away_team_id, cast(home_win as int) as home_win
    from {{ ref('fct_game') }}
    where game_type = 'R' and home_win is not null
)
select
    g.game_pk,
    g.season,
    g.home_win,
    g.home_team_id,   -- team ids carried for the season simulator; the model reads FEATURES only
    g.away_team_id,
    h.roll_off_run_value - a.roll_off_run_value   as off_rv_diff,
    h.roll_def_run_value - a.roll_def_run_value   as def_rv_diff,
    h.roll_win_pct - a.roll_win_pct               as win_pct_diff,
    -- Rolling runs for/against per team (leakage-safe) for the B1-Pythagorean baseline (log5).
    h.roll_runs_for       as home_rs,
    h.roll_runs_against   as home_ra,
    a.roll_runs_for       as away_rs,
    a.roll_runs_against   as away_ra
from g
join tf h on h.game_pk = g.game_pk and h.team_id = g.home_team_id
join tf a on a.game_pk = g.game_pk and a.team_id = g.away_team_id
where h.prior_games >= 10 and a.prior_games >= 10
