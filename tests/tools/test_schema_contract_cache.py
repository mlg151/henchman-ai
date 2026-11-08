"""Only bounded immutable schema meta-validation is reused across contracts."""

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier, Lock

import pytest

from henchman.tools import contracts
from henchman.tools.contracts import SchemaContract, SchemaContractError


@pytest.fixture(autouse=True)
def isolated_cache():
    cached = getattr(contracts, "_check_schema_cached", None)
    if cached is not None:
        cached.cache_clear()
    yield
    if cached is not None:
        cached.cache_clear()


@pytest.fixture
def checked_schemas(monkeypatch):
    original = contracts.Draft202012Validator.check_schema
    observed = []
    lock = Lock()

    def check(_cls, schema, *args, **kwargs):
        with lock:
            observed.append(deepcopy(schema))
        return original(schema, *args, **kwargs)

    monkeypatch.setattr(contracts.Draft202012Validator, "check_schema", classmethod(check))
    return observed


def test_equal_detached_schemas_reuse_meta_check_despite_object_key_order(checked_schemas):
    first = {"type": "object", "properties": {"value": {"type": "integer", "minimum": 3}}}
    second = {"properties": {"value": {"minimum": 3, "type": "integer"}}, "type": "object"}
    left, right = SchemaContract(first), SchemaContract(second)
    left.validate({"value": 4})
    right.validate({"value": 5})
    assert len(checked_schemas) == 1
    assert left._validator is not right._validator
    assert left._validator.schema is not right._validator.schema
    first["properties"]["value"]["minimum"] = 0
    exposed = right.schema
    exposed["properties"]["value"]["minimum"] = 0
    for contract in (left, right):
        with pytest.raises(SchemaContractError, match="minimum"):
            contract.validate({"value": 1})


def test_nested_mutation_rechecks_meta_schema_and_values_remain_fresh(checked_schemas):
    source = {"type": "object", "properties": {"value": {"type": "integer"}}}
    original = SchemaContract(source)
    SchemaContract(deepcopy(source))
    source["properties"]["value"]["type"] = "string"
    changed = SchemaContract(source)
    assert len(checked_schemas) == 2
    original.validate({"value": 1})
    changed.validate({"value": "one"})
    with pytest.raises(SchemaContractError, match="type"):
        changed.validate({"value": 1})
    with pytest.raises(SchemaContractError, match="type"):
        original.validate({"value": "one"})


@pytest.mark.parametrize("schemas", [
    [True, 1], [False, 0],
    [{"minimum": 1}, {"minimum": 1.0}],
    [{"const": True}, {"const": 1}],
    [{"enum": [1, 2]}, {"enum": [2, 1]}],
    [{"prefixItems": [{"type": "string"}, {"type": "integer"}]},
     {"prefixItems": [{"type": "integer"}, {"type": "string"}]}],
])
def test_canonical_key_preserves_types_and_array_order(checked_schemas, schemas):
    for schema in schemas:
        if type(schema) is int:
            with pytest.raises(SchemaContractError, match="invalid_schema"):
                SchemaContract(schema)
        else:
            SchemaContract(schema)
            SchemaContract(deepcopy(schema))
    assert len(checked_schemas) == len(schemas)


def test_invalid_meta_schema_never_poisoned_by_or_saved_in_success_cache(checked_schemas):
    SchemaContract({"type": "integer"})
    for _ in range(2):
        with pytest.raises(SchemaContractError, match="invalid_schema"):
            SchemaContract({"type": "not-a-type"})
    SchemaContract({"type": "integer"})
    assert checked_schemas == [{"type": "integer"}, {"type": "not-a-type"}, {"type": "not-a-type"}]


@pytest.mark.parametrize(("schema", "reason"), [
    ({"$ref": "https://private.invalid/schema"}, "external_reference"),
    ({"$ref": "#/$defs/missing"}, "unresolved_reference"),
    ({"pattern": "(x+)+$"}, "unsupported_regex"),
    ({"type": "string", "description": "x" * 65536}, "payload_limit"),
    ({1: "invalid-key"}, "invalid_json"),
])
def test_warm_cache_does_not_bypass_local_or_json_limits(schema, reason):
    SchemaContract({"type": "string"})
    for _ in range(2):
        with pytest.raises(SchemaContractError, match=reason):
            SchemaContract(schema)


def test_warm_cache_does_not_bypass_depth_or_per_value_budget():
    SchemaContract(True)
    nested = {}
    for _ in range(70):
        nested = {"child": nested}
    with pytest.raises(SchemaContractError, match="depth_limit"):
        SchemaContract({"const": nested})
    for _ in range(2):
        with pytest.raises(SchemaContractError, match="validation_limit"):
            SchemaContract({"$ref": "#"}).validate({})
    SchemaContract(True).validate({"still": "valid"})


def test_cache_evicts_old_schema_after_64_successes(checked_schemas):
    for value in range(65):
        SchemaContract({"const": value})
    SchemaContract({"const": 64})
    assert len(checked_schemas) == 65
    SchemaContract({"const": 0})
    assert len(checked_schemas) == 66
    cached = getattr(contracts, "_check_schema_cached", None)
    assert cached is not None
    assert cached.cache_info().currsize == cached.cache_info().maxsize == 64


def test_canonical_key_limit_is_64kib_with_larger_valid_schemas_uncached(monkeypatch, checked_schemas):
    schema = {"description": ""}
    overhead = len(json.dumps(schema, separators=(",", ":")).encode("ascii"))
    schema["description"] = "x" * (65536 - overhead)
    SchemaContract(schema)
    SchemaContract(schema)
    assert len(checked_schemas) == 1
    # The current admission bound is also 64KiB. Raising it independently must
    # not make a larger valid schema consume cache space or become a new error.
    monkeypatch.setattr(contracts, "MAX_SCHEMA_BYTES", 131072)
    schema["description"] += "x"
    SchemaContract(schema)
    SchemaContract(schema)
    assert len(checked_schemas) == 3
    assert contracts._check_schema_cached.cache_info().currsize == 1


def test_concurrent_misses_and_hits_never_share_mutable_validators(monkeypatch):
    workers = 4
    barrier = Barrier(workers)
    original = contracts.Draft202012Validator.check_schema
    checked = []
    lock = Lock()

    def check(_cls, schema, *args, **kwargs):
        with lock:
            checked.append(deepcopy(schema))
        barrier.wait(timeout=10)
        return original(schema, *args, **kwargs)

    monkeypatch.setattr(contracts.Draft202012Validator, "check_schema", classmethod(check))
    schema = {"type": "integer", "minimum": 2}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        compiled = list(executor.map(lambda _: SchemaContract(schema), range(workers)))
    assert len({id(item._validator) for item in compiled}) == workers
    compiled[0]._validator.schema["minimum"] = 0
    for item in compiled[1:]:
        assert item._validator.schema["minimum"] == 2
        with pytest.raises(SchemaContractError, match="minimum"):
            item.validate(1)
    # functools permits duplicate first misses; once populated, the same
    # immutable key must bypass the compiler and remain detached.
    def check_after_misses(_cls, schema, *args, **kwargs):
        checked.append(deepcopy(schema))
        return original(schema, *args, **kwargs)

    monkeypatch.setattr(contracts.Draft202012Validator, "check_schema", classmethod(check_after_misses))
    final = SchemaContract(schema)
    final.validate(2)
    with pytest.raises(SchemaContractError, match="minimum"):
        final.validate(1)
    assert len(checked) == workers
