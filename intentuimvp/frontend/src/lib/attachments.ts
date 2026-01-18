export type AttachmentStatus = "pending" | "processing" | "ready" | "error";

export type AttachmentItem = {
  id: string;
  name: string;
  mimeType: string;
  sizeBytes: number;
  attachmentType: string;
  status: AttachmentStatus;
  previewUrl?: string;
  textPreview?: string;
  descriptionPreview?: string;
  errorMessage?: string | null;
  sourceKey?: string;
};

export type AttachmentApiResponse = {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  attachment_type: string;
  status: string;
  text_preview?: string | null;
  description_preview?: string | null;
  error_message?: string | null;
  content_url: string;
  preview_url?: string | null;
};

export type AttachmentListResponse = {
  attachments: AttachmentApiResponse[];
  count: number;
  max_bytes: number;
};

export const formatBytes = (bytes: number): string => {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unitIndex]}`;
};

export const resolveAttachmentUrl = (
  baseUrl: string,
  path?: string | null
): string | undefined => {
  if (!path) {
    return undefined;
  }
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  if (path.startsWith("/")) {
    return `${baseUrl}${path}`;
  }
  return `${baseUrl}/${path}`;
};

export const normalizeAttachment = (
  api: AttachmentApiResponse,
  baseUrl: string
): AttachmentItem => ({
  id: api.id,
  name: api.filename,
  mimeType: api.mime_type,
  sizeBytes: api.size_bytes,
  attachmentType: api.attachment_type,
  status: (api.status as AttachmentStatus) ?? "processing",
  previewUrl: resolveAttachmentUrl(baseUrl, api.preview_url ?? api.content_url),
  textPreview: api.text_preview ?? undefined,
  descriptionPreview: api.description_preview ?? undefined,
  errorMessage: api.error_message ?? undefined,
});
