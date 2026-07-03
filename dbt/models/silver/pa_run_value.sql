-- Per-PA run value from OUR RE24: value = RE(end state) - RE(start state) + runs on the play.
-- End state = the next PA's start state in the same half-inning (0 if the PA ended the inning).
-- This is the KAT-validated linear weight (HR ~1.40, 1B ~0.47). Attributed to the batting team
-- (offense) and the fielding team (defense) so team-level run-value rates can be rolled up.
-- Restricted to complete innings, consistent with the gold_run_expectancy construction.
with pa as (
    select p.*,
        (p.inning * 2 + case when p.inning_topbot = 'Bot' then 1 else 0 end) as half_pos
    from {{ ref('fct_plate_appearance') }} p
),
game_last as (
    select game_pk, max(half_pos) as last_pos from pa group by game_pk
),
seq as (
    select pa.*, gl.last_pos,
        lead(outs_start) over (partition by pa.game_pk, pa.inning, pa.inning_topbot
                               order by at_bat_number) as next_outs,
        lead(base_state) over (partition by pa.game_pk, pa.inning, pa.inning_topbot
                               order by at_bat_number) as next_base
    from pa join game_last gl using (game_pk)
),
g as (
    select game_pk, home_team_id, away_team_id from {{ ref('fct_game') }}
)
select
    s.game_pk,
    s.at_bat_number,
    s.season,
    s.game_date,
    s.game_type,
    case when s.inning_topbot = 'Top' then g.away_team_id else g.home_team_id end as bat_team_id,
    case when s.inning_topbot = 'Top' then g.home_team_id else g.away_team_id end as fld_team_id,
    s.events,
    (coalesce(re_end.run_expectancy, 0) - re_start.run_expectancy + s.runs_on_play) as run_value
from seq s
join g using (game_pk)
join {{ ref('gold_run_expectancy') }} re_start
    on re_start.season = s.season and re_start.outs_start = s.outs_start
    and re_start.base_state = s.base_state
left join {{ ref('gold_run_expectancy') }} re_end
    on re_end.season = s.season and re_end.outs_start = s.next_outs
    and re_end.base_state = s.next_base
where s.half_pos < s.last_pos    -- complete innings only (matches the RE24 truncation guard)
