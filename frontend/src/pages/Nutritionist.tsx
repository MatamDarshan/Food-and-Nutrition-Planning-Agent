import { useEffect, useRef, useState } from 'react';
import { Bot, BookOpen, ExternalLink, Loader2, RotateCcw, Send, Sparkles, User } from 'lucide-react';
import { toast } from 'sonner';
import { chatApi, messageOf } from '../lib/api';
import type { ChatTurn } from '../lib/types';
import { useApp } from '../lib/store';
import { PageHeader } from '../components/Layout';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';

const PROMPTS = [
  'Suggest a high-protein snack',
  'What can I substitute for paneer?',
  'Why was this meal recommended for me?',
  'How can I improve my iron intake?',
  'Explain my calorie target',
];

export function Nutritionist() {
  const chat = useApp((s) => s.chat);
  const setChat = useApp((s) => s.setChat);
  const planId = useApp((s) => s.planId);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chat.length) chatApi.history().then(setChat).catch(() => undefined);
  }, [chat.length, setChat]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chat, busy]);

  const ask = async (message: string) => {
    const text = message.trim();
    if (!text || busy) return;
    const history: ChatTurn[] = [...chat, { role: 'user', content: text }];
    setChat(history);
    setInput('');
    setBusy(true);
    try {
      const reply = await chatApi.send(text, chat, planId || undefined);
      setChat([...history, { role: 'assistant', content: reply.reply, citations: reply.citations }]);
    } catch (error) {
      toast.error(messageOf(error));
      setChat(chat);
    } finally {
      setBusy(false);
    }
  };

  const clear = async () => {
    try {
      await chatApi.clear();
      setChat([]);
      toast.success('Conversation cleared');
    } catch {
      toast.error('Could not clear the conversation');
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Grounded in your plan and nutrition science"
        title="AI Nutritionist"
        description="Ask anything about your meals, nutrients or substitutions. Answers include sources from the nutrition knowledge base."
        action={<Button variant="outline" onClick={clear}><RotateCcw className="h-4 w-4" /> New conversation</Button>}
      />

      <div className="np-card flex h-[calc(100vh-15rem)] min-h-[520px] flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-brand-100 bg-brand-50/40 px-5 py-3.5">
          <span className="relative grid h-10 w-10 place-items-center rounded-xl bg-brand-600 text-white">
            <Bot className="h-5 w-5" />
            <span className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-emerald-500" />
          </span>
          <div>
            <p className="text-sm font-bold">Nutri Assistant</p>
            <p className="text-[11px] text-muted-foreground">Online · ICMR-NIN knowledge base connected</p>
          </div>
          <Badge className="ml-auto" variant="success"><Sparkles className="h-3 w-3" /> RAG powered</Badge>
        </div>

        <div className="np-scrollbar flex-1 space-y-5 overflow-y-auto px-4 py-6 sm:px-6">
          {!chat.length && (
            <div className="mx-auto max-w-xl text-center">
              <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-600"><Bot className="h-7 w-7" /></span>
              <h3 className="mt-4 text-lg font-bold">Hi! I'm your nutritionist.</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                I know your profile, targets and current meal plan. Try one of these to get started.
              </p>
              <div className="mt-6 grid gap-2 text-left sm:grid-cols-2">
                {PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => ask(prompt)}
                    className="rounded-xl border border-brand-100 bg-white p-3.5 text-left text-xs font-semibold transition hover:border-brand-400 hover:bg-brand-50"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {chat.map((turn, index) => (
            <div key={`${index}-${turn.role}`} className={`flex gap-3 ${turn.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${turn.role === 'user' ? 'bg-brand-100 text-brand-700' : 'bg-brand-600 text-white'}`}>
                {turn.role === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </span>
              <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed sm:max-w-[75%] ${turn.role === 'user' ? 'bg-brand-600 text-white' : 'border border-brand-100 bg-white text-ink/85'}`}>
                <p className="whitespace-pre-wrap">{turn.content}</p>
                {!!turn.citations?.length && (
                  <div className="mt-3 border-t border-brand-100 pt-2.5">
                    <p className="mb-1.5 flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                      <BookOpen className="h-3 w-3" /> Sources
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {turn.citations.map((citation, i) => (
                        <span key={i} className="inline-flex items-center gap-1 rounded-lg bg-brand-50 px-2 py-1 text-[10px] font-semibold text-brand-700">
                          <ExternalLink className="h-2.5 w-2.5" /> {citation.source} · p.{citation.page || 1}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {busy && (
            <div className="flex gap-3">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-white"><Bot className="h-4 w-4" /></span>
              <div className="flex items-center gap-2 rounded-2xl border border-brand-100 bg-white px-4 py-3 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Thinking with your plan and knowledge base…
              </div>
            </div>
          )}
          <div ref={bottom} />
        </div>

        <div className="border-t border-brand-100 bg-white px-4 py-4 sm:px-6">
          <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
            {PROMPTS.slice(0, 3).map((prompt) => (
              <button
                key={prompt}
                onClick={() => ask(prompt)}
                disabled={busy}
                className="shrink-0 rounded-full border border-brand-100 px-3 py-1.5 text-[11px] font-semibold text-muted-foreground hover:border-brand-400 hover:text-brand-700 disabled:opacity-50"
              >
                {prompt}
              </button>
            ))}
          </div>
          <form
            onSubmit={(e) => { e.preventDefault(); ask(input); }}
            className="flex items-end gap-2"
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(input); } }}
              placeholder="Ask about meals, nutrients or substitutions…"
              rows={1}
              className="max-h-32 min-h-11 flex-1 resize-none rounded-xl border border-input bg-cream px-4 py-3 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20"
            />
            <Button type="submit" disabled={busy || !input.trim()} className="h-11 w-11 shrink-0 rounded-xl p-0">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </form>
          <p className="mt-2 text-center text-[10px] text-muted-foreground">
            Educational guidance only · Always consult a qualified clinician for medical advice.
          </p>
        </div>
      </div>
    </>
  );
}
