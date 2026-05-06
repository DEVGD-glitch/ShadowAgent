'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronRight,
  ChevronLeft,
  Sparkles,
  Eye,
  EyeOff,
  Loader2,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Wifi,
  WifiOff,
  Globe,
  Mic,
  Volume2,
  Cat,
} from 'lucide-react';
import {
  useOnboardingStore,
  ONBOARDING_PROVIDERS,
} from '@/stores/onboarding-store';
import { useSettingsStore, STT_PROVIDERS, TTS_PROVIDERS, PERSONALITIES, PET_SKINS } from '@/stores/settings-store';
import { useAgentStore } from '@/stores/agent-store';
import { testConnection, getModels } from '@/lib/api';
import { checkBackendHealth, loginToBackend } from '@/lib/backend';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';

const STEPS = [
  { title: 'Welcome', subtitle: 'Meet your AI companion' },
  { title: 'Backend Connection', subtitle: 'Connect to Shadow Agent server' },
  { title: 'Choose Provider', subtitle: 'Select your LLM provider' },
  { title: 'API Key', subtitle: 'Connect your account' },
  { title: 'Voice & Avatar', subtitle: 'Customize your experience' },
  { title: 'Ready!', subtitle: 'Start your journey' },
];

export function OnboardingWizard() {
  const {
    step,
    selectedProvider,
    apiKey,
    showApiKey,
    connectionStatus,
    connectionError,
    setStep,
    nextStep,
    prevStep,
    setSelectedProvider,
    setApiKey,
    toggleShowApiKey,
    setConnectionStatus,
    setConnectionError,
    completeOnboarding,
  } = useOnboardingStore();

  const { setShowOnboarding, setVoice, voice, setAvatar, avatar, setPersonality, personality, setDesktopPet, desktopPet, backendConfig, setBackendConfig, setApiKey: setApiKeyStore, updateHealth } = useSettingsStore();
  const { setCurrentModel, models, setModels, setBackendConnected, setAuthenticated } = useAgentStore();

  // Backend connection state
  const [backendStatus, setBackendStatus] = useState<'idle' | 'testing' | 'success' | 'error' | 'skipped'>('idle');
  const [authPassword, setAuthPassword] = useState('');

  const confetti = useMemo(() => {
    if (step !== 5) return [];
    return Array.from({ length: 30 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      color: ['#7c3aed', '#a78bfa', '#22c55e', '#f59e0b', '#ef4444', '#3b82f6'][Math.floor(Math.random() * 6)],
      delay: Math.random() * 2,
    }));
  }, [step]);

  const canProceed = () => {
    switch (step) {
      case 0: return true;
      case 1: return backendStatus === 'success' || backendStatus === 'skipped';
      case 2: return !!selectedProvider;
      case 3: return selectedProvider === 'ollama' || apiKey.length >= 10;
      case 4: return true;
      case 5: return true;
      default: return false;
    }
  };

  // Test backend connection (with 10s timeout)
  const handleTestBackend = async () => {
    setBackendStatus('testing');

    const timeoutPromise = new Promise<false>((resolve) =>
      setTimeout(() => resolve(false), 10000)
    );

    const healthPromise = checkBackendHealth().then((result) => result || false);

    const isHealthy = await Promise.race([healthPromise, timeoutPromise]);

    if (isHealthy) {
      setBackendStatus('success');
      setBackendConnected('connected');

      try {
        // Try to authenticate
        const authResult = await loginToBackend(authPassword || undefined);
        if (authResult.success) {
          setAuthenticated(true);
        }

        // Load models
        const modelsData = await getModels();
        setModels(modelsData);

        // Update health
        updateHealth({ lastCheck: Date.now() });
      } catch (err) {
        setBackendStatus('error');
      }
    } else {
      setBackendStatus('error');
      setBackendConnected('disconnected');
    }
  };

  const handleTestConnection = useCallback(async () => {
    if (!selectedProvider) return;
    setConnectionStatus('testing');
    setConnectionError(null);

    try {
      const result = await testConnection(selectedProvider, apiKey);
      if (result.success) {
        setConnectionStatus('success');
        if (apiKey) {
          setApiKeyStore(selectedProvider, apiKey);
        }
      } else {
        setConnectionStatus('error');
        setConnectionError(result.error || 'Connection failed');
      }
    } catch {
      setConnectionStatus('error');
      setConnectionError('Network error. Please check your connection.');
    }
  }, [selectedProvider, apiKey, setConnectionStatus, setConnectionError, setApiKeyStore]);

  const handleFinish = () => {
    completeOnboarding();
    setShowOnboarding(false);

    // Set the matching model
    const matchingModel = models.find((m) =>
      m.provider.toLowerCase() === selectedProvider?.toLowerCase()
    );
    if (matchingModel) {
      setCurrentModel(matchingModel);
    }
  };

  // Auto-test connection on step 3 (API Key step) — only once when step changes
  useEffect(() => {
    if (step === 3 && connectionStatus === 'idle' && selectedProvider && apiKey && apiKey.length >= 10 && selectedProvider !== 'ollama') {
      handleTestConnection();
    }
    // Only re-run when step changes, not on every apiKey keystroke
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-[oklch(0.06_0.02_280)] backdrop-blur-xl"
    >
      {/* Confetti */}
      <AnimatePresence>
        {confetti.length > 0 && (
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            {confetti.map((piece) => (
              <motion.div
                key={piece.id}
                className="absolute w-2 h-2 rounded-sm"
                style={{
                  left: `${piece.x}%`,
                  backgroundColor: piece.color,
                }}
                initial={{ y: -20, opacity: 1, rotate: 0 }}
                animate={{ y: '110vh', opacity: 0, rotate: 720 }}
                transition={{
                  duration: 3,
                  delay: piece.delay,
                  ease: 'easeIn',
                }}
              />
            ))}
          </div>
        )}
      </AnimatePresence>

      <div className="w-full max-w-lg mx-4">
        {/* Progress Bar */}
        <div className="flex items-center gap-1 mb-8">
          {STEPS.map((_, i) => (
            <motion.div
              key={i}
              className="flex-1 h-1 rounded-full"
              animate={{
                backgroundColor: i <= step ? '#7c3aed' : 'oklch(1 0 0 / 6%)',
              }}
              transition={{ duration: 0.3 }}
            />
          ))}
        </div>

        {/* Step Content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
            className="bg-[oklch(0.1_0.015_280)] border border-white/[0.06] rounded-2xl p-8 max-h-[70vh] overflow-y-auto"
          >
            {/* Step 0: Welcome */}
            {step === 0 && (
              <div className="text-center">
                <motion.div
                  className="w-20 h-20 rounded-2xl bg-gradient-to-br from-purple-500/30 to-violet-600/30 border border-purple-500/20 flex items-center justify-center mx-auto mb-6"
                  animate={{
                    boxShadow: [
                      '0 0 30px oklch(0.627 0.265 293 / 20%)',
                      '0 0 60px oklch(0.627 0.265 293 / 30%)',
                      '0 0 30px oklch(0.627 0.265 293 / 20%)',
                    ],
                  }}
                  transition={{ duration: 3, repeat: Infinity }}
                >
                  <Sparkles className="h-10 w-10 text-purple-400" />
                </motion.div>
                <h2 className="text-2xl font-bold text-white/90 mb-2">
                  Welcome to Shadow Agent
                </h2>
                <p className="text-sm text-white/40 leading-relaxed max-w-sm mx-auto">
                  Your self-evolving AI companion that learns, adapts, and grows with every interaction. Let&apos;s get you set up.
                </p>
              </div>
            )}

            {/* Step 1: Backend Connection */}
            {step === 1 && (
              <div>
                <h2 className="text-xl font-bold text-white/90 mb-1">Backend Connection</h2>
                <p className="text-sm text-white/40 mb-6">Connect to the Shadow Agent FastAPI server</p>

                <div className="space-y-4">
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

                  <div>
                    <Label className="text-xs text-white/50 mb-1.5 block">Auth Password (optional)</Label>
                    <Input
                      type="password"
                      value={authPassword}
                      onChange={(e) => setAuthPassword(e.target.value)}
                      placeholder="Leave empty if no auth required"
                      className="bg-white/[0.03] border-white/[0.06] text-white/70 text-xs"
                    />
                  </div>

                  <div className="flex items-center gap-3">
                    <Button
                      onClick={handleTestBackend}
                      disabled={backendStatus === 'testing'}
                      className="bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 border border-purple-500/20"
                    >
                      {backendStatus === 'testing' ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : backendStatus === 'success' ? (
                        <CheckCircle2 className="h-4 w-4 mr-2 text-green-400" />
                      ) : backendStatus === 'error' ? (
                        <XCircle className="h-4 w-4 mr-2 text-red-400" />
                      ) : (
                        <Wifi className="h-4 w-4 mr-2" />
                      )}
                      Test Connection
                    </Button>
                    {backendStatus !== 'success' && (
                      <Button
                        onClick={() => setBackendStatus('skipped')}
                        variant="ghost"
                        className="text-white/30 hover:text-white/60 hover:bg-white/[0.03] text-xs"
                      >
                        Skip
                      </Button>
                    )}
                    {backendStatus === 'success' && (
                      <span className="text-sm text-green-400 flex items-center gap-1">
                        <Wifi className="h-3.5 w-3.5" /> Connected!
                      </span>
                    )}
                    {backendStatus === 'error' && (
                      <span className="text-sm text-red-400 flex items-center gap-1">
                        <WifiOff className="h-3.5 w-3.5" /> Cannot reach server
                      </span>
                    )}
                  </div>

                  {backendStatus === 'error' && (
                    <div className="p-3 rounded-xl bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-xs">
                      <p className="font-medium mb-1">Backend not found</p>
                      <p className="text-yellow-300/60">Make sure the Shadow Agent server is running on port {backendConfig.port}. You can continue setup without it — the app will work in offline mode.</p>
                      <button
                        onClick={() => setBackendStatus('skipped')}
                        className="mt-2 text-purple-400 hover:text-purple-300 underline underline-offset-2 transition-colors"
                      >
                        Skip this step
                      </button>
                    </div>
                  )}

                  {backendStatus === 'skipped' && (
                    <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-300 text-xs">
                      <p>Backend connection skipped. The app will run in offline mode. You can connect later in Settings.</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Step 2: Provider Selection */}
            {step === 2 && (
              <div>
                <h2 className="text-xl font-bold text-white/90 mb-1">Choose Your Provider</h2>
                <p className="text-sm text-white/40 mb-6">Select the LLM provider you&apos;d like to use</p>
                <div className="space-y-2">
                  {[
                    ...ONBOARDING_PROVIDERS,
                    { id: 'groq', name: 'Groq', description: 'Fast inference, Llama & Mixtral', icon: '⚡', apiKeyUrl: 'https://console.groq.com/keys' },
                    { id: 'deepinfra', name: 'DeepInfra', description: 'Serverless LLM inference', icon: '🔥', apiKeyUrl: 'https://deepinfra.com/dash/api_keys' },
                    { id: 'openrouter', name: 'OpenRouter', description: 'Unified API for many models', icon: '🌐', apiKeyUrl: 'https://openrouter.ai/keys' },
                  ].filter((p, i, arr) => arr.findIndex(x => x.id === p.id) === i).map((provider, i) => (
                    <motion.button
                      key={provider.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.06 }}
                      onClick={() => setSelectedProvider(provider.id)}
                      className={cn(
                        'w-full flex items-center gap-3 p-3 rounded-xl border transition-all text-left',
                        selectedProvider === provider.id
                          ? 'border-purple-500/30 bg-purple-500/10'
                          : 'border-white/[0.04] bg-white/[0.02] hover:bg-white/[0.04]'
                      )}
                      whileHover={{ x: 3 }}
                      whileTap={{ scale: 0.99 }}
                    >
                      <span className="text-2xl">{provider.icon}</span>
                      <div className="flex-1">
                        <p className={cn(
                          'text-sm font-medium',
                          selectedProvider === provider.id ? 'text-purple-300' : 'text-white/60'
                        )}>
                          {provider.name}
                        </p>
                        <p className="text-[10px] text-white/30">{provider.description}</p>
                      </div>
                      <div className={cn(
                        'w-5 h-5 rounded-full border-2 flex items-center justify-center',
                        selectedProvider === provider.id
                          ? 'border-purple-400 bg-purple-400/20'
                          : 'border-white/10'
                      )}>
                        {selectedProvider === provider.id && (
                          <div className="w-2 h-2 rounded-full bg-purple-400" />
                        )}
                      </div>
                    </motion.button>
                  ))}
                </div>
              </div>
            )}

            {/* Step 3: API Key */}
            {step === 3 && (
              <div>
                <h2 className="text-xl font-bold text-white/90 mb-1">Enter Your API Key</h2>
                <p className="text-sm text-white/40 mb-6">
                  {selectedProvider === 'ollama' || selectedProvider === 'pollinations'
                    ? 'No API key needed for this provider!'
                    : `Enter your ${[...ONBOARDING_PROVIDERS, { id: 'groq', name: 'Groq' }, { id: 'deepinfra', name: 'DeepInfra' }, { id: 'openrouter', name: 'OpenRouter' }].find(p => p.id === selectedProvider)?.name || selectedProvider} API key`}
                </p>

                {selectedProvider === 'ollama' || selectedProvider === 'pollinations' ? (
                  <div className="p-4 rounded-xl bg-green-500/10 border border-green-500/20 text-green-300 text-sm text-center">
                    ✅ No API key required
                  </div>
                ) : (
                  <>
                    <div className="relative mb-3">
                      <Input
                        type={showApiKey ? 'text' : 'password'}
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder="sk-..."
                        className="bg-white/[0.03] border-white/[0.06] text-white/70 pr-10 font-mono text-sm"
                      />
                      <button
                        onClick={toggleShowApiKey}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
                      >
                        {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    {selectedProvider && (
                      <a
                        href={[...ONBOARDING_PROVIDERS, { id: 'groq', name: 'Groq', apiKeyUrl: 'https://console.groq.com/keys' }, { id: 'deepinfra', name: 'DeepInfra', apiKeyUrl: 'https://deepinfra.com/dash/api_keys' }, { id: 'openrouter', name: 'OpenRouter', apiKeyUrl: 'https://openrouter.ai/keys' }].find(p => p.id === selectedProvider)?.apiKeyUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300 transition-colors"
                      >
                        <ExternalLink className="h-3 w-3" />
                        Get an API key
                      </a>
                    )}
                  </>
                )}
              </div>
            )}

            {/* Step 4: Voice & Avatar Setup */}
            {step === 4 && (
              <div className="space-y-4">
                <h2 className="text-xl font-bold text-white/90 mb-1">Voice & Avatar</h2>
                <p className="text-sm text-white/40 mb-4">Customize your AI experience (optional)</p>

                {/* STT */}
                <div>
                  <Label className="text-xs text-white/50 mb-1.5 block flex items-center gap-1">
                    <Mic className="h-3 w-3" /> Speech-to-Text
                  </Label>
                  <select
                    value={voice.sttProvider}
                    onChange={(e) => setVoice({ sttProvider: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-white/70 text-xs appearance-none cursor-pointer focus:border-purple-500/30 focus:outline-none"
                  >
                    <option value="" className="bg-[oklch(0.12_0.015_280)]">Disabled</option>
                    {STT_PROVIDERS.map((p) => (
                      <option key={p.id} value={p.id} className="bg-[oklch(0.12_0.015_280)]">
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* TTS */}
                <div>
                  <Label className="text-xs text-white/50 mb-1.5 block flex items-center gap-1">
                    <Volume2 className="h-3 w-3" /> Text-to-Speech
                  </Label>
                  <select
                    value={voice.ttsProvider}
                    onChange={(e) => setVoice({ ttsProvider: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.06] text-white/70 text-xs appearance-none cursor-pointer focus:border-purple-500/30 focus:outline-none"
                  >
                    <option value="" className="bg-[oklch(0.12_0.015_280)]">Disabled</option>
                    {TTS_PROVIDERS.map((p) => (
                      <option key={p.id} value={p.id} className="bg-[oklch(0.12_0.015_280)]">
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Avatar */}
                <div className="flex items-center justify-between">
                  <Label className="text-xs text-white/50 flex items-center gap-1">
                    🎭 Enable VRM Avatar
                  </Label>
                  <Switch
                    checked={avatar.enabled}
                    onCheckedChange={(checked) => setAvatar({ enabled: checked })}
                  />
                </div>

                {/* Personality */}
                <div>
                  <Label className="text-xs text-white/50 mb-1.5 block">Personality</Label>
                  <div className="grid grid-cols-4 gap-2">
                    {PERSONALITIES.slice(0, 4).map((p) => (
                      <motion.button
                        key={p.id}
                        onClick={() => setPersonality(p.id)}
                        className={cn(
                          'flex flex-col items-center gap-1 p-2 rounded-xl border transition-all',
                          personality === p.id
                            ? `bg-gradient-to-br ${p.color} ${p.border}`
                            : 'bg-white/[0.02] border-white/[0.04] hover:bg-white/[0.04]'
                        )}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                      >
                        <span className="text-lg">{p.emoji}</span>
                        <span className="text-[9px] text-white/40">{p.name}</span>
                      </motion.button>
                    ))}
                  </div>
                </div>

                {/* Desktop Pet */}
                <div className="flex items-center justify-between">
                  <Label className="text-xs text-white/50 flex items-center gap-1">
                    <Cat className="h-3 w-3" /> Desktop Pet
                  </Label>
                  <Switch
                    checked={desktopPet.enabled}
                    onCheckedChange={(checked) => setDesktopPet({ enabled: checked })}
                  />
                </div>
                {desktopPet.enabled && (
                  <div className="grid grid-cols-7 gap-1">
                    {PET_SKINS.map((skin) => (
                      <motion.button
                        key={skin.id}
                        onClick={() => setDesktopPet({ skin: skin.id })}
                        className={cn(
                          'flex flex-col items-center gap-0.5 p-1.5 rounded-lg border transition-all',
                          desktopPet.skin === skin.id
                            ? 'bg-purple-500/20 border-purple-500/20'
                            : 'bg-white/[0.02] border-white/[0.04]'
                        )}
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                      >
                        <span className="text-sm">{skin.emoji}</span>
                        <span className="text-[7px] text-white/30">{skin.name}</span>
                      </motion.button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Step 5: Ready */}
            {step === 5 && (
              <div className="text-center">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: 'spring', stiffness: 200, delay: 0.2 }}
                  className="text-5xl mb-4"
                >
                  🚀
                </motion.div>
                <h2 className="text-2xl font-bold text-white/90 mb-2">
                  You&apos;re All Set!
                </h2>
                <p className="text-sm text-white/40 leading-relaxed max-w-sm mx-auto mb-6">
                  Shadow Agent is ready to assist you. Start a conversation, and watch as it learns and evolves with every interaction.
                </p>

                {/* Summary */}
                <div className="text-left space-y-2 mb-6 p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                  <p className="text-xs text-white/40 font-medium mb-2">Setup Summary:</p>
                  <div className="flex items-center gap-2 text-xs text-white/50">
                    <Globe className="h-3 w-3" />
                    <span>Backend: {backendStatus === 'success' ? 'Connected' : 'Offline mode'}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-white/50">
                    <Sparkles className="h-3 w-3" />
                    <span>Provider: {selectedProvider || 'Not selected'}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-white/50">
                    <Mic className="h-3 w-3" />
                    <span>STT: {voice.sttProvider || 'Disabled'}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-white/50">
                    <Volume2 className="h-3 w-3" />
                    <span>TTS: {voice.ttsProvider || 'Disabled'}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-white/50">
                    🎭 <span>Avatar: {avatar.enabled ? 'Enabled' : 'Disabled'}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-white/50">
                    💖 <span>Personality: {PERSONALITIES.find(p => p.id === personality)?.name || 'Assistant'}</span>
                  </div>
                </div>

                <Button
                  onClick={handleFinish}
                  size="lg"
                  className="bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 border border-purple-500/20"
                >
                  <Sparkles className="h-4 w-4 mr-2" />
                  Start Chatting
                </Button>
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        {/* Navigation Buttons */}
        <div className="flex items-center justify-between mt-6">
          <AnimatePresence>
            {step > 0 && (
              <motion.button
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                onClick={prevStep}
                className="flex items-center gap-1 text-xs text-white/30 hover:text-white/60 transition-colors"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                Back
              </motion.button>
            )}
          </AnimatePresence>

          <div className="ml-auto">
            {step < 5 && step !== 3 && (
              <motion.button
                onClick={nextStep}
                disabled={!canProceed()}
                className={cn(
                  'flex items-center gap-1 px-4 py-2 rounded-lg text-xs font-medium transition-all',
                  canProceed()
                    ? 'bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 border border-purple-500/20'
                    : 'bg-white/[0.03] text-white/20 cursor-not-allowed'
                )}
                whileHover={canProceed() ? { scale: 1.05 } : {}}
                whileTap={canProceed() ? { scale: 0.95 } : {}}
              >
                {step === 3 && (selectedProvider === 'ollama' || selectedProvider === 'pollinations') ? 'Skip' : 'Next'}
                <ChevronRight className="h-3.5 w-3.5" />
              </motion.button>
            )}
            {step === 3 && (selectedProvider !== 'ollama' && selectedProvider !== 'pollinations') && (
              <motion.button
                onClick={nextStep}
                disabled={!canProceed()}
                className={cn(
                  'flex items-center gap-1 px-4 py-2 rounded-lg text-xs font-medium transition-all',
                  canProceed()
                    ? 'bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 border border-purple-500/20'
                    : 'bg-white/[0.03] text-white/20 cursor-not-allowed'
                )}
                whileHover={canProceed() ? { scale: 1.05 } : {}}
                whileTap={canProceed() ? { scale: 0.95 } : {}}
              >
                Next
                <ChevronRight className="h-3.5 w-3.5" />
              </motion.button>
            )}
          </div>
        </div>

        {/* Step Counter */}
        <p className="text-center text-[10px] text-white/15 mt-4">
          Step {step + 1} of {STEPS.length}
        </p>
      </div>
    </motion.div>
  );
}
