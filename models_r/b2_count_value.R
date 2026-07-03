# B2 - count effects (R side of the parity gate).
# Run value by count (RE24 chained to the count level) and swing rate by count.
suppressMessages({
  library(arrow)
  library(dplyr)
  library(jsonlite)
})

gold <- Sys.getenv("MLB_GOLD_DIR", "data/gold")
res <- Sys.getenv("MLB_RESULTS_DIR", "data/results")
dir.create(res, showWarnings = FALSE, recursive = TRUE)

df <- read_parquet(file.path(gold, "count_pitches.parquet"))
g <- df %>%
  group_by(balls, strikes) %>%
  summarise(run_value = mean(pa_run_value), swing_rate = mean(is_swing), n = n(), .groups = "drop")

counts <- list()
for (i in seq_len(nrow(g))) {
  key <- paste0(g$balls[i], "-", g$strikes[i])
  counts[[key]] <- list(
    run_value = round(g$run_value[i], 6),
    swing_rate = round(g$swing_rate[i], 6),
    n = g$n[i]
  )
}
out <- list(n = nrow(df), counts = counts)

write_json(out, file.path(res, "b2_count_value__r.json"), auto_unbox = TRUE, digits = 12)
cat(toJSON(list(stage = "models_r", model = "b2_count_value",
                rv_3_0 = counts[["3-0"]]$run_value, rv_0_2 = counts[["0-2"]]$run_value),
           auto_unbox = TRUE, digits = 12), "\n")
