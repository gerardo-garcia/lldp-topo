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
from os import linesep


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
    logger.debug(f"Server: {server}")
    if not ssh_command:
        server_fields = server.split("@")
        username = server_fields[0]
        host = server_fields[1]
        client = paramiko.client.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=username)
        logger.debug(f"Command: {command}")
        _stdin, _stdout, _stderr = client.exec_command(command)
        _exit_status = _stdout.channel.recv_exit_status()
        if _exit_status:
            logger.error(f"Command: {command} failed")
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


def run_command_list(server, command_list, ssh_command=None):
    logger.info(f"Server: {server}")
    logger.info(f"Command list:{linesep}{linesep.join(command_list)}")
    answer_list = []
    if not ssh_command:
        server_fields = server.split("@")
        username = server_fields[0]
        host = server_fields[1]
        client = paramiko.client.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=username)
        for command in command_list:
            logger.debug(f"Command: {command}")
            _stdin, _stdout, _stderr = client.exec_command(command)
            _exit_status = _stdout.channel.recv_exit_status()
            if _exit_status:
                logger.error(f"Command: {command} failed")
                raise Exception()
            logger.debug(f"Command: {command} completed successfully")
            # print(_stdout.read().decode())
            answer_list.append(_stdout.read().decode())
    else:
        for command in command_list:
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
            answer_list.append(_stdout.decode())
    if len(command_list) != len(answer_list):
        logger.warning("Length of command list executed via SSH does not match length of answers")
    return answer_list


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


def get_iface_cmd_list(interface):
    iface_cmd_list = [
        f"cat /sys/class/net/{interface}/device/device",
        f"cat /sys/class/net/{interface}/device/vendor",
        f"cat /sys/class/net/{interface}/device/numa_node",
        f"cat /sys/class/net/{interface}/speed || echo UNKNOWN",
        f"cat /sys/class/net/{interface}/operstate || echo UNKNOWN",
        f"cat /sys/class/net/{interface}/device/sriov_numvfs || echo UNKNOWN",
    ]
    return iface_cmd_list


def map_vendor_device_id(vendor_id, device_id):
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

    vendor_name = VENDOR_DEVICE_MAPPING.get(vendor_id, {}).get("vendor_name", "Unknown")
    vendor_name = VENDOR_DEVICE_MAPPING.get(vendor_id, {}).get("devices", {}).get(device_id, "Unknown")
    return vendor_name, vendor_name


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
        iface_info["extra"] = f"{vendor_name},{vendor_id},{device_name},{device_id},{speed},{operstate},{numvfs}"
        iface_info_dict[interface] = iface_info


def get_ifaces_info(server, interface_list, extra_pf_info=False, ssh_command=None):
    try:
        iface_dict = {}
        command_list = []
        # Generate list of commands to know iface type for each interface
        for interface in interface_list:
            command = (
                f'iface_type="pf"; [ -d "/sys/class/net/{interface}/device/physfn" ] && iface_type="vf"; '
                + f'[ ! -d "/sys/class/net/{interface}/device" ] && iface_type="vlan"; echo $iface_type'
            )
            command_list.append(command)
        # Run list of commands in a single SSH session to know type of each interface
        logger.debug(f"Command list: {command_list}")
        answer_list = run_command_list(server, command_list, ssh_command)
        if len(command_list) != len(answer_list):
            logger.warning("Length of command list executed via SSH does not match length of answers")
        # Store in iface_dict all interfaces with its type
        # At the same time, generate a list of pf-type interfaces
        physical_iface_list = []
        for iface_index in range(len(interface_list)):
            iface_name = interface_list[iface_index]
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

    except Exception:
        logger.info(print(f"Server {server}: {command} DID NOT WORK"))
        e = traceback_format_exc()
        logger.critical(
            f"Server {server}: {command} DID NOT WORK. Exit Exception: {e}",
            exc_info=True,
        )
        exit(1)


def get_lldp_info(server, ssh_command=None):
    try:
        commands = [
            "lldpcli -f json show chassis details",
            "lldpcli -f json show interfaces details",
            "lldpcli -f json show neighbors details",
        ]
        for command in commands:
            logger.info(f"LLDP command: {command}")
        answers = run_command_list(server, commands, ssh_command)
        chassis = yaml.safe_load(answers[0])
        logger.debug(f"Server {server}. Chassis: {chassis}")
        interfaces = yaml.safe_load(answers[1])
        logger.debug(f"Server {server}. Interfaces: {interfaces}")
        neighbors = yaml.safe_load(answers[2])
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


def parse_neighbors(neighbors):
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
            # Expected chassis:
            # "chassis": {
            #     "SW-DAT2": {
            #         "id": {
            #             "type": "mac",
            #             "value": "0c:29:ef:c9:46:a0"
            #         },
            #     "capability": [ ...
            #     ]
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
    logger.info(f"Neighbor info:\n{yaml.safe_dump(neighbor_dict, indent=4, default_flow_style=False, sort_keys=False)}")
    return neighbor_dict


