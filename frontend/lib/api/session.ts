let closed = false;
const inFlight = new Set<AbortController>();

export function isSessionClosed(): boolean {
  return closed;
}

export function closeSession(): void {
  closed = true;
  for (const controller of inFlight) {
    controller.abort();
  }
  inFlight.clear();
}

export function openSession(): void {
  closed = false;
}

export function trackRequest(controller: AbortController): void {
  inFlight.add(controller);
}

export function untrackRequest(controller: AbortController): void {
  inFlight.delete(controller);
}