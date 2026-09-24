export type HealthResponse = {
  status: "ok" | "degraded";
  database: "ok" | "unavailable";
  version: string;
};

const baseUrl = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${baseUrl}/api/health/`);
  if (response.status !== 200 && response.status !== 503) {
    throw new Error(`Health request failed (${response.status}).`);
  }

  const data: unknown = await response.json();
  if (
    typeof data !== "object" ||
    data === null ||
    !("status" in data) ||
    !("database" in data) ||
    !("version" in data) ||
    typeof data.version !== "string" ||
    !(
      (response.status === 200 && data.status === "ok" && data.database === "ok") ||
      (response.status === 503 &&
        data.status === "degraded" &&
        data.database === "unavailable")
    )
  ) {
    throw new Error("Unexpected health response.");
  }
  return data as HealthResponse;
}
