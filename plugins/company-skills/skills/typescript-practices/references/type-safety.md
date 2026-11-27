# Type safety

How to make the compiler catch mistakes: `unknown` over `any`, narrowing, branded types, exhaustive checks, and `satisfies`. The examples target TypeScript 7.0 and Node 24, with the compiler settings that [checks.md](checks.md) requires. They are quoted from the [examples package](../examples/package.json), where CI type-checks, lints, and tests them.

## `any`, `unknown`, and casts

- Use `unknown` for a value whose type you do not know yet, such as parsed JSON or a caught error. Narrow it before you use it. `any` turns the checks off for every use of the value, and oxlint's `no-unsafe-*` rules report it.
- Write no explicit `any`. Where one cannot be avoided, such as a library type that demands it, add a comment saying why.
- In a union of event or message shapes, give a field of unknown shape the type `unknown`, not `any`.
- Every `as` cast and `!` non-null assertion needs a reason the compiler cannot see, in a comment. Prefer narrowing. Never cast through `any` or `unknown` to make a type fit, as in `null as any`. If the code is not written yet, throw `new Error("not implemented")`.
- Use `as const` objects instead of `enum`. Node's type stripping rejects `enum`, and a const object is plain JavaScript.

## Narrowing

TypeScript narrows a union inside a branch that tests it: `typeof` for primitives, `instanceof` for classes, `in` for a property, `Array.isArray`, and `===` against a literal. A type predicate, `value is T`, or an assertion function, `asserts value is T`, names a narrowing check so it can be reused.

A type predicate or assertion function is a promise the compiler cannot check. It must test every field the type promises. A check of the `type` field alone lets a value with no `email` become a `User`. From [`src/type-safety/assert-user.ts`](../examples/src/type-safety/assert-user.ts):

```ts
// Assert with type predicate: check every field the type promises
export function assertIsUser(value: unknown): asserts value is User {
  if (
    typeof value !== "object" ||
    value === null ||
    !("type" in value) ||
    value.type !== "user" ||
    !("name" in value) ||
    typeof value.name !== "string" ||
    !("email" in value) ||
    typeof value.email !== "string"
  ) {
    throw new Error("Not a user");
  }
}
```

For input from outside the process, such as a request body or a file, parse with a schema at the boundary instead of writing a guard by hand.

## Branded types

A branded type gives a primitive a name the compiler checks, so two IDs that are both strings cannot be swapped. Give keys, key IDs, ciphertexts, and other values that must not mix their own brand. Create a branded value only in one function that checks or produces it. From [`src/type-safety/branded.ts`](../examples/src/type-safety/branded.ts):

```ts
// Branded type for domain modeling
type Brand<T, B extends string> = T & { readonly __brand: B };
export type UserId = Brand<string, "UserId">;
export type OrderId = Brand<number, "OrderId">;

export const toUserId = (id: string): UserId => id as UserId;
export const toOrderId = (id: number): OrderId => id as OrderId;

// Usage — prevents accidental id mix-ups at compile time
export function getOrder(userId: UserId, orderId: OrderId): string {
  return `${userId}/${orderId}`;
}
```

## Exhaustive checks

Model a value with a fixed set of shapes as a discriminated union: each member has a literal `status`, `type`, or `kind` field. Switch on that field, and in the `default` branch assign the value to `never`. When someone adds a member and forgets a case, the assignment stops compiling. The `throw` still runs for a value from outside the program whose shape the union does not list. oxlint's `switch-exhaustiveness-check` reports the same gap. From [`src/type-safety/exhaustive.ts`](../examples/src/type-safety/exhaustive.ts):

```ts
// Exhaustive switch with discriminated union
export function renderState(state: RequestState): string {
  switch (state.status) {
    case "loading":
      return "Loading…";
    case "success":
      return state.data.join(", ");
    case "error":
      return state.error.message;
    default: {
      const _exhaustive: never = state;
      throw new Error(`Unhandled state: ${JSON.stringify(_exhaustive)}`);
    }
  }
}
```

## `satisfies`

Use `satisfies` to check a value against a type without widening it to that type. An annotation, `const endpoints: Record<string, Endpoint>`, would accept any key and forget which member each entry is. With `satisfies`, the compiler checks every entry and keeps each one's own type. From [`src/type-safety/satisfies.ts`](../examples/src/type-safety/satisfies.ts):

```ts
const endpoints = {
  api: { url: "https://api.example.com" },
  worker: { socket: "/run/worker.sock" },
} satisfies Record<string, Endpoint>;
```

Under `isolatedDeclarations`, an exported value needs a type annotation, so use `satisfies` on values the module keeps to itself.

## Generic, conditional, and mapped types

- Use the standard library's types: `Partial`, `Required`, `Readonly`, `Pick`, `Omit`, `Record`, `NonNullable`, `ReturnType`, `Awaited`, and the string types `Uppercase`, `Lowercase`, `Capitalize`, and `Uncapitalize`. Never declare a type of your own with one of those names. It hides the built-in one.
- Constrain a type parameter to what the code uses, as in `K extends keyof T`. Use a type parameter in at least two places, or it adds nothing.
- Keep conditional, mapped, and template literal types for library code whose callers gain from them. Test each one with a type test.
- A function's return type is covariant and its parameter types are contravariant under `strict`. So `() => "a"` can be used where `() => string` is expected, and `(value: string) => void` where `(value: "a") => void` is expected, but not the other way round. This holds for function types, not for methods, whose parameters TypeScript checks both ways.
