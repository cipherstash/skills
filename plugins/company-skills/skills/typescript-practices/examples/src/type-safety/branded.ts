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
