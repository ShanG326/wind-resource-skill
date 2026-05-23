import struct
import math
import zlib
import re
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class SensorConfig:
    sensor_id: str
    sensor_type: str  # ws, wd, temp, pressure
    height_m: float
    orientation: str
    stat_type: str    # avg, sd, min, max
    channel_name: str
    unit: str


@dataclass
class MastData:
    mast_id: str
    project_name: str
    data_start: str
    data_end: str
    interval_minutes: int = 10
    sensors: list = field(default_factory=list)
    df: Optional[pd.DataFrame] = None
    flag_names: list = field(default_factory=list)


CHANNEL_PATTERNS = [
    # nrgpy export format: Ch1_Anem_140.00m_E_Avg_m/s
    (r"Ch(\d+)_Anem_(\d+\.?\d*)m_([A-Z])_(Avg|SD|Min|Max|Gust)_(.+)",
     lambda m: SensorConfig(
         sensor_id=f"Ch{m.group(1)}", sensor_type="ws",
         height_m=float(m.group(2)), orientation=m.group(3),
         stat_type=m.group(4).lower(), channel_name=m.group(0), unit=m.group(5))),
    (r"Ch(\d+)_Vane_(\d+\.?\d*)m_([A-Z])_(Avg|SD|Min|Max|GustDir)_(.+)",
     lambda m: SensorConfig(
         sensor_id=f"Ch{m.group(1)}", sensor_type="wd",
         height_m=float(m.group(2)), orientation=m.group(3),
         stat_type=m.group(4).lower(), channel_name=m.group(0), unit=m.group(5))),
    (r"Ch(\d+)_Analog_(\d+\.?\d*)m_([A-Z])_(Avg|SD|Min|Max)_(C)",
     lambda m: SensorConfig(
         sensor_id=f"Ch{m.group(1)}", sensor_type="temp",
         height_m=float(m.group(2)), orientation="",
         stat_type=m.group(4).lower(), channel_name=m.group(0), unit=m.group(5))),
    (r"Ch(\d+)_Analog_(\d+\.?\d*)m_([A-Z])_(Avg|SD|Min|Max)_(kPa|hPa)",
     lambda m: SensorConfig(
         sensor_id=f"Ch{m.group(1)}", sensor_type="pressure",
         height_m=float(m.group(2)), orientation="",
         stat_type=m.group(4).lower(), channel_name=m.group(0), unit=m.group(5))),
    # NRG with unit suffix: Ch1_Anem_140mA_SW_Avg_m/s
    (r"Ch(\d+)_Anem_(\d+)m([A-Z]?)_(\w+)_(Avg|SD|Min|Max)_(.+)",
     lambda m: SensorConfig(
         sensor_id=f"Ch{m.group(1)}", sensor_type="ws",
         height_m=float(m.group(2)), orientation=m.group(4),
         stat_type=m.group(5).lower(), channel_name=m.group(0), unit=m.group(6))),
    (r"Ch(\d+)_Vane_(\d+)m_(\w+)_(Avg|SD|Min|Max)_(.+)",
     lambda m: SensorConfig(
         sensor_id=f"Ch{m.group(1)}", sensor_type="wd",
         height_m=float(m.group(2)), orientation=m.group(3),
         stat_type=m.group(4).lower(), channel_name=m.group(0), unit=m.group(5))),
    (r"Ch(\d+)_Temperature_(\d+)m_(Avg|SD|Min|Max)_(.+)",
     lambda m: SensorConfig(
         sensor_id=f"Ch{m.group(1)}", sensor_type="temp",
         height_m=float(m.group(2)), orientation="",
         stat_type=m.group(3).lower(), channel_name=m.group(0), unit=m.group(4))),
    (r"Ch(\d+)_Pressure_(\d+)m_(Avg|SD|Min|Max)_(.+)",
     lambda m: SensorConfig(
         sensor_id=f"Ch{m.group(1)}", sensor_type="pressure",
         height_m=float(m.group(2)), orientation="",
         stat_type=m.group(3).lower(), channel_name=m.group(0), unit=m.group(4))),
    # NRG without unit suffix
    (r"Ch(\d+)_Anem_(\d+)m([A-Z]?)_(\w+)_(Avg|SD|Min|Max)$",
     lambda m: SensorConfig(
         sensor_id=f"Ch{m.group(1)}", sensor_type="ws",
         height_m=float(m.group(2)), orientation=m.group(4),
         stat_type=m.group(5).lower(), channel_name=m.group(0), unit="m/s")),
    (r"Ch(\d+)_Vane_(\d+)m_(Avg|SD|Min|Max)$",
     lambda m: SensorConfig(
         sensor_id=f"Ch{m.group(1)}", sensor_type="wd",
         height_m=float(m.group(2)), orientation="N",
         stat_type=m.group(3).lower(), channel_name=m.group(0), unit="deg")),
    (r"Ch(\d+)_Temperature_(\d+)m_(Avg|SD|Min|Max)$",
     lambda m: SensorConfig(
         sensor_id=f"Ch{m.group(1)}", sensor_type="temp",
         height_m=float(m.group(2)), orientation="",
         stat_type=m.group(3).lower(), channel_name=m.group(0), unit="C")),
    (r"Ch(\d+)_Pressure_(\d+)m_(Avg|SD|Min|Max)$",
     lambda m: SensorConfig(
         sensor_id=f"Ch{m.group(1)}", sensor_type="pressure",
         height_m=float(m.group(2)), orientation="",
         stat_type=m.group(3).lower(), channel_name=m.group(0), unit="Kpa")),
    (r"Ch(\d+)_Temp_(\d+)m_(Avg|SD|Min|Max)$",
     lambda m: SensorConfig(
         sensor_id=f"Ch{m.group(1)}", sensor_type="temp",
         height_m=float(m.group(2)), orientation="",
         stat_type=m.group(3).lower(), channel_name=m.group(0), unit="C")),
]


