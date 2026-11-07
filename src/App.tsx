import React, { useState, useEffect, useRef } from 'react';
import { ArcReactorButton } from './components/ArcReactorButton';
import { WebcamSimulator } from './components/WebcamSimulator';
import { VirtualPcScreen } from './components/VirtualPcScreen';
import { AirKeyboardSimulator } from './components/AirKeyboardSimulator';
import { CodeStudio } from './components/CodeStudio';
import { SetupGuide } from './components/SetupGuide';
import { SettingsStudio } from './components/SettingsStudio';
import { 
  FolderArchive, 
  Terminal, 
  Sliders, 
  Monitor, 
  Sparkles, 
  Hand, 
  ShieldCheck, 
  CheckCircle2, 
  MousePointer, 
  Download,
  Keyboard as KeyboardIcon
} from 'lucide-react';
import JSZip from 'jszip';
import { POINTER_V_FILES } from './data/codeFiles';

export default function App() {
  const [activeTab, setActiveTab] = useState<'chamber' | 'keyboard' | 'code' | 'settings' | 'guide'>('chamber');
  const [isModeActive, setIsModeActive] = useState<boolean>(true);
  const [brushLocked, setBrushLocked] = useState<boolean>(false);
  const [currentGesture, setCurrentGesture] = useState<string>('POINTING');
  const [lastAction, setLastAction] = useState<string>('NONE');
  const [dwellProgress, setDwellProgress] = useState<number>(0);

  // Air Keyboard Settings state
  const [symbolsEnabled, setSymbolsEnabled] = useState<boolean>(true);
  const [dimInactiveZone, setDimInactiveZone] = useState<boolean>(true);
  const [thumbSpace, setThumbSpace] = useState<boolean>(true);
  const [swipeSensitivity, setSwipeSensitivity] = useState<number>(1.0);

  // Active region (~70% of webcam frame mapped to screen)
  const [activeRegion, setActiveRegion] = useState({
    xMin: 0.15,
    yMin: 0.15,
    xMax: 0.85,
    yMax: 0.85,
  });

  // Settings
  const [sensitivity, setSensitivity] = useState(1.0);
  const [minCutoff, setMinCutoff] = useState(1.0);
  const [beta, setBeta] = useState(0.007);
  const [doubleTapWindow, setDoubleTapWindow] = useState(500);
  const [dwellTime, setDwellTime] = useState(0.60);
  const [singleClickEnabled, setSingleClickEnabled] = useState(true);

  // Finger position in normalized webcam space (0..1)
  const [fingerPos, setFingerPos] = useState({ x: 0.5, y: 0.45 });

  // Mapped cursor position on the virtual screen (0..100%)
  const [virtualCursor, setVirtualCursor] = useState({ x: 50, y: 45 });

  // Dwell timer ref
  const dwellTimerRef = useRef<number | null>(null);
  const dwellStartRef = useRef<number | null>(null);

  // Map finger position inside active region to virtual desktop coordinates
  useEffect(() => {
    const { xMin, yMin, xMax, yMax } = activeRegion;
    const clampedX = Math.max(xMin, Math.min(xMax, fingerPos.x));
    const clampedY = Math.max(yMin, Math.min(yMax, fingerPos.y));

    const spanX = Math.max(0.01, xMax - xMin);
    const spanY = Math.max(0.01, yMax - yMin);

    const normX = (clampedX - xMin) / spanX;
    const normY = (clampedY - yMin) / spanY;

    // Apply sensitivity
    const targetX = Math.max(2, Math.min(98, normX * 100));
    const targetY = Math.max(2, Math.min(98, normY * 100));

    setVirtualCursor({ x: targetX, y: targetY });

    // Handle Dwell Brush Lock when finger rests in a small area
    if (isModeActive && !brushLocked) {
      if (dwellStartRef.current === null) {
        dwellStartRef.current = Date.now();
      }

      const elapsed = (Date.now() - dwellStartRef.current) / 1000;
      const progress = Math.min(1, elapsed / dwellTime);
      setDwellProgress(progress);

      if (elapsed >= dwellTime) {
        setBrushLocked(true);
        setDwellProgress(0);
        dwellStartRef.current = null;
        setLastAction('BRUSH_LOCK_TOGGLE');
      }
    } else {
      setDwellProgress(0);
      dwellStartRef.current = null;
    }
  }, [fingerPos, activeRegion, isModeActive, brushLocked, dwellTime]);

  const handleFingerMove = (pos: { x: number; y: number }) => {
    setFingerPos(pos);
    dwellStartRef.current = Date.now();
  };

  // Simulate an air tap
  const handleAirTap = () => {
    setLastAction('DOUBLE_CLICK');
    setCurrentGesture('AIR DOUBLE-TAP');
    setTimeout(() => {
      setLastAction('NONE');
      setCurrentGesture('POINTING');
    }, 500);
  };

  const handleToggleBrushLock = () => {
    setBrushLocked(!brushLocked);
    setLastAction(brushLocked ? 'BRUSH_UNLOCK' : 'BRUSH_LOCK_TOGGLE');
  };

  // Direct Zip Downloader in Header
  const handleDownloadAllZip = async () => {
    const zip = new JSZip();
    const folder = zip.folder("pointer_v");
    if (folder) {
      POINTER_V_FILES.forEach((f) => {
        folder.file(f.name, f.content);
      });
    }
    const content = await zip.generateAsync({ type: "blob" });
    const url = URL.createObjectURL(content);
    const link = document.createElement("a");
    link.href = url;
    link.download = "PointerV-Source.zip";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-[#0B0E13] text-slate-100 flex flex-col antialiased selection:bg-blue-600/30 selection:text-blue-200">
      {/* 1. Universal Top Bar Contract: Brand Zone — Nav Links — Action Button */}
      <header className="flex items-center justify-between gap-8 px-6 py-3.5 border-b border-[#232A36] bg-[#11151C]/90 backdrop-blur-md sticky top-0 z-50">
        {/* Brand Zone */}
        <div className="flex items-center gap-2.5 whitespace-nowrap shrink-0">
          <div className="w-6 h-6 rounded-md border border-[#2F7BFF] bg-[#171C25] flex items-center justify-center font-bold text-xs text-[#2F7BFF]">
            PV
          </div>
          <span className="text-base font-bold tracking-wider text-white">
            POINTER V
          </span>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center gap-6 text-xs font-semibold text-slate-400">
          <button
            onClick={() => setActiveTab('chamber')}
            className={`whitespace-nowrap transition-colors cursor-pointer ${
              activeTab === 'chamber' ? 'text-[#2F7BFF] border-b-2 border-[#2F7BFF] pb-1 -mb-1' : 'hover:text-slate-200'
            }`}
          >
            Live Chamber & PC Sandbox
          </button>
          <button
            onClick={() => setActiveTab('keyboard')}
            className={`whitespace-nowrap transition-colors cursor-pointer flex items-center gap-1.5 ${
              activeTab === 'keyboard' ? 'text-[#2F7BFF] border-b-2 border-[#2F7BFF] pb-1 -mb-1' : 'hover:text-slate-200'
            }`}
          >
            <span>Air Keyboard Simulator</span>
            <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-indigo-950 text-indigo-300 border border-indigo-800">
              NEW
            </span>
          </button>
          <button
            onClick={() => setActiveTab('code')}
            className={`whitespace-nowrap transition-colors cursor-pointer ${
              activeTab === 'code' ? 'text-[#2F7BFF] border-b-2 border-[#2F7BFF] pb-1 -mb-1' : 'hover:text-slate-200'
            }`}
          >
            Python Source Explorer
          </button>
          <button
            onClick={() => setActiveTab('settings')}
            className={`whitespace-nowrap transition-colors cursor-pointer ${
              activeTab === 'settings' ? 'text-[#2F7BFF] border-b-2 border-[#2F7BFF] pb-1 -mb-1' : 'hover:text-slate-200'
            }`}
          >
            One Euro & Calibration
          </button>
          <button
            onClick={() => setActiveTab('guide')}
            className={`whitespace-nowrap transition-colors cursor-pointer ${
              activeTab === 'guide' ? 'text-[#2F7BFF] border-b-2 border-[#2F7BFF] pb-1 -mb-1' : 'hover:text-slate-200'
            }`}
          >
            Windows Setup & .EXE Build
          </button>
        </nav>

        {/* Primary Action Button */}
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={handleDownloadAllZip}
            className="flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold text-white bg-[#2F7BFF] hover:bg-[#5BA0FF] rounded-md shadow-[0_0_12px_rgba(47,123,255,0.4)] transition-all whitespace-nowrap cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download .ZIP</span>
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 flex flex-col gap-6">
        {/* Master Header & Power Node */}
        <section className="flex flex-col md:flex-row items-center justify-between gap-6 p-6 rounded-lg bg-[#11151C] border border-[#232A36] shadow-xl">
          <div className="flex-1">
            <div className="flex items-center gap-2 text-xs font-mono text-[#2F7BFF] mb-1">
              <span>PER-MONITOR DPI V2</span>
              <span aria-hidden="true">·</span>
              <span>WIN32 HARDWARE SENDINPUT</span>
              <span aria-hidden="true">·</span>
              <span>GLOBAL HOTKEY CTRL+ALT+T</span>
            </div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-white">
              CONTROL YOUR PC IN THE AIR WITH ONE HAND
            </h1>
            <p className="text-xs md:text-sm text-slate-400 mt-2 max-w-2xl leading-relaxed">
              Real-time MediaPipe Tasks HandLandmarker tracking at 60 FPS. Perform air double-taps to launch files, dwell or pinch to lock brush in Photoshop and Paint, and navigate multi-monitor setups without arm fatigue.
            </p>

            {/* Status Metadata Strip */}
            <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-slate-400 mt-4 pt-4 border-t border-[#232A36]">
              <div>
                STATUS: <span className={isModeActive ? 'text-emerald-400 font-bold' : 'text-slate-500'}>{isModeActive ? 'RUNNING' : 'PAUSED'}</span>
              </div>
              <span aria-hidden="true">·</span>
              <div>
                LATENCY: <span className="text-[#2F7BFF] tabular-nums">7.8 ms</span>
              </div>
              <span aria-hidden="true">·</span>
              <div>
                INFERENCE: <span className="text-[#2F7BFF] tabular-nums">60.0 FPS</span>
              </div>
              <span aria-hidden="true">·</span>
              <div>
                BRUSH LOCK: <span className={brushLocked ? 'text-rose-400 font-bold' : 'text-slate-400'}>{brushLocked ? 'MOUSE DOWN' : 'OFF'}</span>
              </div>
            </div>
          </div>

          {/* Master Engaging Toggle */}
          <div className="flex flex-col items-center gap-2 shrink-0">
            <ArcReactorButton
              isActive={isModeActive}
              onToggle={() => setIsModeActive(!isModeActive)}
            />
            <span className="text-[11px] font-mono text-slate-400">
              {isModeActive ? 'POINTER V: ON' : 'POINTER V: PAUSED'}
            </span>
          </div>
        </section>

        {/* Tab 1: Live Chamber & PC Sandbox */}
        {activeTab === 'chamber' && (
          <div className="flex flex-col gap-6">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left Column: Webcam HUD Simulator (5 cols) */}
              <div className="lg:col-span-5 flex flex-col gap-4">
                <WebcamSimulator
                  activeRegion={activeRegion}
                  onActiveRegionChange={setActiveRegion}
                  isModeActive={isModeActive}
                  brushLocked={brushLocked}
                  dwellProgress={dwellProgress}
                  currentGesture={currentGesture}
                  fingerPos={fingerPos}
                  onFingerMove={handleFingerMove}
                  onAirTap={handleAirTap}
                />

                {/* Gesture Quick Reference Card */}
                <div className="p-4 rounded-lg bg-[#11151C] border border-[#232A36] text-xs">
                  <div className="font-semibold text-[#2F7BFF] tracking-wide mb-2">
                    AIR GESTURE HOTKEYS & CONTROLS
                  </div>
                  <ul className="space-y-1.5 font-mono text-[11px] text-slate-300">
                    <li className="flex justify-between">
                      <span className="text-slate-400">Air Double-Tap:</span>
                      <span className="text-cyan-300">Double Left Click (Open files/apps)</span>
                    </li>
                    <li className="flex justify-between">
                      <span className="text-slate-400">Hold 0.6s (Dwell) / Pinch:</span>
                      <span className="text-amber-300">Lock Brush Down (Continuous Paint)</span>
                    </li>
                    <li className="flex justify-between">
                      <span className="text-slate-400">Open Palm:</span>
                      <span className="text-emerald-300">Rest / Pause Cursor</span>
                    </li>
                    <li className="flex justify-between">
                      <span className="text-slate-400">Two-Finger Hold (0.5s):</span>
                      <span className="text-indigo-300">Right Click (Context Menu)</span>
                    </li>
                    <li className="flex justify-between">
                      <span className="text-slate-400">Two-Finger Move Y:</span>
                      <span className="text-slate-300">Smooth Page Scroll</span>
                    </li>
                  </ul>
                </div>
              </div>

              {/* Right Column: Virtual PC Screen (7 cols) */}
              <div className="lg:col-span-7 flex flex-col gap-4">
                <VirtualPcScreen
                  cursorPos={virtualCursor}
                  brushLocked={brushLocked}
                  onToggleBrushLock={handleToggleBrushLock}
                  lastAction={lastAction}
                  isModeActive={isModeActive}
                  dwellProgress={dwellProgress}
                />
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Floating Air Keyboard Simulator */}
        {activeTab === 'keyboard' && (
          <AirKeyboardSimulator />
        )}

        {/* Tab 3: Python Source Code Explorer */}
        {activeTab === 'code' && (
          <CodeStudio />
        )}

        {/* Tab 4: Configuration & One Euro Calibration */}
        {activeTab === 'settings' && (
          <SettingsStudio
            activeRegion={activeRegion}
            onActiveRegionChange={setActiveRegion}
            sensitivity={sensitivity}
            onSensitivityChange={setSensitivity}
            minCutoff={minCutoff}
            onMinCutoffChange={setMinCutoff}
            beta={beta}
            onBetaChange={setBeta}
            doubleTapWindow={doubleTapWindow}
            onDoubleTapWindowChange={setDoubleTapWindow}
            dwellTime={dwellTime}
            onDwellTimeChange={setDwellTime}
            singleClickEnabled={singleClickEnabled}
            onToggleSingleClick={setSingleClickEnabled}
            symbolsEnabled={symbolsEnabled}
            onToggleSymbolsEnabled={setSymbolsEnabled}
            dimInactiveZone={dimInactiveZone}
            onToggleDimInactiveZone={setDimInactiveZone}
            thumbSpace={thumbSpace}
            onToggleThumbSpace={setThumbSpace}
            swipeSensitivity={swipeSensitivity}
            onSwipeSensitivityChange={setSwipeSensitivity}
          />
        )}

        {/* Tab 5: Windows Setup Guide & EXE Builder */}
        {activeTab === 'guide' && (
          <SetupGuide />
        )}
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-[#232A36] bg-[#11151C] py-4 px-6 text-center text-xs font-mono text-slate-500">
        POINTER V · CONTROL YOUR PC IN THE AIR WITH ONE HAND · PYTHON 3.12 · MEDIAPIPE · WIN32 SENDINPUT
      </footer>
    </div>
  );
}
