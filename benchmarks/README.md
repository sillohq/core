# The Sillo benchmark

Sillo, FastAPI and Django, serving identical routes over real HTTP, measured by
an established load generator.

Everything here is designed so you can run it yourself and disagree with us.
The applications are three short files you can read in a couple of minutes, the
payloads have a single shared definition, and every export carries the machine
the numbers came from.

---

## Quick start

```bash
cd benchmarks

uv venv && source .venv/bin/activate
uv pip install -e ".[all]"

brew install oha          # macOS. see "Load generators" for other platforms

python -m sillo_bench doctor       # confirm the suite can run here
python -m sillo_bench run          # ~13 minutes at the defaults
```

Results print to the terminal and are written to `results/` as CSV, JSON and
Markdown.

If you'd rather not install all three frameworks, install the ones you want and
run those:

```bash
uv pip install -e ".[sillo,fastapi]"
python -m sillo_bench run --frameworks sillo,fastapi
```

---

## What is measured

Five scenarios, chosen so that a slow result points at something specific
rather than at "the framework".

| scenario | route | isolates |
| --- | --- | --- |
| `plaintext` | `/plaintext` | Fixed per-request overhead: routing, request construction, response send. The body is two bytes so it contributes nothing. |
| `json` | `/json` | The same, plus encoding a small object. |
| `path-param` | `/items/42` | Adds path extraction and integer coercion. |
| `query-param` | `/search?q=…&page=3&per_page=25` | Adds query string parsing and coercion of three values. |
| `rows` | `/rows` | Dominated by the JSON encoder: 200 nested objects. |

The interesting comparison is usually *within* a framework rather than across
one row. A framework that is quick on `rows` and slow on `plaintext` has a fast
encoder behind an expensive request path, which is a different problem from
being uniformly slow, and the fix is different too.

