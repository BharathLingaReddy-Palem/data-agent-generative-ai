import Markdown from '../components/Markdown';
// ChatPage.jsx — Conversational AI Analyst with streaming-style display
import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, MessageSquare, User, Bot, Code, Loader2 } from 'lucide-react';
import { sendChatMessage } from '../api';
import { useStore, useProjectState } from '../useStore';

export function Message({ msg }) {
  const isUser = msg.role === 'user';
  const failed = msg.execution_status === 'failed' || /PolicyError|Executed code produced:|timed out/i.test(msg.evidence || '');
  const verified = msg.execution_status === 'succeeded';
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex gap-3"
      style={{ marginBottom: 16, flexDirection: isUser ? 'row-reverse' : 'row' }}
    >
      {/* Avatar */}
      <div style={{
        width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: isUser ? 'rgba(168, 85, 247, 0.2)' : 'rgba(0, 255, 136, 0.12)',
        border: `1px solid ${isUser ? 'rgba(168,85,247,0.4)' : 'var(--accent-green-border)'}`,
      }}>
        {isUser
          ? <User size={14} style={{ color: '#a855f7' }} />
          : <Bot size={14} style={{ color: 'var(--accent-green)' }} />
        }
      </div>

      {/* Bubble */}
      <div className="chat-bubble-wrap">
        <div style={{
          background: isUser ? 'rgba(168, 85, 247, 0.08)' : 'var(--bg-elevated)',
          border: `1px solid ${isUser ? 'rgba(168,85,247,0.2)' : 'var(--border-subtle)'}`,
          borderRadius: isUser ? '12px 4px 12px 12px' : '4px 12px 12px 12px',
          padding: '12px 16px',
        }}>
          <Markdown>{msg.content}</Markdown>
        </div>

        {/* Code evidence */}
        {msg.code && (
          <details className="calculation-details">
            <summary className="flex items-center gap-2" style={{ padding: '6px 12px', borderBottom: '1px solid var(--border-subtle)', background: 'rgba(255,255,255,0.02)' }}>
              <Code size={12} style={{ color: 'var(--accent-green)' }} />
              <span className="text-xs text-secondary">{failed ? "Calculation attempt" : verified ? "View calculation code" : "Suggested code"}</span>
            </summary>
            <pre style={{ padding: '10px 12px', fontSize: '0.75rem', color: 'var(--text-secondary)', overflowX: 'auto', margin: 0 }}>
              <code>{msg.code}</code>
            </pre>
          </details>
        )}

        {(msg.evidence || msg.calculation_error) && (
          <div style={{
            marginTop: 6,
            padding: '8px 12px',
            background: 'rgba(0, 255, 136, 0.04)',
            border: '1px solid var(--accent-green-border)',
            borderRadius: 8,
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '0.78rem',
            color: failed ? 'var(--accent-red)' : 'var(--text-secondary)',
          }} role={failed ? 'alert' : 'status'}>
            <strong>{failed ? 'Calculation failed' : verified ? 'Calculation succeeded' : 'Saved evidence (not reverified)'}</strong>
            {failed ? <p style={{marginTop:6}}>{msg.calculation_error || msg.evidence}</p> : <details className="evidence-details"><summary>View calculated evidence</summary><pre>{msg.evidence}</pre></details>}
          </div>
        )}
      </div>
    </motion.div>
  );
}

const STARTER_PROMPTS = [
  'What are the top 3 insights from this dataset?',
  'Which columns have the highest correlation with the target?',
  'Summarize the data quality issues found',
  'What percentage of records have missing values?',
  'What is the average and median of the numeric columns?',
];

