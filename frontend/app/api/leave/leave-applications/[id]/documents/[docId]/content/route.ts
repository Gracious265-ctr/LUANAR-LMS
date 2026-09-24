import { cookies } from "next/headers";

const DJANGO_API_URL = process.env.DJANGO_API_URL || "http://localhost:8000";

/**
 * Stream the document bytes from Django, forwarding status, content-type and
 * content-disposition (so ``?download=1`` still attaches the filename). The
 * access token travels in the cookie and is replayed as a Bearer header.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; docId: string }> }
) {
  const { id, docId } = await params;
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("access_token")?.value;

  const headers: Record<string, string> = {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const upstream = await fetch(
    `${DJANGO_API_URL}/api/v1/leave-applications/${id}/documents/${docId}/content/`,
    { headers }
  );

  const responseHeaders = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) responseHeaders.set("Content-Type", contentType);
  const contentDisposition = upstream.headers.get("content-disposition");
  if (contentDisposition) {
    responseHeaders.set("Content-Disposition", contentDisposition);
  }

  if (!upstream.ok || !upstream.body) {
    return new Response(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: responseHeaders,
    });
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}