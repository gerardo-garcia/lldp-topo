#!/usr/bin/python3

import argparse
from prettytable import PrettyTable
import json
import logging
import paramiko
import subprocess
from traceback import format_exc as traceback_format_exc
from typing import Dict
import yaml


####################################
# Global functions
####################################
def print_pretty_table(headers, rows):
    table = PrettyTable(headers)
    for row in rows:
        table.add_row(row)
    table.align = "l"
    print(table)


def print_yaml_json(headers, rows, to_json=False):
    output = []
    for row in rows:
        item = {}
        for i in range(len(row)):
            item[headers[i]] = row[i]
        output.append(item)
    if to_json:
        print(json.dumps(output, indent=4))
    else:
        print(yaml.safe_dump(output, indent=4, default_flow_style=False, sort_keys=False))


def print_csv(headers, rows):
    print(";".join(headers))
    for row in rows:
        str_row = list(map(str, row))
        print(";".join(str_row))


def print_table(headers, rows, output_format):
    if output_format == "table":
        print_pretty_table(headers, rows)
    elif output_format == "yaml":
        print_yaml_json(headers, rows)
    elif output_format == "json":
        print_yaml_json(headers, rows, to_json=True)
    else:
        # if output_format == "csv":
        print_csv(headers, rows)


def set_logger(verbose):
    global logger
    log_format_simple = "%(levelname)s %(message)s"
    log_format_complete = "%(asctime)s %(levelname)s %(name)s %(filename)s:%(lineno)s %(funcName)s(): %(message)s"
    log_formatter_simple = logging.Formatter(log_format_simple, datefmt="%Y-%m-%dT%H:%M:%S")
    handler = logging.StreamHandler()
    handler.setFormatter(log_formatter_simple)
    logger = logging.getLogger("lldp-topo")
    logger.setLevel(level=logging.WARNING)
    logger.addHandler(handler)
    if verbose == 1:
        logger.setLevel(level=logging.INFO)
    elif verbose > 1:
        log_formatter = logging.Formatter(log_format_complete, datefmt="%Y-%m-%dT%H:%M:%S")
        handler.setFormatter(log_formatter)
        logger.setLevel(level=logging.DEBUG)


def run_command(server, command, ssh_command=None):
    logger.info(f"Server: {server}")
    if not ssh_command:
        server_fields = server.split("@")
        username = server_fields[0]
        host = server_fields[1]
        client = paramiko.client.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=username)
        logger.info(f"Command: {command}")
        _stdin, _stdout, _stderr = client.exec_command(command)
        _exit_status = _stdout.channel.recv_exit_status()
        if _exit_status:
            logger.info(f"Command: {command} failed")
            raise Exception()
        logger.info(f"Command: {command} completed successfully")
        # print(_stdout.read().decode())
        return _stdout.read().decode()
    else:
        subprocess_cmd = f"{ssh_command} {server} {command}"
        logger.info(f"Command: {subprocess_cmd}")
        result = subprocess.run(
            subprocess_cmd,
            shell=True,
            check=True,
            # Required for python<3.7
            stdout=subprocess.PIPE,
            # These 2 lines can be uncommented for python>=3.7
            # capture_output=True,
            # text=True,
        )
        _stdout = result.stdout
        # _stderr = result.stderr
        return _stdout.decode()


def test_ssh_lldpcli(servers_list, ssh_command=None):
    test_output = 0
    for server in servers_list:
        command = "echo"
        try:
            run_command(server, command, ssh_command)
            print(f"Server {server}: SSH working")
            command = "lldpcli show chassis"
            try:
                logger.info(f"LLDP command: {command}")
                run_command(server, command, ssh_command)
                print(f"Server {server}: LLDPCLI working")
            except Exception:
                test_output = 1
                print(f"Server {server}: LLDPCLI NOT working")
        except Exception:
            test_output = 1
            print(f"Server {server}: SSH NOT working")
    return test_output


