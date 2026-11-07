import React from 'react';
import { Power } from 'lucide-react';

interface ArcReactorButtonProps {
  isActive: boolean;
  onToggle: () => void;
  size?: number;
}

export const ArcReactorButton: React.FC<ArcReactorButtonProps> = ({
  isActive,
  onToggle,
  size = 140,
}) => {
  return (
    <button
      onClick={onToggle}
      className="group relative flex items-center justify-center rounded-2xl transition-all duration-300 active:scale-95 focus:outline-none cursor-pointer"
      style={{ width: size, height: size }}
      title={isActive ? "Deactivate Pointer V (Ctrl+Alt+Space)" : "Activate Pointer V (Ctrl+Alt+Space)"}
      aria-label="Toggle Pointer V Tracking"
    >
      {/* Background card with subtle border */}
      <div
        className={`absolute inset-0 rounded-2xl border transition-all duration-300 ${
          isActive
            ? 'bg-[#11151C] border-[#2F7BFF]/60 shadow-[0_0_24px_rgba(47,123,255,0.25)]'
            : 'bg-[#11151C]/80 border-[#232A36]'
        }`}
      />

      {/* Subtle corner tick lines */}
      <div className="absolute top-2 left-2 w-2 h-2 border-t-2 border-l-2 border-[#2F7BFF]/50 pointer-events-none" />
      <div className="absolute top-2 right-2 w-2 h-2 border-t-2 border-r-2 border-[#2F7BFF]/50 pointer-events-none" />
      <div className="absolute bottom-2 left-2 w-2 h-2 border-b-2 border-l-2 border-[#2F7BFF]/50 pointer-events-none" />
      <div className="absolute bottom-2 right-2 w-2 h-2 border-b-2 border-r-2 border-[#2F7BFF]/50 pointer-events-none" />

      {/* Inner circular trigger */}
      <div
        className={`relative flex flex-col items-center justify-center rounded-xl transition-all duration-300 ${
          isActive
            ? 'w-[75%] h-[75%] bg-[#171C25] border border-[#2F7BFF]'
            : 'w-[75%] h-[75%] bg-[#171C25]/60 border border-[#232A36]'
        }`}
      >
        <Power
          className={`w-7 h-7 mb-1 transition-colors duration-300 ${
            isActive ? 'text-[#2F7BFF]' : 'text-slate-500 group-hover:text-slate-300'
          }`}
        />
        <span
          className={`text-xs font-semibold tracking-wider transition-colors ${
            isActive ? 'text-[#E6EAF2]' : 'text-slate-400'
          }`}
        >
          {isActive ? 'ACTIVE' : 'PAUSED'}
        </span>
        <span className="text-[10px] font-mono text-slate-500 mt-0.5">
          {isActive ? '60 FPS' : 'STANDBY'}
        </span>
      </div>
    </button>
  );
};
