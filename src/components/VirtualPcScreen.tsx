import React, { useState, useRef, useEffect } from 'react';
import { 
  Folder, 
  Paintbrush, 
  FileText, 
  Monitor, 
  X, 
  RotateCcw, 
  Maximize2,
  MousePointer,
  Sparkles,
  Layers
} from 'lucide-react';

interface VirtualPcScreenProps {
  cursorPos: { x: number; y: number };
  brushLocked: boolean;
  onToggleBrushLock: () => void;
  lastAction: string;
  isModeActive: boolean;
  dwellProgress: number;
}

interface PaintStroke {
  points: { x: number; y: number }[];
  color: string;
  size: number;
}

export const VirtualPcScreen: React.FC<VirtualPcScreenProps> = ({
  cursorPos,
  brushLocked,
  onToggleBrushLock,
  lastAction,
  isModeActive,
  dwellProgress,
}) => {
  const [openWindow, setOpenWindow] = useState<'paint' | 'notes' | 'folder' | null>('paint');
  const [paintStrokes, setPaintStrokes] = useState<PaintStroke[]>([]);
  const [currentStroke, setCurrentStroke] = useState<{ x: number; y: number }[]>([]);
  const [brushColor, setBrushColor] = useState('#00e5ff');
  const [brushSize, setBrushSize] = useState(4);
  const [rippleAnim, setRippleAnim] = useState<{ x: number; y: number; double: boolean } | null>(null);
  const [contextMenuPos, setContextMenuPos] = useState<{ x: number; y: number } | null>(null);

  const paintCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Trigger ripple animation on clicks
  useEffect(() => {
    if (lastAction === 'SINGLE_CLICK') {
      setRippleAnim({ x: cursorPos.x, y: cursorPos.y, double: false });
      const timer = setTimeout(() => setRippleAnim(null), 400);
      return () => clearTimeout(timer);
    } else if (lastAction === 'DOUBLE_CLICK') {
      setRippleAnim({ x: cursorPos.x, y: cursorPos.y, double: true });
      // If double click lands on an icon, open it
      const timer = setTimeout(() => setRippleAnim(null), 500);
      return () => clearTimeout(timer);
    } else if (lastAction === 'RIGHT_CLICK') {
      setContextMenuPos({ x: cursorPos.x, y: cursorPos.y });
    }
  }, [lastAction, cursorPos]);

  // Handle continuous painting when Brush Lock is active
  useEffect(() => {
    if (!brushLocked) {
      if (currentStroke.length > 0) {
        setPaintStrokes((prev) => [...prev, { points: currentStroke, color: brushColor, size: brushSize }]);
        setCurrentStroke([]);
      }
      return;
    }

    // Brush is locked! Add points to current continuous stroke
    const canvas = paintCanvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const container = containerRef.current?.getBoundingClientRect();
    if (!container) return;

    // Check if cursor is inside the paint canvas bounds
    const screenAbsX = container.left + (cursorPos.x / 100) * container.width;
    const screenAbsY = container.top + (cursorPos.y / 100) * container.height;

    if (
      screenAbsX >= rect.left &&
      screenAbsX <= rect.right &&
      screenAbsY >= rect.top &&
      screenAbsY <= rect.bottom
    ) {
      const localX = screenAbsX - rect.left;
      const localY = screenAbsY - rect.top;
      setCurrentStroke((prev) => [...prev, { x: localX, y: localY }]);
    }
  }, [cursorPos, brushLocked, brushColor, brushSize]);

  // Render paint strokes on canvas
  useEffect(() => {
    const canvas = paintCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Completed strokes
    paintStrokes.forEach((stroke) => {
      if (stroke.points.length < 2) return;
      ctx.strokeStyle = stroke.color;
      ctx.lineWidth = stroke.size;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.beginPath();
      ctx.moveTo(stroke.points[0].x, stroke.points[0].y);
      for (let i = 1; i < stroke.points.length; i++) {
        ctx.lineTo(stroke.points[i].x, stroke.points[i].y);
      }
      ctx.stroke();
    });

    // Active live stroke
    if (currentStroke.length > 1) {
      ctx.strokeStyle = brushColor;
      ctx.lineWidth = brushSize;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.beginPath();
      ctx.moveTo(currentStroke[0].x, currentStroke[0].y);
      for (let i = 1; i < currentStroke.length; i++) {
        ctx.lineTo(currentStroke[i].x, currentStroke[i].y);
      }
      ctx.stroke();
    }
  }, [paintStrokes, currentStroke, brushColor, brushSize]);

  return (
    <div
      ref={containerRef}
      onClick={() => setContextMenuPos(null)}
      className="relative w-full h-[540px] rounded-lg border border-slate-800 bg-[#070b14] overflow-hidden select-none shadow-2xl flex flex-col"
    >
      {/* Desktop Wallpaper with subtle Stark Hologram grid */}
      <div className="absolute inset-0 hud-grid-pattern opacity-40 pointer-events-none" />

      {/* Top OS Menu / Title Ribbon */}
      <div className="relative z-10 flex items-center justify-between px-3 py-1.5 bg-slate-950/80 border-b border-slate-800 text-xs">
        <div className="flex items-center gap-2 text-slate-300">
          <Monitor className="w-3.5 h-3.5 text-cyan-400" />
          <span className="font-semibold tracking-wide">VIRTUAL WINDOWS DESKTOP</span>
          <span className="text-[11px] font-mono text-slate-500">· MULTI-APP TEST CHAMBER</span>
        </div>

        <div className="flex items-center gap-3 text-[11px] font-mono">
          <span className="text-slate-400">
            POINTER: <span className="text-cyan-400">{cursorPos.x.toFixed(1)}%, {cursorPos.y.toFixed(1)}%</span>
          </span>
          <button
            onClick={onToggleBrushLock}
            className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-all cursor-pointer ${
              brushLocked
                ? 'bg-rose-500 text-white shadow-[0_0_10px_rgba(244,63,94,0.6)]'
                : 'bg-slate-800 text-slate-300 hover:text-white'
            }`}
          >
            {brushLocked ? 'BRUSH LOCKED (MOUSE DOWN)' : 'LOCK BRUSH (DWELL / PINCH)'}
          </button>
        </div>
      </div>

      {/* Desktop Workspace Area */}
      <div className="relative flex-1 p-4">
        {/* Desktop Icons */}
        <div className="flex flex-col gap-4 w-20">
          <button
            onDoubleClick={() => setOpenWindow('paint')}
            onClick={() => {}}
            className="group flex flex-col items-center gap-1 p-2 rounded hover:bg-cyan-500/10 border border-transparent hover:border-cyan-500/30 transition-colors text-center cursor-pointer"
          >
            <div className="w-10 h-10 rounded bg-cyan-950/60 border border-cyan-500/40 flex items-center justify-center text-cyan-400 group-hover:scale-105 transition-transform">
              <Paintbrush className="w-5 h-5" />
            </div>
            <span className="text-[11px] font-medium text-slate-200">Paint Studio</span>
          </button>

          <button
            onDoubleClick={() => setOpenWindow('folder')}
            className="group flex flex-col items-center gap-1 p-2 rounded hover:bg-cyan-500/10 border border-transparent hover:border-cyan-500/30 transition-colors text-center cursor-pointer"
          >
            <div className="w-10 h-10 rounded bg-amber-950/60 border border-amber-500/40 flex items-center justify-center text-amber-400 group-hover:scale-105 transition-transform">
              <Folder className="w-5 h-5" />
            </div>
            <span className="text-[11px] font-medium text-slate-200">Documents</span>
          </button>

          <button
            onDoubleClick={() => setOpenWindow('notes')}
            className="group flex flex-col items-center gap-1 p-2 rounded hover:bg-cyan-500/10 border border-transparent hover:border-cyan-500/30 transition-colors text-center cursor-pointer"
          >
            <div className="w-10 h-10 rounded bg-indigo-950/60 border border-indigo-500/40 flex items-center justify-center text-indigo-400 group-hover:scale-105 transition-transform">
              <FileText className="w-5 h-5" />
            </div>
            <span className="text-[11px] font-medium text-slate-200">Notes.txt</span>
          </button>
        </div>

        {/* Paint Application Window */}
        {openWindow === 'paint' && (
          <div className="absolute top-6 left-28 w-[440px] h-[380px] bg-slate-900/95 border border-cyan-500/40 rounded-lg shadow-2xl flex flex-col overflow-hidden backdrop-blur-md">
            {/* Window Header */}
            <div className="flex items-center justify-between px-3 py-1.5 bg-slate-950 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Paintbrush className="w-3.5 h-3.5 text-cyan-400" />
                <span className="text-xs font-semibold text-slate-200">Tony Creative Paint · One Euro Stabilized</span>
              </div>
              <button
                onClick={() => setOpenWindow(null)}
                className="text-slate-400 hover:text-white p-0.5 rounded cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Paint Toolbar */}
            <div className="flex items-center justify-between px-3 py-1.5 bg-slate-900 border-b border-slate-800 text-xs">
              <div className="flex items-center gap-2">
                {['#00e5ff', '#ff5722', '#ffb300', '#10b981', '#a855f7', '#ffffff'].map((c) => (
                  <button
                    key={c}
                    onClick={() => setBrushColor(c)}
                    style={{ backgroundColor: c }}
                    className={`w-4 h-4 rounded-full border cursor-pointer transition-transform ${
                      brushColor === c ? 'scale-125 border-white ring-2 ring-cyan-400/50' : 'border-slate-700'
                    }`}
                  />
                ))}
              </div>

              <div className="flex items-center gap-3">
                <span className="text-[11px] font-mono text-slate-400">
                  Size: {brushSize}px
                </span>
                <input
                  type="range"
                  min="2"
                  max="12"
                  value={brushSize}
                  onChange={(e) => setBrushSize(Number(e.target.value))}
                  className="w-16 accent-cyan-400 cursor-pointer"
                />
                <button
                  onClick={() => setPaintStrokes([])}
                  className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-cyan-400 cursor-pointer"
                >
                  <RotateCcw className="w-3 h-3" />
                  Clear
                </button>
              </div>
            </div>

            {/* Drawing Canvas */}
            <div className="relative flex-1 bg-[#050811] overflow-hidden">
              <canvas
                ref={paintCanvasRef}
                width={440}
                height={300}
                className="w-full h-full cursor-crosshair"
              />
              {paintStrokes.length === 0 && currentStroke.length === 0 && (
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-slate-600 text-xs text-center p-4">
                  <p>Hold index finger still for 0.6s (Dwell) or Pinch</p>
                  <p className="text-[11px] text-slate-500 mt-1">Left click locks DOWN and strokes follow your finger smoothly!</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Notes Window */}
        {openWindow === 'notes' && (
          <div className="absolute top-12 left-44 w-[360px] h-[280px] bg-slate-900/95 border border-indigo-500/40 rounded-lg shadow-2xl flex flex-col overflow-hidden backdrop-blur-md">
            <div className="flex items-center justify-between px-3 py-1.5 bg-slate-950 border-b border-slate-800">
              <span className="text-xs font-semibold text-slate-200">Notes.txt</span>
              <button onClick={() => setOpenWindow(null)} className="text-slate-400 hover:text-white cursor-pointer">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="flex-1 p-3 font-mono text-xs text-slate-300 leading-relaxed overflow-y-auto">
              Tony Pointer gesture calibration checklist:<br /><br />
              1. Double-tap in the air to execute double click.<br />
              2. Keep open palm to pause cursor tracking.<br />
              3. Hold 2 fingers to open this context menu.<br />
              4. Win32 SendInput bypasses DirectX focus hooks.
            </div>
          </div>
        )}

        {/* Right Click Context Menu */}
        {contextMenuPos && (
          <div
            style={{ left: `${contextMenuPos.x}%`, top: `${contextMenuPos.y}%` }}
            className="absolute z-30 w-44 bg-slate-950 border border-cyan-500/40 rounded shadow-xl py-1 text-xs text-slate-300 font-mono"
          >
            <div className="px-3 py-1 text-[10px] text-slate-500 border-b border-slate-800">CONTEXT MENU (RIGHT CLICK)</div>
            <button onClick={() => setOpenWindow('paint')} className="w-full text-left px-3 py-1.5 hover:bg-cyan-950 hover:text-cyan-300 cursor-pointer">Open Paint</button>
            <button onClick={() => setOpenWindow('notes')} className="w-full text-left px-3 py-1.5 hover:bg-cyan-950 hover:text-cyan-300 cursor-pointer">View Notes</button>
            <button onClick={() => setPaintStrokes([])} className="w-full text-left px-3 py-1.5 hover:bg-cyan-950 hover:text-cyan-300 cursor-pointer">Clear Canvas</button>
            <div className="border-t border-slate-800 my-1" />
            <button onClick={() => setContextMenuPos(null)} className="w-full text-left px-3 py-1 text-slate-500 hover:text-slate-300 cursor-pointer">Dismiss</button>
          </div>
        )}

        {/* Simulated Tony Pointer Reticle Overlay */}
        <div
          style={{
            left: `${cursorPos.x}%`,
            top: `${cursorPos.y}%`,
            transform: 'translate(-50%, -50%)',
          }}
          className="absolute pointer-events-none z-40 transition-[left,top] duration-75 ease-out"
        >
          {/* Main Reticle */}
          <div className="relative flex items-center justify-center">
            {/* Outer Rotating Arc Segments */}
            <div
              className={`w-9 h-9 rounded-full border border-dashed transition-all duration-300 ${
                brushLocked
                  ? 'border-orange-500 animate-[spin_4s_linear_infinite]'
                  : 'border-cyan-400/80 animate-[spin_8s_linear_infinite]'
              }`}
            />

            {/* Center Core */}
            <div
              className={`absolute w-3.5 h-3.5 rounded-full transition-all duration-300 ${
                brushLocked
                  ? 'bg-orange-500 shadow-[0_0_12px_rgba(255,87,34,1)] scale-110'
                  : 'bg-cyan-400 shadow-[0_0_10px_rgba(0,229,255,0.9)]'
              }`}
            />

            {/* Dwell Progress Sweep Arc */}
            {dwellProgress > 0 && !brushLocked && (
              <svg className="absolute w-12 h-12 -rotate-90 pointer-events-none">
                <circle
                  cx="24"
                  cy="24"
                  r="18"
                  fill="none"
                  stroke="#ffb300"
                  strokeWidth="2.5"
                  strokeDasharray="113"
                  strokeDashoffset={113 - 113 * dwellProgress}
                />
              </svg>
            )}
          </div>
        </div>

        {/* Click Ripple Animation */}
        {rippleAnim && (
          <div
            style={{
              left: `${rippleAnim.x}%`,
              top: `${rippleAnim.y}%`,
              transform: 'translate(-50%, -50%)',
            }}
            className="absolute pointer-events-none z-30"
          >
            <div className="w-12 h-12 rounded-full border-2 border-cyan-400 animate-ping opacity-80" />
            {rippleAnim.double && (
              <div className="w-8 h-8 rounded-full border border-amber-400 animate-ping opacity-90 -mt-10 -ml-1" />
            )}
          </div>
        )}
      </div>

      {/* Taskbar Bottom Strip */}
      <div className="relative z-10 flex items-center justify-between px-3 py-1 bg-slate-950 border-t border-slate-800 text-xs">
        <div className="flex items-center gap-2">
          <div className="px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/40 text-[11px] font-hud font-bold text-cyan-300">
            START
          </div>
          <span className="text-[11px] font-mono text-slate-500">
            ACTIVE PROFILE: {openWindow === 'paint' ? 'PAINT MODE (STABILIZED)' : 'DEFAULT MODE'}
          </span>
        </div>

        <div className="flex items-center gap-3 text-[11px] font-mono text-slate-400">
          <span>ONE EURO FILTER: ACTIVE</span>
          <span className="text-cyan-400">60.0 FPS</span>
        </div>
      </div>
    </div>
  );
};