def parse_channel_name(name: str) -> Optional[SensorConfig]:
    for pattern, builder in CHANNEL_PATTERNS:
        m = re.match(pattern, name)
        if m:
            return builder(m)
    return None


def _extract_channel_names(decomp: bytes) -> list[tuple[int, str]]:
    results = []
    current = []
    for i, b in enumerate(decomp):
        if 32 <= b < 127:
            current.append(chr(b))
        else:
            s = ''.join(current)
            if s and len(s) >= 10 and parse_channel_name(s):
                results.append((i - len(s), s))
            current = []
    seen = set()
    unique = []
    for pos, name in results:
        if name not in seen:
            seen.add(name)
            unique.append((pos, name))
    return unique


def _find_data_start(decomp: bytes, after_name_offset: int) -> Optional[int]:
    pos = after_name_offset
    end = min(pos + 30, len(decomp) - 4)
    while pos < end:
        if decomp[pos] == 0x00:
            check = pos + 1
            if check + 4 <= len(decomp):
                val = struct.unpack('<f', decomp[check:check+4])[0]
                if math.isnan(val) or (not math.isnan(val) and abs(val) < 1000):
                    return check
        pos += 1
    return None


def _parse_single_channel(decomp: bytes, name: str, name_offset: int,
                          next_channel_offset: int) -> Optional[tuple[str, np.ndarray, SensorConfig]]:
    config = parse_channel_name(name)
    if config is None:
        return None
    second = decomp.find(name.encode('ascii'), name_offset + len(name) + 1)
    if second < 0:
        return None
    after_second = second + len(name)
    if after_second >= len(decomp):
        return None
    unit_len = decomp[after_second]
    after_second += 1 + unit_len
    data_start = _find_data_start(decomp, after_second)
    if data_start is None:
        return None
    data_end = next_channel_offset
    for back in range(200):
        check_pos = next_channel_offset - back - 4
        if check_pos <= data_start + 4:
            break
        if check_pos + 4 <= len(decomp):
            val = struct.unpack('<f', decomp[check_pos:check_pos+4])[0]
            if math.isnan(val) or abs(val) < 1000:
                data_end = check_pos + 4
                break
    data_count = (data_end - data_start) // 4
    if data_count <= 0:
        return None
    WINDOG_INVALID = -999999.0
    values = np.empty(data_count, dtype=np.float32)
    for i in range(data_count):
        off = data_start + i * 4
        if off + 4 <= len(decomp):
            val = struct.unpack('<f', decomp[off:off+4])[0]
            if math.isnan(val) or val <= WINDOG_INVALID:
                values[i] = np.nan
            else:
                values[i] = val
        else:
            values[i] = np.nan
    col_name = f"{config.sensor_type}_{int(config.height_m)}m"
    if config.orientation:
        col_name += f"_{config.orientation}"
    col_name += f"_{config.stat_type}"
    config.channel_name = col_name
    return col_name, values, config