def get_iface_info(server, interface, extra_pf_info=False, ssh_command=None):
    VENDOR_DEVICE_MAPPING = {
        "0x8086": {
            "vendor_name": "Intel",
            "devices": {
                "0x10fb": "Niantic IXGBE 82599 SFP",
                "0x1016": "e1000 82540EP_LOM",
                "0x1521": "e1000 I350 Copper",
                "0x1528": "Twinville IXGBE X540T",
                "0x154d": "Niantic IXGBE 82599 SFP_SF2",
                "0x1572": "Fortville XL710 SFP",
                "0x1583": "Fortville XL710 QSFP_A",
                "0x1584": "Fortville XL710 QSFP_B",
                "0x1585": "Fortville XL710 QSFP_C",
                "0x158b": "Fortville XXV710 for 25GbE SFP28",
                "0x37d2": "X722 for 10GBASE-T",
            },
        },
        "0x15b3": {
            "vendor_name": "Mellanox",
            "devices": {
                "0x1015": "MT27710 Family [ConnectX-4 Lx]",
                "0x1016": "MT27710 Family [ConnectX-4 Lx Virtual Function]",
                "0x1019": "MT28800 Family [ConnectX-5 Ex]",
            },
        },
        "0x14e4": {
            "vendor_name": "Broadcom",
            "devices": {
                "0x1657": "BCM5719",
            },
        },
    }
    # More vendor_ids in this link:
    # https://pci-ids.ucw.cz/read/PC
    # More device_ids in this link:
    # https://doc.dpdk.org/api-2.2/rte__pci__dev__ids_8h_source.html

    try:
        iface_info = {}

        command = (
            f'iface_type="pf"; [ -d "/sys/class/net/{interface}/device/physfn" ] && iface_type="vf"; '
            + f'[ ! -d "/sys/class/net/{interface}/device" ] && iface_type="vlan"; echo $iface_type'
        )
        logger.debug(f"Command before SSH: {command}")
        output = run_command(server, command, ssh_command)
        iface_type = output.strip()
        iface_info["type"] = iface_type
        if iface_type == "pf" and extra_pf_info:
            command = f"cat /sys/class/net/{interface}/device/device"
            logger.debug(f"Command before SSH: {command}")
            output = run_command(server, command, ssh_command)
            device_id = output.strip()

            command = f"cat /sys/class/net/{interface}/device/vendor"
            logger.debug(f"Command before SSH: {command}")
            output = run_command(server, command, ssh_command)
            vendor_id = output.strip()

            vendor_name = VENDOR_DEVICE_MAPPING.get(vendor_id, {}).get("vendor_name", "Unknown")
            device_name = VENDOR_DEVICE_MAPPING.get(vendor_id, {}).get("devices", {}).get(device_id, "Unknown")

            command = f"cat /sys/class/net/{interface}/device/numa_node"
            logger.debug(f"Command before SSH: {command}")
            output = run_command(server, command, ssh_command)
            numa_id = output.strip()

            command = f"cat /sys/class/net/{interface}/speed || echo UNKNOWN"
            logger.debug(f"Command before SSH: {command}")
            output = run_command(server, command, ssh_command)
            speed = output.strip()

            command = f"cat /sys/class/net/{interface}/operstate || echo UNKNOWN"
            logger.debug(f"Command before SSH: {command}")
            output = run_command(server, command, ssh_command)
            operstate = output.strip()

            iface_info["device_id"] = device_id
            iface_info["device_name"] = device_name
            iface_info["vendor_id"] = vendor_id
            iface_info["vendor_name"] = vendor_name
            iface_info["numa_id"] = numa_id
            iface_info["speed"] = speed
            iface_info["operstate"] = operstate
            iface_info["extra"] = f"{vendor_name},{vendor_id},{device_name},{device_id},{speed},{operstate}"
    except Exception:
        logger.info(print(f"Server {server}: {command} DID NOT WORK"))
        e = traceback_format_exc()
        logger.critical(
            f"Server {server}: {command} DID NOT WORK. Exit Exception: {e}",
            exc_info=True,
        )
        exit(1)
    return iface_info


