# M1 - metric stability (R side of the parity gate).
# Year-over-year correlation of batter rate stats: K%/BB% stabilize fast (skill), BABIP is noise.
# Reads ONLY the gold feed; writes results to data/results/ as a flat file. No DuckDB here.
suppressMessages({
  library(arrow)
  library(dplyr)
  library(jsonlite)
})

MIN_PA <- 300
STATS <- c("k_pct", "bb_pct", "babip")

gold <- Sys.getenv("MLB_GOLD_DIR", "data/gold")
res <- Sys.getenv("MLB_RESULTS_DIR", "data/results")
dir.create(res, showWarnings = FALSE, recursive = TRUE)

df <- read_parquet(file.path(gold, "batter_season.parquet"))
q <- df %>%
  filter(pa >= MIN_PA) %>%
  select(batter_id, season, all_of(STATS))

# Pair each qualified batter-season t with the same batter's season t+1.
nxt <- q %>% mutate(season = season - 1L)
pairs <- inner_join(q, nxt, by = c("batter_id", "season"), suffix = c("_t", "_t1"))

out <- list(n_pairs = nrow(pairs))
for (s in STATS) {
  xt <- pairs[[paste0(s, "_t")]]
  xt1 <- pairs[[paste0(s, "_t1")]]
  ok <- !is.na(xt) & !is.na(xt1)
  out[[paste0(s, "_yoy_corr")]] <- round(cor(xt[ok], xt1[ok]), 6)
  out[[paste0(s, "_n")]] <- sum(ok)
}

# digits = 12: jsonlite defaults to 4 significant digits, which would truncate the round(6)
# values and spuriously fail EXACT parity against Python. Preserve full precision on the wire.
write_json(out, file.path(res, "m1_stability__r.json"),
           auto_unbox = TRUE, pretty = TRUE, digits = 12)
cat(toJSON(c(list(stage = "models_r", model = "m1_stability"), out),
           auto_unbox = TRUE, digits = 12), "\n")
