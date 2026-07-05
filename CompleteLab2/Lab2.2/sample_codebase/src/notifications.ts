import { trackEvent } from "./analytics";

export interface Notification {
  email: string;
  subject: string;
  body: string;
}

const sentNotifications: Notification[] = [];

export function sendOrderShippedNotification(
  email: string,
  orderId: string,
  trackingNumber: string
): Notification {
  const notification: Notification = {
    email,
    subject: `Your order ${orderId} has shipped`,
    body: `Good news! Order ${orderId} is on its way. Tracking number: ${trackingNumber}.`,
  };

  sentNotifications.push(notification);
  trackEvent("notification_sent", { type: "order_shipped", email, orderId });

  return notification;
}

export function sendOrderCancelledNotification(
  email: string,
  orderId: string
): Notification {
  const notification: Notification = {
    email,
    subject: `Your order ${orderId} was cancelled`,
    body: `Order ${orderId} has been cancelled. Contact support if this wasn't expected.`,
  };

  sentNotifications.push(notification);
  trackEvent("notification_sent", { type: "order_canceled", email, orderId });

  return notification;
}

export function getSentNotifications(): ReadonlyArray<Notification> {
  return sentNotifications;
}

export function clearSentNotifications(): void {
  sentNotifications.length = 0;
}
