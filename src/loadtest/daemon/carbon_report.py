from __future__ import annotations
from typing import List

from dataclasses import dataclass, asdict, fields

import csv
import time
import requests
from pathlib import Path
from yarl import URL

from . import daemon


def job(c: CarbonReportConfig):
    fn = f"carbon-report-{c.bts_unix}.csv"
    fp = Path(c.report_path) / fn
    
    @dataclass(init=True)
    class _CsvFmt:
        timestamp: int
        carbon_intensity_gco2_kwh: float
        energy_use_joules: float
        carbon_emission_gco2: float
        
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

        req: requests.Response = requests.get(
            c.carbon_url,
            params={'tspad': (ct - c.bts_unix) * c.sps},
            )
        
        data = req.json()
        ci = data.get('carbon_intensity_gco2_kwh', '')
        eu = data.get('energy_use_joules', '')
        ce = data.get('carbon_emission_gco2', '')
        
        with open(fp, 'a') as f:
            w = csv.writer(f)
            w.writerow(
                _CsvFmt(
                    timestamp=int(time.time()),
                    carbon_intensity_gco2_kwh=ci,
                    energy_use_joules=eu,
                    carbon_emission_gco2=ce,
                    ).get_row()
                )
        
        time.sleep(c.interval_seconds)


@dataclass
class CarbonReportConfig(daemon.Config):
    bts_unix: int  # Base timestamp Unix
    sps: int  # Seconds per seconds
    interval_seconds: int  # Report interval
    carbon_url: URL | str  # Carbon data URL
    report_path: str  # File to save carbon CSV report