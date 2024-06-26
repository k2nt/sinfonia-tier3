from typing import Optional, Dict, Any

import time
import toml
import gevent
import logging
import numpy as np
import csv
import threading
from pathlib import Path

import locust.stats
from locust import FastHttpUser, events, task, constant_throughput
from locust.runners import WorkerRunner
from yarl import URL

import src.loadtest.daemon as daemon


locust.stats.CSV_STATS_INTERVAL_SEC = 1


_NUM_CONCURRENT_REQ = 1
_RPS_PER_USER: float = 0
_CONFIG: Dict[str, Any] = dict()
_TIER2_ROOT_URL: str = ""
_APP_ROOT_URL: str = ""
_MATMUL_URL: str = ""
_REPORT_ROOT_PATH: Optional[str] = None
_MATRIX_SIZE = int = 0
# _FSCV = None  # CSV file stream


class MatMulUser(FastHttpUser):
    # Number of allowed concurrent requests
    # concurrency = 100

    @task()
    def matmul(self):        
        def _matmul():
            self.client.get(
                _MATMUL_URL,
                params={
                    'gen': _CONFIG['load']['is_generate_matrix'],
                    'sz': _MATRIX_SIZE
                    }
                )
    
        # spawn concurrent coroutines        
        pool = gevent.pool.Pool()
        for _ in range(_NUM_CONCURRENT_REQ):
            pool.spawn(_matmul)
            
        pool.join()

        
@events.test_start.add_listener
def on_startup(environment, **kw):
    environment.stats.use_response_times_cache = True
    
    init_resources()
    
    if isinstance(environment.runner, WorkerRunner):
        return
    
    start_daemons()
    logging.info('Starting master runner')
    
    
# @events.test_stop.add_listener
# def on_shutdown(environment, **kw):
#     _FSCV.close()
    
    
# @events.report_to_master.add_listener
# def on_report_to_master(client_id, data):
#     logging.info(f'Reporting to master runner ... {data}')
#     pass
        

latency_buffer = []
latency_buffer_lock = threading.Lock()

@events.worker_report.add_listener
def on_worker_report(client_id, data):
    
    stats_total = data['stats_total']
    response_times = stats_total['response_times']
    
    if not response_times:
        return
    
    response_times_list = []
    for time, count in response_times.items():
        response_times_list.extend([time] * count)

    avg_latency = np.mean(response_times_list)
    p95 = np.percentile(response_times_list, 95)
    
    num_reqs_each_sec = stats_total['num_reqs_per_sec']
    rps = sum(num_reqs_each_sec.values()) / len(num_reqs_each_sec)

    # start_ts = stats_total['start_time']
    last_request_ts = stats_total['last_request_timestamp']
    
    with latency_buffer_lock:
        latency_buffer.append([
            # round(start_ts),
            round(last_request_ts),
            round(avg_latency),
            round(p95),
            round(rps)
        ])
    
def write_latency_data(latency_csv_file):
    with latency_buffer_lock:
        if not latency_buffer:
            return
        with open(latency_csv_file, 'a') as latency_csv_fp:
            latency_csv_writer = csv.writer(latency_csv_fp)
            for worker_data in latency_buffer:
                latency_csv_writer.writerow(worker_data)
        
        latency_buffer.clear()

def latency_report_job(c: daemon.carbon_report.CarbonReportConfig):
    fn = f"latency-report-{c.num_user}-{c.rps}rps-{c.matrix_size}msz.csv"
    fp = Path(c.report_root_path) / fn
    while True:
        write_latency_data(fp)
        time.sleep(c.report_per_second)
    
        
def init_resources():
    global _CONFIG
    _CONFIG = toml.load('src/sinfonia_tier3_loadtest/.locust.autogen.toml')
    
    global _RPS_PER_USER
    _RPS_PER_USER = _CONFIG['load']['rps_per_user']
    
    global _APP_ROOT_URL
    _APP_ROOT_URL = _CONFIG['network']['app_root_url']
    
    global _TIER2_ROOT_URL
    _TIER2_ROOT_URL = _CONFIG['network']['tier2_root_url']
    
    global _MATMUL_URL
    _MATMUL_URL = str(URL(_APP_ROOT_URL) / 'matmul')
    
    global _MATRIX_SIZE
    _MATRIX_SIZE = _CONFIG['load']['matrix_size']
    
    global _REPORT_ROOT_PATH
    if 'report' in _CONFIG:
        _REPORT_ROOT_PATH = _CONFIG['report']['report_root_path']
    
    # # Open Locust statistics CSV file stream
    # global _FSCV
    # if 'report' in _CONFIG:
    #     _rps = _RPS_PER_USER * _CONFIG['load']['users']
    #     _fn = f"locust-stats-{_rps}rps-{_CONFIG['load']['matrix_size']}msz"
    #     _FSCV = open(URL(_REPORT_ROOT_PATH) / _fn)
    
    MatMulUser.wait_time = constant_throughput(_RPS_PER_USER)
        
        
def start_daemons():
    # Carbon report daemon
    if 'report' not in _CONFIG:
        return
    
    # j = daemon.carbon_report.job
    c = daemon.carbon_report.CarbonReportConfig(
        num_user=_CONFIG['load']['users'],
        bts_unix=_CONFIG['metadata']['bts_unix'],
        matrix_size=_MATRIX_SIZE,
        rps=_RPS_PER_USER * _CONFIG['load']['users'] * _NUM_CONCURRENT_REQ,
        carbon_url=str(URL(_TIER2_ROOT_URL) / 'carbon'),
        resu_url=str(URL(_TIER2_ROOT_URL) / 'resu'),
        report_per_second=_CONFIG['report']['report_per_second'],
        report_root_path=_CONFIG['report']['report_root_path'],
        )
    
    # daemon.start(j, c)
    
    t = threading.Thread(target=latency_report_job, args=[c], daemon=True)
    t.start()
