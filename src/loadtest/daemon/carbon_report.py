from __future__ import annotations
from typing import List

import csv
import time
import requests
from dataclasses import dataclass, asdict, fields
from pathlib import Path

from yarl import URL

from . import daemon


def job(c: CarbonReportConfig):
    fn = f"carbon-report-{int(c.rps)}rps-{c.matrix_size}msz.csv"
    fp = Path(c.report_root_path) / fn
    
    @dataclass(init=True)
    class _CsvFmt:
        timestamp: int
        carbon_intensity_gco2_kwh: float
        energy_use_joules: float
        carbon_emission_gco2: float
        cpu_ratio_pct: float
        mem_ratio_pct: float
        
        @classmethod
        def get_column(cls) -> List:
            all_fields = fields(cls)
            return [field.name for field in all_fields]
        
        def get_row(self) -> List:
            return list(asdict(self).values())
    
    # Write column names to report file
    with open(fp, 'a') as f:
        w = csv.writer(f)
        w.writerow(_CsvFmt.get_column())
    
    while True:
        ct = int(time.time())

        req_carbon = requests.get(
            c.carbon_url,
            params={'tspad': (ct - c.bts_unix) * c.clock_seconds_per_second},
            )
        
        data = req_carbon.json()
        ci = data.get('carbon_intensity_gco2_kwh', '')
        eu = data.get('energy_use_joules', '')
        ce = data.get('carbon_emission_gco2', '')
        
        req_resu = requests.get(
            c.resu_url,
            # params={'tspad': (ct - c.bts_unix) * c.clock_seconds_per_second},
            params={'tspad': 0}
            )
        
        data_resu = req_resu.json()
        cpu_ratio = data_resu.get('cpu_ratio', '')
        mem_ratio = data_resu.get('mem_ratio', '')
        
        with open(fp, 'a') as f:
            w = csv.writer(f)
            w.writerow(
                _CsvFmt(
                    timestamp=int(time.time()),
                    carbon_intensity_gco2_kwh=ci,
                    energy_use_joules=eu,
                    carbon_emission_gco2=ce,
                    cpu_ratio_pct=cpu_ratio * 100,
                    mem_ratio_pct=mem_ratio * 100
                    ).get_row()
                )
        
        time.sleep(c.report_per_second)


@dataclass(init=True)
class CarbonReportConfig(daemon.Config):
    bts_unix: int  # Base timestamp Unix
    matrix_size: int  
    rps: int  # RPS for the current session
    clock_seconds_per_second: int  # Seconds per seconds
    carbon_url: URL | str  # Carbon data URL
    resu_url: URL | str  # Resource usage URL
    report_per_second: int  # Report interval
    report_root_path: str  # File to save carbon CSV report
