type LoadingState = { status: "loading" };
type SuccessState = { status: "success"; data: string[] };
type ErrorState = { status: "error"; error: Error };
export type RequestState = LoadingState | SuccessState | ErrorState;

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
