# B3 - aging curves (R side of the parity gate).
# Quadratic fit of OPS on age -> peak-age estimate (cross-sectional; survivor bias noted).
suppressMessages({
  library(arrow)
  library(dplyr)
  library(jsonlite)
})

gold <- Sys.getenv("MLB_GOLD_DIR", "data/gold")
res <- Sys.getenv("MLB_RESULTS_DIR", "data/results")
dir.create(res, showWarnings = FALSE, recursive = TRUE)

df <- read_parquet(file.path(gold, "player_age.parquet")) %>%
  mutate(age_sq = age^2)
m <- lm(ops ~ age + age_sq, data = df)
co <- coef(m)

out <- list(
  n = nrow(df),
  coef = list(
    intercept = round(co[["(Intercept)"]], 8),
    age = round(co[["age"]], 8),
    age_sq = round(co[["age_sq"]], 8)
  ),
  peak_age = round(-co[["age"]] / (2 * co[["age_sq"]]), 4),
  r_squared = round(summary(m)$r.squared, 6)
)

write_json(out, file.path(res, "b3_aging__r.json"), auto_unbox = TRUE, pretty = TRUE, digits = 12)
cat(toJSON(c(list(stage = "models_r", model = "b3_aging"), out), auto_unbox = TRUE, digits = 12), "\n")
