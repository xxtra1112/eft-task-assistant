import copy
import json
import socket
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import network_candidates as network


def adapter(name, addresses, kind="ethernet", up=True, gateway=True, **metadata):
    return {"interface_name": name, "addresses": addresses, "interface_type": kind,
            "is_up": up, "has_gateway": gateway, **metadata}


def ranked_addresses(result):
    return [entry["address"] for entry in result["candidates"]]


def test_192_preferred_across_healthy_physical_adapters_without_mutating_input():
    adapters = [adapter("以太网", ["10.2.0.4"]),
                adapter("无线网络连接", ["192.168.3.8"], "wifi"),
                adapter("办公室", ["172.20.0.5"])]
    original = copy.deepcopy(adapters)
    result = network.rank_network_candidates(adapters)
    assert ranked_addresses(result) == ["192.168.3.8", "10.2.0.4", "172.20.0.5"]
    assert result["preferred_address"] == "192.168.3.8"
    assert sum(entry["recommended"] for entry in result["candidates"]) == 1
    assert result["candidates"][0]["display_name"] == "无线网络连接 · 192.168.3.8"
    assert adapters == original


@pytest.mark.parametrize("degraded", [
    adapter("WiFi", ["192.168.0.8"], "wifi", up=False),
    adapter("WiFi", ["192.168.0.8"], "wifi", gateway=False),
    adapter("WireGuard", ["192.168.0.8"]),
    adapter("vEthernet (WSL)", ["192.168.0.8"]),
    adapter("办公隧道", ["192.168.0.8"], "131"),
    adapter("任意名称", ["192.168.0.8"], hardware_interface=False),
    adapter("singbox_tun", ["192.168.0.8"]),
    adapter("Mihomo", ["192.168.0.8"]),
])
def test_down_gatewayless_and_virtual_192_are_below_healthy_10(degraded):
    result = network.rank_network_candidates([degraded, adapter("以太网", ["10.1.0.2"])])
    assert ranked_addresses(result) == ["10.1.0.2", "192.168.0.8"]


def test_no_192_keeps_both_other_rfc1918_ranges_and_manual_entry():
    result = network.rank_network_candidates([
        adapter("B", ["172.31.255.254"]), adapter("A", ["10.255.255.254"]),
    ])
    assert ranked_addresses(result) == ["10.255.255.254", "172.31.255.254"]
    assert result["preferred_address"] == "10.255.255.254"
    assert result["manual_entry"]["available"] is True


@pytest.mark.parametrize("saved", ["10.2.0.5", "172.16.0.9", " 10.2.0.5 "])
def test_saved_present_ip_wins_even_on_gatewayless_vpn(saved):
    result = network.rank_network_candidates([
        adapter("WiFi", ["192.168.1.5"], "wifi"),
        adapter("VPN", ["10.2.0.5", "172.16.0.9"], gateway=False),
    ], saved)
    assert result["saved_address_valid"] is True
    assert result["preferred_reason"] == "saved"
    assert result["candidates"][0]["address"] == saved.strip()
    assert result["candidates"][0]["recommended"] is True


@pytest.mark.parametrize("saved", ["10.2.0.99", "172.16.0.9", "8.8.8.8", "::1",
                                  "192.168.1.5:8765", "http://192.168.1.5", "", None])
def test_invalid_absent_or_down_saved_selection_falls_back(saved):
    result = network.rank_network_candidates([
        adapter("WiFi", ["192.168.1.5"], "wifi"),
        adapter("旧网卡", ["172.16.0.9"], up=False),
    ], saved)
    assert result["saved_address_valid"] is False
    assert result["preferred_reason"] == "ranked"
    assert result["preferred_address"] == "192.168.1.5"


def test_all_down_keeps_addresses_but_does_not_recommend_one():
    result = network.rank_network_candidates([adapter("旧网卡", ["192.168.1.4"], up=False)],
                                             "192.168.1.4")
    assert ranked_addresses(result) == ["192.168.1.4"]
    assert result["preferred_address"] == ""
    assert result["preferred_reason"] == "none"
    assert result["saved_address_valid"] is False
    assert result["candidates"][0]["recommended"] is False


def test_multiple_ips_and_aliases_choose_best_metadata_without_borrowing_gateway():
    adapters = [adapter("VPN别名", ["192.168.1.5"], gateway=True),
                adapter("无线网卡", ["192.168.1.5", "192.168.1.6", "192.168.1.5"],
                        "wifi", gateway=False),
                adapter("已断开别名", ["192.168.1.5"], up=False)]
    result = network.rank_network_candidates(adapters)
    assert ranked_addresses(result) == ["192.168.1.5", "192.168.1.6"]
    candidate = result["candidates"][0]
    assert candidate["interface_name"] == "无线网卡"
    assert candidate["interface_type"] == "wifi"
    assert candidate["has_gateway"] is False
    assert set(candidate["interface_names"]) == {"VPN别名", "无线网卡", "已断开别名"}
    assert network.rank_network_candidates(list(reversed(adapters))) == result


