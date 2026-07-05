# Migration Notes

## `logEvent` → `trackEvent`

`analytics.ts` deprecated `logEvent(name, payload)` in favor of
`trackEvent(name, payload)`, which has the same signature. All call sites
in `src/` have been migrated:

- `src/orders.ts`
  - `createOrder` — `order_created`
  - `shipOrder` — `order_status_changed` (status: `"shipped"`)
  - `cancelOrder` — `order_status_changed` (status: `"cancelled"`)
- `src/notifications.ts`
  - `sendOrderShippedNotification` — `notification_sent` (type: `"order_shipped"`)
  - `sendOrderCancelledNotification` — `notification_sent` (type: `"order_canceled"`)

`logEvent` itself remains in `analytics.ts`, still marked `@deprecated`,
for backward compatibility. No production code calls it anymore.

## `order_cancelled` → `order_canceled` event type

The `notification_sent` event's `type` payload value emitted by
`sendOrderCancelledNotification` (`src/notifications.ts`) was renamed from
`"order_cancelled"` to `"order_canceled"` for spelling consistency with
the rest of the analytics event vocabulary.

This rename is scoped to that one event-type string. It does **not**
affect:

- The `sendOrderCancelledNotification` function name.
- The `OrderStatus` type's `"cancelled"` value or `order.status` in
  `src/orders.ts`.
- The `order_status_changed` event's `status: "cancelled"` payload field
  in `src/orders.ts`.
- User-facing notification subject/body text (still reads "cancelled").

Any downstream analytics consumers filtering on
`payload.type === "order_cancelled"` for the `notification_sent` event
must update to `"order_canceled"`.
