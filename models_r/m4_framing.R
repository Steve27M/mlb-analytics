# M4 - catcher framing (R side of the parity gate).
# Logistic GLM of called-strike probability on pitch location; called strikes above expected,
# valued at ~0.125 runs/strike and summed per catcher, are framing runs.
suppressMessages({
  library(arrow)
  library(dplyr)
  library(jsonlite)
})

RUN_PER_STRIKE <- 0.125
MIN_PITCHES <- 2000

gold <- Sys.getenv("MLB_GOLD_DIR", "data/gold")
res <- Sys.getenv("MLB_RESULTS_DIR", "data/results")
dir.create(res, showWarnings = FALSE, recursive = TRUE)

df <- read_parquet(file.path(gold, "called_pitches.parquet"))
m <- glm(is_called_strike ~ plate_x + plate_z + plate_x_sq + plate_z_sq,
         data = df, family = binomial())

df$pred <- predict(m, type = "response")
df$framing <- (df$is_called_strike - df$pred) * RUN_PER_STRIKE
cs <- df %>%
  group_by(catcher_id, season) %>%
  summarise(runs = sum(framing), pitches = n(), .groups = "drop") %>%
  filter(pitches >= MIN_PITCHES)

co <- coef(m)
out <- list(
  n = nrow(df),
  coef = list(
    intercept = round(co[["(Intercept)"]], 8),
    plate_x = round(co[["plate_x"]], 8),
    plate_z = round(co[["plate_z"]], 8),
    plate_x_sq = round(co[["plate_x_sq"]], 8),
    plate_z_sq = round(co[["plate_z_sq"]], 8)
  ),
  top_framer_runs = round(max(cs$runs), 4),
  bottom_framer_runs = round(min(cs$runs), 4),
  n_qualified = nrow(cs)
)

# digits = 12: preserve precision for EXACT parity (see DECISIONS.md).
write_json(out, file.path(res, "m4_framing__r.json"), auto_unbox = TRUE, pretty = TRUE, digits = 12)
cat(toJSON(c(list(stage = "models_r", model = "m4_framing"), out), auto_unbox = TRUE, digits = 12), "\n")
