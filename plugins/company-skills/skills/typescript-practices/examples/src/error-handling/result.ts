export type Result<T, E> =
  | { data: T; failure?: never }
  | { data?: never; failure: E };

export type PortFailure = {
  type: "NotANumber" | "OutOfRange";
  message: string;
};

export function parsePort(input: string): Result<number, PortFailure> {
  const port = Number(input);
  if (!Number.isInteger(port)) {
    return {
      failure: {
        type: "NotANumber",
        message: `port "${input}" is not a number`,
      },
    };
  }
  if (port < 1 || port > 65535) {
    return {
      failure: {
        type: "OutOfRange",
        message: `port ${port} is not 1 to 65535`,
      },
    };
  }
  return { data: port };
}
