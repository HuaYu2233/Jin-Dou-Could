import { client } from "./client";

export interface EnvConfigField {
  key: string;
  value: string;
  group: string;
  hint: string;
  required: boolean;
  sensitive: boolean;
}

export interface EnvConfigGroup {
  name: string;
  fields: EnvConfigField[];
}

export interface EnvConfigResponse {
  enabled: boolean;
  path: string;
  backup: string | null;
  groups: EnvConfigGroup[];
}

export interface EnvConfigSaveResponse {
  ok: boolean;
  path: string;
  backup: string;
  errors: string[];
}

export function getEnvConfig(): Promise<EnvConfigResponse> {
  return client<EnvConfigResponse>("/api/v1/admin/env-config");
}

export function saveEnvConfig(values: Record<string, string>): Promise<EnvConfigSaveResponse> {
  return client<EnvConfigSaveResponse>("/api/v1/admin/env-config/save", {
    method: "POST",
    body: JSON.stringify({ values }),
  });
}

export function generateEnvValues(): Promise<Record<string, string>> {
  return client<Record<string, string>>("/api/v1/admin/env-config/generate", {
    method: "POST",
  });
}