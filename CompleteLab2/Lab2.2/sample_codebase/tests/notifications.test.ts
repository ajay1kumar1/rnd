import {
  clearSentNotifications,
  getSentNotifications,
  sendOrderCancelledNotification,
  sendOrderShippedNotification,
} from "../src/notifications";
import { clearEventLog, getEventLog } from "../src/analytics";

describe("notifications", () => {
  beforeEach(() => {
    clearSentNotifications();
    clearEventLog();
  });

  it("sends a shipped notification and logs an analytics event", () => {
    const notification = sendOrderShippedNotification(
      "alice@example.com",
      "NP-100245",
      "FDX9284710385621"
    );

    expect(notification.email).toBe("alice@example.com");
    expect(notification.subject).toContain("NP-100245");
    expect(getSentNotifications()).toHaveLength(1);

    const events = getEventLog();
    expect(events).toHaveLength(1);
    expect(events[0].name).toBe("notification_sent");
    expect(events[0].payload).toMatchObject({
      type: "order_shipped",
      orderId: "NP-100245",
    });
  });

  it("sends a cancelled notification and logs an analytics event", () => {
    const notification = sendOrderCancelledNotification(
      "bob@example.com",
      "NP-100190"
    );

    expect(notification.subject).toContain("cancelled");
    expect(getEventLog()[0].payload).toMatchObject({
      type: "order_canceled",
      orderId: "NP-100190",
    });
  });
});
