-- One row per plate appearance (grain: game_pk, at_bat_number) = the last pitch of the at-bat.
-- Carries the base-out state at the START of the PA (constant through the PA), the batting-team
-- score before/after, and the PA outcome. Feeds gold_run_expectancy (RE24) and the game model.
with last_pitch as (
    select *
    from {{ ref('stg_statcast__pitches') }}
    qualify row_number() over (partition by game_pk, at_bat_number order by pitch_number desc) = 1
),
pa as (
    select
        game_pk,
        at_bat_number,
        season,
        game_date,
        game_type,
        inning,
        inning_topbot,
        batter_id,
        pitcher_id,
        outs_when_up                                              as outs_start,
        (runner_1b_id is not null)                                as on_1b,
        (runner_2b_id is not null)                                as on_2b,
        (runner_3b_id is not null)                                as on_3b,
        -- base state 0..7 = 4*3B + 2*2B + 1*1B
        (case when runner_3b_id is not null then 4 else 0 end
         + case when runner_2b_id is not null then 2 else 0 end
         + case when runner_1b_id is not null then 1 else 0 end)  as base_state,
        bat_score                                                 as bat_score_start,
        -- batting team's post-play score (away bats on Top, home on Bottom)
        coalesce(case when inning_topbot = 'Top' then post_away_score else post_home_score end,
                 bat_score)                                       as bat_score_post,
        events,
        description
    from last_pitch
)
select
    *,
    (bat_score_post - bat_score_start) as runs_on_play,
    case base_state
        when 0 then 'bases empty' when 1 then '1B' when 2 then '2B' when 3 then '1B_2B'
        when 4 then '3B' when 5 then '1B_3B' when 6 then '2B_3B' when 7 then 'loaded'
    end as base_label
from pa
