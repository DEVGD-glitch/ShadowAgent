'use client';

import { memo, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Copy, Check, User, Bot, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatMessage } from '@/stores/agent-store';
import { ToolCallBadge } from './tool-call-badge';
import { ThinkingSection } from './thinking-section';
import { StreamingCursor } from './streaming-cursor';

interface MessageItemProps {
  message: ChatMessage;
  index: number;
}

const SyntaxHighlighterComponent = SyntaxHighlighter as unknown as React.ComponentType<any>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const syntaxStyle = oneDark as any;

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      // Fallback for non-HTTPS contexts
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
    }
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1 rounded-md bg-white/5 text-white/30 hover:text-white/60 hover:bg-white/10 transition-colors"
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.9 }}
    >
      {copied ? <Check className="h-3.5 w-3.5 text-green-400" /> : <Copy className="h-3.5 w-3.5" />}
    </motion.button>
  );
}

export const MessageItem = memo(function MessageItem({ message, index }: MessageItemProps) {
  const isUser = message.role === 'user';
  const isError = message.role === 'error';
  const isSystem = message.role === 'system';

  if (isSystem) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: index * 0.05 }}
        className="flex justify-center my-3"
      >
        <div className="px-4 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-300 text-xs">
          {message.content}
        </div>
      </motion.div>
    );
  }

  if (isError) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: index * 0.05 }}
        className="flex justify-center my-3"
      >
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-sm max-w-lg">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{message.content}</span>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.03, duration: 0.3 }}
      className={cn(
        'flex gap-3 px-4 py-3',
        isUser ? 'justify-end' : 'justify-start'
      )}
    >
      {/* Avatar for assistant */}
      {!isUser && (
        <motion.div
          className="flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500/30 to-violet-600/30 border border-purple-500/20 flex items-center justify-center mt-0.5"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
        >
          <Bot className="h-3.5 w-3.5 text-purple-300" />
        </motion.div>
      )}

      {/* Message Content */}
      <div
        className={cn(
          'max-w-[75%] min-w-0',
          isUser ? 'order-first' : ''
        )}
      >
        {/* Thinking Section */}
        {message.thinking && (
          <ThinkingSection
            content={message.thinking.content}
            duration={message.thinking.duration}
          />
        )}

        {/* Tool Calls */}
        {message.toolCalls?.map((tc) => (
          <ToolCallBadge key={tc.id} toolCall={tc} />
        ))}

        {/* Message Bubble */}
        <div
          className={cn(
            'rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
            isUser
              ? 'bg-gradient-to-br from-purple-500/20 to-violet-600/15 border border-purple-500/20 text-white/90'
              : 'bg-white/[0.03] border border-white/[0.06] text-white/80'
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="markdown-content">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeSanitize]}
                components={{
                  code({ className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    const isInline = !match;
                    const codeString = String(children).replace(/\n$/, '');

                    if (isInline) {
                      return (
                        <code className={className} {...props}>
                          {children}
                        </code>
                      );
                    }

                    return (
                      <div className="relative group">
                        <div className="flex items-center justify-between px-4 py-1.5 bg-white/[0.03] border-b border-white/[0.06] rounded-t-xl">
                          <span className="text-[10px] font-mono text-white/30">{match[1]}</span>
                          <CopyButton text={codeString} />
                        </div>
                        <SyntaxHighlighterComponent
                          style={syntaxStyle}
                          language={match[1]}
                          PreTag="div"
                          customStyle={{
                            margin: 0,
                            borderRadius: '0 0 0.75rem 0.75rem',
                            background: 'oklch(0.1 0.02 280)',
                            border: '1px solid oklch(1 0 0 / 6%)',
                            borderTop: 'none',
                            fontSize: '0.8125rem',
                          }}
                          {...props}
                        >
                          {codeString}
                        </SyntaxHighlighterComponent>
                      </div>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
              {message.isStreaming && <StreamingCursor />}
            </div>
          )}

          {/* Attachments */}
          {message.attachments && message.attachments.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {message.attachments.map((att, i) => (
                <div
                  key={i}
                  className="px-2 py-1 rounded-md bg-white/5 text-white/40 text-xs flex items-center gap-1"
                >
                  📎 {att}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Timestamp */}
        <div className={cn(
          'mt-1 text-[10px] text-white/20',
          isUser ? 'text-right' : 'text-left'
        )}>
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
          {message.model && (
            <span className="ml-2 text-purple-400/40">{message.model}</span>
          )}
        </div>
      </div>

      {/* Avatar for user */}
      {isUser && (
        <motion.div
          className="flex-shrink-0 w-7 h-7 rounded-lg bg-white/10 border border-white/10 flex items-center justify-center mt-0.5"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 400, damping: 20 }}
        >
          <User className="h-3.5 w-3.5 text-white/50" />
        </motion.div>
      )}
    </motion.div>
  );
});
