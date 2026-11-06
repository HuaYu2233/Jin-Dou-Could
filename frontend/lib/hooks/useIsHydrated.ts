"use client";

import { useSyncExternalStore } from "react";

function subscribe(): () => void {
  return () => {};
}

export function useIsHydrated(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false
  );
}