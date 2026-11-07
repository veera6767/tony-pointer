import React from 'react';
import { Sliders, Save, RefreshCw, Eye, Sparkles } from 'lucide-react';

interface ActiveRegion {
  xMin: number;
  yMin: number;
  xMax: number;
  yMax: number;
}

interface SettingsStudioProps {
  activeRegion: ActiveRegion;
  onActiveRegionChange: (ar: ActiveRegion) => void;
  sensitivity: number;
  onSensitivityChange: (s: number) => void;
  minCutoff: number;
  onMinCutoffChange: (v: number) => void;
  beta: number;
  onBetaChange: (v: number) => void;
  doubleTapWindow: number;
  onDoubleTapWindowChange: (v: number) => void;
  dwellTime: number;
  onDwellTimeChange: (v: number) => void;
  singleClickEnabled: boolean;
  onToggleSingleClick: (v: boolean) => void;
  // Air Keyboard Settings
  symbolsEnabled?: boolean;
  onToggleSymbolsEnabled?: (v: boolean) => void;
  dimInactiveZone?: boolean;
  onToggleDimInactiveZone?: (v: boolean) => void;
  thumbSpace?: boolean;
  onToggleThumbSpace?: (v: boolean) => void;
  swipeSensitivity?: number;
  onSwipeSensitivityChange?: (v: number) => void;
}

