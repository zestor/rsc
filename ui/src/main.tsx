import React, { DragEvent, useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Bot, CheckCircle2, Download, FileText, Paperclip, Play, Search, Settings2, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Document as DocxDocument, Packer, Paragraph, TextRun, HeadingLevel } from 'docx';
import { jsPDF } from 'jspdf';
import './styles.css';

type SafeConfig = {
  llm_provider: string;
  loop_model: string;
  eval_model: string;
  search_provider: string;
  search_max_results: number;
  skill_top_k: number;
  skill_routing: string;
  skill_library_paths: string[];
  state_dir: string;
  log_dir: string;
  models: Array<{ provider: string; model: string; label: string }>;
  modes: Array<{ id: string; label: string; description: string }>;
  ui_available: boolean;
};

type RubricItem = { label: string; description: string };
type StreamEvent = { event: string; data: Record<string, unknown> };
type RunResponse = {
  session_id: string;
  status: string;
  final_score: number;
  turns_used: number;
  final_output: string;
  total_tokens_input: number;
  total_tokens_output: number;
  memory_rules_added: string[];
  turns: Array<Record<string, unknown>>;
};

type PlannerTask = { id: string; title: string; status: 'pending' | 'active' | 'complete' | 'failed' };
type RoleResponse = {
  role: string;
  turn: number;
  text: string;
  reasoningText: string;
  chars: number;
  reasoningChars: number;
  reasoningElapsed: number;
  responseElapsed: number;
  success: boolean;
};
type TurnTranscript = {
  turn: number;
  plannerTasks: PlannerTask[];
  roleResponses: RoleResponse[];
  activeRoleTab: string;
};
type SearchBlock = {
  id: string;
  provider: string;
  query: string;
  queryIndex: number;
  queryCount: number;
  content: string;
  status: 'active' | 'complete';
  resultCount: number;
  role: string;
  sequence: number;
};
type TimelineItem =
  | { kind: 'activity'; sequence: number; event: StreamEvent }
  | { kind: 'search'; sequence: number; block: SearchBlock }
  | { kind: 'turn-header'; sequence: number; turn: number }
  | { kind: 'role-response'; sequence: number; response: RoleResponse; plannerTasks: PlannerTask[] };
const ROLE_ORDER = ['planner', 'critic', 'verifier', 'reviser', 'synthesizer'];

const defaultRubric: RubricItem[] = [
  { label: 'complete', description: 'The answer fully satisfies the requested task.' },
  { label: 'correct', description: 'The answer is logically consistent and grounded where applicable.' },
];

