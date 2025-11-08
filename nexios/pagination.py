import abc
import base64
import json
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple, Union


class PaginationError(Exception):
    """Base class for all pagination errors"""


class InvalidPageError(PaginationError):
    """Raised when requesting an invalid page number"""


class InvalidPageSizeError(PaginationError):
    """Raised when requesting an invalid page size"""


class InvalidCursorError(PaginationError):
    """Raised when providing an invalid cursor"""


class LinkBuilder:
    def __init__(
        self,
        base_url: str,
        request_params: Dict[str, Union[str, List[str]]],
        pagination_params: List[str],
    ):
        self.base_url = base_url
        self.request_params = request_params
        self.pagination_params = pagination_params

    def build_link(self, new_params: Dict[str, Any]) -> str:
        filtered_params: Dict[str, Any] = {
            k: v
            for k, v in self.request_params.items()
            if k not in self.pagination_params
        }
        merged_params = {**filtered_params, **new_params}
        return f"{self.base_url}?{urllib.parse.urlencode(merged_params, doseq=True)}"


class BasePaginationStrategy(abc.ABC):
    @abc.abstractmethod
    def parse_parameters(self, request_params: Dict[str, Any]) -> Any:
        pass

    @abc.abstractmethod
    def calculate_offset_limit(self, *args: List[int]) -> Tuple[int, int]:
        pass

    @abc.abstractmethod
    def generate_metadata(
        self,
        total_items: int,
        items: List[Any],
        base_url: str,
        request_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        pass


class SyncDataHandler(abc.ABC):
    @abc.abstractmethod
    def get_total_items(self) -> int:
        pass

    @abc.abstractmethod
    def get_items(self, offset: int, limit: int) -> List[Any]:
        pass


class SyncListDataHandler(SyncDataHandler):
    def __init__(self, data: List[Any]):
        self.data = data

    def get_total_items(self) -> int:
        return len(self.data)

    def get_items(self, offset: int, limit: int) -> List[Any]:
        return self.data[offset : offset + limit]


class AsyncDataHandler(abc.ABC):
    @abc.abstractmethod
    async def get_total_items(self) -> int:
        pass

    @abc.abstractmethod
    async def get_items(self, offset: int, limit: int) -> List[Any]:
        pass


class AsyncListDataHandler(AsyncDataHandler):
    def __init__(self, data: List[Any]):
        self.data = data

    async def get_total_items(self) -> int:
        return len(self.data)

    async def get_items(self, offset: int, limit: int) -> List[Any]:
        return self.data[offset : offset + limit]


# ==================== PAGINATION STRATEGIES ====================


class PageNumberPagination(BasePaginationStrategy):
    def __init__(
        self,
        page_param: str = "page",
        page_size_param: str = "page_size",
        default_page: int = 1,
        default_page_size: int = 20,
        max_page_size: int = 100,
    ):
        self.page_param = page_param
        self.page_size_param = page_size_param
        self.default_page = default_page
        self.default_page_size = default_page_size
        self.max_page_size = max_page_size

    def parse_parameters(self, request_params: Dict[str, Any]) -> Tuple[int, int]:
        page = int(request_params.get(self.page_param, self.default_page))
        page_size = int(
            request_params.get(self.page_size_param, self.default_page_size)
        )

        if page_size > self.max_page_size:
            page_size = self.max_page_size

        if page < 1:
            raise InvalidPageError("Page number must be at least 1")
        if page_size < 1:
            raise InvalidPageSizeError("Page size must be at least 1")

        return page, page_size

    def calculate_offset_limit(self, page: int, page_size: int) -> Tuple[int, int]:  # type: ignore
        return (page - 1) * page_size, page_size

    def generate_metadata(
        self,
        total_items: int,
        items: List[Any],
        base_url: str,
        request_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        page, page_size = self.parse_parameters(request_params)
        total_pages = (total_items + page_size - 1) // page_size if page_size else 1

        link_builder = LinkBuilder(
            base_url, request_params, [self.page_param, self.page_size_param]
        )

        links = {}

        if page > 1:
            links["prev"] = link_builder.build_link(
                {self.page_param: page - 1, self.page_size_param: page_size}
            )
        if page < total_pages:
            links["next"] = link_builder.build_link(
                {self.page_param: page + 1, self.page_size_param: page_size}
            )

        links["first"] = link_builder.build_link(
            {self.page_param: 1, self.page_size_param: page_size}
        )
        links["last"] = link_builder.build_link(
            {self.page_param: total_pages, self.page_size_param: page_size}
        )

        return {
            "total_items": total_items,
            "total_pages": total_pages,
            "page": page,
            "page_size": page_size,
            "links": links,
        }


class LimitOffsetPagination(BasePaginationStrategy):
    def __init__(
        self,
        limit_param: str = "limit",
        offset_param: str = "offset",
        default_limit: int = 20,
        max_limit: int = 100,
    ):
        self.limit_param = limit_param
        self.offset_param = offset_param
        self.default_limit = default_limit
        self.max_limit = max_limit

    def parse_parameters(self, request_params: Dict[str, Any]) -> Tuple[int, int]:
        limit = int(request_params.get(self.limit_param, self.default_limit))
        offset = int(request_params.get(self.offset_param, 0))

        if limit > self.max_limit:
            limit = self.max_limit
        if limit < 0:
            raise InvalidPageSizeError("Limit cannot be negative")
        if offset < 0:
            raise InvalidPageError("Offset cannot be negative")

        return limit, offset

    def calculate_offset_limit(self, limit: int, offset: int) -> Tuple[int, int]:  # type: ignore
        return offset, limit

    def generate_metadata(
        self,
        total_items: int,
        items: List[Any],
        base_url: str,
        request_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        limit, offset = self.parse_parameters(request_params)
        current_page = (offset // limit) + 1 if limit else 1
        total_pages = (total_items + limit - 1) // limit if limit else 1

        link_builder = LinkBuilder(
            base_url, request_params, [self.limit_param, self.offset_param]
        )

        links = {}

        if offset > 0:
            prev_offset = max(0, offset - limit)
            links["prev"] = link_builder.build_link(
                {self.limit_param: limit, self.offset_param: prev_offset}
            )

        if offset + limit < total_items:
            next_offset = offset + limit
            links["next"] = link_builder.build_link(
                {self.limit_param: limit, self.offset_param: next_offset}
            )

        links["first"] = link_builder.build_link(
            {self.limit_param: limit, self.offset_param: 0}
        )
        links["last"] = link_builder.build_link(
            {self.limit_param: limit, self.offset_param: max(0, total_items - limit)}
        )

        return {
            "total_items": total_items,
            "limit": limit,
            "offset": offset,
            "current_page": current_page,
            "total_pages": total_pages,
            "links": links,
        }


class CursorPagination(BasePaginationStrategy):
    def __init__(
        self,
        cursor_param: str = "cursor",
        page_size_param: str = "page_size",
        default_page_size: int = 20,
        max_page_size: int = 100,
        sort_field: str = "id",
    ):
        self.cursor_param = cursor_param
        self.page_size_param = page_size_param
        self.default_page_size = default_page_size
        self.max_page_size = max_page_size
        self.sort_field = sort_field

    def parse_parameters(
        self, request_params: Dict[str, Any]
    ) -> Tuple[Optional[str], int]:
        cursor = request_params.get(self.cursor_param)
        page_size = int(
            request_params.get(self.page_size_param, self.default_page_size)
        )
        page_size = min(page_size, self.max_page_size)
        return cursor, page_size

    def decode_cursor(self, cursor: str) -> Dict[str, Any]:
        try:
            decoded = base64.b64decode(cursor).decode("utf-8")
            return json.loads(decoded)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise InvalidCursorError("Invalid cursor format")

    def encode_cursor(self, value: Any) -> str:
        cursor_data = {self.sort_field: value}
        return base64.b64encode(json.dumps(cursor_data).encode("utf-8")).decode("utf-8")

    def calculate_offset_limit(  # type:ignore
        self, cursor: Optional[str], page_size: int
    ) -> Tuple[int, int]:  # type:ignore
        decoded_cursor = urllib.parse.unquote(cursor) if cursor else None
        if decoded_cursor:
            try:
                cursor_data = self.decode_cursor(decoded_cursor)
            except InvalidCursorError:
                raise InvalidCursorError("Invalid cursor format")
            return cursor_data[self.sort_field], page_size
        return 0, page_size

    def generate_metadata(
        self,
        total_items: int,
        items: List[Any],
        base_url: str,
        request_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        cursor, page_size = self.parse_parameters(request_params)
        link_builder = LinkBuilder(
            base_url, request_params, [self.cursor_param, self.page_size_param]
        )

        links = {}
        next_cursor = self.encode_cursor(items[-1][self.sort_field]) if items else None
        prev_cursor = self.encode_cursor(items[0][self.sort_field]) if items else None

        if next_cursor:
            links["next"] = link_builder.build_link(
                {self.cursor_param: next_cursor, self.page_size_param: page_size}
            )
        if cursor:
            links["prev"] = link_builder.build_link(
                {self.cursor_param: prev_cursor, self.page_size_param: page_size}
            )

        return {
            "total_items": total_items,
            "page_size": page_size,
            "cursor": cursor,
            "links": links,
        }


# ==================== PAGINATORS ====================


class SyncPaginator:
    def __init__(
        self,
        data_handler: SyncDataHandler,
        pagination_strategy: BasePaginationStrategy,
        base_url: str,
        request_params: Dict[str, Any],
        validate_total_items: bool = True,
    ):
        self.data_handler = data_handler
        self.pagination_strategy = pagination_strategy
        self.base_url = base_url
        self.request_params = request_params
        self.validate_total_items = validate_total_items

    def paginate(self) -> Dict[str, Any]:
        params = self.pagination_strategy.parse_parameters(self.request_params)
        offset, limit = self.pagination_strategy.calculate_offset_limit(*params)

        total_items = self.data_handler.get_total_items()
        if self.validate_total_items and offset >= total_items and total_items > 0:
            raise InvalidPageError("Requested offset exceeds total items")

        items = self.data_handler.get_items(offset, limit)
        metadata = self.pagination_strategy.generate_metadata(
            total_items, items, self.base_url, self.request_params
        )

        return {"items": items, "pagination": metadata}


class AsyncPaginator:
    def __init__(
        self,
        data_handler: AsyncDataHandler,
        pagination_strategy: BasePaginationStrategy,
        base_url: str,
        request_params: Dict[str, Any],
        validate_total_items: bool = True,
    ):
        self.data_handler = data_handler
        self.pagination_strategy = pagination_strategy
        self.base_url = base_url
        self.request_params = request_params
        self.validate_total_items = validate_total_items

    async def paginate(self) -> Dict[str, Any]:
        params = self.pagination_strategy.parse_parameters(self.request_params)
        offset, limit = self.pagination_strategy.calculate_offset_limit(*params)

        total_items = await self.data_handler.get_total_items()
        if self.validate_total_items and offset >= total_items and total_items > 0:
            raise InvalidPageError("Requested offset exceeds total items")

        items = await self.data_handler.get_items(offset, limit)
        metadata = self.pagination_strategy.generate_metadata(
            total_items, items, self.base_url, self.request_params
        )

        return {"items": items, "pagination": metadata}


class PaginatedResponse:
    def __init__(self, data: Dict[str, Any]):
        self.items = data["items"]
        self.metadata = data["pagination"]

    def to_dict(self) -> Dict[str, Any]:
        return {"data": self.items, "pagination": self.metadata}


class AsyncPaginatedResponse:
    def __init__(self, data: Dict[str, Any]):
        self.items = data["items"]
        self.metadata = data["pagination"]

    def to_dict(self) -> Dict[str, Any]:
        return {"data": self.items, "pagination": self.metadata}
