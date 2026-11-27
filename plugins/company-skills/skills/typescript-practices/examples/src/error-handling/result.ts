export type Result<T, E> =
  | { data: T; failure?: never }
  | { data?: never; failure: E };

export type PortFailure = {
  type: "NotANumber" | "OutOfRange";
  message: string;
};

export function parsePort(input: string): Result<number, PortFailure> {
  // Number() also accepts "", " 80 ", "0x50", and "1e3", so check the text first.
  if (!/^[0-9]+$/.test(input)) {
    return {
      failure: {
        type: "NotANumber",
        message: `port "${input}" is not a number`,
      },
    };
  }
  const port = Number(input);
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
