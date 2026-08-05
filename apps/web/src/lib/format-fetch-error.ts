/** Normalize browser fetch errors to COPY_GUIDE recovery copy. */
export function formatFetchError(message: string): string {
  if (/failed to fetch|networkerror|load failed|connection refused/i.test(message)) {
    return "Couldn't reach your Odoo instance. Check the URL and that the instance is up, then retry.";
  }
  return message;
}
