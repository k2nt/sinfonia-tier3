#
# Sinfonia
#
# deploy helm charts to a cloudlet kubernetes cluster for edge-native applications
#
# Copyright (c) 2022-2023 Carnegie Mellon University
#
# SPDX-License-Identifier: MIT
#

from __future__ import annotations
from typing import Optional

import time
import argparse
from uuid import UUID
from enum import IntEnum
import json 
import csv 

import typer
from requests.exceptions import HTTPError, ConnectionError
from yarl import URL

from src.domain import format
from . import __version__
from .cloudlet_deployment import sinfonia_deploy, CloudletDeployment
from .local_deployment import sinfonia_runapp
from .geolocation import GeoLocation
from .app_name import uuid_to_app_name, app_name_to_uuid


# Amherst, MA
# CLIENT_GEOLOCATION = GeoLocation(lat=42.340382, long=-72.496819)

# Jacksonville, FL
CLIENT_GEOLOCATION = GeoLocation(lat=30.209041, long=-81.592600)
# Region
CONFIG_FILE = 'src/sinfonia_tier3_loadtest/NM.json'
LATENCY_FILE = 'src/sinfonia_tier3_loadtest/NM.csv'
GEOLOC_FILE = 'src/sinfonia_tier3_loadtest/NM-geoloc.csv'
# Zone
CLIENT_ZONE = 'Jacksonville'
INJECTED_LATENCY = 0


cli = typer.Typer()


class DeploymentStatus(IntEnum):
    DEPLOYED = 0
    TIMEOUT = 1
    HTTP_ERROR = 2
    FAILED = 3
    
    
def deployment_status_repr(s: DeploymentStatus):
    r = format.str.bold(s.name)
    if s == DeploymentStatus.DEPLOYED:
        return format.str.green(r)
    return format.str.red(r)


def highlight_repr(s: str) -> str:
    return format.str.bold(format.str.magenta(s))


