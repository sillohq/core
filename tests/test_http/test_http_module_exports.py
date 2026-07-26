from sillo.http import (
    Accepts,
    AcceptsMiddleware,
    HTTP_200_OK,
    HTTP_404_NOT_FOUND,
    RequestContext,
    RequestId,
    RequestIdMiddleware,
    parse_accept_header,
)
from sillo.http.accepts import AcceptsInfo
from sillo.http.lifecycle import generate_request_id
from sillo.http.status import HTTP_201_CREATED
from sillo.websockets import status as websocket_status


def test_accepts_exports_from_http_module():
    assert parse_accept_header("application/json")[0].value == "application/json"
    assert isinstance(Accepts(), AcceptsMiddleware)
    assert AcceptsInfo is not None


def test_lifecycle_exports_from_http_module():
    assert isinstance(generate_request_id(), str)
    assert isinstance(RequestId(), RequestIdMiddleware)

    with RequestContext() as context:
        context["ok"] = True
        assert RequestContext.current() is context
        assert context["ok"] is True


def test_statuses_live_in_protocol_modules():
    assert HTTP_200_OK == 200
    assert HTTP_404_NOT_FOUND == 404
    assert HTTP_201_CREATED == 201
    assert websocket_status.WS_1000_NORMAL_CLOSURE == 1000
    assert not hasattr(websocket_status, "HTTP_200_OK")
