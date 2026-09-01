---
title: Testing
description: GraphClient and SubscriptionStream — driving the real endpoint, with the JSON assembly and dictionary walking already done.
---

A GraphQL test written through a plain HTTP client is four lines of JSON
assembly and a dictionary walk before it reaches the thing under test.

```python
from sillo.graphql.testing import GraphClient


def test_me():
    with GraphClient(app) as gql:
        result = gql.query("{ me { email } }")
        assert result.ok
        assert result["me"]["email"] == "ada@example.com"
```

Nothing here reaches around the transports. A test drives the same route a
client does — which is the only way a test of an endpoint tells you anything
about the endpoint.

## GraphClient

```python
GraphClient(app, path="/graphql", headers={"authorization": "Bearer …"})
```

Headers given here are sent with every request, which is how you test as a
signed-in user.

```python
gql.query(document, variables={...}, operation_name="Me", headers={...})
gql.mutate(document, variables={...})           # the same method, named for intent
gql.execute(document, method="GET")             # over GET
gql.batch("{ a }", "{ b }")                     # -> list[GraphResult]
gql.ide()                                       # the explorer page, as a browser
```

## GraphResult

The dictionary walking, done.

| | |
|---|---|
| `result["field"]` | Into `data`, with a readable failure if it is not there |
| `result.data` | The whole `data` |
| `result.errors` | The error objects |
| `result.messages` | Just the messages — what an assertion usually wants |
| `result.codes` | Each error's `extensions.code` |
| `result.extensions` | Including `cost` |
| `result.ok` | No errors |
| `result.status_code` | The HTTP status |
| `result.headers` | Response headers |
| `result.raise_for_errors()` | Fail loudly; returns `self` |

The subscript is the one worth knowing about. On a miss it says what was there
instead of raising `KeyError` on `None`:

```
AssertionError: 'me' is not in data (['posts']); errors: ['Not authenticated']
```

Which is the difference between a test that tells you what went wrong and one
that tells you `NoneType is not subscriptable`.

## Asserting on errors

Codes rather than messages — a message is copy, a code is contract:

```python
def test_a_missing_post_is_not_found():
    with GraphClient(app) as gql:
        result = gql.query("{ post(id: 999) { title } }")
        assert result.codes == ["NOT_FOUND"]


def test_an_internal_error_is_masked():
    with GraphClient(app) as gql:
        result = gql.query("{ boom }")
        assert result.messages == ["Unexpected error"]
        assert "postgres://" not in str(result.body)
```

That second one is worth having. It is the assertion that catches the day
somebody turns masking off to debug something and forgets.

## Subscriptions

The handshake, written once.

```python
PRICES = "subscription ($symbol: String!) { prices(symbol: $symbol) { last } }"


async def test_prices_stream():
    with GraphClient(app) as gql:
        async with gql.subscribe(PRICES, symbol="ACME") as stream:
            first = await stream.next()
            assert first["prices"]["last"] == 10
```

Entering connects, sends `connection_init`, waits for `connection_ack` and
sends the `subscribe`. Leaving completes the operation and closes the socket,
so a test that fails part-way through does not leave a subscription running.

Variables go as keywords or as `variables={...}`.

```python
await stream.next()          # the next value
await stream.collect(3)      # the next three
await stream.complete()      # unsubscribe early
```

`next()` steps over `ping`/`pong` frames. If the subscription **completed**
instead of producing another value it raises `StreamEnded` rather than hanging
— which is the failure a test means to catch:

```python
async def test_it_stops_after_three():
    with GraphClient(app) as gql:
        async with gql.subscribe("subscription { ticks(count: 3) }") as stream:
            await stream.collect(3)
            with pytest.raises(StreamEnded):
                await stream.next()
```

An `error` message from the server comes back as a result with `codes`, rather
than as an exception, so refusals assert like any other error:

```python
async def test_introspection_is_refused_over_the_socket():
    with GraphClient(app) as gql:
        async with gql.subscribe("{ __schema { types { name } } }") as stream:
            assert (await stream.next()).codes == ["OPERATION_NOT_PERMITTED"]
```

## Testing loaders

The assertion worth writing is the number of queries, not the result.

```python
async def test_authors_are_batched(query_counter):
    with GraphClient(app) as gql:
        result = gql.query("{ posts(first: 20) { author { name } } }")

    assert result.ok
    assert query_counter.count == 2      # posts, then authors — not 21
```

Without that, an N+1 regression passes every functional test and shows up as a
slow afternoon.

Outside a request, open a scope:

```python
from sillo.graphql import LoaderRegistry


async def test_the_batch_function_aligns_its_results():
    async with LoaderRegistry().scope():
        assert await load_author(7) == expected
```

## Testing cost

Pinning the cost of your client's real operations turns a schema change that
makes one ten times more expensive into a failing assertion:

```python
def test_the_feed_query_stays_affordable():
    with GraphClient(app) as gql:
        result = gql.query(FEED_QUERY, variables={"first": 20})
        assert result.extensions["cost"]["cost"] < 500
```

## Testing configuration

Build a `Graph` per test rather than sharing one, so a policy change in one
test cannot leak:

```python
import pytest
from sillo import SilloApp
from sillo.graphql import Graph, Limits


@pytest.fixture
def build(schema):
    def make(**kwargs):
        app = SilloApp(debug=False)
        Graph(schema, **kwargs).mount(app)
        return app
    return make


def test_a_deep_query_is_refused(build):
    with GraphClient(build(limits=Limits(depth=3))) as gql:
        result = gql.query("{ a { b { c { d } } } }")
        assert result.codes == ["OPERATION_TOO_COMPLEX"]
```

## Testing as a user

Authentication middleware runs on the route, so a test signs in the way a
client does — with a header:

```python
def test_drafts_need_a_session():
    with GraphClient(app) as gql:
        assert gql.query("{ drafts { id } }").codes == ["UNAUTHENTICATED"]

    with GraphClient(app, headers={"authorization": f"Bearer {token}"}) as gql:
        assert gql.query("{ drafts { id } }").ok
```

For a subscription, the token goes in `connection_init` instead:

```python
async with gql.subscribe(FEED, connection_params={"authorization": token}) as s:
    ...
```
