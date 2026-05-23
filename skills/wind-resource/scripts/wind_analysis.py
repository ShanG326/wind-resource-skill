import math
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import pandas as pd
from scipy import stats as sp_stats


WPD_CLASSES = [
    (0, 100, 1, "贫乏"), (100, 150, 2, "一般"),
    (150, 200, 3, "较丰富"), (200, 250, 4, "丰富"),
    (250, 300, 5, "很丰富"), (300, 400, 6, "极丰富"),
    (400, float('inf'), 7, "极丰富"),
]

TURBULENCE_CLASSES = [
    (0.10, "A+"), (0.16, "A"), (0.18, "B"), (float('inf'), "C"),
]

DIR16_NAMES = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
               'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']


def deg_to_dir16(deg: float) -> str:
    idx = int((deg + 11.25) % 360 / 22.5)
    return DIR16_NAMES[idx]


@dataclass
class QualityReport:
    total_records: int = 0
    valid_records: int = 0
    completeness_pct: float = 0.0
    channel_completeness: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)


@dataclass
class WindStats:
    mean_wind_speed: dict = field(default_factory=dict)
    max_wind_speed: dict = field(default_factory=dict)
    wind_power_density: dict = field(default_factory=dict)
    speed_distribution: dict = field(default_factory=dict)
    monthly_mean: dict = field(default_factory=dict)
    seasonal_mean: dict = field(default_factory=dict)
    hourly_mean: dict = field(default_factory=dict)


@dataclass
class DirectionStats:
    dir_frequency: dict = field(default_factory=dict)
    dir_mean_speed: dict = field(default_factory=dict)
    dir_wpd: dict = field(default_factory=dict)
    dominant_dir: str = ""
    dominant_energy_dir: str = ""


@dataclass
class ShearStats:
    alpha_values: dict = field(default_factory=dict)
    mean_alpha: float = 0.0


@dataclass
class TurbulenceStats:
    ti_values: dict = field(default_factory=dict)
    ti_at_15: dict = field(default_factory=dict)
    iec_class: dict = field(default_factory=dict)


@dataclass
class AirDensityResult:
    mean_rho: float = 0.0


@dataclass
class WeibullResult:
    k_values: dict = field(default_factory=dict)
    c_values: dict = field(default_factory=dict)
    ks_test: dict = field(default_factory=dict)


@dataclass
class ExtremeWindResult:
    v50: dict = field(default_factory=dict)
    iec_class: dict = field(default_factory=dict)


@dataclass
class ComprehensiveReport:
    quality: QualityReport = field(default_factory=QualityReport)
    wind_stats: WindStats = field(default_factory=WindStats)
    direction: DirectionStats = field(default_factory=DirectionStats)
    shear: ShearStats = field(default_factory=ShearStats)
    turbulence: TurbulenceStats = field(default_factory=TurbulenceStats)
    air_density: AirDensityResult = field(default_factory=AirDensityResult)
    weibull: WeibullResult = field(default_factory=WeibullResult)
    extreme: ExtremeWindResult = field(default_factory=ExtremeWindResult)
    wpd_class: dict = field(default_factory=dict)
    avg_temp: float = 0.0
    avg_pressure: float = 0.0
    data_months: int = 0


def quality_control(df, ws_cols, wd_cols):
    report = QualityReport()
    report.total_records = len(df)
    for col in ws_cols + wd_cols:
        if col in df.columns:
            valid = df[col].notna().sum()
            total = len(df)
            report.channel_completeness[col] = {
                'valid': int(valid), 'total': int(total),
                'pct': round(valid / total * 100, 1) if total > 0 else 0,
            }
    if ws_cols:
        primary = ws_cols[0]
        report.valid_records = int(df[primary].notna().sum())
        report.completeness_pct = round(report.valid_records / report.total_records * 100, 1)
    for col in ws_cols:
        if col in df.columns:
            bad = ((df[col] < 0) | (df[col] > 75)).sum()
            if bad > 0:
                report.issues.append(f"{col}: {bad} out of range")
    if 'Timestamp' in df.columns:
        months = df['Timestamp'].dt.to_period('M').nunique()
        report.issues.append(f"Data covers {months} months")
        if months < 12:
            report.issues.append(f"Warning: less than 1 year of data")
    return report


