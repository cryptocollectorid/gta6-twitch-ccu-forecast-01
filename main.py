#!/usr/bin/env python3
"""Forecast GTA VI launch-day Twitch CCU, hours 2-24, as 5 quantiles/hour.

Method (validated on the 4 practice launches and by leave-one-out over the
comparables bundled in the case file):

  * Launch days have a characteristic UTC shape: a dip in hours 2-4 (night),
    then a ramp as the US unlocks and wakes, peaking in the evening
    (hours 17-21). The ramp's size depends strongly on the hour-1 print:
    launches that are already huge at hour 1 ramp much less (in log terms)
    than launches that start small.
  * For each hour h, regress the log ratio ln(viewers_h / viewers_1) of
    past big launches on ln(hour-1 viewers) plus a dummy for a
    rolling-midnight unlock (GTA VI unlocks at midnight local, country by
    country, so the dummy is 1 for this case). The regression is fit on
    comparables whose hour-1 print is at least 5,000 viewers (smaller
    categories are sparsely sampled and their ratios are noise), excluding
    the GTA VI category's own pre-release history, which is not a launch.
  * The hour-1 print is clamped to the observed range of the training
    launches, so an unprecedented launch size cannot extrapolate the fit.
  * Quantiles are lognormal: median from the regression, spread from the
    residual standard deviation (floored at 0.20, capped at 1.00 in log
    space), so the 5-95% band honestly reflects how much launch days vary.
  * If too few comparables are usable for an hour, fall back to the house
    baseline (persistence with a widening spread) for that hour, so the
    output is always valid.

Standard library only, no network, deterministic: the same input file
always produces the same output bytes.

Usage: python3 main.py
  Reads $MAKEFUN_INPUT_DIR (default /input/) for *.in files and writes
  one *.out file per case to $MAKEFUN_OUTPUT_DIR (default /output/).
"""

import json
import math
import os
import statistics
from datetime import datetime, timezone

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

P1_FLOOR = 5000.0       # ignore comparables whose hour-1 print is smaller
SIGMA_FLOOR = 0.20      # log-space spread floor (honest uncertainty)
SIGMA_CAP = 1.00        # log-space spread cap
MIN_POINTS = 8          # minimum comparables to fit the regression per hour


def solve3(a, b):
    """Solve a 3x3 linear system by Gaussian elimination; None if singular."""
    n = 3
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(m[r][i]))
        m[i], m[p] = m[p], m[i]
        if abs(m[i][i]) < 1e-12:
            return None
        for r in range(i + 1, n):
            f = m[r][i] / m[i][i]
            for c in range(i, n + 1):
                m[r][c] -= f * m[i][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))) / m[i][i]
    return x


def ols2(xs, ys):
    """Two-parameter OLS (intercept, slope); (median, 0.0) if degenerate."""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    vx = sum((x - mx) ** 2 for x in xs)
    if vx <= 1e-12:
        return statistics.median(ys), 0.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / vx
    return my - b * mx, b


def is_rolling_midnight(comp):
    """True when the unlock text describes a midnight-local rolling unlock."""
    u = (comp.get("unlock") or "").lower()
    if "simultaneous" in u or "single global" in u:
        return False
    return "midnight local" in u