def read_windog(file_path: str, project_name: str = "", mast_id: str = "",
                start_date: str = "") -> MastData:
    with open(file_path, 'rb') as f:
        raw = f.read()
    if raw[:4] != b'akz\x01':
        raise ValueError("Not a valid .windog file")
    decomp = zlib.decompress(raw[12:])
    flag_names = []
    for kw in ['Icing', 'Invalid', 'Low quality', 'Synthesized', 'Tower shading']:
        if decomp.find(kw.encode('ascii')) >= 0:
            flag_names.append(kw)
    channels = _extract_channel_names(decomp)
    sensor_data = {}
    sensors = []
    for idx, (pos, name) in enumerate(channels):
        next_offset = channels[idx + 1][0] if idx + 1 < len(channels) else len(decomp)
        result = _parse_single_channel(decomp, name, pos, next_offset)
        if result:
            col_name, values, config = result
            sensor_data[col_name] = values
            sensors.append(config)
    if not sensor_data:
        raise ValueError("No channel data extracted from .windog file")
    min_len = min(len(v) for v in sensor_data.values())
    for k in sensor_data:
        sensor_data[k] = sensor_data[k][:min_len]
    df = pd.DataFrame(sensor_data)
    if not start_date:
        start_date = "2025-02-20 00:00"
    timestamps = pd.date_range(start=start_date, periods=min_len, freq='10min')
    df.insert(0, 'Timestamp', timestamps)
    if not mast_id:
        mast_id = "unknown"
    if not project_name:
        project_name = mast_id
    return MastData(
        mast_id=mast_id, project_name=project_name,
        data_start=str(timestamps[0]), data_end=str(timestamps[-1]),
        interval_minutes=10, sensors=sensors, df=df, flag_names=flag_names,
    )


def read_csv(file_path: str, project_name: str = "", mast_id: str = "") -> MastData:
    df = pd.read_csv(file_path, encoding='utf-8-sig')
    rename_map = {}
    sensors = []
    for col in df.columns:
        if col in ('Timestamp', 'DateTime', 'Date_Time'):
            continue
        config = parse_channel_name(col)
        if config:
            new_name = f"{config.sensor_type}_{int(config.height_m)}m"
            if config.orientation:
                new_name += f"_{config.orientation}"
            new_name += f"_{config.stat_type}"
            config.channel_name = new_name
            rename_map[col] = new_name
            sensors.append(config)
    df = df.rename(columns=rename_map)
    ts_col = None
    for c in ['Timestamp', 'DateTime', 'Date_Time']:
        if c in df.columns:
            ts_col = c
            break
    if ts_col:
        df[ts_col] = pd.to_datetime(df[ts_col])
    if not mast_id:
        mast_id = "unknown"
    if not project_name:
        project_name = mast_id
    timestamps = df[ts_col] if ts_col else pd.date_range(start='2025-01-01', periods=len(df), freq='10min')
    return MastData(
        mast_id=mast_id, project_name=project_name,
        data_start=str(timestamps.iloc[0]), data_end=str(timestamps.iloc[-1]),
        interval_minutes=10, sensors=sensors, df=df,
    )


