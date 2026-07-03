-- One row per qualified batter-season (grain: batter_id, season) with age and OPS. B3 aging feed:
-- quadratic OPS-vs-age fit -> peak-age estimate (~26-29). Age = season - birth_year (Chadwick).
-- Cross-sectional over 2023-2025 (short window; survivor bias caveat noted in the model).
select
    bs.batter_id,
    bs.season,
    (bs.season - c.birth_year)   as age,
    bs.ops
from {{ ref('gold_batter_season') }} bs
join {{ ref('stg_people') }} c on c.player_id = bs.batter_id
where bs.pa >= 200
  and bs.ops is not null
  and (bs.season - c.birth_year) between 19 and 44
