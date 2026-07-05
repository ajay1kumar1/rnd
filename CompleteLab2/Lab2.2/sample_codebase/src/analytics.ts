export interface EventPayload {
  [key: string]: unknown;
}

export interface LoggedEvent {
  name: string;
  payload: EventPayload;
  timestamp: string;
}

const eventLog: LoggedEvent[] = [];

/**
 * @deprecated Use `trackEvent` instead. `logEvent` will be removed in a
 * future release and is kept only for backward compatibility.
 */
export function logEvent(name: string, payload: EventPayload): void {
  eventLog.push({ name, payload, timestamp: new Date().toISOString() });
  console.log(`[analytics] ${name}`, payload);
}

export function trackEvent(name: string, payload: EventPayload): void {
  eventLog.push({ name, payload, timestamp: new Date().toISOString() });
  console.log(`[analytics] ${name}`, payload);
}

export function getEventLog(): ReadonlyArray<LoggedEvent> {
  return eventLog;
}

export function clearEventLog(): void {
  eventLog.length = 0;
}
