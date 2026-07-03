# M7 - BABIP shrinkage (R side of the parity gate).
# Linear mixed model with batter random intercepts: shrink each batter's BABIP toward the mean.
# ICC = persistent (between-batter) share of BABIP variance.
suppressMessages({
  library(arrow)
  library(dplyr)
  library(lme4)
  library(jsonlite)
})

MIN_PA <- 150

gold <- Sys.getenv("MLB_GOLD_DIR", "data/gold")
res <- Sys.getenv("MLB_RESULTS_DIR", "data/results")
dir.create(res, showWarnings = FALSE, recursive = TRUE)

df <- read_parquet(file.path(gold, "batter_season.parquet")) %>%
  filter(pa >= MIN_PA, !is.na(babip)) %>%
  mutate(batter_id = as.character(batter_id),
         babip_pts = babip * 100)  # points scale, matches Python (ICC is scale-invariant)

m <- lmer(babip_pts ~ 1 + (1 | batter_id), data = df, REML = TRUE)

vc <- as.data.frame(VarCorr(m))
group_var <- vc$vcov[vc$grp == "batter_id"]
resid_var <- vc$vcov[vc$grp == "Residual"]
icc <- group_var / (group_var + resid_var)

re <- ranef(m)$batter_id
blups <- as.list(round(re[["(Intercept)"]], 6))
names(blups) <- rownames(re)

out <- list(
  n_obs = nrow(df),
  n_batters = length(unique(df$batter_id)),
  intercept = round(fixef(m)[["(Intercept)"]], 6),
  group_var = round(group_var, 8),
  resid_var = round(resid_var, 8),
  icc = round(icc, 6),
  blups = blups
)

write_json(out, file.path(res, "m7_babip_shrinkage__r.json"), auto_unbox = TRUE, digits = 12)
cat(toJSON(list(stage = "models_r", model = "m7_babip_shrinkage",
                intercept = round(fixef(m)[["(Intercept)"]], 6),
                group_var = round(group_var, 8), resid_var = round(resid_var, 8),
                icc = round(icc, 6)), auto_unbox = TRUE, digits = 12), "\n")
