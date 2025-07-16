#!/usr/bin/python3
"""
Module providing functions to get LLDP topology information from servers.
It includes functions to print the information in various formats (table, JSON, YAML, CSV),
test SSH connectivity, and retrieve LLDP information from servers.
"""


import argparse
import json
import logging
import sys
import subprocess
from os import linesep
from typing import Dict
from traceback import format_exc as traceback_format_exc
import paramiko
import yaml
from prettytable import PrettyTable


logger = logging.getLogger("lldp-topo")


####################################
# Global functions
####################################
def print_pretty_table(headers, rows):
    """Prints the data in a pretty table format using PrettyTable."""
    table = PrettyTable(headers)
    for row in rows:
        table.add_row(row)
    table.align = "l"
    print(table)


def print_yaml_json(headers, rows, to_json=False):
    """Prints the data in YAML or JSON format."""
    output = []
    for row in rows:
        item = {}
        for i, value in enumerate(row):
            item[headers[i]] = value
        output.append(item)
    if to_json:
        print(json.dumps(output, indent=4))
    else:
        print(yaml.safe_dump(output, indent=4, default_flow_style=False, sort_keys=False))


def print_csv(headers, rows):
    """Prints the data in CSV format."""
    print(";".join(headers))
    for row in rows:
        str_row = list(map(str, row))
        print(";".join(str_row))


def print_table(headers, rows, output_format):
    """Prints the data in the specified format."""
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
    """Sets up the logger with the specified verbosity level."""
    log_format_simple = "%(levelname)s %(message)s"
    log_format_complete = (
        "%(asctime)s %(levelname)s %(name)s %(filename)s:%(lineno)s %(funcName)s(): %(message)s"
    )
    log_formatter_simple = logging.Formatter(log_format_simple, datefmt="%Y-%m-%dT%H:%M:%S")
    handler = logging.StreamHandler()
    handler.setFormatter(log_formatter_simple)
    logger.setLevel(level=logging.WARNING)
    logger.addHandler(handler)
    if verbose == 1:
        logger.setLevel(level=logging.INFO)
    elif verbose > 1:
        log_formatter = logging.Formatter(log_format_complete, datefmt="%Y-%m-%dT%H:%M:%S")
        handler.setFormatter(log_formatter)
        logger.setLevel(level=logging.DEBUG)


def run_command(server, command, ssh_command=None):
    """Runs a command on a remote server via SSH or an alternative SSH command."""
    logger.debug("Server: %s", server)
    if not ssh_command:
        server_fields = server.split("@")
        username = server_fields[0]
        host = server_fields[1]
        client = paramiko.client.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=username)
        logger.debug("Command: %s", command)
        _, _stdout, _stderr = client.exec_command(command)
        _exit_status = _stdout.channel.recv_exit_status()
        if _exit_status:
            error_output = _stderr.read().decode().strip()
            stdout_output = _stdout.read().decode().strip()
            logger.error("[%s] Command failed: %s", server, command)
            logger.error("[%s] stderr: %s", server, error_output)
            logger.error("[%s] stdout: %s", server, stdout_output)
            raise RuntimeError(f"Command failed on {server}: {command} | stderr: {error_output}")
        logger.info("Command: '%s' completed successfully", command)
        # print(_stdout.read().decode())
        return _stdout.read().decode()
    else:
        subprocess_cmd = f"{ssh_command} {server} {command}"
        logger.info("Command: %s", subprocess_cmd)
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


