import { useState } from "react";
import { BookshelfPage } from "./components/BookshelfPage";
import { MetadataPage } from "./components/MetadataPage";
import { OokChatPage } from "./components/OokChatPage";
import { OpsPage } from "./components/OpsPage";
import { Shell } from "./components/Shell";
import { SimilarityGraph } from "./components/SimilarityGraph";
import { UploadPage } from "./components/UploadPage";

type TabId = "bookshelf" | "new-book" | "ook-chat" | "ops" | "graph";

interface UploadContext {
  sessionId: string;
  bucket: string;
  key: string;
  filename: string;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>("bookshelf");
  const [uploadCtx, setUploadCtx] = useState<UploadContext | null>(null);
  const [graphFocusId, setGraphFocusId] = useState<string | null>(null);

  function handleUploadComplete(sessionId: string, bucket: string, key: string, filename: string) {
    setUploadCtx({ sessionId, bucket, key, filename });
  }

  function handleResetUpload() {
    setUploadCtx(null);
  }

  function handleNavigateTab(tab: TabId) {
    // Clear upload context when leaving the new-book tab to ensure each session is independent
    if (activeTab === "new-book" && tab !== "new-book") {
      setUploadCtx(null);
    }
    setActiveTab(tab);
  }

  function handleNavigateToNewBook() {
    setActiveTab("new-book");
    setUploadCtx(null);
  }

  function renderContent() {
    switch (activeTab) {
      case "bookshelf":
        return (
          <BookshelfPage
            onNavigateToNewBook={handleNavigateToNewBook}
            onViewGraph={(bookId) => { setGraphFocusId(bookId); setActiveTab("graph"); }}
          />
        );
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
      case "ops":
        return <OpsPage onNavigateToNewBook={handleNavigateToNewBook} />;
      case "graph":
        return <SimilarityGraph focusBookId={graphFocusId} onClearFocus={() => setGraphFocusId(null)} />;
    }
  }

  return (
    <Shell active={activeTab} onNav={handleNavigateTab}>
      {renderContent()}
    </Shell>
  );
}
