import os
import json
import dataclasses
from datetime import datetime
import numpy as np


def _fn(col_name):
    parts = col_name.split('_')
    if parts[0] == 'ws' and len(parts) >= 3:
        h = parts[1]
        orient = parts[2] if parts[2] not in ('avg', 'sd', 'min', 'max') else ''
        return f"{h}({orient})" if orient else h
    elif parts[0] == 'wd':
        return parts[1] if len(parts) > 1 else col_name
    elif parts[0] in ('temp', 'pressure'):
        return parts[1] if len(parts) > 1 else col_name
    return col_name


def generate_markdown_report(mast_data, report, chart_paths, output_path):
    lines = []
    def add(text=""):
        lines.append(text)
    def add_table(headers, rows):
        add("| " + " | ".join(headers) + " |")
        add("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            add("| " + " | ".join(str(c) for c in row) + " |")

    title = mast_data.project_name
    if not title.endswith("Mast") and not title.endswith("mast"):
        title += " Mast"
    add(f"# {title} Wind Resource Assessment Report")
    add()
    add(f"**Date**: {datetime.now().strftime('%Y-%m-%d')}")
    add(f"**Mast ID**: {mast_data.mast_id}")
    add(f"**Period**: {mast_data.data_start} ~ {mast_data.data_end}")
    add(f"**Interval**: {mast_data.interval_minutes} min")
    add()

    add("## 1. Project Overview")
    add()
    add("### 1.1 Standards")
    add("- GB/T 18710-2002 Wind Energy Resource Assessment")
    add("- GB/T 18709-2002 Wind Energy Resource Measurement")
    add("- IEC 61400-12-1:2017 Power Performance Measurement")
    add("- IEC 61400-1:2019 Design Requirements")
    add()

    add("## 2. Data Overview")
    add()
    add("### 2.1 Data Completeness")
    add(f"- Total records: {report.quality.total_records}")
    add(f"- Valid records: {report.quality.valid_records}")
    add(f"- Completeness: {report.quality.completeness_pct}%")
    add(f"- Coverage months: {report.data_months}")
    add()

    if report.quality.issues:
        add("### 2.2 Data Quality Notes")
        for issue in report.quality.issues:
            add(f"- {issue}")
        add()

    if 'completeness' in chart_paths:
        add("### 2.3 Channel Completeness")
        add()
        add(f"![Completeness]({os.path.basename(chart_paths['completeness'])})")
        add()

    add("### 2.4 Channel Completeness Detail")
    add()
    ch_rows = [[_fn(col), info['valid'], info['total'], f"{info['pct']}%"]
                for col, info in sorted(report.quality.channel_completeness.items())]
    add_table(["Channel", "Valid", "Total", "Completeness"], ch_rows)
    add()

    add("## 3. Wind Speed Analysis")
    add()
    add("### 3.1 Environmental Parameters")
    add(f"- Mean temperature: {report.avg_temp} C")
    add(f"- Mean pressure: {report.avg_pressure} kPa")
    add(f"- Mean air density: {report.air_density.mean_rho} kg/m3")
    if report.air_density.mean_rho > 0:
        add(f"- Density ratio: {report.air_density.mean_rho / 1.225:.3f}")
    add()

    add("### 3.2 Wind Speed Statistics by Height")
    add()
    ws_rows = []
    for col in report.wind_stats.mean_wind_speed:
        wpd = report.wind_stats.wind_power_density.get(col, 0)
        wpd_info = report.wpd_class.get(col, {})
        grade = wpd_info.get('grade', '-')
        desc = wpd_info.get('description', '-')
        k = report.weibull.k_values.get(col, '-')
        c = report.weibull.c_values.get(col, '-')
        ws_rows.append([_fn(col), report.wind_stats.mean_wind_speed[col],
                        report.wind_stats.max_wind_speed[col], f"{wpd}",
                        f"Grade {grade} ({desc})", f"{k}", f"{c}"])
    add_table(["Height", "Mean(m/s)", "Max(m/s)", "WPD(W/m2)",
               "Class", "Weibull k", "Weibull c"], ws_rows)
    add()

    for col in report.wind_stats.speed_distribution:
        key = f'speed_dist_{col}'
        if key in chart_paths:
            add(f"#### {_fn(col)} Speed Distribution")
            add()
            add(f"![Speed Distribution]({os.path.basename(chart_paths[key])})")
            add()

    if 'monthly' in chart_paths:
        add("### 3.3 Monthly Mean Wind Speed")
        add()
        add(f"![Monthly]({os.path.basename(chart_paths['monthly'])})")
        add()

    if report.wind_stats.seasonal_mean:
        add("### 3.4 Seasonal Variation")
        add()
        for col, seasons in report.wind_stats.seasonal_mean.items():
            if seasons:
                add(f"**{_fn(col)}**: Spring {seasons.get('spring', '-')} / "
                    f"Summer {seasons.get('summer', '-')} / "
                    f"Autumn {seasons.get('autumn', '-')} / "
                    f"Winter {seasons.get('winter', '-')} m/s")
        add()

    if 'hourly' in chart_paths:
        add("### 3.5 Diurnal Variation")
        add()
        add(f"![Diurnal]({os.path.basename(chart_paths['hourly'])})")
        add()

    add("## 4. Wind Direction Analysis")
    add()
    if 'wind_rose' in chart_paths:
        add("### 4.1 Wind Rose")
        add()
        add(f"![Wind Rose]({os.path.basename(chart_paths['wind_rose'])})")
        add()

    if report.direction.dir_frequency:
        add("### 4.2 16-Sector Wind Statistics")
        add()
        dir_rows = []
        for name in DIR16_NAMES:
            freq = report.direction.dir_frequency.get(name, 0)
            spd = report.direction.dir_mean_speed.get(name, 0)
            wpd = report.direction.dir_wpd.get(name, 0)
            dir_rows.append([name, f"{freq}%", f"{spd}", f"{wpd:.0f}"])
        add_table(["Sector", "Frequency", "Mean Speed(m/s)", "WPD"], dir_rows)
        add()

    add(f"**Dominant wind direction**: {report.direction.dominant_dir} (highest frequency)")
    add(f"**Dominant energy direction**: {report.direction.dominant_energy_dir} (highest energy)")
    add()

    add("## 5. Wind Shear Analysis")
    add()
    if report.shear.alpha_values:
        shear_rows = []
        for pair, alpha in report.shear.alpha_values.items():
            eval_str = "Low" if alpha < 0.15 else "Normal" if alpha < 0.20 else "High" if alpha < 0.30 else "Very High"
            shear_rows.append([pair, f"{alpha}", eval_str])
        add_table(["Layer", "Shear alpha", "Assessment"], shear_rows)
        add()
        add(f"**Mean shear alpha**: {report.shear.mean_alpha}")
    add()

    if 'shear' in chart_paths:
        add(f"![Shear Profile]({os.path.basename(chart_paths['shear'])})")
        add()

    add("## 6. Turbulence Intensity")
    add()
    if report.turbulence.ti_values:
        ti_rows = []
        for col, ti in report.turbulence.ti_values.items():
            ti_15 = report.turbulence.ti_at_15.get(col, '-')
            iec = report.turbulence.iec_class.get(col, '-')
            ti_rows.append([_fn(col), f"{ti}", f"{ti_15}", f"{iec}"])
        add_table(["Height", "Mean TI", "TI@15m/s", "IEC Class"], ti_rows)
    add()

    add("## 7. Extreme Wind Speed")
    add()
    if report.extreme.v50:
        ext_rows = [[_fn(col), f"{v50}", report.extreme.iec_class.get(col, '-')]
                     for col, v50 in report.extreme.v50.items()]
        add_table(["Height", "V50(m/s)", "IEC Class"], ext_rows)
        add()
        if report.data_months < 12:
            add("> **Note**: Less than 1 year of data, V50 estimate has high uncertainty.")
            add()
    add()

    add("## 8. Comprehensive Assessment")
    add()
    if report.wind_stats.mean_wind_speed:
        best_col = max(report.wind_stats.mean_wind_speed, key=report.wind_stats.mean_wind_speed.get)
        best_ws = report.wind_stats.mean_wind_speed[best_col]
        best_wpd = report.wind_stats.wind_power_density.get(best_col, 0)
        best_grade = report.wpd_class.get(best_col, {})
        grade_str = f"{best_grade.get('grade', '-')}" if best_grade else '-'

        add(f"### 8.1 Wind Resource Grade")
        add(f"- Best layer: {_fn(best_col)}, annual mean {best_ws} m/s")
        add(f"- Wind power density: {best_wpd} W/m2, Grade {grade_str}")
        if report.air_density.mean_rho > 0:
            add(f"- Standard density corrected: {round(best_wpd * 1.225 / report.air_density.mean_rho, 1)} W/m2")
        add()

        add("### 8.2 Overall Assessment")
        evaluations = []
        if best_ws >= 7:
            evaluations.append(("Wind resource", "Excellent", f"Annual mean {best_ws}m/s"))
        elif best_ws >= 5.5:
            evaluations.append(("Wind resource", "Fair", f"Annual mean {best_ws}m/s"))
        else:
            evaluations.append(("Wind resource", "Poor", f"Annual mean {best_ws}m/s"))

        if report.air_density.mean_rho < 1.0:
            evaluations.append(("Air density", "Low", f"{report.air_density.mean_rho}kg/m3"))
        else:
            evaluations.append(("Air density", "Normal", f"{report.air_density.mean_rho}kg/m3"))

        if report.shear.mean_alpha < 0.1:
            evaluations.append(("Wind shear", "Low", f"a={report.shear.mean_alpha}"))
        elif report.shear.mean_alpha < 0.2:
            evaluations.append(("Wind shear", "Normal", f"a={report.shear.mean_alpha}"))
        else:
            evaluations.append(("Wind shear", "High", f"a={report.shear.mean_alpha}"))

        add_table(["Indicator", "Assessment", "Note"], [[e[0], e[1], e[2]] for e in evaluations])
        add()

    add("## 9. Conclusions & Recommendations")
    add()
    if report.wind_stats.mean_wind_speed:
        best_col = max(report.wind_stats.mean_wind_speed, key=report.wind_stats.mean_wind_speed.get)
        best_ws = report.wind_stats.mean_wind_speed[best_col]
        if best_ws >= 7:
            add(f"1. Wind resource is excellent, annual mean {best_ws}m/s, good development potential.")
        elif best_ws >= 5.5:
            add(f"1. Wind resource is fair, annual mean {best_ws}m/s, further economic analysis needed.")
        else:
            add(f"1. Wind resource is poor, annual mean {best_ws}m/s, development not recommended.")
        if report.data_months < 12:
            add(f"2. Current data only {report.data_months} months, recommend continuing measurement to 1 year.")
        if report.air_density.mean_rho < 1.0:
            add("3. Air density is low, consider density correction in energy yield estimation.")
        add("4. Recommend MCP analysis with long-term reference data.")
        add("5. Recommend CFD simulation combined with terrain for turbine layout optimization.")
    add()

    content = "\n".join(lines)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return content


DIR16_NAMES = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
               'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']


def save_analysis_json(report, output_path):
    def to_dict(obj):
        if dataclasses.is_dataclass(obj):
            return {f.name: to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
        elif isinstance(obj, dict):
            return {k: to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [to_dict(v) for v in obj]
        elif isinstance(obj, (int, float, str, bool)):
            return obj
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return str(obj)
    data = to_dict(report)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
