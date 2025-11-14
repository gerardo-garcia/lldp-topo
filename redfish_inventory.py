#!/usr/bin/env python3
"""
redfish_inventory.py
Connects to a Redfish instance and retrieves:
 - number of CPUs
 - total memory (GiB)
 - number of disks (and total size if available)
 - number of network interfaces

Usage:
    python redfish_inventory.py https://IP_OR_HOST username password [--insecure]

Example:
    python redfish_inventory.py https://192.0.2.10 admin P@ssw0rd --insecure
"""
import logging
import sys
import argparse
import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin
import urllib3

urllib3.disable_warnings()
logger = logging.getLogger(__name__)
redfish_path = "/redfish/v1/"


# ----- Utilities -----
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


def get_json(session, base, path):
    """GET a path (absolute or relative) and return JSON or None."""
    url = path if path.startswith("http") else urljoin(base, path)
    try:
        r = session.get(url, timeout=10)
        r.raise_for_status()
        logger.debug(f"GET {url} succeeded. Json: {r.json()}")
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed GET {url}: {e}")
        return None


def safe_int(xs, default=0):
    try:
        return int(xs)
    except Exception:
        return default


def bytes_to_gib(bytes_val):
    try:
        return float(bytes_val) / (1024**3)
    except Exception:
        return None


# ----- Specific extraction -----
def count_processors(session, base, system):
    logger.info("Counting processors...")
    # Try ProcessorSummary.Count
    ps = system.get("ProcessorSummary") or {}
    if "Count" in ps:
        return safe_int(ps["Count"])
    # Try /Processors collection
    if "Processors" in system and system["Processors"].get("@odata.id"):
        proc_coll = get_json(session, base, system["Processors"]["@odata.id"])
        if proc_coll and "Members" in proc_coll:
            return len(proc_coll["Members"])
    # Fallback: search for resources whose @odata.type includes "Processor"
    found = search_for_type(session, base, system, "Processor")
    if found is not None:
        return found
    return 0


def count_memory(session, base, system):
    logger.info("Counting memory...")
    # Try MemorySummary.TotalSystemMemoryGiB
    ms = system.get("MemorySummary") or {}
    if "TotalSystemMemoryGiB" in ms:
        try:
            return float(ms["TotalSystemMemoryGiB"])
        except Exception:
            pass
    # Try /Memory collection
    total_bytes = 0
    if "Memory" in system and system["Memory"].get("@odata.id"):
        mem_coll = get_json(session, base, system["Memory"]["@odata.id"])
        if mem_coll and "Members" in mem_coll:
            for m in mem_coll["Members"]:
                mem = get_json(session, base, m.get("@odata.id") or m.get("@odata.id", ""))
                if not mem:
                    continue
                # Look for CapacityMiB or CapacityBytes
                if "CapacityMiB" in mem:
                    total_bytes += safe_int(mem["CapacityMiB"]) * 1024 * 1024
                elif "CapacityBytes" in mem:
                    total_bytes += safe_int(mem["CapacityBytes"])
                elif "CapacityKB" in mem:
                    total_bytes += safe_int(mem["CapacityKB"]) * 1024
    # If we collected something
    if total_bytes > 0:
        gib = bytes_to_gib(total_bytes)
        return round(gib, 2)
    # Fallback: if MemorySummary.TotalSystemMemoryGiB doesn't exist and no collection -> return None
    return None


def count_disks(session, base, system):
    logger.info("Counting disks...")
    # Many locations: /Systems/{id}/Storage -> Drives, or /Chassis/.../Drives
    disks = []
    total_bytes = 0
    # 1) Try Storage within the system
    if "Storage" in system and system["Storage"].get("@odata.id"):
        stor = get_json(session, base, system["Storage"]["@odata.id"])
        if stor and "Members" in stor:
            # Each member is a Storage resource that may have Drives
            for s in stor["Members"]:
                sres = get_json(session, base, s.get("@odata.id"))
                if not sres:
                    continue
                if "Drives" in sres:
                    for drive in sres["Drives"]:
                        drv_coll = get_json(session, base, drive["@odata.id"])
                        if drv_coll and "Members" in drv_coll:
                            for d in drv_coll["Members"]:
                                disks.append(d.get("@odata.id") or d.get("Id") or str(d))
                                dres = get_json(session, base, d.get("@odata.id"))
                                if dres:
                                    if "CapacityBytes" in dres:
                                        total_bytes += safe_int(dres["CapacityBytes"])
                                    elif "CapacityGB" in dres:
                                        total_bytes += safe_int(dres["CapacityGB"]) * (1024**3)
    # 2) Search in Chassis -> Drives
    chassis = get_json(session, base, f"{redfish_path}/Chassis")
    if chassis and "Members" in chassis:
        for c in chassis["Members"]:
            cres = get_json(session, base, c.get("@odata.id"))
            if not cres:
                continue
            if "Drives" in cres and cres["Drives"].get("@odata.id"):
                drv_coll = get_json(session, base, cres["Drives"]["@odata.id"])
                if drv_coll and "Members" in drv_coll:
                    for d in drv_coll["Members"]:
                        if (d.get("@odata.id") or d.get("Id")) not in disks:
                            disks.append(d.get("@odata.id") or d.get("Id") or str(d))
                            dres = get_json(session, base, d.get("@odata.id"))
                            if dres:
                                if "CapacityBytes" in dres:
                                    total_bytes += safe_int(dres["CapacityBytes"])
                                elif "CapacityGB" in dres:
                                    total_bytes += safe_int(dres["CapacityGB"]) * (1024**3)
    # Result
    count = len(disks)
    size_gib = round(bytes_to_gib(total_bytes), 2) if total_bytes > 0 else None
    return count, size_gib


