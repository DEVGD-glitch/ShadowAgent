'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send,
  Square,
  Paperclip,
  Mic,
  MicOff,
  X,
  Image as ImageIcon,
} from 'lucide-react';
import { useAgentStore } from '@/stores/agent-store';
import { useSettingsStore } from '@/stores/settings-store';
import { cn } from '@/lib/utils';
import { sendMessage, abortTask, parseExpressions } from '@/lib/api';
import type { SSEEvent } from '@/lib/api';

interface AttachedFile {
  file: File;
  dataUrl?: string; // only for images
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'text/plain', 'application/pdf', 'application/json', 'text/csv'];

export function ChatInput() {
  const [input, setInput] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isSendingRef = useRef(false);

  const {
    addMessage,
    updateMessage,
    setStreaming,
    setStatus,
    currentModel,
    isStreaming,
    circuitBreakerOpen,
    setActiveTools,
    updateMetrics,
    setCurrentExpression,
    setBackendConnected,
  } = useAgentStore();

  const { voice, avatar } = useSettingsStore();
  const [isRecording, setIsRecording] = useState(false);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  // Listen for setChatInput custom event from suggestion buttons
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (typeof detail === 'string') {
        setInput(detail);
        textareaRef.current?.focus();
      }
    };
    window.addEventListener('setChatInput', handler);
    return () => window.removeEventListener('setChatInput', handler);
  }, []);

  // Drag and drop handlers
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFiles = useCallback((fileList: File[]) => {
    const newFiles: AttachedFile[] = [];
    const errors: string[] = [];

    fileList.forEach((file) => {
      if (!ALLOWED_TYPES.includes(file.type)) {
        errors.push(`"${file.name}" has unsupported type: ${file.type || 'unknown'}`);
        return;
      }
      if (file.size > MAX_FILE_SIZE) {
        errors.push(`"${file.name}" exceeds 10MB limit (${(file.size / 1024 / 1024).toFixed(1)}MB)`);
        return;
      }
      newFiles.push({ file });
    });

    if (errors.length > 0) {
      setValidationError(errors.join('; '));
      setTimeout(() => setValidationError(null), 5000);
    }

    // Read dataUrls for images
    newFiles.forEach((af, idx) => {
      if (af.file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (e) => {
          const dataUrl = e.target?.result as string;
          setAttachedFiles((prev) => {
            const updated = [...prev];
            // Find the entry that matches this file (by reference in newFiles)
            const targetIndex = prev.length + idx - (newFiles.length - prev.length) + idx;
            // Safer: find by file reference
            const matchIdx = updated.findIndex((f) => f.file === af.file && !f.dataUrl);
            if (matchIdx >= 0) {
              updated[matchIdx] = { ...updated[matchIdx], dataUrl };
            }
            return updated;
          });
        };
        reader.readAsDataURL(af.file);
      }
    });

    setAttachedFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    handleFiles(droppedFiles);
  }, [handleFiles]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    handleFiles(selectedFiles);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    handleFiles(selectedFiles);
    if (imageInputRef.current) imageInputRef.current.value = '';
  };

  const removeFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming || circuitBreakerOpen) return;
    if (isSendingRef.current) return;
    isSendingRef.current = true;

    const userMessageId = `msg-${crypto.randomUUID()}`;
    const assistantMessageId = `msg-${crypto.randomUUID()}`;

    const fileNames = attachedFiles.map((af) => af.file.name);
    const imageDataUrls = attachedFiles
      .filter((af) => af.dataUrl)
      .map((af) => af.dataUrl!);

    // Add user message
    addMessage({
      id: userMessageId,
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
      attachments: fileNames.length > 0 ? fileNames : undefined,
    });

    setInput('');
    setAttachedFiles([]);
    setStreaming(true);
    setStatus('thinking');

    // Add assistant message placeholder
    addMessage({
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true,
      model: currentModel?.name,
    });

    setStatus('streaming');

    // Create abort controller with idle timeout
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    // SSE idle timeout: abort if no event received within 60 seconds
    let idleTimeoutId = setTimeout(() => {
      abortController.abort();
    }, 60000);

    const resetIdleTimeout = () => {
      clearTimeout(idleTimeoutId);
      idleTimeoutId = setTimeout(() => {
        abortController.abort();
      }, 60000);
    };

    // Stream response via SSE
    let fullContent = '';
    let thinkingContent = '';
    let currentToolCalls: Array<{
      id: string;
      name: string;
      args: Record<string, unknown>;
      status: 'pending' | 'success' | 'error';
      result?: string;
      duration?: number;
    }> = [];

    try {
      for await (const event of sendMessage(trimmed, {
        stream: true,
        images: imageDataUrls.length > 0 ? imageDataUrls : undefined,
        signal: abortController.signal,
      })) {
        // Reset idle timeout on each received event
        resetIdleTimeout();

        switch (event.type) {
          case 'token':
            fullContent += event.data;
            // Parse expressions from content
            const { expressions, cleanText } = parseExpressions(fullContent);
            if (expressions.length > 0 && avatar.enabled) {
              setCurrentExpression(expressions[expressions.length - 1]);
            }
            updateMessage(assistantMessageId, {
              content: fullContent,
              isStreaming: true,
              expressions: expressions.length > 0 ? expressions : undefined,
            });
            break;

          case 'thinking':
            thinkingContent += event.data;
            updateMessage(assistantMessageId, {
              thinking: {
                id: `thinking-${assistantMessageId}`,
                content: thinkingContent,
                duration: undefined,
                collapsed: true,
              },
            });
            break;

          case 'tool_call':
            try {
              const toolData = JSON.parse(event.data);
              currentToolCalls.push({
                id: `tc-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                name: toolData.name || event.data,
                args: toolData.args || {},
                status: 'pending',
              });
              setActiveTools(currentToolCalls.map((tc) => tc.name));
              updateMessage(assistantMessageId, {
                toolCalls: [...currentToolCalls],
              });
            } catch {
              currentToolCalls.push({
                id: `tc-${Date.now()}`,
                name: event.data,
                args: {},
                status: 'pending',
              });
              setActiveTools(currentToolCalls.map((tc) => tc.name));
              updateMessage(assistantMessageId, {
                toolCalls: [...currentToolCalls],
              });
            }
            break;

          case 'tool_result':
            try {
              const resultData = JSON.parse(event.data);
              const toolName = resultData.name || '';
              const tcIndex = currentToolCalls.findIndex((tc) => tc.name === toolName);
              if (tcIndex >= 0) {
                currentToolCalls[tcIndex] = {
                  ...currentToolCalls[tcIndex],
                  status: resultData.success ? 'success' : 'error',
                  result: resultData.result || resultData.output || '',
                  duration: resultData.duration,
                };
              }
              updateMessage(assistantMessageId, {
                toolCalls: [...currentToolCalls],
              });
            } catch {
              // Non-JSON tool result
            }
            break;

          case 'expression':
            if (avatar.enabled) {
              setCurrentExpression(event.data);
            }
            break;

          case 'error':
            addMessage({
              id: `error-${Date.now()}`,
              role: 'error',
              content: event.data || 'An error occurred while generating the response.',
              timestamp: Date.now(),
            });
            break;

          case 'done':
            // Finalize
            break;

          case 'keepalive':
            // Ignore keepalive
            break;
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // Aborted by user or idle timeout
      } else {
        addMessage({
          id: `error-${Date.now()}`,
          role: 'error',
          content: err instanceof Error ? err.message : 'An error occurred. Please try again.',
          timestamp: Date.now(),
        });
      }
    } finally {
      clearTimeout(idleTimeoutId);
      isSendingRef.current = false;
    }

    updateMessage(assistantMessageId, {
      isStreaming: false,
    });
    setStreaming(false);
    setStatus('idle');
    setActiveTools([]);
    abortControllerRef.current = null;
    updateMetrics({
      tokensUsed: Math.floor(fullContent.length * 0.4) + Math.floor(trimmed.length * 0.3),
      llmCalls: 1,
    });
  };

  const handleStop = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    await abortTask();
    setStreaming(false);
    setStatus('idle');
    setActiveTools([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Voice recording using Web Speech API with backend STT fallback
  const recognitionRef = useRef<any>(null);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      // Stop recording
      setIsRecording(false);
      if (recognitionRef.current) {
        recognitionRef.current.stop();
        recognitionRef.current = null;
      }
      return;
    }

    // Start recording
    setIsRecording(true);

    // Try Web Speech API first (browser-native, free, no API key)
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = voice.language === 'fr' ? 'fr-FR' :
                          voice.language === 'ja' ? 'ja-JP' :
                          voice.language === 'zh' ? 'zh-CN' :
                          voice.language === 'de' ? 'de-DE' :
                          voice.language === 'es' ? 'es-ES' : 'en-US';

      let finalTranscript = '';

      recognition.onresult = (event: any) => {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcript;
          } else {
            interim += transcript;
          }
        }
        // Show interim results in the input
        if (interim || finalTranscript) {
          setInput((prev) => {
            // Only update if not already set from this session
            if (prev.includes('[Voice input') && prev.includes('placeholder]')) {
              return finalTranscript + interim;
            }
            return finalTranscript + interim;
          });
        }
      };

      recognition.onend = () => {
        setIsRecording(false);
        recognitionRef.current = null;
        // If we got final transcript, it's already in the input
      };

      recognition.onerror = (event: any) => {
        console.warn('Speech recognition error:', event.error);
        setIsRecording(false);
        recognitionRef.current = null;

        if (event.error === 'not-allowed') {
          setInput((prev) => prev + (prev ? '\n' : '') + '[Microphone access denied. Please allow microphone in browser settings.]');
        }
      };

      recognitionRef.current = recognition;
      recognition.start();
    } else {
      // Fallback: no Web Speech API available
      setIsRecording(false);
      setInput((prev) => prev + (prev ? ' ' : '') + '[Voice input not supported in this browser. Try Chrome or Edge.]');
    }
  }, [isRecording, voice.language]);

  const tokenCount = Math.floor(input.length * 0.3);

  // Derive image and file lists from attachedFiles
  const imageFiles = attachedFiles.filter((af) => af.dataUrl);
  const nonImageFiles = attachedFiles.filter((af) => !af.dataUrl);

  return (
    <div className="relative">
      {/* Drag & Drop Overlay */}
      <AnimatePresence>
        {isDragging && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="drop-overlay rounded-t-2xl"
          >
            <div className="text-center">
              <Paperclip className="h-8 w-8 text-purple-400 mx-auto mb-2" />
              <p className="text-sm text-purple-300">Drop files here</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Circuit Breaker Warning */}
      <AnimatePresence>
        {circuitBreakerOpen && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className="mb-2 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-300 text-xs text-center"
          >
            ⚡ Provider is currently unavailable. Please wait or switch to a different model.
          </motion.div>
        )}
      </AnimatePresence>

      {/* Validation Error */}
      <AnimatePresence>
        {validationError && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className="mb-2 px-4 py-2 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-xs text-center"
          >
            {validationError}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Image Previews */}
      <AnimatePresence>
        {imageFiles.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 5 }}
            className="flex flex-wrap gap-2 mb-2 px-2"
          >
            {imageFiles.map((af, i) => {
              const originalIndex = attachedFiles.indexOf(af);
              return (
                <motion.div
                  key={originalIndex}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="relative group"
                >
                  <img
                    src={af.dataUrl}
                    alt={`Attachment ${i + 1}`}
                    className="w-16 h-16 rounded-lg object-cover border border-white/[0.06]"
                  />
                  <button
                    onClick={() => removeFile(originalIndex)}
                    className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500/80 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <X className="h-2.5 w-2.5" />
                  </button>
                </motion.div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>

      {/* File Chips (non-image) */}
      <AnimatePresence>
        {nonImageFiles.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 5 }}
            className="flex flex-wrap gap-1.5 mb-2 px-2"
          >
            {nonImageFiles.map((af, i) => {
              const originalIndex = attachedFiles.indexOf(af);
              return (
                <motion.div
                  key={originalIndex}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-purple-500/10 border border-purple-500/20 text-[11px] text-purple-300"
                >
                  📎 {af.file.name}
                  <button
                    onClick={() => removeFile(originalIndex)}
                    className="hover:text-white transition-colors"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </motion.div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input Area */}
      <div
        className="flex items-end gap-2 p-3 rounded-2xl bg-white/[0.03] border border-white/[0.06] focus-within:border-purple-500/30 focus-within:bg-white/[0.04] transition-all duration-200"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* File Attachment */}
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          multiple
          onChange={handleFileSelect}
        />
        <motion.button
          onClick={() => fileInputRef.current?.click()}
          className="p-2 rounded-lg text-white/30 hover:text-white/60 hover:bg-white/[0.04] transition-colors shrink-0"
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
        >
          <Paperclip className="h-4 w-4" />
        </motion.button>

        {/* Image Attachment */}
        <input
          ref={imageInputRef}
          type="file"
          className="hidden"
          accept="image/*"
          multiple
          onChange={handleImageSelect}
        />
        <motion.button
          onClick={() => imageInputRef.current?.click()}
          className="p-2 rounded-lg text-white/30 hover:text-white/60 hover:bg-white/[0.04] transition-colors shrink-0"
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
        >
          <ImageIcon className="h-4 w-4" />
        </motion.button>

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message GenericAgent..."
          rows={1}
          className="flex-1 bg-transparent text-sm text-white/90 placeholder:text-white/20 resize-none outline-none max-h-[200px] py-1.5"
          disabled={isStreaming}
        />

        {/* Token Counter */}
        {input.length > 0 && (
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-[10px] text-white/20 font-mono self-end mb-2 shrink-0"
          >
            ~{tokenCount} tokens
          </motion.span>
        )}

        {/* Voice Input */}
        {voice.sttProvider && (
          <motion.button
            onClick={toggleRecording}
            className={cn(
              'p-2 rounded-lg transition-colors shrink-0',
              isRecording
                ? 'text-red-400 bg-red-500/10'
                : 'text-white/30 hover:text-white/60 hover:bg-white/[0.04]'
            )}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
          >
            {isRecording ? (
              <motion.div
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 0.5, repeat: Infinity }}
              >
                <MicOff className="h-4 w-4" />
              </motion.div>
            ) : (
              <Mic className="h-4 w-4" />
            )}
          </motion.button>
        )}

        {/* Send / Stop Button */}
        <motion.button
          onClick={isStreaming ? handleStop : handleSend}
          disabled={!isStreaming && (!input.trim() || circuitBreakerOpen)}
          className={cn(
            'p-2 rounded-lg transition-all shrink-0',
            isStreaming
              ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
              : input.trim()
                ? 'bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 border border-purple-500/20'
                : 'text-white/20 cursor-not-allowed'
          )}
          whileHover={isStreaming || input.trim() ? { scale: 1.1 } : {}}
          whileTap={isStreaming || input.trim() ? { scale: 0.9 } : {}}
        >
          {isStreaming ? <Square className="h-4 w-4" /> : <Send className="h-4 w-4" />}
        </motion.button>
      </div>

      {/* Bottom Info */}
      <div className="flex items-center justify-between mt-1.5 px-2">
        <span className="text-[10px] text-white/15">
          Shift+Enter for new line
        </span>
        <span className="text-[10px] text-white/15">
          {currentModel?.name || 'No model selected'}
        </span>
      </div>
    </div>
  );
}