def run_command_list(server, command_list, ssh_command=None):
    """Runs a list of commands on a remote server via SSH or an alternative SSH command."""
    logger.info("Server: %s", server)
    logger.info("Command list:%s%s", linesep, linesep.join(command_list))
    answer_list = []
    if not ssh_command:
        server_fields = server.split("@")
        client = paramiko.client.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(server_fields[1], username=server_fields[0])
        for command in command_list:
            logger.debug("Command: %s", command)
            _, _stdout, _stderr = client.exec_command(command)
            stdout_output = _stdout.read().decode().strip()
            error_output = _stderr.read().decode().strip()
            _exit_status = _stdout.channel.recv_exit_status()
            if _exit_status:
                logger.error("[%s] Command failed: %s", server, command)
                logger.error("[%s] stdout: %s", server, stdout_output)
                logger.error("[%s] stderr: %s", server, error_output)
                raise RuntimeError(
                    f"Command failed on {server}: {command} | stderr: {error_output}"
                )
            logger.debug("[%s] Command succeeded: %s", server, command)
            logger.debug("[%s] stdout: %s", server, stdout_output)
            answer_list.append(stdout_output)

    else:
        for command in command_list:
            subprocess_cmd = f"{ssh_command} {server} {command}"
            logger.info("Command: %s", subprocess_cmd)
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
            answer_list.append(_stdout.decode())
    if len(command_list) != len(answer_list):
        logger.warning("Length of command list executed via SSH does not match length of answers")
    return answer_list


def test_ssh_lldpcli(servers_list, ssh_command=None):
    """Test SSH connectivity and LLDPCLI command on a list of servers.
    Returns 0 if all tests pass, 1 if any test fails."""
    test_output = 0
    for server in servers_list:
        command = "echo"
        try:
            run_command(server, command, ssh_command)
            print(f"Server {server}: SSH working")
            command = "lldpcli show chassis"
            try:
                logger.info("LLDP command: %s", command)
                run_command(server, command, ssh_command)
                print(f"Server {server}: LLDPCLI working")
            except RuntimeError:
                test_output = 1
                print(f"Server {server}: LLDPCLI NOT working")
        except RuntimeError:
            test_output = 1
            print(f"Server {server}: SSH NOT working")
    return test_output


def get_iface_cmd_list(interface):
    """Generates a list of commands to get extra information about a network interface."""
    iface_cmd_list = [
        f"cat /sys/class/net/{interface}/device/device",
        f"cat /sys/class/net/{interface}/device/vendor",
        f"cat /sys/class/net/{interface}/device/numa_node",
        f"cat /sys/class/net/{interface}/speed || echo UNKNOWN SPEED",
        f"cat /sys/class/net/{interface}/operstate || echo UNKNOWN OPERSTATE",
        f"cat /sys/class/net/{interface}/device/sriov_numvfs || echo UNKNOWN NUMVFS",
    ]
    return iface_cmd_list


def map_vendor_device_id(vendor_id, device_id):
    """Maps vendor_id and device_id to vendor_name and device_name."""
    # This mapping is based on the PCI IDs and DPDK device IDs.
    # The mapping is not exhaustive and can be extended as needed.
    # Vendor IDs and Device IDs can be found in:
    # https://pci-ids.ucw.cz/read/PC
    # https://doc.dpdk.org/api-2.2/rte__pci__dev__ids_8h_source.html
    # Example of vendor_id and device_id:
    # vendor_id = "0x8086"
    # device_id = "0x10fb"
    vendor_device_mapping = {
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
                "0x165f": "BCM5120",
                "0x16d6": "BCM-57412 NextXtreme-E",
                "0x16d7": "BCM-57414 NextXtreme-E",
            },
        },
    }

    vendor_name = vendor_device_mapping.get(vendor_id, {}).get("vendor_name", "UNKNOWN VENDOR")
    device_name = (
        vendor_device_mapping.get(vendor_id, {}).get("devices", {}).get(device_id, "UNKNOWN DEVICE")
    )
    return vendor_name, device_name