export const SettingsStudio: React.FC<SettingsStudioProps> = ({
  activeRegion,
  onActiveRegionChange,
  sensitivity,
  onSensitivityChange,
  minCutoff,
  onMinCutoffChange,
  beta,
  onBetaChange,
  doubleTapWindow,
  onDoubleTapWindowChange,
  dwellTime,
  onDwellTimeChange,
  singleClickEnabled,
  onToggleSingleClick,
  symbolsEnabled = true,
  onToggleSymbolsEnabled,
  dimInactiveZone = true,
  onToggleDimInactiveZone,
  thumbSpace = true,
  onToggleThumbSpace,
  swipeSensitivity = 1.0,
  onSwipeSensitivityChange,
}) => {
  const resetDefaults = () => {
    onActiveRegionChange({ xMin: 0.15, yMin: 0.15, xMax: 0.85, yMax: 0.85 });
    onSensitivityChange(1.0);
    onMinCutoffChange(1.0);
    onBetaChange(0.007);
    onDoubleTapWindowChange(500);
    onDwellTimeChange(0.60);
    onToggleSingleClick(true);
    if (onToggleSymbolsEnabled) onToggleSymbolsEnabled(true);
    if (onToggleDimInactiveZone) onToggleDimInactiveZone(true);
    if (onToggleThumbSpace) onToggleThumbSpace(true);
    if (onSwipeSensitivityChange) onSwipeSensitivityChange(1.0);
  };

  return (
    <div className="flex flex-col gap-6 bg-slate-950 border border-slate-800 rounded-lg p-6 shadow-xl text-slate-200">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-lg font-bold font-hud text-cyan-400 tracking-wide">
            POINTER V CONFIGURATION ENGINE
          </h2>
          <p className="text-xs text-slate-400">
            Real-time threshold calibration for One Euro filters, air-tap detectors, and active regions
          </p>
        </div>

        <button
          onClick={resetDefaults}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 transition-colors cursor-pointer"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Reset Defaults</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Panel 1: One Euro Filter */}
        <div className="flex flex-col gap-4 p-4 rounded-lg bg-slate-900/40 border border-slate-800">
          <div className="text-xs font-semibold text-cyan-400 font-hud tracking-wide">
            1. ONE EURO FILTER PARAMETERS
          </div>

          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-300">Min Cutoff (fc_min):</span>
              <span className="text-cyan-400">{minCutoff.toFixed(2)} Hz</span>
            </div>
            <input
              type="range"
              min="0.1"
              max="4.0"
              step="0.05"
              value={minCutoff}
              onChange={(e) => onMinCutoffChange(Number(e.target.value))}
              className="accent-cyan-400 cursor-pointer"
            />
            <span className="text-[10px] text-slate-500 font-mono">Lower values eliminate tremor at rest</span>
          </div>

          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-300">Beta Speed Coefficient:</span>
              <span className="text-cyan-400">{beta.toFixed(4)}</span>
            </div>
            <input
              type="range"
              min="0.001"
              max="0.03"
              step="0.001"
              value={beta}
              onChange={(e) => onBetaChange(Number(e.target.value))}
              className="accent-cyan-400 cursor-pointer"
            />
            <span className="text-[10px] text-slate-500 font-mono">Higher values adapt instantly to fast flicks</span>
          </div>

          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-300">Pointer Sensitivity:</span>
              <span className="text-cyan-400">{sensitivity.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="2.5"
              step="0.1"
              value={sensitivity}
              onChange={(e) => onSensitivityChange(Number(e.target.value))}
              className="accent-cyan-400 cursor-pointer"
            />
          </div>
        </div>

        {/* Panel 2: Gestures */}
        <div className="flex flex-col gap-4 p-4 rounded-lg bg-slate-900/40 border border-slate-800">
          <div className="text-xs font-semibold text-cyan-400 font-hud tracking-wide">
            2. AIR-TAP & BRUSH GESTURES
          </div>

          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-300">Double-Tap Window:</span>
              <span className="text-cyan-400">{doubleTapWindow} ms</span>
            </div>
            <input
              type="range"
              min="250"
              max="750"
              step="25"
              value={doubleTapWindow}
              onChange={(e) => onDoubleTapWindowChange(Number(e.target.value))}
              className="accent-cyan-400 cursor-pointer"
            />
            <span className="text-[10px] text-slate-500 font-mono">Max duration between 2 air-taps for double click</span>
          </div>

          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-300">Brush Lock Dwell Hold:</span>
              <span className="text-cyan-400">{dwellTime.toFixed(2)} s</span>
            </div>
            <input
              type="range"
              min="0.30"
              max="1.20"
              step="0.05"
              value={dwellTime}
              onChange={(e) => onDwellTimeChange(Number(e.target.value))}
              className="accent-cyan-400 cursor-pointer"
            />
            <span className="text-[10px] text-slate-500 font-mono">Holding index finger stationary locks left click</span>
          </div>

          <div className="flex items-center justify-between pt-2">
            <span className="text-xs font-mono text-slate-300">Single Air-Tap as Left Click:</span>
            <input
              type="checkbox"
              checked={singleClickEnabled}
              onChange={(e) => onToggleSingleClick(e.target.checked)}
              className="accent-cyan-400 w-4 h-4 cursor-pointer"
            />
          </div>
        </div>

        {/* Panel 3: Active Region Dimensions */}
        <div className="flex flex-col gap-4 p-4 rounded-lg bg-slate-900/40 border border-slate-800">
          <div className="text-xs font-semibold text-cyan-400 font-hud tracking-wide">
            3. ACTIVE REGION FRAME MAPPING
          </div>

          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-300">Horizontal Active Span:</span>
              <span className="text-cyan-400">{(activeRegion.xMin * 100).toFixed(0)}% .. {(activeRegion.xMax * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min="0.05"
              max="0.35"
              step="0.01"
              value={activeRegion.xMin}
              onChange={(e) =>
                onActiveRegionChange({
                  ...activeRegion,
                  xMin: Number(e.target.value),
                  xMax: 1 - Number(e.target.value),
                })
              }
              className="accent-cyan-400 cursor-pointer"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-300">Vertical Active Span:</span>
              <span className="text-cyan-400">{(activeRegion.yMin * 100).toFixed(0)}% .. {(activeRegion.yMax * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min="0.05"
              max="0.35"
              step="0.01"
              value={activeRegion.yMin}
              onChange={(e) =>
                onActiveRegionChange({
                  ...activeRegion,
                  yMin: Number(e.target.value),
                  yMax: 1 - Number(e.target.value),
                })
              }
              className="accent-cyan-400 cursor-pointer"
            />
          </div>

          <div className="p-2.5 rounded bg-black/40 border border-slate-800 font-mono text-[11px] text-slate-400 leading-normal">
            Moving your finger within this boundary spans 100% of your multi-monitor desktop without arm strain.
          </div>
        </div>

        {/* Panel 4: Air Keyboard & Symbols Panel Tuning */}
        <div className="flex flex-col gap-4 p-4 rounded-lg bg-slate-900/40 border border-slate-800">
          <div className="text-xs font-semibold text-purple-400 font-hud tracking-wide">
            4. AIR KEYBOARD & SYMBOLS
          </div>

          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-300">Docked Symbols Panel:</span>
            <input
              type="checkbox"
              checked={symbolsEnabled}
              onChange={(e) => onToggleSymbolsEnabled && onToggleSymbolsEnabled(e.target.checked)}
              className="accent-purple-400 w-4 h-4 cursor-pointer"
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-300">Dim Inactive Zone (40%):</span>
            <input
              type="checkbox"
              checked={dimInactiveZone}
              onChange={(e) => onToggleDimInactiveZone && onToggleDimInactiveZone(e.target.checked)}
              className="accent-cyan-400 w-4 h-4 cursor-pointer"
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-300">Thumb Tap as Space:</span>
            <input
              type="checkbox"
              checked={thumbSpace}
              onChange={(e) => onToggleThumbSpace && onToggleThumbSpace(e.target.checked)}
              className="accent-amber-400 w-4 h-4 cursor-pointer"
            />
          </div>

          <div className="flex flex-col gap-1.5 pt-1">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-300">Swipe Sensitivity:</span>
              <span className="text-purple-400">{swipeSensitivity.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="2.0"
              step="0.1"
              value={swipeSensitivity}
              onChange={(e) => onSwipeSensitivityChange && onSwipeSensitivityChange(Number(e.target.value))}
              className="accent-purple-400 cursor-pointer"
            />
            <span className="text-[10px] text-slate-500 font-mono">Whole-hand swipe distance normalized by hand size</span>
          </div>

          <div className="p-2.5 rounded bg-black/40 border border-purple-900/40 font-mono text-[11px] text-purple-300 leading-normal">
            Shortcuts: Open palm (0.5s) to launch, Ctrl+Alt+K, Ctrl+Alt+S (zone toggle), Fist/Esc to exit.
          </div>
        </div>
      </div>
    </div>
  );
};
