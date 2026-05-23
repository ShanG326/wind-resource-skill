#!/usr/bin/env python3
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from windog_reader import read_mast_data
from wind_analysis import run_full_analysis
from chart_generator import generate_all_charts
from report_generator import generate_markdown_report, save_analysis_json


def main():
    parser = argparse.ArgumentParser(description='Wind Resource Assessment Report Generator')
    parser.add_argument('data_file', help='Wind data file/directory path (.windog / .csv / .rld / directory)')
    parser.add_argument('--project-name', default='', help='Project name')
    parser.add_argument('--mast-id', default='', help='Mast ID')
    parser.add_argument('--start-date', default='', help='Data start date (YYYY-MM-DD)')
    parser.add_argument('--elevation', type=float, default=0, help='Mast elevation (m)')
    parser.add_argument('--output-dir', default='.', help='Output directory')
    parser.add_argument('--encryption-pass', default='', help='NRG .rld encryption password')
    parser.add_argument('--client-id', default='', help='NRG Cloud API client ID')
    parser.add_argument('--client-secret', default='', help='NRG Cloud API client secret')

    args = parser.parse_args()

    data_file = args.data_file
    if not os.path.exists(data_file):
        print(f"Error: file/directory not found: {data_file}")
        sys.exit(1)

    project_name = args.project_name or os.path.splitext(os.path.basename(data_file.rstrip('/\\')))[0]
    mast_id = args.mast_id or ''
    output_dir = args.output_dir

    print("=" * 60)
    print("Wind Resource Assessment Report Generator")
    print("=" * 60)
    print(f"Data file: {data_file}")
    print(f"Project: {project_name}")
    print(f"Mast ID: {mast_id or '(auto)'}")
    print()

    # 1. Read data
    print("[1/5] Reading wind data...")
    try:
        rld_kwargs = {}
        if args.encryption_pass:
            rld_kwargs['encryption_pass'] = args.encryption_pass
        if args.client_id:
            rld_kwargs['client_id'] = args.client_id
        if args.client_secret:
            rld_kwargs['client_secret'] = args.client_secret
        mast_data = read_mast_data(
            data_file, project_name=project_name, mast_id=mast_id,
            start_date=args.start_date, **rld_kwargs,
        )
        print(f"  Period: {mast_data.data_start} ~ {mast_data.data_end}")
        print(f"  Rows: {len(mast_data.df)}")
        print(f"  Sensors: {len(mast_data.sensors)}")
    except Exception as e:
        print(f"  Error: {e}")
        sys.exit(1)

    # 2. Analysis
    print("\n[2/5] Running wind resource analysis...")
    try:
        report = run_full_analysis(mast_data.df, mast_data.sensors, elevation=args.elevation)
        print(f"  Air density: {report.air_density.mean_rho} kg/m3")
        if report.wind_stats.mean_wind_speed:
            best = max(report.wind_stats.mean_wind_speed, key=report.wind_stats.mean_wind_speed.get)
            print(f"  Max mean wind speed: {report.wind_stats.mean_wind_speed[best]} m/s")
            print(f"  Max wind power density: {report.wind_stats.wind_power_density[best]} W/m2")
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 3. Charts
    print("\n[3/5] Generating charts...")
    charts_dir = os.path.join(output_dir, f"{project_name}_wind_report_charts")
    try:
        chart_paths = generate_all_charts(report, charts_dir)
        print(f"  Generated {len(chart_paths)} charts")
    except Exception as e:
        print(f"  Warning: {e}")
        chart_paths = {}

    # 4. Reports
    print("\n[4/5] Generating reports...")
    report_path = os.path.join(output_dir, f"{project_name}_wind_report.md")
    json_path = os.path.join(output_dir, f"{project_name}_analysis.json")
    try:
        generate_markdown_report(mast_data, report, chart_paths, report_path)
        print(f"  Markdown: {report_path}")
    except Exception as e:
        print(f"  Warning: {e}")
    try:
        save_analysis_json(report, json_path)
        print(f"  JSON data: {json_path}")
    except Exception as e:
        print(f"  Warning: {e}")

    # 5. Done
    print(f"\n[5/5] Done!")
    print(f"  Report: {report_path}")
    print(f"  Data: {json_path}")
    print(f"  Charts: {charts_dir}/")
    print("=" * 60)
    return report_path


if __name__ == '__main__':
    main()
