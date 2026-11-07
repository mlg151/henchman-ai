"""Exact host restrictions have one canonical, bounded configuration form."""

import pytest
from pydantic import ValidationError

from henchman.config.schema import Settings


def test_network_hosts_default_empty_and_canonical_names():
    assert Settings().tools.network_allowed_hosts is None
    empty = Settings(tools={"network_allowed_hosts": []}).tools
    assert empty.model_dump(exclude_unset=True) == {"network_allowed_hosts": []}
    configured = Settings(tools={"network_allowed_hosts": [
        "EXAMPLE.com.", "faß.de", "8.8.8.8", "2001:4860:4860:0:0:0:0:8888",
    ]}).tools
    assert configured.network_allowed_hosts == ["example.com", "xn--fa-hia.de", "8.8.8.8", "2001:4860:4860::8888"]


@pytest.mark.parametrize("value", [
    "example.com", [1], [""], [" example.com"], ["*.example.com"], ["https://example.com"],
    ["example.com:443"], ["user@example.com"], ["example.com/path"], ["foo_bar"],
    ["example..com"], ["example.com.."], ["xn--abc"], ["[2001:4860:4860::8888]"],
    ["fe80::1%eth0"], ["127.1"], ["2130706433"], ["0x7f000001"], ["0177.0.0.1"],
    ["１２７.１"], ["０ｘ７ｆ０００００１"],
    ["allowed.test＠evil.test"], ["allowed.test﹫evil.test"], ["allowed.test：443"],
    ["allowed.test﹕443"], ["allowed.test／evil.test"], ["allowed.test？query"], ["allowed.test＃fragment"],
    ["＠evil.test"], ["evil.test："], ["evil.test：80"], ["evil.test：8443"], ["user：password＠evil.test"],
    ["https：／／allowed.test"],
    ["EXAMPLE.com", "example.com."], ["x" * 64 + ".test"], [f"host-{i}.test" for i in range(129)],
])
def test_invalid_network_host_configuration_is_rejected(value):
    with pytest.raises(ValidationError):
        Settings(tools={"network_allowed_hosts": value})
