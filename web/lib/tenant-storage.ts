"use client";

const ACTIVE_TENANT_KEY = "prompt-similarity.active-tenant";

export function readStoredTenantId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(ACTIVE_TENANT_KEY);
}

export function writeStoredTenantId(tenantId: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(ACTIVE_TENANT_KEY, tenantId);
}