def get_lldp_info(server, ssh_command=None):
    try:
        command = "lldpcli -f json show chassis details"
        logger.info(f"LLDP command: {command}")
        output = run_command(server, command, ssh_command)
        chassis = yaml.safe_load(output)
        logger.debug(f"Server {server}. Chassis: {chassis}")
        logger.info(f"LLDP command: {command}")
        command = "lldpcli -f json show interfaces details"
        output = run_command(server, command, ssh_command)
        interfaces = yaml.safe_load(output)
        logger.debug(f"Server {server}. Interfaces: {interfaces}")
        logger.info(f"LLDP command: {command}")
        command = "lldpcli -f json show neighbors details"
        output = run_command(server, command, ssh_command)
        neighbors = yaml.safe_load(output)
        logger.debug(f"Server {server}. Neighbors: {neighbors}")
    except Exception:
        logger.info(print(f"Server {server}: {command} DID NOT WORK"))
        e = traceback_format_exc()
        logger.critical(
            f"Server {server}: {command} DID NOT WORK. Exit Exception: {e}",
            exc_info=True,
        )
        exit(1)
    return chassis, interfaces, neighbors


def get_brws_capabilities(chassis):
    logger.debug(f"Capabilities: {yaml.safe_dump(chassis, indent=4, default_flow_style=False, sort_keys=False)}")
    bridge = "X"
    router = "X"
    wlan = "X"
    station = "X"
    for c in chassis.get("capability", []):
        if c.get("type") == "Bridge":
            if "enabled" in c:
                bridge = str(int(c.get("enabled")))
            continue
        if c.get("type") == "Router":
            if "enabled" in c:
                router = str(int(c.get("enabled")))
            continue
        if c.get("type") == "Wlan":
            if "enabled" in c:
                wlan = str(int(c.get("enabled")))
            continue
        if c.get("type") == "Station":
            if "enabled" in c:
                station = str(int(c.get("enabled")))
            continue
    brws = f"{bridge}{router}{wlan}{station}"
    return brws


def get_neighbors(neighbors):
    neighbor_dict = {}
    neighbor_list = neighbors.get("lldp", {}).get("interface", [])
    if isinstance(neighbor_list, Dict):
        neighbor_list = [neighbor_list]
    for neigh in neighbor_list:
        for iface_name, iface_info in neigh.items():
            chassis = iface_info.get("chassis", {})
            chassis_keys = list(chassis.keys())
            if len(chassis_keys) != 1:
                logger.error(f"Expected a single chassis in iface info. There are {len(chassis_keys)} keys: {chassis_keys}")
                exit(1)
            chassis_name = chassis_keys[0]
            chassis_id = chassis[chassis_name].get("id", {}).get("value", "UNKNOWN")
            brws = get_brws_capabilities(chassis[chassis_name])
            port = iface_info.get("port", {}).get("id", {}).get("value", "")
            neighbor_dict[iface_name] = {
                "chassis": chassis_name,
                "chassis_id": chassis_id,
                "brws": brws,
                "port": port,
            }
    logger.info(f"Neighbor info:\n{yaml.safe_dump(neighbor_dict, indent=4, default_flow_style=False, sort_keys=False)}")
    return neighbor_dict


####################################
# Global variables
####################################
topo = {}

