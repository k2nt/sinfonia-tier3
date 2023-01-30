#
# Sinfonia
#
# deploy helm charts to a cloudlet kubernetes cluster for edge-native applications
#
# Copyright (c) 2022 Carnegie Mellon University
#
# SPDX-License-Identifier: MIT
#

from __future__ import annotations

import argparse
from typing import Sequence
from uuid import UUID

import pyqrcode
from requests.exceptions import HTTPError
from yarl import URL

from . import __version__
from .cloudlet_deployment import sinfonia_deploy
from .local_deployment import sinfonia_runapp

ALIASES = {
    "helloworld": "00000000-0000-0000-0000-000000000000",
}


def app_uuid(value: str) -> UUID:
    uuid = ALIASES.get(value, value)
    return UUID(uuid)


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """parse those args"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config-debug",
        action="store_true",
        help="Create wireguard and resolv config in current directory",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Extra logging for debugging"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--qrcode", action="store_true", help="Generate QR code for wireguard-android"
    )
    parser.add_argument(
        "--zeroconf",
        action="store_true",
        help="Try to discover local Tier2 through MDNS",
    )
    parser.add_argument("tier1_url", metavar="tier1-url", type=URL)
    parser.add_argument("application_uuid", metavar="application-uuid", type=app_uuid)
    parser.add_argument("application", nargs=argparse.REMAINDER)
    return parser.parse_args(args)


def sinfonia_tier3(
    tier1_url: URL | str,
    application_uuid: UUID,
    application: Sequence[str],
    config_debug: bool = False,
    debug: bool = False,
    qrcode: bool = False,
    zeroconf: bool = False,
) -> int:
    # Request one or more backend deployments
    try:
        print("Deploying... ", end="", flush=True)
        deployments = sinfonia_deploy(URL(tier1_url), application_uuid, debug, zeroconf)
        print("done")
    except ConnectionError:
        print("failed to connect to sinfonia-tier1/-tier2")
        return 1
    except HTTPError as e:
        print(f'failed to deploy backend: "{e.response.text}"')
        return 1

    # Pick the best deployment (first returned for now...)
    deployment_data = deployments[0]

    if qrcode:
        wgconf = deployment_data.tunnel_config.to_wgconfig(wgquick_format=True)

        # Hacky way to add the wireguard-android specific IncludedApplications.
        # We could probably extend wireguard-tools to add these as well as
        # adding a method to generate the qrcode object.
        if application:
            included_apps = ",".join(application)
            wgconf.replace(
                "[Interface]", f"[Interface]\nIncludedApplications = {included_apps}"
            )

        qrconf = pyqrcode.create(wgconf, error="L")
        print(qrconf.terminal(quiet_zone=1))
        return 0

    return sinfonia_runapp(
        deployment_data.deployment_name,
        deployment_data.tunnel_config,
        application,
        config_debug,
    )


def main() -> int:
    args = parse_args()
    return sinfonia_tier3(
        args.tier1_url,
        args.application_uuid,
        args.application,
        config_debug=args.config_debug,
        debug=args.debug,
        qrcode=args.qrcode,
        zeroconf=args.zeroconf,
    )
