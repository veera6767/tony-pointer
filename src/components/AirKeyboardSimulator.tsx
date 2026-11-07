import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Keyboard as KeyboardIcon, 
  Sparkles, 
  Layers, 
  ArrowLeft, 
  ArrowRight, 
  ArrowUp, 
  ArrowDown, 
  CornerDownLeft, 
  Delete, 
  Copy, 
  Check, 
  RotateCcw, 
  Sliders, 
  Hand, 
  Camera, 
  Zap, 
  ShieldCheck, 
  Info,
  ChevronRight,
  ChevronLeft
} from 'lucide-react';

// Exact Main Keyboard Rows definition (10 + 9 + 7 = 26 letters)
const MAIN_ROWS = [
  // Row 1 (14 keys)
  ['Esc', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12', 'Del'],
  // Row 2 (14 keys)
  ['`', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=', 'Backspace'],
  // Row 3 (14 keys)
  ['Tab', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P', '[', ']', '\\'],
  // Row 4 (13 keys)
  ['Caps Lock', 'A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', ';', "'", 'Enter'],
  // Row 5 (12 keys)
  ['Shift', 'Z', 'X', 'C', 'V', 'B', 'N', 'M', ',', '.', '/', 'Shift'],
  // Row 6 (10 keys)
  ['Ctrl', 'Win', 'Alt', 'SPACE', 'Alt', 'Ctrl', '←', '↑', '↓', '→']
];

// Exact Symbols Panel Rows definition (6 rows aligned with main)
const SYMBOL_ROWS = [
  // Row 1: navigation (8 keys)
  ['Home', 'End', 'PgUp', 'PgDn', 'PrtSc', 'Ins', 'Pause', 'ScrLk'],
  // Row 2: shifted number symbols (12 keys)
  ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '_', '+'],
  // Row 3: math/operators (8 keys)
  ['+', '-', '*', '/', '=', '<', '>', '~'],
  // Row 4: brackets/quotes (8 keys)
  ['{', '}', '[', ']', '(', ')', '"', "'"],
  // Row 5: punctuation (8 keys)
  [':', ';', '?', '|', '\\', '/', ',', '.'],
  // Row 6: editing (4 keys)
  ['Backspace', 'Enter', 'Tab', 'Del']
];

// Helper to generate 4-key windows progressive across a row
function buildWindows(rowKeys: string[]): { start: number; keys: string[] }[] {
  const n = rowKeys.length;
  if (n <= 4) {
    return [{ start: 0, keys: rowKeys }];
  }
  const windows: { start: number; keys: string[] }[] = [];
  let s = 0;
  while (s < n) {
    if (s + 4 >= n) {
      windows.push({ start: n - 4, keys: rowKeys.slice(n - 4, n) });
      break;
    }
    windows.push({ start: s, keys: rowKeys.slice(s, s + 4) });
    s += 4;
  }
  return windows;
}

const FINGER_LABELS = ['Index', 'Middle', 'Ring', 'Pinky'];
const FINGER_SHORT = ['IX', 'MD', 'RG', 'PK'];

export const AirKeyboardSimulator: React.FC = () => {
  // Navigation State
  const [currentZone, setCurrentZone] = useState<'MAIN' | 'SYMBOLS'>('MAIN');
  const [currentRow, setCurrentRow] = useState<number>(3); // Default to home row (Caps, A S D F...)
  const [mainWinIdx, setMainWinIdx] = useState<number>(0);
  const [symbolWinIdx, setSymbolWinIdx] = useState<number>(0);

  // Settings
  const [symbolsEnabled, setSymbolsEnabled] = useState<boolean>(true);
  const [dimInactive, setDimInactive] = useState<boolean>(true);
  const [thumbIsSpace, setThumbIsSpace] = useState<boolean>(true);

  // Modifiers state: 0 = off, 1 = latched (1 tap), 2 = locked (2 taps)
  const [shiftState, setShiftState] = useState<number>(0);
  const [ctrlState, setCtrlState] = useState<number>(0);
  const [altState, setAltState] = useState<number>(0);
  const [winState, setWinState] = useState<number>(0);
  const [capsLock, setCapsLock] = useState<boolean>(false);

  // Typed Text Output
  const [typedText, setTypedText] = useState<string>('Hello Iron Man! ');
  const [lastActionFeedback, setLastActionFeedback] = useState<string>('Ready - Press keys 1-4 or click');
  const [copied, setCopied] = useState<boolean>(false);
  const [bounceAnimation, setBounceAnimation] = useState<boolean>(false);

  // Live Camera preview state
  const [cameraActive, setCameraActive] = useState<boolean>(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Finger curl simulators for manual sliders & hold-repeat
  const [fingerCurls, setFingerCurls] = useState<number[]>([10, 10, 10, 10]); // index, middle, ring, pinky 0..100
  const [activeFingerTap, setActiveFingerTap] = useState<number | null>(null);

  // Precomputed windows
  const mainWindows = MAIN_ROWS.map(r => buildWindows(r));
  const symbolWindows = SYMBOL_ROWS.map(r => buildWindows(r));

  // Current active window
  const activeWinIdx = currentZone === 'MAIN' ? mainWinIdx : symbolWinIdx;
  const currentWindows = currentZone === 'MAIN' 
    ? mainWindows[currentRow] 
    : symbolWindows[currentRow];
  const safeWinIdx = Math.min(activeWinIdx, Math.max(0, currentWindows.length - 1));
  const activeWindow = currentWindows[safeWinIdx] || { start: 0, keys: [] };

  // Check if at right edge of MAIN to show crossing arrow
  const isAtMainRightEdge = currentZone === 'MAIN' && safeWinIdx === currentWindows.length - 1 && symbolsEnabled;
  const isAtSymbolsLeftEdge = currentZone === 'SYMBOLS' && safeWinIdx === 0;

  // Inter-zone crossing
  const handleNextWindow = useCallback(() => {
    if (currentZone === 'MAIN') {
      if (safeWinIdx < currentWindows.length - 1) {
        setMainWinIdx(safeWinIdx + 1);
      } else if (symbolsEnabled) {
        // Cross into SYMBOLS zone
        setCurrentZone('SYMBOLS');
        setSymbolWinIdx(0);
        setLastActionFeedback('Swiped Right: Crossed into SYMBOLS panel');
      }
    } else {
      // In SYMBOLS
      if (safeWinIdx < currentWindows.length - 1) {
        setSymbolWinIdx(safeWinIdx + 1);
      } else {
        // Bounce animation at boundary
        setBounceAnimation(true);
        setTimeout(() => setBounceAnimation(false), 300);
        setLastActionFeedback('End of Symbols: Right boundary bounce');
      }
    }
  }, [currentZone, safeWinIdx, currentWindows.length, symbolsEnabled]);

  const handlePrevWindow = useCallback(() => {
    if (currentZone === 'SYMBOLS') {
      if (safeWinIdx > 0) {
        setSymbolWinIdx(safeWinIdx - 1);
      } else {
        // Cross back to MAIN zone
        setCurrentZone('MAIN');
        const mainW = mainWindows[currentRow];
        setMainWinIdx(mainW.length - 1);
        setLastActionFeedback('Swiped Left: Returned to MAIN keyboard');
      }
    } else {
      // In MAIN
      if (safeWinIdx > 0) {
        setMainWinIdx(safeWinIdx - 1);
      } else {
        setBounceAnimation(true);
        setTimeout(() => setBounceAnimation(false), 300);
      }
    }
  }, [currentZone, safeWinIdx, currentRow, mainWindows]);

  const handleRowUp = useCallback(() => {
    if (currentRow > 0) {
      setCurrentRow(r => r - 1);
      setLastActionFeedback(`Swiped Up: Row ${currentRow} → ${currentRow - 1}`);
    }
  }, [currentRow]);

  const handleRowDown = useCallback(() => {
    if (currentRow < 5) {
      setCurrentRow(r => r + 1);
      setLastActionFeedback(`Swiped Down: Row ${currentRow} → ${currentRow + 1}`);
    }
  }, [currentRow]);

  const toggleZone = useCallback(() => {
    if (!symbolsEnabled) return;
    if (currentZone === 'MAIN') {
      setCurrentZone('SYMBOLS');
      setLastActionFeedback('Zone Toggle: Switched to SYMBOLS (Ctrl+Alt+S)');
    } else {
      setCurrentZone('MAIN');
      setLastActionFeedback('Zone Toggle: Switched to MAIN (Ctrl+Alt+S)');
    }
  }, [symbolsEnabled, currentZone]);

  // Execute a key press
  const executeKey = useCallback((key: string, fingerIndex: number) => {
    setActiveFingerTap(fingerIndex);
    setTimeout(() => setActiveFingerTap(null), 220);

    // Modifier keys handling
    if (key === 'Shift') {
      setShiftState(s => (s + 1) % 3);
      setLastActionFeedback(`Shift: ${['OFF', 'LATCHED (1x)', 'LOCKED (2x)'][(shiftState + 1) % 3]}`);
      return;
    }
    if (key === 'Ctrl') {
      setCtrlState(c => (c + 1) % 3);
      setLastActionFeedback(`Ctrl: ${['OFF', 'LATCHED (1x)', 'LOCKED (2x)'][(ctrlState + 1) % 3]}`);
      return;
    }
    if (key === 'Alt') {
      setAltState(a => (a + 1) % 3);
      setLastActionFeedback(`Alt: ${['OFF', 'LATCHED (1x)', 'LOCKED (2x)'][(altState + 1) % 3]}`);
      return;
    }
    if (key === 'Win') {
      setWinState(w => (w + 1) % 3);
      setLastActionFeedback(`Win: ${['OFF', 'LATCHED (1x)', 'LOCKED (2x)'][(winState + 1) % 3]}`);
      return;
    }
    if (key === 'Caps Lock') {
      setCapsLock(c => !c);
      setLastActionFeedback(`Caps Lock: ${!capsLock ? 'ON' : 'OFF'}`);
      return;
    }

    // Special keys
    if (key === 'Backspace') {
      setTypedText(t => t.slice(0, -1));
      setLastActionFeedback(`Finger ${fingerIndex + 1} (${FINGER_LABELS[fingerIndex]}): Backspace`);
      return;
    }
    if (key === 'Enter') {
      setTypedText(t => t + '\n');
      setLastActionFeedback(`Finger ${fingerIndex + 1} (${FINGER_LABELS[fingerIndex]}): Newline`);
      return;
    }
    if (key === 'SPACE' || key === 'Space') {
      setTypedText(t => t + ' ');
      setLastActionFeedback(`Finger ${fingerIndex + 1} (${FINGER_LABELS[fingerIndex]}): Space`);
      return;
    }
    if (key === 'Tab') {
      setTypedText(t => t + '    ');
      setLastActionFeedback(`Finger ${fingerIndex + 1} (${FINGER_LABELS[fingerIndex]}): Tab (4 spaces)`);
      return;
    }
    if (key === 'Del') {
      setTypedText(t => t.slice(0, -1));
      setLastActionFeedback(`Finger ${fingerIndex + 1} (${FINGER_LABELS[fingerIndex]}): Delete`);
      return;
    }

    // Letters & Symbols
    let outputChar = key;
    const isLetter = key.length === 1 && key.toUpperCase() !== key.toLowerCase();

    if (isLetter) {
      const isShifted = (shiftState > 0) !== capsLock;
      outputChar = isShifted ? key.toUpperCase() : key.toLowerCase();
    }

    setTypedText(t => t + outputChar);
    setLastActionFeedback(`Finger ${fingerIndex + 1} (${FINGER_LABELS[fingerIndex]}): Typed '${outputChar}'`);

    // Reset latched modifiers (state === 1)
    if (shiftState === 1) setShiftState(0);
    if (ctrlState === 1) setCtrlState(0);
    if (altState === 1) setAltState(0);
    if (winState === 1) setWinState(0);
  }, [shiftState, ctrlState, altState, winState, capsLock]);

  // Handle tap from finger 0..3
  const handleFingerTap = useCallback((fingerIdx: number) => {
    if (activeWindow && activeWindow.keys[fingerIdx]) {
      executeKey(activeWindow.keys[fingerIdx], fingerIdx);
    }
  }, [activeWindow, executeKey]);

  // Handle thumb tap
  const handleThumbTap = useCallback(() => {
    setActiveFingerTap(4); // 4 = thumb
    setTimeout(() => setActiveFingerTap(null), 220);
    if (thumbIsSpace) {
      setTypedText(t => t + ' ');
      setLastActionFeedback('Thumb Tap: Typed [SPACE]');
    } else {
      setLastActionFeedback('Thumb Tap: Thumb action triggered');
    }
  }, [thumbIsSpace]);

  // Physical keyboard listeners for quick simulation testing
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't capture when typing in an input
      if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA') {
        return;
      }

      // Keys 1, 2, 3, 4 trigger finger taps
      if (e.key === '1') {
        e.preventDefault();
        handleFingerTap(0);
      } else if (e.key === '2') {
        e.preventDefault();
        handleFingerTap(1);
      } else if (e.key === '3') {
        e.preventDefault();
        handleFingerTap(2);
      } else if (e.key === '4') {
        e.preventDefault();
        handleFingerTap(3);
      } else if (e.code === 'Space') {
        e.preventDefault();
        handleThumbTap();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        handleRowUp();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        handleRowDown();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        handlePrevWindow();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        handleNextWindow();
      } else if (e.key.toLowerCase() === 's' && (e.ctrlKey || e.altKey || !e.shiftKey)) {
        // Toggle zone with S or Ctrl+Alt+S
        if (e.ctrlKey || e.altKey) {
          e.preventDefault();
          toggleZone();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleFingerTap, handleThumbTap, handleRowUp, handleRowDown, handlePrevWindow, handleNextWindow, toggleZone]);

  // Webcam streamer
  const toggleCamera = async () => {
    if (cameraActive) {
      if (videoRef.current && videoRef.current.srcObject) {
        const stream = videoRef.current.srcObject as MediaStream;
        stream.getTracks().forEach(track => track.stop());
        videoRef.current.srcObject = null;
      }
      setCameraActive(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play();
        }
        setCameraActive(true);
      } catch (err) {
        console.warn('Webcam permission not granted or device not available', err);
      }
    }
  };

  const copyText = () => {
    navigator.clipboard.writeText(typedText);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex flex-col gap-6">
      {/* HUD Header Bar for Keyboard Mode */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-4 rounded-lg bg-slate-950/80 border border-slate-800 shadow-xl hud-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-md bg-cyan-950/70 border border-cyan-400/60 flex items-center justify-center text-cyan-400">
            <KeyboardIcon className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold font-hud tracking-wide text-white">
                FLOATING AIR KEYBOARD HUD
              </span>
              <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
                ACTIVE ZONE: {currentZone}
              </span>
              <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-slate-900 text-slate-300 border border-slate-800">
                ROW {currentRow + 1}/6
              </span>
              <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-slate-900 text-slate-300 border border-slate-800">
                WIN {safeWinIdx + 1}/{currentWindows.length}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5 font-mono">
              Hover 4 adjacent keys locked to 4 fingers (Index, Middle, Ring, Pinky). Swipe to slide windows or rows.
            </p>
          </div>
        </div>

        {/* Quick controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={toggleZone}
            disabled={!symbolsEnabled}
            className={`px-3 py-1.5 text-xs font-mono rounded border transition-colors flex items-center gap-1.5 cursor-pointer ${
              currentZone === 'SYMBOLS'
                ? 'bg-purple-950 border-purple-500 text-purple-300 shadow-[0_0_10px_rgba(168,85,247,0.3)]'
                : 'bg-slate-900 border-slate-700 text-slate-300 hover:text-white'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Switch Zone (Ctrl+Alt+S)</span>
          </button>

          <button
            onClick={toggleCamera}
            className={`px-3 py-1.5 text-xs font-mono rounded border transition-colors flex items-center gap-1.5 cursor-pointer ${
              cameraActive 
                ? 'bg-cyan-950 border-cyan-500 text-cyan-300' 
                : 'bg-slate-900 border-slate-700 text-slate-400 hover:text-slate-200'
            }`}
          >
            <Camera className="w-3.5 h-3.5" />
            <span>{cameraActive ? 'Hide Mirror' : 'Live Mirror'}</span>
          </button>
        </div>
      </div>

      {/* Main Dual Holographic Keyboard Stage */}
      <div className={`relative p-5 rounded-xl bg-slate-950/90 border border-slate-800/90 shadow-2xl backdrop-blur-md overflow-x-auto transition-transform ${
        bounceAnimation ? 'translate-x-1.5' : ''
      }`}>
        {/* Holographic grid backdrop overlay */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#0284c70a_1px,transparent_1px),linear-gradient(to_bottom,#0284c70a_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none rounded-xl" />

        <div className="relative flex flex-col md:flex-row gap-6 items-stretch min-w-[920px]">
          {/* ================= LEFT: MAIN KEYBOARD (Exact 6 Rows, 26 letters) ================= */}
          <div className={`flex-1 transition-opacity duration-200 ${
            currentZone === 'SYMBOLS' && dimInactive ? 'opacity-40' : 'opacity-100'
          }`}>
            <div className="flex items-center justify-between mb-3 border-b border-cyan-950 pb-2">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_6px_#00e5ff]" />
                <span className="text-xs font-hud font-bold tracking-wider text-cyan-300">
                  MAIN KEYBOARD (LEFT ZONE · LAPTOP-STYLE)
                </span>
              </div>
              <span className="text-[10px] font-mono text-cyan-500">
                {currentZone === 'MAIN' ? '● FOCUS LOCKED' : '○ INACTIVE'}
              </span>
            </div>

            {/* Render 6 Main Rows */}
            <div className="flex flex-col gap-1.5 font-mono text-xs">
              {MAIN_ROWS.map((rowKeys, rIdx) => {
                const isSelectedRow = currentZone === 'MAIN' && currentRow === rIdx;
                const win = mainWindows[rIdx][Math.min(mainWinIdx, mainWindows[rIdx].length - 1)];
                const lockedStartIndex = isSelectedRow ? win.start : -1;
                const lockedEndIndex = isSelectedRow ? win.start + 4 : -1;

                return (
                  <div 
                    key={`main-row-${rIdx}`} 
                    className={`flex items-center gap-1 p-1 rounded transition-colors ${
                      isSelectedRow ? 'bg-cyan-950/30 border border-cyan-800/40' : 'opacity-85'
                    }`}
                  >
                    {/* Row Indicator */}
                    <div className="w-5 text-[9px] font-mono text-slate-500 shrink-0 text-center">
                      R{rIdx + 1}
                    </div>

                    {/* Keys in Row */}
                    <div className="flex items-center gap-1 flex-1">
                      {rowKeys.map((key, kIdx) => {
                        const isLocked = isSelectedRow && kIdx >= lockedStartIndex && kIdx < lockedEndIndex;
                        const fingerIdx = isLocked ? kIdx - lockedStartIndex : -1;
                        const isBeingTapped = isLocked && activeFingerTap === fingerIdx;

                        // Width formatting based on key role
                        let widthClass = 'flex-1 min-w-[28px]';
                        if (key === 'SPACE') widthClass = 'w-36 flex-grow-[3]';
                        else if (key === 'Backspace' || key === 'Enter' || key === 'Caps Lock') widthClass = 'w-20 shrink-0';
                        else if (key === 'Shift') widthClass = 'w-16 shrink-0';
                        else if (key === 'Tab') widthClass = 'w-14 shrink-0';

                        // Check sticky modifier state
                        let modifierStatus = '';
                        if (key === 'Shift' && shiftState > 0) modifierStatus = shiftState === 1 ? 'LATCH' : 'LOCK';
                        if (key === 'Ctrl' && ctrlState > 0) modifierStatus = ctrlState === 1 ? 'LATCH' : 'LOCK';
                        if (key === 'Alt' && altState > 0) modifierStatus = altState === 1 ? 'LATCH' : 'LOCK';
                        if (key === 'Win' && winState > 0) modifierStatus = winState === 1 ? 'LATCH' : 'LOCK';
                        if (key === 'Caps Lock' && capsLock) modifierStatus = 'ON';

                        return (
                          <button
                            key={`main-k-${rIdx}-${kIdx}`}
                            onClick={() => {
                              if (isLocked) {
                                handleFingerTap(fingerIdx);
                              } else {
                                setCurrentZone('MAIN');
                                setCurrentRow(rIdx);
                                // find closest window containing this key
                                const targetWinIdx = mainWindows[rIdx].findIndex(w => kIdx >= w.start && kIdx < w.start + 4);
                                if (targetWinIdx >= 0) setMainWinIdx(targetWinIdx);
                              }
                            }}
                            className={`relative h-10 px-1 rounded flex flex-col items-center justify-center font-bold transition-all text-center select-none cursor-pointer ${widthClass} ${
                              isBeingTapped
                                ? 'bg-cyan-300 text-slate-950 scale-95 shadow-[0_0_15px_#00e5ff]'
                                : isLocked
                                ? 'bg-cyan-600/30 border-2 border-cyan-400 text-cyan-100 shadow-[0_0_12px_rgba(0,229,255,0.4)]'
                                : 'bg-slate-900/70 border border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                            }`}
                          >
                            {/* Finger Badge on locked keys */}
                            {isLocked && (
                              <div className="absolute -top-2 left-1/2 -translate-x-1/2 px-1 py-0.2 bg-cyan-400 text-[8px] font-mono text-slate-950 rounded shadow font-extrabold whitespace-nowrap">
                                {FINGER_SHORT[fingerIdx]} (F{fingerIdx + 1})
                              </div>
                            )}

                            {/* Modifier badge */}
                            {modifierStatus && (
                              <span className="absolute bottom-0.5 right-1 text-[8px] text-amber-400 font-extrabold">
                                {modifierStatus}
                              </span>
                            )}

                            <span className={`${key.length > 2 ? 'text-[10px]' : 'text-xs'}`}>
                              {key}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ================= GLOWING VERTICAL DIVIDER & INTER-ZONE ARROW ================= */}
          <div className="flex flex-col items-center justify-center px-1 relative shrink-0">
            {/* Holographic vertical laser line */}
            <div className="w-[2px] h-full bg-gradient-to-b from-cyan-500/20 via-purple-500/50 to-cyan-500/20 shadow-[0_0_10px_rgba(168,85,247,0.5)]" />

            {/* Glowing Center Badge */}
            <div className="my-auto py-3 px-1.5 bg-slate-900 border border-purple-800/80 rounded-md flex flex-col items-center gap-2 z-10 shadow-lg">
              <span className="text-[9px] font-mono text-purple-400 [writing-mode:vertical-lr] rotate-180 tracking-widest font-bold">
                DIVIDER
              </span>

              {/* Pulsing Inter-Zone Cross Arrow Indicator */}
              {isAtMainRightEdge && (
                <div 
                  onClick={handleNextWindow}
                  title="Swipe Right to cross into SYMBOLS"
                  className="w-7 h-7 rounded-full bg-purple-500/20 border border-purple-400 flex items-center justify-center text-purple-300 animate-pulse cursor-pointer shadow-[0_0_10px_#a855f7]"
                >
                  <ChevronRight className="w-4 h-4" />
                </div>
              )}

              {isAtSymbolsLeftEdge && (
                <div 
                  onClick={handlePrevWindow}
                  title="Swipe Left to return to MAIN"
                  className="w-7 h-7 rounded-full bg-cyan-500/20 border border-cyan-400 flex items-center justify-center text-cyan-300 animate-pulse cursor-pointer shadow-[0_0_10px_#00e5ff]"
                >
                  <ChevronLeft className="w-4 h-4" />
                </div>
              )}
            </div>
          </div>

          {/* ================= RIGHT: SYMBOLS PANEL (6 Aligned Rows, Violet/Teal Theme) ================= */}
          {symbolsEnabled && (
            <div className={`w-[360px] shrink-0 transition-opacity duration-200 ${
              currentZone === 'MAIN' && dimInactive ? 'opacity-40' : 'opacity-100'
            }`}>
              <div className="flex items-center justify-between mb-3 border-b border-purple-950 pb-2">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-purple-400 shadow-[0_0_6px_#a855f7]" />
                  <span className="text-xs font-hud font-bold tracking-wider text-purple-300">
                    SYMBOLS PANEL (RIGHT ZONE · DOCKED)
                  </span>
                </div>
                <span className="text-[10px] font-mono text-purple-400">
                  {currentZone === 'SYMBOLS' ? '● FOCUS LOCKED' : '○ INACTIVE'}
                </span>
              </div>

              {/* Render 6 Symbols Rows */}
              <div className="flex flex-col gap-1.5 font-mono text-xs">
                {SYMBOL_ROWS.map((rowKeys, rIdx) => {
                  const isSelectedRow = currentZone === 'SYMBOLS' && currentRow === rIdx;
                  const win = symbolWindows[rIdx][Math.min(symbolWinIdx, symbolWindows[rIdx].length - 1)];
                  const lockedStartIndex = isSelectedRow ? win.start : -1;
                  const lockedEndIndex = isSelectedRow ? win.start + 4 : -1;

                  return (
                    <div 
                      key={`symbol-row-${rIdx}`} 
                      className={`flex items-center gap-1 p-1 rounded transition-colors ${
                        isSelectedRow ? 'bg-purple-950/30 border border-purple-800/40' : 'opacity-85'
                      }`}
                    >
                      {/* Keys in Row */}
                      <div className="flex items-center gap-1 flex-1">
                        {rowKeys.map((key, kIdx) => {
                          const isLocked = isSelectedRow && kIdx >= lockedStartIndex && kIdx < lockedEndIndex;
                          const fingerIdx = isLocked ? kIdx - lockedStartIndex : -1;
                          const isBeingTapped = isLocked && activeFingerTap === fingerIdx;

                          return (
                            <button
                              key={`symbol-k-${rIdx}-${kIdx}`}
                              onClick={() => {
                                if (isLocked) {
                                  handleFingerTap(fingerIdx);
                                } else {
                                  setCurrentZone('SYMBOLS');
                                  setCurrentRow(rIdx);
                                  const targetWinIdx = symbolWindows[rIdx].findIndex(w => kIdx >= w.start && kIdx < w.start + 4);
                                  if (targetWinIdx >= 0) setSymbolWinIdx(targetWinIdx);
                                }
                              }}
                              className={`relative h-10 px-1 flex-1 min-w-[28px] rounded flex flex-col items-center justify-center font-bold transition-all text-center select-none cursor-pointer ${
                                isBeingTapped
                                  ? 'bg-purple-300 text-slate-950 scale-95 shadow-[0_0_15px_#c084fc]'
                                  : isLocked
                                  ? 'bg-purple-700/40 border-2 border-cyan-400 text-cyan-200 shadow-[0_0_12px_rgba(0,229,255,0.4)]'
                                  : 'bg-slate-900/70 border border-purple-900/40 text-purple-300/70 hover:border-purple-700 hover:text-purple-200'
                              }`}
                            >
                              {/* Finger Badge on locked keys */}
                              {isLocked && (
                                <div className="absolute -top-2 left-1/2 -translate-x-1/2 px-1 py-0.2 bg-cyan-400 text-[8px] font-mono text-slate-950 rounded shadow font-extrabold whitespace-nowrap">
                                  {FINGER_SHORT[fingerIdx]} (F{fingerIdx + 1})
                                </div>
                              )}

                              <span className={`${key.length > 2 ? 'text-[10px]' : 'text-xs'}`}>
                                {key}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Control Strip & Interactive Simulator Deck */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (7 cols): Interactive Text Output & Per-Finger Tap Simulator */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          {/* Real-time Typed Text Output Notepad */}
          <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 shadow-md flex flex-col gap-3">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold text-cyan-400">
                  REAL-TIME TYPED OUTPUT STREAM
                </span>
                <span className="text-[10px] text-slate-500 font-mono">
                  (Simulated Win32 SendInput Scancodes)
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={copyText}
                  className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-mono rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 cursor-pointer"
                >
                  {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
                <button
                  onClick={() => setTypedText('')}
                  className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-mono rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-400 hover:text-rose-400 cursor-pointer"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Clear</span>
                </button>
              </div>
            </div>

            {/* Output Textarea display */}
            <div className="relative min-h-[90px] p-3 rounded bg-black/60 border border-slate-800 font-mono text-sm text-cyan-100 whitespace-pre-wrap break-words selection:bg-cyan-500/30 selection:text-white">
              {typedText || <span className="text-slate-600 italic">Start typing by tapping fingers 1-4...</span>}
              <span className="inline-block w-2 h-4 bg-cyan-400 ml-1 animate-pulse align-middle" />
            </div>

            {/* Last Action Feedback strip */}
            <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-1">
              <span className="text-cyan-400">{lastActionFeedback}</span>
              <div className="flex items-center gap-3">
                <span>Caps: <strong className={capsLock ? 'text-cyan-300' : 'text-slate-600'}>{capsLock ? 'ON' : 'OFF'}</strong></span>
                <span>Shift: <strong className={shiftState > 0 ? 'text-amber-400' : 'text-slate-600'}>{['OFF', 'LATCH', 'LOCK'][shiftState]}</strong></span>
              </div>
            </div>
          </div>

          {/* Interactive Air Finger Tap Deck */}
          <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 flex flex-col gap-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <span className="text-xs font-mono font-bold text-cyan-400 font-hud tracking-wide">
                PER-FINGER AIR-TAP CONTROLLER (PRESS 1, 2, 3, 4 OR CLICK)
              </span>
              <span className="text-[10px] font-mono text-slate-500">
                Visual order matches hand on camera
              </span>
            </div>

            <div className="grid grid-cols-5 gap-2.5">
              {FINGER_LABELS.map((fingerName, idx) => {
                const mappedKey = activeWindow.keys[idx] || '-';
                const isTapped = activeFingerTap === idx;

                return (
                  <button
                    key={`finger-trigger-${idx}`}
                    onClick={() => handleFingerTap(idx)}
                    className={`p-3 rounded-lg border flex flex-col items-center gap-1.5 transition-all cursor-pointer ${
                      isTapped 
                        ? 'bg-cyan-400 border-cyan-300 text-slate-950 scale-95 shadow-[0_0_15px_rgba(0,229,255,0.8)]' 
                        : 'bg-slate-900/80 border-slate-700 text-slate-200 hover:border-cyan-500/70 hover:bg-slate-800/90'
                    }`}
                  >
                    <span className="text-[10px] font-mono text-slate-400">
                      F{idx + 1} ({FINGER_SHORT[idx]})
                    </span>
                    <span className="text-base font-bold font-hud text-cyan-300">
                      {mappedKey}
                    </span>
                    <span className="text-[9px] font-mono text-slate-500">
                      {fingerName}
                    </span>
                  </button>
                );
              })}

              {/* Thumb Button */}
              <button
                onClick={handleThumbTap}
                className={`p-3 rounded-lg border flex flex-col items-center gap-1.5 transition-all cursor-pointer ${
                  activeFingerTap === 4
                    ? 'bg-amber-400 border-amber-300 text-slate-950 scale-95 shadow-[0_0_15px_rgba(251,191,36,0.8)]'
                    : 'bg-slate-900/80 border-amber-800/40 text-amber-200 hover:border-amber-500 hover:bg-slate-800/90'
                }`}
              >
                <span className="text-[10px] font-mono text-amber-400">
                  THUMB
                </span>
                <span className="text-base font-bold font-hud text-amber-300">
                  SPACE
                </span>
                <span className="text-[9px] font-mono text-slate-500">
                  Press Spacebar
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* Right Column (5 cols): Window Slider Nav & Live Camera Preview */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          {/* Navigation Controls: Whole-Hand Swipes */}
          <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 flex flex-col gap-3">
            <span className="text-xs font-mono font-bold text-cyan-400 font-hud tracking-wide border-b border-slate-800 pb-2">
              WHOLE-HAND SWIPE & SLIDING DOOR NAVIGATION
            </span>

            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              <button
                onClick={handleRowUp}
                disabled={currentRow === 0}
                className="flex items-center justify-center gap-2 p-2 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 disabled:opacity-40 cursor-pointer"
              >
                <ArrowUp className="w-3.5 h-3.5 text-cyan-400" />
                <span>Swipe Up (Row {currentRow + 1}→{Math.max(1, currentRow)})</span>
              </button>

              <button
                onClick={handleRowDown}
                disabled={currentRow === 5}
                className="flex items-center justify-center gap-2 p-2 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 disabled:opacity-40 cursor-pointer"
              >
                <ArrowDown className="w-3.5 h-3.5 text-cyan-400" />
                <span>Swipe Down (Row {currentRow + 1}→{Math.min(6, currentRow + 2)})</span>
              </button>

              <button
                onClick={handlePrevWindow}
                className="flex items-center justify-center gap-2 p-2 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5 text-cyan-400" />
                <span>Swipe Left (Prev Win)</span>
              </button>

              <button
                onClick={handleNextWindow}
                className="flex items-center justify-center gap-2 p-2 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 cursor-pointer"
              >
                <ArrowRight className="w-3.5 h-3.5 text-cyan-400" />
                <span>Swipe Right (Next Win)</span>
              </button>
            </div>

            <div className="p-2.5 rounded bg-black/40 border border-slate-800 text-[11px] font-mono text-slate-400 space-y-1">
              <div>• <strong>Left/Right Swipes:</strong> Hop 4-key progressive windows.</div>
              <div>• <strong>Last Window of Main:</strong> Swiping right crosses the glowing divider into Symbols.</div>
              <div>• <strong>First Window of Symbols:</strong> Swiping left returns to Main keyboard.</div>
            </div>
          </div>

          {/* Live Camera Mirror with HUD Overlays */}
          {cameraActive ? (
            <div className="relative rounded-lg overflow-hidden border border-cyan-800/80 bg-black aspect-video flex items-center justify-center shadow-lg">
              <video 
                ref={videoRef} 
                autoPlay 
                playsInline 
                muted 
                className="w-full h-full object-cover scale-x-[-1]"
              />
              <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/70 border border-cyan-400/50 text-[10px] font-mono text-cyan-300">
                LIVE CAMERA MIRROR (TRACKING ACTIVE)
              </div>
              <div className="absolute inset-0 border-2 border-cyan-500/20 pointer-events-none" />
            </div>
          ) : (
            <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 flex flex-col gap-2.5 text-xs font-mono text-slate-400">
              <div className="flex items-center justify-between text-cyan-400 font-bold">
                <span>AIR KEYBOARD GESTURES SUMMARY</span>
                <span className="text-[10px] text-slate-500">Tony Pointer Mark 85</span>
              </div>
              <div className="space-y-1 text-[11px]">
                <div className="flex justify-between">
                  <span className="text-slate-400">Open Palm Hold (0.5s):</span>
                  <span className="text-cyan-300">Open Air Keyboard</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Fist Hold (0.5s) / Esc:</span>
                  <span className="text-rose-300">Exit to Pointer Mode</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Individual Finger Curl:</span>
                  <span className="text-emerald-300">Type Locked Key (1-4)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Hold Key &gt;0.5s:</span>
                  <span className="text-amber-300">Key Repeat (30 cps)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Thumb Air Tap:</span>
                  <span className="text-cyan-300">Spacebar</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Swipe X / Y:</span>
                  <span className="text-indigo-300">Slide Windows / Rows</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
