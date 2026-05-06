'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Cpu,
  Mic,
  MicOff,
  Globe,
  Shield,
  Palette,
  RefreshCw,
  Eye,
  EyeOff,
  Volume2,
  VolumeX,
  Server,
  Wifi,
  WifiOff,
  AlertCircle,
  Cat,
  Plus,
  Trash2,
  Loader2,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Settings2,
  User,
} from 'lucide-react';
import { useSettingsStore, type ThemeMode, STT_PROVIDERS, TTS_PROVIDERS, PERSONALITIES, PET_SKINS, VOICE_STYLES, LLM_PROVIDERS } from '@/stores/settings-store';
import { useAgentStore } from '@/stores/agent-store';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { ModelList } from './model-list';
import { HealthDashboard } from './health-dashboard';
import { getModels, testConnection, getMcpStatus } from '@/lib/api';
import { checkBackendHealth } from '@/lib/backend';

const THEME_OPTIONS: { id: ThemeMode; label: string; preview: string }[] = [
  { id: 'dark', label: 'Dark', preview: 'bg-gradient-to-br from-gray-900 to-gray-800' },
  { id: 'light', label: 'Light', preview: 'bg-gradient-to-br from-white to-gray-100' },
  { id: 'catppuccin', label: 'Catppuccin (Coming soon)', preview: 'bg-gradient-to-br from-[#1e1e2e] to-[#313244]' },
  { id: 'glass', label: 'Glass (Coming soon)', preview: 'bg-gradient-to-br from-purple-900/50 to-blue-900/50 backdrop-blur' },
];

