# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

<!-- insertion marker -->
## [v3.3.0](https://github.com/nexios-labs/Nexios/releases/tag/v3.3.0) - 2025-11-11

<small>[Compare with v3.2.1](https://github.com/nexios-labs/Nexios/compare/v3.2.1...v3.3.0)</small>

### Features

- enhance WebsocketRouter to support mounted routers and Groups ([7041828](https://github.com/nexios-labs/Nexios/commit/7041828cce2d69f295a23bcc220ec50751ca42fb) by techwithdunamix).

### Bug Fixes

- remove sub-router mounting logic ([71cf84a](https://github.com/nexios-labs/Nexios/commit/71cf84a4a3707aca894f53347c4c17ef98acf059) by techwithdunamix).

### Code Refactoring

- unify HTTP and WebSocket routing ([c713fb8](https://github.com/nexios-labs/Nexios/commit/c713fb8a9912203a975d870dac94b4c98b309f45) by techwithdunamix).
- merge WSRouter into Router for unified routing ([cb3c2e6](https://github.com/nexios-labs/Nexios/commit/cb3c2e6419ec028a98efaf5c9c6b5555bfa6046d) by techwithdunamix).
- improve route matching and method handling ([071df3d](https://github.com/nexios-labs/Nexios/commit/071df3d6195bf8be6533c662f43105d64d0f1fb0) by techwithdunamix).
- update route matching to use scope object ([e74147b](https://github.com/nexios-labs/Nexios/commit/e74147bbb466196a5dcc7d6ce9d2b1bab3ffb1c6) by techwithdunamix).

## [v3.2.1](https://github.com/nexios-labs/Nexios/releases/tag/v3.2.1) - 2025-11-07

<small>[Compare with v3.2.0](https://github.com/nexios-labs/Nexios/compare/v3.2.0...v3.2.1)</small>

### Features

- add dynamic OG image and social sharing meta tags (#214) ([a6520cf](https://github.com/nexios-labs/Nexios/commit/a6520cf929811b52e4118fdd3391ffda1be00687) by techwithdunamix).

### Code Refactoring

- replace generic Parameter with specific types (#216) ([0b7c40d](https://github.com/nexios-labs/Nexios/commit/0b7c40d2c1a3ad40c7faa2771e80590a11d74897) by dunamix 🦄).

## [v3.2.0](https://github.com/nexios-labs/Nexios/releases/tag/v3.2.0) - 2025-11-07

<small>[Compare with v3.1.0](https://github.com/nexios-labs/Nexios/compare/v3.1.0...v3.2.0)</small>

### Features

- implement automatic OpenAPI documentation and UI serving ([60b2acd](https://github.com/nexios-labs/Nexios/commit/60b2acda2cee618fd8ed7dbe7cb906e0ecb5e31c) by techwithdunamix).
- implement automatic OpenAPI specification generation ([d09b47c](https://github.com/nexios-labs/Nexios/commit/d09b47c0cc872682b777fb94f4335b506fc3bb9f) by techwithdunamix).
- Add utility function for extracting routes recursively ([b3630a7](https://github.com/nexios-labs/Nexios/commit/b3630a708502827e9a988ffe2332fe15fa88c430) by techwithdunamix).

### Bug Fixes

- improve route path handling and specification generation ([f5e7d6e](https://github.com/nexios-labs/Nexios/commit/f5e7d6e76227358625e3a61a50fcc267de1d47b5) by techwithdunamix).

### Code Refactoring

- remove APIDocumentation singleton and unused imports (#211) ([ba14678](https://github.com/nexios-labs/Nexios/commit/ba1467889bae07271089030a83ac2266379eb5d2) by dunamix 🦄).
- remove APIDocumentation instantiation from NexiosApp ([fc43ae4](https://github.com/nexios-labs/Nexios/commit/fc43ae4298a65234a0e2102359b5ad52252964a7) by techwithdunamix).
- move get_openapi function to APIDocumentation class ([eb0f25b](https://github.com/nexios-labs/Nexios/commit/eb0f25b9859941ff16e83da719d43475a427e3af) by techwithdunamix).
- restructure routing and grouping (#210) ([8c92b07](https://github.com/nexios-labs/Nexios/commit/8c92b07070cdbc124b56be53298e806ca554985d) by dunamix 🦄).

## [v3.1.0](https://github.com/nexios-labs/Nexios/releases/tag/v3.1.0) - 2025-11-03

<small>[Compare with v3.0.0](https://github.com/nexios-labs/Nexios/compare/v3.0.0...v3.1.0)</small>

### Bug Fixes

- improve scope checking in auth decorator  (#205) ([ede042e](https://github.com/nexios-labs/Nexios/commit/ede042ef1233e5eca74ec445989db53ce3ac0917) by dunamix 🦄).
- improve scope checking in auth decorator (#205) ([ceff089](https://github.com/nexios-labs/Nexios/commit/ceff089b2080f140d17952094a32c9c241d02ba9) by techwithdunamix).
- return streamed response in call_next manager ([30ffb16](https://github.com/nexios-labs/Nexios/commit/30ffb16eedaa6b0d4554ba1993051302f94b37d2) by techwithdunamix).

## [v3.0.0](https://github.com/nexios-labs/Nexios/releases/tag/v3.0.0) - 2025-11-01

<small>[Compare with v2.11.13](https://github.com/nexios-labs/Nexios/compare/v2.11.13...v3.0.0)</small>

### Features

- add path setter to URL struct ([83caf66](https://github.com/nexios-labs/Nexios/commit/83caf66938a75f7f86222968fbe5db4f0f376917) by techwithdunamix).
- enhance StaticFiles with security, caching, and custom handlers ([6b6e7fa](https://github.com/nexios-labs/Nexios/commit/6b6e7fa4d00290e940b51ea186cf341659e62771) by techwithdunamix).
- refactor authentication examples and update documentation ([894b2aa](https://github.com/nexios-labs/Nexios/commit/894b2aa23aaa82e5d307bbcd2571bf201beb5a71) by techwithdunamix).
- enhance request handling and add property checks ([486fbf8](https://github.com/nexios-labs/Nexios/commit/486fbf89ab924496fc9d77f44b587b686fdc0132) by techwithdunamix).
- enhance StaticFiles serving with security and functionality improvements ([524e38b](https://github.com/nexios-labs/Nexios/commit/524e38b9b1a9d0e26681fb89efa572cb8d7bce7d) by techwithdunamix).
- add root_path support for mounted applications ([9f2a225](https://github.com/nexios-labs/Nexios/commit/9f2a225c8aed3ad2be47f8f4da609efbf4ee92f5) by techwithdunamix).
- add custom authentication backend and improve permission handling ([b122390](https://github.com/nexios-labs/Nexios/commit/b122390fce8ed8ddcd10ff43c4a5ed172624086c) by techwithdunamix).
- add API key authentication backend and documentation ([f5e4549](https://github.com/nexios-labs/Nexios/commit/f5e4549aba676c7479927b5ca43196370c108ece) by techwithdunamix).

### Bug Fixes

-  return the streamed response instead of nexios response manager for the call_next function manager ([9c7bb62](https://github.com/nexios-labs/Nexios/commit/9c7bb62e140f497382d5768abbcfef1b2400b230) by techwithdunamix).
- correct the use of process.nextTick ([964dd41](https://github.com/nexios-labs/Nexios/commit/964dd41bf62a1a8d38677d84c450b3cc4a199277) by techwithdunamix).
- enhance cursor decoding and error handling ([c557a9c](https://github.com/nexios-labs/Nexios/commit/c557a9c7514bca3b79221187a2d2bb8172c0e0c6) by techwithdunamix).
- replace delete_session with del for session management ([329ad1f](https://github.com/nexios-labs/Nexios/commit/329ad1f8411dee1a7e42e084486c6b0166d8291c) by techwithdunamix).
- improve CORS middleware and error handling ([d632ec9](https://github.com/nexios-labs/Nexios/commit/d632ec96f1c0414f182eb6abd9777fd6bf1754b8) by techwithdunamix).
- improve CORS method validation and preflight handling ([8aa71ab](https://github.com/nexios-labs/Nexios/commit/8aa71ab388fe331003693d80d66fee1794782a87) by techwithdunamix).
- remove unused context injection code ([6edc2f4](https://github.com/nexios-labs/Nexios/commit/6edc2f42e4b6a7bb14e2bc88399956aba06fd28d) by techwithdunamix).
- correctly prefix HTTP endpoint paths in OpenAPI documentation ([e285b6e](https://github.com/nexios-labs/Nexios/commit/e285b6ea53b53195cb2f70c7006e6be69a0ce1a4) by techwithdunamix).
- correct expires header to use UTC time ([471aea6](https://github.com/nexios-labs/Nexios/commit/471aea61c9415a4c740d86e4d12a12f2f426cd26) by techwithdunamix).
- use set_header method to manage response headers ([dcf17bb](https://github.com/nexios-labs/Nexios/commit/dcf17bb449f96766b0558a34ff29966f400d63b1) by techwithdunamix).
- fix url_for nested routes tests: add tests for routing ([afa3dae](https://github.com/nexios-labs/Nexios/commit/afa3daec0f06c588e9192b4bbd8d3d447270d1f9) by techwithdunamix).
- resolve import issues and improve authentication handling ([78034ec](https://github.com/nexios-labs/Nexios/commit/78034ec49d86f894b41f574c867e4f1ccd65050f) by techwithdunamix).

### Code Refactoring

- restructure authentication module imports ([edc3c3c](https://github.com/nexios-labs/Nexios/commit/edc3c3c3510d03b7b65b3d460980709fce7de958) by techwithdunamix).
- remove deprecated StaticFilesHandler class ([d140038](https://github.com/nexios-labs/Nexios/commit/d1400382103a168727d87b44135b053748dd8505) by techwithdunamix).
- remove common middleware ([40d3080](https://github.com/nexios-labs/Nexios/commit/40d30806b4c0643f027fb5b6b74d8417c1ddf00c) by techwithdunamix).
- improve file session management ([300b992](https://github.com/nexios-labs/Nexios/commit/300b9921d66f12be96ceb2db491a840366de9758) by techwithdunamix).
- remove path parameter from mount methods ([bfef31d](https://github.com/nexios-labs/Nexios/commit/bfef31d790c60a3f7539dfc8960167049bc5e7fb) by techwithdunamix).
- improve type annotations and remove unused imports ([c92d8a4](https://github.com/nexios-labs/Nexios/commit/c92d8a48b30c95ab5de03dd350ecec47cf2608ee) by techwithdunamix).
- add type: ignore comments to suppress mypy errors ([7114fe8](https://github.com/nexios-labs/Nexios/commit/7114fe8d66ad453a8f62d01ff4bc5d5629c06c68) by techwithdunamix).
- remove file router and apply static typing ([d961614](https://github.com/nexios-labs/Nexios/commit/d9616142be8d337145e6be326e44d19d8f607c38) by techwithdunamix).
- update user auth system to latest standard ([c422440](https://github.com/nexios-labs/Nexios/commit/c422440b91b3fc37b979e3ba627d93791aa848f7) by techwithdunamix).
- update user authentication and loading process ([be7509e](https://github.com/nexios-labs/Nexios/commit/be7509ebc6140bc9c9c36b26877af7aaa1c57d4b) by techwithdunamix).
- overhaule authentication system ([a636a99](https://github.com/nexios-labs/Nexios/commit/a636a997efd28fee6983adee14810f694c7fa584) by techwithdunamix).
- remove hooks and related tests ([d501922](https://github.com/nexios-labs/Nexios/commit/d5019223e20c599b6f734b8ccb0f70556c083836) by techwithdunamix).
- reorganize user and authentication modules ([52f6dcd](https://github.com/nexios-labs/Nexios/commit/52f6dcd063caeb7a061afff94e6cd2c7dbe9777e) by techwithdunamix).

## [v2.11.13](https://github.com/nexios-labs/Nexios/releases/tag/v2.11.13) - 2025-10-07

<small>[Compare with v2.11.12](https://github.com/nexios-labs/Nexios/compare/v2.11.12...v2.11.13)</small>

### Code Refactoring

- remove router-level exception handlers ([fcd5279](https://github.com/nexios-labs/Nexios/commit/fcd527981561fde79e7c935443a4cafc7c34e4f9) by techwithdunamix).

## [v2.11.12](https://github.com/nexios-labs/Nexios/releases/tag/v2.11.12) - 2025-10-07

<small>[Compare with v2.11.11](https://github.com/nexios-labs/Nexios/compare/v2.11.11...v2.11.12)</small>

### Code Refactoring

- update configuration handling and remove validation ([6af39f2](https://github.com/nexios-labs/Nexios/commit/6af39f29328b56d115bfc557f25e62cbb63daa0f) by techwithdunamix).

## [v2.11.11](https://github.com/nexios-labs/Nexios/releases/tag/v2.11.11) - 2025-10-07

<small>[Compare with v2.11.10](https://github.com/nexios-labs/Nexios/compare/v2.11.10...v2.11.11)</small>

### Features

- add exception handling to router ([0611326](https://github.com/nexios-labs/Nexios/commit/0611326db03f7fa78d7bea9cfd280d8f7c4ff610) by techwithdunamix).
- add request_content_type parameter to routing methods ([af6b43a](https://github.com/nexios-labs/Nexios/commit/af6b43a5cf80543663f165ff30d625538c2493e5) by techwithdunamix).

### Bug Fixes

- improve error handling for existing routes and update documentation ([4472b3c](https://github.com/nexios-labs/Nexios/commit/4472b3ca89d6a9e289e792acb2834557421d58c7) by techwithdunamix).

### Code Refactoring

- optimize exception handling and middleware initialization ([442422c](https://github.com/nexios-labs/Nexios/commit/442422c0660a4268185e4b6bdbfeb74414efed7f) by techwithdunamix).
- move OpenAPI documentation setup to routing  (#192) ([26d2970](https://github.com/nexios-labs/Nexios/commit/26d29707dab3c1d46a446590dce1b78489b572f3) by dunamix 🦄).
- remove duplicate route check in Router ([6df4b60](https://github.com/nexios-labs/Nexios/commit/6df4b6034a90cb7263f37762becef552da7f2563) by techwithdunamix).
- move OpenAPI documentation setup to routing ([e419518](https://github.com/nexios-labs/Nexios/commit/e419518f98da79cb494759d913f3b5385c414cde) by techwithdunamix).
- reorganize BaseRouter and BaseRoute ([9e17a8c](https://github.com/nexios-labs/Nexios/commit/9e17a8c918f899d38196ed28bdfd60eb7add7021) by techwithdunamix).

## [v2.11.10](https://github.com/nexios-labs/Nexios/releases/tag/v2.11.10) - 2025-10-04

<small>[Compare with v2.11.9](https://github.com/nexios-labs/Nexios/compare/v2.11.9...v2.11.10)</small>

## [v2.11.9](https://github.com/nexios-labs/Nexios/releases/tag/v2.11.9) - 2025-10-03

<small>[Compare with v2.11.8](https://github.com/nexios-labs/Nexios/compare/v2.11.8...v2.11.9)</small>

### Features

- enhance WebSocket route registration ([7204db6](https://github.com/nexios-labs/Nexios/commit/7204db65186679a733d28f743e1ac1c441c32c42) by techwithdunamix).

### Bug Fixes

- Fix all pytest warnings ([32e49ca](https://github.com/nexios-labs/Nexios/commit/32e49ca2ad94b4f45e8a448d4ca95a792e9629ce) by dmb225).

### Code Refactoring

- update template context and middleware ([b540d12](https://github.com/nexios-labs/Nexios/commit/b540d12b40b8af1b1700084ecbde5d0e8c2a75a8) by techwithdunamix).

## [v2.11.8](https://github.com/nexios-labs/Nexios/releases/tag/v2.11.8) - 2025-10-02

<small>[Compare with v2.11.7](https://github.com/nexios-labs/Nexios/compare/v2.11.7...v2.11.8)</small>

### Bug Fixes

- add request_content_type parameter to Route and Router classes ([556ae46](https://github.com/nexios-labs/Nexios/commit/556ae46d2120525e381ebc001045dcb5adabcc04) by techwithdunamix).

## [v2.11.7](https://github.com/nexios-labs/Nexios/releases/tag/v2.11.7) - 2025-10-01

<small>[Compare with v2.11.6](https://github.com/nexios-labs/Nexios/compare/v2.11.6...v2.11.7)</small>

### Bug Fixes

-  fix params mismatch ([6c61b4d](https://github.com/nexios-labs/Nexios/commit/6c61b4d70fbf85780d8e5195754928bc8fd54a3f) by techwithdunamix).

## [v2.11.6](https://github.com/nexios-labs/Nexios/releases/tag/v2.11.6) - 2025-10-01

<small>[Compare with v2.11.5](https://github.com/nexios-labs/Nexios/compare/v2.11.5...v2.11.6)</small>

### Features

- add request_content_type parameter to router ([a62877e](https://github.com/nexios-labs/Nexios/commit/a62877edbc6c2a3843a287050a5c1efde4a3cc04) by techwithdunamix).

## [v2.11.5](https://github.com/nexios-labs/Nexios/releases/tag/v2.11.5) - 2025-10-01

<small>[Compare with v2.11.4](https://github.com/nexios-labs/Nexios/compare/v2.11.4...v2.11.5)</small>

### Code Refactoring

- use add_ws_route method directly ([9954d3b](https://github.com/nexios-labs/Nexios/commit/9954d3bf4ab550f2deec496df151720b064a712c) by techwithdunamix).
- remove debug print statement ([048f0e2](https://github.com/nexios-labs/Nexios/commit/048f0e2d6910987ec86b943fa5780a85466c56e4) by techwithdunamix).

## [v2.11.4](https://github.com/nexios-labs/Nexios/releases/tag/v2.11.4) - 2025-09-24

<small>[Compare with v2.11.3](https://github.com/nexios-labs/Nexios/compare/v2.11.3...v2.11.4)</small>

### Bug Fixes

- improve context passing to dependencies ([a2b68fa](https://github.com/nexios-labs/Nexios/commit/a2b68fa4290388c444bfb1d23925dac9cb109c13) by techwithdunamix).
- update context only if middleware provides it ([8dc1712](https://github.com/nexios-labs/Nexios/commit/8dc1712e8f840992c8349893d61c4d7f56e14145) by techwithdunamix).

## [v2.11.3](https://github.com/nexios-labs/Nexios/releases/tag/v2.11.3) - 2025-09-16

<small>[Compare with v2.11.2](https://github.com/nexios-labs/Nexios/compare/v2.11.2...v2.11.3)</small>

### Bug Fixes

- check returned state before updating app state ([3bb457b](https://github.com/nexios-labs/Nexios/commit/3bb457b554059550f8f4b30c50b28cbcd789cff8) by techwithdunamix).

## [v2.11.2](https://github.com/nexios-labs/Nexios/releases/tag/v2.11.2) - 2025-09-14

<small>[Compare with v2.11.1](https://github.com/nexios-labs/Nexios/compare/v2.11.1...v2.11.2)</small>

### Features

- update theme colors and button styles ([bf031df](https://github.com/nexios-labs/Nexios/commit/bf031dfa3e8be8154f5dc66ba9efa4680eed0d06) by techwithdunamix).
- add request_content_type parameter for OpenAPI documentation ([c50e937](https://github.com/nexios-labs/Nexios/commit/c50e9376938fcf38e854869d0457a970f75f62c6) by techwithdunamix).

### Bug Fixes

- remove debug prints and improve UploadedFile class ([acd274b](https://github.com/nexios-labs/Nexios/commit/acd274bcf815a941851ef9e3b859e2da07e2964b) by techwithdunamix).

### Code Refactoring

- update UploadedFile for Pydantic 2 compatibility ([c38b8fc](https://github.com/nexios-labs/Nexios/commit/c38b8fc29f6c0d80d3547cfe87c6dd3f9c11c3b2) by techwithdunamix).
- comment out size checks for parts and files ([c0afe2c](https://github.com/nexios-labs/Nexios/commit/c0afe2c0d28a84094d9aaab0d5b6bc066f641a78) by techwithdunamix).
- extract response processing logic into a separate function ([a00ff80](https://github.com/nexios-labs/Nexios/commit/a00ff80466ef61582651c94871cdd60f2d08d255) by techwithdunamix).

## [v2.11.1](https://github.com/nexios-labs/Nexios/releases/tag/v2.11.1) - 2025-09-10

<small>[Compare with v2.11.0](https://github.com/nexios-labs/Nexios/compare/v2.11.0...v2.11.1)</small>

### Bug Fixes

- remove None type from json response check ([c81d5ec](https://github.com/nexios-labs/Nexios/commit/c81d5ec0eacecf8da6cf79fc13ce75bfcfcc5738) by techwithdunamix).
- update logging method in middleware ([2e086ea](https://github.com/nexios-labs/Nexios/commit/2e086eaf45c0f2f0baed7d46ecd4f88ee3ae92e7) by techwithdunamix).

### Code Refactoring

- replace request-specific logger with module-level logger ([7472232](https://github.com/nexios-labs/Nexios/commit/74722320a7ee69249d8bafcc2fe9388ec71d8003) by techwithdunamix).

## [v2.11.0](https://github.com/nexios-labs/Nexios/releases/tag/v2.11.0) - 2025-09-06

<small>[Compare with v2.10.3](https://github.com/nexios-labs/Nexios/compare/v2.10.3...v2.11.0)</small>

### Features

- add class-based middleware example ([7089943](https://github.com/nexios-labs/Nexios/commit/70899431102dceeec832cecf7fb0495fe241cab1) by techwithdunamix).
- add Pydantic Integration link to sidebar ([cfe5d95](https://github.com/nexios-labs/Nexios/commit/cfe5d9585e97921e1cb23e5c8879d62e4f6966a7) by techwithdunamix).
- update version and logo in readme ([0a9a09b](https://github.com/nexios-labs/Nexios/commit/0a9a09b2322799bb1e1355b21511797727138be0) by techwithdunamix).
- update branding and add documentation styles ([a4b8586](https://github.com/nexios-labs/Nexios/commit/a4b858646be342eeb8bbd29e440ab3dd56ea3805) by techwithdunamix).

### Code Refactoring

- make code more concise and remove unused imports ([861ac1a](https://github.com/nexios-labs/Nexios/commit/861ac1a324d32ac9bfd0a834ef482396a596b295) by techwithdunamix).
- update database examples for async support ([89b0a26](https://github.com/nexios-labs/Nexios/commit/89b0a2649adf074d12ff8a8de7680083075f1f2d) by techwithdunamix).
- update route parameter handling in example ([690d386](https://github.com/nexios-labs/Nexios/commit/690d386d8eb529342aae37ed3ef2cbad4294729e) by techwithdunamix).

## [v2.10.3](https://github.com/nexios-labs/Nexios/releases/tag/v2.10.3) - 2025-08-28

<small>[Compare with v2.10.2](https://github.com/nexios-labs/Nexios/compare/v2.10.2...v2.10.3)</small>

### Features

- add global state support ([d30cc4e](https://github.com/nexios-labs/Nexios/commit/d30cc4ed71ee66120d6e5cb3a362afb28c395bcf) by techwithdunamix).
- enhance websocket route addition and update docs ([df17a76](https://github.com/nexios-labs/Nexios/commit/df17a7600ea876e264f24e0e03b3b44f37839a4d) by techwithdunamix).

### Bug Fixes

- correct logging_middleware function parameters ([d8705b9](https://github.com/nexios-labs/Nexios/commit/d8705b999e15bd2770c1b54ea33189c5a0b807c9) by techwithdunamix).

## [v2.10.2](https://github.com/nexios-labs/Nexios/releases/tag/v2.10.2) - 2025-08-16

<small>[Compare with v2.10.1](https://github.com/nexios-labs/Nexios/compare/v2.10.1...v2.10.2)</small>

### Bug Fixes

- add Callable import to jwt backend ([694ad92](https://github.com/nexios-labs/Nexios/commit/694ad92b3ce138465cc0c99743df6c53a52ddc6b) by techwithdunamix).
- change request.json() to request.json ([9b1524b](https://github.com/nexios-labs/Nexios/commit/9b1524bb0ac72dc66c56028fb0063f3bf38560f7) by techwithdunamix).

## [v2.10.1](https://github.com/nexios-labs/Nexios/releases/tag/v2.10.1) - 2025-08-07

<small>[Compare with v2.10.0](https://github.com/nexios-labs/Nexios/compare/v2.10.0...v2.10.1)</small>

### Bug Fixes

- improve CSRF protection and token handling ([e7c910f](https://github.com/nexios-labs/Nexios/commit/e7c910fb47730f0a56a651cfab3b728766bdbb87) by techwithdunamix).
- fix routing docs orgnization ([4f0cfe4](https://github.com/nexios-labs/Nexios/commit/4f0cfe45c363eb63a9cf5d860f8a0cf4e893dec1) by techwithdunamix).
-  fix websockets documentation on channels ([bcdadd4](https://github.com/nexios-labs/Nexios/commit/bcdadd4ab434fea9282cdfe981a64bb0fb34968b) by techwithdunamix).

## [v2.10.0](https://github.com/nexios-labs/Nexios/releases/tag/v2.10.0) - 2025-08-02

<small>[Compare with v2.9.3](https://github.com/nexios-labs/Nexios/compare/v2.9.3...v2.10.0)</small>

### Features

- introduce new has_permission decorator ([4461729](https://github.com/nexios-labs/Nexios/commit/4461729214d969b5cf24d26a4238d565de4165f5) by techwithdunamix).
- allow set_config to auto initalize MakeConfig class when kwargs is passed in ([b728eb9](https://github.com/nexios-labs/Nexios/commit/b728eb97cfa6957fe13e5e26e9a12a325e967b5b) by techwithdunamix).

### Bug Fixes

- fix issues in docs ([335dbde](https://github.com/nexios-labs/Nexios/commit/335dbde1b2fa8150ba197f1892cd0952cf4c2584) by techwithdunamix).

## [v2.9.3](https://github.com/nexios-labs/Nexios/releases/tag/v2.9.3) - 2025-07-30

<small>[Compare with v2.9.2](https://github.com/nexios-labs/Nexios/compare/v2.9.2...v2.9.3)</small>

### Features

- Add multipart form data support ([cf8e9bd](https://github.com/nexios-labs/Nexios/commit/cf8e9bd9a8ef73f4bb35227b850f92f17aafe7d4) by techwithdunamix).

### Code Refactoring

- clean dependecy ([c7f0b90](https://github.com/nexios-labs/Nexios/commit/c7f0b90ea438ee9cde70555f8e57adaf0903223a) by techwithdunamix).
- refactor auth docs ([7c8681d](https://github.com/nexios-labs/Nexios/commit/7c8681d84419f27abf7b79f603ab935acdb34fe6) by techwithdunamix).

## [v2.9.2](https://github.com/nexios-labs/Nexios/releases/tag/v2.9.2) - 2025-07-28

<small>[Compare with v2.9.1](https://github.com/nexios-labs/Nexios/compare/v2.9.1...v2.9.2)</small>

### Features

- enhance CSRF protection and documentation ([fd8c74e](https://github.com/nexios-labs/Nexios/commit/fd8c74e7ac89a873a146931f43caa46f69b50847) by techwithdunamix).

## [v2.9.1](https://github.com/nexios-labs/Nexios/releases/tag/v2.9.1) - 2025-07-27

<small>[Compare with v2.9.0](https://github.com/nexios-labs/Nexios/compare/v2.9.0...v2.9.1)</small>

### Bug Fixes

- clean up formatting in index.md and remove unnecessary whitespace ([0f3a05e](https://github.com/nexios-labs/Nexios/commit/0f3a05e6098f24f45aaa85d1d5ae7665f985971f) by techwithdunamix).
- remove duplicate entry for granian in requirements.txt ([c4cca7e](https://github.com/nexios-labs/Nexios/commit/c4cca7e6319ef5ff9e1430357f5004654020e01f) by techwithdunamix).

## [v2.9.0](https://github.com/nexios-labs/Nexios/releases/tag/v2.9.0) - 2025-07-23

<small>[Compare with v2.8.6](https://github.com/nexios-labs/Nexios/compare/v2.8.6...v2.9.0)</small>

### Features

- update global dependency test to use custom error handling ([a152ac1](https://github.com/nexios-labs/Nexios/commit/a152ac1ef62bf6a863f6eaa845d6c50d280d77ce) by techwithdunamix).
- update README and main application structure, remove unused files, and add new index template ([7ee5e9a](https://github.com/nexios-labs/Nexios/commit/7ee5e9ac5b7647c1c461b4e07f43af3ee37729fb) by techwithdunamix).
- add support for dependency injection error handling and global dependencies in tests ([15c97d1](https://github.com/nexios-labs/Nexios/commit/15c97d12838b6ab5f37950b0da78691b462fc23e) by techwithdunamix).
- enhance inject_dependencies to support context and app dependency injection ([740fe5f](https://github.com/nexios-labs/Nexios/commit/740fe5f384beb7123bd31c7c9288458f2ce95cc5) by techwithdunamix).
- enhance Context initialization with additional parameters for improved middleware functionality ([5948752](https://github.com/nexios-labs/Nexios/commit/5948752c1af97fc3f643d448932357c7bba0cd5f) by techwithdunamix).

### Bug Fixes

- ensure proper handling of async and sync handlers in inject_dependencies function ([9c16653](https://github.com/nexios-labs/Nexios/commit/9c166533f616b0f7b96fa92f431c5596335ae8ed) by techwithdunamix).
- update user type annotation from User to BaseUser in Context class ([0625030](https://github.com/nexios-labs/Nexios/commit/06250303bd40dded62b185a6ac42d5aa0983358c) by techwithdunamix).

### Code Refactoring

- simplify dependency injection in Router class ([4afcc83](https://github.com/nexios-labs/Nexios/commit/4afcc832aea236aa05383a78406e612f4b157f66) by techwithdunamix).

## [v2.8.6](https://github.com/nexios-labs/Nexios/releases/tag/v2.8.6) - 2025-07-18

<small>[Compare with v2.8.5](https://github.com/nexios-labs/Nexios/compare/v2.8.5...v2.8.6)</small>

## [v2.8.5](https://github.com/nexios-labs/Nexios/releases/tag/v2.8.5) - 2025-07-18

<small>[Compare with v2.8.4](https://github.com/nexios-labs/Nexios/compare/v2.8.4...v2.8.5)</small>

## [v2.8.4](https://github.com/nexios-labs/Nexios/releases/tag/v2.8.4) - 2025-07-18

<small>[Compare with v2.8.3](https://github.com/nexios-labs/Nexios/compare/v2.8.3...v2.8.4)</small>

### Bug Fixes

- improve CSRF token handling and enhance security middleware defaults ([1164bc9](https://github.com/nexios-labs/Nexios/commit/1164bc92072722f08ec58984193ed8a1685d5cbd) by techwithdunamix).

## [v2.8.3](https://github.com/nexios-labs/Nexios/releases/tag/v2.8.3) - 2025-07-18

<small>[Compare with v2.8.2](https://github.com/nexios-labs/Nexios/compare/v2.8.2...v2.8.3)</small>

### Bug Fixes

- initialize _session_cache in BaseSessionInterface constructor ([ebf905c](https://github.com/nexios-labs/Nexios/commit/ebf905cd10f8782316987919101f78027bfa8ad4) by techwithdunamix).

## [v2.8.2](https://github.com/nexios-labs/Nexios/releases/tag/v2.8.2) - 2025-07-18

<small>[Compare with v2.8.0](https://github.com/nexios-labs/Nexios/compare/v2.8.0...v2.8.2)</small>

### Features

- add virtualenv setup step in release workflow ([6914016](https://github.com/nexios-labs/Nexios/commit/6914016cbf22dd859c4cc53fd05b3782f6893dfc) by techwithdunamix).
- implement new tag creation workflow for releases ([8da3c1b](https://github.com/nexios-labs/Nexios/commit/8da3c1b6670406e07d24708f8d10e959e0a1b9e5) by techwithdunamix).

### Bug Fixes

- update build command in release workflow ([1e27d0d](https://github.com/nexios-labs/Nexios/commit/1e27d0d1f1405124e9d917ab377fa6cd892d79b3) by techwithdunamix).

### Code Refactoring

- simplify release workflow by removing deprecated steps ([3d741ed](https://github.com/nexios-labs/Nexios/commit/3d741ed48b1f6ab2c5af1163b6c2fb17eb9a2693) by techwithdunamix).

## [v2.8.0](https://github.com/nexios-labs/Nexios/releases/tag/v2.8.0) - 2025-07-15

<small>[Compare with v2.7.0](https://github.com/nexios-labs/Nexios/compare/v2.7.0...v2.8.0)</small>

### Features

- enhance dependency injection documentation ([819db75](https://github.com/nexios-labs/Nexios/commit/819db751d04267799d9820e9e9d4bf8bfd0508dd) by techwithdunamix).
- add support for app-level and router-level dependencies ([8a1e3b4](https://github.com/nexios-labs/Nexios/commit/8a1e3b44765e26fbc38a4aa37ab044430dee324d) by techwithdunamix).
- add support for synchronous and asynchronous generator dependencies ([2910caf](https://github.com/nexios-labs/Nexios/commit/2910caf51e5e8422c680b42bb95344ddec9da397) by techwithdunamix).
- enhance run command to support custom commands as lists or strings ([5eca2f6](https://github.com/nexios-labs/Nexios/commit/5eca2f6db801a29bd928ed90355d6696b7973c0a) by techwithdunamix).

### Bug Fixes

- update release and triage workflows for consistency ([62335c4](https://github.com/nexios-labs/Nexios/commit/62335c451f48d1e450a3e8184e412b090203cc28) by techwithdunamix).
- resolve issues with dependency merging in Router class ([09735cf](https://github.com/nexios-labs/Nexios/commit/09735cf940e754791bd4b599c88bbc236b9090b7) by techwithdunamix).
- add TYPE_CHECKING import for improved type hinting in _builder.py ([8392fe9](https://github.com/nexios-labs/Nexios/commit/8392fe92fa5c51243c4ca9970fadf8134023724e) by techwithdunamix).

## [v2.7.0](https://github.com/nexios-labs/Nexios/releases/tag/v2.7.0) - 2025-07-09

<small>[Compare with v2.6.2](https://github.com/nexios-labs/Nexios/compare/v2.6.2...v2.7.0)</small>

### Features

- enhance templating system with request context support ([88d05e0](https://github.com/nexios-labs/Nexios/commit/88d05e022d0d309b91d055c18a2ffab251095397) by techwithdunamix).

### Bug Fixes

- improve session handling and error logging ([f6fa900](https://github.com/nexios-labs/Nexios/commit/f6fa900799e1dc67b1ebe2d89e898e56d76cb6b0) by techwithdunamix).
- add version bump test comment to main module ([bbebd50](https://github.com/nexios-labs/Nexios/commit/bbebd50382e3a9082b9d2399758f993441141e9a) by techwithdunamix).

## [v2.6.2](https://github.com/nexios-labs/Nexios/releases/tag/v2.6.2) - 2025-07-04

<small>[Compare with v2.6.1](https://github.com/nexios-labs/Nexios/compare/v2.6.1...v2.6.2)</small>

### Features

- enhance configuration management docs by adding support for .env files, enabling environment-specific settings, and improving validation for required configuration keys ([956ca50](https://github.com/nexios-labs/Nexios/commit/956ca50dd5b6b0863fadfe4fcb81eb0a8280e33f) by techwithdunamix).

### Code Refactoring

- simplify app.run() method and add development warning ([6b7fcdc](https://github.com/nexios-labs/Nexios/commit/6b7fcdc60e2d3598da63ded0efa2f8daac42613f) by techwithdunamix).
- remove unused imports from ping, shell, and urls command files to clean up code ([6c87e7f](https://github.com/nexios-labs/Nexios/commit/6c87e7f0b5042cd44d902a4af58345d7222452ef) by techwithdunamix).

## [v2.6.1](https://github.com/nexios-labs/Nexios/releases/tag/v2.6.1) - 2025-07-03

<small>[Compare with v2.6.0](https://github.com/nexios-labs/Nexios/compare/v2.6.0...v2.6.1)</small>

### Features

- enhance Nexios CLI commands to support optional configuration loading, improve error handling, and update command help descriptions for clarity ([0328566](https://github.com/nexios-labs/Nexios/commit/0328566d491dff65f4e7d6fc123b1b1fb488c5e7) by techwithdunamix).
- implement configuration file support for Nexios CLI, allowing app and server options to be defined in `nexios.config.py`, and enhance command functionality to load configurations seamlessly ([57cd0d7](https://github.com/nexios-labs/Nexios/commit/57cd0d7d0be6f3587910f2ed7e12705b7cea2d3e) by techwithdunamix).
- add 'URL Configuration' section to documentation and enhance CLI guide with new commands for listing URLs and checking route existence ([2886dbb](https://github.com/nexios-labs/Nexios/commit/2886dbba99ffa250d3fd4f93a5ec974ac53103a5) by techwithdunamix).
- enhance app loading by adding auto-search for nexios.config.py and .nexioscli files in the current directory ([5d103e7](https://github.com/nexios-labs/Nexios/commit/5d103e7d885238eb5c2012dc4f625d8d0fa3daef) by techwithdunamix).
- add CLI commands to list registered URLs and ping routes in the Nexios application, with support for loading app instances from module paths or config files ([30cf2eb](https://github.com/nexios-labs/Nexios/commit/30cf2eba3ec0af72ac34344c4b7c43896b30fe45) by techwithdunamix).

### Code Refactoring

- clean up imports in CLI command files and remove unused type hints from ping, shell, and urls modules ([7daacfd](https://github.com/nexios-labs/Nexios/commit/7daacfdd5104515969073f333981b9f2d189a9f6) by techwithdunamix).
- update imports in shell.py to suppress linting warnings and clean up exports in utils module ([668f526](https://github.com/nexios-labs/Nexios/commit/668f52639358484a7e8f37a96b4452be719793d1) by techwithdunamix).
- remove unused 'normalize_url_path' from exports in utils module ([8a7c5fb](https://github.com/nexios-labs/Nexios/commit/8a7c5fbc36c5c987b5d5cd90d53ea7617d2c658d) by techwithdunamix).
- simplify CLI structure by removing unused utility and validation functions, consolidating command implementations, and enhancing app loading from main module ([fb28f17](https://github.com/nexios-labs/Nexios/commit/fb28f173357bb3c305209d98a77204d320c6a7d5) by techwithdunamix).

## [v2.6.0](https://github.com/nexios-labs/Nexios/releases/tag/v2.6.0) - 2025-06-30

<small>[Compare with v2.5.3](https://github.com/nexios-labs/Nexios/compare/v2.5.3...v2.6.0)</small>

## [v2.5.3](https://github.com/nexios-labs/Nexios/releases/tag/v2.5.3) - 2025-06-30

<small>[Compare with v2.5.2](https://github.com/nexios-labs/Nexios/compare/v2.5.2...v2.5.3)</small>

### Features

- enhance server startup by adding support for granian and uvicorn with temporary entry point creation ([53e5c80](https://github.com/nexios-labs/Nexios/commit/53e5c8003d6be55a47eca12ba5590657bf6319cd) by techwithdunamix).

### Bug Fixes

- refine CORS preflight request test by updating allowed methods and headers to match middleware behavior ([be4dc12](https://github.com/nexios-labs/Nexios/commit/be4dc12626da31b71bb249c06fae2e0853f92b0d) by techwithdunamix).
- update CORS middleware to handle preflight requests more robustly by refining header management and allowing dynamic header responses ([55ca14f](https://github.com/nexios-labs/Nexios/commit/55ca14f391e0da584b1a31075878d49b4e546f3e) by techwithdunamix).

### Code Refactoring

- remove main function and update version constraints for pytest in uv.lock ([e55c5e0](https://github.com/nexios-labs/Nexios/commit/e55c5e08570d994e36a00d4bebafc965f5f028af) by techwithdunamix).

## [v2.5.2](https://github.com/nexios-labs/Nexios/releases/tag/v2.5.2) - 2025-06-29

<small>[Compare with v2.5.1](https://github.com/nexios-labs/Nexios/compare/v2.5.1...v2.5.2)</small>

### Features

- enhance NexiosApp.run method to support Granian server ([a218b0b](https://github.com/nexios-labs/Nexios/commit/a218b0b6dadf653ff74831970be40af345d90aac) by techwithdunamix).

### Bug Fixes

- correct spelling of 'exclude_from_schema' in application and routing modules ([98d2e24](https://github.com/nexios-labs/Nexios/commit/98d2e24bc1849dfcc60d7789278a7570a6793d6c) by techwithdunamix).
- update header encoding in StreamingResponse for compatibility ([8cac5de](https://github.com/nexios-labs/Nexios/commit/8cac5de6390d8fba1dd54839396e4e1fedd5a51c) by techwithdunamix).
- remove duplicate import of NexiosApp in day22 index documentation ([0ebdbb3](https://github.com/nexios-labs/Nexios/commit/0ebdbb36bacf8e6d58d5a1af14cd638dd1e214c2) by techwithdunamix).

### Code Refactoring

- update error handling UI and enhance JavaScript functionality ([4a76d92](https://github.com/nexios-labs/Nexios/commit/4a76d9268ee9b4dd1804912a66f241a931ea7e47) by techwithdunamix).

## [v2.5.1](https://github.com/nexios-labs/Nexios/releases/tag/v2.5.1) - 2025-06-26

<small>[Compare with v2.5.0](https://github.com/nexios-labs/Nexios/compare/v2.5.0...v2.5.1)</small>

### Features

- add request verification and enhance locust tests ([2a50d82](https://github.com/nexios-labs/Nexios/commit/2a50d826dd4c7c5c09ef1545d056c1047a292119) by techwithdunamix).
- introduce context-aware dependency injection system for request-scoped data access ([a52ea4f](https://github.com/nexios-labs/Nexios/commit/a52ea4f81eceeb6b1d69f91d478a84a6596233f5) by techwithdunamix).

### Bug Fixes

- correct indentation in release workflow for changelog generation step ([0fe3595](https://github.com/nexios-labs/Nexios/commit/0fe35957aab1d7f561958e9728430b84776e5023) by techwithdunamix).

## [v2.5.0](https://github.com/nexios-labs/Nexios/releases/tag/v2.5.0) - 2025-06-21

<small>[Compare with v2.4.14](https://github.com/nexios-labs/Nexios/compare/v2.4.14...v2.5.0)</small>

### Bug Fixes

- allow optional status code in response methods and default to instance status code ([e4f1b15](https://github.com/nexios-labs/Nexios/commit/e4f1b15151304e65e914541ce2e46ce40324ad6c) by techwithdunamix).

## [v2.4.14](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.14) - 2025-06-20

<small>[Compare with v2.4.13](https://github.com/nexios-labs/Nexios/compare/v2.4.13...v2.4.14)</small>

### Bug Fixes

- handle directory initialization and path formatting in StaticFiles class for improved file serving, closes #136 ([13c9892](https://github.com/nexios-labs/Nexios/commit/13c98923d1a0d4532957943e1d4ddd78599c797e) by techwithdunamix).

## [v2.4.13](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.13) - 2025-06-18

<small>[Compare with v2.4.12](https://github.com/nexios-labs/Nexios/compare/v2.4.12...v2.4.13)</small>

### Bug Fixes

- update endpoint path formatting to simplify parameter representation in application.py ([617bd7b](https://github.com/nexios-labs/Nexios/commit/617bd7b6a03c9ff90a26eb49ac86f7e576e80a38) by techwithdunamix).
- resolve merge conflict by removing unnecessary conflict markers in client.py ([2c6e1b2](https://github.com/nexios-labs/Nexios/commit/2c6e1b213cb1dae1c0704ba7c0b18d0e432a210e) by techwithdunamix).
- reorder import statements for improved organization in structs.py ([a57c5cb](https://github.com/nexios-labs/Nexios/commit/a57c5cb656bbbc058fa79f723bb8adf27d1342ff) by techwithdunamix).

### Code Refactoring

- improve code clarity by renaming variables and enhancing type hinting across multiple files ([657743e](https://github.com/nexios-labs/Nexios/commit/657743e854629f43ac255bca08759cea1257fb81) by techwithdunamix).
- remove unused imports across various files to clean up the codebase ([c622e17](https://github.com/nexios-labs/Nexios/commit/c622e1781024404508357eef7751318d7df056f6) by techwithdunamix).
- update authentication handling and file upload method in API examples ([f24af31](https://github.com/nexios-labs/Nexios/commit/f24af316c96ab19bd86bd20e6cf0649af8881c6d) by techwithdunamix).

## [v2.4.12](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.12) - 2025-06-15

<small>[Compare with v2.4.11](https://github.com/nexios-labs/Nexios/compare/v2.4.11...v2.4.12)</small>

## [v2.4.11](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.11) - 2025-06-15

<small>[Compare with v2.4.10](https://github.com/nexios-labs/Nexios/compare/v2.4.10...v2.4.11)</small>

## [v2.4.10](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.10) - 2025-06-14

<small>[Compare with v2.4.9](https://github.com/nexios-labs/Nexios/compare/v2.4.9...v2.4.10)</small>

### Bug Fixes

- update GitHub Actions workflow to run Tox with uv ([c6c5a83](https://github.com/nexios-labs/Nexios/commit/c6c5a83721beec1482a9a6eb17919f126d29dcdd) by techwithdunamix).
- address minor bugs in middleware handling and improve error logging for better debugging ([68e8055](https://github.com/nexios-labs/Nexios/commit/68e805567f9cfa4cabc8bb11c834250a67bbf221) by techwithdunamix).

### Code Refactoring

- remove .editorconfig and package-lock.json, update pyproject.toml for Hatchling, enhance requirements.txt, and modify GitHub Actions workflow for uv; adjust middleware usage in application and tests ([754394f](https://github.com/nexios-labs/Nexios/commit/754394ffa98d4c32a11b27ee7e87521061debc47) by techwithdunamix).
- consolidate middleware imports and update related references across documentation and codebase ([95b5dcc](https://github.com/nexios-labs/Nexios/commit/95b5dcc1e3cccd871a0bfe6fd213b49c2cb51a86) by techwithdunamix).

## [v2.4.9](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.9) - 2025-06-06

<small>[Compare with v2.4.8](https://github.com/nexios-labs/Nexios/compare/v2.4.8...v2.4.9)</small>

### Features

- enhance API documentation routes with customizable URLs for Swagger and ReDoc; add ReDoc UI generation ([d11085c](https://github.com/nexios-labs/Nexios/commit/d11085c20886429b2eccd6f4d50e5a243eda8a1b) by techwithdunamix).

### Code Refactoring

- update constructor to accept optional config and kwargs, merging them with defaults for improved flexibility ([850fe78](https://github.com/nexios-labs/Nexios/commit/850fe78443acf92f1aacb76bb3cafb35160138ca) by techwithdunamix).

## [v2.4.8](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.8) - 2025-06-05

<small>[Compare with v2.4.7](https://github.com/nexios-labs/Nexios/compare/v2.4.7...v2.4.8)</small>

### Features

- add templating guide link in documentation; refactor TemplateEngine for improved configuration handling and error management; update TemplateContextMiddleware for better type hints; remove unused utility functions ([5f7138d](https://github.com/nexios-labs/Nexios/commit/5f7138dc3ac62ad06f66bcf4e13d9d7bc9848efe) by techwithdunamix).
- add properties and methods for enhanced request handling ([0592629](https://github.com/nexios-labs/Nexios/commit/05926297b9431fe8d474ee17edd81528249db8ca) by techwithdunamix).
- add 'Concurrency Utilities' section to the guide and update dependency metadata ([6404256](https://github.com/nexios-labs/Nexios/commit/6404256b995709929c5d12917a1d93ed202291ce) by techwithdunamix).

### Bug Fixes

- restore __repr__ method in MakeConfig; add warning for missing secret_key in session handling ([49a6867](https://github.com/nexios-labs/Nexios/commit/49a6867f6f8104eea5a16243719a659e448f2a44) by techwithdunamix).
- improve clarity in concurrency guide and update examples for better understanding ([d790c96](https://github.com/nexios-labs/Nexios/commit/d790c967282b3bca49d550dc05c773f92c123cb9) by techwithdunamix).
- correct import paths from 'cuncurrency' to 'concurrency' and remove deprecated concurrency utility file ([32863d9](https://github.com/nexios-labs/Nexios/commit/32863d9d882ade12ffd7c80289247c6c21f0d2d1) by techwithdunamix).
- update markdown configuration and correct file data handling in concurrency guide ([f3a85c2](https://github.com/nexios-labs/Nexios/commit/f3a85c24d9b49ae73aa97558f4f636448f49b9e3) by techwithdunamix).
- correct image upload handling in concurrency guide ([1e2230d](https://github.com/nexios-labs/Nexios/commit/1e2230db686e0f260398b26d0d0399cf629bc933) by techwithdunamix).

### Code Refactoring

- correct async function calls in request handling examples chore: remove outdated ASGI and async Python documentation ([1eb836a](https://github.com/nexios-labs/Nexios/commit/1eb836a0ea118e094d66591afe7f2186bec60ce3) by techwithdunamix).
- remove deprecated error handling test for concurrency utilities ([1e99ab4](https://github.com/nexios-labs/Nexios/commit/1e99ab4a2ed14542c6d70e40d0eea6e0d6b8cc1f) by techwithdunamix).
- enhance dependency injection to support synchronous and asynchronous handlers ([ae3c6ce](https://github.com/nexios-labs/Nexios/commit/ae3c6cefa693214e6641b6896c92410e870522f5) by techwithdunamix).
- move utility functions to a new location and remove deprecated files ([7b3a8c4](https://github.com/nexios-labs/Nexios/commit/7b3a8c4e3573e28615b35969934dcb86e63e3ae3) by techwithdunamix).

## [v2.4.7](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.7) - 2025-06-01

<small>[Compare with v2.4.6](https://github.com/nexios-labs/Nexios/compare/v2.4.6...v2.4.7)</small>

### Features

- add test for adding route with path parameters ([223ada8](https://github.com/nexios-labs/Nexios/commit/223ada8628e15adc382653a22fd6488f22575b37) by techwithdunamix).
- enhance add_route method to support optional path and handler parameters ([999eefe](https://github.com/nexios-labs/Nexios/commit/999eefe6a9383a266caa20f3da508507ecada4bc) by techwithdunamix).
- redesign SVG icon with gradients, shadows, and new shapes ([caba18c](https://github.com/nexios-labs/Nexios/commit/caba18cf56221949cbdac6cba6e1495b53c82514) by techwithdunamix).

### Bug Fixes

- cast session to BaseSessionInterface for type safety ([3a462a3](https://github.com/nexios-labs/Nexios/commit/3a462a373de883f8533c13f68eb286f198c8bdc8) by techwithdunamix).
- restore _setup_openapi call in handle_lifespan method ([076048f](https://github.com/nexios-labs/Nexios/commit/076048fdb9ee8554b852751f8bd9a1ef258e1918) by techwithdunamix).
- streamline session configuration access and improve file path handling ([f963f3e](https://github.com/nexios-labs/Nexios/commit/f963f3e4a492776cd2e9b89ac4424ee2d3b5d718) by techwithdunamix).
- improve session configuration handling with getattr for safer access ([9d48c3b](https://github.com/nexios-labs/Nexios/commit/9d48c3ba575c0d473e3e83681573fe8772a4d531) by techwithdunamix).
- update support icon URL to point to the new documentation site ([44c2d6a](https://github.com/nexios-labs/Nexios/commit/44c2d6a855b3982c52be2a9e5cfeeaeb2fbd6d99) by techwithdunamix).

### Code Refactoring

- rename __middleware to _middleware and update imports ([b5acb31](https://github.com/nexios-labs/Nexios/commit/b5acb31f860fa4c53187bd65490ecbd19e90beec) by techwithdunamix).

## [v2.4.6](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.6) - 2025-05-30

<small>[Compare with v2.4.5](https://github.com/nexios-labs/Nexios/compare/v2.4.5...v2.4.6)</small>

### Bug Fixes

- implement OpenAPI setup during application shutdown and improve JSON property typing ([9fa250f](https://github.com/nexios-labs/Nexios/commit/9fa250fe159f2f1ed00d2445fa3f2bdd0fbaad63) by techwithdunamix).

## [v2.4.5](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.5) - 2025-05-27

<small>[Compare with v2.4.4](https://github.com/nexios-labs/Nexios/compare/v2.4.4...v2.4.5)</small>

### Bug Fixes

- Remove debug print statements and clean up lifespan event handling ([477fd63](https://github.com/nexios-labs/Nexios/commit/477fd6392ca831409398194fcfbfacc00243fcc5) by techwithdunamix).
- Remove unnecessary method call in lifespan event handling ([9a90cef](https://github.com/nexios-labs/Nexios/commit/9a90cef6872bfcf0bc7bef2df5d90baf297d9cff) by techwithdunamix).
- Improve error logging in lifespan event handling and clean up whitespace ([a7cb24c](https://github.com/nexios-labs/Nexios/commit/a7cb24cfad8219b48261839b2827220d4145f322) by techwithdunamix).

## [v2.4.4](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.4) - 2025-05-25

<small>[Compare with v2.4.3](https://github.com/nexios-labs/Nexios/compare/v2.4.3...v2.4.4)</small>

### Features

- implement form parsing and routing enhancements with new internal modules ([0a3f3ac](https://github.com/nexios-labs/Nexios/commit/0a3f3ac7cbe46b0acaf78c9c5d634052a3bfe495) by dunamix).

### Bug Fixes

- Set default path for Group initialization and add test for external ASGI app integration ([25e1a87](https://github.com/nexios-labs/Nexios/commit/25e1a8785698487c10543a08d90498dc50c44ebc) by dunamix).
- Updates route handling to support both Routes and BaseRoute instances ([758808d](https://github.com/nexios-labs/Nexios/commit/758808deb533971d2377f5cc09e374b22b63a92e) by dunamix).
- improve error message for client disconnection in ASGIRequestResponseBridge ([21ab8d7](https://github.com/nexios-labs/Nexios/commit/21ab8d7e3ad97bc5fa024bd430c09676f77bc6d7) by dunamix).

### Code Refactoring

- Remove trailing slash from Group path initialization and clean up unused tests ([07b4e02](https://github.com/nexios-labs/Nexios/commit/07b4e02bddeb8a692fde4d21ee31aedfcb587243) by dunamix).
- Improve type hints and path handling in Group class ([25bb14c](https://github.com/nexios-labs/Nexios/commit/25bb14c997e38683bd88b65f6ed7b3a2ef6af176) by dunamix).
- reorganize middleware structure and update routing to use new middleware definitions ([bfe82e6](https://github.com/nexios-labs/Nexios/commit/bfe82e679cbd553ed8991c08abce8149af66c5c0) by dunamix).

## [v2.4.3](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.3) - 2025-05-20

<small>[Compare with v2.4.2](https://github.com/nexios-labs/Nexios/compare/v2.4.2...v2.4.3)</small>

### Features

- enhance server error template with improved layout and request information section ([b1bc951](https://github.com/nexios-labs/Nexios/commit/b1bc951e92bb00c707b0c1f1ef74e8cf3d9a1e74) by dunamix).
- add handler hooks documentation and implement before/after request decorators ([5aa3038](https://github.com/nexios-labs/Nexios/commit/5aa30380110433f416a4ad147f3b669a107d2c07) by dunamix).
- add examples for authentication, exception handling, middleware, request inputs, responses, and routing ([dfd1c84](https://github.com/nexios-labs/Nexios/commit/dfd1c84bfa26ff54b2ac59d5a6d59777c70bc6b7) by dunamix).
- add JWT and API key authentication backends ([3c33103](https://github.com/nexios-labs/Nexios/commit/3c33103dddce6ff0f96271956e9b97ed3fb2ee65) by dunamix).

### Bug Fixes

- update workflow to ignore pushes to main branch ([196898d](https://github.com/nexios-labs/Nexios/commit/196898da56d693e91c76f9f8db91c70d3bc41538) by dunamix).
- update typing SVG font and styling in README ([eba82f8](https://github.com/nexios-labs/Nexios/commit/eba82f89ca3ee5b95fc68870f295f2b5eb7032b7) by dunamix).
- correct heading formatting in getting started guide ([88a2f9e](https://github.com/nexios-labs/Nexios/commit/88a2f9e4624fa4b810cb49c67fb9ba1f6955bec8) by dunamix).

## [v2.4.2](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.2) - 2025-05-15

<small>[Compare with v2.4.1](https://github.com/nexios-labs/Nexios/compare/v2.4.1...v2.4.2)</small>

### Features

- add File Router guide to documentation and update config for navigation ([6857813](https://github.com/nexios-labs/Nexios/commit/6857813cdcaaaedc567115334ccdea64e9c96fe0) by dunamix).
- add ASGI and Async Python guides to documentation ([a20ff88](https://github.com/nexios-labs/Nexios/commit/a20ff888c6448bebfa0910c3aa20189156631641) by dunamix).

### Bug Fixes

- improve JWT import error handling and raise informative exceptions ([3f4e386](https://github.com/nexios-labs/Nexios/commit/3f4e386b2c0c318693a1d75c1bbd19164b3bc50c) by dunamix).
- update project description for clarity on performance features ([91acec4](https://github.com/nexios-labs/Nexios/commit/91acec4c4042a2faf9b89874d117b5b1a67aa80e) by dunamix).
- clean up code formatting and add deprecation warning for get_application ([293f1ad](https://github.com/nexios-labs/Nexios/commit/293f1ad729fe23ef50f117e14b82ce05880db4a5) by dunamix).
- improve comments and update PyPI publishing step in release workflow ([d9375cd](https://github.com/nexios-labs/Nexios/commit/d9375cdbc3f8d97900d3cc1edb1fa6bc989620f4) by dunamix).

### Code Refactoring

- update VitePress config for improved structure and clarity ([538e6b0](https://github.com/nexios-labs/Nexios/commit/538e6b0758d374e59537288b572d5a4f82a36131) by dunamix).
- enhance method detection in APIView for dynamic method registration ([74e0f13](https://github.com/nexios-labs/Nexios/commit/74e0f13d294bcd7e02a2ee6ab678bb4afef77193) by dunamix).
- replace get_application with NexiosApp and add startup/shutdown hooks ([be9d751](https://github.com/nexios-labs/Nexios/commit/be9d751ebbbaa7a9eb710626da42b62e62a98093) by dunamix).

## [v2.4.1](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.1) - 2025-05-14

<small>[Compare with v2.4.0](https://github.com/nexios-labs/Nexios/compare/v2.4.0...v2.4.1)</small>

### Features

- add GitHub Actions workflow for automated release on tag push ([7c945c3](https://github.com/nexios-labs/Nexios/commit/7c945c37e025b2cfcf4d8904c3620f7c443c0746) by dunamix).
- add base_app reference to scope for improved access in request handling ([84c2c23](https://github.com/nexios-labs/Nexios/commit/84c2c23714dde850dd35349f0b7dc0c7ce7566e9) by dunamix).

### Bug Fixes

- remove redundant phrasing in framework description for clarity ([f50ab97](https://github.com/nexios-labs/Nexios/commit/f50ab9748246f7892a67ba5fc68dcdb5ea78aad4) by dunamix).
- simplify installation instructions by removing broken examples ([2d61ee4](https://github.com/nexios-labs/Nexios/commit/2d61ee4f58b936e1ee0e70c8b01002510752089d) by dunamix).
- correct GitHub link in VitePress config for accuracy ([acab1ba](https://github.com/nexios-labs/Nexios/commit/acab1ba6d1478e57f005c8136964aeec17f06d7d) by dunamix).
- update version badge from 2.4.0rc1 to 2.4.0 for consistency ([332d0d4](https://github.com/nexios-labs/Nexios/commit/332d0d4adb352d8a0e05ea7509760b5fa71a00b0) by dunamix).
- move remove_header method to improve clarity ([9731d85](https://github.com/nexios-labs/Nexios/commit/9731d85378b0c52e4582d9377e1e289356d08534) by dunamix).
- inherit BaseRouter in Router and WSRouter classes for consistency ([f63a848](https://github.com/nexios-labs/Nexios/commit/f63a848abdb5de9d17ef4e805956b1ec1023974b) by dunamix).
- remove inline comment from routing example for clarity ([bcf1867](https://github.com/nexios-labs/Nexios/commit/bcf1867b3e4e8e892b2b01d18c88cdba2a3f46bd) by dunamix).
- remove inline comments from routing example for clarity ([6258d54](https://github.com/nexios-labs/Nexios/commit/6258d54ef8576ed7bc40c3bf2b3175a85838924d) by dunamix).
- add type hints for version and callable parameters in multiple files ([563955e](https://github.com/nexios-labs/Nexios/commit/563955e2be8e06d5f7a750359c6603ebd2cb09bc) by dunamix).
- remove debug print statement from Router class ([16f0708](https://github.com/nexios-labs/Nexios/commit/16f0708e03dadacc6361e1edb5f06fec8e2d9380) by dunamix).
- store reference to the Router instance in scope for better access ([7538676](https://github.com/nexios-labs/Nexios/commit/7538676c30d39ed55a61b04f444dde8a433e9ba6) by dunamix).
- update documentation URL to point to the correct Netlify site ([99d774f](https://github.com/nexios-labs/Nexios/commit/99d774f6eb72342d2fad89d67dc7a0c76a3d6d1f) by dunamix).
- update warning message for clarity on Granian integration ([19458f2](https://github.com/nexios-labs/Nexios/commit/19458f27bdf51afc30ee54b4fe87865a3d108b56) by dunamix).
- update version number to 2.4.0 and enhance README for consistency ([673b3b5](https://github.com/nexios-labs/Nexios/commit/673b3b58bfb0cf2ca95593d443928526199626de) by dunamix).

## [v2.4.0](https://github.com/nexios-labs/Nexios/releases/tag/v2.4.0) - 2025-05-11

<small>[Compare with v2.3.1](https://github.com/nexios-labs/Nexios/compare/v2.3.1...v2.4.0)</small>

### Features

- set base path for VitePress configuration ([a02156f](https://github.com/nexios-labs/Nexios/commit/a02156f36fd07191383d6221a7f93f69d558474c) by dunamix).
- add .nojekyll file to prevent GitHub Pages from ignoring files ([ab44836](https://github.com/nexios-labs/Nexios/commit/ab448366f2e624062d5eae559ed53ffd4bacaca2) by dunamix).
- add .nojekyll file to prevent GitHub Pages from ignoring _files ([afa2caf](https://github.com/nexios-labs/Nexios/commit/afa2caf953867666796c1dc0e16e432d446f43ad) by dunamix).
- update API Reference link and enhance Getting Started section with version badge ([af5bc06](https://github.com/nexios-labs/Nexios/commit/af5bc065d3b32143d74934f2f367bd4c8ffa1483) by dunamix).
- add OpenAPI section to navigation and enhance OpenAPI documentation links ([a0c650f](https://github.com/nexios-labs/Nexios/commit/a0c650f4b6827589bfb53bd375278b29048f5c76) by dunamix).
- update getting started section to use pip for installation and remove VitePress references ([55198b1](https://github.com/nexios-labs/Nexios/commit/55198b120729202212d727a2f35928908e7cd1b7) by dunamix).
- enhance file upload documentation and update site configuration with social links ([fea59ad](https://github.com/nexios-labs/Nexios/commit/fea59ade8c04cfbd75c3f88b5fb9cb0f94c2e282) by dunamix).
- update CORS documentation and add file upload guide ([c47e388](https://github.com/nexios-labs/Nexios/commit/c47e3880de0dd42c1960b3d8799f78a00be44662) by dunamix).
- enhance API documentation with detailed sections on application, request, response, routing, and WebSocket handling ([a9eb3e1](https://github.com/nexios-labs/Nexios/commit/a9eb3e10925c01e523cd01bf073b169d92cae83d) by dunamix).
- update VitePress config with new meta tags and favicon for improved SEO and branding ([86078f5](https://github.com/nexios-labs/Nexios/commit/86078f5c1b5fe78e3ba3d4059052a1c5daa9eb46) by dunamix).
- add comprehensive CLI documentation including installation, usage, commands, and server selection ([add8e6c](https://github.com/nexios-labs/Nexios/commit/add8e6cfd7e2750625f053e8de474b1c5e99bfce) by dunamix).
- enhance WebSocket documentation with new sections on Channels, Groups, and Static Files ([caf6b69](https://github.com/nexios-labs/Nexios/commit/caf6b69116c771291de22be716d4fb5dcd91b8c5) by dunamix).
- add Howto and Websockets sections to navigation and create initial markdown files ([05bf9aa](https://github.com/nexios-labs/Nexios/commit/05bf9aabcad36777b2d95c63f00cd9008bded507) by dunamix).
- add Request Info section with detailed examples for handling HTTP requests ([639d262](https://github.com/nexios-labs/Nexios/commit/639d26297e35a277c6abe8199c838aed6b4eb2ca) by dunamix).
- add Authentication and Session Management documentation with examples ([84c7df0](https://github.com/nexios-labs/Nexios/commit/84c7df0866f26dcffcccbc4f435a5ab2a21d5363) by dunamix).
- add Events section to documentation with usage examples ([5934e37](https://github.com/nexios-labs/Nexios/commit/5934e37a42c5368d7c0eca317844c6e2886b308b) by dunamix).
- add manual integration section for pagination with example code ([a4455cc](https://github.com/nexios-labs/Nexios/commit/a4455cc65f71f143713590e4bf5accc176dc48be) by dunamix).
- add documentation for Class-Based Views with usage examples and middleware support ([4eaafdf](https://github.com/nexios-labs/Nexios/commit/4eaafdf7275c4947054cae0c8377b4ca0525bdb5) by dunamix).
- enhance response methods to accept custom data handlers for synchronous and asynchronous pagination ([0cb609e](https://github.com/nexios-labs/Nexios/commit/0cb609e62f0aa467331b43b324da9fb6366d14fe) by dunamix).
- implement synchronous and asynchronous pagination methods with customizable strategies and data handlers ([47942c7](https://github.com/nexios-labs/Nexios/commit/47942c7c1a4fa8b25d7ac67fe22c70f735c6a883) by dunamix).
- add 'Error Handling' guide with comprehensive coverage and examples for managing exceptions ([e2fb9f4](https://github.com/nexios-labs/Nexios/commit/e2fb9f4523b4b72a335953fad3abba9c9d2fee59) by dunamix).
- enhance headers guide with detailed examples and best practices for request and response headers ([656fbc0](https://github.com/nexios-labs/Nexios/commit/656fbc0f32ebfd093716da9d36a10d44a2960fc5) by dunamix).
- add 'Headers' guide with detailed examples for request and response headers ([a578a30](https://github.com/nexios-labs/Nexios/commit/a578a303f9096cf68460410f4e3870cad0bb5e36) by dunamix).
- enhance 'Cookies' guide with comprehensive examples and security best practices ([e48bee9](https://github.com/nexios-labs/Nexios/commit/e48bee99e287c92153c93ed918815a4ac262aece) by dunamix).
- add 'Middleware' and 'Cookies' guides to documentation ([f3cd3ca](https://github.com/nexios-labs/Nexios/commit/f3cd3caaa9e9d316e9902b8b8f06c7ee04d5627e) by dunamix).
- add 'Routers and Sub-Applications' guide and update navigation ([b21c76a](https://github.com/nexios-labs/Nexios/commit/b21c76a0db6f82c024391d6bb8f29928e97592f3) by dunamix).
- add 'Sending Responses' guide and update navigation ([c86c0be](https://github.com/nexios-labs/Nexios/commit/c86c0be7cd55925b83cfbb4f22376b3fc521f1ab) by dunamix).
- enhance request handling by passing path parameters to route handlers ([820333e](https://github.com/nexios-labs/Nexios/commit/820333e51d11300f36202d48b04942138fcfd9ce) by dunamix).
- enhance documentation with getting started and routing guides ([fd11c9d](https://github.com/nexios-labs/Nexios/commit/fd11c9dac10756a85a2a9e073efa6ba4af080fb0) by dunamix).
- add comprehensive documentation and configuration for Nexios framework ([1c11fa0](https://github.com/nexios-labs/Nexios/commit/1c11fa047f9ccc9c73f8e5bea6a0c5e2a40d4aa1) by dunamix).
- Enhance dependency injection and add string representation for Request class ([6e4d754](https://github.com/nexios-labs/Nexios/commit/6e4d754649433e3a3ba9a60f699d1f98f7c31c66) by dunamix).
- Implement advanced event system with support for priority listeners, event phases, and asynchronous execution ([b4b2dfd](https://github.com/nexios-labs/Nexios/commit/b4b2dfd5de6b0c8c163567afb010139937b676d9) by dunamix).
- Add comprehensive overview of Nexios framework in about.md ([dcd873a](https://github.com/nexios-labs/Nexios/commit/dcd873a33479e19bc8cdc72ba1f52d77b7c6a3e6) by dunamix).
- Update SUMMARY.md to include comprehensive Dependency Injection section ([3961b33](https://github.com/nexios-labs/Nexios/commit/3961b33bba8a0f00e3a1288125f1bbc7e9c78313) by dunamix).
- Enhance documentation and add dependency injection support in Nexios framework ([18f56ab](https://github.com/nexios-labs/Nexios/commit/18f56ab89fcb52eb2defbbe329a36bd8e9de1cec) by dunamix).
- Add comprehensive documentation for About section, including Authors, Design Patterns, Performance, and Philosophy ([3c978cb](https://github.com/nexios-labs/Nexios/commit/3c978cb5154f3b3194bdbe5a537a2e253df44d40) by dunamix).
- Enhance dependency injection system with new documentation and integration in routing ([a20b69d](https://github.com/nexios-labs/Nexios/commit/a20b69d219e998f0d02bc44cd2393c47170642ba) by dunamix).
- Implement dependency injection system with DependencyProvider and related classes ([ec4c074](https://github.com/nexios-labs/Nexios/commit/ec4c0746adbc26c9495262be4ba73e71f889452b) by dunamix).
- Add multi-server support with Uvicorn and Granian in Nexios CLI ([5c0b174](https://github.com/nexios-labs/Nexios/commit/5c0b174b0087b8c23507f20fc2266b0230ee4468) by dunamix).
- Add example applications and routes for Nexios framework ([c099eaa](https://github.com/nexios-labs/Nexios/commit/c099eaa740174982cf860c3a0e4bb1ccbf4fa26d) by dunamix).
- Add new project templates with enhanced features and configurations ([219a86a](https://github.com/nexios-labs/Nexios/commit/219a86a0bdaf46648c6bb4ac3b692569c1d5f745) by dunamix).
- Enhance SUMMARY.md with additional sections and improved structure ([c1f2418](https://github.com/nexios-labs/Nexios/commit/c1f2418f1308c6cc424b8b95ba34248f8c307a6f) by dunamix).
- Implement comprehensive WebSocket testing suite with multiple endpoints and error handling ([d36449a](https://github.com/nexios-labs/Nexios/commit/d36449a6e41bfc4a59db0463c299785561e50c33) by dunamix).
- Add WebSocket support and enhance form data handling ([0e50d27](https://github.com/nexios-labs/Nexios/commit/0e50d27b232903ec49ddc92656ab2a7c1a338ca1) by dunamix).
- Enhance server error handling with detailed debugging information and improved HTML template ([b0bcad6](https://github.com/nexios-labs/Nexios/commit/b0bcad6adb2f59b6f433f28bf29979a52234b029) by dunamix).
- Implement CLI tools for project scaffolding and development server management; enhance documentation ([9530bf9](https://github.com/nexios-labs/Nexios/commit/9530bf9e006fa23a764b89dbbd46ebe423423108) by dunamix).
- update dependencies for jinja2 and pyjwt with optional extras ([fd1fefb](https://github.com/nexios-labs/Nexios/commit/fd1fefb41f3fe952d3e7d168efe7d3c8aeb93801) by dunamix).
- enhance request handling to support JSON responses ([b97b5d9](https://github.com/nexios-labs/Nexios/commit/b97b5d92d0997fe2a2384b3ea4f2f200dd8e7326) by dunamix).

### Bug Fixes

- update feature list in README for accuracy and clarity ([eedeb24](https://github.com/nexios-labs/Nexios/commit/eedeb24f8ed895bd3628f4c3a9f20d5db74620a1) by dunamix).
- update version number and enhance README badges ([13c099a](https://github.com/nexios-labs/Nexios/commit/13c099ae925003f3953ab47168294b8166724113) by dunamix).
- remove redundant options and examples from CLI documentation ([a24f986](https://github.com/nexios-labs/Nexios/commit/a24f986f1e11e5c3c2bfcb71355677862e45e282) by dunamix).
- remove base path from VitePress configuration ([8b3092e](https://github.com/nexios-labs/Nexios/commit/8b3092eb4064c4b5890be76cd4276f56916a90c5) by dunamix).
- update base path in VitePress configuration ([a7cea7f](https://github.com/nexios-labs/Nexios/commit/a7cea7f23565c3710cd2d0905046a2b60202572b) by dunamix).
- set base path in VitePress configuration ([681a9c4](https://github.com/nexios-labs/Nexios/commit/681a9c4554d189f9fcd9acbb9c8ac4f18a8d5db5) by dunamix).
- update install command to prevent frozen lockfile during dependency installation ([d932457](https://github.com/nexios-labs/Nexios/commit/d932457d25f3084f558eeb43cda6130a4c014e15) by dunamix).
- correct whitespace in hero name in index.md ([8a27f9e](https://github.com/nexios-labs/Nexios/commit/8a27f9ecb6c086016afeb0c6fa1a405099ce06c6) by dunamix).
- update install command in GitHub Actions workflow for consistency ([c39f1d9](https://github.com/nexios-labs/Nexios/commit/c39f1d99e9185af6ec2d266e8605a3248885ff76) by dunamix).
- update step name for clarity in GitHub Pages deployment ([cb13f80](https://github.com/nexios-labs/Nexios/commit/cb13f8045f38d765b9f1136f31c5dedd893cd0d5) by dunamix).
- remove .nojekyll creation step from deploy workflow ([43c419e](https://github.com/nexios-labs/Nexios/commit/43c419ea00085efae93724a5764ac655fd7d5fbf) by dunamix).
- update install command in deploy-docs workflow to use pnpm install ([66ab0d9](https://github.com/nexios-labs/Nexios/commit/66ab0d9878c50a3f39996635d78f0f60f797e43a) by dunamix).
- enable pnpm setup and correct build command formatting in deploy-docs workflow ([d931e15](https://github.com/nexios-labs/Nexios/commit/d931e15836f9639d4f27b836dafe53393bfc833b) by dunamix).
- update metadata and lockfile for improved dependency management ([2cadb3c](https://github.com/nexios-labs/Nexios/commit/2cadb3c23e7d471b934554f43a1c9a0730511f10) by dunamix).
- update installation and routing documentation for clarity ([863b120](https://github.com/nexios-labs/Nexios/commit/863b120005fecf32fe39a5ff7eff2f2ed9c84693) by dunamix).
- correct path parameter access in room handler and chat endpoint ([ac4c0c1](https://github.com/nexios-labs/Nexios/commit/ac4c0c11c179763310722e1439a65dea6cdc5dd7) by dunamix).
- Initialize configuration in NexiosApp constructor ([3e89ae6](https://github.com/nexios-labs/Nexios/commit/3e89ae6330ed491d332e8e232cef7e9cfc09e53e) by dunamix).
- Correct order of sections in SUMMARY.md for better clarity ([124a354](https://github.com/nexios-labs/Nexios/commit/124a3543ae661fae379ac2a96fed1cf1506ba1f6) by dunamix).
- set default type for Schema and update model references ([e546910](https://github.com/nexios-labs/Nexios/commit/e5469107d19d6caf2183d4ea47f1fe8c50d21b84) by dunamix).
- add default value support to RouteParam.get method ([b6cef3d](https://github.com/nexios-labs/Nexios/commit/b6cef3deb1e79093f5e9163c344d9608676b9478) by dunamix).
- handle ImportError for Jinja2 with a clear installation message ([b7dd792](https://github.com/nexios-labs/Nexios/commit/b7dd7924f92ff532c0e90f87be620828e61de596) by dunamix).
- remove unused response_model parameter and handle empty path case ([b43df18](https://github.com/nexios-labs/Nexios/commit/b43df185336237ecf8aef08ec615df436de1ccf9) by dunamix).
- correct response type alias for consistency ([39c062a](https://github.com/nexios-labs/Nexios/commit/39c062a70eea8686edea684083d0ab57a505016c) by dunamix).

### Code Refactoring

- update GitHub Actions workflow for VitePress deployment ([d357f9c](https://github.com/nexios-labs/Nexios/commit/d357f9cabef5692f9aa47bbdea152a60e5ef6f56) by dunamix).
- streamline deployment workflow for VitePress ([72c7e08](https://github.com/nexios-labs/Nexios/commit/72c7e084d3878b4b5a36f687b7c8af6bc0e6245a) by dunamix).
- streamline project creation and server run commands, enhance validation functions ([979121d](https://github.com/nexios-labs/Nexios/commit/979121d63ebcafc0f31342b005ca61beaa3495b5) by dunamix).
- simplify headers property and update header preservation logic ([9e79805](https://github.com/nexios-labs/Nexios/commit/9e798055f152360fcf9c57702b6e30821b4895e1) by dunamix).
- update response header method references to use set_header ([1fc05aa](https://github.com/nexios-labs/Nexios/commit/1fc05aa61329f7c2afd7b5b9f13f64692d3f9267) by dunamix).
- change request_response to async and await its execution in Routes class ([c4de608](https://github.com/nexios-labs/Nexios/commit/c4de60888cb56bf0086b2b98800845764b541c6b) by dunamix).
- move Convertor and related classes to converters.py ([18c9cd5](https://github.com/nexios-labs/Nexios/commit/18c9cd5aba5f44a9ac8ac1294fee5096210e5710) by dunamix).
- remove unnecessary inheritance from Any in Depend class ([bf3b04d](https://github.com/nexios-labs/Nexios/commit/bf3b04de4017a4cd37af33ea2c4cd637d3623c59) by dunamix).
- remove unused ParamSpec import ([21616cd](https://github.com/nexios-labs/Nexios/commit/21616cd3fb23b0f4ae2e5b9e2ad3e3ad75d51ea0) by dunamix).
- remove debug print statements and enhance dependency injection in routing ([87fc066](https://github.com/nexios-labs/Nexios/commit/87fc06694f3d0de4de6778b0fa3ae92284803a50) by dunamix).
- update Pydantic model configuration to use ConfigDict test: update assertions in exception handler tests to check for JSON responses ([c828e68](https://github.com/nexios-labs/Nexios/commit/c828e6894010d81091556c03ff034a206d9cb489) by dunamix).
- Remove unused TypeVar and clean up lifespan handling in NexiosApp ([3a1dbec](https://github.com/nexios-labs/Nexios/commit/3a1dbec5abce7513038737988861e745c11d3cbe) by dunamix).
- Update typing imports and lifespan type annotation in __init__.py ([7b0cbeb](https://github.com/nexios-labs/Nexios/commit/7b0cbeb0aa75573498ecdb47936bc428b9db1428) by dunamix).
- Remove redundant examples and streamline event handling section in events.md ([4b05d37](https://github.com/nexios-labs/Nexios/commit/4b05d37eb0ca7d79025614ba512e22ce153cd1d3) by dunamix).
- Improve type annotations and remove unnecessary type ignores across multiple files ([a73673c](https://github.com/nexios-labs/Nexios/commit/a73673c80c102aa4d5d6992ae36267a16e8cb77a) by dunamix).
- update type annotations for middleware functions to improve clarity and consistency ([dad9220](https://github.com/nexios-labs/Nexios/commit/dad922044562502cf47dae82192714f7fe597252) by dunamix).
- enhance type annotations for improved clarity and consistency across application, exception handling, and middleware modules ([006dbda](https://github.com/nexios-labs/Nexios/commit/006dbdab6443dad1695ed4f5d0e317e07658e6a2) by dunamix).
- streamline type annotations and clean up imports across application, dependencies, routing, and types modules ([c85022d](https://github.com/nexios-labs/Nexios/commit/c85022da763a104b1ab61d455ec51d3685981032) by dunamix).
- Add support for additional route parameters in Router class ([9e25486](https://github.com/nexios-labs/Nexios/commit/9e25486f3af83eb54d880b712b18d2e143fab228) by dunamix).
- Enhance lifespan shutdown handling in NexiosApp ([3f6a3e4](https://github.com/nexios-labs/Nexios/commit/3f6a3e467ef02d9d034788b8716ec3f69278f8f3) by dunamix).
- Simplify lifespan shutdown handling in NexiosApp ([e80913f](https://github.com/nexios-labs/Nexios/commit/e80913f22ce2646f6535d7cc9118a2aa0670798c) by dunamix).
- Update Nexios to use Granian server and enhance configuration options ([ac1d76c](https://github.com/nexios-labs/Nexios/commit/ac1d76c9afcf14e8bd4ed185b34fa45793329e83) by dunamix).
- Remove WebSocket connection handling from Client class ([696ed22](https://github.com/nexios-labs/Nexios/commit/696ed2214242d3578479b7ec8f1435b2031210cc) by dunamix).
- Remove debug print statement from ASGI application callable ([cdb44d0](https://github.com/nexios-labs/Nexios/commit/cdb44d04fb312e0e04ae3ab072e829bf1ddf7f9d) by dunamix).
- rename WebSocketEndpoint to WebSocketConsumer and update imports ([0d32e20](https://github.com/nexios-labs/Nexios/commit/0d32e206bf1cd0308621b36497dcaddacd7a6996) by dunamix).
- reorganize session handling and update imports ([d65dfd2](https://github.com/nexios-labs/Nexios/commit/d65dfd2364e61af781672f37e31e42bd9db778eb) by dunamix).

## [v2.3.1](https://github.com/nexios-labs/Nexios/releases/tag/v2.3.1) - 2025-04-14

<small>[Compare with v2.3.0-rc.1](https://github.com/nexios-labs/Nexios/compare/v2.3.0-rc.1...v2.3.1)</small>

### Features

- add comprehensive documentation for Nexios configuration and hooks ([878f79a](https://github.com/nexios-labs/Nexios/commit/878f79a34635439cde3aeb390d51cf86f1bd91e0) by dunamix).
- add funding configuration for "Buy Me a Coffee" ([3e662e0](https://github.com/nexios-labs/Nexios/commit/3e662e0ba5792274643b3caff5af3ecd125d79fa) by dunamix).
- add responses parameter to route handler ([cde174a](https://github.com/nexios-labs/Nexios/commit/cde174a9ffcc660215ac3526226ec0400b4a4f87) by dunamix).
- add exclude_from_schema option to FileRouter and Router classes ([8bd908e](https://github.com/nexios-labs/Nexios/commit/8bd908e5e086d09fe18a34bc732450ee38374aff) by dunamix).

### Bug Fixes

- update default config import and streamline code formatting ([8cec770](https://github.com/nexios-labs/Nexios/commit/8cec77035420dc38073c7a9e4cd3bbf087da26ad) by dunamix).
- remove unused import from jwt backend ([512a764](https://github.com/nexios-labs/Nexios/commit/512a764a83a8066410dc472c6df8fe81a87ec8cb) by dunamix).
- improve formatting and clarity in managing_config.md ([369346c](https://github.com/nexios-labs/Nexios/commit/369346cd4b1c014a202b82e7b932715bcd2d8b39) by dunamix).
- standardize warning formatting and update hook descriptions in misc.md ([0438641](https://github.com/nexios-labs/Nexios/commit/04386418a1e1f53b5c8110c81c1ba63dff3c448a) by dunamix).
- add missing links for Managing Config and Misc in SUMMARY.md ([80993b8](https://github.com/nexios-labs/Nexios/commit/80993b837c85680c48f5fb0ee8c23600f59da70c) by dunamix).
- update badge alignment and formatting in README files ([7aac3c7](https://github.com/nexios-labs/Nexios/commit/7aac3c73dc31a5ec2c2273509c2138aa774125aa) by dunamix).
- add GitHub funding link for techwithdunamix ([9c482cd](https://github.com/nexios-labs/Nexios/commit/9c482cdc25b7e68b3cec450cf70cf73d35cb35bb) by dunamix).
- add pytest-asyncio and pydantic dependencies; update asyncio_fixture_scope in pytest options ([8a004e1](https://github.com/nexios-labs/Nexios/commit/8a004e134b59767333e43c8b6bb70b7511eae289) by dunamix).
- update image attributes for Swagger API documentation ([399d77f](https://github.com/nexios-labs/Nexios/commit/399d77fac6bd1a8452adc66844c3901b604d74b3) by dunamix).
- update visitor count alt text and correct image path ([4bd1fd0](https://github.com/nexios-labs/Nexios/commit/4bd1fd026e366410877f52e9c79a0004a0dc8e64) by dunamix).
- update GzipMiddleware usage in example to use wrap_asgi method ([8fa590b](https://github.com/nexios-labs/Nexios/commit/8fa590b3758e316c4c5c1ae985efc4346d547727) by dunamix).
- handle empty context in render function to prevent errors ([ebdc3de](https://github.com/nexios-labs/Nexios/commit/ebdc3de17c7027a3e59a67da0a4c4732161b4fb9) by dunamix).
- correct path handling in FileRouter for improved route mapping ([d0a2c9d](https://github.com/nexios-labs/Nexios/commit/d0a2c9db279b8b940e65b49bda99d8c96c73beda) by dunamix).
- improve method handling in FileRouter for route mapping ([d09106f](https://github.com/nexios-labs/Nexios/commit/d09106f346a1874a40fe209e587245c944f5a3c5) by dunamix).
- fixed method handling and schema exclusion in FileRouter ([a44f1ec](https://github.com/nexios-labs/Nexios/commit/a44f1ecc72b67ad83256f16c0d12a9a1fa8d741e) by dunamix).

### Code Refactoring

- streamline OpenAPI configuration and documentation setup ([32c6adc](https://github.com/nexios-labs/Nexios/commit/32c6adccf3b7eac2f0e3b8c8881cbf39303a2336) by dunamix).
- remove unused WebSocketSession file ([24f1327](https://github.com/nexios-labs/Nexios/commit/24f1327dee9cf8b97d7753fa30e92995e1b217f0) by dunamix).
- update middleware integration and improve ASGI compatibility ([309f2a4](https://github.com/nexios-labs/Nexios/commit/309f2a444f0da94aa51c700b33f708b6a0a16ef4) by dunamix).

## [v2.3.0-rc.1](https://github.com/nexios-labs/Nexios/releases/tag/v2.3.0-rc.1) - 2025-04-04

<small>[Compare with first commit](https://github.com/nexios-labs/Nexios/compare/921f570f769df8d1935e7251ef985a69fb2fc537...v2.3.0-rc.1)</small>

### Features

- update logging documentation for clarity and consistency; remove deprecated file-router documentation ([3e316cc](https://github.com/nexios-labs/Nexios/commit/3e316cc8cefffffcfa201044d510612ba29891d4) by dunamix).
- enhance path parameter replacement using regex for improved flexibility ([34395ac](https://github.com/nexios-labs/Nexios/commit/34395acc4a9ad7edfdf1b0952b605c6236d564de) by dunamix).
- add restrict_slash method and improve path handling in route mapping ([65e6ffd](https://github.com/nexios-labs/Nexios/commit/65e6ffdf62ae8655a98657a773e8db2cb221c009) by dunamix).
- implement new HTML rendering functionality and restructure file organization ([862a82c](https://github.com/nexios-labs/Nexios/commit/862a82c66b26b1ffd9436d7f0d8c691801935227) by dunamix).
- add OpenAPI setup during application startup ([f7250c4](https://github.com/nexios-labs/Nexios/commit/f7250c48adf159ea44dcb904e120fd18a314f77b) by dunamix).
- enhance route documentation and add get_all_routes method ([c6b3014](https://github.com/nexios-labs/Nexios/commit/c6b3014d5c1966c3f5bba616f4ff20dd2a2f45a2) by dunamix).
- add session configuration enhancements and improve expiration handling ([0983224](https://github.com/nexios-labs/Nexios/commit/09832244e57fc6d6be65486a1030615c825c5974) by dunamix).
- implement session-based authentication backend and enhance session handling ([73726eb](https://github.com/nexios-labs/Nexios/commit/73726eb75a1945b3e2eca74e569bd0c61707e71b) by dunamix).
- enhance JWT decoding and improve exception handling with custom handlers ([f1312c5](https://github.com/nexios-labs/Nexios/commit/f1312c549ee4ada61b8df2774d611e8013935fc3) by dunamix).
- enhance routing configuration with exempt paths and add route decorator ([886b8b4](https://github.com/nexios-labs/Nexios/commit/886b8b48f75ad41fc88767e7cc6ed0b8c1702a7b) by dunamix).
- migrate HTML rendering to file router plugin ([5892f80](https://github.com/nexios-labs/Nexios/commit/5892f806302e6e37367ad703556900752686e82f) by dunamix).
- improve type annotations and formatting in WebSocketEndpoint ([7d3cbf1](https://github.com/nexios-labs/Nexios/commit/7d3cbf1d61a5e5e34c9d778df8e3648a318921df) by dunamix).
- adds jinja2 template plugin ([af4ff09](https://github.com/nexios-labs/Nexios/commit/af4ff09ce935096a144aa9f8782e4d13b1e404e0) by Mohammed Al Ameen).
- adds middleware support for file router ([cb2d050](https://github.com/nexios-labs/Nexios/commit/cb2d050a619407bd4793c4de7f6f683e6968af47) by Mohammed Al Ameen).
- refactor route handling to use pathlib for module imports and streamline method mapping ([ac7c336](https://github.com/nexios-labs/Nexios/commit/ac7c336bf9f694eefb8895a752d3b5ce1641dfa9) by dunamix).
- adds file router plugin ([0c5f20a](https://github.com/nexios-labs/Nexios/commit/0c5f20a5c569329747db95011189483c99cb9c57) by Mohammed Al Ameen).
- add Swagger UI generation and auto-documentation capabilities ([1fe8f3c](https://github.com/nexios-labs/Nexios/commit/1fe8f3c94e3507df48225a155a9c0b3e3a006091) by dunamix).
- enhance path parameter handling and request/response preparation in APIDocumentation ([6f1a3b2](https://github.com/nexios-labs/Nexios/commit/6f1a3b29466888abcf0ef014df6a749443ef5c3d) by dunamix).
- implement OpenAPI configuration and documentation routes ([ab600ca](https://github.com/nexios-labs/Nexios/commit/ab600cad724cbda4e21220c7a51748b7f7226e3f) by dunamix).
- add initial OpenAPI models and structure ([62a3581](https://github.com/nexios-labs/Nexios/commit/62a35810fc83c6334699b9f767f7b2490f89a496) by dunamix).
- add encoding attribute and update middleware type in WebSocketEndpoint class docs: add Nexios Event System Integration Guide with examples and best practices ([e7f0310](https://github.com/nexios-labs/Nexios/commit/e7f031018033e9ba869deeb6bb785d611c3c7bf0) by dunamix).
- add as_route class method to convert WebSocketEndpoint into a route ([d45127c](https://github.com/nexios-labs/Nexios/commit/d45127c5617da40f1fa67821337dec89f1e42d3c) by dunamix).
- enhance authentication decorator to accept string or list of scopes ([0d13ad8](https://github.com/nexios-labs/Nexios/commit/0d13ad83e4b28c952c8f71d194c7297db7a724fc) by dunamix).
- ✨: add make_response method to create responses using custom response classes; enhance method chaining with preserved headers and cookies ([666dd63](https://github.com/nexios-labs/Nexios/commit/666dd63e9afe3015587d31d57c0645889e0a56cc) by dunamix).
- ✨: add content_length property and set_body method in NexiosResponse; enhance set_headers to support overriding headers in CORS middleware ([5147f1f](https://github.com/nexios-labs/Nexios/commit/5147f1f1b482de39d8427936942189ba08b97762) by dunamix).
- 🔧: add lifespan support to NexiosApp and implement close_all_connections method in ChannelBox ([e5daae8](https://github.com/nexios-labs/Nexios/commit/e5daae8d11f6c57cd44995b8a5dbd4594a57b2ac) by dunamix).
- ✨: enhance WebSocketEndpoint with logging capabilities and new channel management methods ([15aebaa](https://github.com/nexios-labs/Nexios/commit/15aebaa89a1739825c0465214620a4fe28a600d3) by dunamix).
- ✨: add GitHub Actions workflow for running tests and uploading coverage reports ([fe9ba80](https://github.com/nexios-labs/Nexios/commit/fe9ba8008394d09daf899dd0fd55543c9e0daa9c) by dunamix).
- enhance JWT handling and add route-specific middleware decorator ([77b40aa](https://github.com/nexios-labs/Nexios/commit/77b40aab9d2c2c1854cda8cacf62c83234d83e83) by dunamix).
- update authentication backends to improve configuration handling and error reporting ([04061ac](https://github.com/nexios-labs/Nexios/commit/04061ac4818d53588d4d1b7cb6d5f8f1fe2d8f75) by dunamix).
- update project initialization and database configuration templates for improved database connection handling ([f4b6815](https://github.com/nexios-labs/Nexios/commit/f4b6815185daf308b30c5cbe30af381267706027) by dunamix).
- enhance Nexios CLI with project initialization and database setup commands ([c147664](https://github.com/nexios-labs/Nexios/commit/c1476644569c40c28204fb8d5b2d41c9d64243a7) by dunamix).
- implement authentication backends and middleware for user authentication ([36c6929](https://github.com/nexios-labs/Nexios/commit/36c6929ca6abda816bac389d0462a2162470feb9) by dunamix).
- implement JWT authentication backend and utility functions for token handling ([8c99db3](https://github.com/nexios-labs/Nexios/commit/8c99db3b2949f343ab48946d0a50a08e358f89d6) by dunamix).
- implement API key and session authentication backends for enhanced security ([a21cab1](https://github.com/nexios-labs/Nexios/commit/a21cab15e7cb8e8eebce0a7baf962d0949db54a9) by dunamix).
- implement basic authentication backend and middleware for user authentication ([ff53a90](https://github.com/nexios-labs/Nexios/commit/ff53a9046b811cc6661ac3d3dbd150c658147e33) by dunamix).
- implement authentication middleware and user classes for enhanced user management ([1b23b84](https://github.com/nexios-labs/Nexios/commit/1b23b84d6a81dbac56eb6187365e6b0b1ad82ce3) by dunamix).
- add request lifecycle decorators for enhanced request handling and logging ([92a824a](https://github.com/nexios-labs/Nexios/commit/92a824a21595c3377684d1f18cfabf0430c08a4b) by dunamix).
- initialize authentication module in the Nexio library ([0243d88](https://github.com/nexios-labs/Nexios/commit/0243d889ee9ceb4ca8747dfd5e534ed82019acea) by dunamix).
- add parameter validation for route handlers and enhance route decorators ([ad8d694](https://github.com/nexios-labs/Nexios/commit/ad8d694f8f0194f5e20288714f0e9429040713d5) by dunamix).
- enhance middleware execution and improve session expiration handling ([813b234](https://github.com/nexios-labs/Nexios/commit/813b234d1a7f443bb7444457690ae5cd0d7bf247) by dunamix).
- update logo to SVG format and adjust mkdocs configuration and request file methods ([3963dd9](https://github.com/nexios-labs/Nexios/commit/3963dd903cac7619beb12fcbb6b3abf843adaaa7) by dunamix).

### Bug Fixes

- remove unnecessary blank line in Router class ([0b04c40](https://github.com/nexios-labs/Nexios/commit/0b04c400a72c7dfe27726333a6d48449b5322f03) by dunamix).
- standardize header casing and improve CORS middleware logic ([cb02735](https://github.com/nexios-labs/Nexios/commit/cb027352c0ce75bbe32f45258ae7ba2bbdec415c) by dunamix).
- correct string representation in BaseSessionInterface and clean up test cases ([7d74cbf](https://github.com/nexios-labs/Nexios/commit/7d74cbf7e034a9e355108b200602090d54904ebb) by dunamix).
- update session expiration logic and improve session management ([c50b14b](https://github.com/nexios-labs/Nexios/commit/c50b14b3ffdd2fc097a132b2b4040fdb32e59499) by dunamix).
- correct typo in first_middleware function parameter name ([b3bf139](https://github.com/nexios-labs/Nexios/commit/b3bf139fa0863ae05792efb674de68b55ede0a57) by dunamix).
- update permissions and simplify git push in format-code.yml ([1e478bc](https://github.com/nexios-labs/Nexios/commit/1e478bc85e2c134551cce3985f87f2e08ed8a3b3) by dunamix).
- update GitHub token usage in format-code.yml for secure pushing ([129b7d4](https://github.com/nexios-labs/Nexios/commit/129b7d47df67a261dd523f33979e42cd540e762f) by dunamix).
- update GitHub token secret name in deploy-docs.yml ([fb60e22](https://github.com/nexios-labs/Nexios/commit/fb60e223d534efd6231a260dc1488f6a2183b647) by dunamix).
- remove unused import of MiddlewareType in consumers.py ([288bff7](https://github.com/nexios-labs/Nexios/commit/288bff7998129d003c961e9f03258e15f601397e) by dunamix).
- import WebsocketRoutes inside as_route method to avoid import errors ([9182134](https://github.com/nexios-labs/Nexios/commit/9182134cf5ad0ef6090db8ba1cc2a871b5da7f2e) by dunamix).
- 🔧: correct app reference in handle_http_request; add wrap_with_middleware method to support ASGI middleware integration; improve error handling in BaseMiddleware ([bcaa3ee](https://github.com/nexios-labs/Nexios/commit/bcaa3eea3ef1c432ee424e232916590cf9ca877e) by dunamix).
- 🔧: suppress RuntimeError in BaseMiddleware to handle EndOfStream gracefully; add type ignore for message assertion ([a14e73b](https://github.com/nexios-labs/Nexios/commit/a14e73bcfccb9d2a71614ac889b9a9b7b27c7054) by dunamix).
- 🔧: remove debug print statement for message in NexiosApp to clean up output ([0a9dd94](https://github.com/nexios-labs/Nexios/commit/0a9dd9439d986c73af0b22e3e8adf8d2674b844f) by dunamix).
- 🔧: improve exception handling in collapse_excgroups; update BaseResponse initialization to remove setup parameter and enhance cookie management ([ae2e1b4](https://github.com/nexios-labs/Nexios/commit/ae2e1b41a13b44b0b5d51995773f1bfbfdfa325e) by dunamix).
- 🔧: update datetime import to use timezone.utc; simplify payload sending logic in Channel class ([74440f4](https://github.com/nexios-labs/Nexios/commit/74440f46e219a5a009e39edffe0085d5597c935a) by dunamix).
- 🔧: handle empty range end in FileResponse initialization to prevent ValueError ([0b846b5](https://github.com/nexios-labs/Nexios/commit/0b846b584d860eaa39263df1f389415925f6f0af) by dunamix).
- 🔧: update FileResponse initialization and improve range handling in response.py; modify BaseMiddleware to suppress RuntimeError; clean up test_response.py ([22f4374](https://github.com/nexios-labs/Nexios/commit/22f43743cec74710ee2ac9fefe96479eb8ffeb16) by dunamix).
- 🔧: update FileResponse initialization to include setup parameter and clean up range handling comments ([02a5196](https://github.com/nexios-labs/Nexios/commit/02a51961730471b0b29bde008594f3d409fea42e) by dunamix).
- 🔧: update .gitignore, improve gzip documentation, refactor middleware handling, and replace print statements with logger in hooks ([feaa074](https://github.com/nexios-labs/Nexios/commit/feaa0747c27e6e74e32eb8eec502d8d175bb589b) by dunamix).
- 🔧: ensure websocket is closed properly on disconnect in WebSocketEndpoint ([1bd2372](https://github.com/nexios-labs/Nexios/commit/1bd23724acb270b1d4953e7a40c59136b7952540) by dunamix).
- 🔧: add channel_remove_status variable in ChannelBox and simplify loop in WebSocketEndpoint ([f00c6c4](https://github.com/nexios-labs/Nexios/commit/f00c6c4eed94885f08c751ca90b6fe9a950a1ddc) by dunamix).
- 🔧: make expires parameter optional in Channel class constructor ([58dc8ed](https://github.com/nexios-labs/Nexios/commit/58dc8ed592c2f1929138d79b8ab249fd1ddd5688) by dunamix).
- 🐛 fix: enhance exception handling by raising exceptions when no handler is present; add user setter to Request class ([caeb648](https://github.com/nexios-labs/Nexios/commit/caeb64846606cda970f23063949e35f7a538ac53) by dunamix).
- simplify method type casting in Request class ([9ea14e5](https://github.com/nexios-labs/Nexios/commit/9ea14e560894cb0ea138b264f10c4abbbcdc5068) by dunamix).
- update cookie deletion logic to use None and set expiry to 0 ([6e24d61](https://github.com/nexios-labs/Nexios/commit/6e24d61c07b70a1597d0106b241b49e7932b43e2) by dunamix).
- improve request handling and error logging in NexioApp ([f96d209](https://github.com/nexios-labs/Nexios/commit/f96d209addf6c9403fbaeaaafbfdf09d1ff7a2b8) by dunamix).
- update allowed HTTP methods to lowercase and improve method validation in CORS middleware ([c0eb15d](https://github.com/nexios-labs/Nexios/commit/c0eb15daa61202219958c6a534dcba55da220de2) by dunamix).
- remove debug print statements from response and middleware classes ([40d65f6](https://github.com/nexios-labs/Nexios/commit/40d65f66c14799bfb2f8945c905e86bc95719b58) by dunamix).
- remove debug print statements and update CORS headers handling ([3154d2c](https://github.com/nexios-labs/Nexios/commit/3154d2c0388e548aa49d9ebd25baf4b2e42340ff) by dunamix).
- re issues ([94803fe](https://github.com/nexios-labs/Nexios/commit/94803feae27e8785109c8e94ed798616364b37cd) by dunamix).

### Code Refactoring

- remove unused file router and HTML plugin examples ([5132229](https://github.com/nexios-labs/Nexios/commit/5132229bf9bc528fc32fa5e7308d3abf029cfc71) by dunamix).
- refactor routing logic and add utility functions for route management ([6e455e2](https://github.com/nexios-labs/Nexios/commit/6e455e204e05c6b4eb2bd15e89e76a72d2a069ac) by dunamix).
- simplify parameter type annotations in OpenAPI models ([362a41f](https://github.com/nexios-labs/Nexios/commit/362a41f556094aa4c63a133f464d609794b753a6) by dunamix).
- clean up whitespace and formatting in application.py and routing.py ([bddda05](https://github.com/nexios-labs/Nexios/commit/bddda05d1258bdf99cc6dcd58ef192e4300b6412) by dunamix).
- apply code formatting and clean up whitespace across multiple files ([6ca85b3](https://github.com/nexios-labs/Nexios/commit/6ca85b30a48bfc9d6f5521d0f55254c5dbdb94cc) by dunamix).
- remove redundant comment in Address class ([aa2b314](https://github.com/nexios-labs/Nexios/commit/aa2b314af61126d1d9b9b2bf00a1143a3671f36d) by dunamix).
- remove unused constants and enhance OpenAPIConfig with contact and license fields ([4f10851](https://github.com/nexios-labs/Nexios/commit/4f108515d1b1a0af1e228bf54ca8209174a1f54e) by dunamix).
- streamline APIDocumentation class and enhance parameter handling ([a02a881](https://github.com/nexios-labs/Nexios/commit/a02a8814ef1e32309777e50b56e6b486efb60ab2) by dunamix).
- ♻️: replace getLogger with create_logger and update logo size in README ([c12afe9](https://github.com/nexios-labs/Nexios/commit/c12afe9837b691db1698bdd37666f539e4b90617) by dunamix).
- ♻️: update documentation for Class-Based Views and remove Class-Based Handlers ([29163fe](https://github.com/nexios-labs/Nexios/commit/29163fe4808a80847ce8fb2fc995176208e8c3c8) by dunamix).
- ♻️: update APIView to assign request and response attributes ([520d2d5](https://github.com/nexios-labs/Nexios/commit/520d2d5a78711080afe2208189d69372e78294fb) by dunamix).
- ♻️: remove unused import from routing module ([2f03e46](https://github.com/nexios-labs/Nexios/commit/2f03e46162dcb1ea00d774418c19a16f32f8a87d) by dunamix).
- ♻️: remove unused imports and clean up HTTPMethod class in types module ([d2494cd](https://github.com/nexios-labs/Nexios/commit/d2494cd7798290ca38129615cfe413c174f36694) by dunamix).
- ♻️: remove APIHandler class; introduce APIView for enhanced class-based views with routing support ([817c947](https://github.com/nexios-labs/Nexios/commit/817c9474c177e3067a13579c6046feda346d79b9) by dunamix).
- ♻️: reorganize utils and async_helpers; move functions to _utils and update imports ([22109df](https://github.com/nexios-labs/Nexios/commit/22109dfab417ccf806ec0c70e1bf0a09ac8a5806) by dunamix).
- 🔧: remove unused middlewares and update FileResponse initialization in response.py ([cdefcf9](https://github.com/nexios-labs/Nexios/commit/cdefcf996089b5540428fb8e85bf537fb2d53c03) by dunamix).
- 🔧: rename __handle_lifespan to handle_lifespan and improve message logging in NexiosApp ([2721527](https://github.com/nexios-labs/Nexios/commit/2721527c3f2c889cdea6b70da35293a8b638bef4) by dunamix).
- remove database session management and related files ([2e0b77a](https://github.com/nexios-labs/Nexios/commit/2e0b77a1b4ffa45a58c538392e80192f1fc83cac) by dunamix).
- remove direct authentication middleware instantiation and simplify BasicAuthBackend initialization ([8f2d4ab](https://github.com/nexios-labs/Nexios/commit/8f2d4aba52e038ee353c0da2873eaa2df33901b4) by dunamix).
- remove BaseConfig dependency and implement global configuration management ([79a343a](https://github.com/nexios-labs/Nexios/commit/79a343aa2ede7f169d90c3edc3bd0b6d728d2622) by dunamix).

