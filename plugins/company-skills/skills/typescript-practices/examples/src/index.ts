// The package entry point. It exists so that publint and attw check the
// package's shape; the references quote the modules it re-exports.
export { readConfig } from "./error-handling/cause.js";
export {
  type PortFailure,
  parsePort,
  type Result,
} from "./error-handling/result.js";
export { assertIsUser, type User } from "./type-safety/assert-user.js";
export {
  getOrder,
  type OrderId,
  toOrderId,
  toUserId,
  type UserId,
} from "./type-safety/branded.js";
export { type RequestState, renderState } from "./type-safety/exhaustive.js";
export { apiUrl } from "./type-safety/satisfies.js";
