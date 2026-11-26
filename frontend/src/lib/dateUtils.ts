export const IST_TIMEZONE = "Asia/Kolkata";

export function parseBackendDate(input: string | number | Date): Date {
  if (input instanceof Date) return input;
  if (typeof input === "number") return new Date(input);
  const trimmed = String(input || "").trim();
  if (!trimmed) return new Date(NaN);

  // Preserve pure YYYY-MM-DD calendar dates (transactions, FD maturity dates) without shifting across midnight
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    return new Date(`${trimmed}T12:00:00+05:30`);
  }

  // If an ISO timestamp lacks an explicit timezone offset, treat it as stored UTC
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(trimmed)) {
    return new Date(`${trimmed.replace(" ", "T")}Z`);
  }

  return new Date(trimmed);
}

export const formatIST = (date: string | number | Date | null | undefined): string => {
  if (date === null || date === undefined || date === "") return "—";
  const parsed = parseBackendDate(date);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: IST_TIMEZONE,
    dateStyle: "medium",
    timeStyle: "short",
    hour12: true,
  }).format(parsed);
};

export const formatISTWithTz = (date: string | number | Date | null | undefined): string => {
  const formatted = formatIST(date);
  return formatted === "—" ? "—" : `${formatted} IST`;
};

export const formatISTDateOnly = (date: string | number | Date | null | undefined): string => {
  if (date === null || date === undefined || date === "") return "—";
  const parsed = parseBackendDate(date);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: IST_TIMEZONE,
    dateStyle: "medium",
  }).format(parsed);
};