No scenario touches a database. That is deliberate — a database turns every
framework's number into a measurement of the database — but it also means these
results describe framework overhead and nothing else. See
[What this does not tell you](#what-this-does-not-tell-you).

---

## How it is kept fair

This is a benchmark published by the authors of one of the frameworks in it, so
the methodology matters more than the numbers.

**One shared payload definition.** All three applications import their response
bodies from `sillo_bench/payloads.py`. Neither can serve a slightly smaller
object than another.

**One server, one configuration.** Every framework is served by the same
uvicorn, same version, same worker count, access logging off, on a fresh
process bound to a fresh port. The server is a constant; the application is
what varies.

**Correctness is proven before speed is measured.** Every scenario is requested
once and checked for the expected status *and* expected content before any
load is applied. This matters more than it sounds: a framework whose route is
missing returns a fast 404, and a framework that 500s returns a short body very
quickly. Without this check, either would top the table. A scenario that fails
verification is reported as `failed`, never as a number.

**Non-2xx responses invalidate a result.** A server shedding load under
pressure answers quickly and posts excellent throughput. Any non-2xx response
during measurement turns that cell into an error.

**Medians, not means, across repeated rounds.** Each scenario runs an unmeasured
warmup, then N measured rounds with a quiet gap between them. The median round
is reported. A single scheduler hiccup skews a mean and cannot be told apart
from a real result afterwards. When rounds disagree by more than 10%, the report
says so explicitly rather than presenting the median as settled.

**FastAPI's handlers carry return annotations, and it matters enormously.** A
handler declared `async def rows() -> dict` serializes through pydantic-core's
Rust serializer. Drop the annotation and it falls back to FastAPI's pure-Python
`jsonable_encoder`. On the `rows` payload that is a **13x** difference — 286µs
against 3731µs — larger than any gap between the three frameworks here.

The annotations stay. Showing a framework at its best is the only defensible
choice for a benchmark published by a competitor, and it is what modern FastAPI
code looks like. It is worth knowing about in its own right: if your own FastAPI
service is slower than this table suggests, check your return annotations before
anything else.

**Django's middleware is the one real judgement call.** Django ships a default
`MIDDLEWARE` list — security headers, sessions, CSRF, auth, messages,
clickjacking. A bare Sillo or FastAPI application has no equivalent, so running
Django's default stack against nothing would measure the stack rather than the
framework.

The default here is therefore an **empty** middleware list, which is the honest
analogue. Django's real defaults are one environment variable away, and running
both is more informative than either alone:

```bash
SILLO_BENCH_DJANGO_MIDDLEWARE=default python -m sillo_bench run --frameworks django
```

**Django views are `async def`.** Under ASGI a sync view is pushed to a thread
pool, which would measure a deployment choice rather than the framework.

**The C accelerators are off by default.** `uvloop` and `httptools` speed up
every framework roughly equally, so they move the absolute numbers without
moving the comparison. Install `.[fast]` if you want figures closer to a tuned
deployment.

---

## Commands

### `doctor`

Reports what is installed and what is missing, with the command to fix each
gap. Run this first.

```bash
python -m sillo_bench doctor
```

### `list`

Shows the scenarios, the frameworks and which load generators are present.

```bash
python -m sillo_bench list
```

### `run`

The benchmark.

```bash
python -m sillo_bench run [options]
```

| option | default | meaning |
| --- | --- | --- |
| `--frameworks` | all | Comma-separated: `sillo`, `fastapi`, `django` |
| `--scenarios` | all | Comma-separated; see `list` |
| `--tool` | `auto` | `oha`, `bombardier`, `wrk`, `hey`, or `auto` |
| `--duration` | `10` | Seconds per measured round |
| `--connections` | `64` | Concurrent connections |
| `--rounds` | `3` | Measured rounds; the median is reported |
| `--warmup` | `3` | Unmeasured warmup seconds |
| `--workers` | `1` | uvicorn workers per server |
| `--settle` | `1.0` | Quiet seconds between rounds |
| `--export` | `csv,json,md` | Output formats |
| `--out` | `./results` | Output directory |
| `--note` | – | A caveat recorded with the results; repeatable |
| `--quiet` | off | Suppress progress lines |

Exits non-zero if any cell failed, so it can gate CI.

### `serve`

Runs one framework's application and prints its routes, for poking at by hand.

```bash
python -m sillo_bench serve sillo
curl http://127.0.0.1:PORT/rows
```

---

## Exports

`run` writes three files per invocation, timestamped so runs accumulate rather
than overwrite.

**`results-<stamp>.csv`** — one row per scenario/framework cell, a clean
rectangle with a fixed column order, so appended runs stay concatenable and it
loads into a dataframe without a header block to skip.

```
scenario,framework,requests_per_second,latency_mean_ms,latency_p50_ms,
latency_p95_ms,latency_p99_ms,rounds,total_requests,non_2xx,
round_spread_pct,error
```

```python
import pandas as pd
df = pd.read_csv("results/results-20260816T101500Z.csv")
df.pivot(index="scenario", columns="framework", values="requests_per_second")
```

**`environment-<stamp>.csv`** — the machine and package versions, as key/value
pairs. Separate from the results so the results stay rectangular.

**`results-<stamp>.json`** — the archival record: every individual round plus
the load generator's raw output. The terminal table and the CSV both collapse
rounds to a median; this keeps what was collapsed, so a number that looks wrong
later can be checked rather than re-argued.

**`results-<stamp>.md`** — throughput and p99 tables plus the environment
block, ready to paste into a README or an issue.

Export a subset with `--export csv` or `--export json,md`.

---

## Load generators

The measurement is not done in Python. Timing requests from the process that
serves them hides the socket, the event loop under contention and the server's
own parsing, and it cannot generate concurrency realistically.

| tool | install | notes |
| --- | --- | --- |
| **`oha`** | `brew install oha` · `cargo install oha` | **Recommended.** JSON output with a full percentile map. |
| `bombardier` | `brew install bombardier` · `go install github.com/codesenberg/bombardier@latest` | JSON output. |
| `wrk` | `brew install wrk` · `apt install wrk` | Text output, scraped. Reports no p95 without a Lua script, so that column is blank. |
| `hey` | `brew install hey` · `go install github.com/rakyll/hey@latest` | Text output, scraped. |

`auto` picks the first installed one in that order, preferring the two that
emit JSON — their numbers are read out of a document rather than scraped from
formatted text that changes between releases.

Adding a fifth means one `LoadTool` subclass in `loadtools.py`: a command line
and a parser returning a `Measurement`.

---

## Reading the output

```
scenario      sillo                 fastapi               django
--------------------------------------------------------------------------
plaintext         21,340 rps (1.00x)    12,880 rps (0.60x)     7,410 rps (0.35x)
                p50 2.87ms            p50 4.76ms            p50 8.31ms
```

Throughput is the median of the measured rounds; higher is better. The
multiplier compares each framework to the fastest in that row, and is the part
that carries between machines — the absolute figures do not.

---

## What this does not tell you

Worth being blunt about, because framework benchmarks are routinely
over-read.

**It measures framework overhead, nothing else.** No scenario touches a
database, a cache, a template or an external service. A handler doing a 2ms
query costs 2ms in every framework here, and a 40µs difference in request
handling disappears into it entirely. Where these numbers matter is cheap,
high-volume endpoints: health checks, cached reads, token validation, internal
fan-out.

**It is one machine.** Absolute throughput depends on the CPU, the OS, what
else is running and whether the machine is thermally throttled. Run it yourself;
that is what this suite is for. Ratios travel better than absolute numbers, but
not perfectly.

**Frameworks are not only fast or slow.** Django brings an ORM, an admin, auth,
migrations and thirty years of accumulated answers. None of that appears in a
requests-per-second figure, and choosing a framework on this table alone would
be a mistake.

**The load generator is on the same machine as the server.** It competes for
the same CPUs, which compresses the differences between frameworks at high
concurrency. Running the generator on a separate host over a real network is
more faithful and more work; if you do, record it with `--note`.

---

## Reproducing a published result

Every result Sillo publishes is produced by this suite at the defaults, with
the environment block attached. To check one:

```bash
cd benchmarks
uv pip install -e ".[all]"
python -m sillo_bench run --rounds 5 --duration 30
```

Compare the environment blocks first. If the CPUs differ, compare the
multipliers rather than the raw throughput.

Found something wrong with the methodology? Open an issue. A benchmark
maintained by one of its own subjects only stays honest if it is checked.
