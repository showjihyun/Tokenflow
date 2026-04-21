import { ApiError } from "../api/client";
import type { ErrorVariant } from "../components/ErrorState";

/**
 * Map a thrown error to the closest SPEC §10.4 error taxonomy variant so the
 * user sees actionable copy ("retry", "fix API key", etc.) instead of a raw
 * ``500 Internal Server Error`` string. Non-ApiError throws (network down,
 * thrown ``Error``) fall through to ``generic``.
 */
export function errorVariantFrom(err: unknown): ErrorVariant {
  if (err instanceof ApiError) {
    if (err.status === 401 || err.status === 403) return "api_key_invalid";
    if (err.status === 429) return "rate_limit";
    if (err.status >= 500 && err.status < 600) return "upstream_5xx";
  }
  return "generic";
}
