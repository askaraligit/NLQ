function parseApiUrl(value: string | undefined): string {
  const message =
    "NEXT_PUBLIC_API_URL must be an absolute HTTP(S) URL without credentials, a query, or a fragment. Copy apps/web/.env.example to apps/web/.env.local and configure it.";

  if (!value?.trim()) {
    throw new Error(message);
  }

  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(message);
  }

  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  ) {
    throw new Error(message);
  }

  return url.toString().replace(/\/$/, "");
}

// A direct property access lets Next.js inline this public setting in client code.
export const publicEnv = Object.freeze({
  apiUrl: parseApiUrl(process.env.NEXT_PUBLIC_API_URL),
});
