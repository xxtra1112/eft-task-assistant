from urllib.error import HTTPError, URLError

import pytest

from catalog import CatalogError
from reemr_maps import ReemrNetworkError, ReemrPolicyError, access_denied, temporary_network_failure


@pytest.mark.parametrize("failure", [
    URLError(ConnectionRefusedError(10061, "由于目标计算机积极拒绝，无法连接")),
    ReemrNetworkError("RE3MR 暂时无法核查 robots：连接超时"),
    TimeoutError("robots request timed out"),
    ConnectionRefusedError(10061, "拒绝连接"),
])
def test_typed_network_failures_are_not_policy_denials(failure):
    wrapped = CatalogError("无法读取 RE3MR：" + str(failure))
    wrapped.__cause__ = failure
    assert not access_denied(wrapped)
    assert temporary_network_failure(wrapped)


@pytest.mark.parametrize("failure", [
    HTTPError("https://reemr.se/", 403, "Forbidden", {}, None),
    HTTPError("https://reemr.se/", 401, "Unauthorized", {}, None),
    ReemrPolicyError("robots rule invalid"),
    PermissionError("denied"),
])
def test_explicit_denial_wins_over_network_context(failure):
    failure.__context__ = TimeoutError("temporary network context")
    wrapped = ReemrNetworkError("network wrapper")
    wrapped.__cause__ = failure
    assert access_denied(wrapped)
    assert not temporary_network_failure(wrapped)


def test_unknown_policy_message_remains_fail_closed():
    assert access_denied(CatalogError("robots invalid"))
    assert not temporary_network_failure(CatalogError("unclassified failure"))