@pytest.mark.parametrize("name,kind,expected", [
    ("无线网络连接", "", "wifi"), ("以太网 2", "", "ethernet"),
    ("Adaptateur sans fil", 71, "wifi"), ("Netzwerk", 6, "ethernet"),
    ("LAN", "ethernet", "ethernet"), ("WLAN", "", "wifi"),
    ("本地连接", 23, "vpn"), ("任意名称", "unknown", "unknown"),
])
def test_localized_names_and_numeric_interface_types(name, kind, expected):
    result = network.rank_network_candidates([adapter(name, ["192.168.5.8"], kind)])
    assert result["candidates"][0]["interface_type"] == expected


@pytest.mark.parametrize("address", [
    "100.64.0.1", "100.127.255.254", "169.254.1.1", "127.0.0.1", "8.8.8.8",
    "0.0.0.0", "224.0.0.1", "255.255.255.255", "192.0.0.8", "198.18.0.1",
    "172.15.255.255", "172.32.0.0", "192.169.0.1", "192.168.999.1",
    "192.168.1.1/24", "192.168.001.1", "::1", "fd00::1", "fe80::1%5",
    "::ffff:192.168.1.1", "invalid", "", None, 12345,
])
def test_only_literal_rfc1918_ipv4_is_lan(address):
    result = network.rank_network_candidates([adapter("LAN", [address])], address)
    assert result["candidates"] == []
    assert result["preferred_address"] == ""
    assert result["manual_entry"]["available"] is True


def test_windows_shaped_fixture_and_unusable_address_states():
    result = network.rank_network_candidates([{
        "InterfaceAlias": "无线网络连接", "InterfaceType": 71, "Status": "Up",
        "IPv4Address": [{"IPAddress": "192.168.1.9", "AddressState": "Preferred"},
                        {"IPAddress": "192.168.1.10", "AddressState": "Tentative"},
                        {"IPAddress": "192.168.1.11", "AddressState": "Duplicate"}],
        "IPv4DefaultGateway": [{"NextHop": "192.168.1.1"}], "HardwareInterface": True,
    }])
    assert ranked_addresses(result) == ["192.168.1.9"]
    assert result["candidates"][0]["has_gateway"] is True
    assert result["candidates"][0]["is_up"] is True


def test_numeric_windows_address_states_keep_only_deprecated_and_preferred():
    result = network.rank_network_candidates([adapter("LAN", [
        {"IPAddress": f"192.168.1.{state + 1}", "AddressState": state}
        for state in range(6)
    ])])
    assert ranked_addresses(result) == ["192.168.1.4", "192.168.1.5"]


def test_administratively_enabled_does_not_override_disconnected_status():
    result = network.rank_network_candidates([{
        "interface_name": "WiFi", "addresses": "192.168.1.5", "enabled": True,
        "Status": "Disconnected", "has_gateway": True,
    }, adapter("LAN", "10.1.1.2")], "192.168.1.5")
    assert result["preferred_address"] == "10.1.1.2"
    assert result["saved_address_valid"] is False


@pytest.mark.parametrize("gateway", ["", "0.0.0.0", "::", "not-an-ip", "127.0.0.1", "169.254.1.1"])
def test_invalid_gateway_does_not_boost_candidate(gateway):
    result = network.rank_network_candidates([
        adapter("WiFi", "192.168.1.5", "wifi", gateways=[gateway]),
        adapter("Ethernet", "10.0.0.8"),
    ])
    assert result["preferred_address"] == "10.0.0.8"
    assert result["candidates"][1]["has_gateway"] is False


def test_unknown_status_is_explicit_and_saved_selection_is_retained():
    result = network.rank_network_candidates([
        adapter("Fallback", "10.0.0.8", "unknown", up=None, gateway=False),
        adapter("WiFi", "192.168.1.5", "wifi"),
    ], "10.0.0.8")
    assert result["preferred_address"] == "10.0.0.8"
    assert result["candidates"][0]["is_up"] is None


def test_rank_has_no_io_and_handles_empty_or_malformed_rows():
    with patch.object(network.subprocess, "run", side_effect=AssertionError("subprocess")), \
            patch.object(network.socket, "getaddrinfo", side_effect=AssertionError("DNS")):
        result = network.rank_network_candidates([None, "bad", {}, {"addresses": 42}])
    assert result["candidates"] == []
    assert result["manual_entry"]["available"] is True