def calc_wind_statistics(df, ws_cols, rho):
    result = WindStats()
    for col in ws_cols:
        if col not in df.columns:
            continue
        v = df[col].dropna()
        if len(v) == 0:
            continue
        result.mean_wind_speed[col] = round(float(v.mean()), 2)
        result.max_wind_speed[col] = round(float(v.max()), 2)
        result.wind_power_density[col] = round(0.5 * rho * float((v ** 3).mean()), 2)
    for col in ws_cols:
        if col not in df.columns:
            continue
        v = df[col].dropna()
        bins = np.arange(0, 31, 1)
        counts, _ = np.histogram(v, bins=bins)
        total = counts.sum()
        result.speed_distribution[col] = {
            f"{int(bins[i])}-{int(bins[i+1])}": round(int(counts[i]) / total * 100, 2)
            if total > 0 else 0
            for i in range(len(counts))
        }
    if 'Timestamp' in df.columns:
        for col in ws_cols:
            if col not in df.columns:
                continue
            monthly = df.groupby(df['Timestamp'].dt.to_period('M'))[col].mean()
            result.monthly_mean[col] = {str(k): round(float(v), 2) for k, v in monthly.items()}
        month = df['Timestamp'].dt.month
        seasons = {
            'spring': month.isin([3, 4, 5]), 'summer': month.isin([6, 7, 8]),
            'autumn': month.isin([9, 10, 11]), 'winter': month.isin([12, 1, 2]),
        }
        for col in ws_cols:
            if col not in df.columns:
                continue
            result.seasonal_mean[col] = {}
            for s_name, mask in seasons.items():
                s_data = df.loc[mask, col].dropna()
                if len(s_data) > 0:
                    result.seasonal_mean[col][s_name] = round(float(s_data.mean()), 2)
        for col in ws_cols:
            if col not in df.columns:
                continue
            hourly = df.groupby(df['Timestamp'].dt.hour)[col].mean()
            result.hourly_mean[col] = {int(k): round(float(v), 2) for k, v in hourly.items()}
    return result


def calc_direction_stats(df, ws_cols, wd_cols):
    result = DirectionStats()
    wd_col = wd_cols[0] if wd_cols else None
    ws_col = ws_cols[0] if ws_cols else None
    if not wd_col or not ws_col or wd_col not in df.columns or ws_col not in df.columns:
        return result
    valid = df[[ws_col, wd_col]].dropna()
    for i, name in enumerate(DIR16_NAMES):
        center = i * 22.5
        lower = (center - 11.25) % 360
        upper = (center + 11.25) % 360
        if lower < upper:
            mask = (valid[wd_col] >= lower) & (valid[wd_col] < upper)
        else:
            mask = (valid[wd_col] >= lower) | (valid[wd_col] < upper)
        sector_data = valid.loc[mask, ws_col]
        count = len(sector_data)
        total = len(valid)
        result.dir_frequency[name] = round(count / total * 100, 1) if total > 0 else 0
        result.dir_mean_speed[name] = round(float(sector_data.mean()), 2) if count > 0 else 0
        result.dir_wpd[name] = round(float((sector_data ** 3).mean()), 2) if count > 0 else 0
    if result.dir_frequency:
        result.dominant_dir = max(result.dir_frequency, key=result.dir_frequency.get)
    if result.dir_wpd:
        result.dominant_energy_dir = max(result.dir_wpd, key=result.dir_wpd.get)
    return result


def calc_wind_shear(df, ws_cols, heights):
    result = ShearStats()
    avg_cols = [(col, heights.get(col, 0)) for col in ws_cols if 'avg' in col]
    avg_cols.sort(key=lambda x: x[1], reverse=True)
    for i in range(len(avg_cols) - 1):
        col_high, h_high = avg_cols[i]
        col_low, h_low = avg_cols[i + 1]
        if h_high <= 0 or h_low <= 0 or h_high == h_low:
            continue
        valid = df[[col_high, col_low]].dropna()
        valid = valid[(valid[col_low] > 0) & (valid[col_high] > 0)]
        if len(valid) == 0:
            continue
        ratios = np.log(valid[col_high] / valid[col_low])
        log_h = np.log(h_high / h_low)
        alpha_vals = ratios / log_h
        alpha_vals = alpha_vals[(alpha_vals > -1) & (alpha_vals < 1)]
        if len(alpha_vals) == 0:
            continue
        key = f"{int(h_high)}m-{int(h_low)}m"
        result.alpha_values[key] = round(float(alpha_vals.mean()), 3)
    if result.alpha_values:
        result.mean_alpha = round(float(np.mean(list(result.alpha_values.values()))), 3)
    return result


def calc_turbulence(df, ws_cols, sd_cols_map):
    result = TurbulenceStats()
    for avg_col in ws_cols:
        if 'avg' not in avg_col or avg_col not in df.columns:
            continue
        sd_col = sd_cols_map.get(avg_col)
        if sd_col is None or sd_col not in df.columns:
            continue
        valid = df[[avg_col, sd_col]].dropna()
        valid = valid[valid[avg_col] > 0]
        if len(valid) == 0:
            continue
        ti_vals = valid[sd_col] / valid[avg_col]
        result.ti_values[avg_col] = round(float(ti_vals.mean()), 3)
        near_15 = valid[(valid[avg_col] >= 14) & (valid[avg_col] <= 16)]
        if len(near_15) > 0:
            ti_15 = float((near_15[sd_col] / near_15[avg_col]).mean())
            result.ti_at_15[avg_col] = round(ti_15, 3)
            for threshold, cls in TURBULENCE_CLASSES:
                if ti_15 < threshold:
                    result.iec_class[avg_col] = cls
                    break
    return result


