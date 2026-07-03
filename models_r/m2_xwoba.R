# M2/M3 - xwOBA-over-expected (R side of the parity gate).
# M2 (simple) and M3 (multiple) OLS of batted-ball value on launch speed + angle. Fitted value =
# expected batted-ball value; residuals aggregate to hitter over/under-performance.
suppressMessages({
  library(arrow)
  library(dplyr)
  library(jsonlite)
})

gold <- Sys.getenv("MLB_GOLD_DIR", "data/gold")
res <- Sys.getenv("MLB_RESULTS_DIR", "data/results")
dir.create(res, showWarnings = FALSE, recursive = TRUE)

df <- read_parquet(file.path(gold, "batted_balls.parquet")) %>%
  filter(!is.na(launch_speed), !is.na(launch_angle), !is.na(woba_value)) %>%
  mutate(launch_angle_sq = launch_angle^2)

m2 <- lm(woba_value ~ launch_speed, data = df)
m3 <- lm(woba_value ~ launch_speed + launch_angle + launch_angle_sq, data = df)

pred3 <- predict(m3)
ok <- !is.na(df$statcast_xwoba)
xwoba_corr <- cor(pred3[ok], df$statcast_xwoba[ok])

c2 <- coef(m2)
c3 <- coef(m3)
out <- list(
  n = nrow(df),
  m2 = list(
    intercept = round(c2[["(Intercept)"]], 8),
    launch_speed = round(c2[["launch_speed"]], 8),
    r_squared = round(summary(m2)$r.squared, 8)
  ),
  m3 = list(
    intercept = round(c3[["(Intercept)"]], 8),
    launch_speed = round(c3[["launch_speed"]], 8),
    launch_angle = round(c3[["launch_angle"]], 8),
    launch_angle_sq = round(c3[["launch_angle_sq"]], 8),
    r_squared = round(summary(m3)$r.squared, 8)
  ),
  m3_xwoba_corr = round(xwoba_corr, 6)
)

# digits = 12: jsonlite defaults to 4 sig-digits and would break EXACT parity (see DECISIONS.md).
write_json(out, file.path(res, "m2_xwoba__r.json"), auto_unbox = TRUE, pretty = TRUE, digits = 12)
cat(toJSON(c(list(stage = "models_r", model = "m2_xwoba"), out), auto_unbox = TRUE, digits = 12), "\n")