export function SettingsPage() {
  const {
    theme,
    setTheme,
    autonomousMode,
    setAutonomousMode,
    autoUpdate,
    setAutoUpdate,
    voice,
    setVoice,
    avatar,
    setAvatar,
    desktopPet,
    setDesktopPet,
    personality,
    setPersonality,
    mcpServers,
    setMcpServers,
    backendConfig,
    setBackendConfig,
    apiKeys,
    setApiKey,
    removeApiKey,
    language,
    setLanguage,
  } = useSettingsStore();

  const { setModels, setBackendConnected } = useAgentStore();

  const [showSttKey, setShowSttKey] = useState(false);
  const [showTtsKey, setShowTtsKey] = useState(false);
  const [backendTestStatus, setBackendTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [newMcpName, setNewMcpName] = useState('');
  const [newMcpUrl, setNewMcpUrl] = useState('');
  const [refreshingMcp, setRefreshingMcp] = useState(false);

  // Test backend connection
  const handleTestBackend = async () => {
    setBackendTestStatus('testing');
    const isHealthy = await checkBackendHealth();
    if (isHealthy) {
      setBackendTestStatus('success');
      setBackendConnected('connected');
      // Load models from backend
      const models = await getModels();
      setModels(models);
      setTimeout(() => setBackendTestStatus('idle'), 3000);
    } else {
      setBackendTestStatus('error');
      setBackendConnected('disconnected');
      setTimeout(() => setBackendTestStatus('idle'), 3000);
    }
  };

  // Refresh MCP status
  const handleRefreshMcp = async () => {
    setRefreshingMcp(true);
    const status = await getMcpStatus();
    setMcpServers(status);
    setRefreshingMcp(false);
  };

  // Add MCP server
  const handleAddMcp = () => {
    if (!newMcpName.trim() || !newMcpUrl.trim()) return;
    // Validate URL format
    try {
      new URL(newMcpUrl.trim());
    } catch {
      alert('Invalid URL format. Please enter a valid URL (e.g., http://localhost:3001)');
      return;
    }
    setMcpServers([
      ...mcpServers,
      { name: newMcpName.trim(), url: newMcpUrl.trim(), status: 'disconnected', toolsCount: 0 },
    ]);
    setNewMcpName('');
    setNewMcpUrl('');
  };

  // Remove MCP server
  const handleRemoveMcp = (index: number) => {
    setMcpServers(mcpServers.filter((_, i) => i !== index));
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="h-full overflow-y-auto p-6"
    >
      <Tabs defaultValue="models" className="space-y-4">
        <TabsList className="bg-white/[0.03] border border-white/[0.06] flex-wrap">
          <TabsTrigger
            value="models"
            className="data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-300"
          >
            <Cpu className="h-3.5 w-3.5 mr-1.5" />
            Models
          </TabsTrigger>
          <TabsTrigger
            value="voice"
            className="data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-300"
          >
            <Mic className="h-3.5 w-3.5 mr-1.5" />
            Voice & Avatar
          </TabsTrigger>
          <TabsTrigger
            value="mcp"
            className="data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-300"
          >
            <Server className="h-3.5 w-3.5 mr-1.5" />
            MCP
          </TabsTrigger>
          <TabsTrigger
            value="general"
            className="data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-300"
          >
            <Palette className="h-3.5 w-3.5 mr-1.5" />
            General
          </TabsTrigger>
          <TabsTrigger
            value="health"
            className="data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-300"
          >
            <Shield className="h-3.5 w-3.5 mr-1.5" />
            Health
          </TabsTrigger>
        </TabsList>

        {/* Models Tab */}
        <TabsContent value="models">
          <div className="space-y-4">
            {/* API Keys per Provider */}
            <Card className="bg-white/[0.02] border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-white/70 flex items-center gap-2">
                  <Globe className="h-4 w-4 text-purple-400" />
                  Provider API Keys
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {LLM_PROVIDERS.map((provider) => (
                  <ProviderKeyInput
                    key={provider.id}
                    provider={provider.name}
                    providerId={provider.id}
                    apiKey={apiKeys[provider.name] || ''}
                    onSetKey={(key) => setApiKey(provider.name, key)}
                    onRemoveKey={() => removeApiKey(provider.name)}
                    requiresKey={provider.requiresKey}
                    icon={provider.icon}
                    description={provider.description}
                    apiKeyUrl={provider.apiKeyUrl}
                  />
                ))}
              </CardContent>
            </Card>

            {/* Model List */}
            <Card className="bg-white/[0.02] border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-white/70 flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-purple-400" />
                  LLM Model Management
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ModelList />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Voice & Avatar Tab */}
        <TabsContent value="voice">
          <div className="space-y-4">
            {/* STT Config */}
            <Card className="bg-white/[0.02] border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-white/70 flex items-center gap-2">
                  <Mic className="h-4 w-4 text-blue-400" />
                  Speech-to-Text
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label className="text-xs text-white/50">Enable STT</Label>
                  <Switch
                    checked={voice.sttProvider !== ''}
                    onCheckedChange={(checked) =>
                      setVoice({ sttProvider: checked ? 'openai' : '' })
                    }
                  />
                </div>
                {voice.sttProvider && (
                  <>
                    <div>
                      <Label className="text-xs text-white/50 mb-1.5 block">Provider</Label>
                      <select
                        value={voice.sttProvider}
                        onChange={(e) => setVoice({ sttProvider: e.target.value })}
                        className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-white/70 text-xs appearance-none cursor-pointer focus:border-purple-500/30 focus:outline-none"
                      >
                        {STT_PROVIDERS.map((p) => (
                          <option key={p.id} value={p.id} className="bg-[oklch(0.12_0.015_280)]">
                            {p.name} — {p.description}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <Label className="text-xs text-white/50 mb-1.5 block">Language</Label>
                      <select
                        value={voice.language}
                        onChange={(e) => setVoice({ language: e.target.value })}
                        className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-white/70 text-xs appearance-none cursor-pointer focus:border-purple-500/30 focus:outline-none"
                      >
                        <option value="en" className="bg-[oklch(0.12_0.015_280)]">English</option>
                        <option value="fr" className="bg-[oklch(0.12_0.015_280)]">French</option>
                        <option value="ja" className="bg-[oklch(0.12_0.015_280)]">Japanese</option>
                        <option value="zh" className="bg-[oklch(0.12_0.015_280)]">Chinese</option>
                        <option value="de" className="bg-[oklch(0.12_0.015_280)]">German</option>
                        <option value="es" className="bg-[oklch(0.12_0.015_280)]">Spanish</option>
                      </select>
                    </div>
                    <div>
                      <Label className="text-xs text-white/50 mb-1.5 block">Voice Style</Label>
                      <div className="flex gap-2">
                        {VOICE_STYLES.map((style) => (
                          <motion.button
                            key={style.id}
                            onClick={() => setVoice({ voiceStyle: style.id })}
                            className={cn(
                              'flex-1 px-3 py-2 rounded-lg text-xs transition-colors border',
                              voice.voiceStyle === style.id
                                ? 'bg-purple-500/20 text-purple-300 border-purple-500/20'
                                : 'bg-white/[0.03] text-white/40 border-white/[0.06] hover:bg-white/[0.06]'
                            )}
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                          >
                            {style.name}
                          </motion.button>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            {/* TTS Config */}
            <Card className="bg-white/[0.02] border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-white/70 flex items-center gap-2">
                  <Volume2 className="h-4 w-4 text-green-400" />
                  Text-to-Speech
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label className="text-xs text-white/50">Enable TTS</Label>
                  <Switch
                    checked={voice.ttsProvider !== ''}
                    onCheckedChange={(checked) =>
                      setVoice({ ttsProvider: checked ? 'edge' : '' })
                    }
                  />
                </div>
                {voice.ttsProvider && (
                  <div>
                    <Label className="text-xs text-white/50 mb-1.5 block">Provider</Label>
                    <select
                      value={voice.ttsProvider}
                      onChange={(e) => setVoice({ ttsProvider: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-white/70 text-xs appearance-none cursor-pointer focus:border-purple-500/30 focus:outline-none"
                    >
                      {TTS_PROVIDERS.map((p) => (
                        <option key={p.id} value={p.id} className="bg-[oklch(0.12_0.015_280)]">
                          {p.name} — {p.description}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* VRM Avatar Config */}
            <Card className="bg-white/[0.02] border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-white/70 flex items-center gap-2">
                  🎭 VRM Avatar
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-xs text-white/50">Enable Avatar</Label>
                    <p className="text-[10px] text-white/25">3D avatar with lip-sync and expressions</p>
                  </div>
                  <Switch
                    checked={avatar.enabled}
                    onCheckedChange={(checked) => setAvatar({ enabled: checked })}
                  />
                </div>
                {avatar.enabled && (
                  <>
                    <div>
                      <Label className="text-xs text-white/50 mb-1.5 block">Avatar Model Path</Label>
                      <Input
                        value={avatar.modelPath}
                        onChange={(e) => setAvatar({ modelPath: e.target.value })}
                        placeholder="/path/to/avatar.vrm"
                        className="bg-white/[0.03] border-white/[0.06] text-white/70 text-xs"
                      />
                    </div>
                    <div>
                      <Label className="text-xs text-white/50 mb-1.5 block">Expression Mode</Label>
                      <div className="flex gap-2">
                        {(['automatic', 'manual'] as const).map((mode) => (
                          <motion.button
                            key={mode}
                            onClick={() => setAvatar({ expressionMode: mode })}
                            className={cn(
                              'flex-1 px-3 py-2 rounded-lg text-xs transition-colors border capitalize',
                              avatar.expressionMode === mode
                                ? 'bg-purple-500/20 text-purple-300 border-purple-500/20'
                                : 'bg-white/[0.03] text-white/40 border-white/[0.06] hover:bg-white/[0.06]'
                            )}
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                          >
                            {mode}
                          </motion.button>
                        ))}
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <Label className="text-xs text-white/50">Show Lip Sync</Label>
                      <Switch
                        checked={avatar.showLipSync}
                        onCheckedChange={(checked) => setAvatar({ showLipSync: checked })}
                      />
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            {/* Personality Selector */}
            <Card className="bg-white/[0.02] border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-white/70 flex items-center gap-2">
                  💖 Personality
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                  {PERSONALITIES.map((p) => (
                    <motion.button
                      key={p.id}
                      onClick={() => setPersonality(p.id)}
                      className={cn(
                        'flex flex-col items-center gap-2 p-3 rounded-xl border transition-all text-center',
                        personality === p.id
                          ? `bg-gradient-to-br ${p.color} ${p.border}`
                          : 'bg-white/[0.02] border-white/[0.04] hover:bg-white/[0.04]'
                      )}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                    >
                      <span className="text-2xl">{p.emoji}</span>
                      <span className={cn(
                        'text-xs font-medium',
                        personality === p.id ? 'text-white/80' : 'text-white/50'
                      )}>
                        {p.name}
                      </span>
                      <span className="text-[9px] text-white/25 leading-tight">{p.description}</span>
                    </motion.button>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Desktop Pet */}
            <Card className="bg-white/[0.02] border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-white/70 flex items-center gap-2">
                  <Cat className="h-4 w-4 text-orange-400" />
                  Desktop Pet
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-xs text-white/50">Enable Desktop Pet</Label>
                    <p className="text-[10px] text-white/25">Animated companion on your screen</p>
                  </div>
                  <Switch
                    checked={desktopPet.enabled}
                    onCheckedChange={(checked) => setDesktopPet({ enabled: checked })}
                  />
                </div>
                {desktopPet.enabled && (
                  <>
                    <div>
                      <Label className="text-xs text-white/50 mb-1.5 block">Skin</Label>
                      <div className="grid grid-cols-4 sm:grid-cols-7 gap-2">
                        {PET_SKINS.map((skin) => (
                          <motion.button
                            key={skin.id}
                            onClick={() => setDesktopPet({ skin: skin.id })}
                            className={cn(
                              'flex flex-col items-center gap-1 p-2 rounded-xl border transition-all',
                              desktopPet.skin === skin.id
                                ? 'bg-purple-500/20 border-purple-500/20'
                                : 'bg-white/[0.02] border-white/[0.04] hover:bg-white/[0.04]'
                            )}
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                          >
                            <span className="text-xl">{skin.emoji}</span>
                            <span className="text-[9px] text-white/40">{skin.name}</span>
                          </motion.button>
                        ))}
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <Label className="text-xs text-white/50">Click Interactions</Label>
                      <Switch
                        checked={desktopPet.interactionEnabled}
                        onCheckedChange={(checked) => setDesktopPet({ interactionEnabled: checked })}
                      />
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* MCP Tab */}
        <TabsContent value="mcp">
          <Card className="bg-white/[0.02] border-white/[0.06]">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold text-white/70 flex items-center gap-2">
                  <Server className="h-4 w-4 text-orange-400" />
                  MCP Server Configuration
                </CardTitle>
                <motion.button
                  onClick={handleRefreshMcp}
                  className="p-1.5 rounded-lg text-white/30 hover:text-white/60 hover:bg-white/[0.04] transition-colors"
                  whileHover={{ scale: 1.1, rotate: 180 }}
                  whileTap={{ scale: 0.9 }}
                >
                  <RefreshCw className={cn('h-3.5 w-3.5', refreshingMcp && 'animate-spin')} />
                </motion.button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {mcpServers.map((server, i) => (
                <motion.div
                  key={`${server.name}-${i}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.06 }}
                  className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]"
                >
                  <div
                    className={cn(
                      'p-1.5 rounded-md',
                      server.status === 'connected'
                        ? 'bg-green-500/10 text-green-400'
                        : server.status === 'error'
                          ? 'bg-red-500/10 text-red-400'
                          : 'bg-gray-500/10 text-gray-400'
                    )}
                  >
                    {server.status === 'connected' ? (
                      <Wifi className="h-3.5 w-3.5" />
                    ) : server.status === 'error' ? (
                      <AlertCircle className="h-3.5 w-3.5" />
                    ) : (
                      <WifiOff className="h-3.5 w-3.5" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-white/60">{server.name}</p>
                    <p className="text-[10px] text-white/25 font-mono">{server.url}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {server.toolsCount > 0 && (
                      <Badge variant="outline" className="text-[10px] border-white/[0.08] text-white/30">
                        {server.toolsCount} tools
                      </Badge>
                    )}
                    <Badge
                      className={cn(
                        'text-[9px] py-0',
                        server.status === 'connected' && 'bg-green-500/10 text-green-300 border-green-500/20',
                        server.status === 'error' && 'bg-red-500/10 text-red-300 border-red-500/20',
                        server.status === 'disconnected' && 'bg-gray-500/10 text-gray-300 border-gray-500/20',
                      )}
                      variant="outline"
                    >
                      {server.status}
                    </Badge>
                    <motion.button
                      onClick={() => handleRemoveMcp(i)}
                      className="p-1 rounded-md text-white/20 hover:text-red-400 transition-colors"
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.9 }}
                    >
                      <Trash2 className="h-3 w-3" />
                    </motion.button>
                  </div>
                </motion.div>
              ))}

              {/* Add MCP Server */}
              <Separator className="bg-white/[0.06]" />
              <div className="space-y-2">
                <p className="text-xs text-white/40 font-medium">Add MCP Server</p>
                <div className="flex gap-2">
                  <Input
                    value={newMcpName}
                    onChange={(e) => setNewMcpName(e.target.value)}
                    placeholder="Name"
                    className="bg-white/[0.03] border-white/[0.06] text-white/70 text-xs flex-1"
                  />
                  <Input
                    value={newMcpUrl}
                    onChange={(e) => setNewMcpUrl(e.target.value)}
                    placeholder="http://localhost:3001"
                    className="bg-white/[0.03] border-white/[0.06] text-white/70 text-xs flex-1"
                  />
                  <Button
                    onClick={handleAddMcp}
                    size="sm"
                    disabled={!newMcpName.trim() || !newMcpUrl.trim()}
                    className="bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 border border-purple-500/20 shrink-0"
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* General Tab */}
        <TabsContent value="general">
          <div className="space-y-4">
            {/* Backend Connection */}
            <Card className="bg-white/[0.02] border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-white/70 flex items-center gap-2">
                  <Globe className="h-4 w-4 text-cyan-400" />
                  Backend Connection
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-xs text-white/50 mb-1.5 block">Host</Label>
                    <Input
                      value={backendConfig.host}
                      onChange={(e) => setBackendConfig({ host: e.target.value })}
                      className="bg-white/[0.03] border-white/[0.06] text-white/70 text-xs"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-white/50 mb-1.5 block">Port</Label>
                    <Input
                      type="number"
                      value={backendConfig.port}
                      onChange={(e) => setBackendConfig({ port: parseInt(e.target.value) || 8765 })}
                      className="bg-white/[0.03] border-white/[0.06] text-white/70 text-xs"
                    />
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <Label className="text-xs text-white/50">Auto-connect on startup</Label>
                  <Switch
                    checked={backendConfig.autoConnect}
                    onCheckedChange={(checked) => setBackendConfig({ autoConnect: checked })}
                  />
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    onClick={handleTestBackend}
                    size="sm"
                    className="bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 border border-purple-500/20"
                    disabled={backendTestStatus === 'testing'}
                  >
                    {backendTestStatus === 'testing' ? (
                      <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                    ) : backendTestStatus === 'success' ? (
                      <CheckCircle2 className="h-3.5 w-3.5 mr-1.5 text-green-400" />
                    ) : backendTestStatus === 'error' ? (
                      <XCircle className="h-3.5 w-3.5 mr-1.5 text-red-400" />
                    ) : null}
                    Test Connection
                  </Button>
                  {backendTestStatus === 'success' && (
                    <span className="text-xs text-green-400">Connected!</span>
                  )}
                  {backendTestStatus === 'error' && (
                    <span className="text-xs text-red-400">Cannot reach backend</span>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Theme */}
            <Card className="bg-white/[0.02] border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-white/70 flex items-center gap-2">
                  <Palette className="h-4 w-4 text-purple-400" />
                  Theme
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-4 gap-3">
                  {THEME_OPTIONS.map((opt) => (
                    <motion.button
                      key={opt.id}
                      onClick={() => setTheme(opt.id)}
                      className={cn(
                        'flex flex-col items-center gap-2 p-3 rounded-xl border transition-all',
                        theme === opt.id
                          ? 'border-purple-500/30 bg-purple-500/10'
                          : 'border-white/[0.04] bg-white/[0.02] hover:bg-white/[0.04]'
                      )}
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                    >
                      <div
                        className={cn(
                          'w-full h-8 rounded-lg border border-white/10',
                          opt.preview
                        )}
                      />
                      <span
                        className={cn(
                          'text-[10px] font-medium',
                          theme === opt.id ? 'text-purple-300' : 'text-white/40'
                        )}
                      >
                        {opt.label}
                      </span>
                    </motion.button>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Language */}
            <Card className="bg-white/[0.02] border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-white/70 flex items-center gap-2">
                  <Globe className="h-4 w-4 text-blue-400" />
                  Language
                </CardTitle>
              </CardHeader>
              <CardContent>
                <select
                  className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-white/70 text-xs appearance-none cursor-pointer focus:border-purple-500/30 focus:outline-none"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                >
                  <option value="en" className="bg-[oklch(0.12_0.015_280)]">English</option>
                  <option value="fr" className="bg-[oklch(0.12_0.015_280)]">French</option>
                  <option value="ja" className="bg-[oklch(0.12_0.015_280)]">Japanese</option>
                  <option value="zh" className="bg-[oklch(0.12_0.015_280)]">Chinese</option>
                </select>
              </CardContent>
            </Card>

            {/* Toggles */}
            <Card className="bg-white/[0.02] border-white/[0.06]">
              <CardHeader>
                <CardTitle className="text-sm font-semibold text-white/70">
                  Preferences
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Shield className="h-4 w-4 text-orange-400" />
                    <div>
                      <p className="text-xs text-white/60">Autonomous Mode</p>
                      <p className="text-[10px] text-white/25">Allow agent to act without confirmation</p>
                    </div>
                  </div>
                  <Switch
                    checked={autonomousMode}
                    onCheckedChange={setAutonomousMode}
                  />
                </div>
                <Separator className="bg-white/[0.06]" />
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <RefreshCw className="h-4 w-4 text-green-400" />
                    <div>
                      <p className="text-xs text-white/60">Auto-Update</p>
                      <p className="text-[10px] text-white/25">Automatically check for updates</p>
                    </div>
                  </div>
                  <Switch
                    checked={autoUpdate}
                    onCheckedChange={setAutoUpdate}
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Health Tab */}
        <TabsContent value="health">
          <HealthDashboard />
        </TabsContent>
      </Tabs>
    </motion.div>
  );
}

// ============ Provider Key Input Subcomponent ============

function ProviderKeyInput({
  provider,
  providerId,
  apiKey,
  onSetKey,
  onRemoveKey,
  requiresKey = true,
  icon = '🔑',
  description = '',
  apiKeyUrl = '',
}: {
  provider: string;
  providerId: string;
  apiKey: string;
  onSetKey: (key: string) => void;
  onRemoveKey: () => void;
  requiresKey?: boolean;
  icon?: string;
  description?: string;
  apiKeyUrl?: string;
}) {
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<'idle' | 'success' | 'error'>('idle');

  const handleTest = async () => {
    setTesting(true);
    setTestResult('idle');
    const result = await testConnection(providerId.toLowerCase(), apiKey);
    setTestResult(result.success ? 'success' : 'error');
    setTesting(false);
    setTimeout(() => setTestResult('idle'), 3000);
  };

  // Free providers don't need a key
  if (!requiresKey) {
    return (
      <motion.div
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        className="space-y-2"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-base">{icon}</span>
            <div>
              <Label className="text-xs text-white/50">{provider}</Label>
              <p className="text-[9px] text-white/25">{description}</p>
            </div>
          </div>
          <Badge variant="outline" className="text-[9px] border-green-500/20 text-green-300">
            Free — No key needed
          </Badge>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className="space-y-2"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">{icon}</span>
          <div>
            <Label className="text-xs text-white/50">{provider}</Label>
            <p className="text-[9px] text-white/25">{description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {apiKey && (
            <Badge variant="outline" className="text-[9px] border-green-500/20 text-green-300">
              Key set
            </Badge>
          )}
          {apiKeyUrl && (
            <a
              href={apiKeyUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[9px] text-purple-400 hover:text-purple-300 flex items-center gap-0.5"
            >
              <ExternalLink className="h-2.5 w-2.5" />
              Get key
            </a>
          )}
        </div>
      </div>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Input
            type={showKey ? 'text' : 'password'}
            value={apiKey}
            onChange={(e) => onSetKey(e.target.value)}
            placeholder={`Enter ${provider} API key...`}
            className="bg-white/[0.03] border-white/[0.06] text-white/70 text-xs pr-8 font-mono"
          />
          <button
            onClick={() => setShowKey(!showKey)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
          >
            {showKey ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
          </button>
        </div>
        {apiKey && (
          <>
            <Button
              onClick={handleTest}
              size="sm"
              disabled={testing}
              className="bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 border border-purple-500/20 shrink-0 text-xs px-3"
            >
              {testing ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : testResult === 'success' ? (
                <CheckCircle2 className="h-3 w-3 text-green-400" />
              ) : testResult === 'error' ? (
                <XCircle className="h-3 w-3 text-red-400" />
              ) : (
                'Test'
              )}
            </Button>
            <Button
              onClick={onRemoveKey}
              size="sm"
              variant="destructive"
              className="shrink-0 text-xs px-2"
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </>
        )}
      </div>
    </motion.div>
  );
}
