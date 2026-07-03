# B5 - streaky performances (R side of the parity gate).
# Wald-Wolfowitz runs test per hitter-season + permutation test on the busiest hitter-season.
# Observed statistics are deterministic (match Python exactly); the permutation null is stochastic
# (matches within Monte-Carlo error, NOT by seed — R Mersenne-Twister vs numpy PCG64).
suppressMessages({
  library(arrow)
  library(dplyr)
  library(jsonlite)
})

MIN_GAMES <- 100
N_PERM <- 10000

runs_count <- function(seq) {
  if (length(seq) == 0) return(0L)
  1L + sum(seq[-1] != seq[-length(seq)])
}

gold <- Sys.getenv("MLB_GOLD_DIR", "data/gold")
res <- Sys.getenv("MLB_RESULTS_DIR", "data/results")
dir.create(res, showWarnings = FALSE, recursive = TRUE)

df <- read_parquet(file.path(gold, "batter_games.parquet")) %>%
  arrange(batter_id, season, game_date, game_pk)

observed <- list()
seqs <- list()
grps <- df %>% group_by(batter_id, season) %>% group_split()
for (g in grps) {
  seq <- g$got_hit
  n <- length(seq); n1 <- sum(seq); n0 <- n - n1
  if (n < MIN_GAMES || n1 == 0 || n0 == 0) next
  runs <- runs_count(seq)
  exp <- 2 * n1 * n0 / n + 1
  var <- 2 * n1 * n0 * (2 * n1 * n0 - n) / (n^2 * (n - 1))
  key <- paste0(g$batter_id[1], "-", g$season[1])
  observed[[key]] <- list(n = n, runs = runs, z = round((runs - exp) / sqrt(var), 6))
  seqs[[key]] <- seq
}

zs <- vapply(observed, function(v) v$z, numeric(1))
# Deterministic pick: busiest hitter-season (tie-break by key).
ord <- order(-vapply(observed, function(v) v$n, numeric(1)), names(observed))
top_key <- names(observed)[ord[1]]
seq <- seqs[[top_key]]
set.seed(12345)
perm <- replicate(N_PERM, runs_count(sample(seq)))

out <- list(
  n_batter_seasons = length(observed),
  mean_z = round(mean(zs), 6),
  sd_z = round(sd(zs), 6),
  observed = observed,
  perm = list(
    key = top_key,
    observed_runs = observed[[top_key]]$runs,
    perm_mean = round(mean(perm), 4),
    perm_sd = round(sd(perm), 4),
    perm_p = round(mean(perm <= observed[[top_key]]$runs), 4),
    n_perm = N_PERM
  )
)

write_json(out, file.path(res, "b5_streaks__r.json"), auto_unbox = TRUE, digits = 12)
cat(toJSON(list(stage = "models_r", model = "b5_streaks",
                n_batter_seasons = length(observed), mean_z = round(mean(zs), 6),
                perm_mean = round(mean(perm), 4)), auto_unbox = TRUE, digits = 12), "\n")
