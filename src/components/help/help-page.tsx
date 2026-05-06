'use client';

import { motion } from 'framer-motion';
import {
  Book,
  Keyboard,
  MessageSquare,
  Sparkles,
  Zap,
  Shield,
  LifeBuoy,
  ExternalLink,
  ChevronRight,
  Search,
  FileText,
  Video,
  MessageCircle,
  Star,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { useState } from 'react';

const KEYBOARD_SHORTCUTS = [
  { key: 'Ctrl + K', action: 'Open command palette' },
  { key: 'Ctrl + /', action: 'Show keyboard shortcuts' },
  { key: 'Ctrl + Enter', action: 'Send message' },
  { key: 'Escape', action: 'Stop generation' },
  { key: 'Ctrl + N', action: 'New conversation' },
  { key: 'Ctrl + Shift + S', action: 'Toggle sidebar' },
];

const FAQ_ITEMS = [
  {
    question: 'How do I get started with Shadow Agent?',
    answer: 'Shadow Agent works out of the box with free providers! Click the settings icon, and you can start chatting immediately. For enhanced capabilities, add your API keys from OpenAI, Anthropic, or Google.',
  },
  {
    question: 'What are the free providers?',
    answer: 'Pollinations AI provides free LLM access, Edge TTS provides free text-to-speech, and your browser provides free speech recognition. No API keys needed to get started!',
  },
  {
    question: 'How do I add my own API keys?',
    answer: 'Go to Settings > Models, and enter your API keys for the providers you want to use. Your keys are stored securely using your operating system keychain.',
  },
  {
    question: 'Can I use Shadow Agent in other languages?',
    answer: 'Yes! Shadow Agent supports English, French, Chinese, Japanese, and more. You can configure your preferred language in Settings > General.',
  },
  {
    question: 'How does the memory system work?',
    answer: 'Shadow Agent has a 5-layer memory system: Meta Rules (safety), Index (semantic search), Global Facts (knowledge), Skills (procedures), and Archives (history). This allows it to learn and remember information across conversations.',
  },
  {
    question: 'What is MCP?',
    answer: 'MCP (Model Context Protocol) allows Shadow Agent to connect to external tools and services. You can configure MCP servers in Settings > MCP.',
  },
];

const FEATURE_GUIDES = [
  {
    icon: MessageSquare,
    title: 'Chat',
    description: 'Start conversations, attach files, use voice input',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10',
  },
  {
    icon: Sparkles,
    title: 'AI Models',
    description: 'Switch between Claude, GPT, Gemini, and more',
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/10',
  },
  {
    icon: Zap,
    title: 'Voice Mode',
    description: 'Speak to Shadow Agent and hear responses',
    color: 'text-green-400',
    bgColor: 'bg-green-500/10',
  },
  {
    icon: Shield,
    title: 'Privacy',
    description: 'Your data stays on your device',
    color: 'text-cyan-400',
    bgColor: 'bg-cyan-500/10',
  },
];

export function HelpPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null);

  const filteredFaq = FAQ_ITEMS.filter(
    (item) =>
      item.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.answer.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="h-full overflow-y-auto p-6 space-y-6"
    >
      {/* Header */}
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-bold text-white">Help Center</h1>
        <p className="text-white/50">Learn how to get the most out of Shadow Agent</p>
      </div>

      {/* Search */}
      <div className="relative max-w-md mx-auto">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/40" />
        <Input
          placeholder="Search help articles..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10 bg-white/[0.03] border-white/[0.06] focus:border-purple-500/30"
        />
      </div>

      {/* Quick Start Guide */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {FEATURE_GUIDES.map((feature, i) => (
          <motion.div
            key={feature.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
          >
            <Card className="bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04] transition-colors cursor-pointer">
              <CardContent className="flex flex-col items-center text-center p-4">
                <div className={`p-3 rounded-xl ${feature.bgColor} mb-3`}>
                  <feature.icon className={`h-6 w-6 ${feature.color}`} />
                </div>
                <h3 className="font-medium text-white/80 text-sm">{feature.title}</h3>
                <p className="text-white/40 text-xs mt-1">{feature.description}</p>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Keyboard Shortcuts */}
      <Card className="bg-white/[0.02] border-white/[0.06]">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm font-semibold text-white/70">
            <Keyboard className="h-4 w-4 text-purple-400" />
            Keyboard Shortcuts
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {KEYBOARD_SHORTCUTS.map((shortcut) => (
              <div
                key={shortcut.key}
                className="flex items-center justify-between p-2 rounded-lg bg-white/[0.03]"
              >
                <span className="text-white/60 text-xs">{shortcut.action}</span>
                <kbd className="px-2 py-1 rounded bg-white/[0.06] text-white/80 text-xs font-mono">
                  {shortcut.key}
                </kbd>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* FAQ */}
      <Card className="bg-white/[0.02] border-white/[0.06]">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm font-semibold text-white/70">
            <Book className="h-4 w-4 text-blue-400" />
            Frequently Asked Questions
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {filteredFaq.map((faq, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: i * 0.05 }}
            >
              <button
                onClick={() => setExpandedFaq(expandedFaq === i ? null : i)}
                className="w-full flex items-center justify-between p-3 rounded-lg bg-white/[0.03] hover:bg-white/[0.05] transition-colors text-left"
              >
                <span className="text-white/80 text-sm pr-4">{faq.question}</span>
                <ChevronRight
                  className={`h-4 w-4 text-white/40 transition-transform ${
                    expandedFaq === i ? 'rotate-90' : ''
                  }`}
                />
              </button>
              {expandedFaq === i && (
                <motion.p
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  className="text-white/50 text-sm mt-2 px-3"
                >
                  {faq.answer}
                </motion.p>
              )}
            </motion.div>
          ))}
          {filteredFaq.length === 0 && (
            <p className="text-white/40 text-center py-4">No results found</p>
          )}
        </CardContent>
      </Card>

      {/* Resources */}
      <Card className="bg-white/[0.02] border-white/[0.06]">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm font-semibold text-white/70">
            <LifeBuoy className="h-4 w-4 text-green-400" />
            Resources
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <a
              href="https://github.com/DEVGD-glitch/GenericAgent_Shadow"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.03] hover:bg-white/[0.05] transition-colors"
            >
              <Star className="h-5 w-5 text-white/60" />
              <div>
                <p className="text-white/80 text-sm font-medium">GitHub Repository</p>
                <p className="text-white/40 text-xs">View source code</p>
              </div>
              <ExternalLink className="h-4 w-4 text-white/30 ml-auto" />
            </a>
            <a
              href="#"
              className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.03] hover:bg-white/[0.05] transition-colors"
            >
              <FileText className="h-5 w-5 text-white/60" />
              <div>
                <p className="text-white/80 text-sm font-medium">Documentation</p>
                <p className="text-white/40 text-xs">Full documentation</p>
              </div>
              <ExternalLink className="h-4 w-4 text-white/30 ml-auto" />
            </a>
            <a
              href="#"
              className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.03] hover:bg-white/[0.05] transition-colors"
            >
              <MessageCircle className="h-5 w-5 text-white/60" />
              <div>
                <p className="text-white/80 text-sm font-medium">Community</p>
                <p className="text-white/40 text-xs">Join discussions</p>
              </div>
              <ExternalLink className="h-4 w-4 text-white/30 ml-auto" />
            </a>
          </div>
        </CardContent>
      </Card>

      {/* Version Info */}
      <div className="text-center text-white/30 text-xs">
        <p>Shadow Agent v1.2.0</p>
        <p className="mt-1">Built with ❤️ by the Shadow Agent Team</p>
      </div>
    </motion.div>
  );
}