def count_interfaces(session, base, system):
    logger.info("Counting network interfaces...")
    # Check EthernetInterfaces / NetworkInterfaces in System
    interfaces = []
    # 1) EthernetInterfaces
    if "EthernetInterfaces" in system and system["EthernetInterfaces"].get("@odata.id"):
        eth = get_json(session, base, system["EthernetInterfaces"]["@odata.id"])
        if eth and "Members" in eth:
            for m in eth["Members"]:
                interfaces.append(m.get("@odata.id") or m.get("Id") or str(m))
    # 2) NetworkInterfaces
    if "NetworkInterfaces" in system and system["NetworkInterfaces"].get("@odata.id"):
        net = get_json(session, base, system["NetworkInterfaces"]["@odata.id"])
        if net and "Members" in net:
            for m in net["Members"]:
                if (m.get("@odata.id") or m.get("Id") or str(m)) not in interfaces:
                    interfaces.append(m.get("@odata.id") or m.get("Id") or str(m))
    return len(interfaces)


def search_for_type(session, base, system, type_keyword):
    """
    Simple search: looks in members of related collections and counts
    resources whose @odata.type contains type_keyword.
    Returns count or None if nothing found.
    """
    checked = set()
    to_check = []
    # Add common links
    for link in ("Processors", "Memory", "EthernetInterfaces", "NetworkInterfaces", "Storage"):
        if link in system and isinstance(system[link], dict) and system[link].get("@odata.id"):
            to_check.append(system[link]["@odata.id"])
    # Add System itself
    to_check.append(system.get("@odata.id") or "")
    found = 0
    for path in to_check:
        if not path:
            continue
        coll = get_json(session, base, path)
        if not coll:
            continue
        # Look for Members
        if "Members" in coll:
            for m in coll["Members"]:
                mpath = m.get("@odata.id")
                if not mpath or mpath in checked:
                    continue
                checked.add(mpath)
                mres = get_json(session, base, mpath)
                if not mres:
                    continue
                otype = mres.get("@odata.type", "")
                if (
                    type_keyword.lower() in otype.lower()
                    or type_keyword.lower() in str(mres.get("Name", "")).lower()
                ):
                    found += 1
    return found if found > 0 else None


# ----- Main -----
def inventory(base_url, username, password, verify_ssl=True):
    session = requests.Session()
    session.auth = HTTPBasicAuth(username, password)
    session.verify = verify_ssl
    session.headers.update({"Accept": "application/json"})

    logger.info(f"Connecting to Redfish service at {base_url}{redfish_path} ...")
    root = get_json(session, base_url, redfish_path)
    if not root:
        logger.error("Failed to retrieve %s, cannot proceed.", redfish_path)
        return None

    logger.info("Retrieving Systems ...")
    systems = get_json(
        session, base_url, root.get("Systems", {}).get("@odata.id", f"{redfish_path}Systems")
    )
    if not systems or "Members" not in systems:
        logger.error("Systems not found in Redfish service.")
        return None

    results = []
    for sys_m in systems["Members"]:
        sys_path = sys_m.get("@odata.id")
        sys_res = get_json(session, base_url, sys_path)
        if not sys_res:
            continue
        sys_name = sys_res.get("Name") or sys_res.get("Id") or sys_path
        cpus = count_processors(session, base_url, sys_res)
        mem_gib = count_memory(session, base_url, sys_res)
        disk_count, disk_gib = count_disks(session, base_url, sys_res)
        if_count = count_interfaces(session, base_url, sys_res)
        results.append(
            {
                "System": sys_name,
                "CPUs": cpus,
                "Memory_GiB": mem_gib,
                "Disk_count": disk_count,
                "Disk_total_GiB": disk_gib,
                "Network_interfaces": if_count,
                "System_path": sys_path,
            }
        )
    return results


def main():
    parser = argparse.ArgumentParser(description="Basic inventory via Redfish")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="increase output verbosity"
    )
    parser.add_argument("base", help="Base URL (e.g. https://192.0.2.10)")
    parser.add_argument("user", help="Username")
    parser.add_argument("password", help="Password")
    parser.add_argument("--insecure", action="store_true", help="Do not verify TLS certificate")
    args = parser.parse_args()

    print(args)

    # Initialize logger
    set_logger(args.verbose)

    res = inventory(args.base, args.user, args.password, verify_ssl=not args.insecure)
    if not res:
        print("No inventory obtained.")
        sys.exit(2)

    # Display results
    for r in res:
        print("----")
        print(f"System: {r['System']}")
        print(f"  Path: {r['System_path']}")
        print(f"  CPUs: {r['CPUs']}")
        print(f"  Memory (GiB): {r['Memory_GiB']}")
        print(
            f"  Disks: {r['Disk_count']}"
            + (f" (≈ {r['Disk_total_GiB']} GiB)" if r["Disk_total_GiB"] else "")
        )
        print(f"  Network interfaces: {r['Network_interfaces']}")
    print("---- End ----")


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    main()
