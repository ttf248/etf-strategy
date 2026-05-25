import { ReportDetailView } from "@/components/report-detail-view";

type ReportDetailPageProps = {
  params: Promise<{ id: string }>;
};

export default async function ReportDetailPage({ params }: ReportDetailPageProps) {
  const resolved = await params;
  return <ReportDetailView reportId={resolved.id} />;
}
