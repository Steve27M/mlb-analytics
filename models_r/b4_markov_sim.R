# B4 - Markov half-inning simulation (R side of the parity gate).
# Build the base-out transition distribution from PBP, simulate half-innings from a start state,
# and reconcile the simulated RE with gold_run_expectancy (RE24). Distributional tier: transition
# summary deterministic (matches Python); simulated means within Monte-Carlo error.
suppressMessages({
  library(arrow)
  library(dplyr)
  library(jsonlite)
})

N_SIM <- 10000
ABSORB <- 24L

gold <- Sys.getenv("MLB_GOLD_DIR", "data/gold")
res <- Sys.getenv("MLB_RESULTS_DIR", "data/results")
dir.create(res, showWarnings = FALSE, recursive = TRUE)

df <- read_parquet(file.path(gold, "pa_transitions.parquet"))
# Stable transition order so the fixed-seed RNG is reproducible across rebuilds (matches the
# Python side; parquet/DuckDB row order isn't guaranteed).
df <- df %>% arrange(from_state, to_state, runs)
to_by <- split(df$to_state, df$from_state)
runs_by <- split(df$runs, df$from_state)

simulate <- function(start, n) {
  totals <- numeric(n)
  for (i in seq_len(n)) {
    s <- start
    r <- 0
    while (s != ABSORB) {
      key <- as.character(s)
      tos <- to_by[[key]]
      runs <- runs_by[[key]]
      j <- sample.int(length(tos), 1L)
      r <- r + runs[j]
      s <- tos[j]
    }
    totals[i] <- r
  }
  totals
}

summ <- df %>% group_by(from_state) %>% summarise(n = n(), mean_runs = mean(runs), .groups = "drop")
summary <- list()
for (i in seq_len(nrow(summ))) {
  summary[[as.character(summ$from_state[i])]] <-
    list(n = summ$n[i], mean_runs = round(summ$mean_runs[i], 6))
}

set.seed(777)
sim_empty0 <- mean(simulate(0L, N_SIM))
sim_loaded0 <- mean(simulate(21L, N_SIM))

re24 <- read_parquet(file.path(gold, "run_expectancy.parquet"))
pooled <- function(bs, outs) {
  sub <- re24 %>% filter(base_state == bs, outs_start == outs)
  sum(sub$run_expectancy * sub$n_occurrences) / sum(sub$n_occurrences)
}

out <- list(
  n_transitions = nrow(df),
  transition_summary = summary,
  sim_re_empty_0 = round(sim_empty0, 4),
  sim_re_loaded_0 = round(sim_loaded0, 4),
  re24_empty_0 = round(pooled(0, 0), 4),
  re24_loaded_0 = round(pooled(7, 0), 4),
  n_sim = N_SIM
)

write_json(out, file.path(res, "b4_markov_sim__r.json"), auto_unbox = TRUE, digits = 12)
cat(toJSON(list(stage = "models_r", model = "b4_markov_sim",
                sim_re_empty_0 = round(sim_empty0, 4), re24_empty_0 = round(pooled(0, 0), 4),
                sim_re_loaded_0 = round(sim_loaded0, 4), re24_loaded_0 = round(pooled(7, 0), 4)),
           auto_unbox = TRUE, digits = 12), "\n")