function App() {
  const [config, setConfig] = useState<SafeConfig | null>(null);
  const [question, setQuestion] = useState('explain non-human intelligence modification of humanity, hybrids, flood, messiah who had lineage to seth and fathered by non-human intelligence');
  const [mode, setMode] = useState('research');
  const [model, setModel] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [searchBlocks, setSearchBlocks] = useState<SearchBlock[]>([]);
  const [turnTranscripts, setTurnTranscripts] = useState<TurnTranscript[]>([]);
  const [result, setResult] = useState<RunResponse | null>(null);
  const [submittedQuestion, setSubmittedQuestion] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [runElapsed, setRunElapsed] = useState(0);
  const runStartedAtRef = useRef(0);
  const sequenceCounterRef = useRef(0);
  const eventSequenceRef = useRef<number[]>([]);
  const roleResponseSequences = useRef<Map<string, number>>(new Map());
  const roleTimings = useRef<Map<string, { startedAt: number; reasoningDoneAt: number; responseStartedAt: number }>>(new Map());
  const [, forceRenderTick] = useState(0);
  const tickIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const transcriptRef = useRef<HTMLElement | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);
  const autoFollowTranscriptRef = useRef(true);

  useEffect(() => {
    fetchWithRetry('/api/config')
      .then((response) => response.json())
      .then((payload: SafeConfig) => {
        setConfig(payload);
        setMode(payload.modes?.[1]?.id || payload.modes?.[0]?.id || 'research');
        setModel(payload.models?.[0]?.model || payload.loop_model);
      })
      .catch((err) => setError(String(err)));
  }, []);

  const canSubmit = useMemo(() => question.trim().length > 0 && !loading, [question, loading]);
  const visibleEvents = useMemo(
    () => events.filter(
      (item) =>
        !item.event.startsWith('log.') &&
        !isSearchActivityEvent(item) &&
        item.event !== 'planner.tasks' &&
        item.event !== 'role.delta' &&
        item.event !== 'role.complete'
    ),
    [events]
  );

  const timeline = useMemo(() => {
    const items: TimelineItem[] = [];
    // Activity events
    visibleEvents.forEach((event, index) => {
      const seq = (event as StreamEvent & { _sequence?: number })._sequence
        ?? (eventSequenceRef.current[index] ?? index);
      items.push({ kind: 'activity', sequence: seq, event });
    });
    // Search blocks
    searchBlocks.forEach((block) => {
      items.push({ kind: 'search', sequence: block.sequence, block });
    });
    // Turn transcripts: header + role responses interleaved by sequence
    turnTranscripts.forEach((transcript) => {
      // Compute the first role response's sequence for this turn, so the
      // header sorts just before its first role (and after any preceding
      // search blocks).
      let firstRoleSeq = (transcript.turn - 1) * 1000;
      if (transcript.roleResponses.length > 0) {
        const firstKey = `${transcript.roleResponses[0].turn}-${transcript.roleResponses[0].role}`;
        firstRoleSeq = roleResponseSequences.current.get(firstKey) ?? firstRoleSeq;
      }
      items.push({ kind: 'turn-header', sequence: firstRoleSeq - 0.5, turn: transcript.turn });
      transcript.roleResponses.forEach((response) => {
        const key = `${response.turn}-${response.role}`;
        const seq = roleResponseSequences.current.get(key) ?? firstRoleSeq;
        items.push({
          kind: 'role-response',
          sequence: seq,
          response,
          plannerTasks: response.role === 'planner' ? transcript.plannerTasks : [],
        });
      });
    });
    items.sort((left, right) => left.sequence - right.sequence);
    return items;
  }, [visibleEvents, searchBlocks, turnTranscripts]);

  function updateAutoFollowState() {
    const transcript = transcriptRef.current;
    if (!transcript) return;
    const distanceFromBottom = transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight;
    autoFollowTranscriptRef.current = distanceFromBottom < 48;
  }

  useEffect(() => {
    if (!autoFollowTranscriptRef.current) return;
    transcriptEndRef.current?.scrollIntoView({ block: 'end' });
  }, [events.length, visibleEvents.length, result, error, turnTranscripts.length, searchBlocks.length]);

  async function submit() {
    if (!canSubmit) return;
    setLoading(true);
    setEvents([]);
    setSearchBlocks([]);
    setTurnTranscripts([]);
    setResult(null);
    setRunElapsed(0);
    setSubmittedQuestion(question.trim());
    setError('');
    runStartedAtRef.current = Date.now();
    sequenceCounterRef.current = 0;
    eventSequenceRef.current = [];
    roleResponseSequences.current = new Map();
    roleTimings.current = new Map();
    autoFollowTranscriptRef.current = true;
    if (tickIntervalRef.current) clearInterval(tickIntervalRef.current);
    tickIntervalRef.current = setInterval(() => forceRenderTick((n) => n + 1), 500);
    const formData = new FormData();
    formData.append('task', question);
    formData.append('mode', mode);
    formData.append('model', model);
    formData.append('rubric_json', JSON.stringify(defaultRubric));
    files.forEach((file) => formData.append('files', file));
    try {
      const response = await fetchWithRetry('/api/runs/stream', { method: 'POST', body: formData });
      if (!response.ok || !response.body) throw new Error(`Request failed with ${response.status}`);
      await readEventStream(response.body);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      if (tickIntervalRef.current) {
        clearInterval(tickIntervalRef.current);
        tickIntervalRef.current = null;
      }
    }
  }

  async function readEventStream(body: ReadableStream<Uint8Array>) {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    const upsertTurnTranscript = (
      turn: number,
      updater: (existing: TurnTranscript) => TurnTranscript
    ) => {
      setTurnTranscripts((existing) => {
        const transcripts = [...existing];
        const index = transcripts.findIndex((item) => item.turn === turn);
        const current = index >= 0
          ? transcripts[index]
          : { turn, plannerTasks: [], roleResponses: [], activeRoleTab: '' };
        const next = updater(current);
        if (index >= 0) transcripts[index] = next;
        else transcripts.push(next);
        transcripts.sort((left, right) => left.turn - right.turn);
        return transcripts;
      });
    };

    const latestTurnNumber = (existing: TurnTranscript[]) => existing[existing.length - 1]?.turn || 1;

    const ensureRoleResponse = (role: string, turn: number) => {
      const key = `${turn}-${role}`;
      if (!roleResponseSequences.current.has(key)) {
        sequenceCounterRef.current += 1;
        roleResponseSequences.current.set(key, sequenceCounterRef.current);
      }
      upsertTurnTranscript(turn, (existing) => {
        if (existing.roleResponses.some((response) => response.role === role && response.turn === turn)) return existing;
        return {
          ...existing,
          roleResponses: [
            ...existing.roleResponses,
            {
              role,
              turn,
              text: '',
              reasoningText: '',
              chars: 0,
              reasoningChars: 0,
              reasoningElapsed: 0,
              responseElapsed: 0,
              success: true,
            },
          ],
        };
      });
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';
      for (const part of parts) {
        const parsed = parseSse(part);
        if (!parsed) continue;
        sequenceCounterRef.current += 1;
        eventSequenceRef.current = [...eventSequenceRef.current, sequenceCounterRef.current];
        (parsed as StreamEvent & { _sequence?: number })._sequence = sequenceCounterRef.current;
        setEvents((existing) => [...existing, parsed]);
        if (parsed.event === 'log.search.start') {
          const searchData = parsed.data as {
            provider?: string;
            query?: { text?: string; preview?: string };
            query_index?: number;
            query_count?: number;
            role?: string;
          };
          const query = String(searchData.query?.text || searchData.query?.preview || 'Search');
          const role = String(searchData.role || 'planner');
          sequenceCounterRef.current += 1;
          setSearchBlocks((existing) => [
            ...existing,
            {
              id: `search-${existing.length + 1}`,
              provider: String(searchData.provider || ''),
              query,
              queryIndex: Number(searchData.query_index || 0),
              queryCount: Number(searchData.query_count || 0),
              content: '',
              status: 'active',
              resultCount: 0,
              role,
              sequence: sequenceCounterRef.current,
            },
          ]);
        }
        if (parsed.event === 'log.search.complete') {
          const searchData = parsed.data as {
            provider?: string;
            query?: { text?: string; preview?: string };
            query_index?: number;
            query_count?: number;
            result_count?: number;
            content?: { text?: string; preview?: string };
            role?: string;
          };
          const query = String(searchData.query?.text || searchData.query?.preview || 'Search');
          const content = String(searchData.content?.text || searchData.content?.preview || '');
          const role = String(searchData.role || 'planner');
          setSearchBlocks((existing) => {
            const updated = [...existing];
            const reverseIndex = [...updated].reverse().findIndex((item) => (
              item.status === 'active' &&
              item.query === query &&
              item.queryIndex === Number(searchData.query_index || 0)
            ));
            const index = reverseIndex >= 0 ? updated.length - 1 - reverseIndex : -1;
            if (index >= 0) {
              updated[index] = {
                ...updated[index],
                provider: String(searchData.provider || updated[index].provider),
                queryCount: Number(searchData.query_count || updated[index].queryCount),
                content,
                status: 'complete',
                resultCount: Number(searchData.result_count || 0),
              };
            } else {
              sequenceCounterRef.current += 1;
              updated.push({
                id: `search-${updated.length + 1}`,
                provider: String(searchData.provider || ''),
                query,
                queryIndex: Number(searchData.query_index || 0),
                queryCount: Number(searchData.query_count || 0),
                content,
                status: 'complete',
                resultCount: Number(searchData.result_count || 0),
                role,
                sequence: sequenceCounterRef.current,
              });
            }
            return updated;
          });
        }
        if (parsed.event === 'planner.tasks') {
          const plannerData = parsed.data as { turn?: number; tasks?: PlannerTask[] };
          const nextTurn = Number(plannerData.turn || 0);
          const tasks = (plannerData.tasks || []) as PlannerTask[];
          setTurnTranscripts((existing) => {
            const turn = nextTurn || latestTurnNumber(existing);
            const transcripts = [...existing];
            const index = transcripts.findIndex((item) => item.turn === turn);
            const current = index >= 0
              ? transcripts[index]
              : { turn, plannerTasks: [], roleResponses: [], activeRoleTab: '' };
            const next = { ...current, plannerTasks: tasks };
            if (index >= 0) transcripts[index] = next;
            else transcripts.push(next);
            transcripts.sort((left, right) => left.turn - right.turn);
            return transcripts;
          });
        }
        if (parsed.event === 'planner.task.update') {
          const taskUpdate = parsed.data as unknown as PlannerTask;
          setTurnTranscripts((existing) => {
            if (existing.length === 0) return existing;
            const transcripts = [...existing];
            const index = transcripts.length - 1;
            transcripts[index] = {
              ...transcripts[index],
              plannerTasks: transcripts[index].plannerTasks.map((task) =>
                task.id === taskUpdate.id ? { ...task, status: taskUpdate.status } : task
              ),
            };
            return transcripts;
          });
        }
        if (parsed.event === 'log.role.start') {
          const roleData = parsed.data as { role: string; turn: number };
          if (roleData.role) {
            const timingKey = `${roleData.turn}-${roleData.role}`;
            roleTimings.current.set(timingKey, { startedAt: Date.now(), reasoningDoneAt: 0, responseStartedAt: 0 });
            ensureRoleResponse(roleData.role, roleData.turn);
            upsertTurnTranscript(roleData.turn, (existing) => ({
              ...existing,
              activeRoleTab: roleData.role,
            }));
          }
        }
        if (parsed.event === 'role.delta') {
          const deltaData = parsed.data as {
            role: string;
            turn: number;
            delta: { preview?: string };
            reasoning?: { preview?: string };
          };
          ensureRoleResponse(deltaData.role, deltaData.turn);
          const deltaText = deltaData.delta?.preview || '';
          const reasoningText = deltaData.reasoning?.preview || '';
          // Track timing: when reasoning ends and response begins
          const timingKey = `${deltaData.turn}-${deltaData.role}`;
          const timing = roleTimings.current.get(timingKey);
          if (timing) {
            if (reasoningText && !timing.reasoningDoneAt) {
              // still receiving reasoning
            } else if (deltaText && !reasoningText && !timing.reasoningDoneAt) {
              // reasoning ended, response started
              timing.reasoningDoneAt = Date.now();
              timing.responseStartedAt = Date.now();
            } else if (deltaText && !timing.responseStartedAt) {
              timing.responseStartedAt = Date.now();
            }
          }
          if (deltaText || reasoningText) {
            upsertTurnTranscript(deltaData.turn, (existing) => {
              const updated = [...existing.roleResponses];
              const index = updated.findIndex((r) => r.role === deltaData.role && r.turn === deltaData.turn);
              if (index >= 0) {
                updated[index] = {
                  ...updated[index],
                  text: updated[index].text + deltaText,
                  reasoningText: updated[index].reasoningText + reasoningText,
                  chars: updated[index].chars + deltaText.length,
                  reasoningChars: updated[index].reasoningChars + reasoningText.length,
                };
              } else {
                updated.push({
                  role: deltaData.role,
                  turn: deltaData.turn,
                  text: deltaText,
                  reasoningText,
                  chars: deltaText.length,
                  reasoningChars: reasoningText.length,
                  reasoningElapsed: 0,
                  responseElapsed: 0,
                  success: true,
                });
              }
              return {
                ...existing,
                roleResponses: updated,
              };
            });
          }
          upsertTurnTranscript(deltaData.turn, (existing) => ({
            ...existing,
            activeRoleTab: existing.activeRoleTab || deltaData.role,
          }));
        }
        if (parsed.event === 'role.complete') {
          const roleData = parsed.data as RoleResponse & { reasoning_text?: string; reasoning_chars?: number; elapsed_seconds?: number };
          const timingKey = `${roleData.turn}-${roleData.role}`;
          const timing = roleTimings.current.get(timingKey);
          const reasoningElapsed = timing ? (timing.reasoningDoneAt - timing.startedAt) / 1000 : 0;
          const responseElapsed = timing ? ((Date.now() - (timing.responseStartedAt || timing.reasoningDoneAt)) / 1000) : (roleData.elapsed_seconds || 0);
          upsertTurnTranscript(roleData.turn, (existing) => {
            const updated = [...existing.roleResponses];
            const index = updated.findIndex((r) => r.role === roleData.role && r.turn === roleData.turn);
            const nextRoleData: RoleResponse = {
              role: roleData.role,
              turn: roleData.turn,
              text: roleData.text || '',
              chars: roleData.chars || 0,
              reasoningText: roleData.reasoning_text || '',
              reasoningChars: roleData.reasoning_chars || 0,
              reasoningElapsed,
              responseElapsed,
              success: roleData.success !== false,
            };
            if (index >= 0) {
              updated[index] = {
                ...nextRoleData,
                reasoningText: nextRoleData.reasoningText || updated[index].reasoningText,
                reasoningChars: nextRoleData.reasoningChars || updated[index].reasoningChars,
                text: nextRoleData.text || updated[index].text,
                chars: nextRoleData.chars || updated[index].chars,
              };
            } else updated.push(nextRoleData);
            return {
              ...existing,
              roleResponses: updated,
              activeRoleTab: existing.activeRoleTab || roleData.role,
            };
          });
        }
        if (parsed.event === 'rsc.run.complete') {
          setResult(parsed.data as unknown as RunResponse);
          if (runStartedAtRef.current) setRunElapsed((Date.now() - runStartedAtRef.current) / 1000);
        }
        if (parsed.event === 'rsc.run.error') setError(String(parsed.data.error || 'Run failed'));
      }
    }
  }

  function onFilesSelected(nextFiles: FileList | null) {
    if (!nextFiles) return;
    addFiles(Array.from(nextFiles));
  }

  function addFiles(nextFiles: File[]) {
    setFiles((existing) => {
      const seen = new Set(existing.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
      const additions = nextFiles.filter((file) => !seen.has(`${file.name}:${file.size}:${file.lastModified}`));
      return [...existing, ...additions];
    });
  }

  function onDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    addFiles(Array.from(event.dataTransfer.files || []));
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark"><Bot size={18} /></span>
          <div>
            <h1>Recursive Scaffolded Cognition</h1>
            <p>Recursive search and skill-routed reasoning</p>
          </div>
        </div>
      </header>

      <main className="chat-layout">
        <section className="transcript" ref={transcriptRef} onScroll={updateAutoFollowState}>
          {!submittedQuestion && events.length === 0 && !result && !error && (
            <div className="welcome-card">
              <h2>What do you want to understand?</h2>
              <p>Ask a question, pick a mode/model, attach markdown, PDF, DOCX, CSV, JSON, or text files, then stream the reasoning trace here.</p>
            </div>
          )}

          {submittedQuestion && (
            <div className="message user-message">
              <div className="message-label">You</div>
              <MarkdownBlock className="message-body">{submittedQuestion}</MarkdownBlock>
              {files.length > 0 && (
                <div className="message-files">
                  {files.map((file, index) => <AttachmentChip file={file} key={`${file.name}-${index}`} />)}
                </div>
              )}
            </div>
          )}

          {(timeline.length > 0 || loading) && (
            <>
              {timeline.map((item, index) => {
                if (item.kind === 'activity') {
                  return null;
                }
                if (item.kind === 'search') {
                  return <SearchBlockCard block={item.block} key={item.block.id} />;
                }
                if (item.kind === 'turn-header') {
                  return (
                    <div className="message turn-message" key={`turn-header-${item.turn}`}>
                      <div className="message-label">Loop Turn {item.turn}</div>
                    </div>
                  );
                }
                if (item.kind === 'role-response') {
                  return (
                    <div key={`role-${item.response.role}-${item.response.turn}`}>
                      <RoleResponseCard response={item.response} roleTimings={roleTimings} />
                      {item.response.role === 'planner' && item.plannerTasks.length > 0 && (
                        <PlannerTaskCard tasks={item.plannerTasks} done={Boolean(result)} />
                      )}
                    </div>
                    );
                  }
                  return null;
                })}
            </>
          )}

          {error && <pre className="error-box">{error}</pre>}

          {result && (
            <ResultCard
              result={result}
              elapsed={runElapsed}
              onExpand={() => setSidebarOpen(true)}
            />
          )}
          <div ref={transcriptEndRef} />
        </section>

        <ActivityBar loading={loading} visibleEvents={visibleEvents} />

        <section
          className="composer-card"
          onDragOver={(event) => event.preventDefault()}
          onDrop={onDrop}
        >
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask anything..."
            rows={3}
            className="question-box"
          />
          {files.length > 0 && (
            <div className="attachment-row" aria-label="Attached files">
              {files.map((file, index) => (
                <span className="file-chip editable" key={`${file.name}-${index}`}>
                  <FileText size={14} />
                  <span>{file.name}</span>
                  <button type="button" onClick={() => setFiles(files.filter((_, idx) => idx !== index))} title="Remove file">
                    <X size={13} />
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="controls-row">
            <label className="tool-button" htmlFor="rsc-attachment-input" title="Attach files">
              <Paperclip size={16} /> Attach
            </label>
            <input
              id="rsc-attachment-input"
              type="file"
              multiple
              className="hidden-file"
              tabIndex={-1}
              accept=".md,.markdown,.txt,.text,.pdf,.docx,.csv,.json,.yaml,.yml,.rst"
              onChange={(event) => onFilesSelected(event.target.files)}
            />
            <label className="select-label">
              <Search size={15} />
              <select value={mode} onChange={(event) => setMode(event.target.value)}>
                {(config?.modes || []).map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
              </select>
            </label>
            <label className="select-label wide">
              <Settings2 size={15} />
              <select value={model} onChange={(event) => setModel(event.target.value)}>
                {(config?.models || []).map((item) => <option value={item.model} key={`${item.provider}-${item.model}`}>{item.label}</option>)}
              </select>
            </label>
            <button type="button" className="send-button" onClick={submit} disabled={!canSubmit} title={loading ? 'Working' : 'Submit'}>
              <Play size={17} fill="currentColor" />
            </button>
          </div>
        </section>
      </main>
      {sidebarOpen && result && (
        <SidebarPanel
          result={result}
          elapsed={runElapsed}
          onClose={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
}

function AttachmentChip({ file }: { file: File }) {
  return (
    <span className="file-chip">
      <FileText size={14} />
      <span>{file.name}</span>
    </span>
  );
}

function parseSse(chunk: string): StreamEvent | null {
  const event = chunk.split('\n').find((line) => line.startsWith('event: '))?.slice(7).trim();
  const dataLine = chunk.split('\n').find((line) => line.startsWith('data: '));
  if (!event || !dataLine) return null;
  return { event, data: JSON.parse(dataLine.slice(6)) };
}

function ActivityBar({ loading, visibleEvents }: { loading: boolean; visibleEvents: StreamEvent[] }) {
  const activityEvents = visibleEvents.filter((item) => item.event === 'activity.update');
  if (activityEvents.length === 0 && !loading) return null;

  const latest = activityEvents.length > 0 ? activityEvents[activityEvents.length - 1] : null;
  const status = latest ? (loading && latest.data.status === 'active' ? 'active' : latest.data.status) : 'active';
  const progress = latest ? Math.round(Number(latest.data.progress || 0) * 100) : 0;
  const title = latest ? String(latest.data.title || 'Working') : 'Starting…';
  const detail = latest ? String(latest.data.detail || '') : '';

  if (status === 'complete' && !loading) return null;

  return (
    <div className="activity-bar">
      <div className="activity-bar-row">
        <span className="activity-bar-title">{title}</span>
        {detail && <span className="activity-bar-detail">{detail}</span>}
        <span className="activity-bar-pct">{progress}%</span>
      </div>
      <div className="activity-bar-track">
        <div className="activity-bar-fill" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}

function isSearchActivityEvent(event: StreamEvent) {
  if (event.event !== 'activity.update') return false;
  const title = String(event.data.title || '');
  return title.startsWith('Searching the web') || title.startsWith('Search complete') || title.startsWith('Planning search') || title.includes('search complete');
}

function MarkdownBlock({ children, className }: { children: string; className?: string }) {
  return (
    <div className={`markdown-body ${className || ''}`.trim()}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}

function RoleResponseCard({ response, roleTimings: _roleTimings }: { response: RoleResponse; roleTimings: React.MutableRefObject<Map<string, { startedAt: number; reasoningDoneAt: number; responseStartedAt: number }>> }) {
  const [activeTab, setActiveTab] = useState<'reasoning' | 'response'>('response');
  const responseTokens = Math.round(response.chars / 3.8);
  const reasoningTokens = Math.round(response.reasoningChars / 3.8);
  
  // Compute live elapsed times for active (incomplete) roles
  const now = Date.now();
  const timingKey = `${response.turn}-${response.role}`;
  const timing = _roleTimings.current.get(timingKey);
  let liveReasoningElapsed = response.reasoningElapsed;
  let liveResponseElapsed = response.responseElapsed;
  if (timing && response.success) {
    if (timing.startedAt && !timing.reasoningDoneAt && response.reasoningChars > 0) {
      liveReasoningElapsed = (now - timing.startedAt) / 1000;
    } else if (timing.reasoningDoneAt) {
      liveReasoningElapsed = (timing.reasoningDoneAt - timing.startedAt) / 1000;
    }
    if (timing.responseStartedAt && response.text.length > 0) {
      liveResponseElapsed = (now - timing.responseStartedAt) / 1000;
    }
  }
  
  return (
    <div className="role-response-card">
      <div className="role-card-header">
        <div className="message-label" style={{ marginBottom: 0 }}>{response.role}</div>
        <div className="role-tab-meta role-card-meta">
          <span>turn {response.turn}</span>
          {reasoningTokens > 0 && <span>{reasoningTokens} reasoning tokens</span>}
          <span>{responseTokens} tokens</span>
          {liveReasoningElapsed > 0 && <span>reasoning {liveReasoningElapsed.toFixed(1)}s</span>}
          {liveResponseElapsed > 0 && <span>response {liveResponseElapsed.toFixed(1)}s</span>}
          {!response.success && <span className="role-tab-error">failed</span>}
        </div>
      </div>
      <div className="role-tabs">
        <button
          className={`role-tab-btn ${activeTab === 'reasoning' ? 'active' : ''}`}
          onClick={() => setActiveTab('reasoning')}
          disabled={!response.reasoningText}
        >
          Reasoning{liveReasoningElapsed > 0 ? ` (${liveReasoningElapsed.toFixed(1)}s)` : ''}
        </button>
        <button
          className={`role-tab-btn ${activeTab === 'response' ? 'active' : ''}`}
          onClick={() => setActiveTab('response')}
        >
          Response{liveResponseElapsed > 0 ? ` (${liveResponseElapsed.toFixed(1)}s)` : ''}
        </button>
      </div>
      <div className="role-card-scroll">
        {activeTab === 'reasoning' && response.reasoningText && (
          <MarkdownBlock className="role-tab-markdown role-tab-reasoning">{response.reasoningText}</MarkdownBlock>
        )}
        {activeTab === 'reasoning' && !response.reasoningText && (
          <div className="search-placeholder">No reasoning captured.</div>
        )}
        {activeTab === 'response' && (
          <MarkdownBlock className="role-tab-markdown">{response.text}</MarkdownBlock>
        )}
      </div>
    </div>
  );
}

function PlannerTaskCard({ tasks, done }: { tasks: PlannerTask[]; done: boolean }) {
  return (
    <div className="message task-message task-card">
      <div className="message-label">Tasks {tasks.length}</div>
      <div className="task-card-scroll">
        <div className="task-list role-task-list">
          {tasks.map((item) => (
            <TaskRow key={item.id} task={item} done={done && item.status !== 'active'} />
          ))}
        </div>
      </div>
    </div>
  );
}

function SearchBlockCard({ block }: { block: SearchBlock }) {
  return (
    <div className="message search-block-card">
      <div className="search-card-header">
        <div className="message-label" style={{ marginBottom: 0 }}>
          <Search size={14} /> {block.role ? `${block.role}` : 'Search'} search {block.queryIndex > 0 ? `${block.queryIndex}/${block.queryCount || '?'}` : ''}
        </div>
        <div className="answer-meta">
          {block.provider && <span>{block.provider}</span>}
          <span>{block.status}</span>
          {block.resultCount > 0 && <span>{block.resultCount} results</span>}
        </div>
      </div>
      <div className="message-body search-query-line">{block.query}</div>
      <div className="search-card-scroll">
        {block.content ? (
          <MarkdownBlock className="role-tab-markdown">{block.content}</MarkdownBlock>
        ) : (
          <div className="search-placeholder">Waiting for search results...</div>
        )}
      </div>
    </div>
  );
}

function TaskRow({ task, done }: { task: PlannerTask; done: boolean }) {
  const isComplete = task.status === 'complete' || done;
  const isActive = task.status === 'active';
  const isFailed = task.status === 'failed';
  const icon = isComplete ? '✓' : isActive ? '⟳' : isFailed ? '✗' : '•';
  return (
    <div className={`task-row ${isComplete ? 'done' : ''} ${isActive ? 'active' : ''} ${isFailed ? 'failed' : ''}`}>
      <span>{icon}</span>
      <strong>{task.title}</strong>
    </div>
  );
}

function currentActivity(events: StreamEvent[]) {
  const last = [...events].reverse().find((item) => item.event === 'activity.update') || events[events.length - 1];
  if (!last) return 'Starting';
  if (last.event === 'activity.update') return String(last.data.title || 'Working');
  return last.event.replace(/^log\./, '').replaceAll('.', ' ');
}

async function fetchWithRetry(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  let lastError: unknown;
  for (let attempt = 0; attempt <= 5; attempt += 1) {
    try {
      const response = await fetch(input, init);
      if (response.ok || !isRetryableStatus(response.status) || attempt === 5) return response;
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
      if (attempt === 5) break;
    }
    await delay((attempt + 1) * 5000);
  }
  throw lastError instanceof Error ? lastError : new Error(String(lastError || 'Network request failed'));
}

function isRetryableStatus(status: number) {
  return status === 408 || status === 409 || status === 425 || status === 429 || status >= 500;
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// Result Card & Sidebar
// ---------------------------------------------------------------------------

function extractTitle(markdown: string): string {
  const match = markdown.match(/^#\s+(.+)$/m);
  return match ? match[1].trim() : 'Result';
}

function extractPreviewLines(markdown: string, count: number = 20): string {
  return markdown.split('\n').slice(0, count).join('\n');
}

function downloadFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function downloadMarkdown(content: string, title: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  downloadFile(blob, `${title}.md`);
}

async function downloadDocx(content: string, title: string) {
  const lines = content.split('\n');
  const paragraphs: Paragraph[] = [];
  let inCodeBlock = false;
  let codeBuffer: string[] = [];

  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        paragraphs.push(new Paragraph({
          children: [new TextRun({ text: codeBuffer.join('\n'), font: 'Courier New', size: 20 })],
          spacing: { before: 120, after: 120 },
        }));
        codeBuffer = [];
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
      continue;
    }
    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }
    if (line.startsWith('# ')) {
      paragraphs.push(new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun({ text: line.slice(2).replace(/\*\*/g, ''), bold: true })],
        spacing: { before: 240, after: 120 },
      }));
    } else if (line.startsWith('## ')) {
      paragraphs.push(new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [new TextRun({ text: line.slice(3).replace(/\*\*/g, ''), bold: true })],
        spacing: { before: 200, after: 100 },
      }));
    } else if (line.startsWith('### ')) {
      paragraphs.push(new Paragraph({
        heading: HeadingLevel.HEADING_3,
        children: [new TextRun({ text: line.slice(4).replace(/\*\*/g, ''), bold: true })],
        spacing: { before: 160, after: 80 },
      }));
    } else if (line.startsWith('- ') || line.startsWith('* ')) {
      const text = line.slice(2).replace(/\*\*(.*?)\*\*/g, '$1');
      paragraphs.push(new Paragraph({
        children: [new TextRun({ text })],
        bullet: { level: 0 },
        spacing: { before: 40, after: 40 },
      }));
    } else if (/^\d+\.\s/.test(line)) {
      const text = line.replace(/^\d+\.\s+/, '').replace(/\*\*(.*?)\*\*/g, '$1');
      paragraphs.push(new Paragraph({
        children: [new TextRun({ text })],
        numbering: { reference: 'default-numbering', level: 0 },
        spacing: { before: 40, after: 40 },
      }));
    } else if (line.startsWith('> ')) {
      paragraphs.push(new Paragraph({
        children: [new TextRun({ text: line.slice(2), italics: true, color: '525252' })],
        indent: { left: 720 },
        spacing: { before: 80, after: 80 },
      }));
    } else if (line.trim() === '---') {
      paragraphs.push(new Paragraph({
        children: [new TextRun({ text: '' })],
        thematicBreak: true,
      }));
    } else if (line.trim() === '') {
      paragraphs.push(new Paragraph({ children: [] }));
    } else {
      // Strip inline markdown: bold, italic, code, links
      const cleaned = line
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
        .replace(/\*\*(.*?)\*\*/g, '$1')
        .replace(/\*(.*?)\*/g, '$1')
        .replace(/`([^`]+)`/g, '$1');
      paragraphs.push(new Paragraph({
        children: [new TextRun({ text: cleaned })],
        spacing: { before: 60, after: 60 },
      }));
    }
  }

  const doc = new DocxDocument({
    numbering: {
      config: [{
        reference: 'default-numbering',
        levels: [{ level: 0, format: 'decimal', text: '%1.', alignment: 'left', style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
      }],
    },
    sections: [{ children: paragraphs }],
  });
  const blob = await Packer.toBlob(doc);
  downloadFile(blob, `${title}.docx`);
}

async function downloadPdf(content: string, title: string) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 15;
  const maxWidth = pageWidth - margin * 2;
  let y = margin;

  const checkPageBreak = (needed: number) => {
    if (y + needed > pageHeight - margin) {
      doc.addPage();
      y = margin;
    }
  };

  const lines = content.split('\n');
  let inCodeBlock = false;
  let codeLines: string[] = [];

  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        checkPageBreak(6);
        doc.setFont('courier', 'normal');
        doc.setFontSize(9);
        doc.setFillColor(240, 240, 240);
        const codeText = codeLines.join('\n');
        const splitCode = doc.splitTextToSize(codeText, maxWidth - 4);
        const blockHeight = splitCode.length * 4 + 4;
        checkPageBreak(blockHeight);
        doc.rect(margin, y - 2, maxWidth, blockHeight, 'F');
        for (const cl of splitCode) {
          doc.text(cl, margin + 2, y + 2);
          y += 4;
        }
        y += 4;
        codeLines = [];
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
      continue;
    }
    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    if (line.startsWith('# ')) {
      checkPageBreak(12);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(18);
      const text = line.slice(2).replace(/\*\*/g, '');
      const split = doc.splitTextToSize(text, maxWidth);
      for (const sl of split) {
        doc.text(sl, margin, y);
        y += 8;
      }
      y += 4;
    } else if (line.startsWith('## ')) {
      checkPageBreak(10);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(14);
      const text = line.slice(3).replace(/\*\*/g, '');
      const split = doc.splitTextToSize(text, maxWidth);
      for (const sl of split) {
        doc.text(sl, margin, y);
        y += 6;
      }
      y += 3;
    } else if (line.startsWith('### ')) {
      checkPageBreak(8);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(12);
      const text = line.slice(4).replace(/\*\*/g, '');
      const split = doc.splitTextToSize(text, maxWidth);
      for (const sl of split) {
        doc.text(sl, margin, y);
        y += 6;
      }
      y += 2;
    } else if (line.startsWith('- ') || line.startsWith('* ')) {
      checkPageBreak(6);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(11);
      const text = '• ' + line.slice(2).replace(/\*\*(.*?)\*\*/g, '$1').replace(/\*(.*?)\*/g, '$1').replace(/`([^`]+)`/g, '$1');
      const split = doc.splitTextToSize(text, maxWidth - 6);
      for (const sl of split) {
        doc.text(sl, margin + 4, y);
        y += 5;
      }
      y += 1;
    } else if (/^\d+\.\s/.test(line)) {
      checkPageBreak(6);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(11);
      const text = line.replace(/\*\*(.*?)\*\*/g, '$1').replace(/\*(.*?)\*/g, '$1').replace(/`([^`]+)`/g, '$1');
      const split = doc.splitTextToSize(text, maxWidth - 6);
      for (const sl of split) {
        doc.text(sl, margin + 4, y);
        y += 5;
      }
      y += 1;
    } else if (line.startsWith('> ')) {
      checkPageBreak(6);
      doc.setFont('helvetica', 'italic');
      doc.setFontSize(10);
      doc.setTextColor(100, 100, 100);
      const text = line.slice(2);
      const split = doc.splitTextToSize(text, maxWidth - 10);
      for (const sl of split) {
        doc.text(sl, margin + 6, y);
        y += 5;
      }
      doc.setTextColor(0, 0, 0);
      y += 2;
    } else if (line.trim() === '---') {
      checkPageBreak(4);
      doc.setDrawColor(200, 200, 200);
      doc.line(margin, y, pageWidth - margin, y);
      y += 6;
    } else if (line.trim() === '') {
      y += 4;
    } else {
      checkPageBreak(6);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(11);
      const cleaned = line
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
        .replace(/\*\*(.*?)\*\*/g, '$1')
        .replace(/\*(.*?)\*/g, '$1')
        .replace(/`([^`]+)`/g, '$1');
      const split = doc.splitTextToSize(cleaned, maxWidth);
      for (const sl of split) {
        checkPageBreak(5);
        doc.text(sl, margin, y);
        y += 5;
      }
      y += 2;
    }
  }

  doc.save(`${title}.pdf`);
}

function ResultCard({ result, elapsed, onExpand }: { result: RunResponse; elapsed: number; onExpand: () => void }) {
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const title = extractTitle(result.final_output);
  const preview = extractPreviewLines(result.final_output, 20);
  const previewLineCount = result.final_output.split('\n').length;

  useEffect(() => {
    if (!showMenu) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setShowMenu(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showMenu]);

  return (
    <div className="message result-card" onClick={onExpand} role="button" tabIndex={0}>
      <div className="result-card-header">
        <div className="result-card-title-group">
          <CheckCircle2 size={14} />
          <span className="result-card-title">{title}</span>
        </div>
        <div className="result-card-actions">
          <span className="result-card-meta">{elapsed > 0 ? `${elapsed.toFixed(1)}s · ` : ''}{result.status} · score {result.final_score.toFixed(2)} · {result.turns_used} turn{result.turns_used === 1 ? '' : 's'}</span>
          <div className="result-download-wrapper" ref={menuRef} onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="tool-button result-download-btn"
              onClick={() => setShowMenu(!showMenu)}
              title="Download"
            >
              <Download size={15} /> Download
            </button>
            {showMenu && (
              <div className="result-download-menu">
                <button type="button" onClick={() => { downloadMarkdown(result.final_output, title); setShowMenu(false); }}>Markdown (.md)</button>
                <button type="button" onClick={() => { downloadDocx(result.final_output, title); setShowMenu(false); }}>Word (.docx)</button>
                <button type="button" onClick={() => { downloadPdf(result.final_output, title); setShowMenu(false); }}>PDF (.pdf)</button>
              </div>
            )}
          </div>
        </div>
      </div>
      <div className="result-card-preview markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{preview}</ReactMarkdown>
        {previewLineCount > 20 && <div className="result-card-overflow">… {previewLineCount - 20} more lines</div>}
      </div>
    </div>
  );
}

function SidebarPanel({ result, elapsed, onClose }: { result: RunResponse; elapsed: number; onClose: () => void }) {
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const title = extractTitle(result.final_output);

  useEffect(() => {
    if (!showMenu) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setShowMenu(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showMenu]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <aside className="sidebar-panel">
      <div className="sidebar-header">
        <span className="sidebar-title">{title}</span>
        {elapsed > 0 && <span className="result-card-meta" style={{ marginLeft: 0 }}>{elapsed.toFixed(1)}s</span>}
        <div className="sidebar-actions">
          <div className="result-download-wrapper" ref={menuRef}>
            <button
              type="button"
              className="tool-button result-download-btn"
              onClick={() => setShowMenu(!showMenu)}
              title="Download"
            >
              <Download size={15} /> Download
            </button>
            {showMenu && (
              <div className="result-download-menu">
                <button type="button" onClick={() => { downloadMarkdown(result.final_output, title); setShowMenu(false); }}>Markdown (.md)</button>
                <button type="button" onClick={() => { downloadDocx(result.final_output, title); setShowMenu(false); }}>Word (.docx)</button>
                <button type="button" onClick={() => { downloadPdf(result.final_output, title); setShowMenu(false); }}>PDF (.pdf)</button>
              </div>
            )}
          </div>
          <button type="button" className="tool-button sidebar-close-btn" onClick={onClose} title="Close preview">
            <X size={16} />
          </button>
        </div>
      </div>
      <div className="sidebar-content">
        <div className="sidebar-scroll markdown-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.final_output}</ReactMarkdown>
        </div>
      </div>
    </aside>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
