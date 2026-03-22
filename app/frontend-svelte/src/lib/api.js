const API_BASE = "";

export async function getConfig() {
  const response = await fetch(`${API_BASE}/api/config`);
  if (!response.ok) return null;
  return response.json();
}

export async function createSession() {
  const response = await fetch(`${API_BASE}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to create session: ${response.status} - ${text}`);
  }
  const data = await response.json();
  const sessionId = data.id ?? data.session_id;
  if (!sessionId) throw new Error("Session ID not found in response");
  return { session_id: sessionId };
}

export async function uploadFile(file, signal) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/api/upload`, {
    method: "POST",
    body: formData,
    signal,
  });
  if (!response.ok) {
    let msg = `Upload failed: ${response.status}`;
    try {
      const err = await response.json();
      msg = err.detail ?? msg;
    } catch {
      msg = (await response.text()) || msg;
    }
    throw new Error(msg);
  }
  const data = await response.json();
  if (data.status !== "success")
    throw new Error(data.error ?? "File upload failed");
  return {
    data: data.data,
    mimeType: data.mimeType,
    displayName: data.filename,
    serverFilename: data.serverFilename ?? data.filename,
  };
}

export async function deleteUploadedFile(filename) {
  if (!filename) return;
  const response = await fetch(
    `${API_BASE}/api/upload/${encodeURIComponent(filename)}`,
    {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    },
  );
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Delete failed: ${response.status} - ${text}`);
  }
  return response.json();
}

export async function streamQuery(
  {
    user_id,
    session_id,
    message_parts,
    api_key,
    use_vertex,
    vertex_project,
    vertex_location,
    model_id,
  },
  { signal, onChunk },
) {
  const body = {
    user_id,
    session_id,
    message_parts,
  };
  if (api_key) body.api_key = api_key;
  if (use_vertex) {
    body.use_vertex = true;
    if (vertex_project) body.vertex_project = vertex_project;
    if (vertex_location) body.vertex_location = vertex_location;
  }
  if (model_id) body.model_id = model_id;
  const response = await fetch(`${API_BASE}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const text = await response.text();
    let msg = `Query failed: ${response.status}`;
    try {
      const j = JSON.parse(text);
      if (j.detail)
        msg = typeof j.detail === "string" ? j.detail : `${msg} - ${text}`;
    } catch (_) {
      if (text) msg += ` - ${text}`;
    }
    throw new Error(msg);
  }
  if (!response.body) throw new Error("Response body is null");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    while (buffer.includes("\n\n")) {
      const end = buffer.indexOf("\n\n");
      const message = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const dataLines = message
        .split("\n")
        .filter((ln) => ln.startsWith("data: "));
      const jsonStr = dataLines
        .map((ln) => ln.slice(6))
        .join("\n")
        .trim();
      if (!jsonStr) continue;
      try {
        const event = JSON.parse(jsonStr);
        onChunk(event);
        if (event && typeof event.error === "string")
          throw new Error(event.error);
      } catch (e) {
        if (e instanceof SyntaxError) continue;
        throw e;
      }
    }
  }
}

export async function getLatestPdf() {
  const response = await fetch(`${API_BASE}/api/reports/latest-pdf`);
  if (!response.ok) return null;
  return response.json();
}

export function getDownloadUrl(filename) {
  return `${API_BASE}/api/reports/download/${encodeURIComponent(filename)}`;
}
