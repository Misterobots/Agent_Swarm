// Placeholder until the cross-platform Desktop builds exist (Phase C of
// plans/peppy-orbiting-honey.md — electron-builder currently only has a
// Windows/nsis target configured). Deliberately honest rather than linking to
// a private repo's releases or a build that doesn't exist yet.
import Link from "next/link";

export default function DownloadPage() {
  return (
    <div className="landing">
      <main className="landing-hero" style={{ gridTemplateColumns: "1fr", paddingTop: "4rem", paddingBottom: "4rem" }}>
        <div className="landing-hero-copy">
          <p className="landing-eyebrow">Downloads</p>
          <h1 className="landing-headline">Not published yet.</h1>
          <p className="landing-subhead">
            Windows, macOS, and Linux installers are being built out. In the
            meantime, the Desktop app runs from source — see the docs for the
            local build steps.
          </p>
          <div className="landing-ctas">
            <Link href="/docs" className="landing-cta-primary">Read the docs</Link>
            <Link href="/" className="landing-cta-secondary">Back home</Link>
          </div>
        </div>
      </main>
    </div>
  );
}
