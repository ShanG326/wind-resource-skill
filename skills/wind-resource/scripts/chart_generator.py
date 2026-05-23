import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager


def _setup_chinese_font():
    candidates = ['SimHei', 'Microsoft YaHei', 'STSong', 'WenQuanYi Micro Hei']
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            return name
    return None


CN_FONT = _setup_chinese_font()
if CN_FONT:
    plt.rcParams['font.sans-serif'] = [CN_FONT, 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


DIR16_NAMES = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
               'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']


def _friendly_name(col_name):
    parts = col_name.split('_')
    if len(parts) >= 3:
        h = parts[1]
        orient = parts[2] if len(parts) > 3 and parts[2] not in ('avg', 'sd', 'min', 'max') else ''
        return f"{h}({orient})" if orient else h
    return col_name


def plot_wind_rose(dir_freq, dir_speed, output_path, title="Wind Rose"):
    angles = np.linspace(0, 2 * np.pi, 16, endpoint=False)
    freq = [dir_freq.get(n, 0) for n in DIR16_NAMES]
    speed = [dir_speed.get(n, 0) for n in DIR16_NAMES]
    fig, ax = plt.subplots(subplot_kw={'projection': 'polar'}, figsize=(10, 10))
    width = 2 * np.pi / 16 * 0.8
    max_spd = max(speed) if speed else 10
    colors = plt.cm.YlOrRd(np.array(speed) / max_spd if max_spd > 0 else np.zeros(16))
    ax.bar(angles, freq, width=width, color=colors, alpha=0.85, edgecolor='white', linewidth=0.5)
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_thetagrids(np.degrees(angles), DIR16_NAMES)
    ax.set_ylim(0, max(freq) * 1.2 if freq else 10)
    sm = plt.cm.ScalarMappable(cmap='YlOrRd', norm=plt.Normalize(vmin=0, vmax=max_spd))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, pad=0.1, shrink=0.6)
    cbar.set_label('Mean wind speed (m/s)')
    ax.set_title(title, fontsize=16, pad=20)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_speed_distribution(speed_dist, weibull_k, weibull_c, output_path, title="Speed Distribution"):
    fig, ax = plt.subplots(figsize=(12, 6))
    bins = sorted(speed_dist.keys())
    freqs = [speed_dist[b] for b in bins]
    centers = [int(b.split('-')[0]) + 0.5 for b in bins]
    ax.bar(centers, freqs, width=0.9, color='#4472C4', alpha=0.7, label='Measured', edgecolor='white')
    if weibull_k and weibull_c and weibull_k > 0:
        from scipy.stats import weibull_min
        x = np.linspace(0.01, 30, 300)
        pdf = weibull_min.pdf(x, weibull_k, 0, weibull_c) * 100
        ax.plot(x, pdf, 'r-', linewidth=2, label=f'Weibull(k={weibull_k:.2f}, c={weibull_c:.1f})')
    ax.set_xlabel('Wind speed (m/s)', fontsize=12)
    ax.set_ylabel('Frequency (%)', fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.legend(fontsize=11)
    ax.set_xlim(0, 25)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_monthly_variation(monthly_mean, output_path, title="Monthly Mean Wind Speed"):
    fig, ax = plt.subplots(figsize=(12, 6))
    for col, monthly in monthly_mean.items():
        months = sorted(monthly.keys())
        vals = [monthly[m] for m in months]
        short_months = [m[-5:] if len(m) > 7 else m for m in months]
        ax.plot(short_months, vals, marker='o', linewidth=2, label=_friendly_name(col))
    ax.set_xlabel('Month', fontsize=12)
    ax.set_ylabel('Mean wind speed (m/s)', fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.legend(fontsize=10, ncol=2)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_hourly_variation(hourly_mean, output_path, title="Diurnal Wind Speed"):
    fig, ax = plt.subplots(figsize=(12, 6))
    for col, hourly in hourly_mean.items():
        hours = sorted(hourly.keys())
        vals = [hourly[h] for h in hours]
        ax.plot(hours, vals, marker='o', linewidth=2, label=_friendly_name(col))
    ax.set_xlabel('Hour', fontsize=12)
    ax.set_ylabel('Mean wind speed (m/s)', fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.legend(fontsize=10, ncol=2)
    ax.set_xticks(range(0, 24, 2))
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_shear_profile(mean_wind_speed, heights, output_path, title="Wind Shear Profile"):
    fig, ax = plt.subplots(figsize=(8, 10))
    h_vals, v_vals = [], []
    for col, v in mean_wind_speed.items():
        h = heights.get(col, 0)
        if h > 0:
            h_vals.append(h)
            v_vals.append(v)
    if not h_vals:
        plt.close()
        return
    pairs = sorted(zip(h_vals, v_vals))
    h_s, v_s = [p[0] for p in pairs], [p[1] for p in pairs]
    ax.plot(v_s, h_s, 'bo-', linewidth=2, markersize=8, label='Measured')
    if len(h_s) >= 2:
        from scipy.optimize import curve_fit
        def power_law(h, alpha, v_ref):
            return v_ref * (h / h_s[-1]) ** alpha
        try:
            popt, _ = curve_fit(power_law, h_s, v_s, p0=[0.15, v_s[-1]])
            h_fit = np.linspace(min(h_s), max(h_s), 100)
            v_fit = power_law(h_fit, *popt)
            ax.plot(v_fit, h_fit, 'r--', linewidth=1.5, label=f'Power law fit (a={popt[0]:.3f})')
        except Exception:
            pass
    ax.set_xlabel('Mean wind speed (m/s)', fontsize=12)
    ax.set_ylabel('Height (m)', fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_completeness(channel_completeness, output_path, title="Data Completeness"):
    fig, ax = plt.subplots(figsize=(12, 6))
    cols = sorted(channel_completeness.keys())
    pcts = [channel_completeness[c]['pct'] for c in cols]
    names = [_friendly_name(c) for c in cols]
    colors = ['#2E7D32' if p >= 95 else '#F57F17' if p >= 90 else '#C62828' for p in pcts]
    bars = ax.bar(names, pcts, color=colors, alpha=0.85)
    for bar, pct in zip(bars, pcts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f'{pct:.1f}%', ha='center', va='bottom', fontsize=9)
    ax.set_ylabel('Completeness (%)', fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.set_ylim(0, 105)
    ax.axhline(y=90, color='orange', linestyle='--', alpha=0.5, label='90% baseline')
    ax.axhline(y=95, color='green', linestyle='--', alpha=0.5, label='95% baseline')
    ax.legend(fontsize=10)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def generate_all_charts(report, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    chart_paths = {}
    if report.direction.dir_frequency:
        path = os.path.join(output_dir, "wind_rose.png")
        plot_wind_rose(report.direction.dir_frequency, report.direction.dir_mean_speed, path)
        chart_paths['wind_rose'] = path
    for col, dist in report.wind_stats.speed_distribution.items():
        k = report.weibull.k_values.get(col, 0)
        c = report.weibull.c_values.get(col, 0)
        name = _friendly_name(col).replace('/', '_').replace('(', '').replace(')', '')
        path = os.path.join(output_dir, f"speed_dist_{name}.png")
        plot_speed_distribution(dist, k, c, path, f"Speed Distribution - {_friendly_name(col)}")
        chart_paths[f'speed_dist_{col}'] = path
    if report.wind_stats.monthly_mean:
        path = os.path.join(output_dir, "monthly_variation.png")
        plot_monthly_variation(report.wind_stats.monthly_mean, path)
        chart_paths['monthly'] = path
    if report.wind_stats.hourly_mean:
        path = os.path.join(output_dir, "hourly_variation.png")
        plot_hourly_variation(report.wind_stats.hourly_mean, path)
        chart_paths['hourly'] = path
    heights = {}
    for col in report.wind_stats.mean_wind_speed:
        parts = col.split('_')
        if len(parts) >= 2:
            try:
                heights[col] = float(parts[1].replace('m', ''))
            except ValueError:
                pass
    path = os.path.join(output_dir, "shear_profile.png")
    plot_shear_profile(report.wind_stats.mean_wind_speed, heights, path)
    chart_paths['shear'] = path
    if report.quality.channel_completeness:
        path = os.path.join(output_dir, "data_completeness.png")
        plot_completeness(report.quality.channel_completeness, path)
        chart_paths['completeness'] = path
    return chart_paths
