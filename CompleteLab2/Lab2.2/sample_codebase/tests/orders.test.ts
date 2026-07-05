import {
  cancelOrder,
  clearOrders,
  createOrder,
  getOrder,
  shipOrder,
} from "../src/orders";
import { clearEventLog, getEventLog } from "../src/analytics";
import { clearSentNotifications, getSentNotifications } from "../src/notifications";

describe("orders", () => {
  beforeEach(() => {
    clearOrders();
    clearEventLog();
    clearSentNotifications();
  });

  it("creates an order and logs an order_created event", () => {
    const order = createOrder({
      orderId: "NP-100245",
      email: "grace@example.com",
      status: "processing",
      items: [
        { sku: "SKU-142", name: "27in 4K Monitor", quantity: 1, price: 329.99 },
      ],
      trackingNumber: null,
    });

    expect(getOrder("NP-100245")).toEqual(order);
    expect(getEventLog()).toHaveLength(1);
    expect(getEventLog()[0].name).toBe("order_created");
  });

  it("ships an order, updates status, and triggers a notification", () => {
    createOrder({
      orderId: "NP-100190",
      email: "carol@example.com",
      status: "processing",
      items: [
        { sku: "SKU-620", name: "Monitor Stand", quantity: 1, price: 88.46 },
      ],
      trackingNumber: null,
    });

    const shipped = shipOrder("NP-100190", "784561239874");

    expect(shipped.status).toBe("shipped");
    expect(shipped.trackingNumber).toBe("784561239874");
    expect(getSentNotifications()).toHaveLength(1);

    const events = getEventLog();
    expect(events.some((e) => e.name === "order_status_changed")).toBe(true);
  });

  it("throws when shipping an unknown order", () => {
    expect(() => shipOrder("UNKNOWN", "xyz")).toThrow("No order found");
  });

  it("cancels an order and triggers a notification", () => {
    createOrder({
      orderId: "NP-100212",
      email: "erin@example.com",
      status: "processing",
      items: [{ sku: "SKU-455", name: "Desk Mat", quantity: 1, price: 42.0 }],
      trackingNumber: null,
    });

    const cancelled = cancelOrder("NP-100212");

    expect(cancelled.status).toBe("cancelled");
    expect(getSentNotifications()[0].subject).toContain("cancelled");
  });
});