####################################
# Main
####################################
if __name__ == "__main__":
    # Argument parse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        choices=["table", "csv", "yaml", "json"],
        default="table",
        help="output format",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0, help="increase output verbosity")
    parser.add_argument(
        "--test",
        default=False,
        action="store_true",
        help="only test ssh connectivity and lldpcli",
    )
    parser.add_argument(
        "-c",
        "--command",
        type=str,
        action="store",
        default=None,
        help="alternative command to connect to servers via ssh, e.g. `juju ssh`",
    )
    parser.add_argument(
        "servers_list",
        metavar="SERVER",
        type=str,
        nargs="+",
        help="server to be connected in format `user@server`",
    )
    parser.add_argument(
        "-q",
        "--quick",
        default=False,
        action="store_true",
        help="print only LLDP neighbors, not all LLDP interfaces",
    )
    parser.add_argument(
        "-e",
        "--extra",
        default=False,
        action="store_true",
        help="no extra info about server interfaces",
    )
    args = parser.parse_args()

    # Initialize logger
    set_logger(args.verbose)

    # Initialize variables
    headers = [
        "Edge 1",
        "ChassisID 1",
        "BRWS 1",
        "Iface 1",
        "Iface 1 Type",
        "Iface 1 Extra",
        "MAC 1",
        "Edge 2",
        "ChassisID 2",
        "BRWS 2",
        "Iface 2",
    ]
    rows = []

    if args.test:
        # Test SSH and LLDPCLI and exits
        test_output = test_ssh_lldpcli(args.servers_list, ssh_command=args.command)
        exit(test_output)
    for server in args.servers_list:
        # Get LLDP info and append it to rows
        logger.info(f"Server: {server}")
        chassis, interfaces, neighbors = get_lldp_info(server, ssh_command=args.command)

        # Get relevant fields from chassis
        logger.debug(f"Chassis: {yaml.safe_dump(chassis, indent=4, default_flow_style=False, sort_keys=False)}")
        chassis_keys = list(chassis.get("local-chassis", {}).get("chassis", {}).keys())
        if len(chassis_keys) != 1:
            logger.error(f"More than 1 chassis found in server {server}")
            exit(1)
        edge1 = chassis_keys[0]
        chassis_id1 = chassis["local-chassis"]["chassis"][edge1].get("id", {}).get("value", "UNKNOWN")
        brws1 = get_brws_capabilities(chassis["local-chassis"]["chassis"][edge1])

        # Get relevant fields from neighbors and store them in neighbors_dict[iface]
        logger.debug(f"Neighbors: {yaml.safe_dump(neighbors, indent=4, default_flow_style=False, sort_keys=False)}")
        neighbors_dict = get_neighbors(neighbors)

        # Iterate over interfaces and get relevant fields from interfaces and the associated neighbor
        logger.debug(f"Interfaces: {yaml.safe_dump(interfaces, indent=4, default_flow_style=False, sort_keys=False)}")
        interface_list = interfaces.get("lldp", {}).get("interface", [])
        for iface in interface_list:
            iface_keys = list(iface.keys())
            if len(chassis_keys) != 1:
                logger.error(f"Expected a single key in iface dict. There are {len(chassis_keys)} keys: {iface_keys}")
                exit(1)
            # Get relevant fields from interface
            iface1 = iface_keys[0]
            # if re.match("enp.*s.*f.*", iface1) or re.match("ens.*f.*", iface1):
            #     logger.info(f"Skipping interface {iface1} since it is an SR-IOV interface")
            #     continue
            mac1 = iface[iface1].get("port", {}).get("id", {}).get("value", "")

            # Get relevant fields from neighbors in interface iface1
            neighbor_info = neighbors_dict.get(iface1, {})
            edge2 = neighbor_info.get("chassis")
            logger.debug(f"args.quick:{args.quick}")
            logger.debug(f"edge2:{edge2}")
            if args.quick and not edge2:
                continue
            chassis_id2 = neighbor_info.get("chassis_id")
            brws2 = neighbor_info.get("brws")
            iface2 = neighbor_info.get("port")

            # Get interface info from the server
            iface1_info = get_iface_info(server, iface1, extra_pf_info=args.extra, ssh_command=args.command)
            logger.info(f"Interface {iface1}: {iface1_info}")
            iface1_type = iface1_info["type"]
            if iface1_type != "pf":
                continue
            iface1_extra = "N/A"
            if args.extra:
                iface1_extra = iface1_info["extra"]
            new_row = [
                edge1,
                chassis_id1,
                brws1,
                iface1,
                iface1_type,
                iface1_extra,
                mac1,
                edge2,
                chassis_id2,
                brws2,
                iface2,
            ]
            logger.info(f"New row: {new_row}")
            rows.append(new_row)

    print_table(headers, rows, args.output)
