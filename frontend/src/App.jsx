import { useState } from 'react';
import { useAuth } from './state/auth';
import { useConversation } from './state/conversation';
import LoginPage from './components/LoginPage';
import Header from './components/Header';
import ChatColumn from './components/ChatColumn';
import AnalysisPanel from './components/AnalysisPanel';
import CompareView from './components/CompareView';
import AboutModal from './components/AboutModal';

function MainApp() {
  const { user, signOut } = useAuth();
  const conv = useConversation();
  const [aboutOpen, setAboutOpen] = useState(false);

  return (
    <div className="min-h-screen bg-ink text-silver flex flex-col">
      <Header
        threshold={conv.threshold}
        onThresholdChange={conv.setThreshold}
        domain={conv.domain}
        onDomainChange={conv.setDomain}
        compareMode={conv.compareMode}
        onToggleCompare={conv.toggleCompareMode}
        onOpenAbout={() => setAboutOpen(true)}
        onNewConversation={conv.clearConversation}
        user={user}
        onSignOut={signOut}
      />

      <main className="flex-1 p-4 grid grid-cols-1 lg:grid-cols-2 gap-4 max-w-7xl w-full mx-auto">
        <div className="h-[78vh] min-h-[460px]">
          <ChatColumn
            messages={conv.messages}
            domain={conv.domain}
            loading={conv.loading}
            loadingStep={conv.loadingStep}
            error={conv.error}
            feedbackByMessage={conv.feedbackByMessage}
            onSend={conv.sendSentence}
            onRetry={conv.retry}
            onSubmitClarification={conv.submitClarification}
            onFeedback={conv.recordFeedback}
          />
        </div>

        <div className="h-[78vh] min-h-[460px]">
          {conv.compareMode ? (
            <CompareView
              baselineResult={conv.baselineResult}
              result={conv.latestResult}
              threshold={conv.threshold}
              overriddenId={conv.overriddenId}
              onSelectInterpretation={conv.overrideInterpretation}
              onReanalyze={conv.reanalyzeWithThreshold}
            />
          ) : (
            <AnalysisPanel
              result={conv.latestResult}
              threshold={conv.threshold}
              overriddenId={conv.overriddenId}
              onSelectInterpretation={conv.overrideInterpretation}
              onReanalyze={conv.reanalyzeWithThreshold}
            />
          )}
        </div>
      </main>

      <AboutModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
    </div>
  );
}

export default function App() {
  const { user } = useAuth();
  const required = import.meta.env.VITE_AUTH_REQUIRED === 'true';
  if (required && !user) return <LoginPage />;
  return <MainApp />;
}
