# M6 - pitcher arsenal archetypes (R side of the parity gate).
# Standardize -> prcomp -> kmeans into pitch-mix / stuff archetypes. Parity is label-invariant
# (PC |corr| + cluster ARI in the gate). Cluster labels emitted 0-indexed to match Python.
suppressMessages({
  library(arrow)
  library(dplyr)
  library(jsonlite)
})

FEATURES <- c("velo", "spin", "h_move", "v_move", "fastball_pct", "breaking_pct", "n_pitch_types")
N_PC <- 4
K <- 6

gold <- Sys.getenv("MLB_GOLD_DIR", "data/gold")
res <- Sys.getenv("MLB_RESULTS_DIR", "data/results")
dir.create(res, showWarnings = FALSE, recursive = TRUE)

df <- read_parquet(file.path(gold, "pitcher_arsenal.parquet")) %>%
  arrange(pitcher_id, season)
x <- scale(as.matrix(df[, FEATURES]))            # standardize (mean 0, sd 1)
pca <- prcomp(x, center = FALSE, scale. = FALSE) # already standardized
pcs <- pca$x[, 1:N_PC]
set.seed(0)
labels <- kmeans(pcs, centers = K, nstart = 25)$cluster - 1L  # 0-indexed like Python

ev <- (pca$sdev^2 / sum(pca$sdev^2))[1:N_PC]
rows <- lapply(seq_len(nrow(df)), function(i) {
  list(
    pitcher_id = df$pitcher_id[i],
    season = df$season[i],
    pc = round(as.numeric(pcs[i, ]), 6),
    cluster = labels[i]
  )
})
out <- list(n = nrow(df), features = FEATURES,
            explained_var = round(ev, 6), rows = rows)

write_json(out, file.path(res, "m6_arsenal__r.json"), auto_unbox = TRUE, digits = 12)
cat(toJSON(list(stage = "models_r", model = "m6_arsenal", n = nrow(df),
                explained_var = round(ev, 6)), auto_unbox = TRUE, digits = 12), "\n")
