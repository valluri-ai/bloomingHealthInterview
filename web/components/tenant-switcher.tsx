"use client";

import { Plus, RefreshCw } from "lucide-react";
import { useState } from "react";

import type { TenantSeedType, TenantSummary } from "@/lib/types";


export function TenantSwitcher({
  tenants,
  activeTenantId,
  onTenantChange,
  onCreateTenant,
  busy = false,
  loading = false,
}: {
  tenants: TenantSummary[];
  activeTenantId: string;
  onTenantChange: (tenantId: string) => void;
  onCreateTenant: (input: { name: string; tenant_id?: string; seed_type: TenantSeedType }) => Promise<void>;
  busy?: boolean;
  loading?: boolean;
}) {
  const [isCreating, setIsCreating] = useState(false);
  const [name, setName] = useState("");
  const [tenantId, setTenantId] = useState("");
  const activeValue = tenants.some((tenant) => tenant.tenant_id === activeTenantId) ? activeTenantId : "";

  return (
    <div className="tenant-switcher">
      <div className="tenant-switcher-row">
        <label className="field compact-field tenant-field">
          <span>Tenant</span>
          <select
            value={activeValue}
            onChange={(event) => onTenantChange(event.target.value)}
            disabled={loading || busy || tenants.length === 0}
          >
            {!loading && tenants.length > 0 ? null : (
              <option value="">{loading ? "Loading tenants..." : "No tenants available"}</option>
            )}
            {tenants.map((tenant) => (
              <option key={tenant.tenant_id} value={tenant.tenant_id}>
                {tenant.name} · {tenant.prompt_count} prompts
              </option>
            ))}
          </select>
        </label>
        <button
          className="ghost-button tenant-create-toggle"
          type="button"
          onClick={() => setIsCreating((current) => !current)}
        >
          <Plus size={14} />
          {isCreating ? "Cancel" : "Create tenant"}
        </button>
      </div>
      <p className="tenant-switcher-note">
        Built-ins: 12 Prompt Sample and Benchmark 1K. New tenants start empty.
      </p>
      {isCreating ? (
        <div className="tenant-create-panel">
          <label className="field compact-field">
            <span>Name</span>
            <input value={name} onChange={(event) => setName(event.target.value)} placeholder="New tenant" />
          </label>
          <label className="field compact-field">
            <span>Tenant ID</span>
            <input value={tenantId} onChange={(event) => setTenantId(event.target.value)} placeholder="optional-slug" />
          </label>
          <button
            className="primary-button tenant-create-submit"
            type="button"
            disabled={busy || !name.trim()}
            onClick={async () => {
              await onCreateTenant({
                name: name.trim(),
                tenant_id: tenantId.trim() || undefined,
                seed_type: "empty",
              });
              setName("");
              setTenantId("");
              setIsCreating(false);
            }}
          >
            <RefreshCw size={14} />
            {busy ? "Creating..." : "Create and switch"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
