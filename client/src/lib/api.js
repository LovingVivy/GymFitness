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

/** Upload a file as multipart/form-data (field name `file`). */
export async function upload(path, file, { token } = {}) {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(extractMessage(data), data?.error?.code, response.status);
  }
  return data;
}

function filenameFrom(disposition, fallback) {
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition || "");
  return match ? decodeURIComponent(match[1]) : fallback;
}

/**
 * Download a private file (export, invoice, template) with the bearer token,
 * then hand it to the browser as a normal download.
 */
export async function download(url, { token, fallbackName = "tai-ve" } = {}) {
  const target = url.startsWith("/api/") ? url : `${API_BASE}${url}`;
  const response = await fetch(target, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(extractMessage(data), data?.error?.code, response.status);
  }
  const blob = await response.blob();
  const name = filenameFrom(response.headers.get("Content-Disposition"), fallbackName);
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(link.href), 10_000);
  return name;
}