def get_extra_ifaces_info(server, interface_list, iface_info_dict, ssh_command):
    """
    Get extra information from the list of physical interfaces (interface_list)
    of a server (server) via SSH (or alternative ssh_command)
    and store the inforamtion in iface_info_dict
    """
    command_list = []
    for interface in interface_list:
        command_list.extend(get_iface_cmd_list(interface))
    answers = run_command_list(server, command_list, ssh_command)
    if len(answers) != len(command_list):
        logger.warning("Length of command list executed via SSH does not match length of answers")

    answer_index = 0
    for interface in interface_list:
        device_id = answers[answer_index].strip()
        vendor_id = answers[answer_index + 1].strip()
        vendor_name, device_name = map_vendor_device_id(vendor_id, device_id)
        numa_id = answers[answer_index + 2].strip()
        speed = answers[answer_index + 3].strip()
        operstate = answers[answer_index + 4].strip()
        numvfs = answers[answer_index + 5].strip()
        answer_index += 6
        iface_info = iface_info_dict[interface]
        iface_info["device_id"] = device_id
        iface_info["device_name"] = device_name
        iface_info["vendor_id"] = vendor_id
        iface_info["vendor_name"] = vendor_name
        iface_info["numa_id"] = numa_id
        iface_info["speed"] = speed
        iface_info["operstate"] = operstate
        iface_info["numvfs"] = numvfs
        iface_info["extra"] = (
            f"{vendor_name},{vendor_id},{device_name},{device_id},{speed},{operstate},{numvfs}"
        )
        iface_info_dict[interface] = iface_info


def get_ifaces_info(server, interface_list, extra_pf_info=False, ssh_command=None):
    """
    Get information about interfaces of a server (server) via SSH (or alternative ssh_command).
    The information is stored in a dictionary (iface_dict) with interface names as keys.
    If extra_pf_info is True, it will also get extra information about physical interfaces.
    The extra information includes device ID, vendor ID, NUMA ID, speed, operstate,
    and number of VFs.
    """
    try:
        iface_dict = {}
        command_list = []
        # Generate list of commands to know iface type for each interface
        for interface in interface_list:
            command = (
                f'iface_type="pf"; [ -d "/sys/class/net/{interface}/device/physfn" ] '
                + f'&& iface_type="vf"; [ ! -d "/sys/class/net/{interface}/device" ] '
                + '&& iface_type="vlan"; echo $iface_type'
            )
            command_list.append(command)
        # Run list of commands in a single SSH session to know type of each interface
        logger.debug("Command list: %s", command_list)
        answer_list = run_command_list(server, command_list, ssh_command)
        if len(command_list) != len(answer_list):
            logger.warning(
                "Length of command list executed via SSH does not match length of answers"
            )
        # Store in iface_dict all interfaces with its type
        # At the same time, generate a list of pf-type interfaces
        physical_iface_list = []
        for iface_index, iface_name in enumerate(interface_list):
            iface_type = answer_list[iface_index].strip()
            if iface_type == "pf":
                physical_iface_list.append(iface_name)
            iface_dict[iface_name] = {
                "type": iface_type,
            }
        # Get extra information for all PF interfaces
        if extra_pf_info:
            get_extra_ifaces_info(server, physical_iface_list, iface_dict, ssh_command)
        return iface_dict

    except RuntimeError as e:
        logger.info(print(f"Server {server}: {command} DID NOT WORK"))
        error_msg = traceback_format_exc()
        logger.critical(
            "Server %s: '%s' DID NOT WORK. Exit Exception %s: %s",
            server,
            command,
            e,
            error_msg,
            exc_info=True,
        )
        sys.exit(1)


def get_lldp_info(server, ssh_command=None):
    """Get LLDP information from a server via SSH or an alternative SSH command."""
    try:
        commands = [
            "lldpcli -f json show chassis details",
            "lldpcli -f json show interfaces details",
            "lldpcli -f json show neighbors details",
        ]
        for command in commands:
            logger.info("LLDP command: %s", command)
        answers = run_command_list(server, commands, ssh_command)
        chassis = yaml.safe_load(answers[0])
        logger.debug("Server %s. Chassis: %s", server, chassis)
        interfaces = yaml.safe_load(answers[1])
        logger.debug("Server %s. Interfaces: %s", server, interfaces)
        neighbors = yaml.safe_load(answers[2])
        logger.debug("Server %s. Neighbors: %s", server, neighbors)
    except RuntimeError:
        logger.info(print(f"Server {server}: {command} DID NOT WORK"))
        e = traceback_format_exc()
        logger.critical(
            "Server %s: %s DID NOT WORK. Exit Exception: %s",
            server,
            command,
            e,
            exc_info=True,
        )
        exit(1)
    return chassis, interfaces, neighbors