def get_value(csv_file, row_name, col_name):
    with open(csv_file, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['client'] == row_name:
                return float(row[col_name])

def get_geoloc_value(csv_file, row_name):
    with open(csv_file, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['client'] == row_name:
                return float(row['latitude']), float(row['longitude'])


def print_deployment_status(
        app_uuid: UUID,
        deployments: list[CloudletDeployment], 
        connected_deployment: CloudletDeployment,
        deployment_status: DeploymentStatus,
        error_log: Optional[str] = None
):
    print()
    print("DEPLOYMENT STATUS:")
    print(f"  * Connection status: {deployment_status_repr(deployment_status)}")
    
    if error_log is not None:
        print(f"  * Log: {format.str.red(error_log)}")
        return
    
    deployment_hosts = []
    for d in deployments:
        for _, v in d.tunnel_config.peers.items():
            deployment_hosts.append(str(v.endpoint_host))
            
    connected_deployment_peers_data = list(connected_deployment.tunnel_config.peers.values())
    connected_deployment_host = str(connected_deployment_peers_data[0].endpoint_host)
    app_key = connected_deployment.application_key
    deploy_name = connected_deployment.deployment_name
    
    with open(CONFIG_FILE) as json_file:
        config = json.load(json_file)
        
        if connected_deployment_host in config.keys():
            server_zone = config[connected_deployment_host]
            global INJECTED_LATENCY
            INJECTED_LATENCY = get_value(LATENCY_FILE, CLIENT_ZONE, server_zone) / 2
        else:
            print(f'{connected_deployment_host} is not in the config. Pleae check the config file {CONFIG_FILE}!')
    
    print(f"  * Client geolocation: {CLIENT_GEOLOCATION}")
    print(f"  * Client zone: {CLIENT_ZONE}")
    print(f"  * Host zone: {server_zone}")
    print(f"  * Simulated latency (milliseconds): {INJECTED_LATENCY}")
    print(f"  * Deployed app: {app_uuid} ({uuid_to_app_name(app_uuid)})")
    print(f"  * Deployment size: {len(deployments)}")
    print(f"  * Deployment hosts: {deployment_hosts}")
    print(f"  * Connected host IP: {highlight_repr(connected_deployment_host)}")
    print(f"  * Application key: {app_key}")
    print(f"  * Deployment name: {deploy_name}")
    print()
    
    
def print_separator():
    print("========================================")


@cli.command()
def sinfonia_tier3_loadtest(
        tier1_url: str = typer.Option("http://192.168.245.31:5000"),
        dry_run: bool = typer.Option(False),
        app_uuid: str = typer.Option("loadtest"),
        app_port: int = typer.Option(30080),
        local_app: str = typer.Option("/bin/bash"),
        loadtest_config_path: str = typer.Option("src/sinfonia_tier3_loadtest/.cli.toml"),
        T: int = typer.Option(5, help="Number of samples"),
        config_debug: bool = typer.Option(False),
        debug: bool = typer.Option(False),
        zone: str = typer.Option(""),
        web_port: int = typer.Option(8089),
        master_port: int = typer.Option(5557),
) -> int:
    if zone:
        global CLIENT_ZONE
        CLIENT_ZONE = zone
        
    lat, long = get_geoloc_value(GEOLOC_FILE, CLIENT_ZONE)
    global CLIENT_GEOLOCATION
    CLIENT_GEOLOCATION = GeoLocation(lat=lat, long=long)
    
    try:
        app_uuid = UUID(app_uuid)
    except Exception:
        try:
            app_uuid = app_name_to_uuid(app_uuid)
        except Exception as e:
            print(f"app not supported")
            exit(1)
    
    for t in range(T):
        print()
        print()
        print(f"STARTING SAMPLE T = {t+1} (of {T})")
        print_separator()
        print()
        
        # Request one or more backend deployments
        
        deployment_status = DeploymentStatus.DEPLOYED
        deployment_data = None
        deployments = None
        error_log = None
        
        try:
            print("Deploying... ")
            deployments = sinfonia_deploy(
                tier1_url=URL(tier1_url), 
                geoloc=CLIENT_GEOLOCATION, 
                app_uuid=app_uuid, 
                debug=debug
                )
            print("Done!")
        except ConnectionError:
            deployment_status = DeploymentStatus.TIMEOUT
            error_log = "failed to connect to sinfonia-tier1"
        except HTTPError as e:
            deployment_status = DeploymentStatus.HTTP_ERROR
            error_log = f'failed to deploy backend: "{e.response.text}"'
        except Exception as e:
            deployment_status = DeploymentStatus.FAILED
            error_log = f'failed with message: {e}'

        # Pick the best deployment (first returned for now...)
        if error_log is None:
            deployment_data = deployments[0]
            deployment_peers_data = list(deployment_data.tunnel_config.peers.values())
            deployment_host = str(deployment_peers_data[0].endpoint_host)
        
        # print(deployments[0])
        
        print_deployment_status(
            app_uuid=app_uuid,
            deployments=deployments,
            deployment_status=deployment_status,
            error_log=error_log,
            connected_deployment=deployment_data,
            )
        
        if error_log:
            break
        
        # This is to wait for loadtest app to completely terminate
        # Not ideal (and can bug), but this seems to work for now
        print()
        print("10-second countdown before test starts")
        for i in range(10, 0, -1):
            print(f"{i} ... ", end='', flush=True)
            time.sleep(1)
        print("Done!")
            
        if dry_run:
            continue
        
        try:
            with format.str.ForeCyan():
                sinfonia_runapp(
                    deployment_data.deployment_name,
                    deployment_data.tunnel_config,
                    deployment_host,
                    loadtest_config_path,
                    local_app,
                    INJECTED_LATENCY,
                    CLIENT_ZONE,
                    web_port,
                    master_port,
                    app_port,
                    config_debug,
                    )
        except Exception as e:
            print(f"exception: {e}")
            break
    
    print()    
    print()
    print("TEST RECAP (NOT IMPLEMENTED)")
    print_separator()
    print()


if __name__ == '__main__':
    cli()
