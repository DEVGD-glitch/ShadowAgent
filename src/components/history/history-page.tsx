'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  Trash2,
  MessageSquare,
  Calendar,
  Clock,
  ArrowRight,
  Plus,
} from 'lucide-react';
import { useAgentStore } from '@/stores/agent-store';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';

export function HistoryPage() {
  const { sessions, removeSession, loadSession, clearMessages, addSession } = useAgentStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const filteredSessions = sessions.filter(
    (s) =>
      s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.messageCount.toString().includes(searchQuery)
  );

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / 86400000);

    if (days === 0) return 'Today';
    if (days === 1) return 'Yesterday';
    if (days < 7) return `${days} days ago`;
    return date.toLocaleDateString();
  };

  const handleLoadSession = (id: string) => {
    loadSession(id);
  };

  const handleNewSession = () => {
    clearMessages();
    const newSession = {
      id: `session-${crypto.randomUUID()}`,
      title: 'New Conversation',
      messageCount: 0,
      date: Date.now(),
      messages: [],
    };
    addSession(newSession);
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="h-full overflow-y-auto p-6"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-white/80">Session History</h2>
          <p className="text-xs text-white/30 mt-0.5">
            {sessions.length} session{sessions.length !== 1 ? 's' : ''}
          </p>
        </div>
        <Button
          onClick={handleNewSession}
          size="sm"
          className="bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 border border-purple-500/20"
        >
          <Plus className="h-3.5 w-3.5 mr-1" />
          New Chat
        </Button>
      </div>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" />
        <Input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search sessions..."
          className="pl-9 bg-white/[0.03] border-white/[0.06] text-white/70 placeholder:text-white/20 focus:border-purple-500/30"
        />
      </div>

      {/* Session List */}
      <div className="space-y-2">
        <AnimatePresence>
          {filteredSessions.map((session, i) => (
            <motion.div
              key={session.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: -20, height: 0 }}
              transition={{ delay: i * 0.04 }}
              layout
              className="group"
            >
              <div className="flex items-center gap-4 p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] hover:border-white/[0.08] transition-all cursor-pointer"
                onClick={() => handleLoadSession(session.id)}
              >
                {/* Icon */}
                <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400 shrink-0">
                  <MessageSquare className="h-4 w-4" />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white/70 truncate">
                    {session.title}
                  </p>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="flex items-center gap-1 text-[10px] text-white/25">
                      <MessageSquare className="h-2.5 w-2.5" />
                      {session.messageCount} messages
                    </span>
                    <span className="flex items-center gap-1 text-[10px] text-white/25">
                      <Calendar className="h-2.5 w-2.5" />
                      {formatDate(session.date)}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <AlertDialog open={deleteId === session.id} onOpenChange={(open) => !open && setDeleteId(null)}>
                    <AlertDialogTrigger asChild>
                      <motion.button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteId(session.id);
                        }}
                        className="p-1.5 rounded-md text-white/20 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </motion.button>
                    </AlertDialogTrigger>
                    <AlertDialogContent className="bg-[oklch(0.12_0.015_280)] border-white/10 text-white">
                      <AlertDialogHeader>
                        <AlertDialogTitle>Delete Session</AlertDialogTitle>
                        <AlertDialogDescription className="text-white/40">
                          Are you sure you want to delete &quot;{session.title}&quot;? This action cannot be undone.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel className="bg-white/5 border-white/10 text-white/70">Cancel</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={() => {
                            removeSession(session.id);
                            setDeleteId(null);
                          }}
                          className="bg-red-500/20 text-red-300 hover:bg-red-500/30"
                        >
                          Delete
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                  <motion.div
                    className="p-1.5 rounded-md text-white/20 group-hover:text-purple-400 transition-colors"
                    whileHover={{ scale: 1.1 }}
                  >
                    <ArrowRight className="h-3.5 w-3.5" />
                  </motion.div>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {filteredSessions.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-12"
          >
            <Clock className="h-8 w-8 text-white/10 mx-auto mb-3" />
            <p className="text-sm text-white/30">
              {searchQuery ? 'No matching sessions found' : 'No sessions yet'}
            </p>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}
