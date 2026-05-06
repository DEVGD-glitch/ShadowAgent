'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  Brain,
  BookOpen,
  Star,
  Tag,
  ChevronRight,
  FileText,
  Layers,
  Loader2,
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { MOCK_MEMORY_LAYERS, MOCK_SKILLS, MOCK_SOPS, searchMemory, getMemoryLayers, getSkills, getSOPs } from '@/lib/api';
import { cn } from '@/lib/utils';

type MemoryLayer = typeof MOCK_MEMORY_LAYERS[number];
type Skill = typeof MOCK_SKILLS[number];
type SOP = typeof MOCK_SOPS[number];

export function MemoryPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Array<{
    id: string; content: string; layer: string; score: number; timestamp: number;
  }> | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [skillFilter, setSkillFilter] = useState<string>('all');

  // Data fetching state
  const [memoryLayers, setMemoryLayers] = useState<MemoryLayer[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [sops, setSOPs] = useState<SOP[]>([]);
  const [isLoadingLayers, setIsLoadingLayers] = useState(true);
  const [isLoadingSkills, setIsLoadingSkills] = useState(true);
  const [isLoadingSOPs, setIsLoadingSOPs] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch memory layers
  useEffect(() => {
    let cancelled = false;
    setIsLoadingLayers(true);
    getMemoryLayers().then((data) => {
      if (!cancelled) {
        setMemoryLayers(data);
        setIsLoadingLayers(false);
      }
    }).catch((err) => {
      console.error('Failed to fetch memory layers:', err);
      if (!cancelled) {
        setError('Failed to load memory data');
        setIsLoadingLayers(false);
      }
    });
    return () => { cancelled = true; };
  }, []);

  // Fetch skills
  useEffect(() => {
    let cancelled = false;
    setIsLoadingSkills(true);
    getSkills().then((data) => {
      if (!cancelled) {
        setSkills(data);
        setIsLoadingSkills(false);
      }
    }).catch((err) => {
      console.error('Failed to fetch skills:', err);
      if (!cancelled) {
        setError('Failed to load skills data');
        setIsLoadingSkills(false);
      }
    });
    return () => { cancelled = true; };
  }, []);

  // Fetch SOPs
  useEffect(() => {
    let cancelled = false;
    setIsLoadingSOPs(true);
    getSOPs().then((data) => {
      if (!cancelled) {
        setSOPs(data);
        setIsLoadingSOPs(false);
      }
    }).catch((err) => {
      console.error('Failed to fetch SOPs:', err);
      if (!cancelled) {
        setError('Failed to load SOPs data');
        setIsLoadingSOPs(false);
      }
    });
    return () => { cancelled = true; };
  }, []);

  // Cleanup search timeout on unmount
  useEffect(() => {
    return () => {
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    };
  }, []);

  // Search debounce
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const handleSearch = (query: string) => {
    setSearchQuery(query);
    clearTimeout(searchTimeoutRef.current ?? undefined);
    if (!query.trim()) return;
    searchTimeoutRef.current = setTimeout(async () => {
      setIsSearching(true);
      try {
        const results = await searchMemory(query);
        setSearchResults(results);
      } finally {
        setIsSearching(false);
      }
    }, 300);
  };

  const categories = ['all', ...new Set(skills.map((s) => s.category))];

  const filteredSkills =
    skillFilter === 'all'
      ? skills
      : skills.filter((s) => s.category === skillFilter);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="h-full overflow-y-auto p-6"
    >
      {error && (
        <div className="mb-4 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-300 text-xs text-center">
          {error}
        </div>
      )}
      <Tabs defaultValue="layers" className="space-y-4">
        <TabsList className="bg-white/[0.03] border border-white/[0.06]">
          <TabsTrigger
            value="layers"
            className="data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-300"
          >
            <Layers className="h-3.5 w-3.5 mr-1.5" />
            Memory Layers
          </TabsTrigger>
          <TabsTrigger
            value="skills"
            className="data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-300"
          >
            <Star className="h-3.5 w-3.5 mr-1.5" />
            Skills
          </TabsTrigger>
          <TabsTrigger
            value="sops"
            className="data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-300"
          >
            <BookOpen className="h-3.5 w-3.5 mr-1.5" />
            SOPs
          </TabsTrigger>
          <TabsTrigger
            value="search"
            className="data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-300"
          >
            <Search className="h-3.5 w-3.5 mr-1.5" />
            Search
          </TabsTrigger>
        </TabsList>

        {/* Memory Layers Tab */}
        <TabsContent value="layers">
          {isLoadingLayers ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 text-purple-400 animate-spin" />
              <span className="ml-2 text-sm text-white/30">Loading memory layers...</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {memoryLayers.map((layer, i) => {
                const percentage = layer.maxSize > 0 ? Math.round((layer.size / layer.maxSize) * 100) : 0;
                return (
                  <motion.div
                    key={layer.level}
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.08 }}
                  >
                    <Card className="bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04] transition-colors">
                      <CardContent className="p-5">
                        <div className="flex items-center gap-3 mb-3">
                          <span
                            className="text-xs font-mono font-bold px-2 py-1 rounded-md"
                            style={{ background: `${layer.color}20`, color: layer.color }}
                          >
                            {layer.level}
                          </span>
                          <div>
                            <p className="text-sm font-semibold text-white/70">{layer.name}</p>
                            <p className="text-[10px] text-white/25">{layer.description}</p>
                          </div>
                        </div>
                        <div className="h-3 rounded-full bg-white/[0.04] overflow-hidden mb-2">
                          <motion.div
                            className="h-full rounded-full"
                            style={{
                              background: `linear-gradient(90deg, ${layer.color}60, ${layer.color})`,
                            }}
                            initial={{ width: 0 }}
                            animate={{ width: `${percentage}%` }}
                            transition={{ delay: i * 0.08 + 0.3, duration: 0.8 }}
                          />
                        </div>
                        <div className="flex items-center justify-between text-[10px] text-white/25">
                          <span>{layer.size} items</span>
                          <span>{percentage}% full</span>
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                );
              })}
            </div>
          )}
        </TabsContent>

        {/* Skills Tab */}
        <TabsContent value="skills">
          {isLoadingSkills ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 text-purple-400 animate-spin" />
              <span className="ml-2 text-sm text-white/30">Loading skills...</span>
            </div>
          ) : (
            <>
              <div className="mb-4 flex items-center gap-2 flex-wrap">
                {categories.map((cat) => (
                  <motion.button
                    key={cat}
                    onClick={() => setSkillFilter(cat)}
                    className={cn(
                      'px-3 py-1 rounded-lg text-xs font-medium transition-colors',
                      skillFilter === cat
                        ? 'bg-purple-500/20 text-purple-300 border border-purple-500/20'
                        : 'bg-white/[0.03] text-white/30 border border-white/[0.06] hover:bg-white/[0.05]'
                    )}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    {cat === 'all' ? 'All' : cat.charAt(0).toUpperCase() + cat.slice(1)}
                  </motion.button>
                ))}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <AnimatePresence mode="popLayout">
                  {filteredSkills.map((skill, i) => (
                    <motion.div
                      key={skill.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      transition={{ delay: i * 0.04 }}
                      layout
                    >
                      <Card className="bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04] transition-colors cursor-pointer group">
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <Star className="h-4 w-4 text-yellow-400/60" />
                              <p className="text-sm font-medium text-white/70 group-hover:text-white/90 transition-colors">
                                {skill.name}
                              </p>
                            </div>
                            <div className="flex items-center gap-1">
                              <div
                                className={cn(
                                  'w-12 h-1.5 rounded-full bg-white/[0.06] overflow-hidden',
                                )}
                              >
                                <div
                                  className="h-full rounded-full bg-gradient-to-r from-purple-500 to-violet-500"
                                  style={{ width: `${skill.quality * 100}%` }}
                                />
                              </div>
                              <span className="text-[10px] text-white/30 font-mono">
                                {(skill.quality * 100).toFixed(0)}%
                              </span>
                            </div>
                          </div>

                          <div className="flex items-center gap-2 flex-wrap mb-2">
                            <Badge
                              variant="secondary"
                              className="text-[10px] bg-white/[0.04] text-white/40"
                            >
                              {skill.category}
                            </Badge>
                            {skill.tags.slice(0, 3).map((tag) => (
                              <Badge
                                key={tag}
                                variant="outline"
                                className="text-[10px] border-white/[0.08] text-white/25"
                              >
                                <Tag className="h-2 w-2 mr-0.5" />
                                {tag}
                              </Badge>
                            ))}
                          </div>

                          <div className="flex items-center gap-3 text-[10px] text-white/20">
                            <span>Used {skill.usageCount} times</span>
                            <span>
                              Last: {new Date(skill.lastUsed).toLocaleDateString()}
                            </span>
                          </div>
                        </CardContent>
                      </Card>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            </>
          )}
        </TabsContent>

        {/* SOPs Tab */}
        <TabsContent value="sops">
          {isLoadingSOPs ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 text-purple-400 animate-spin" />
              <span className="ml-2 text-sm text-white/30">Loading SOPs...</span>
            </div>
          ) : (
            <div className="space-y-3">
              {sops.map((sop, i) => (
                <motion.div
                  key={sop.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.06 }}
                >
                  <Card className="bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04] transition-colors cursor-pointer group">
                    <CardContent className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-violet-500/10 text-violet-400 shrink-0">
                          <FileText className="h-4 w-4" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-white/70 group-hover:text-white/90 transition-colors">
                            {sop.name}
                          </p>
                          <p className="text-xs text-white/30 mt-0.5 truncate">
                            {sop.description}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-white/20 shrink-0">
                          <span>{sop.steps} steps</span>
                          <ChevronRight className="h-3 w-3 group-hover:text-purple-400 transition-colors" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Search Tab */}
        <TabsContent value="search">
          <Card className="bg-white/[0.02] border-white/[0.06] mb-4">
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" />
                  <Input
                    value={searchQuery}
                    onChange={(e) => handleSearch(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch(searchQuery)}
                    placeholder="Search across all memory layers..."
                    className="pl-9 bg-white/[0.03] border-white/[0.06] text-white/70 placeholder:text-white/20 focus:border-purple-500/30"
                  />
                </div>
                <motion.button
                  onClick={() => handleSearch(searchQuery)}
                  disabled={isSearching || !searchQuery.trim()}
                  className="px-4 py-2 rounded-lg bg-purple-500/20 text-purple-300 text-sm font-medium hover:bg-purple-500/30 disabled:opacity-30 transition-colors"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  {isSearching ? 'Searching...' : 'Search'}
                </motion.button>
              </div>
            </CardContent>
          </Card>

          {searchResults && (
            <div className="space-y-3">
              <p className="text-xs text-white/30">
                Found {searchResults.length} results
              </p>
              <AnimatePresence>
                {searchResults.map((result, i) => (
                  <motion.div
                    key={result.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.08 }}
                  >
                    <Card className="bg-white/[0.02] border-white/[0.06]">
                      <CardContent className="p-4">
                        <div className="flex items-start gap-3">
                          <Badge
                            variant="outline"
                            className="text-[10px] border-purple-500/20 text-purple-300 shrink-0 mt-0.5"
                          >
                            {result.layer}
                          </Badge>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-white/60">{result.content}</p>
                            <div className="flex items-center gap-3 mt-2 text-[10px] text-white/20">
                              <span>Score: {(result.score * 100).toFixed(0)}%</span>
                              <span>{new Date(result.timestamp).toLocaleDateString()}</span>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </motion.div>
  );
}
