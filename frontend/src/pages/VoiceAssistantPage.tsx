import React, { useState, useEffect, useRef } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Mic, MicOff, Send, Volume2, Globe, Bot, User, Sparkles } from 'lucide-react';
import { useToast } from '../context/ToastContext';
import { useAuth } from '../context/AuthContext';

interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  intent?: string;
  confidence?: number;
  entities?: Record<string, any>;
  timestamp: string;
}

export const VoiceAssistantPage: React.FC = () => {
  const { language, setLanguage } = useAuth();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      text:
        language === 'bn-IN'
          ? 'নমস্কার! গ্রামসেতু এআই ভয়েস সহায়ক-এ আপনাকে স্বাগতম। আপনি কি বাজার দর জানতে চান নাকি গাড়ি বুক করতে চান?'
          : language === 'hi-IN'
          ? 'नमस्ते! ग्रामसेतु वॉइस असिस्टेंट में आपका स्वागत है। क्या आप मंडी भाव जानना चाहते हैं या गाड़ी बुक करना चाहते हैं?'
          : 'Welcome to GramSetu Voice Assistant! How can I assist you today? You can ask about mandi prices, book shared transport, or check payments.',
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);
  const [inputText, setInputText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const recognitionRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const toast = useToast();

  useEffect(() => {
    // Scroll to bottom
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    // Setup Web Speech API if supported
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = language;

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setInputText(transcript);
        setIsListening(false);
        handleSend(transcript);
      };

      recognition.onerror = () => {
        setIsListening(false);
        toast.info('Voice input paused', 'You can also type your message.');
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    }
  }, [language]);

  const toggleListening = () => {
    if (!recognitionRef.current) {
      toast.info('Speech Recognition not supported in this browser', 'Please type in the message box below.');
      return;
    }
    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      try {
        recognitionRef.current.lang = language;
        recognitionRef.current.start();
        setIsListening(true);
      } catch (err) {
        console.error('Speech error:', err);
      }
    }
  };

  const speakText = (text: string) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = language;
      window.speechSynthesis.speak(utterance);
    }
  };

  const handleSend = async (textToSend?: string) => {
    const query = textToSend || inputText;
    if (!query.trim()) return;

    const userMsg: Message = {
      id: Math.random().toString(36).substring(2, 9),
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setIsLoading(true);

    try {
      const res = await api.voiceQuery({
        transcription_text: query,
        language: language,
      });

      const replyText =
        res.reply_text ||
        (language === 'bn-IN'
          ? `আপনার অনুরোধ গ্রহণ করা হয়েছে (অভিপ্রায়: ${res.intent})।`
          : language === 'hi-IN'
          ? `आपका अनुरोध प्राप्त हुआ (इरादा: ${res.intent})।`
          : `Request processed (intent: ${res.intent}).`);

      const assistantMsg: Message = {
        id: Math.random().toString(36).substring(2, 9),
        sender: 'assistant',
        text: replyText,
        intent: res.intent,
        confidence: res.confidence,
        entities: res.entities,
        timestamp: new Date().toLocaleTimeString(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
      speakText(replyText);
    } catch (err: any) {
      toast.error('Voice assistant error', 'Could not process query');
    } finally {
      setIsLoading(false);
    }
  };

  // Quick Prompt Chips based on selected language
  const promptChips = {
    'bn-IN': [
      'আজকে আলুর দাম কত?',
      'আমার ৫০০ কেজি টমেটো তোলার আছে, গাড়ি চাই',
      'আমার পেমেন্ট কখন আসবে?',
      'হুগলির কোল্ড স্টোরেজ খালি আছে?',
    ],
    'hi-IN': [
      'आज आलू का भाव क्या है?',
      'मुझे कटाई के लिए गाड़ी बुक करनी है',
      'मेरा पिछला भुगतान कब मिलेगा?',
      'कोल्ड स्टोरेज में जगह है क्या?',
    ],
    'en-IN': [
      'What is the potato price today?',
      'Book shared transport for 500kg potato',
      'Check status of my recent payment',
      'Check storage capacity in Hooghly',
    ],
  }[language] || [];

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900">GramSetu AI Multilingual Voice Assistant</h1>
          <p className="text-xs text-slate-500 mt-1">
            Zero-literacy voice interface for smallholder farmers in Bengali (বাংলা), Hindi (हिन्दी), and English.
          </p>
        </div>

        {/* Language Toggle */}
        <div className="flex items-center space-x-1 bg-white border border-slate-200 p-1 rounded-xl">
          {(['bn-IN', 'hi-IN', 'en-IN'] as const).map((lang) => (
            <button
              key={lang}
              onClick={() => setLanguage(lang)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
                language === lang
                  ? 'bg-emerald-700 text-white shadow-xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {lang === 'bn-IN' ? 'বাংলা' : lang === 'hi-IN' ? 'हिन्दी' : 'English'}
            </button>
          ))}
        </div>
      </div>

      {/* Main Chat Interface */}
      <Card className="h-[520px] flex flex-col p-0 overflow-hidden">
        {/* Messages Scroll Area */}
        <div className="flex-1 p-6 overflow-y-auto space-y-4">
          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex items-start space-x-3 ${
                m.sender === 'user' ? 'flex-row-reverse space-x-reverse' : ''
              }`}
            >
              <div
                className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 ${
                  m.sender === 'user'
                    ? 'bg-slate-800 text-white'
                    : 'bg-emerald-700 text-emerald-100'
                }`}
              >
                {m.sender === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div className="max-w-[75%] space-y-1">
                <div
                  className={`p-4 rounded-2xl text-xs leading-relaxed ${
                    m.sender === 'user'
                      ? 'bg-slate-900 text-white rounded-tr-xs'
                      : 'bg-slate-50 text-slate-900 border border-slate-200/80 rounded-tl-xs'
                  }`}
                >
                  <p>{m.text}</p>
                </div>

                <div className="flex items-center justify-between text-[10px] text-slate-400 px-1">
                  <span>{m.timestamp}</span>
                  {m.intent && (
                    <div className="flex items-center space-x-1">
                      <span className="font-semibold text-emerald-700">Intent: {m.intent}</span>
                      <button
                        onClick={() => speakText(m.text)}
                        className="text-slate-400 hover:text-slate-600 ml-2"
                        title="Listen to audio reply"
                      >
                        <Volume2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Quick Suggestion Chips */}
        <div className="px-6 py-2 bg-slate-50/50 border-t border-slate-100 flex items-center space-x-2 overflow-x-auto">
          <span className="text-[10px] font-bold text-slate-400 uppercase flex-shrink-0">
            Suggested:
          </span>
          {promptChips.map((chip, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(chip)}
              className="text-xs bg-white text-slate-700 px-3 py-1 rounded-full border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50 transition-colors flex-shrink-0"
            >
              {chip}
            </button>
          ))}
        </div>

        {/* Input & Voice Mic Row */}
        <div className="p-4 bg-white border-t border-slate-200/80 flex items-center space-x-3">
          <button
            onClick={toggleListening}
            className={`p-3 rounded-2xl transition-all shadow-sm ${
              isListening
                ? 'bg-rose-600 text-white animate-pulse'
                : 'bg-emerald-700 text-white hover:bg-emerald-800'
            }`}
            title={isListening ? 'Stop listening' : 'Start voice recognition'}
          >
            {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
          </button>

          <input
            type="text"
            placeholder={
              language === 'bn-IN'
                ? 'মাইকে বলুন অথবা বাংলায় লিখুন...'
                : language === 'hi-IN'
                ? 'माइक से बोलें या हिंदी में लिखें...'
                : 'Speak or type your query...'
            }
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            className="flex-1 text-xs p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-500"
          />

          <Button
            size="md"
            onClick={() => handleSend()}
            isLoading={isLoading}
            leftIcon={<Send className="w-4 h-4" />}
          >
            Send
          </Button>
        </div>
      </Card>
    </div>
  );
};
