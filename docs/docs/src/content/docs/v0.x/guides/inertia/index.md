---
title: Inertia
description: "Build a React or Vue front end against Sillo routes with sillo-inertia: server-side routing, no API layer, and no client-side router to keep in sync."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Inertia with Sillo
  - tag: meta
    attrs:
      property: og:description
      content: A React or Vue front end with no API between it and the server. The page's props are delivered with the page rather than fetched after it.
---

#  Inertia

[Inertia.js](https://inertiajs.com) lets you write a React or Vue front end
without building an API for it. Routes stay on the server, handlers return a
component name and its props, and the client swaps the page without a full
reload.

A handler names a component and returns its props:

```python
@app.get("/dashboard")
async def dashboard(request: Request, response: Response):
    return await render("Dashboard", {"stats": {"signed_in_as": request.user.email}})
```

The component receives them as props:

```tsx
export default function Dashboard({ stats }: Props) {
  return <p>Signed in as {stats.signed_in_as}</p>
}
```

There is no endpoint to define, no client-side fetch, no loading state, and no
second description of the same data.

##  Where it sits

It is the middle path between [Templating](/v0.x/guides/templating/) and
[Frontend (SPA)](/v0.x/guides/frontend/): you get a real component-based front end,
but routing, authorisation and data loading stay in Python, where the rest of
your application already is.

| | Routing | Data reaches the page by | You also maintain |
| --- | --- | --- | --- |
| Templating | Server | Template context | Nothing |
| **Inertia** | **Server** | **Props, with the page** | **Components** |
| SPA | Client | `fetch` from an API | Components, a router, an API |

Choose Templating when the page is mostly content. Choose a SPA when something
other than your own front end consumes the API, a mobile client, a partner
integration. Choose Inertia when you want components and there is exactly one
consumer.

##  How a page renders

Your handler is the same either way. What the response *is* gets decided by
the request:

- **First visit.** A browser navigation. The response is the full HTML shell
  with the page object embedded, so the document has a title and content before
  any JavaScript runs.
- **Every navigation after**: an XHR carrying `X-Inertia`. The response is the
  page object as JSON, and the client swaps it into the page already open.

This is why Inertia pages are excluded from the OpenAPI document. A `GET
/login` that returns an HTML document to a browser and a JSON page object to
Inertia is not an API endpoint, and describing it as one ("Successful
Response", `application/json`) is worse than not describing it at all.

##  Installing

Support lives in a separate package, so nothing here is carried by
applications that do not use it.

```bash
uv add sillo-inertia
```

The [starter](/v0.x/guides/inertia/start/) has it wired already, along with Vite,
React, Tailwind and a working auth flow. Starting there is the shortest path
to a running page.

##  This section

- **[Creating a Project](/v0.x/guides/inertia/start/)**: the starter, the two
  development processes, and the task reference
- **[Project Structure](/v0.x/guides/inertia/structure/)**: `views/`, `js/`,
  `root.html`, and the paths that have to agree
- **[Pages and Props](/v0.x/guides/inertia/pages/)**: `render`, shared props,
  redirects, and handlers that only gather data
- **[Forms and Validation](/v0.x/guides/inertia/forms/)**: returning errors across
  the redirect a failed submission makes
- **[Assets and Deployment](/v0.x/guides/inertia/assets/)**: Vite in development and
  production, asset versions, and shipping it

##  Related

- [Frontend (SPA)](/v0.x/guides/frontend/): serving a built SPA with client-side
  routing
- [Templating](/v0.x/guides/templating/): server-rendered Jinja pages
- [Static Files](/v0.x/guides/static-files/): serving assets
- [`sillo-inertia` on GitHub](https://github.com/sillohq/inertia): full
  reference
