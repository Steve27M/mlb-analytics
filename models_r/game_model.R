# Game win-probability model (R side of the parity gate).
# Logistic model of home win from home-minus-away pre-game rolling form (leakage-safe). Trained on
# 2023-2024; evaluated once on the sealed 2025 holdout. Benchmarked against a home-field baseline.
suppressMessages({
  library(arrow)
  library(dplyr)
  library(jsonlite)
})

gold <- Sys.getenv("MLB_GOLD_DIR", "data/gold")
res <- Sys.getenv("MLB_RESULTS_DIR", "data/results")
dir.create(res, showWarnings = FALSE, recursive = TRUE)

df <- read_parquet(file.path(gold, "game_features.parquet"))
train <- df %>% filter(season %in% c(2023, 2024))
test <- df %>% filter(season == 2025)   # sealed holdout

m <- glm(home_win ~ off_rv_diff + def_rv_diff + win_pct_diff, data = train, family = binomial())
pred <- predict(m, newdata = test, type = "response")
yte <- test$home_win

# B1-Pythagorean baseline via log5. Exponent fit on TRAIN team-seasons only (origin log-log fit,
# same as b1_pythagoras) so the sealed holdout is untouched. Each team's strength = its rolling
# Pythagorean win expectation; log5 combines them; a fixed train-derived home-field logit is added.
ts <- read_parquet(file.path(gold, "team_season.parquet"))
ts <- ts %>% filter(season %in% c(2023, 2024), w > 0, l > 0)
e <- unname(coef(lm(log(w / l) ~ 0 + log(rs / ra), data = ts))[1])
pyth <- function(rs, ra) (rs^e) / (rs^e + ra^e)
ph <- pyth(test$home_rs, test$home_ra)
pa <- pyth(test$away_rs, test$away_ra)
p0 <- (ph * (1 - pa)) / (ph * (1 - pa) + pa * (1 - ph))
hfa <- log(mean(train$home_win) / (1 - mean(train$home_win)))
pyth_pred <- 1 / (1 + exp(-(log(p0 / (1 - p0)) + hfa)))
brier_pyth <- mean((pyth_pred - yte)^2)

brier <- mean((pred - yte)^2)
# AUC via the Mann-Whitney U identity (ties averaged, matching sklearn roc_auc_score).
rk <- rank(pred)
n_pos <- sum(yte == 1)
n_neg <- sum(yte == 0)
auc <- (sum(rk[yte == 1]) - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
acc <- mean((pred >= 0.5) == yte)
base <- mean(train$home_win)

co <- coef(m)
out <- list(
  n_train = nrow(train),
  n_test = nrow(test),
  coef = list(
    intercept = round(co[["(Intercept)"]], 8),
    off_rv_diff = round(co[["off_rv_diff"]], 8),
    def_rv_diff = round(co[["def_rv_diff"]], 8),
    win_pct_diff = round(co[["win_pct_diff"]], 8)
  ),
  brier = round(brier, 6),
  auc = round(auc, 6),
  accuracy = round(acc, 6),
  brier_hfa_baseline = round(mean((base - yte)^2), 6),
  brier_pyth_baseline = round(brier_pyth, 6),
  mean_pred = round(mean(pred), 6),
  mean_actual = round(mean(yte), 6)
)

write_json(out, file.path(res, "game_model__r.json"), auto_unbox = TRUE, pretty = TRUE, digits = 12)
cat(toJSON(c(list(stage = "models_r", model = "game_model"), out), auto_unbox = TRUE, digits = 12), "\n")
