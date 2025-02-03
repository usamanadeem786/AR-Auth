from collections.abc import Callable, Coroutine

from fastapi import Depends, Header, Query
from sqlalchemy.sql import Select

from auth.repositories.base import BaseRepository, M

RawOrdering = list[str]
Ordering = list[tuple[list[str], bool]]
Pagination = tuple[int, int]
PaginatedObjects = tuple[list[M], int]
GetPaginatedObjects = Callable[
    [Select, Pagination, Ordering, BaseRepository[M]],
    Coroutine[None, None, PaginatedObjects[M]],
]


async def get_paginated_objects(
    statement: Select,
    pagination: Pagination,
    ordering: Ordering,
    repository: BaseRepository[M],
) -> PaginatedObjects[M]:
    limit, skip = pagination
    statement = repository.orderize(statement, ordering)
    return await repository.paginate(statement, limit, skip)


async def get_paginated_objects_noop(
    statement: Select,
    pagination: Pagination,
    ordering: Ordering,
    repository: BaseRepository[M],
) -> PaginatedObjects[M]:
    return ([], 0)


async def get_paginated_objects_getter(
    hx_target: str | None = Header(None, include_in_schema=False),
) -> GetPaginatedObjects[M]:
    if hx_target == "aside-content":
        return get_paginated_objects_noop
    return get_paginated_objects


async def get_pagination(
    limit: int = Query(10, ge=0), skip: int = Query(0, ge=0)
) -> Pagination:
    return min(limit, 100), skip


async def get_raw_ordering(ordering: str = Query(None)) -> RawOrdering:
    return ordering.split(",") if ordering else []


class OrderingGetter:
    def __init__(self, default: Ordering | None = None) -> None:
        self.default = default if default else []

    async def __call__(
        self,
        raw_ordering: RawOrdering = Depends(get_raw_ordering),
    ) -> Ordering:
        ordering_fields = []
        for field in raw_ordering:
            is_desc = False
            if field.startswith("-"):
                is_desc = True
                field = field[1:]
            ordering_fields.append((field.split("."), is_desc))

        if len(ordering_fields) == 0:
            return self.default

        return ordering_fields