def get_brws_capabilities(chassis):
    """Get BRWS capabilities from the chassis information."""
    logger.debug(
        "Capabilities: %s",
        yaml.safe_dump(chassis, indent=4, default_flow_style=False, sort_keys=False),
    )
    bridge = "X"
    router = "X"
    wlan = "X"
    station = "X"

    caps = chassis.get("capability", [])

    if isinstance(caps, dict):
        caps = [caps]

    for c in caps:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "Bridge":
            if "enabled" in c:
                bridge = str(int(c.get("enabled")))
        elif c.get("type") == "Router":
            if "enabled" in c:
                router = str(int(c.get("enabled")))
        elif c.get("type") == "Wlan":
            if "enabled" in c:
                wlan = str(int(c.get("enabled")))
        elif c.get("type") == "Station":
            if "enabled" in c:
                station = str(int(c.get("enabled")))

    brws = f"{bridge}{router}{wlan}{station}"
    return brws


def parse_neighbors(neighbors):
    """Parse the neighbors information from LLDP data."""
    neighbor_dict = {}
    neighbor_list = neighbors.get("lldp", {}).get("interface", [])
    if isinstance(neighbor_list, Dict):
        neighbor_list = [neighbor_list]
    for neigh in neighbor_list:
        for iface_name, iface_info in neigh.items():
            chassis = iface_info.get("chassis", {})
            chassis_keys = list(chassis.keys())
            if len(chassis_keys) != 1:
                logger.error(
                    "Expected a single chassis in iface info. There are %d keys: %s",
                    len(chassis_keys),
                    chassis_keys,
                )
                sys.exit(1)
            chassis_name = chassis_keys[0]
            # Expected chassis:
            # "chassis": {
            #     "SW-DAT2": {
            #         "id": {
            #             "type": "mac",
            #             "value": "0c:29:ef:c9:46:a0"
            #         },
            #         "capability": [ ...
            #         ]
            # }
            # In some cases, the name of the chassis is not sent by the switch
            # "chassis": {
            #     "id": {
            #         "type": "mac",
            #         "value": "8c:04:ba:c1:b2:40"
            #     }
            # }
            if chassis_name == "id":
                chassis_id = chassis.get("id", {})
                if chassis_id.get("type", "") == "mac" and chassis_id.get("value"):
                    chassis_mac = chassis_id["value"]
                    chassis_id = chassis_mac
                    # A name is generated based on the MAC address
                    # chassis_name = f"mac-{chassis_mac}"
                else:
                    chassis_name = "UNKNOWN"
                    chassis_id = "UNKNOWN"
                brws = get_brws_capabilities(chassis)
            else:
                chassis_id = chassis[chassis_name].get("id", {}).get("value", "UNKNOWN")
                brws = get_brws_capabilities(chassis[chassis_name])
            port = iface_info.get("port", {}).get("id", {}).get("value", "")
            neighbor_dict[iface_name] = {
                "chassis": chassis_name,
                "chassis_id": chassis_id,
                "brws": brws,
                "port": port,
            }
    logger.info(
        "Neighbor info:\n%s",
        yaml.safe_dump(neighbor_dict, indent=4, default_flow_style=False, sort_keys=False),
    )
    return neighbor_dict


####################################
# Global variables
####################################
topo = {}

####################################
# Subcommands
####################################


