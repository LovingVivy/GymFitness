const API_BASE = "/api/v1";

export class ApiError extends Error {
  constructor(message, code, status) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

function extractMessage(data) {
  return (
    data?.error?.message ||
    data?.detail?.error?.message ||
    (Array.isArray(data?.detail) ? data.detail[0]?.msg : null) ||
    "Có lỗi xảy ra, vui lòng thử lại."
  );
}

/**
 * Call the backend. The API answers with {"error": {code, message}} on
 * failure, so every throw carries a code the caller can branch on.
 */
export async function request(path, { method = "GET", body, token } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new ApiError(extractMessage(data), data?.error?.code, response.status);
  }
  return data;
}
