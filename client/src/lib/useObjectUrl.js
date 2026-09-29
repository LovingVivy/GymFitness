import { useEffect, useState } from "react";

/**
 * Turn an authorised file URL into a displayable object URL.
 *
 * Uploaded files are private, so an <img src> cannot fetch them directly — the
 * bearer token has to travel in the request. This hook fetches the bytes once
 * and hands back a blob URL, revoking it on cleanup.
 */
export function useObjectUrl(remoteUrl, token) {
  const [objectUrl, setObjectUrl] = useState("");

  useEffect(() => {
    if (!remoteUrl || !token) {
      setObjectUrl("");
      return undefined;
    }

    let created = "";
    let cancelled = false;

    fetch(remoteUrl, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => (response.ok ? response.blob() : null))
      .then((blob) => {
        if (!blob || cancelled) return;
        created = URL.createObjectURL(blob);
        setObjectUrl(created);
      })
      .catch(() => {
        /* ảnh lỗi thì rơi về chữ viết tắt */
      });

    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [remoteUrl, token]);

  return objectUrl;
}
