"""Read-only local IPv4 discovery and deterministic phone-pairing suggestions.

``rank_network_candidates`` accepts an iterable of adapter mappings. Canonical
keys are ``interface_name``, ``interface_type`` (wifi/ethernet/vpn/virtual or an
IANA number), ``addresses`` (IPv4 strings or IPAddress mappings), ``is_up``
(bool, or None when unknown), ``gateways``, ``has_gateway``, ``is_virtual``,
``hardware_interface`` and ``description``. Common Windows JSON property names
are also accepted. No argument is mutated and ranking performs no I/O.

Only RFC1918 IPv4 addresses become candidates. Availability, physical versus
virtual, and gateway presence precede the usual 192.168/16, 10/8, 172.16/12
preference. A present, non-down explicitly saved IP overrides that order.
``recommended`` identifies the preferred entry, not verified reachability.
Duplicate IPs retain their best adapter's metadata plus all interface aliases.
The separate ``manual_entry`` is always available, even with zero candidates.
"""

import ipaddress
import json
import os
import re
import socket
import subprocess
from collections.abc import Mapping


_LAN_NETWORKS = tuple(ipaddress.IPv4Network(value) for value in (
    "192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12",
))
_ENUMERATION_TIMEOUT = 8
_VIRTUAL_PATTERN = re.compile(
    r"vpn|virtual|vethernet|hyper-v|vmware|virtualbox|\bvbox|wireguard|"
    r"wintun|tailscale|zerotier|hamachi|openvpn|sing[-_]?box|mihomo|"
    r"(?:^|[^a-z0-9])(?:tap|tun)(?:$|[^a-z0-9])|"
    r"tunnel|loopback|docker|\bwsl\b|虚拟|隧道|回环", re.IGNORECASE,
)
_WINDOWS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$adapters = @{}
Get-NetAdapter -IncludeHidden -ErrorAction Stop | ForEach-Object {
    $adapters[[int]$_.InterfaceIndex] = $_
}
$rows = @(Get-NetIPConfiguration -All -ErrorAction Stop | ForEach-Object {
    $config = $_
    $adapter = $adapters[[int]$config.InterfaceIndex]
    if ($null -eq $adapter) { $adapter = $config.NetAdapter }
    $isUp = $null
    $virtual = $null
    $hardware = $null
    $kind = $null
    if ($null -ne $adapter) {
        $isUp = ([string]$adapter.Status -eq 'Up')
        $virtual = $adapter.Virtual
        $hardware = $adapter.HardwareInterface
        $kind = $adapter.InterfaceType
    }
    [PSCustomObject]@{
        interface_name = [string]$config.InterfaceAlias
        description = [string]$config.InterfaceDescription
        interface_type = $kind
        is_up = $isUp
        is_virtual = $virtual
        hardware_interface = $hardware
        addresses = @($config.IPv4Address | ForEach-Object {
            if ($_.AddressState -eq 'Preferred' -or $_.AddressState -eq 'Deprecated') {
                [string]$_.IPAddress
            }
        })
        gateways = @($config.IPv4DefaultGateway | ForEach-Object { [string]$_.NextHop })
    }
})
ConvertTo-Json -InputObject $rows -Depth 5 -Compress
"""


def _get(adapter, *keys, default=None):
    for key in keys:
        if key in adapter and adapter[key] is not None:
            return adapter[key]
    return default


def _items(value):
    if value is None:
        return ()
    if isinstance(value, (str, Mapping)):
        return (value,)
    if isinstance(value, (list, tuple, set)):
        return value
    return ()


def _ipv4(value):
    if isinstance(value, Mapping):
        value = _get(value, "IPAddress", "address", "NextHop")
    if not isinstance(value, str):
        return None
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    return address if isinstance(address, ipaddress.IPv4Address) else None


def _lan_address(value):
    address = _ipv4(value)
    if address is not None and any(address in network for network in _LAN_NETWORKS):
        return str(address)
    return ""


def _boolean(value):
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        return {"true": True, "false": False, "1": True, "0": False}.get(value.lower())
    return None


def _availability(adapter):
    explicit = _boolean(_get(adapter, "is_up", "IsUp"))
    if explicit is not None:
        return explicit
    if _boolean(adapter.get("enabled")) is False:
        return False
    status = str(_get(adapter, "status", "Status", "OperationalStatus", default="")).casefold()
    if status in {"up", "connected", "已连接", "启用"}:
        return True
    if status in {"down", "disabled", "disconnected", "not present", "lowerlayerdown",
                  "已断开连接", "已禁用", "断开连接", "禁用"}:
        return False
    return None


def _interface_kind(adapter, name):
    raw_kind = str(_get(adapter, "interface_type", "InterfaceType", default="")).casefold()
    description = str(_get(adapter, "description", "InterfaceDescription", default=""))
    identity = f"{name} {description} {raw_kind}"
    virtual = (_boolean(_get(adapter, "is_virtual", "Virtual")) is True
               or _boolean(_get(adapter, "hardware_interface", "HardwareInterface")) is False
               or bool(_VIRTUAL_PATTERN.search(identity)) or raw_kind in {"23", "131", "ppp"})
    if virtual:
        return ("vpn" if re.search(r"vpn|wireguard|wintun|tailscale|zerotier|sing[-_]?box|mihomo|"
                                  r"(?:^|[^a-z0-9])(?:tap|tun)(?:$|[^a-z0-9])|"
                                  r"tunnel|隧道|\bppp\b", identity, re.IGNORECASE)
                or raw_kind in {"23", "131"} else "virtual"), True
    if raw_kind in {"71", "wifi", "wi-fi", "wireless", "ieee80211"}:
        return "wifi", False
    if raw_kind in {"6", "ethernet", "ethernetcsmacd"}:
        return "ethernet", False
    if re.search(r"wi[ -]?fi|wlan|wireless|无线", identity, re.IGNORECASE):
        return "wifi", False
    if re.search(r"ethernet|以太网|有线", identity, re.IGNORECASE):
        return "ethernet", False
    return "unknown", False


def _has_gateway(adapter):
    gateways = _get(adapter, "gateways", "IPv4DefaultGateway", "gateway")
    if gateways is not None:
        for value in _items(gateways):
            address = _ipv4(value)
            if address is not None and not (address.is_unspecified or address.is_loopback
                                            or address.is_link_local or address.is_multicast
                                            or address == ipaddress.IPv4Address("255.255.255.255")):
                return True
        return False
    return _boolean(_get(adapter, "has_gateway")) is True


def _rank_key(candidate):
    address = ipaddress.IPv4Address(candidate["address"])
    subnet_rank = next(index for index, network in enumerate(_LAN_NETWORKS) if address in network)
    return (
        {True: 0, None: 1, False: 2}[candidate["is_up"]],
        candidate["is_virtual"], not candidate["has_gateway"], subnet_rank,
        candidate["interface_type"] not in {"wifi", "ethernet"},
        int(address), candidate["interface_name"].casefold(), candidate["interface_name"],
        candidate["interface_type"],
    )


def rank_network_candidates(adapters, saved_address=""):
    """Return candidates, preferred_address, saved_address_valid and manual_entry.

    Saved selections must be bare RFC1918 IPv4 addresses still present on a
    non-down adapter. Unknown socket-fallback status is accepted, but never
    presented as known enabled. All-down inventories have no recommendation.
    The first candidate is preferred when a recommendation exists. No device
    probes, DNS, filesystem or subprocess calls occur in this function.
    """
    grouped = {}
    for adapter in adapters:
        if not isinstance(adapter, Mapping):
            continue
        name = str(_get(adapter, "interface_name", "InterfaceAlias", "Name", default="未知网卡"))
        interface_type, virtual = _interface_kind(adapter, name)
        addresses = _get(adapter, "addresses", "ipv4_addresses", "IPv4Address", "address")
        for value in _items(addresses):
            if isinstance(value, Mapping):
                state = value.get("AddressState")
                if state is not None and str(state).casefold() not in {"preferred", "deprecated", "3", "4"}:
                    continue
            address = _lan_address(value)
            if not address:
                continue
            candidate = {
                "address": address, "interface_name": name,
                "interface_type": interface_type, "has_gateway": _has_gateway(adapter),
                "is_up": _availability(adapter), "is_virtual": virtual,
                "recommended": False,
            }
            grouped.setdefault(address, []).append(candidate)
    candidates = []
    for entries in grouped.values():
        candidate = min(entries, key=_rank_key).copy()
        candidate["interface_names"] = sorted({entry["interface_name"] for entry in entries})
        candidate["display_name"] = f"{candidate['interface_name']} · {candidate['address']}"
        candidates.append(candidate)
    candidates.sort(key=_rank_key)
    saved = _lan_address(saved_address)
    saved_candidate = next((entry for entry in candidates
                            if entry["address"] == saved and entry["is_up"] is not False), None)
    preferred = saved_candidate or next((entry for entry in candidates if entry["is_up"] is not False), None)
    if preferred is not None:
        preferred["recommended"] = True
        candidates.remove(preferred)
        candidates.insert(0, preferred)
    return {
        "candidates": candidates,
        "preferred_address": preferred["address"] if preferred is not None else "",
        "preferred_reason": "saved" if saved_candidate else "ranked" if preferred else "none",
        "saved_address_valid": saved_candidate is not None,
        "manual_entry": {"available": True, "label": "手动输入 IP"},
    }


def _windows_adapters():
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    completed = subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
         "-Command", _WINDOWS_SCRIPT],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding="utf-8-sig", errors="strict", check=True, timeout=_ENUMERATION_TIMEOUT,
        creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=startupinfo,
    )
    result = json.loads(completed.stdout)
    if isinstance(result, Mapping):
        result = [result]
    if not isinstance(result, list) or any(not isinstance(entry, Mapping) for entry in result):
        raise ValueError("Invalid adapter enumeration response")
    return result


def _socket_adapters():
    hostname = socket.gethostname()
    addresses = socket.getaddrinfo(hostname, None, socket.AF_INET)
    return [{"interface_name": "本机地址（网卡信息未知）", "interface_type": "unknown",
             "addresses": [entry[4][0] for entry in addresses], "is_up": None}]


def discover_network_candidates(saved_address=""):
    """Enumerate local configuration only; never connect to a peer or change it.

    Windows enumeration is hidden and limited to eight seconds. If it fails or
    yields no usable RFC1918 IP, hostname socket resolution supplies a degraded
    inventory without gateway, type or enabled-state claims. No remote target
    is queried for reachability. ``discovery_source`` is windows/socket/none;
    ``discovery_error`` contains exception class names only. No app or DB state
    is accessed; callers provide any saved IP explicitly.
    """
    errors = []
    if os.name == "nt":
        try:
            result = rank_network_candidates(_windows_adapters(), saved_address)
            if result["candidates"]:
                result.update(discovery_source="windows", discovery_error="")
                return result
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            errors.append(type(error).__name__)
    try:
        result = rank_network_candidates(_socket_adapters(), saved_address)
    except OSError as error:
        errors.append(type(error).__name__)
        result = rank_network_candidates([], saved_address)
    result.update(discovery_source="socket" if result["candidates"] else "none",
                  discovery_error=", ".join(errors))
    return result
