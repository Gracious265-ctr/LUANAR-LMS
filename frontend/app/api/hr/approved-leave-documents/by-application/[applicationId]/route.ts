import { apiFetch } from "@/app/api/_lib/api-fetch";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ applicationId: string }> }
) {
  const { applicationId } = await params;
  return apiFetch(
    "GET",
    `hr/approved-leave-documents/by-application/${applicationId}/`
  );
}
