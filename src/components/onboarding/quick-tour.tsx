'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ChevronRight, ChevronLeft, MessageSquare, Settings, Keyboard, Sparkles, Zap, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useSettingsStore } from '@/stores/settings-store';

const TOUR_STEPS = [
  {
    id: 'welcome',
    title: 'Welcome to Shadow Agent! 🌙',
    description: 'Your personal AI companion that thinks, learns, and evolves with you.',
    icon: Sparkles,
    color: 'from-purple-500 to-pink-500',
    points: [
      'Powered by multiple AI models',
      'Voice interaction support',
      'Persistent memory across sessions',
      'Privacy-focused by design',
    ],
  },
  {
    id: 'chat',
    title: 'Start Chatting',
    description: 'Just type your message and press Enter. Shadow Agent will respond instantly.',
    icon: MessageSquare,
    color: 'from-blue-500 to-cyan-500',
    points: [
      'Attach files by dragging & dropping',
      'Use voice input with the mic button',
      'Stop generation anytime with Escape',
      'Get streaming responses in real-time',
    ],
  },
  {
    id: 'customize',
    title: 'Make it Yours',
    description: 'Customize Shadow Agent to match your style and needs.',
    icon: Settings,
    color: 'from-green-500 to-emerald-500',
    points: [
      'Choose your preferred AI model',
      'Configure voice settings',
      'Set up your personality',
      'Add MCP servers for extra capabilities',
    ],
  },
  {
    id: 'shortcuts',
    title: 'Power User Tips',
    description: 'Master these shortcuts for a seamless experience.',
    icon: Keyboard,
    color: 'from-orange-500 to-amber-500',
    points: [
      'Ctrl + K: Command palette',
      'Ctrl + /: Show shortcuts',
      'Ctrl + N: New conversation',
      'Ctrl + Enter: Send quickly',
    ],
  },
  {
    id: 'done',
    title: "You're All Set! 🎉",
    description: 'Ready to explore? Start by asking Shadow Agent anything!',
    icon: Zap,
    color: 'from-pink-500 to-rose-500',
    points: [
      'Try: "Help me write a Python script"',
      'Try: "Summarize this article"',
      'Try: "Explain quantum computing"',
      'Or just say hello! 👋',
    ],
  },
];

interface QuickTourProps {
  onComplete: () => void;
}

export function QuickTour({ onComplete }: QuickTourProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const { setShowOnboarding } = useSettingsStore();

  const step = TOUR_STEPS[currentStep];
  const isLastStep = currentStep === TOUR_STEPS.length - 1;
  const isFirstStep = currentStep === 0;

  const handleNext = () => {
    if (isLastStep) {
      setShowOnboarding(false);
      onComplete();
    } else {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handlePrevious = () => {
    if (!isFirstStep) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleSkip = () => {
    setShowOnboarding(false);
    onComplete();
  };

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'Enter') {
        handleNext();
      } else if (e.key === 'ArrowLeft') {
        handlePrevious();
      } else if (e.key === 'Escape') {
        handleSkip();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentStep]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    >
      <Card className="w-full max-w-lg mx-4 bg-gradient-to-br from-[#1a1a2e] to-[#16213e] border-white/10">
        <CardContent className="p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className={`p-3 rounded-xl bg-gradient-to-br ${step.color}`}>
                <step.icon className="h-6 w-6 text-white" />
              </div>
              <div>
                <span className="text-white/40 text-xs">Step {currentStep + 1} of {TOUR_STEPS.length}</span>
                <h2 className="text-xl font-bold text-white">{step.title}</h2>
              </div>
            </div>
            <button
              onClick={handleSkip}
              className="p-2 rounded-lg hover:bg-white/5 transition-colors text-white/40 hover:text-white/60"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Progress */}
          <div className="flex gap-2 mb-6">
            {TOUR_STEPS.map((_, i) => (
              <div
                key={i}
                className={`h-1 flex-1 rounded-full transition-colors ${
                  i <= currentStep ? 'bg-gradient-to-r ' + step.color : 'bg-white/10'
                }`}
              />
            ))}
          </div>

          {/* Content */}
          <div className="space-y-4 mb-6">
            <p className="text-white/60">{step.description}</p>
            <ul className="space-y-2">
              {step.points.map((point, i) => (
                <motion.li
                  key={i}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="flex items-center gap-2 text-white/80"
                >
                  <Check className="h-4 w-4 text-green-400 flex-shrink-0" />
                  <span className="text-sm">{point}</span>
                </motion.li>
              ))}
            </ul>
          </div>

          {/* Navigation */}
          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              onClick={handlePrevious}
              disabled={isFirstStep}
              className="text-white/60 hover:text-white hover:bg-white/5"
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Back
            </Button>

            <div className="flex gap-2">
              {!isLastStep && (
                <Button
                  variant="ghost"
                  onClick={handleSkip}
                  className="text-white/40 hover:text-white/60"
                >
                  Skip
                </Button>
              )}
              <Button
                onClick={handleNext}
                className={`bg-gradient-to-r ${step.color} text-white border-0 hover:opacity-90`}
              >
                {isLastStep ? 'Get Started' : 'Next'}
                {!isLastStep && <ChevronRight className="h-4 w-4 ml-1" />}
                {isLastStep && <Sparkles className="h-4 w-4 ml-1" />}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