def get_topo_subcmd(main_args):
    """Get LLDP topology information from a list of servers."""
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

    # Go through the list of servers and
    for server in main_args.servers_list:
        # Get LLDP info and append it to rows
        logger.info("Server: %s", server)
        chassis, interfaces, neighbors = get_lldp_info(server, ssh_command=main_args.alt_command)

        # Get relevant fields from chassis
        logger.debug(
            "Chassis: %s",
            yaml.safe_dump(chassis, indent=4, default_flow_style=False, sort_keys=False),
        )
        chassis_keys = list(chassis.get("local-chassis", {}).get("chassis", {}).keys())
        if len(chassis_keys) != 1:
            logger.error("More than 1 chassis found in server %s", server)
            sys.exit(1)
        edge1 = chassis_keys[0]
        chassis_id1 = (
            chassis["local-chassis"]["chassis"][edge1].get("id", {}).get("value", "UNKNOWN")
        )
        brws1 = get_brws_capabilities(chassis["local-chassis"]["chassis"][edge1])

        # Get relevant fields from neighbors and store them in neighbors_dict[iface]
        logger.debug(
            "Neighbors: %s",
            yaml.safe_dump(neighbors, indent=4, default_flow_style=False, sort_keys=False),
        )
        neighbors_dict = parse_neighbors(neighbors)

        # Iterate over interfaces and get relevant fields from interfaces
        # and the associated neighbor
        logger.debug(
            "Interfaces: %s",
            yaml.safe_dump(interfaces, indent=4, default_flow_style=False, sort_keys=False),
        )
        interface_list = interfaces.get("lldp", {}).get("interface", [])
        for iface in interface_list:
            iface_keys = list(iface.keys())
            if len(iface_keys) != 1:
                logger.error(
                    "Expected a single key in iface dict. There are %d keys: %s",
                    len(iface_keys),
                    iface_keys,
                )
                sys.exit(1)
            # Get relevant fields from interface
            iface1 = iface_keys[0]
            # if re.match("enp.*s.*f.*", iface1) or re.match("ens.*f.*", iface1):
            #     logger.info(f"Skipping interface {iface1} since it is an SR-IOV interface")
            #     continue
            # if iface1.startswith("enx"):
            #     logger.info(f"Skipping USB-like interface {iface1}")
            #     continue
            mac1 = iface[iface1].get("port", {}).get("id", {}).get("value", "")

            # Get relevant fields from neighbors in interface iface1
            neighbor_info = neighbors_dict.get(iface1, {})
            logger.debug("neighbor_info:%s", neighbor_info)
            edge2 = neighbor_info.get("chassis")
            logger.debug("args.quick:%s", main_args.quick)
            logger.debug("edge2:%s", edge2)
            if main_args.quick and not edge2:
                continue
            chassis_id2 = neighbor_info.get("chassis_id")
            brws2 = neighbor_info.get("brws")
            iface2 = neighbor_info.get("port")

            # Get interface info from the server
            iface1_info_dict = get_ifaces_info(
                server, [iface1], extra_pf_info=main_args.extra, ssh_command=main_args.alt_command
            )
            iface1_info = iface1_info_dict[iface1]
            logger.info("Interface %s: %s", iface1, iface1_info)
            iface1_type = iface1_info["type"]
            if iface1_type != "pf":
                continue
            iface1_extra = "N/A"
            if main_args.extra:
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
            logger.info("New row: %s", new_row)
            rows.append(new_row)

    print_table(headers, rows, main_args.output)


def get_interface_list(server, ssh_command):
    """Get a list of network interfaces from a server via SSH or an alternative SSH command."""
    try:
        commands = [
            "ip -j link list",
        ]
        answers = run_command_list(server, commands, ssh_command)
        interfaces = yaml.safe_load(answers[0])
        logger.debug("Server %s. Interfaces: %s", server, interfaces)
    except RuntimeError as e:
        logger.info(print(f"Server {server}: One command of {commands} DID NOT WORK"))
        error_msg = traceback_format_exc()
        logger.critical(
            "Server %s: One command of '%s' DID NOT WORK. Exit Exception: %s: %s",
            server,
            commands,
            e,
            error_msg,
            exc_info=True,
        )
        sys.exit(1)
    return interfaces