def release_day_curve(comp):
    """{hour: viewers} for hours 1..24 of the comparable's release day (UTC).

    Returns None when the comparable has no hour-1 print.
    """
    try:
        day0 = datetime.strptime(comp["day_start"][:10], "%Y-%m-%d").replace(
            tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError):
        return None
    out = {}
    for pt in comp.get("hourly") or []:
        frm = pt.get("from") or ""
        if len(frm) < 13 or pt.get("viewers") is None:
            continue
        try:
            dt = datetime.strptime(frm[:19], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=timezone.utc)
        except ValueError:
            continue
        h = int((dt - day0).total_seconds() // 3600) + 1
        if 1 <= h <= 24:
            out[h] = float(pt["viewers"])
    if 1 not in out:
        return None
    return out


def hour1_print(case):
    """The case's hour-1 viewers (best effort if the known row is missing)."""
    known = case.get("known") or []
    for row in known:
        if row.get("hour") == 1 and row.get("viewers") is not None:
            return max(1.0, float(row["viewers"]))
    for row in sorted(known, key=lambda r: r.get("hour", 0)):
        if row.get("viewers") is not None:
            return max(1.0, float(row["viewers"]))
    hist = case.get("history") or []
    for pt in reversed(hist):
        if pt.get("viewers") is not None:
            return max(1.0, float(pt["viewers"]))
    return 1.0


def forecast_hours(case):
    """The 23 hours to forecast, from the case's forecast rows if present."""
    rows = case.get("forecast") or []
    hours = [int(r["hour"]) for r in rows if r.get("hour") is not None]
    hours = [h for h in hours if 2 <= h <= 24]
    return hours if len(hours) == 23 else list(range(2, 25))


def baseline_quantiles(p1, h):
    """House baseline: persistence with a spread widening over the day."""
    return [p1 * math.exp(z * 0.15 * math.sqrt(h - 1)) for z in Z]


def forecast(case):
    p1 = hour1_print(case)
    hours = forecast_hours(case)

    # Collect comparable launch-day curves.
    curves = []  # (log p1, is_rolling, {hour: viewers})
    for comp in case.get("comparables") or []:
        name = comp.get("name") or ""
        if "Grand Theft Auto VI" in name:
            continue  # the category's own pre-release history is not a launch
        curve = release_day_curve(comp)
        if curve is None or curve[1] < P1_FLOOR:
            continue
        curves.append((math.log(curve[1]), is_rolling_midnight(comp), curve))
    curves.sort(key=lambda c: (c[0], c[1]))  # deterministic fit order

    if curves:
        xs_all = [c[0] for c in curves]
        x_lo, x_hi = min(xs_all), max(xs_all)
    else:
        x_lo = x_hi = math.log(p1)
    x_use = min(max(math.log(p1), x_lo), x_hi)

    out = []
    for h in hours:
        pts = []
        for lx, roll, curve in curves:
            v = curve.get(h)
            if v is not None and v > 0:
                pts.append((lx, 1.0 if roll else 0.0, math.log(v / math.exp(lx))))
        if len(pts) >= MIN_POINTS:
            # y = a + b*log(p1) + c*rolling
            xtx = [[0.0] * 3 for _ in range(3)]
            xty = [0.0] * 3
            for x, d, y in pts:
                row = [1.0, x, d]
                for i in range(3):
                    xty[i] += row[i] * y
                    for j in range(3):
                        xtx[i][j] += row[i] * row[j]
            sol = solve3(xtx, xty)
            if sol is not None:
                a, b, c = sol
            else:
                a, b = ols2([p[0] for p in pts], [p[2] for p in pts])
                c = 0.0
            med = a + b * x_use + c  # this case is a rolling-midnight launch
            resid = [y - (a + b * x + c * d) for x, d, y in pts]
            sigma = statistics.pstdev(resid) if len(resid) > 1 else 0.3
            sigma = min(max(sigma, SIGMA_FLOOR), SIGMA_CAP)
            q = [p1 * math.exp(med + z * sigma) for z in Z]
        else:
            q = baseline_quantiles(p1, h)
        q = [max(1.0, min(1e9, v)) for v in q]
        q = sorted(q)  # guarantees non-decreasing quantiles
        out.append({"hour": h, "q": [round(v, 2) for v in q]})
    return {"hours": out}


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input/"
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output/"
    os.makedirs(out_dir, exist_ok=True)
    names = sorted(n for n in os.listdir(in_dir) if n.endswith(".in"))
    for name in names:
        with open(os.path.join(in_dir, name), "r", encoding="utf-8") as f:
            case = json.load(f)
        result = forecast(case)
        out_path = os.path.join(out_dir, name[:-3] + ".out")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, separators=(",", ":"))
            f.write("\n")


if __name__ == "__main__":
    main()
