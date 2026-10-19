import { DocumentsLibrary } from "@/components/documents/documents-library";
import { FadeIn } from "@/components/motion/FadeIn";

export default function DocumentsPage() {
  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">
            Documents
          </h2>
          <p className="text-text-secondary">
            Everything attached to or generated from your leave applications, in
            one place.
          </p>
        </div>

        <DocumentsLibrary />
      </div>
    </FadeIn>
  );
}
