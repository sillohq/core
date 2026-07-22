from typing import Any, cast

import strawberry
from sillo.application import silloApp
from sillo.http import Request, Response
from sillo.routing import Route
from strawberry.types import ExecutionResult


class GraphQL:
    """GraphQL endpoint handler that integrates Strawberry with the sillo framework.

    Registers a route on the sillo application to serve both the GraphiQL interactive
    IDE (via GET) and GraphQL query execution (via POST). Supports query variables,
    operation names, and passes the request/response objects into the Strawberry
    execution context for resolver access.

    Attributes:
        app: The sillo application instance on which the route is registered.
        schema: The Strawberry GraphQL schema used to execute incoming queries.
        path: The URL path where the GraphQL endpoint is mounted.
        graphiql: Whether to serve the GraphiQL interactive IDE on GET requests.
    """

    def __init__(
        self,
        app: silloApp,
        schema: strawberry.Schema,
        path: str = "/graphql",
        graphiql: bool = True,
    ):
        """Initialize the GraphQL handler and register its route on the application.

        Stores references to the application, schema, mount path, and GraphiQL
        toggle, then immediately calls the internal setup method to register the
        route with the sillo router.

        Args:
            app: The sillo application instance on which the GraphQL route will
                be registered for handling incoming HTTP requests.
            schema: A fully constructed Strawberry ``Schema`` object defining the
                GraphQL types, queries, mutations, and subscriptions to serve.
            path: The URL path at which the GraphQL endpoint will be accessible.
                Defaults to ``"/graphql"``.
            graphiql: A boolean flag controlling whether the GraphiQL interactive
                browser IDE is served on GET requests. Defaults to True.

        Returns:
            None. This method initializes the handler and triggers route registration.

        Raises:
            None.
        """
        self.app = app
        self.schema = schema
        self.path = path
        self.graphiql = graphiql

        self._setup()

    def _setup(self):
        """Register the GraphQL endpoint route on the sillo application.

        Creates a sillo ``Route`` bound to the configured path that accepts both
        GET and POST HTTP methods, and adds it to the application's router. GET
        requests serve the GraphiQL IDE while POST requests execute GraphQL queries.

        Args:
            None. This method uses instance attributes configured during initialization.

        Returns:
            None. This method registers the route as a side effect.

        Raises:
            None.
        """
        self.app.add_route(
            Route(self.path, self.handle_request, methods=["GET", "POST"])
        )

    async def handle_request(self, req: Request, res: Response):
        """Handle an incoming HTTP request to the GraphQL endpoint.

        Routes the request based on HTTP method. GET requests return the GraphiQL
        interactive IDE HTML page if enabled, or a 404 response if disabled. POST
        requests parse the JSON body to extract the GraphQL query, variables, and
        operation name, then execute the query against the Strawberry schema and
        return the result as a JSON response. Invalid JSON or non-object bodies
        receive a 400 error response.

        Args:
            req: The incoming HTTP Request object. For POST requests, its JSON body
                must contain a ``"query"`` field and optionally ``"variables"`` and
                ``"operationName"`` fields conforming to the GraphQL over HTTP spec.
            res: The HTTP Response object used to construct the appropriate response
                with the correct content type and status code.

        Returns:
            A Response object containing either the GraphiQL HTML page (GET), a JSON
            GraphQL execution result (POST), or a JSON error message for invalid input.

        Raises:
            None. JSON parsing errors are caught and converted into a 400 response
            with an appropriate error message.
        """
        if req.method == "GET":
            if self.graphiql:
                return res.html(self._get_graphiql_html())
            return res.text("Not Found", status_code=404)

        if req.method == "POST":
            try:
                data = await req.json
            except Exception:
                return res.json(
                    {"errors": [{"message": "Invalid JSON body"}]}, status_code=400
                )

            if not isinstance(data, dict):
                return res.json(
                    {"errors": [{"message": "JSON body must be an object"}]},
                    status_code=400,
                )

            query = data.get("query")
            variables = data.get("variables")
            operation_name = data.get("operationName")

            context = {"request": req, "response": res}

            result: ExecutionResult = await self.schema.execute(
                cast(str, query),
                variable_values=cast(dict, variables),
                context_value=context,
                operation_name=cast(str, operation_name),
            )

            response_data: dict[str, Any] = {}
            if result.data is not None:
                response_data["data"] = result.data
            if result.errors:
                response_data["errors"] = [err.formatted for err in result.errors]

            return res.json(response_data)

    def _get_graphiql_html(self) -> str:
        """Generate the HTML page for the GraphiQL interactive query IDE.

        Returns a self-contained HTML document that loads React, GraphiQL, and the
        GraphiQL Explorer plugin from CDN. The page configures a GraphQL fetcher
        pointing at the current URL, supports WebSocket subscriptions, and includes
        CSRF token handling via cookies. The IDE provides syntax highlighting,
        auto-completion, query documentation browsing, and an explorer panel.

        Args:
            None. This method returns a static HTML template string with embedded
            JavaScript for initializing the GraphiQL application.

        Returns:
            A complete HTML document string that renders the GraphiQL interactive
            IDE when loaded in a web browser.

        Raises:
            None.
        """
        return """
<!doctype html>
<html>
  <head>
    <title>Strawberry GraphiQL</title>
    <link
      rel="icon"
      href="data:image/svg+xml,
        <svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22>
            <text y=%22.9em%22 font-size=%2280%22>&#x1f353;</text>
        </svg>"
    />
    <style>
      body {
        height: 100%;
        margin: 0;
        width: 100%;
        overflow: hidden;
      }
      #graphiql {
        height: 100vh;
        display: flex;
      }
      .docExplorerHide {
        display: none;
      }
      .doc-explorer-contents {
        overflow-y: hidden !important;
      }
      .docExplorerWrap {
        width: unset !important;
        min-width: unset !important;
      }
      .graphiql-explorer-actions select {
        margin-left: 4px;
      }
    </style>
    <script
      crossorigin
      src="https://unpkg.com/react@18.2.0/umd/react.production.min.js"
      integrity="sha384-tMH8h3BGESGckSAVGZ82T9n90ztNXxvdwvdM6UoR56cYcf+0iGXBliJ29D+wZ/x8"
    ></script>
    <script
      crossorigin
      src="https://unpkg.com/react-dom@18.2.0/umd/react-dom.production.min.js"
      integrity="sha384-bm7MnzvK++ykSwVJ2tynSE5TRdN+xL418osEVF2DE/L/gfWHj91J2Sphe582B1Bh"
    ></script>
    <script
      crossorigin
      src="https://unpkg.com/js-cookie@3.0.5/dist/js.cookie.min.js"
      integrity="sha384-/vxhYfM1LENRhdpZ8dwEsQn/X4VhpbEZSiU4m/FwR+PVpzar4fkEOw8FP9Y+OfQN"
    ></script>
    <link
      crossorigin
      rel="stylesheet"
      href="https://unpkg.com/graphiql@3.8.3/graphiql.min.css"
      integrity="sha384-Mq3vbRBY71jfjQAt/DcjxUIYY33ksal4cgdRt9U/hNPvHBCaT2JfJ/PTRiPKf0aM"
    />
    <link
      crossorigin
      rel="stylesheet"
      href="https://unpkg.com/@graphiql/plugin-explorer@1.0.2/dist/style.css"
      integrity="sha384-5DFJlDPW2tSATRbM8kzoP1j194jexLswuNmClWoRr2Q0x7R68JIQzPHZ02Faktwi"
    />
  </head>
  <body>
    <div id="graphiql" class="graphiql-container">Loading...</div>
    <script
      crossorigin
      src="https://unpkg.com/graphiql@3.8.3/graphiql.min.js"
      integrity="sha384-HbRVEFG0JGJZeAHCJ9Xm2+tpknBQ7QZmNlO/DgZtkZ0aJSypT96YYGRNod99l9Ie"
    ></script>
    <script
      crossorigin
      src="https://unpkg.com/@graphiql/plugin-explorer@1.0.2/dist/index.umd.js"
      integrity="sha384-2oonKe47vfHIZnmB6ZZ10vl7T0Y+qrHQF2cmNTaFDuPshpKqpUMGMc9jgj9MLDZ9"
    ></script>
    <script>
      const EXAMPLE_QUERY = `# Welcome to GraphiQL 🍓
#
# GraphiQL is an in-browser tool for writing, validating, and
# testing GraphQL queries.
#
# Type queries into this side of the screen, and you will see intelligent
# typeaheads aware of the current GraphQL type schema and live syntax and
# validation errors highlighted within the text.
#
# GraphQL queries typically start with a "{" character. Lines that starts
# with a # are ignored.
#
# An example GraphQL query might look like:
#
#     {
#       field(arg: "value") {
#         subField
#       }
#     }
#
# Keyboard shortcuts:
#
#       Run Query:  Ctrl-Enter (or press the play button above)
#
#   Auto Complete:  Ctrl-Space (or just start typing)
#
`;

      const fetchURL = window.location.href;

      function httpUrlToWebSockeUrl(url) {
        const parsedURL = new URL(url);
        const protocol = parsedURL.protocol === "http:" ? "ws:" : "wss:";
        parsedURL.protocol = protocol;
        parsedURL.hash = "";
        return parsedURL.toString();
      }

      const headers = {};
      const csrfToken = Cookies.get("csrftoken");

      if (csrfToken) {
        headers["x-csrftoken"] = csrfToken;
      }

      const subscriptionUrl = httpUrlToWebSockeUrl(fetchURL);

      const fetcher = GraphiQL.createFetcher({
        url: fetchURL,
        headers: headers,
        subscriptionUrl,
      });

      const explorerPlugin = GraphiQLPluginExplorer.explorerPlugin();

      const root = ReactDOM.createRoot(document.getElementById("graphiql"));

      root.render(
        React.createElement(GraphiQL, {
          fetcher: fetcher,
          defaultEditorToolsVisibility: true,
          plugins: [explorerPlugin],
          inputValueDeprecation: true,
        }),
      );
    </script>
  </body>
</html>
"""
