#!/usr/bin/python3

import argparse
from prettytable import PrettyTable
import json
import logging
import paramiko
import re
import subprocess
from traceback import format_exc as traceback_format_exc
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
        logger.debug(f"Command: {command} completed")
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
    for neigh in neighbors.get("lldp", {}).get("interface", []):
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
    args = parser.parse_args()

    # Initialize logger
    set_logger(args.verbose)

    # Initialize variables
    headers = [
        "Edge 1",
        "ChassisID 1",
        "BRWS 1",
        "Iface 1",
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
        logger.debug(f"Chassis: {yaml.safe_dump(chassis, indent=4, default_flow_style=False, sort_keys=False)}")

        # Get relevant fields from chassis
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
            if re.match("enp.*s.*f.*", iface1) or re.match("ens.*f.*", iface1):
                logger.info(f"Skipping interface {iface1} since it is an SR-IOV interface")
                continue
            mac1 = iface[iface1].get("port", {}).get("id", {}).get("value", "")
            # Get relevant fields from neighbors in interface iface1
            neighbor_info = neighbors_dict.get(iface1, {})
            edge2 = neighbor_info.get("chassis")
            chassis_id2 = neighbor_info.get("chassis_id")
            brws2 = neighbor_info.get("brws")
            iface2 = neighbor_info.get("port")

            rows.append(
                [
                    edge1,
                    chassis_id1,
                    brws1,
                    iface1,
                    mac1,
                    edge2,
                    chassis_id2,
                    brws2,
                    iface2,
                ]
            )

    print_table(headers, rows, args.output)
