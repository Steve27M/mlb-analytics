# M8 - draft position vs production (R side of the parity gate).
# Regress current (2023-2025) OPS on draft pick for drafted position players who reached MLB.
# Honest result: among players who make it, draft position barely predicts production.
suppressMessages({
  library(arrow)
  library(dplyr)
  library(jsonlite)
})

gold <- Sys.getenv("MLB_GOLD_DIR", "data/gold")
res <- Sys.getenv("MLB_RESULTS_DIR", "data/results")
dir.create(res, showWarnings = FALSE, recursive = TRUE)

df <- read_parquet(file.path(gold, "draft_production.parquet"))
m <- lm(ops ~ pick, data = df)
co <- coef(m)

out <- list(
  n = nrow(df),
  coef = list(
    intercept = round(co[["(Intercept)"]], 8),
    pick = round(co[["pick"]], 8)
  ),
  corr_pick_ops = round(cor(df$pick, df$ops), 6),
  r_squared = round(summary(m)$r.squared, 6)
)

write_json(out, file.path(res, "m8_draft__r.json"), auto_unbox = TRUE, pretty = TRUE, digits = 12)
cat(toJSON(c(list(stage = "models_r", model = "m8_draft"), out), auto_unbox = TRUE, digits = 12), "\n")
