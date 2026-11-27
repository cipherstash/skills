export interface User {
  type: "user";
  name: string;
  email: string;
}

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
