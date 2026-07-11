<p align="center">
    <br />
    <img src="https://raw.githubusercontent.com/lucas-labs/lucode-starlight-theme/refs/heads/master/docs/src/assets/logo.svg" alt="Lucode Starlight Theme" width="64" />
    <br />
    <strong>Lucode Starlight Theme</strong>
    <br />
    An Astro Starlight theme inspired by <code>shadcn/ui</code>.
    <br />
    <a href="https://lucas-labs.github.io/lucode-starlight-theme">Preview/docs</a> · <a href="https://www.npmjs.com/package/lucode-starlight">Npm</a>
</p>

<br />

<p align="center">
<img width="1600" height="900" alt="image" src="https://github.com/user-attachments/assets/e5b26cbb-cd44-494e-8d15-f9c44a5c0d04" />
</p>

# Lucode Starlight Theme

[shadcn/ui](https://ui.shadcn.com/) inspired Starlight theme.

## Attribution

This [Starlight](https://starlight.astro.build/) theme recreates the design of the documentation site for [shadcn/ui](https://ui.shadcn.com/) (as of April 2026). I used the great [adrian-ub/starlight-theme-black](https://github.com/adrian-ub/starlight-theme-black) as a base, which brought an earlier **shadcn/ui**-inspired design to Astro Starlight.

## This Repository

This repo is a Bun workspace monorepo for the theme itself and its documentation site.

The repository contains:

- `packages/lucode-starlight`: the published Starlight theme plugin.
- `docs`: the documentation site for the theme

### Workspace

```txt
./
├─ docs/
│   └─ documentation site for this theme
└─ packages/
    └─ lucode-starlight/
        └─ theme package
```

### Theme Package

The package lives in `packages/lucode-starlight` and is published as `lucode-starlight` on npm.

See [packages/lucode-starlight/README.md](packages/lucode-starlight/README.md) for details on the theme package.

## Documentation Site

The docs site is in `docs` and is built with Astro Starlight using the local theme package.

Also serves as a live preview of the theme.

<br />
<br />
<hr />

<p align="center">
    <br/><br />
    <a href="https://lucode.dev">
        <img src="https://raw.githubusercontent.com/lucas-labs/lucode-starlight-theme/refs/heads/master/docs/src/assets/logo.svg" alt="Lucode" width="32" />
    </a>
    <br />
    <br />
</p>
