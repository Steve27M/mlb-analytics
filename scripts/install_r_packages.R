# Stand up the R environment with renv and install the model-track packages.
# Run once: Rscript scripts/install_r_packages.R  (or `uv run python run.py ... ` wires it later)
options(repos = c(CRAN = "https://cloud.r-project.org"), Ncpus = 4)

if (!requireNamespace("renv", quietly = TRUE)) install.packages("renv")

# Bare init: don't auto-discover deps (no R scripts written yet); we install explicitly.
renv::init(bare = TRUE, restart = FALSE)

renv::install(c(
  "arrow",     # read gold Parquet feeds (files are the ONLY R<->Python interface)
  "dplyr",     # wrangling
  "tidyr",
  "readr",
  "purrr",
  "jsonlite",  # write metrics/results as flat files for the parity gate
  "lme4"       # M7 BABIP shrinkage, B-track mixed-effects
))

renv::snapshot(prompt = FALSE)
cat("R environment ready.\n")
