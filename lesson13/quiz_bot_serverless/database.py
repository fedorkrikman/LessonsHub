import logging
import os
import re
from functools import lru_cache
from typing import Dict, Mapping, Optional, Union

import ydb
from ydb import types as ydb_types

YDB_ENDPOINT = os.getenv("YDB_ENDPOINT")
YDB_DATABASE = os.getenv("YDB_DATABASE")

logger = logging.getLogger(__name__)
_DECLARE_RE = re.compile(r"DECLARE\s+\$(\w+)\s+AS\s+([A-Za-z0-9_<>?, ]+)", re.IGNORECASE)
_YdbType = Union[ydb_types.PrimitiveType, ydb_types.AbstractTypeBuilder]
_PRIMITIVE_TYPE_MAP: Dict[str, ydb_types.PrimitiveType] = {
    "bool": ydb_types.PrimitiveType.Bool,
    "int64": ydb_types.PrimitiveType.Int64,
    "uint64": ydb_types.PrimitiveType.Uint64,
    "int32": ydb_types.PrimitiveType.Int32,
    "uint32": ydb_types.PrimitiveType.Uint32,
    "double": ydb_types.PrimitiveType.Double,
    "float": ydb_types.PrimitiveType.Float,
    "utf8": ydb_types.PrimitiveType.Utf8,
    "string": ydb_types.PrimitiveType.String,
    "bytes": ydb_types.PrimitiveType.String,
    "date": ydb_types.PrimitiveType.Date,
    "datetime": ydb_types.PrimitiveType.Datetime,
    "timestamp": ydb_types.PrimitiveType.Timestamp,
    "interval": ydb_types.PrimitiveType.Interval,
    "json": ydb_types.PrimitiveType.Json,
    "jsondocument": ydb_types.PrimitiveType.JsonDocument,
    "uuid": ydb_types.PrimitiveType.Uuid,
}
_YDB_ERROR = getattr(ydb, "Error", Exception)


def get_ydb_pool(ydb_endpoint, ydb_database, timeout=30):
    ydb_driver_config = ydb.DriverConfig(
        ydb_endpoint,
        ydb_database,
        credentials=ydb.credentials_from_env_variables(),
        root_certificates=ydb.load_ydb_root_certificate(),
    )

    ydb_driver = ydb.Driver(ydb_driver_config)
    ydb_driver.wait(fail_fast=True, timeout=timeout)
    return ydb.SessionPool(ydb_driver)


@lru_cache(maxsize=128)
def _declared_types(query: str) -> Dict[str, str]:
    """Парсит блок DECLARE и возвращает карту параметров на их YQL-типы."""
    return {name: type_name.strip() for name, type_name in _DECLARE_RE.findall(query or "")}


def _resolve_type(type_name: str) -> _YdbType:
    """Строит объект типа YDB из текстового определения (Uint64, List<Uint64>, Optional<...>)."""
    normalized = type_name.strip()
    if normalized.endswith("?"):
        inner = _resolve_type(normalized[:-1])
        return ydb_types.OptionalType(inner)
    lower = normalized.lower()
    if lower.startswith("optional<") and lower.endswith(">"):
        inner = _resolve_type(normalized[len("optional<") : -1])
        return ydb_types.OptionalType(inner)
    if lower.startswith("list<") and lower.endswith(">"):
        inner = _resolve_type(normalized[5:-1])
        return ydb_types.ListType(inner)
    if lower.startswith("set<") and lower.endswith(">"):
        inner = _resolve_type(normalized[4:-1])
        return ydb_types.SetType(inner)
    primitive = _PRIMITIVE_TYPE_MAP.get(lower)
    if primitive is None:
        raise ValueError(f"Unsupported YDB type declaration: {type_name}")
    return primitive


def _infer_type_from_value(value) -> ydb_types.PrimitiveType:
    """Запасной путь на случай отсутствия DECLARE (например, для простых запросов)."""
    if isinstance(value, bool):
        return ydb_types.PrimitiveType.Bool
    if isinstance(value, int):
        return ydb_types.PrimitiveType.Int64
    if isinstance(value, float):
        return ydb_types.PrimitiveType.Double
    if isinstance(value, bytes):
        return ydb_types.PrimitiveType.String
    return ydb_types.PrimitiveType.Utf8


def _make_typed_value(value, value_type: _YdbType):
    """Создает TypedValue и оборачивает тип в Optional при значении None."""
    if value is None and not isinstance(value_type, ydb_types.OptionalType):
        value_type = ydb_types.OptionalType(value_type)
    return ydb_types.TypedValue(value, value_type)


def _prepare_parameters(query: str, raw_kwargs: Mapping[str, object]) -> Dict[str, ydb_types.TypedValue]:
    if not raw_kwargs:
        return {}
    declared = _declared_types(query)
    formatted: Dict[str, ydb_types.TypedValue] = {}
    for key, value in raw_kwargs.items():
        declared_type = declared.get(key)
        if declared and declared_type is None:
            raise ValueError(f"Parameter ${key} is not declared in query.")
        value_type = _resolve_type(declared_type) if declared_type else _infer_type_from_value(value)
        formatted[f"${key}"] = _make_typed_value(value, value_type)
    return formatted


def _describe_parameter_types(parameters: Optional[Mapping[str, ydb_types.TypedValue]]) -> Dict[str, str]:
    if not parameters:
        return {}
    return {name: str(param.value_type) for name, param in parameters.items()}


def _log_ydb_error(query: str, parameters: Optional[Mapping[str, ydb_types.TypedValue]], error: Exception) -> None:
    logger.error(
        "YDB query failed. Query: %s | Parameter types: %s | Error: %s",
        query.strip(),
        _describe_parameter_types(parameters),
        error,
    )


def _run_with_retry(pool, query: str, kwargs: Mapping[str, object], *, expect_result: bool):
    parameters = _prepare_parameters(query, kwargs)

    def callee(session):
        prepared_query = session.prepare(query)
        tx = session.transaction(ydb.SerializableReadWrite())
        result_sets = tx.execute(prepared_query, parameters, commit_tx=True)
        if expect_result:
            return result_sets[0].rows

    try:
        return pool.retry_operation_sync(callee)
    except _YDB_ERROR as exc:
        _log_ydb_error(query, parameters, exc)
        raise


def execute_update_query(pool, query, **kwargs):
    _run_with_retry(pool, query, kwargs, expect_result=False)


def execute_select_query(pool, query, **kwargs):
    return _run_with_retry(pool, query, kwargs, expect_result=True)


# Зададим настройки базы данных
pool = get_ydb_pool(YDB_ENDPOINT, YDB_DATABASE)
