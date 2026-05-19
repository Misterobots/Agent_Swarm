import { Suspense } from "react";
import { ArtGenerator } from "@/components/art-studio/art-generator";

export default function ArtStudioPage() {
  return (
    <Suspense>
      <ArtGenerator />
    </Suspense>
  );
}
