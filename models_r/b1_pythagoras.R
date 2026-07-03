# B1 - Pythagorean expectation (R side of the parity gate).
# Fit the Pythagorean exponent and marginal runs-per-win from team-season run ratios.
suppressMessages({
  library(arrow)
  library(dplyr)
  library(jsonlite)
})

gold <- Sys.getenv("MLB_GOLD_DIR", "data/gold")
res <- Sys.getenv("MLB_RESULTS_DIR", "data/results")
dir.create(res, showWarnings = FALSE, recursive = TRUE)

df <- read_parquet(file.path(gold, "team_season.parquet")) %>%
  filter(w > 0, l > 0)

# Pythagorean exponent: log(W/L) = k * log(RS/RA), through the origin.
k <- coef(lm(log(w / l) ~ 0 + log(rs / ra), data = df))[[1]]
# Runs per win: (W - G/2) = (RS - RA) / runs_per_win, through the origin.
slope <- coef(lm(I(w - games / 2) ~ 0 + I(rs - ra), data = df))[[1]]

out <- list(
  n_team_seasons = nrow(df),
  pythag_exponent = round(k, 6),
  runs_per_win = round(1 / slope, 4)
)

write_json(out, file.path(res, "b1_pythagoras__r.json"), auto_unbox = TRUE, pretty = TRUE, digits = 12)
cat(toJSON(c(list(stage = "models_r", model = "b1_pythagoras"), out), auto_unbox = TRUE, digits = 12), "\n")
