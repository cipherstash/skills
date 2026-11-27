# Project structure

How to lay out and publish a package: packages, the `exports` map, module format, `tsconfig` files, `isolatedDeclarations`, publint and attw, naming and style, and documentation comments. The rules target TypeScript 7.0 and Node 24, with the compiler settings that [checks.md](checks.md) requires. The `exports` map is quoted from the [examples package](../examples/package.json), where CI runs publint and attw over it.

## Packages

- Make one package for each thing that is published or deployed on its own. Put several in one pnpm workspace, as [dependencies.md](dependencies.md) says.
- Give each package `"type": "module"`, an `engines.node` of at least the Node version it targets, and a `files` list of what it publishes, such as `dist`. A package that is never published sets `"private": true`.
- Keep source in `src/`, tests beside it, and build output in `dist/`, which git ignores.
- Import another package of the workspace through its `exports`, never by a relative path into its `src/`.

## The `exports` map

A new package publishes ESM only. Its `exports` map names each entry point, with `types` first in each, because TypeScript uses the first condition that matches. From [`package.json`](../examples/package.json):

```json
  "type": "module",
  "engines": {
    "node": ">=24"
  },
  "packageManager": "pnpm@12.23.0",
  "files": [
    "dist"
  ],
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "default": "./dist/index.js"
    }
```

- A CommonJS caller on Node 24 can still load the package with `require`, since `require` of ESM needs no flag there, as long as the package uses no top-level `await`.
- Code outside the package can import only the paths that `exports` lists. Adding `exports` to a package that had none, or removing an entry, breaks every caller that imported another path. Treat it as a breaking change.
- Follow a repository's own module-format rule when it has one. A repository that publishes both ESM and CommonJS keeps doing so, with `import` and `require` conditions, each with its own `types`.

## Module format

- `module: "nodenext"` makes TypeScript follow Node's rules, so a relative import names the `.js` file the build emits: `import { parsePort } from "./result.js"`.
- Under `verbatimModuleSyntax`, an import that is only a type is written `import type { A }`, or with an inline modifier, `import { type A, b }`. TypeScript then removes exactly what is marked `type`, and keeps every other import.
- Use `moduleResolution: "bundler"` only for code a bundler builds. TypeScript 7 removes `moduleResolution: "node"` and `"node10"`.
- Write `import.meta.dirname`, not `__dirname`, and `import`, not `require`, in an ES module.

## `tsconfig` files

- Start from [assets/tsconfig.json](../assets/tsconfig.json). Its `tsconfig.json` type-checks everything with `noEmit`, tests included. A `tsconfig.build.json` that extends it sets `rootDir` and `outDir`, and leaves the tests out of the build. CI type-checks both, as [checks.md](checks.md) says.
- Name the test runner's types only if you use its globals, which [testing.md](testing.md) says not to. Vitest needs no entry in `types`.
- Set `allowImportingTsExtensions` only with `noEmit`, or with `rewriteRelativeImportExtensions` when the build emits.
- TypeScript 7 removes `baseUrl`. Prefer the `imports` field of `package.json`, as in `"#lib/*": "./src/lib/*"`, to `paths`: Node resolves `imports` at run time, and `paths` changes only what the compiler sees. If you use `paths`, write each target relative, as `"./src/lib/*"`.
- TypeScript 7 has no compiler API for tools to call. Do not write a script that imports `typescript` to type-check or emit. Run `tsc`.

## `isolatedDeclarations`, publint, and attw

- A published package sets `isolatedDeclarations`. Every export then needs a type the compiler can read without inference: an explicit return type on each exported function, and a type annotation on each exported value. Tools can then emit each file's declarations on their own.
- Build the package, then run `publint --strict` and `attw --pack .`, with `--profile esm-only` for an ESM-only package. They report `exports` entries that point at missing files, types that resolve differently from the code, and files left out of the package. [checks.md](checks.md) pins both.
- Compare the declaration files at the base and the head of a change to an exported API. A removed export, a narrowed parameter, or a widened return type is a breaking change.

## Naming and style

- Biome formats every file. Do not format by hand or argue about layout in review.
- Name types, interfaces, and classes in `PascalCase`, and functions, values, and parameters in `camelCase`. Do not prefix an interface with `I`. Name a type parameter `T`, or a word starting with `T`, such as `TKey`.
- Write an acronym as a word, such as `keyId`, `parseJson`, and `HttpClient`.
- Name a file in `kebab-case`, after what it does, such as `all-settled.ts`.
- Use named exports. A default export is only for a file that a tool requires to have one, such as `vitest.config.ts`.
- Name a boolean as a question, such as `isValid` or `hasKey`. Take a `readonly` array as a parameter you do not change.

## Documentation comments

- Give every export of a published package a `/** */` documentation comment. Start with one sentence saying what it does.
- Say what the caller must know that the signature does not: whether it returns a result union and which failures, the errors it throws, units, and whether it takes an `AbortSignal`.
- Use `@param` only when a parameter's meaning is not plain from its name, and `@deprecated` with what to use instead.
- Do not repeat in a comment the types that the signature states.
