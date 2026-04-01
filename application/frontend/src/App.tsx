import { useState } from "react";
import { BookshelfPage } from "./components/BookshelfPage";
import { MetadataPage } from "./components/MetadataPage";
import { OokChatPage } from "./components/OokChatPage";
import { Shell } from "./components/Shell";
import { UploadPage } from "./components/UploadPage";

type TabId = "bookshelf" | "new-book" | "ook-chat";

interface UploadContext {
  sessionId: string;
  bucket: string;
  key: string;
  filename: string;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>("bookshelf");
  const [uploadCtx, setUploadCtx] = useState<UploadContext | null>(null);

  function handleUploadComplete(sessionId: string, bucket: string, key: string, filename: string) {
    setUploadCtx({ sessionId, bucket, key, filename });
  }

  function handleResetUpload() {
    setUploadCtx(null);
  }

  function handleNavigateTab(tab: TabId) {
    setActiveTab(tab);
  }

  function handleNavigateToNewBook() {
    setActiveTab("new-book");
    setUploadCtx(null);
  }

  function renderContent() {
    switch (activeTab) {
      case "bookshelf":
        return <BookshelfPage onNavigateToNewBook={handleNavigateToNewBook} />;
      case "new-book":
        return uploadCtx ? (
          <MetadataPage
            sessionId={uploadCtx.sessionId}
            bucket={uploadCtx.bucket}
            s3Key={uploadCtx.key}
            filename={uploadCtx.filename}
            onReset={handleResetUpload}
          />
        ) : (
          <UploadPage onUploadComplete={handleUploadComplete} />
        );
      case "ook-chat":
        return <OokChatPage />;
    }
  }

  return (
    <Shell active={activeTab} onNav={handleNavigateTab}>
      {renderContent()}
    </Shell>
  );
}
