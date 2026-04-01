import { useState } from "react";
import { MetadataPage } from "./components/MetadataPage";
import { Shell } from "./components/Shell";
import { UploadPage } from "./components/UploadPage";

interface UploadContext {
  sessionId: string;
  bucket: string;
  key: string;
  filename: string;
}

export default function App() {
  const [uploadCtx, setUploadCtx] = useState<UploadContext | null>(null);

  function handleUploadComplete(sessionId: string, bucket: string, key: string, filename: string) {
    setUploadCtx({ sessionId, bucket, key, filename });
  }

  function handleNewBook() {
    setUploadCtx(null);
  }

  return (
    <Shell active="new-book" onNav={handleNewBook}>
      {uploadCtx ? (
        <MetadataPage
          sessionId={uploadCtx.sessionId}
          bucket={uploadCtx.bucket}
          s3Key={uploadCtx.key}
          filename={uploadCtx.filename}
          onReset={handleNewBook}
        />
      ) : (
        <UploadPage onUploadComplete={handleUploadComplete} />
      )}
    </Shell>
  );
}
