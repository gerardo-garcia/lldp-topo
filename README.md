# lldp-topo

This program takes as input a list of nodes to be connected via ssh (pubkey has been injected in the node) and provides as output a table with the list of links, printing them in a table or CSV format.

The program assumes that you can access via ssh to the list of nodes/servers and they have lldpd running (the command lldpcli must be available).

The output is a list of links (two edges) with the following fields:

- Edge 1: name of the input node
- BRWS 1: capabilities of the input node (0/1/X bits corresponding to Bridge, Router, Wlan and Station)
- Iface 1: name of the interface in the input node
- Iface 1 Type: whether the interfaces in the server are `pf`, `vf`, `vlan`
- Iface 1 Extra: extra information for PF interfaces (`vendor_name,vendor_id,device_name,device_id,speed,operstate`)
- MAC 1: MAC of the interface in the input node
- Edge 2: name of the neighbor node
- BRWS 2: capabilities of the neighbor node (0/1/X bits corresponding to Bridge, Router, Wlan and Station)
- Iface 2: name of the interface in the neighbor node

The information about iface type and iface extra is obtained from the server, running some commands.

## Getting started

```bash
$ ./lldp_topo.py -h
usage: lldp_topo.py [-h] [-o {table,csv,yaml,json}] [-v] [--test] [-c COMMAND]
                    SERVER [SERVER ...]

positional arguments:
  SERVER                server to be connected in format `user@server`

optional arguments:
  -h, --help            show this help message and exit
  -o {table,csv,yaml,json}, --output {table,csv,yaml,json}
                        output format
  -v, --verbose         increase output verbosity
  --test                only test ssh connectivity and lldpcli
  -c COMMAND, --command COMMAND
                        alternative command to connect to servers via ssh,
                        e.g. `juju ssh`
  -q, --quick           print only LLDP neighbors, not all LLDP interfaces
  -e, --extra           no extra info about server interfaces
```

To get LLDP topology from a list of servers:

```bash
$ ./lldp_topo.py user1@server1 user2@server2
+------------+--------+------------+-------------------+----------------+--------+---------------------------+
| Edge 1     | BRWS 1 | Iface 1    | MAC 1             | Edge 2         | BRWS 2 | Iface 2                   |
+------------+--------+------------+-------------------+----------------+--------+---------------------------+
| server1    | 1100   | ens3f0     | 68:05:ca:38:6c:50 | None           | None   | None                      |
| server1    | 1100   | eno1       | d0:67:26:cc:f0:ea | switch1        | 11XX   | Ten-GigabitEthernet2/0/9  |
| server1    | 1100   | ens3f1     | 68:05:ca:38:6c:51 | None           | None   | None                      |
| server1    | 1100   | ens3f2     | 68:05:ca:38:6c:52 | None           | None   | None                      |
| server1    | 1100   | eno2       | d0:67:26:cc:f0:eb | switch1        | 11XX   | Ten-GigabitEthernet2/0/10 |
| server1    | 1100   | ens3f3     | 68:05:ca:38:6c:53 | None           | None   | None                      |
| server1    | 1100   | eno3       | d0:67:26:cc:f0:ec | switch1        | 11XX   | Ten-GigabitEthernet2/0/11 |
| server1    | 1100   | eno4       | d0:67:26:cc:f0:ed | switch1        | 11XX   | Ten-GigabitEthernet2/0/12 |
| server2    | 0001   | eno1       | d0:67:26:cc:f5:94 | switch1        | 11XX   | Ten-GigabitEthernet2/0/5  |
| server2    | 0001   | ens3f0     | 3c:fd:fe:9d:40:e8 | None           | None   | None                      |
| server2    | 0001   | eno2       | d0:67:26:cc:f5:95 | switch1        | 11XX   | Ten-GigabitEthernet2/0/6  |
| server2    | 0001   | ens3f1     | 3c:fd:fe:9d:40:e9 | None           | None   | None                      |
| server2    | 0001   | ens3f2     | 3c:fd:fe:9d:40:ea | None           | None   | None                      |
| server2    | 0001   | eno3       | d0:67:26:cc:f5:96 | switch1        | 11XX   | Ten-GigabitEthernet2/0/7  |
| server2    | 0001   | ens3f3     | 3c:fd:fe:9d:40:eb | None           | None   | None                      |
| server2    | 0001   | eno4       | d0:67:26:cc:f5:97 | switch1        | 11XX   | Ten-GigabitEthernet2/0/8  |
+------------+--------+------------+-------------------+----------------+--------+---------------------------+
```

The same in CSV format:

```bash
$ ./lldp_topo.py -o csv user1@server1 user2@server2
Edge 1;BRWS 1;Iface 1;MAC 1;Edge 2;BRWS 2;Iface 2
server1;1100;ens3f0;68:05:ca:38:6c:50;None;None;None
server1;1100;eno1;d0:67:26:cc:f0:ea;switch1;11XX;Ten-GigabitEthernet2/0/9
server1;1100;ens3f1;68:05:ca:38:6c:51;None;None;None
server1;1100;ens3f2;68:05:ca:38:6c:52;None;None;None
server1;1100;eno2;d0:67:26:cc:f0:eb;switch1;11XX;Ten-GigabitEthernet2/0/10
server1;1100;ens3f3;68:05:ca:38:6c:53;None;None;None
server1;1100;eno3;d0:67:26:cc:f0:ec;switch1;11XX;Ten-GigabitEthernet2/0/11
server1;1100;eno4;d0:67:26:cc:f0:ed;switch1;11XX;Ten-GigabitEthernet2/0/12
server2;0001;eno1;d0:67:26:cc:f5:94;switch1;11XX;Ten-GigabitEthernet2/0/5
server2;0001;ens3f0;3c:fd:fe:9d:40:e8;None;None;None
server2;0001;eno2;d0:67:26:cc:f5:95;switch1;11XX;Ten-GigabitEthernet2/0/6
server2;0001;ens3f1;3c:fd:fe:9d:40:e9;None;None;None
server2;0001;ens3f2;3c:fd:fe:9d:40:ea;None;None;None
server2;0001;eno3;d0:67:26:cc:f5:96;switch1;11XX;Ten-GigabitEthernet2/0/7
server2;0001;ens3f3;3c:fd:fe:9d:40:eb;None;None;None
server2;0001;eno4;d0:67:26:cc:f5:97;switch1;11XX;Ten-GigabitEthernet2/0/8
```

To test SSH access to the machines and check that LLDP works in that machine, run:

```bash
$ ./lldp_topo.py --test user1@server1 user2@server2
Server user1@server1: SSH working
Server user1@server1: LLDPCLI working
Server user2@server2: SSH working
Server user2@server2: LLDPCLI working
```

The recommended procedure to troubleshoot any problem is to use option `-v`, which logs commands used to get LLDP information, and the option `-e` which gives us extra information about the interface.

```bash
$ ./lldp_topo.py -v -e user1@server1 user2@server2
```

## Requirements

- Python3
- SSH access with public/private key to the servers to be polled.