def test_windows_discovery_uses_hidden_bounded_read_only_command(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout=json.dumps(adapter("以太网", "192.168.1.3")))

    monkeypatch.setattr(network.subprocess, "STARTUPINFO", lambda: SimpleNamespace(dwFlags=0, wShowWindow=1), raising=False)
    monkeypatch.setattr(network.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
    monkeypatch.setattr(network.subprocess, "SW_HIDE", 0, raising=False)
    monkeypatch.setattr(network.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(network.subprocess, "run", run)
    result = network._windows_adapters()
    assert result[0]["interface_name"] == "以太网"
    command, kwargs = calls[0]
    assert command[:4] == ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive"]
    assert command[command.index("-WindowStyle") + 1] == "Hidden"
    assert "Get-NetIPConfiguration -All" in command[-1]
    assert "Get-NetAdapter -IncludeHidden" in command[-1]
    assert kwargs["timeout"] == 8
    assert kwargs["creationflags"] == 0x08000000
    assert kwargs["startupinfo"].wShowWindow == 0
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs.get("shell", False) is False


@pytest.mark.parametrize("failure", [
    subprocess.TimeoutExpired("powershell.exe", 8), FileNotFoundError("powershell.exe"),
    subprocess.CalledProcessError(1, "powershell.exe"), ValueError("bad JSON"),
])
def test_enumeration_failure_uses_only_hostname_socket_metadata(monkeypatch, failure):
    calls = []

    def local_addresses(host, port, family):
        calls.append((host, port, family))
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))
                for address in ["10.0.0.8", "10.0.0.8", "100.64.0.1", "127.0.0.1"]]

    monkeypatch.setattr(network, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(network, "_windows_adapters", lambda: (_ for _ in ()).throw(failure))
    monkeypatch.setattr(network.socket, "gethostname", lambda: "local-host")
    monkeypatch.setattr(network.socket, "getaddrinfo", local_addresses)
    result = network.discover_network_candidates("10.0.0.8")
    assert calls == [("local-host", None, socket.AF_INET)]
    assert ranked_addresses(result) == ["10.0.0.8"]
    assert result["preferred_reason"] == "saved"
    assert result["discovery_source"] == "socket"
    assert result["discovery_error"] == type(failure).__name__
    candidate = result["candidates"][0]
    assert candidate["is_up"] is None
    assert candidate["interface_type"] == "unknown"
    assert candidate["has_gateway"] is False


def test_successful_windows_inventory_does_not_resolve_or_probe(monkeypatch):
    monkeypatch.setattr(network, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(network, "_windows_adapters", lambda: [adapter("WiFi", "192.168.1.3")])
    monkeypatch.setattr(network.socket, "getaddrinfo", lambda *args: pytest.fail("unexpected DNS"))
    monkeypatch.setattr(network.socket, "socket", lambda *args: pytest.fail("unexpected probe"))
    result = network.discover_network_candidates()
    assert result["discovery_source"] == "windows"
    assert result["preferred_address"] == "192.168.1.3"


@pytest.mark.parametrize("windows_rows", [[], [adapter("公网", "8.8.8.8")]])
def test_empty_usable_windows_inventory_tries_socket_fallback(monkeypatch, windows_rows):
    monkeypatch.setattr(network, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(network, "_windows_adapters", lambda: windows_rows)
    monkeypatch.setattr(network, "_socket_adapters", lambda: [adapter("Fallback", "172.20.1.2", up=None)])
    assert network.discover_network_candidates()["preferred_address"] == "172.20.1.2"


def test_non_windows_uses_socket_inventory_without_starting_powershell(monkeypatch):
    monkeypatch.setattr(network, "os", SimpleNamespace(name="posix"))
    monkeypatch.setattr(network, "_windows_adapters", lambda: pytest.fail("unexpected PowerShell"))
    monkeypatch.setattr(network, "_socket_adapters", lambda: [
        adapter("Fallback", ["100.64.0.2", "169.254.1.1", "10.0.0.4"], up=None),
    ])
    result = network.discover_network_candidates()
    assert ranked_addresses(result) == ["10.0.0.4"]
    assert result["discovery_source"] == "socket"


def test_both_discovery_methods_failing_keeps_manual_entry(monkeypatch):
    monkeypatch.setattr(network, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(network, "_windows_adapters", lambda: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(network, "_socket_adapters", lambda: (_ for _ in ()).throw(socket.gaierror()))
    result = network.discover_network_candidates()
    assert result["candidates"] == []
    assert result["discovery_source"] == "none"
    assert result["manual_entry"]["available"] is True


@pytest.mark.parametrize("payload", ["null", "1", '"text"', '[null]', '["text"]', "invalid"])
def test_invalid_powershell_payload_is_rejected(monkeypatch, payload):
    monkeypatch.setattr(network.subprocess, "STARTUPINFO", lambda: SimpleNamespace(dwFlags=0), raising=False)
    monkeypatch.setattr(network.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
    monkeypatch.setattr(network.subprocess, "SW_HIDE", 0, raising=False)
    monkeypatch.setattr(network.subprocess, "CREATE_NO_WINDOW", 0, raising=False)
    monkeypatch.setattr(network.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=payload))
    with pytest.raises(ValueError):
        network._windows_adapters()