def calc_air_density(df, temp_col='', press_col='', elevation=0):
    result = AirDensityResult()
    if temp_col and press_col and temp_col in df.columns and press_col in df.columns:
        valid = df[[temp_col, press_col]].dropna()
        if len(valid) > 0:
            T_K = valid[temp_col] + 273.15
            P_Pa = valid[press_col] * 1000
            rho = P_Pa / (287.05 * T_K)
            result.mean_rho = round(float(rho.mean()), 4)
    elif elevation > 0:
        result.mean_rho = round(1.225 * math.exp(-elevation / 8500), 4)
    else:
        result.mean_rho = 1.225
    return result


def calc_weibull(df, ws_cols):
    result = WeibullResult()
    for col in ws_cols:
        if 'avg' not in col or col not in df.columns:
            continue
        v = df[col].dropna()
        v = v[v > 0]
        if len(v) < 100:
            continue
        try:
            shape_k, loc, scale_c = sp_stats.weibull_min.fit(v, floc=0)
            result.k_values[col] = round(float(shape_k), 3)
            result.c_values[col] = round(float(scale_c), 2)
            ks_stat, ks_p = sp_stats.kstest(v, 'weibull_min', args=(shape_k, 0, scale_c))
            result.ks_test[col] = round(float(ks_stat), 4)
        except Exception:
            pass
    return result


def calc_extreme_wind(df, ws_max_cols):
    result = ExtremeWindResult()
    if 'Timestamp' not in df.columns:
        return result
    for col in ws_max_cols:
        if col not in df.columns:
            continue
        daily_max = df.groupby(df['Timestamp'].dt.date)[col].max().dropna()
        if len(daily_max) < 365:
            continue
        try:
            loc, scale = sp_stats.gumbel_r.fit(daily_max.values)
            v50 = loc - scale * math.log(-math.log(0.98))
            result.v50[col] = round(float(v50), 2)
            if v50 < 37.5:
                result.iec_class[col] = "III"
            elif v50 < 42.5:
                result.iec_class[col] = "II"
            elif v50 < 50:
                result.iec_class[col] = "I"
            else:
                result.iec_class[col] = "Beyond standard"
        except Exception:
            pass
    return result


def classify_wpd(wpd):
    for low, high, grade, desc in WPD_CLASSES:
        if low <= wpd < high:
            return grade, desc
    return 7, "Extremely rich"


def run_full_analysis(df, sensors, elevation=0):
    report = ComprehensiveReport()
    ws_avg_cols = [s.channel_name for s in sensors if s.sensor_type == 'ws' and s.stat_type == 'avg']
    ws_sd_cols = [s.channel_name for s in sensors if s.sensor_type == 'ws' and s.stat_type == 'sd']
    ws_max_cols = [s.channel_name for s in sensors if s.sensor_type == 'ws' and s.stat_type == 'max']
    wd_cols = [s.channel_name for s in sensors if s.sensor_type == 'wd' and s.stat_type == 'avg']
    temp_cols = [s.channel_name for s in sensors if s.sensor_type == 'temp' and s.stat_type == 'avg']
    press_cols = [s.channel_name for s in sensors if s.sensor_type == 'pressure' and s.stat_type == 'avg']
    heights = {s.channel_name: s.height_m for s in sensors if s.stat_type == 'avg'}
    sd_cols_map = {}
    for avg_s in [s for s in sensors if s.stat_type == 'avg' and s.sensor_type == 'ws']:
        for sd_s in [s for s in sensors if s.stat_type == 'sd' and s.sensor_type == 'ws']:
            if avg_s.height_m == sd_s.height_m and avg_s.orientation == sd_s.orientation:
                sd_cols_map[avg_s.channel_name] = sd_s.channel_name
    temp_col = temp_cols[0] if temp_cols else ''
    press_col = press_cols[0] if press_cols else ''
    report.air_density = calc_air_density(df, temp_col, press_col, elevation)
    if temp_col and temp_col in df.columns:
        report.avg_temp = round(float(df[temp_col].mean()), 2)
    if press_col and press_col in df.columns:
        report.avg_pressure = round(float(df[press_col].mean()), 2)
    report.quality = quality_control(df, ws_avg_cols, wd_cols)
    report.wind_stats = calc_wind_statistics(df, ws_avg_cols, report.air_density.mean_rho)
    report.direction = calc_direction_stats(df, ws_avg_cols, wd_cols)
    report.shear = calc_wind_shear(df, ws_avg_cols, heights)
    report.turbulence = calc_turbulence(df, ws_avg_cols, sd_cols_map)
    report.weibull = calc_weibull(df, ws_avg_cols)
    report.extreme = calc_extreme_wind(df, ws_max_cols)
    for col, wpd in report.wind_stats.wind_power_density.items():
        grade, desc = classify_wpd(wpd)
        report.wpd_class[col] = {'grade': grade, 'description': desc}
    if 'Timestamp' in df.columns:
        report.data_months = df['Timestamp'].dt.to_period('M').nunique()
    return report
