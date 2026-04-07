# Changelog

## v3.11.0 (2026-04-05)

#### New Features

* (routing): add custom route class support ([#348](https://github.com/nexios-labs/nexios/issues/348))
#### Fixes

* fix types and implement  ty ([#349](https://github.com/nexios-labs/nexios/issues/349))
#### Refactorings

* (dependencies): rewrite di system to improve performance ([#351](https://github.com/nexios-labs/nexios/issues/351))
* remove deprecated get_application function  ([#350](https://github.com/nexios-labs/nexios/issues/350))
#### Others

* bump version to 3.11.0

Full set of changes: [`v3.10.6...v3.11.0`](https://github.com/nexios-labs/nexios/compare/v3.10.6...v3.11.0)

## v3.10.6 (2026-04-01)

#### Docs

* (redis): fix contrib docs to match v0.4.2 ([#347](https://github.com/nexios-labs/nexios/issues/347))
* fix issues with docs ([#346](https://github.com/nexios-labs/nexios/issues/346))
#### Others

* bump version to 3.10.6

Full set of changes: [`v3.10.5...v3.10.6`](https://github.com/nexios-labs/nexios/compare/v3.10.5...v3.10.6)

## v3.10.5 (2026-03-30)

#### Docs

* (changelog): update changelog ([#344](https://github.com/nexios-labs/nexios/issues/344))
#### Others

* bump version to 3.10.5

Full set of changes: [`v3.10.4...v3.10.5`](https://github.com/nexios-labs/nexios/compare/v3.10.4...v3.10.5)

## v3.10.4 (2026-03-27)

#### Fixes

* (templating): inject request context into Jinja2 templates automatically ([#340](https://github.com/nexios-labs/nexios/issues/340))
#### Docs

* (mail): expand email integration examples and usage ([#341](https://github.com/nexios-labs/nexios/issues/341))
#### Others

* bump version to 3.10.4

Full set of changes: [`v3.10.3...v3.10.4`](https://github.com/nexios-labs/nexios/compare/v3.10.3...v3.10.4)

## v3.10.3 (2026-03-26)

#### Fixes

* (session): remove  parameter overwrite in load_session_from_cookie ([#339](https://github.com/nexios-labs/nexios/issues/339))
#### Performance improvements

* (http): optimize import statements and code structure ([#337](https://github.com/nexios-labs/nexios/issues/337))
#### Others

* bump version to 3.10.3
* (views): add comprehensive test  for APIView  ([#338](https://github.com/nexios-labs/nexios/issues/338))

Full set of changes: [`v3.10.2...v3.10.3`](https://github.com/nexios-labs/nexios/compare/v3.10.2...v3.10.3)

## v3.10.2 (2026-03-25)

#### Refactorings

* (http): improve json parsing and form handling ([#336](https://github.com/nexios-labs/nexios/issues/336))
* (nexios): wrap route level middleware at init ([#335](https://github.com/nexios-labs/nexios/issues/335))
#### Others

* (release): bump version to 3.10.2

Full set of changes: [`v3.10.1...v3.10.2`](https://github.com/nexios-labs/nexios/compare/v3.10.1...v3.10.2)

## v3.10.1 (2026-03-24)

#### Docs

* update middleware docs in docs index ([#334](https://github.com/nexios-labs/nexios/issues/334))
#### Others

* (release): bump version to 3.10.1
* (docs): update release notes ([#333](https://github.com/nexios-labs/nexios/issues/333))

Full set of changes: [`v3.10.0...v3.10.1`](https://github.com/nexios-labs/nexios/compare/v3.10.0...v3.10.1)

## v3.10.0 (2026-03-20)

#### Refactorings

* (routing): remove path params wrapping ([#332](https://github.com/nexios-labs/nexios/issues/332))
#### Others

* bump version to 3.10.0

Full set of changes: [`v3.9.1...v3.10.0`](https://github.com/nexios-labs/nexios/compare/v3.9.1...v3.10.0)

## v3.9.1 (2026-03-19)

#### Fixes

* (auth): fix scope validation fixes [#328](https://github.com/nexios-labs/nexios/issues/328) ([#330](https://github.com/nexios-labs/nexios/issues/330))
#### Refactorings

* (routing): update router typpes and defaults ([#329](https://github.com/nexios-labs/nexios/issues/329))
* (response): update docs on sending responses ([#327](https://github.com/nexios-labs/nexios/issues/327))
#### Others

* (release): bump version to 3.9.1

Full set of changes: [`v3.9.0...v3.9.1`](https://github.com/nexios-labs/nexios/compare/v3.9.0...v3.9.1)

## v3.9.0 (2026-03-15)

#### Fixes

* (nexios): handle streaming responses and bytes in ASGI request-response bridge ([#326](https://github.com/nexios-labs/nexios/issues/326))
#### Refactorings

* (response): improve header management and middleware processing   ([#322](https://github.com/nexios-labs/nexios/issues/322))
#### Docs

* (middleware): add return value warnings and examples ([#325](https://github.com/nexios-labs/nexios/issues/325))
* (tasks): update integration docs ([#324](https://github.com/nexios-labs/nexios/issues/324))
#### Others

* bump version to 3.9.0
* update project description in pyproject.toml
* reroginze code structure ([#323](https://github.com/nexios-labs/nexios/issues/323))

Full set of changes: [`v3.8.3...v3.9.0`](https://github.com/nexios-labs/nexios/compare/v3.8.3...v3.9.0)

## v3.8.3 (2026-03-04)

#### Refactorings

* (middleware): update tests for changes at ([#317](https://github.com/nexios-labs/nexios/issues/317)) ([#318](https://github.com/nexios-labs/nexios/issues/318))
* move config handling from MakeConfig to Middleware class ([#317](https://github.com/nexios-labs/nexios/issues/317))
#### Docs

* (sessions): fix session interface typo ([#321](https://github.com/nexios-labs/nexios/issues/321))
* (middleware): update CORS, CSRF, and Session guides ([#320](https://github.com/nexios-labs/nexios/issues/320))
* remove unnecessary emojis ([#319](https://github.com/nexios-labs/nexios/issues/319))
* update contribution guidelines and documentation structure ([#316](https://github.com/nexios-labs/nexios/issues/316))
#### Others

* (release): bump version to 3.8.3

Full set of changes: [`v3.8.2...v3.8.3`](https://github.com/nexios-labs/nexios/compare/v3.8.2...v3.8.3)

## v3.8.2 (2026-02-28)

#### New Features

* (docs): implement rotating banner system ([#312](https://github.com/nexios-labs/nexios/issues/312))
#### Fixes

* (docs): update release notes ([#313](https://github.com/nexios-labs/nexios/issues/313))
#### Docs

* (concurrency): add AsyncEvent documentation and examples   ([#315](https://github.com/nexios-labs/nexios/issues/315))
* add email sending features with nexios-contrib/mail ([#311](https://github.com/nexios-labs/nexios/issues/311))
#### Others

* bump version to 3.8.2
* remove granian dependency from all target ([#314](https://github.com/nexios-labs/nexios/issues/314))

Full set of changes: [`v3.8.1...v3.8.2`](https://github.com/nexios-labs/nexios/compare/v3.8.1...v3.8.2)

## v3.8.1 (2026-02-20)

#### New Features

* (docs): update banner content to promote docs summary ([#309](https://github.com/nexios-labs/nexios/issues/309))
#### Refactorings

* (testing): replace Client with TestClient and improve test setup  ([#310](https://github.com/nexios-labs/nexios/issues/310))
#### Others

* (release): bump version to 3.8.1

Full set of changes: [`v3.8.0...v3.8.1`](https://github.com/nexios-labs/nexios/compare/v3.8.0...v3.8.1)

## v3.8.0 (2026-02-15)

#### Refactorings

* update middleware initialization across multiple tests ([#308](https://github.com/nexios-labs/nexios/issues/308))
* Add `config` parameter to middleware constructors ([#307](https://github.com/nexios-labs/nexios/issues/307))
#### Docs

* (session): update session configuration guide
* (cors): update Nexios CORS documentation with new configuration examples
* (middleware): update timeout middleware documentation ([#306](https://github.com/nexios-labs/nexios/issues/306))
#### Others

* bump version to 3.8.0

Full set of changes: [`v3.7.4...v3.8.0`](https://github.com/nexios-labs/nexios/compare/v3.7.4...v3.8.0)

## v3.7.4 (2026-02-04)

#### Docs

* (websockets): fix typos and update websocket examples ([#305](https://github.com/nexios-labs/nexios/issues/305))
* update documentation for routing and websockets ([#304](https://github.com/nexios-labs/nexios/issues/304))
#### Others

* bump version to 3.7.4

Full set of changes: [`v3.7.3...v3.7.4`](https://github.com/nexios-labs/nexios/compare/v3.7.3...v3.7.4)

## v3.7.3 (2026-02-02)

#### Refactorings

* (websockets): remove websocket middleware support ([#303](https://github.com/nexios-labs/nexios/issues/303))
* (Examples): add proper type hints and proper  external integration  ([#301](https://github.com/nexios-labs/nexios/issues/301))
#### Others

* bump version to 3.7.3
* apply code formatting and minor refactors ([#302](https://github.com/nexios-labs/nexios/issues/302))

Full set of changes: [`v3.7.2...v3.7.3`](https://github.com/nexios-labs/nexios/compare/v3.7.2...v3.7.3)

## v3.7.2 (2026-01-26)

#### Fixes

* (websockets): allow empty expire time for channel creation ([#298](https://github.com/nexios-labs/nexios/issues/298))
#### Others

* bump version to 3.7.2

Full set of changes: [`v3.7.1...v3.7.2`](https://github.com/nexios-labs/nexios/compare/v3.7.1...v3.7.2)

## v3.7.1 (2026-01-24)

#### New Features

* add default user model authentication middleware ([#292](https://github.com/nexios-labs/nexios/issues/292))
#### Refactorings

* restructure configuration on middleware  ([#293](https://github.com/nexios-labs/nexios/issues/293))
#### Docs

* (README): compress logo ([#294](https://github.com/nexios-labs/nexios/issues/294))
#### Others

* bump version to 3.7.1

Full set of changes: [`v3.7.0...v3.7.1`](https://github.com/nexios-labs/nexios/compare/v3.7.0...v3.7.1)

## v3.7.0 (2026-01-19)

#### Fixes

* Added Exception and formatted the code  ([#288](https://github.com/nexios-labs/nexios/issues/288))
* correct the indentation in the code snippet ([#286](https://github.com/nexios-labs/nexios/issues/286))
#### Refactorings

* (cli):  drop suppport for `nexios.config.py` ([#290](https://github.com/nexios-labs/nexios/issues/290))
* remove unused nexios config integration
#### Docs

* fix typos and normalize changelog formatting ([#289](https://github.com/nexios-labs/nexios/issues/289))
#### Others

* bump version to 3.7.0
* (v2): depricate nexios v2 ([#291](https://github.com/nexios-labs/nexios/issues/291))

Full set of changes: [`v3.6.3...v3.7.0`](https://github.com/nexios-labs/nexios/compare/v3.6.3...v3.7.0)

## v3.6.3 (2026-01-12)

#### Refactorings

* (routing): replace AsyncEventEmitter with EventEmitter ([#285](https://github.com/nexios-labs/nexios/issues/285))
#### Docs

* (tasks): update task docs and deprecation notice ([#284](https://github.com/nexios-labs/nexios/issues/284))
* (events): update and clarify event system documentation ([#281](https://github.com/nexios-labs/nexios/issues/281))
#### Others

* bump version to 3.6.3
* (deps): bump anyio from 4.12.0 to 4.12.1 ([#279](https://github.com/nexios-labs/nexios/issues/279))
* (events): depricate async event emitter

Full set of changes: [`v3.6.2...v3.6.3`](https://github.com/nexios-labs/nexios/compare/v3.6.2...v3.6.3)

## v3.6.2 (2026-01-08)

#### New Features

* (file): add save method to handle file saving ([#278](https://github.com/nexios-labs/nexios/issues/278))
#### Refactorings

* (internals): organize core data structures ([#277](https://github.com/nexios-labs/nexios/issues/277))
#### Others

* bump version to 3.6.2
* (deps): bump anyio from 4.11.0 to 4.12.0 ([#249](https://github.com/nexios-labs/nexios/issues/249))

Full set of changes: [`v3.6.1...v3.6.2`](https://github.com/nexios-labs/nexios/compare/v3.6.1...v3.6.2)

## v3.6.1 (2026-01-05)

#### New Features

* (docs): add announcement banner component ([#276](https://github.com/nexios-labs/nexios/issues/276))
#### Docs

* (configuration): add warning about global configuration in tests ([#273](https://github.com/nexios-labs/nexios/issues/273))
#### Others

* bump version to 3.6.1

Full set of changes: [`v3.6.0...v3.6.1`](https://github.com/nexios-labs/nexios/compare/v3.6.0...v3.6.1)

## v3.6.0 (2026-01-01)

#### New Features

* (docs): add comment section using Giscus ([#268](https://github.com/nexios-labs/nexios/issues/268))
#### Refactorings

* (config): replace nested config dict with typed classes ([#270](https://github.com/nexios-labs/nexios/issues/270))
#### Docs

* update CORS and session config docs ([#272](https://github.com/nexios-labs/nexios/issues/272))
* update logo image ([#269](https://github.com/nexios-labs/nexios/issues/269))
* update API reference links and remove unused references ([#265](https://github.com/nexios-labs/nexios/issues/265))
* (changelog): update changelog with recent releases ([#264](https://github.com/nexios-labs/nexios/issues/264))
#### Others

* bump version to 3.6.0

Full set of changes: [`v3.5.0...v3.6.0`](https://github.com/nexios-labs/nexios/compare/v3.5.0...v3.6.0)

## v3.5.0 (2025-12-18)

#### Fixes

* (openapi): improve Schema model validation ([#262](https://github.com/nexios-labs/nexios/issues/262))
#### Refactorings

* (openapi): improve schema handling and nesting ([#260](https://github.com/nexios-labs/nexios/issues/260))

Full set of changes: [`v3.4.2...v3.5.0`](https://github.com/nexios-labs/nexios/compare/v3.4.2...v3.5.0)

## v3.4.2 (2025-12-11)

#### New Features

* (auth):  improve error handling ([#253](https://github.com/nexios-labs/nexios/issues/253))
#### Refactorings

* (config): remove unused type definitions and classes ([#254](https://github.com/nexios-labs/nexios/issues/254))
* (config): remove default config and improve error handling ([#254](https://github.com/nexios-labs/nexios/issues/254))
* fallback to singleton with validation from request.state ([#252](https://github.com/nexios-labs/nexios/issues/252))

Full set of changes: [`v3.3.2...v3.4.2`](https://github.com/nexios-labs/nexios/compare/v3.3.2...v3.4.2)

## v3.3.2 (2025-11-27)

#### New Features

* (openapi): add termsOfService field to Info model ([#244](https://github.com/nexios-labs/nexios/issues/244))
* (docs): add Tortoise ORM integration to community extensions ([#243](https://github.com/nexios-labs/nexios/issues/243))
#### Refactorings

* remove unused route path getter and simplify handler type ([#247](https://github.com/nexios-labs/nexios/issues/247))
#### Docs

* add create_background_task to docs ([#245](https://github.com/nexios-labs/nexios/issues/245))
* migrate changelog to auto-changelog format ([#242](https://github.com/nexios-labs/nexios/issues/242))
#### Others

* (release): bump version to 3.3.2

Full set of changes: [`v3.3.1...v3.3.2`](https://github.com/nexios-labs/nexios/compare/v3.3.1...v3.3.2)

## v3.3.1 (2025-11-19)

#### Fixes

* fix inconsistencies around concurrency docs  ([#240](https://github.com/nexios-labs/nexios/issues/240))
* correct Angular commit message format
#### Refactorings

* drop support for multiple server or else when set by user ([#239](https://github.com/nexios-labs/nexios/issues/239))
#### Docs

* update sitemap.xml for NexiosLabs website ([#236](https://github.com/nexios-labs/nexios/issues/236))
* (docs): update navbar links and add blog link ([#235](https://github.com/nexios-labs/nexios/issues/235))
* rename readme.md to README.md
* remove readme.md
* (readme): remove community-driven description from Nexios definition
* update documentation URL and related links
* refactor and reorganise  nexios vitepress docs ([#233](https://github.com/nexios-labs/nexios/issues/233))
* add comprehensive doc for core component ([#232](https://github.com/nexios-labs/nexios/issues/232))
* add comprehensive doc for core components  ([#231](https://github.com/nexios-labs/nexios/issues/231))
* (readme): update import paths for middleware ([#230](https://github.com/nexios-labs/nexios/issues/230))
#### Others

* bump version to 3.3.1 ([#241](https://github.com/nexios-labs/nexios/issues/241))
*  make few changes to nexios build ([#237](https://github.com/nexios-labs/nexios/issues/237))
* (pyproject): normalize readme filename reference ([#234](https://github.com/nexios-labs/nexios/issues/234))

Full set of changes: [`v3.3.0...v3.3.1`](https://github.com/nexios-labs/nexios/compare/v3.3.0...v3.3.1)

## v3.3.0 (2025-11-11)

#### New Features

* (routing): enhance WebsocketRouter to support mounted routers and Groups
#### Fixes

* (routing): remove sub-router mounting logic
#### Refactorings

* (routing): remove deprecated WSRouter ([#228](https://github.com/nexios-labs/nexios/issues/228))
* (websockets): unify HTTP and WebSocket routing
* (nexios): merge WSRouter into Router for unified routing
* (routing): improve route matching and method handling
* (routing): update route matching to use scope object
#### Docs

* Simplify NexiosApp initialization ([#205](https://github.com/nexios-labs/nexios/issues/205))
* remove duplicate FAQ entries and update content ([#221](https://github.com/nexios-labs/nexios/issues/221))
* update API reference and versioning ([#220](https://github.com/nexios-labs/nexios/issues/220))
#### Others

* revert version to 3.3.0
* bump version from 3.2.1 to 3.3.1
* remove python version file
* (release): add changelog entry for v3.2.1

Full set of changes: [`v3.2.1...v3.3.0`](https://github.com/nexios-labs/nexios/compare/v3.2.1...v3.3.0)

## v3.2.1 (2025-11-07)

#### Refactorings

* replace generic Parameter with specific types ([#216](https://github.com/nexios-labs/nexios/issues/216))
#### Docs

* update changelog
#### Others

* (release): bump version to 3.2.1

Full set of changes: [`v3.2.0...v3.2.1`](https://github.com/nexios-labs/nexios/compare/v3.2.0...v3.2.1)

## v3.2.0 (2025-11-07)

#### New Features

* (openapi): implement automatic OpenAPI documentation and UI serving
* (openapi): implement automatic OpenAPI specification generation
* (openapi): Add utility function for extracting routes recursively
#### Fixes

* (openapi): improve route path handling and specification generation
#### Refactorings

* (openapi): remove APIDocumentation singleton and unused imports ([#211](https://github.com/nexios-labs/nexios/issues/211))
* (openapi): remove APIDocumentation instantiation from NexiosApp
* (openapi): move get_openapi function to APIDocumentation class
* restructure routing and grouping ([#210](https://github.com/nexios-labs/nexios/issues/210))
#### Docs

* expand OpenAPI  documentation ([#214](https://github.com/nexios-labs/nexios/issues/214))
* improve jrpc and tasks documentation ([#209](https://github.com/nexios-labs/nexios/issues/209))
* (changelog): update CHANGELOG.md for v3.1.0 release
#### Others

* bump version from 3.1.0 to 3.2.0

Full set of changes: [`v3.1.0...v3.2.0`](https://github.com/nexios-labs/nexios/compare/v3.1.0...v3.2.0)

## v3.1.0 (2025-11-03)

#### Fixes

* (auth): improve scope checking in auth decorator  ([#205](https://github.com/nexios-labs/nexios/issues/205))
* (auth): improve scope checking in auth decorator ([#205](https://github.com/nexios-labs/nexios/issues/205))
* (response): return streamed response in call_next manager
#### Docs

* rewrite README for  utility-first framework ([#207](https://github.com/nexios-labs/nexios/issues/207))
#### Others

* bump version to 3.1.0

Full set of changes: [`v3.0.0...v3.1.0`](https://github.com/nexios-labs/nexios/compare/v3.0.0...v3.1.0)

## v3.0.0 (2025-11-01)

#### New Features

* (URL): add path setter to URL struct
* (static): enhance StaticFiles with security, caching, and custom handlers
* (auth): refactor authentication examples and update documentation
* (http): enhance request handling and add property checks
* (static): enhance StaticFiles serving with security and functionality improvements
* (routing): add root_path support for mounted applications
* (auth): add custom authentication backend and improve permission handling
* (auth): add API key authentication backend and documentation
#### Fixes

* (response):  return the streamed response instead of nexios response manager for the call_next function manager
* correct the use of process.nextTick
* (pagination): enhance cursor decoding and error handling
* (auth): replace delete_session with del for session management
* (cors): improve CORS middleware and error handling
* (dependencies): remove unused context injection code
* (routing): correctly prefix HTTP endpoint paths in OpenAPI documentation
* (http): correct expires header to use UTC time
* (http): use set_header method to manage response headers
* (auth): resolve import issues and improve authentication handling
#### Refactorings

* (auth): restructure authentication module imports
* (static): remove deprecated StaticFilesHandler class
* (middlewares): remove common middleware
* (session): improve file session management
* (router): remove path parameter from mount methods
* (nexios): improve type annotations and remove unused imports
* add type: ignore comments to suppress mypy errors
* (nexios): remove file router and apply static typing
* (users): update user auth system to latest standard
* (auth): update user authentication and loading process
* (auth): overhaule authentication system
* remove hooks and related tests
* (auth): reorganize user and authentication modules
#### Docs

* update documentation URL
* (community): expand documentation for nexios-contrib and open source FAQ
* update CHANGELOG.md with recent fixes
* (readme): update package version in installation instructions
* (readme): update Nexios version and remove v3 warning
* (team): add new contributors to team page
* add emojis and improve structure for better readability
* update authentication documentation and examples
* update version in navbar to v3.0.0-alpha.1
* (config): update version dropdown and sidebar links
* (request): add request type detection and input handling guides
* add emoji icons to guide titles
* (readme): add important notice about v3 branch status and switch to v2 instructions
* (v3): update navigation menu and add new documentation pages
* (authentication): update introductory phrase
* (auth): update authentication documentation and examples
* (guide): update configuration and error handling documentation
* update README and version bump
#### Others

* release version 3.0.0
* bump version to 3.0.0b2
* bump version to 3.0.0b1
* (tox): update pytest command to include specific test directory
* update PyPI token secret name
* update deploy-docs workflow for v2 branch removal
* simplify branch list syntax in deploy-docs workflow
* remove changelog generation and update workflow
* update deploy workflow and version
* update release workflow to commit CHANGELOG
* (release): add changelog generation to release workflow
* update GitHub Actions workflows
* update pytest command to use uv run
* update GitHub Actions workflow configurations
* remove benchmarking code and related files
* remove tox configuration
* remove flake8 and isort configurations
* (release): bump version to 3.0.0-alpha
* bump version to 3.0.0a1
* reformat code to improve readability and consistency
* remove old tests and update test strategy
* remove static file test and update dependency
* replace tox with direct pytest run
* (sessions): fix async test method in test_file_sessions
* (static): add comprehensive tests for static file serving
* (events): add tests for nexios event system
* ensure fresh config for each test and update CSRF default
* (websockets): add comprehensive tests for WebSocket functionality
* (requests): improve AJAX detection test
* add tests for request.object

Full set of changes: [`v2.11.13...v3.0.0`](https://github.com/nexios-labs/nexios/compare/v2.11.13...v3.0.0)

## v2.11.13 (2025-10-07)

#### Refactorings

* (exception_handler): remove router-level exception handlers

Full set of changes: [`v2.11.12...v2.11.13`](https://github.com/nexios-labs/nexios/compare/v2.11.12...v2.11.13)

## v2.11.12 (2025-10-07)

#### Refactorings

* (config): update configuration handling and remove validation

Full set of changes: [`v2.11.11...v2.11.12`](https://github.com/nexios-labs/nexios/compare/v2.11.11...v2.11.12)

## v2.11.11 (2025-10-07)

#### New Features

* (routing): add exception handling to router
* (application): add request_content_type parameter to routing methods
#### Fixes

* (routing): improve error handling for existing routes and update documentation
#### Refactorings

* (exception_handler): optimize exception handling and middleware initialization ([#194](https://github.com/nexios-labs/nexios/issues/194))
* (exception_handler): optimize exception handling and middleware initialization
* (openapi): move OpenAPI documentation setup to routing  ([#192](https://github.com/nexios-labs/nexios/issues/192))
* (routing): remove duplicate route check in Router
* (openapi): move OpenAPI documentation setup to routing
* (router): reorganize BaseRouter and BaseRoute
#### Docs

* (middleware): update middleware documentation and examples
* add Nexios CLI and framework details to documentation
* (readme): remove incorrect information about Rust engine
#### Others

* (readme): fix star message formatting

Full set of changes: [`v2.11.10...v2.11.11`](https://github.com/nexios-labs/nexios/compare/v2.11.10...v2.11.11)

## v2.11.10 (2025-10-04)

#### Docs

* add OpenGraph metadata to all pages

Full set of changes: [`v2.11.9...v2.11.10`](https://github.com/nexios-labs/nexios/compare/v2.11.9...v2.11.10)

## v2.11.9 (2025-10-03)

#### New Features

* (routing): enhance WebSocket route registration
#### Fixes

* Fix all pytest warnings
#### Refactorings

* (templating): update template context and middleware

Full set of changes: [`v2.11.8...v2.11.9`](https://github.com/nexios-labs/nexios/compare/v2.11.8...v2.11.9)

## v2.11.8 (2025-10-02)

#### Fixes

* (routing): add request_content_type parameter to Route and Router classes

Full set of changes: [`v2.11.7...v2.11.8`](https://github.com/nexios-labs/nexios/compare/v2.11.7...v2.11.8)

## v2.11.7 (2025-10-01)

#### Fixes

* (params):  fix params mismatch

Full set of changes: [`v2.11.6...v2.11.7`](https://github.com/nexios-labs/nexios/compare/v2.11.6...v2.11.7)

## v2.11.6 (2025-10-01)

#### New Features

* (routing): add request_content_type parameter to router

Full set of changes: [`v2.11.5...v2.11.6`](https://github.com/nexios-labs/nexios/compare/v2.11.5...v2.11.6)

## v2.11.5 (2025-10-01)

#### Refactorings

* (routing): use add_ws_route method directly
* (dependencies): remove debug print statement
#### Docs

* (course): remove Day 1 to Day 5 course materials

Full set of changes: [`v2.11.4...v2.11.5`](https://github.com/nexios-labs/nexios/compare/v2.11.4...v2.11.5)

## v2.11.4 (2025-09-25)

#### Fixes

* (dependencies): improve context passing to dependencies
* (templating): update context only if middleware provides it
#### Docs

* (seo): add html for github verification
* update site config and add base URL
#### Others

* (deps): bump typing-extensions from 4.12.2 to 4.15.0
* (deps): bump anyio from 4.3.0 to 4.11.0
* remove mkdocs dependency from dev requirements
* remove .nojekyll file from docs
* remove unnecessary blank lines

Full set of changes: [`v2.11.3...v2.11.4`](https://github.com/nexios-labs/nexios/compare/v2.11.3...v2.11.4)

## v2.11.3 (2025-09-16)

#### Fixes

* (application): check returned state before updating app state

Full set of changes: [`v2.11.2...v2.11.3`](https://github.com/nexios-labs/nexios/compare/v2.11.2...v2.11.3)

## v2.11.2 (2025-09-14)

#### New Features

* (docs): update theme colors and button styles
* (nexios): add request_content_type parameter for OpenAPI documentation
#### Fixes

* (http): remove debug prints and improve UploadedFile class
#### Refactorings

* (nexios): update UploadedFile for Pydantic 2 compatibility
* (parser): comment out size checks for parts and files
* (response): extract response processing logic into a separate function
#### Docs

* update middleware and session examples
* (auth): clarify authentication function signature and add tip
#### Others

* comment out max file size test and update tox configuration

Full set of changes: [`v2.11.1...v2.11.2`](https://github.com/nexios-labs/nexios/compare/v2.11.1...v2.11.2)

## v2.11.1 (2025-09-10)

#### Fixes

* (_response_transformer): remove None type from json response check
* (auth): update logging method in middleware
#### Refactorings

* (auth): replace request-specific logger with module-level logger
#### Docs

* (readme): update Nexios version to 2.11.x
* (guide): expand CLI documentation and improve getting started guide
* restructure documentation and remove duplicate content
#### Others

* (deps): update `typing-extensions` dependency
* (pydantic): update typing-extensions dependency for Python 3.10
* remove redundant dependency specifier
* (docs): update og:description meta tag content

Full set of changes: [`v2.11.0...v2.11.1`](https://github.com/nexios-labs/nexios/compare/v2.11.0...v2.11.1)

## v2.11.0 (2025-09-06)

#### New Features

* (examples): add class-based middleware example
* (docs): add Pydantic Integration link to sidebar
* (readme): update version and logo in readme
* (docs): update branding and add documentation styles
#### Refactorings

* (nexios): make code more concise and remove unused imports
* (examples): update database examples for async support
* (docs): update route parameter handling in example
#### Docs

* (middleware): add make_response usage examples
* update contributing guide and refactor documentation process
* remove outdated API reference documents
* (api): remove redundant openapi_config from NexiosApp example
* update response header method in routing guide
* (team): update Mohammed Al-Ameen's description
#### Others

* (docs): update dependency cache
* (deps): update nexios to v2.10.3

Full set of changes: [`v2.10.3...v2.11.0`](https://github.com/nexios-labs/nexios/compare/v2.10.3...v2.11.0)

## v2.10.3 (2025-08-28)

#### New Features

* (application): add global state support
* (websocket): enhance websocket route addition and update docs
#### Fixes

* (docs): correct logging_middleware function parameters
#### Docs

* remove outdated documentation file
* (guide): add streaming response guide and update ASGI content
* (routing): expand documentation on Group class and routing organization
#### Others

* (bump): bump 2.10.1 to 2.10.2
* (dependencies): re-order imports for better readability

Full set of changes: [`v2.10.2...v2.10.3`](https://github.com/nexios-labs/nexios/compare/v2.10.2...v2.10.3)

## v2.10.2 (2025-08-16)

#### Fixes

* (auth): add Callable import to jwt backend
* (request): change request.json() to request.json
#### Docs

* (auth): rewrite authentication API documentation
* (openapi): comprehensive guide updates for authentication and customization
* remove next steps section from concepts.md
* rewrite concepts page with updated framework details and ASGI focus
#### Others

* (benchmarks): update nexios version and lock file

Full set of changes: [`v2.10.1...v2.10.2`](https://github.com/nexios-labs/nexios/compare/v2.10.1...v2.10.2)

## v2.10.1 (2025-08-07)

#### Fixes

* (csrf): improve CSRF protection and token handling
* (docs): fix routing docs orgnization
* (docs):  fix websockets documentation on channels
#### Docs

* (csrf): add section for using CSRF with templates and AJAX
* update response header syntax in routing guide

Full set of changes: [`v2.10.0...v2.10.1`](https://github.com/nexios-labs/nexios/compare/v2.10.0...v2.10.1)

## v2.10.0 (2025-08-02)

#### New Features

* (auth): introduce new has_permission decorator
* (config): allow set_config to auto initalize MakeConfig class when kwargs is passed in
#### Fixes

* (docs): fix issues in docs

Full set of changes: [`v2.9.3...v2.10.0`](https://github.com/nexios-labs/nexios/compare/v2.9.3...v2.10.0)

## v2.9.3 (2025-07-30)

#### New Features

* Add multipart form data support
#### Refactorings

* (deps): clean dependecy
* (docs): refactor auth docs

Full set of changes: [`v2.9.2...v2.9.3`](https://github.com/nexios-labs/nexios/compare/v2.9.2...v2.9.3)

## v2.9.2 (2025-07-28)

#### New Features

* (middleware): enhance CSRF protection and documentation
#### Docs

* fix tiny issues in reame
* add csrf to docs ([#169](https://github.com/nexios-labs/nexios/issues/169))

Full set of changes: [`v2.9.1...v2.9.2`](https://github.com/nexios-labs/nexios/compare/v2.9.1...v2.9.2)

## v2.9.1 (2025-07-27)

#### Fixes

* clean up formatting in index.md and remove unnecessary whitespace
* remove duplicate entry for granian in requirements.txt
#### Docs

* enhance getting started guide and documentation
* Simplify and improve authentication guide with clearer explanations
* update README for Nexios version 2.9.x and clean up formatting
#### Others

* clean up CHANGELOG by removing outdated entries and fixing formatting issues

Full set of changes: [`v2.9.0...v2.9.1`](https://github.com/nexios-labs/nexios/compare/v2.9.0...v2.9.1)

## v2.9.0 (2025-07-23)

#### New Features

* update global dependency test to use custom error handling
* update README and main application structure, remove unused files, and add new index template
* add support for dependency injection error handling and global dependencies in tests
* enhance inject_dependencies to support context and app dependency injection
* enhance Context initialization with additional parameters for improved middleware functionality
#### Fixes

* ensure proper handling of async and sync handlers in inject_dependencies function
* update user type annotation from User to BaseUser in Context class
#### Refactorings

* simplify dependency injection in Router class
#### Docs

* update error handling and middleware documentation
* enhance error handling and middleware documentation
#### Others

* remove temporary package.json files and enhance documentation in getting-started and routing guides

Full set of changes: [`v2.8.6...v2.9.0`](https://github.com/nexios-labs/nexios/compare/v2.8.6...v2.9.0)

## v2.8.6 (2025-07-19)

#### Others

* update release workflow for improved automation

Full set of changes: [`v2.8.5...v2.8.6`](https://github.com/nexios-labs/nexios/compare/v2.8.5...v2.8.6)

## v2.8.5 (2025-07-19)

#### Others

* refactor release workflow for tag-based deployments
* remove PyPI publishing step from release workflow
* enhance release workflow with improved changelog handling

Full set of changes: [`v2.8.4...v2.8.5`](https://github.com/nexios-labs/nexios/compare/v2.8.4...v2.8.5)

## v2.8.4 (2025-07-18)

#### Fixes

* improve CSRF token handling and enhance security middleware defaults
#### Others

* update release workflow and improve CHANGELOG handling

Full set of changes: [`v2.8.3...v2.8.4`](https://github.com/nexios-labs/nexios/compare/v2.8.3...v2.8.4)

## v2.8.3 (2025-07-18)

#### Fixes

* initialize _session_cache in BaseSessionInterface constructor
#### Others

* enhance release workflow and add 404 error handling documentation

Full set of changes: [`v2.8.2...v2.8.3`](https://github.com/nexios-labs/nexios/compare/v2.8.2...v2.8.3)

## v2.8.2 (2025-07-18)

#### New Features

* add virtualenv setup step in release workflow
* implement new tag creation workflow for releases
* implement new tag creation workflow for releases
#### Fixes

* update build command in release workflow
#### Refactorings

* simplify release workflow by removing deprecated steps
#### Others

* remove release notes generation and CHANGELOG update from workflow
* reintroduce `uv publish` command in release workflow
* restore publish command in release workflow
* clean up release workflow by removing unused publish command
* update GitHub Actions release workflow permissions and token usage
* update version to 2.8.0.dev1 in pyproject.toml
* update CHANGELOG.md for version 2.8.0 release

Full set of changes: [`v2.8.0...v2.8.2`](https://github.com/nexios-labs/nexios/compare/v2.8.0...v2.8.2)

## v2.8.0 (2025-07-16)

#### New Features

* enhance dependency injection documentation
* add support for app-level and router-level dependencies
* add support for synchronous and asynchronous generator dependencies
* enhance run command to support custom commands as lists or strings
#### Fixes

* update release and triage workflows for consistency
* resolve issues with dependency merging in Router class
* add TYPE_CHECKING import for improved type hinting in _builder.py
#### Others

* bump version to 2.8.0 in pyproject.toml
* update dependencies and add PDF export functionality
* update VitePress dependency metadata
* update dependencies and enhance error logging in run command

Full set of changes: [`v2.7.0...v2.8.0`](https://github.com/nexios-labs/nexios/compare/v2.7.0...v2.8.0)

## v2.7.0 (2025-07-09)

#### New Features

* enhance templating system with request context support
#### Fixes

* improve session handling and error logging
* add version bump test comment to main module
#### Others

* bump version to 2.7.0 in pyproject.toml, __main__.py, and update readme.md header
* remove RELEASE_SETUP.md and refactor CLI config loading
* add Commitizen configuration for conventional commits and version management in pyproject.toml
* update CHANGELOG.md for v2.6.2 release, documenting app.run() simplification, new CLI support, and configuration management enhancements

Full set of changes: [`v2.6.2...v2.7.0`](https://github.com/nexios-labs/nexios/compare/v2.6.2...v2.7.0)

## v2.6.2 (2025-07-05)

#### Refactorings

* simplify app.run() method and add development warning
* remove unused imports from ping, shell, and urls command files to clean up code
#### Others

* bump version to 2.6.2 in pyproject.toml and __main__.py
* update release workflow to use POETRY_PYPI_TOKEN_PYPI for publishing to PyPI
* streamline project structure by removing unused files and updating configuration management documentation
* remove CHANGELOG.md and nexios.config.py files to streamline project structure and eliminate unused configurations
* update release workflow to improve tag handling and streamline release notes generation
* bump version to 2.6.2a1 in pyproject.toml and __main__.py; remove oneapp module and its related files
* update release workflow to generate changelog without immediate commit, allowing for accurate release notes

Full set of changes: [`v2.6.1...v2.6.2`](https://github.com/nexios-labs/nexios/compare/v2.6.1...v2.6.2)

## v2.6.1 (2025-07-03)

#### New Features

* enhance Nexios CLI commands to support optional configuration loading, improve error handling, and update command help descriptions for clarity
* enhance configuration management docs by adding support for .env files, enabling environment-specific settings, and improving validation for required configuration keys
* implement configuration file support for Nexios CLI, allowing app and server options to be defined in `nexios.config.py`, and enhance command functionality to load configurations seamlessly
* add 'URL Configuration' section to documentation and enhance CLI guide with new commands for listing URLs and checking route existence
* enhance app loading by adding auto-search for nexios.config.py and .nexioscli files in the current directory
* add CLI commands to list registered URLs and ping routes in the Nexios application, with support for loading app instances from module paths or config files
#### Refactorings

* clean up imports in CLI command files and remove unused type hints from ping, shell, and urls modules
* update imports in shell.py to suppress linting warnings and clean up exports in utils module
* remove unused 'normalize_url_path' from exports in utils module
* simplify CLI structure by removing unused utility and validation functions, consolidating command implementations, and enhancing app loading from main module
#### Docs

* update configuration documentation to highlight new CLI support for `nexios.config.py`, including usage tips and best practices for managing app and server options
* update CLI guide to reflect new configuration structure in `nexios.config.py`, streamline examples for development and production setups, and enhance clarity on command usage and supported variables
* update authentication documentation by correcting method calls and removing emoji from descriptions for improved clarity
#### Others

* bump version to 2.6.1 in pyproject.toml and __main__.py
* update release workflow to generate and commit CHANGELOG.md automatically
* remove deprecated `nexios.config.py` file as configuration support has been streamlined and integrated into the CLI
* update changelog for version 2.6.0, including release notes and version bump in README

Full set of changes: [`v2.6.0...v2.6.1`](https://github.com/nexios-labs/nexios/compare/v2.6.0...v2.6.1)

## v2.6.0 (2025-06-30)

#### Others

* update version to 2.6.0 in pyproject.toml and __main__.py

Full set of changes: [`v2.5.3...v2.6.0`](https://github.com/nexios-labs/nexios/compare/v2.5.3...v2.6.0)

## v2.5.3 (2025-06-30)

#### New Features

* enhance server startup by adding support for granian and uvicorn with temporary entry point creation
#### Fixes

* refine CORS preflight request test by updating allowed methods and headers to match middleware behavior
* update CORS middleware to handle preflight requests more robustly by refining header management and allowing dynamic header responses
#### Refactorings

* remove main function and update version constraints for pytest in uv.lock
#### Docs

* revise Day 3 and Day 4 course materials to improve clarity and organization, focusing on asynchronous programming, request/response handling, and the introduction of class-based views with APIHandler for better code management
* update Day 1 and Day 2 course materials to enhance clarity and structure, including improved explanations of Nexios features, routing concepts, and practical examples for building applications
* expand middleware and response handling sections in the guide to clarify usage of Nexios-specific and ASGI middleware, and enhance response object documentation with examples for various response types and customization options
#### Others

* update version to 2.5.4, enhance course materials with revised titles and improved clarity, and add changelog generation to release workflow
* clean up release.yml by removing unnecessary whitespace
* clean up release workflow by removing unused changelog generation steps
* update release workflow to checkout main branch after changelog update

Full set of changes: [`v2.5.2...v2.5.3`](https://github.com/nexios-labs/nexios/compare/v2.5.2...v2.5.3)

## v2.5.2 (2025-06-29)

#### New Features

* enhance NexiosApp.run method to support Granian server
#### Fixes

* correct spelling of 'exclude_from_schema' in application and routing modules
* update header encoding in StreamingResponse for compatibility
* remove duplicate import of NexiosApp in day22 index documentation
#### Refactorings

* update error handling UI and enhance JavaScript functionality
#### Docs

* enhance async-python, authentication, and configuration guides for clarity and completeness
* update link to Examples section in the Nexios guide for better navigation
#### Others

* remove auto-changelog configuration file and update release workflow to include changelog generation
* remove changelog generation step from release workflow
* bump version to 2.5.2
* bump version to 2.5.2 and change license to BSD-3-Clause in pyproject.toml; update release workflow to push changes
* update CHANGELOG.md for v2.5.1 release, including recent merges, fixes, and dependency updates

Full set of changes: [`v2.5.1...v2.5.2`](https://github.com/nexios-labs/nexios/compare/v2.5.1...v2.5.2)

## v2.5.1 (2025-06-26)

#### Fixes

* correct indentation in release workflow for changelog generation step
#### Others

* bump version to 2.5.1 in pyproject.toml and __main__.py
* update CHANGELOG.md for v2.5.0 release, documenting recent fixes and version bump

Full set of changes: [`v2.5.0...v2.5.1`](https://github.com/nexios-labs/nexios/compare/v2.5.0...v2.5.1)

## v2.5.0 (2025-06-21)

#### New Features

* add request verification and enhance locust tests
* introduce context-aware dependency injection system for request-scoped data access
#### Fixes

* allow optional status code in response methods and default to instance status code
#### Others

* bump version to 2.5.0 in pyproject.toml and __main__.py
* update release workflow to include auto-changelog generation and ensure all tags are fetched
* update CHANGELOG.md for v2.4.14 release, including recent fixes, documentation enhancements, and dependency updates

Full set of changes: [`v2.4.14...v2.5.0`](https://github.com/nexios-labs/nexios/compare/v2.4.14...v2.5.0)

## v2.4.14 (2025-06-20)

#### Fixes

* handle directory initialization and path formatting in StaticFiles class for improved file serving, closes [#136](https://github.com/nexios-labs/nexios/issues/136)
#### Docs

* enhance documentation across multiple guides with fundamental concepts, best practices, and structured tips for authentication, configuration, dependency injection, error handling, routing, and WebSocket usage
* remove outdated team and community sections from team.md to streamline documentation
#### Others

* bump version to 2.4.14 in pyproject.toml and __main__.py
* update CHANGELOG.md for v2.4.13 release with recent fixes, documentation updates, and dependency changes

Full set of changes: [`v2.4.13...v2.4.14`](https://github.com/nexios-labs/nexios/compare/v2.4.13...v2.4.14)

## v2.4.13 (2025-06-18)

#### Fixes

* update endpoint path formatting to simplify parameter representation in application.py
* resolve merge conflict by removing unnecessary conflict markers in client.py
* reorder import statements for improved organization in structs.py
#### Refactorings

* improve code clarity by renaming variables and enhancing type hinting across multiple files
* remove unused imports across various files to clean up the codebase
* update authentication handling and file upload method in API examples
#### Docs

* overhaul API examples documentation with updated code snippets, improved structure, and enhanced clarity for various use cases
* enhance getting started guide with uv package manager recommendations and installation instructions
* update API reference documentation to include new authentication, dependencies, and middleware sections, and enhance application setup examples
* add comprehensive API reference documentation for core components, request, response, and routing
#### Others

* bump version to 2.4.13 in pyproject.toml
* add 'dev' script to package.json for local development with VitePress
* remove obsolete Ruff linter workflow from GitHub Actions
* replace Flake8 and MyPy with Ruff in development dependencies
* enhance code formatting by integrating Ruff linter and updating auto-formatting scripts
* enhance ruff configuration and clean up example code by removing unused variables and assertions
* update project dependencies and enhance code formatting tools in pyproject.toml
* update flake8 configuration and improve type hinting across the codebase
* update development dependencies and improve code formatting in CI workflow
* remove benchmarks directory and update pytest options to ignore benchmarks
* remove outdated benchmark results and adjust benchmark script for improved request handling
* add seaborn and update Python version requirements in project dependencies
* update project version to 2.4.12 in uv.lock
* update CHANGELOG for v2.4.12 release, documenting recent changes and improvements

Full set of changes: [`v2.4.12...v2.4.13`](https://github.com/nexios-labs/nexios/compare/v2.4.12...v2.4.13)

## v2.4.12 (2025-06-15)

#### Others

* update project version to 2.4.12 in pyproject.toml and __main__.py
* update project version to 2.4.11 in pyproject.toml

Full set of changes: [`v2.4.11...v2.4.12`](https://github.com/nexios-labs/nexios/compare/v2.4.11...v2.4.12)

## v2.4.11 (2025-06-15)

#### Others

* add step to clean old builds in GitHub Actions workflow
* add step to clean old builds and simplify PyPI publishing in GitHub Actions workflow

Full set of changes: [`v2.4.10...v2.4.11`](https://github.com/nexios-labs/nexios/compare/v2.4.10...v2.4.11)

## v2.4.10 (2025-06-14)

#### Fixes

* update GitHub Actions workflow to run Tox with uv
* address minor bugs in middleware handling and improve error logging for better debugging
#### Refactorings

* remove .editorconfig and package-lock.json, update pyproject.toml for Hatchling, enhance requirements.txt, and modify GitHub Actions workflow for uv; adjust middleware usage in application and tests
* consolidate middleware imports and update related references across documentation and codebase
#### Docs

* update static files documentation to deprecate StaticFilesHandler, introduce StaticFiles class with usage examples, and enhance clarity on serving static assets
* expand Day 5 content on middleware in Nexios, introducing function-based and class-based middleware, built-in middleware examples, and best practices for implementation
* enhance API documentation with best practices, security considerations, and detailed examples for routing and parameter types
* update GitHub link in course index to reflect the correct repository URL
* update Discord and GitHub Issues links for community engagement and support
* revise course structure and content to transition from a 30-day to a 28-day format, enhancing clarity and detail in daily topics, and update metadata for improved SEO and user engagement
* develop a production-ready real-time collaboration platform using Nexios, featuring authentication, WebSocket communication, API endpoints, and comprehensive monitoring and error handling
* implement a real-time chat application using Nexios WebSockets, featuring channel management, message history, presence tracking, and private messaging capabilities
* enhance Day 13 and Day 14 content with WebSocket fundamentals, ChannelBox integration, and real-time chat features, including presence tracking and private messaging
* update Day 11, Day 12, and Day 13 content to reflect changes in request validation, file uploads, and WebSocket setup with Pydantic integration and improved error handling
* add 'Course' section to navigation and expand course content with detailed day-by-day topics for enhanced learning experience
* add 'Examples' section link to navigation for enhanced user access to practical implementations
* add 'Security' section link to the configuration for improved navigation and resource accessibility
* expand configuration and routing documentation with detailed examples, best practices, and enhanced clarity for improved user experience
* overhaul API examples and documentation structure to enhance clarity, introduce best practices, and provide comprehensive code snippets for common use cases
* enhance concepts and installation documentation with tips, warnings, and best practices for improved clarity and usability
#### Others

* add step to set up virtual environment in GitHub Actions workflow
* add setup step for virtual environment in GitHub Actions workflow
* update GitHub Actions workflow to install uv and dependencies, streamline dependency management with uv, and ensure Tox installation
* update file hashes in metadata for dependencies to reflect recent changes

Full set of changes: [`v2.4.9...v2.4.10`](https://github.com/nexios-labs/nexios/compare/v2.4.9...v2.4.10)

## v2.4.9 (2025-06-06)

#### New Features

* (openapi): enhance API documentation routes with customizable URLs for Swagger and ReDoc; add ReDoc UI generation
#### Refactorings

* (MakeConfig): update constructor to accept optional config and kwargs, merging them with defaults for improved flexibility
#### Others

* bump version to 2.4.9 in pyproject.toml
* update CHANGELOG for v2.4.8 release, detailing recent changes and improvements

Full set of changes: [`v2.4.8...v2.4.9`](https://github.com/nexios-labs/nexios/compare/v2.4.8...v2.4.9)

## v2.4.8 (2025-06-05)

#### New Features

* (templating): add templating guide link in documentation; refactor TemplateEngine for improved configuration handling and error management; update TemplateContextMiddleware for better type hints; remove unused utility functions
* (request): add properties and methods for enhanced request handling
#### Fixes

* restore __repr__ method in MakeConfig; add warning for missing secret_key in session handling
* (docs): improve clarity in concurrency guide and update examples for better understanding
#### Refactorings

* (tests): remove deprecated error handling test for concurrency utilities
#### Docs

* enhance core concepts and getting started guide for Nexios with detailed examples and improved structure
* update routing and framework overview in documentation for clarity and completeness
#### Others

* bump version to 2.4.8 in pyproject.toml and __main__.py
* add jinja2 dependency to tox.ini for template rendering support
* remove unused import from request.py to clean up code
* remove unused cached dependencies and temporary files from VitePress build
* (docs): update dependency metadata and remove deprecated theme index files
* update CHANGELOG for v2.4.7 release with recent features and enhancements
* (websockets): add comprehensive tests for WebSocket functionality and consumer behavior

Full set of changes: [`v2.4.7...v2.4.8`](https://github.com/nexios-labs/nexios/compare/v2.4.7...v2.4.8)

## v2.4.7 (2025-06-01)

#### New Features

* (docs): add 'Concurrency Utilities' section to the guide and update dependency metadata
* (routes): add test for adding route with path parameters
* (routes): enhance add_route method to support optional path and handler parameters
* (icon): redesign SVG icon with gradients, shadows, and new shapes
#### Fixes

* correct import paths from 'cuncurrency' to 'concurrency' and remove deprecated concurrency utility file
* (docs): update markdown configuration and correct file data handling in concurrency guide
* (docs): correct image upload handling in concurrency guide
* (request): cast session to BaseSessionInterface for type safety
* (application): restore _setup_openapi call in handle_lifespan method
* (session): streamline session configuration access and improve file path handling
* (session): improve session configuration handling with getattr for safer access
* (readme): update support icon URL to point to the new documentation site
#### Refactorings

* (dependencies): enhance dependency injection to support synchronous and asynchronous handlers
* move utility functions to a new location and remove deprecated files
* (middleware): rename __middleware to _middleware and update imports
#### Others

* update version to 2.4.7 and standardize versioning in documentation

Full set of changes: [`v2.4.6...v2.4.7`](https://github.com/nexios-labs/nexios/compare/v2.4.6...v2.4.7)

## v2.4.6 (2025-05-30)

#### Fixes

* (openapi): implement OpenAPI setup during application shutdown and improve JSON property typing
#### Others

* (versioning): Bump version from 2.4.5 to 2.4.6
* update CHANGELOG for v2.4.5 release with recent fixes and enhancements

Full set of changes: [`v2.4.5...v2.4.6`](https://github.com/nexios-labs/nexios/compare/v2.4.5...v2.4.6)

## v2.4.5 (2025-05-27)

#### Fixes

* Remove debug print statements and clean up lifespan event handling
* Remove unnecessary method call in lifespan event handling
* Improve error logging in lifespan event handling and clean up whitespace
#### Others

* bump version to 2.4.5 in __main__.py and pyproject.toml
* Update CHANGELOG for v2.4.4 release with new features, refactors, and tests

Full set of changes: [`v2.4.4...v2.4.5`](https://github.com/nexios-labs/nexios/compare/v2.4.4...v2.4.5)

## v2.4.4 (2025-05-25)

#### New Features

* implement form parsing and routing enhancements with new internal modules
#### Fixes

* Set default path for Group initialization and add test for external ASGI app integration
* Updates route handling to support both Routes and BaseRoute instances
* improve error message for client disconnection in ASGIRequestResponseBridge
#### Refactorings

* Remove trailing slash from Group path initialization and clean up unused tests
* Improve type hints and path handling in Group class
* reorganize middleware structure and update routing to use new middleware definitions
#### Docs

* Add Groups section and examples to routers-and-subapps guide; fix NexiosApp instantiation in index
#### Others

* update changelog to include recent changes
* update changelog for version 2.4.3 release
* Enhance routing tests for Group class with multiple scenarios

Full set of changes: [`v2.4.3...v2.4.4`](https://github.com/nexios-labs/nexios/compare/v2.4.3...v2.4.4)

## v2.4.3 (2025-05-20)

#### New Features

* enhance server error template with improved layout and request information section
* add handler hooks documentation and implement before/after request decorators
* add examples for authentication, exception handling, middleware, request inputs, responses, and routing
* add JWT and API key authentication backends
#### Fixes

* update workflow to ignore pushes to main branch
* update typing SVG font and styling in README
* correct heading formatting in getting started guide
#### Others

* update version to 2.4.3 in documentation and pyproject.toml
* (release): bump version to 2.4.2 in changelog and update documentation

Full set of changes: [`v2.4.2...v2.4.3`](https://github.com/nexios-labs/nexios/compare/v2.4.2...v2.4.3)

## v2.4.2 (2025-05-15)

#### New Features

* add File Router guide to documentation and update config for navigation
* add ASGI and Async Python guides to documentation
#### Fixes

* improve JWT import error handling and raise informative exceptions
* update project description for clarity on performance features
* clean up code formatting and add deprecation warning for get_application
* (ci): improve comments and update PyPI publishing step in release workflow
#### Refactorings

* update VitePress config for improved structure and clarity
* enhance method detection in APIView for dynamic method registration
* replace get_application with NexiosApp and add startup/shutdown hooks
#### Others

* update version to 2.4.2 in documentation and project files
* (release): bump version to 2.4.1 and update changelog, documentation, and README

Full set of changes: [`v2.4.1...v2.4.2`](https://github.com/nexios-labs/nexios/compare/v2.4.1...v2.4.2)

## v2.4.1 (2025-05-14)

#### New Features

* (ci): add GitHub Actions workflow for automated release on tag push
* (router): add base_app reference to scope for improved access in request handling
#### Fixes

* (docs): remove redundant phrasing in framework description for clarity
* (docs): simplify installation instructions by removing broken examples
* (docs): correct GitHub link in VitePress config for accuracy
* (docs): update version badge from 2.4.0rc1 to 2.4.0 for consistency
* (router): inherit BaseRouter in Router and WSRouter classes for consistency
* (docs): remove inline comment from routing example for clarity
* (docs): remove inline comments from routing example for clarity
* add type hints for version and callable parameters in multiple files
* (router): remove debug print statement from Router class
* (router): store reference to the Router instance in scope for better access
* update documentation URL to point to the correct Netlify site
* (cli): update warning message for clarity on Granian integration
* update version number to 2.4.0 and enhance README for consistency
#### Docs

* update tips in getting-started and add reverse routing section in routing
#### Others

* add test for url generation with request parameters
* add handler_args test for route handler

Full set of changes: [`v2.4.0...v2.4.1`](https://github.com/nexios-labs/nexios/compare/v2.4.0...v2.4.1)

## v2.4.0 (2025-05-11)

#### New Features

* set base path for VitePress configuration
* set base path for VitePress configuration
* add .nojekyll file to prevent GitHub Pages from ignoring files
* add .nojekyll file to prevent GitHub Pages from ignoring _files
* (docs): update API Reference link and enhance Getting Started section with version badge
* (docs): add OpenAPI section to navigation and enhance OpenAPI documentation links
* (docs): update getting started section to use pip for installation and remove VitePress references
* (docs): enhance file upload documentation and update site configuration with social links
* (docs): update CORS documentation and add file upload guide
* (docs): enhance API documentation with detailed sections on application, request, response, routing, and WebSocket handling
* (docs): update VitePress config with new meta tags and favicon for improved SEO and branding
* (docs): add comprehensive CLI documentation including installation, usage, commands, and server selection
* (docs): enhance WebSocket documentation with new sections on Channels, Groups, and Static Files
* (docs): add Howto and Websockets sections to navigation and create initial markdown files
* (docs): add Request Info section with detailed examples for handling HTTP requests
* (docs): add Authentication and Session Management documentation with examples
* (docs): add Events section to documentation with usage examples
* (docs): add manual integration section for pagination with example code
* (docs): add documentation for Class-Based Views with usage examples and middleware support
* (pagination): enhance response methods to accept custom data handlers for synchronous and asynchronous pagination
* (pagination): implement synchronous and asynchronous pagination methods with customizable strategies and data handlers
* (docs): add 'Error Handling' guide with comprehensive coverage and examples for managing exceptions
* (docs): enhance headers guide with detailed examples and best practices for request and response headers
* (docs): add 'Headers' guide with detailed examples for request and response headers
* (docs): enhance 'Cookies' guide with comprehensive examples and security best practices
* (docs): add 'Middleware' and 'Cookies' guides to documentation
* (docs): add 'Routers and Sub-Applications' guide and update navigation
* (docs): add 'Sending Responses' guide and update navigation
* (routing): enhance request handling by passing path parameters to route handlers
* (docs): enhance documentation with getting started and routing guides
* (docs): add comprehensive documentation and configuration for Nexios framework
* (di): Enhance dependency injection and add string representation for Request class
* Implement advanced event system with support for priority listeners, event phases, and asynchronous execution
* Add comprehensive overview of Nexios framework in about.md
* Update SUMMARY.md to include comprehensive Dependency Injection section
* Enhance documentation and add dependency injection support in Nexios framework
* Add comprehensive documentation for About section, including Authors, Design Patterns, Performance, and Philosophy
* Enhance dependency injection system with new documentation and integration in routing
* Implement dependency injection system with DependencyProvider and related classes
* Add multi-server support with Uvicorn and Granian in Nexios CLI
* Add example applications and routes for Nexios framework
* Add new project templates with enhanced features and configurations
* Enhance SUMMARY.md with additional sections and improved structure
* Implement comprehensive WebSocket testing suite with multiple endpoints and error handling
* Add WebSocket support and enhance form data handling
* (errors): Enhance server error handling with detailed debugging information and improved HTML template
* (cli): Implement CLI tools for project scaffolding and development server management; enhance documentation
* (routing): enhance request handling to support JSON responses
#### Fixes

* update feature list in README for accuracy and clarity
* update version number and enhance README badges
* remove redundant options and examples from CLI documentation
* remove base path from VitePress configuration
* update base path in VitePress configuration
* set base path in VitePress configuration
* remove base path from VitePress configuration
* update install command to prevent frozen lockfile during dependency installation
* correct whitespace in hero name in index.md
* remove base path from VitePress configuration
* update install command in GitHub Actions workflow for consistency
* update step name for clarity in GitHub Pages deployment
* remove .nojekyll creation step from deploy workflow
* update install command in deploy-docs workflow to use pnpm install
* enable pnpm setup and correct build command formatting in deploy-docs workflow
* (docs): update metadata and lockfile for improved dependency management
* (docs): correct path parameter access in room handler and chat endpoint
* (config): Initialize configuration in NexiosApp constructor
* Correct order of sections in SUMMARY.md for better clarity
* (openapi): set default type for Schema and update model references
* (import): handle ImportError for Jinja2 with a clear installation message
* (routing): remove unused response_model parameter and handle empty path case
#### Refactorings

* update GitHub Actions workflow for VitePress deployment
* streamline deployment workflow for VitePress
* (cli): streamline project creation and server run commands, enhance validation functions
* (response): simplify headers property and update header preservation logic
* (docs): update response header method references to use set_header
* (routing): change request_response to async and await its execution in Routes class
* (routing): move Convertor and related classes to converters.py
* (dependencies): remove unnecessary inheritance from Any in Depend class
* (types): remove unused ParamSpec import
* remove debug print statements and enhance dependency injection in routing
* (minor): Remove unused TypeVar and clean up lifespan handling in NexiosApp
* Update typing imports and lifespan type annotation in __init__.py
* (docs): Remove redundant examples and streamline event handling section in events.md
* Improve type annotations and remove unnecessary type ignores across multiple files
* update type annotations for middleware functions to improve clarity and consistency
* enhance type annotations for improved clarity and consistency across application, exception handling, and middleware modules
* streamline type annotations and clean up imports across application, dependencies, routing, and types modules
* Add support for additional route parameters in Router class
* Enhance lifespan shutdown handling in NexiosApp
* Simplify lifespan shutdown handling in NexiosApp
* Update Nexios to use Granian server and enhance configuration options
* Remove WebSocket connection handling from Client class
* Remove debug print statement from ASGI application callable
* (websockets): rename WebSocketEndpoint to WebSocketConsumer and update imports
* (session): reorganize session handling and update imports
#### Docs

* Update middleware usage example to reflect changes in route binding
* Remove section on Exception Middleware from error handling documentation
* Update routing documentation to reflect changes in dynamic route handling
* Update feature list to specify 'Inbuilt Database ORM Integration'
* Add comprehensive API reference documentation for Application, Request, Response, Routing, Middleware, and Exceptions
* Enhance documentation for Dependency Injection and Nexios framework with examples and architecture overview
#### Others

* add gh-pages for deployment and update scripts in package.json
* update .gitignore, add GitHub Actions workflow for deploying docs, and create package.json for VitePress
* (release): update version to 2.4.0rc1 and remove deprecated version file
* (docs): enhance handlers and routers documentation with additional examples and clarifications
* (docs): update docs structure for improved readability and maintainability
* (docs): add API reference and enhance guides for handlers, request inputs, and lifecycle management
* (docs): enhance routing documentation with examples and detailed explanations
* (docs): Revise SUMMARY.md and CLI Tools documentation for clarity and consistency
* (docs): Remove redundant section headers and clean up API reference in SUMMARY.md
* remove mypy type checking workflow from GitHub Actions
* (deps): update mypy version to ^1.15.0 and adjust configuration settings
* (docs): Update README.md for improved section headings and formatting
* (docs): Revamp README.md layout and content for improved clarity and engagement
* (docs): Update About section link format in SUMMARY.md
* (docs): Add empty link for About section in SUMMARY.md
* (docs): Remove About Nexios link from SUMMARY.md for improved clarity
* (docs): Update About Nexios link format in SUMMARY.md
* (docs): Add About Nexios link to SUMMARY.md
* (docs): Remove About section from SUMMARY.md for improved clarity
* (pyproject): add pyjwt dependency to development dependencies
* (pyproject): update author email and documentation link
* (pyproject): update homepage and repository links to reflect correct URLs
* (pyproject): add project metadata section for homepage, documentation, funding, and source links

Full set of changes: [`v2.3.1...v2.4.0`](https://github.com/nexios-labs/nexios/compare/v2.3.1...v2.4.0)

## v2.3.1 (2025-04-14)

#### New Features

* (docs): add comprehensive documentation for Nexios configuration and hooks
* (funding): add funding configuration for "Buy Me a Coffee"
* (application): add responses parameter to route handler
* (router): add exclude_from_schema option to FileRouter and Router classes
#### Fixes

* (application): update default config import and streamline code formatting
* (auth): remove unused import from jwt backend
* (docs): improve formatting and clarity in managing_config.md
* (docs): standardize warning formatting and update hook descriptions in misc.md
* (docs): add missing links for Managing Config and Misc in SUMMARY.md
* (readme): update badge alignment and formatting in README files
* (funding): add GitHub funding link for techwithdunamix
* (tox): add pytest-asyncio and pydantic dependencies; update asyncio_fixture_scope in pytest options
* (readme): update image attributes for Swagger API documentation
* (readme): update visitor count alt text and correct image path
* (docs): update GzipMiddleware usage in example to use wrap_asgi method
* (router): handle empty context in render function to prevent errors
* (router): correct path handling in FileRouter for improved route mapping
* (router): improve method handling in FileRouter for route mapping
* (router): fixed method handling and schema exclusion in FileRouter
#### Refactorings

* (openapi): streamline OpenAPI configuration and documentation setup
* (middleware): update middleware integration and improve ASGI compatibility
#### Docs

* (readme): add "Buy Me a Coffee" section for support
#### Others

* (response_rests): update file path handling in send_file_response function
* (version): bump version to 2.3.1rc3
* (version): bump version to 2.3.1rc2
* (version): update version to 2.3.0rc1 and 2.3.1rc1 in main.py and pyproject.toml
* (events): add comprehensive tests for event registration, triggering, and propagation

Full set of changes: [`v2.3.0-rc.1...v2.3.1`](https://github.com/nexios-labs/nexios/compare/v2.3.0-rc.1...v2.3.1)

## v2.3.0-rc.1 (2025-04-05)

#### New Features

* (logging): update logging documentation for clarity and consistency; remove deprecated file-router documentation
* (routing): enhance path parameter replacement using regex for improved flexibility
* (file_router): add restrict_slash method and improve path handling in route mapping
* (file_router): implement new HTML rendering functionality and restructure file organization
* (application): add OpenAPI setup during application startup
* (routing): enhance route documentation and add get_all_routes method
* (session): add session configuration enhancements and improve expiration handling
* (auth): implement session-based authentication backend and enhance session handling
* (file_router): refactor route handling to use pathlib for module imports and streamline method mapping
* (openapi): add Swagger UI generation and auto-documentation capabilities
* (openapi): enhance path parameter handling and request/response preparation in APIDocumentation
* (openapi): implement OpenAPI configuration and documentation routes
* (openapi): add initial OpenAPI models and structure
* (websockets): add as_route class method to convert WebSocketEndpoint into a route
* (auth): enhance authentication decorator to accept string or list of scopes
* ✨: add make_response method to create responses using custom response classes; enhance method chaining with preserved headers and cookies
* ✨: add content_length property and set_body method in NexiosResponse; enhance set_headers to support overriding headers in CORS middleware
* 🔧: add lifespan support to NexiosApp and implement close_all_connections method in ChannelBox
* ✨: enhance WebSocketEndpoint with logging capabilities and new channel management methods
* ✨: add GitHub Actions workflow for running tests and uploading coverage reports
* enhance JWT handling and add route-specific middleware decorator
* update authentication backends to improve configuration handling and error reporting
* update project initialization and database configuration templates for improved database connection handling
* enhance Nexios CLI with project initialization and database setup commands
* implement authentication backends and middleware for user authentication
* implement JWT authentication backend and utility functions for token handling
* implement API key and session authentication backends for enhanced security
* implement basic authentication backend and middleware for user authentication
* implement authentication middleware and user classes for enhanced user management
* add request lifecycle decorators for enhanced request handling and logging
* initialize authentication module in the Nexio library
* add parameter validation for route handlers and enhance route decorators
* enhance middleware execution and improve session expiration handling
* update logo to SVG format and adjust mkdocs configuration and request file methods
#### Fixes

* (routing): remove unnecessary blank line in Router class
* (cors): standardize header casing and improve CORS middleware logic
* (session): correct string representation in BaseSessionInterface and clean up test cases
* (session): update session expiration logic and improve session management
* (test): correct typo in first_middleware function parameter name
* (websockets): remove unused import of MiddlewareType in consumers.py
* (workflow): update permissions and simplify git push in format-code.yml
* (workflow): update GitHub token usage in format-code.yml for secure pushing
* (workflow): update GitHub token secret name in deploy-docs.yml
* (websockets): import WebsocketRoutes inside as_route method to avoid import errors
* 🔧: correct app reference in handle_http_request; add wrap_with_middleware method to support ASGI middleware integration; improve error handling in BaseMiddleware
* 🔧: suppress RuntimeError in BaseMiddleware to handle EndOfStream gracefully; add type ignore for message assertion
* 🔧: remove debug print statement for message in NexiosApp to clean up output
* 🔧: improve exception handling in collapse_excgroups; update BaseResponse initialization to remove setup parameter and enhance cookie management
* 🔧: update datetime import to use timezone.utc; simplify payload sending logic in Channel class
* 🔧: handle empty range end in FileResponse initialization to prevent ValueError
* 🔧: update FileResponse initialization and improve range handling in response.py; modify BaseMiddleware to suppress RuntimeError; clean up test_response.py
* 🔧: update FileResponse initialization to include setup parameter and clean up range handling comments
* 🔧: update .gitignore, improve gzip documentation, refactor middleware handling, and replace print statements with logger in hooks
* 🔧: ensure websocket is closed properly on disconnect in WebSocketEndpoint
* 🔧: add channel_remove_status variable in ChannelBox and simplify loop in WebSocketEndpoint
* 🔧: make expires parameter optional in Channel class constructor
* simplify method type casting in Request class
* update cookie deletion logic to use None and set expiry to 0
* improve request handling and error logging in NexioApp
* update allowed HTTP methods to lowercase and improve method validation in CORS middleware
* remove debug print statements from response and middleware classes
* remove debug print statements and update CORS headers handling
* re issues
#### Refactorings

* (examples): remove unused file router and HTML plugin examples
* (models): simplify parameter type annotations in OpenAPI models
* (structs): remove redundant comment in Address class
* (openapi): remove unused constants and enhance OpenAPIConfig with contact and license fields
* (openapi): streamline APIDocumentation class and enhance parameter handling
* (style): clean up whitespace and formatting in application.py and routing.py
* (style): apply code formatting and clean up whitespace across multiple files
* ♻️: replace getLogger with create_logger and update logo size in README
* ♻️: update documentation for Class-Based Views and remove Class-Based Handlers
* ♻️: update APIView to assign request and response attributes
* ♻️: remove unused import from routing module
* ♻️: remove unused imports and clean up HTTPMethod class in types module
* ♻️: remove APIHandler class; introduce APIView for enhanced class-based views with routing support
* ♻️: reorganize utils and async_helpers; move functions to _utils and update imports
* 🔧: remove unused middlewares and update FileResponse initialization in response.py
* 🔧: rename __handle_lifespan to handle_lifespan and improve message logging in NexiosApp
* remove database session management and related files
* remove direct authentication middleware instantiation and simplify BasicAuthBackend initialization
* remove BaseConfig dependency and implement global configuration management
#### Docs

* update README with corrected logo URL and refined formatting
* enhance lifespan documentation to include async context manager and clarify lifecycle hooks
* (contributing): enhance contribution guidelines and clarify expectations
#### Others

* (deps): update pydantic requirement from ^1.10.2 to >=1.10.2,<3.0.0
* (gitignore): adds .DS_Store to .gitignore file
* (test): add comprehensive tests for request properties, query parameters, path parameters, headers, cookies, state, and body handling
* (docs): improve formatting and consistency in README.md
* (git): add coverage.xml to .gitignore
* (ci): install project dependencies using Poetry in GitHub Actions workflow
* (deps): add pydantic dependency to pyproject.toml
* (docs): add Nexios Events section to documentation
* (test): add exception handlers for server and HTTP errors
* (docs): update table of contents and add plugins section
* (docs): remove obsolete documentation files
* 🔧: update version to 2.1.0rc1 in main and pyproject.toml