####################################
# Global variables
####################################
topo = {}

####################################
# Subcommands
####################################


def get_topo_subcmd(args):
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
    for server in args.servers_list:
        # Get LLDP info and append it to rows
        logger.info(f"Server: {server}")
        chassis, interfaces, neighbors = get_lldp_info(server, ssh_command=args.alt_command)

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
        neighbors_dict = parse_neighbors(neighbors)

        # Iterate over interfaces and get relevant fields from interfaces and the associated neighbor
        logger.debug(f"Interfaces: {yaml.safe_dump(interfaces, indent=4, default_flow_style=False, sort_keys=False)}")
        interface_list = interfaces.get("lldp", {}).get("interface", [])
        for iface in interface_list:
            iface_keys = list(iface.keys())
            if len(iface_keys) != 1:
                logger.error(f"Expected a single key in iface dict. There are {len(iface_keys)} keys: {iface_keys}")
                exit(1)
            # Get relevant fields from interface
            iface1 = iface_keys[0]
            # if re.match("enp.*s.*f.*", iface1) or re.match("ens.*f.*", iface1):
            #     logger.info(f"Skipping interface {iface1} since it is an SR-IOV interface")
            #     continue
            mac1 = iface[iface1].get("port", {}).get("id", {}).get("value", "")

            # Get relevant fields from neighbors in interface iface1
            neighbor_info = neighbors_dict.get(iface1, {})
            logger.debug(f"neighbor_info:{neighbor_info}")
            edge2 = neighbor_info.get("chassis")
            logger.debug(f"args.quick:{args.quick}")
            logger.debug(f"edge2:{edge2}")
            if args.quick and not edge2:
                continue
            chassis_id2 = neighbor_info.get("chassis_id")
            brws2 = neighbor_info.get("brws")
            iface2 = neighbor_info.get("port")

            # Get interface info from the server
            iface1_info_dict = get_ifaces_info(server, [iface1], extra_pf_info=args.extra, ssh_command=args.alt_command)
            iface1_info = iface1_info_dict[iface1]
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


def get_interface_list(server, ssh_command):
    try:
        commands = [
            "ip -j link list",
        ]
        answers = run_command_list(server, commands, ssh_command)
        interfaces = yaml.safe_load(answers[0])
        logger.debug(f"Server {server}. Interfaces: {interfaces}")
    except Exception:
        logger.info(print(f"Server {server}: One command of {commands} DID NOT WORK"))
        e = traceback_format_exc()
        logger.critical(
            f"Server {server}: One command of {commands} DID NOT WORK. Exit Exception: {e}",
            exc_info=True,
        )
        exit(1)
    return interfaces


def list_interfaces_subcmd(args):
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
    for server in args.servers_list:
        # Get LLDP info and append it to rows
        interface_list = get_interface_list(server, ssh_command=args.alt_command)
        interface_list2 = []
        # Get type of interface
        for iface_index in range(len(interface_list)):
            interface_name = interface_list[iface_index]["ifname"]
            interface_list2.append(interface_name)
        iface_info_dict = {}
        iface_info_dict = get_ifaces_info(server, interface_list2, extra_pf_info=True, ssh_command=args.alt_command)
        logger.info(yaml.safe_dump(iface_info_dict, indent=4, default_flow_style=False, sort_keys=False))

        for iface in iface_info_dict:
            if iface_info_dict[iface]["type"] != "pf":
                continue
            new_row = [
                server,
                iface,
                iface_info_dict[iface]["type"],
                iface_info_dict[iface]["device_id"],
                iface_info_dict[iface]["device_name"],
                iface_info_dict[iface]["vendor_id"],
                iface_info_dict[iface]["vendor_name"],
                iface_info_dict[iface]["numa_id"],
                iface_info_dict[iface]["speed"],
                iface_info_dict[iface]["operstate"],
                iface_info_dict[iface]["numvfs"],
            ]
            logger.info(f"New row: {new_row}")
            rows.append(new_row)

    print_table(headers, rows, args.output)


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
    main_parser.add_argument("-v", "--verbose", action="count", default=0, help="increase output verbosity")
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
        help="no extra info about server interfaces",
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
    # From <https://stackoverflow.com/questions/46962065/add-top-level-argparse-arguments-after-subparser-args>
    ns, extras = main_parser.parse_known_args()
    # print(ns)
    # print(extras)
    args = main_parser.parse_args(extras, ns)
    # print(args)

    # Initialize logger
    set_logger(args.verbose)

    # If option test is set, then Test SSH and LLDPCLI and exits
    if args.test:
        test_output = test_ssh_lldpcli(args.servers_list, ssh_command=args.alt_command)
        exit(test_output)

    if args.sub_args in ["get-topology", "gt", "get"]:
        get_topo_subcmd(args)
    elif args.sub_args in ["list-interfaces", "li"]:
        list_interfaces_subcmd(args)
    else:
        raise Exception("Subcommand not implemented")