def list_interfaces_subcmd(main_args):
    """List physical interfaces and their information from a list of servers."""
    # Initialize variables
    headers = [
        "Server",
        "Iface",
        "Type",
        "Device ID",
        "Device Name",
        "Vendor ID",
        "Vendor Name",
        "Numa ID",
        "Speed",
        "Oper State",
        "Num VFs",
    ]
    rows = []

    # Go through the list of servers and get iface info
    for server in main_args.servers_list:
        # Get LLDP info and append it to rows
        interface_list = get_interface_list(server, ssh_command=main_args.alt_command)
        interface_list2 = []
        # Get type of interface
        for iface_dict in interface_list:
            interface_name = iface_dict["ifname"]
            interface_list2.append(interface_name)
        iface_info_dict = {}
        iface_info_dict = get_ifaces_info(
            server, interface_list2, extra_pf_info=True, ssh_command=main_args.alt_command
        )
        logger.info(
            yaml.safe_dump(iface_info_dict, indent=4, default_flow_style=False, sort_keys=False)
        )

        for iface, iface_dict in iface_info_dict.items():
            if iface_dict["type"] != "pf":
                continue
            new_row = [
                server,
                iface,
                iface_dict["type"],
                iface_dict["device_id"],
                iface_dict["device_name"],
                iface_dict["vendor_id"],
                iface_dict["vendor_name"],
                iface_dict["numa_id"],
                iface_dict["speed"],
                iface_dict["operstate"],
                iface_dict["numvfs"],
            ]
            logger.info("New row: %s", new_row)
            rows.append(new_row)

    print_table(headers, rows, main_args.output)


####################################
# Main
####################################
if __name__ == "__main__":
    # Argument parse
    main_parser = argparse.ArgumentParser(prog="lldp_topo.py")
    main_parser.add_argument(
        "-o",
        "--output",
        choices=["table", "csv", "yaml", "json"],
        default="table",
        help="output format",
    )
    main_parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="increase output verbosity"
    )
    main_parser.add_argument(
        "--test",
        default=False,
        action="store_true",
        help="only test ssh connectivity and lldpcli",
    )
    main_parser.add_argument(
        "-c",
        "--alt-command",
        type=str,
        action="store",
        default=None,
        help="alternative command to connect to servers via ssh, e.g. `juju ssh`",
    )
    # main_parser.add_argument(
    #     "servers_list",
    #     metavar="SERVER",
    #     type=str,
    #     nargs="?",
    #     help="server to be connected in format `user@server`",
    # )

    # Add subparser for subcommands
    subparsers = main_parser.add_subparsers(
        dest="sub_args",
        title="subcommands",
        # description='get-topology (alias: get, gt), list-interfaces (alias: li)',
    )

    # Subparsers for the different commands
    # parser_get_topo = argparse.ArgumentParser()
    parser_get_topo = subparsers.add_parser(
        "get-topology",
        help="get LLDP topology",
        aliases=["gt", "get"],
    )
    parser_get_topo.add_argument(
        "servers_list",
        metavar="SERVER",
        type=str,
        nargs="+",
        help="server to be connected in format `user@server`",
    )
    parser_get_topo.add_argument(
        "-q",
        "--quick",
        default=False,
        action="store_true",
        help="print only LLDP neighbors, not all LLDP interfaces",
    )
    parser_get_topo.add_argument(
        "-e",
        "--extra",
        default=False,
        action="store_true",
        help="show extra info about server interfaces",
    )
    # parser_list_interfaces = argparse.ArgumentParser()
    parser_list_interfaces = subparsers.add_parser(
        "list-interfaces",
        help="list physical interfaces and their info",
        aliases=["li"],
    )
    parser_list_interfaces.add_argument(
        "servers_list",
        metavar="SERVER",
        type=str,
        nargs="+",
        help="server to be connected in format `user@server`",
    )

    # Parse args, allowing global options to reach subparsers
    # From
    # <https://stackoverflow.com/questions/46962065/
    # add-top-level-argparse-arguments-after-subparser-args>
    ns, extras = main_parser.parse_known_args()
    # print(ns)
    # print(extras)
    args = main_parser.parse_args(extras, ns)
    # print(args)

    # Initialize logger
    set_logger(args.verbose)

    # If option test is set, then Test SSH and LLDPCLI and exits
    if args.test:
        SSH_CLI_TEST_OUTPUT = test_ssh_lldpcli(args.servers_list, ssh_command=args.alt_command)
        sys.exit(SSH_CLI_TEST_OUTPUT)

    if args.sub_args in ["get-topology", "gt", "get"]:
        get_topo_subcmd(args)
    elif args.sub_args in ["list-interfaces", "li"]:
        list_interfaces_subcmd(args)
    else:
        raise NotImplementedError("Subcommand not implemented")
