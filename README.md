# lldp-topo

This program takes as input a list of nodes to be connected via ssh (pubkey has been injected in the node) and provides as output a table with the list of links, printing them in a table or CSV format.

The program assumes that you can access via ssh to the list of nodes/servers and they have lldpd running (the command lldpcli must be available).

## Getting started

```bash
$ ./lldp_topo.py -h
usage: lldp_topo.py [-h] [-o {table,csv,yaml,json}] [--test] [-v] SERVER [SERVER ...]

positional arguments:
  SERVER                server to be connected in format `user@server`

options:
  -h, --help            show this help message and exit
  -o {table,csv,yaml,json}, --output {table,csv,yaml,json}
                        output format
  --test                only test ssh connectivity and lldpcli
  -v, --verbose         increase output verbosity
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

## Requirements

- Python3