def read_rld(rld_dir: str, project_name: str = "", mast_id: str = "",
             encryption_pass: str = "", client_id: str = "", client_secret: str = "",
             start_date: str = "", end_date: str = "") -> MastData:
    import os
    import tempfile
    try:
        import nrgpy
    except ImportError:
        raise ImportError(
            "Reading .rld files requires nrgpy: pip install nrgpy\n"
            "Also requires SymphoniePRO Desktop or NRG Cloud API.\n"
            "Download: https://www.nrgsystems.com/support/product-support/software/symphoniepro-desktop-application\n"
            "API: https://services.nrgsystems.com"
        )
    txt_dir = tempfile.mkdtemp(prefix="nrg_txt_")
    if client_id and client_secret:
        converter = nrgpy.nrg_api_convert(
            rld_dir=rld_dir, out_dir=txt_dir,
            encryption_pass=encryption_pass,
            client_id=client_id, client_secret=client_secret,
            start_date=start_date or "1970-01-01",
            end_date=end_date or "2150-12-31",
            export_format="csv_zipped",
        )
        converter.process()
    else:
        converter = nrgpy.local_rld(
            rld_dir=rld_dir, out_dir=txt_dir,
            encryption_pass=encryption_pass,
        )
        if not mast_id:
            mast_id = os.path.basename(rld_dir.rstrip("/\\"))
        converter.directory()
    reader = nrgpy.SymProTextRead()
    reader.concat_txt(txt_dir=txt_dir, file_filter=mast_id or "")
    if not hasattr(reader, 'data') or reader.data is None or len(reader.data) == 0:
        raise ValueError(
            "Failed to extract data from .rld files. Check:\n"
            "1. SymphoniePRO Desktop is installed\n"
            "2. Encryption password is correct\n"
            "3. .rld files are complete"
        )
    df = reader.data.copy()
    rename_map = {}
    sensors = []
    for col in df.columns:
        if col in ('Timestamp', 'DateTime', 'Date_Time', 'Date/Time'):
            continue
        config = parse_channel_name(str(col))
        if config:
            new_name = f"{config.sensor_type}_{int(config.height_m)}m"
            if config.orientation:
                new_name += f"_{config.orientation}"
            new_name += f"_{config.stat_type}"
            config.channel_name = new_name
            rename_map[col] = new_name
            sensors.append(config)
    df = df.rename(columns=rename_map)
    for config in sensors:
        if config.sensor_type == "pressure" and config.unit.lower() in ("hpa",):
            col = config.channel_name
            if col in df.columns:
                df[col] = df[col] / 10.0
    ts_col = None
    for c in ['Timestamp', 'DateTime', 'Date_Time', 'Date/Time']:
        if c in df.columns:
            ts_col = c
            break
    if ts_col:
        df[ts_col] = pd.to_datetime(df[ts_col], errors='coerce')
    if not mast_id:
        mast_id = "unknown"
    if not project_name:
        project_name = mast_id
    timestamps = df[ts_col] if ts_col else pd.date_range(
        start=start_date or '2025-01-01', periods=len(df), freq='10min')
    import shutil
    shutil.rmtree(txt_dir, ignore_errors=True)
    return MastData(
        mast_id=mast_id, project_name=project_name,
        data_start=str(timestamps.iloc[0]), data_end=str(timestamps.iloc[-1]),
        interval_minutes=10, sensors=sensors, df=df,
    )


def read_mast_data(file_path: str, project_name: str = "", mast_id: str = "",
                   start_date: str = "", **kwargs) -> MastData:
    import os
    ext = file_path.lower()
    if ext.endswith('.windog'):
        return read_windog(file_path, project_name, mast_id, start_date)
    elif ext.endswith(('.csv', '.txt')):
        return read_csv(file_path, project_name, mast_id)
    elif ext.endswith('.rld') or os.path.isdir(file_path):
        rld_dir = os.path.dirname(file_path) if ext.endswith('.rld') else file_path
        return read_rld(
            rld_dir=rld_dir, project_name=project_name, mast_id=mast_id,
            start_date=start_date,
            encryption_pass=kwargs.get('encryption_pass', ''),
            client_id=kwargs.get('client_id', ''),
            client_secret=kwargs.get('client_secret', ''),
        )
    else:
        try:
            return read_windog(file_path, project_name, mast_id, start_date)
        except ValueError:
            return read_csv(file_path, project_name, mast_id)
