import React from 'react';

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
      className="group relative flex items-center justify-center rounded-full transition-transform active:scale-95 focus:outline-none cursor-pointer"
      style={{ width: size, height: size }}
      title={isActive ? "Deactivate Tony Pointer Mode" : "Engage Tony Pointer Mode"}
      aria-label="Toggle Tony Pointer Mode"
    >
      {/* Outer Glow Halo */}
      <div
        className={`absolute inset-0 rounded-full transition-all duration-500 pointer-events-none ${
          isActive
            ? 'bg-cyan-500/25 blur-xl animate-pulse'
            : 'bg-slate-700/10 blur-md'
        }`}
      />

      {/* Outer Metallic Ring */}
      <div
        className={`absolute inset-0 rounded-full border-2 transition-colors duration-300 ${
          isActive ? 'border-cyan-400 bg-slate-950/90' : 'border-slate-700 bg-slate-950/70'
        }`}
      />

      {/* Rotating Mechanical Coils (10 segments) */}
      <svg
        className={`absolute inset-0 w-full h-full pointer-events-none transition-transform duration-1000 ${
          isActive ? 'animate-[spin_20s_linear_infinite]' : ''
        }`}
        viewBox="0 0 100 100"
      >
        {[...Array(10)].map((_, i) => {
          const angle = (i * 36) * (Math.PI / 180);
          const x1 = 50 + Math.cos(angle) * 35;
          const y1 = 50 + Math.sin(angle) * 35;
          const x2 = 50 + Math.cos(angle) * 44;
          const y2 = 50 + Math.sin(angle) * 44;
          return (
            <line
              key={i}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke={isActive ? '#00e5ff' : '#475569'}
              strokeWidth="2.8"
              strokeLinecap="round"
              opacity={isActive ? 0.9 : 0.4}
            />
          );
        })}
      </svg>

      {/* Middle Concentric Ring */}
      <div
        className={`absolute rounded-full border transition-all duration-300 ${
          isActive
            ? 'border-cyan-400/80 w-[68%] h-[68%] shadow-[inset_0_0_12px_rgba(0,229,255,0.4)]'
            : 'border-slate-700/60 w-[68%] h-[68%]'
        }`}
      />

      {/* Core Repulsor / Arc Reactor Node */}
      <div
        className={`relative flex flex-col items-center justify-center rounded-full transition-all duration-500 ${
          isActive
            ? 'w-[48%] h-[48%] bg-cyan-400/20 border-2 border-cyan-300 shadow-[0_0_20px_rgba(0,229,255,0.8)]'
            : 'w-[48%] h-[48%] bg-slate-900 border border-slate-700'
        }`}
      >
        <span
          className={`font-hud text-xs font-bold tracking-wider transition-colors ${
            isActive ? 'text-white drop-shadow-[0_0_8px_rgba(0,229,255,1)]' : 'text-slate-400'
          }`}
        >
          {isActive ? 'ONLINE' : 'ENGAGE'}
        </span>
        <span className="text-[9px] font-mono tracking-tight text-cyan-400/80">
          {isActive ? 'SYS READY' : 'CLICK'}
        </span>
      </div>
    </button>
  );
};
