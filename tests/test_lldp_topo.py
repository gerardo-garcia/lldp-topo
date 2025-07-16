"""Test cases for lldp_topo module"""

import pytest
import lldp_topo


def test_map_vendor_device_id_known():
    """Test mapping of known vendor and device IDs."""
    vendor, device = lldp_topo.map_vendor_device_id("0x8086", "0x10fb")
    assert vendor == "Intel"
    assert device == "Niantic IXGBE 82599 SFP"


def test_map_vendor_device_id_unknown():
    """Test mapping of unknown vendor and device IDs."""
    vendor, device = lldp_topo.map_vendor_device_id("0x9999", "0x9999")
    assert vendor == "UNKNOWN VENDOR"
    assert device == "UNKNOWN DEVICE"


def test_get_iface_cmd_list():
    """Test retrieval of interface command list."""
    cmds = lldp_topo.get_iface_cmd_list("eth0")
    assert isinstance(cmds, list)
    assert any("eth0" in cmd for cmd in cmds)


def test_get_brws_capabilities_all_disabled():
    """Test retrieval of Bridge, Router, Wlan, Station capabilities when all are disabled."""
    chassis = {
        "capability": [
            {"type": "Bridge", "enabled": 0},
            {"type": "Router", "enabled": 0},
            {"type": "Wlan", "enabled": 0},
            {"type": "Station", "enabled": 0},
        ]
    }
    brws = lldp_topo.get_brws_capabilities(chassis)
    assert brws == "0000"


def test_get_brws_capabilities_all_enabled():
    """Test retrieval of Bridge, Router, Wlan, Station capabilities when all are enabled."""
    chassis = {
        "capability": [
            {"type": "Bridge", "enabled": 1},
            {"type": "Router", "enabled": 1},
            {"type": "Wlan", "enabled": 1},
            {"type": "Station", "enabled": 1},
        ]
    }
    brws = lldp_topo.get_brws_capabilities(chassis)
    assert brws == "1111"


def test_parse_neighbors_named_chassis():
    """Test parsing neighbors with named chassis."""
    neighbors = {
        "lldp": {
            "interface": [
                {
                    "eth0": {
                        "chassis": {
                            "SW-DAT2": {
                                "id": {"type": "mac", "value": "0c:29:ef:c9:46:a0"},
                                "capability": [
                                    {"type": "Bridge", "enabled": 1},
                                    {"type": "Router", "enabled": 0},
                                ],
                            }
                        },
                        "port": {"id": {"value": "Gi1/0/1"}},
                    }
                }
            ]
        }
    }
    result = lldp_topo.parse_neighbors(neighbors)
    assert "eth0" in result
    assert result["eth0"]["chassis"] == "SW-DAT2"
    assert result["eth0"]["chassis_id"] == "0c:29:ef:c9:46:a0"
    assert result["eth0"]["brws"] == "10XX"
    assert result["eth0"]["port"] == "Gi1/0/1"


def test_parse_neighbors_mac_chassis():
    """Test parsing neighbors with MAC chassis."""
    neighbors = {
        "lldp": {
            "interface": [
                {
                    "eth1": {
                        "chassis": {
                            "SW-DAT2": {
                                "id": {"type": "mac", "value": "8c:04:ba:c1:b2:40"},
                                "capability": [
                                    {"type": "Bridge", "enabled": 1},
                                    {"type": "Router", "enabled": 1},
                                ],
                            },
                        },
                        "port": {"id": {"value": "Gi1/0/2"}},
                    }
                }
            ]
        }
    }
    result = lldp_topo.parse_neighbors(neighbors)
    assert "eth1" in result
    assert result["eth1"]["chassis"] == "SW-DAT2"
    assert result["eth1"]["chassis_id"] == "8c:04:ba:c1:b2:40"
    assert result["eth1"]["brws"] == "11XX"
    assert result["eth1"]["port"] == "Gi1/0/2"


def test_parse_neighbors_multiple_chassis():
    """Test parsing neighbors with multiple chassis."""
    neighbors = {
        "lldp": {
            "interface": [
                {
                    "eth2": {
                        "chassis": {
                            "A": {},
                            "B": {},
                        },
                        "port": {"id": {"value": "Gi1/0/3"}},
                    }
                }
            ]
        }
    }
    with pytest.raises(SystemExit):
        lldp_topo.parse_neighbors(neighbors)