export default function ChatPage() {
  const { state } = useStore();
  const { projectId, datasetName, profile } = state;
  const [messages, setMessages] = useProjectState('chatMessages');
  const [input, setInput] = useProjectState('chatInput');
  const [loading, setLoading] = useProjectState('chatLoading');
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'instant', block:'nearest' });
  }, [messages]);

  const sendMsg = async (text) => {
    if (!text.trim() || !projectId || loading) return;
    const userMsg = { role: 'user', content: text };
    setMessages((m) => [...m, userMsg]);
    setInput('');
    setLoading(true);
    try {
      const res = await sendChatMessage(projectId, text);
      setMessages((m) => [...m, {
        role: 'assistant',
        content: res.reply,
        code: res.code_executed,
        evidence: res.calculated_evidence,
        execution_status: res.execution_status,
        calculation_error: res.calculation_error,
      }]);
    } catch (err) {
      setMessages((m) => [...m, {
        role: 'assistant',
        content: `❌ Error: ${err.message}`,
      }]);
    } finally {
      setLoading(false);
    }
  };

  if (!projectId) {
    return (
      <div className="flex items-center justify-center" style={{ height: '60vh', flexDirection: 'column', gap: 16 }}>
        <MessageSquare size={40} style={{ color: 'var(--text-tertiary)' }} />
        <p className="text-secondary">Upload a dataset first</p>
      </div>
    );
  }

  return (
    <div className="chat-page">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex items-center gap-3 mb-4"
      >
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: 'rgba(0, 255, 136, 0.12)',
          border: '1px solid var(--accent-green-border)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Bot size={20} style={{ color: 'var(--accent-green)' }} />
        </div>
        <div>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Conversational Data Analyst</h2>
          <p className="text-xs text-tertiary">
            Ask anything about <strong style={{ color: 'var(--text-secondary)' }}>{datasetName}</strong> · Evidence shown when a calculation succeeds
          </p>
        </div>
      </motion.div>

      {/* Messages */}
      <div className="chat-messages" aria-live="polite">
        {messages.length === 0 ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <div className="card" style={{ textAlign: 'center', padding: '32px 24px', marginBottom: 20 }}>
              <Bot size={32} style={{ color: 'var(--accent-green)', margin: '0 auto 12px' }} />
              <p className="font-semibold text-primary mb-2">Ask me anything about your data</p>
              <p className="text-xs text-tertiary">
                Ask a focused question. Successful calculations include evidence; uncertain answers are identified.
              </p>
            </div>
            <div className="section-title">Suggested Questions</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {STARTER_PROMPTS.map((p) => (
                <button
                  key={p}
                  className="btn btn-ghost"
                  style={{ justifyContent: 'flex-start', textAlign: 'left', height: 'auto', padding: '10px 14px' }}
                  onClick={() => sendMsg(p)}
                >
                  <span className="text-xs" style={{ color: 'var(--accent-green)' }}>→</span>
                  <span className="text-sm">{p}</span>
                </button>
              ))}
            </div>
          </motion.div>
        ) : (
          <div>
            {messages.map((msg, i) => <Message key={i} msg={msg} />)}
            {loading && (
              <div className="flex gap-3 mb-4">
                <div style={{
                  width: 32, height: 32, borderRadius: '50%',
                  background: 'rgba(0, 255, 136, 0.12)',
                  border: '1px solid var(--accent-green-border)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Bot size={14} style={{ color: 'var(--accent-green)' }} />
                </div>
                <div style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '4px 12px 12px 12px',
                  padding: '14px 16px',
                  display: 'flex', gap: 6, alignItems: 'center',
                }}>
                  {[0, 1, 2].map((i) => (
                    <div key={i} style={{
                      width: 6, height: 6, borderRadius: '50%',
                      background: 'var(--accent-green)',
                      animation: `pulse-green 1.2s ${i * 0.2}s infinite`,
                    }} />
                  ))}
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div style={{ paddingTop: 12 }}>
        <div className="flex gap-3" style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-medium)',
          borderRadius: 'var(--radius-lg)',
          padding: '8px 8px 8px 16px',
        }}>
          <input
            className="input"
            style={{ background: 'transparent', border: 'none', flex: 1, padding: '4px 0' }}
            aria-label="Message to analyst"
            placeholder="Ask anything about your data…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMsg(input)}
            disabled={loading}
          />
          <button
            className="btn btn-primary"
            style={{ padding: '8px 16px', borderRadius: 10 }}
            aria-label="Send message"
            onClick={() => sendMsg(input)}
            disabled={!input.trim() || loading}
          >
            {loading ? <Loader2 size={15} className="spin" /> : <Send size={15} />}
          </button>
        </div>
        <p className="text-xs text-tertiary mt-2" style={{ textAlign: 'center' }}>
          Press Enter to send · Review the evidence before making decisions
        </p>
      </div>
    </div>
  );
}
