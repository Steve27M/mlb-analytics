# M5 - strikeouts per start (R side of the parity gate).
# Poisson regression of strikeout count on batters faced -> expected K totals per start.
suppressMessages({
  library(arrow)
  library(dplyr)
  library(jsonlite)
})

gold <- Sys.getenv("MLB_GOLD_DIR", "data/gold")
res <- Sys.getenv("MLB_RESULTS_DIR", "data/results")
dir.create(res, showWarnings = FALSE, recursive = TRUE)

df <- read_parquet(file.path(gold, "pitcher_start.parquet"))
m <- glm(k ~ bf, data = df, family = poisson())

co <- coef(m)
out <- list(
  n = nrow(df),
  coef = list(
    intercept = round(co[["(Intercept)"]], 8),
    bf = round(co[["bf"]], 8)
  ),
  mean_k_per_start = round(mean(df$k), 4),
  k_per_bf = round(sum(df$k) / sum(df$bf), 6)
)

# digits = 12: preserve precision for EXACT parity (see DECISIONS.md).
write_json(out, file.path(res, "m5_k_poisson__r.json"), auto_unbox = TRUE, pretty = TRUE, digits = 12)
cat(toJSON(c(list(stage = "models_r", model = "m5_k_poisson"), out), auto_unbox = TRUE, digits = 12), "\n")
