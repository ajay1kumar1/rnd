import { trackEvent } from "./analytics";
import {
  sendOrderCancelledNotification,
  sendOrderShippedNotification,
} from "./notifications";

export type OrderStatus =
  | "processing"
  | "shipped"
  | "delivered"
  | "cancelled"
  | "returned";

export interface OrderItem {
  sku: string;
  name: string;
  quantity: number;
  price: number;
}

export interface Order {
  orderId: string;
  email: string;
  status: OrderStatus;
  items: OrderItem[];
  trackingNumber: string | null;
}

const orders = new Map<string, Order>();

export function createOrder(order: Order): Order {
  orders.set(order.orderId, order);
  trackEvent("order_created", {
    orderId: order.orderId,
    email: order.email,
    itemCount: order.items.length,
  });
  return order;
}

export function getOrder(orderId: string): Order | undefined {
  return orders.get(orderId);
}

export function shipOrder(orderId: string, trackingNumber: string): Order {
  const order = orders.get(orderId);
  if (!order) {
    throw new Error(`No order found with orderId '${orderId}'`);
  }

  order.status = "shipped";
  order.trackingNumber = trackingNumber;

  trackEvent("order_status_changed", { orderId, status: "shipped" });
  sendOrderShippedNotification(order.email, orderId, trackingNumber);

  return order;
}

export function cancelOrder(orderId: string): Order {
  const order = orders.get(orderId);
  if (!order) {
    throw new Error(`No order found with orderId '${orderId}'`);
  }

  order.status = "cancelled";

  trackEvent("order_status_changed", { orderId, status: "cancelled" });
  sendOrderCancelledNotification(order.email, orderId);

  return order;
}

export function clearOrders(): void {
  orders.clear();
}
