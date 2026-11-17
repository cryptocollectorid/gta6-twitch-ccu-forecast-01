# gta6-twitch-ccu-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/cryptocollectorid/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/cryptocollectorid/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecast GTA VI's launch-day Twitch viewers hour by hour — a forecast program for make.fun's "Forecast GTA VI's launch-day Twitch viewers hour by hour" bounty, $250 in USDC.

## Run it

```sh
MAKEFUN_INPUT_DIR=kit/input MAKEFUN_OUTPUT_DIR=/tmp/out python3 main.py
```

Reads every `*.in` case in `$MAKEFUN_INPUT_DIR` (default `/input/`) and writes one `*.out` forecast per case to `$MAKEFUN_OUTPUT_DIR` (default `/output/`). Python 3.13, standard library only, offline, deterministic.

## How it forecasts

Launch days have a characteristic UTC shape: a dip in hours 2–4 (night), then a ramp as the US unlocks and wakes, peaking in the evening (hours 17–21). The ramp's size depends strongly on the hour-1 print — launches that are already huge at hour 1 ramp much less, in log terms, than launches that start small.

For each hour 2–24, the program regresses the log ratio `ln(viewers_h / viewers_1)` of past big launches on `ln(hour-1 viewers)` plus a dummy for a rolling-midnight unlock (GTA VI unlocks at midnight local, country by country). The fit uses the comparables bundled in the case file with an hour-1 print of at least 5,000 viewers, excluding the GTA VI category's own pre-release history, which is not a launch. The hour-1 print is clamped to the observed range so an unprecedented launch size cannot extrapolate the fit. Quantiles are lognormal: median from the regression, spread from the residual standard deviation (floored at 0.20, capped at 1.00 in log space). If too few comparables are usable for an hour, it falls back to the house baseline (persistence with a widening spread), so the output is always valid.

## Validation

Scored against the SullyGnome hourly counts of the four practice launches (the program itself is never given the answers):

| case | this program | house baseline |
| --- | --- | --- |
| p00 Marvel's Wolverine | 0.197 | 0.744 |
| p01 Red Dead Redemption 2 | 0.129 | 0.287 |
| p02 God of War Ragnarök | 0.132 | 0.215 |
| p03 Marvel's Spider-Man 2 | 0.212 | 0.303 |
| **mean pinball loss (log scale)** | **0.167** | **0.387** |

Leave-one-out over the 9 rolling-midnight comparable launches: mean pinball loss 0.272, vs 0.285 for the same model without the rolling-midnight dummy (the house baseline scores 0.351 leave-one-out over all 28 launches). 90% coverage on the practice cases: 0.97; on leave-one-out: 0.84 (honest target: 0.90).

---

<sub>Entered on [make.fun](https://make.fun/?ref=4pc5tnqn&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
