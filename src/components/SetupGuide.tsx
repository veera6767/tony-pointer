import React, { useState } from 'react';
import { Terminal, Copy, Check, ShieldCheck, Cpu, Monitor, Zap, HelpCircle } from 'lucide-react';

export const SetupGuide: React.FC = () => {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const copyCommand = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const steps = [
    {
      title: "1. Install Python 3.11",
      description: "Download Python 3.11 from python.org. During installation, make sure to check the box 'Add Python to PATH'.",
      command: "python --version",
      notes: "Verify in Command Prompt or PowerShell that Python 3.11+ is printed."
    },
    {
      title: "2. Install Python Dependencies",
      description: "Install MediaPipe Tasks, OpenCV, PySide6, Win32 bindings, and hotkey drivers:",
      command: "pip install -r requirements.txt",
      notes: "On first launch, Tony Pointer will automatically download the Google MediaPipe hand_landmarker.task model."
    },
    {
      title: "3. Run Tony Pointer",
      description: "Start the Stark Industries holographic desktop application:",
      command: "python main.py",
      notes: "The main window will appear with live camera preview, telemetry, and Arc-Reactor power button."
    },
    {
      title: "4. Build Standalone Single-File .EXE",
      description: "Compile Tony Pointer into a portable Windows executable that runs without Python installed:",
      command: "build_exe.bat",
      notes: "The standalone executable will be generated at dist\\TonyPointer.exe."
    }
  ];

  return (
    <div className="flex flex-col gap-6 bg-slate-950 border border-slate-800 rounded-lg p-6 shadow-xl text-slate-200">
      <div className="flex items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-lg font-bold font-hud text-cyan-400 tracking-wide">
            WINDOWS INSTALLATION & DEPLOYMENT PROTOCOL
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Step-by-step instructions for running with Python 3.11 and bundling into a standalone .exe
          </p>
        </div>
      </div>

      {/* Step Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {steps.map((step, idx) => (
          <div key={idx} className="flex flex-col justify-between p-4 rounded-lg bg-slate-900/60 border border-slate-800">
            <div>
              <div className="text-xs font-semibold text-cyan-400 font-hud tracking-wide mb-1">
                {step.title}
              </div>
              <p className="text-xs text-slate-300 leading-relaxed mb-3">
                {step.description}
              </p>
            </div>

            <div>
              <div className="flex items-center justify-between bg-black/60 border border-slate-800 rounded px-3 py-2 font-mono text-xs text-cyan-300">
                <span className="truncate">{step.command}</span>
                <button
                  onClick={() => copyCommand(step.command, idx)}
                  className="ml-2 text-slate-400 hover:text-cyan-300 cursor-pointer shrink-0"
                  title="Copy command"
                >
                  {copiedIndex === idx ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
              <p className="text-[11px] text-slate-500 font-mono mt-1.5">{step.notes}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Technical Excellence & Edge-Cases Accordion */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
        <div className="p-4 rounded-lg bg-slate-900/40 border border-slate-800">
          <div className="flex items-center gap-2 text-xs font-semibold text-cyan-400 font-hud mb-2">
            <ShieldCheck className="w-4 h-4" />
            ELEVATED APPS & GAMES
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Win32 <code className="text-cyan-300 font-mono">SendInput</code> handles mouse events directly at the hardware layer. If controlling elevated installer dialogs or full-screen games, run Command Prompt as Administrator.
          </p>
        </div>

        <div className="p-4 rounded-lg bg-slate-900/40 border border-slate-800">
          <div className="flex items-center gap-2 text-xs font-semibold text-cyan-400 font-hud mb-2">
            <Monitor className="w-4 h-4" />
            MULTI-MONITOR VIRTUAL DESKTOP
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            Tony Pointer queries <code className="text-cyan-300 font-mono">SM_XVIRTUALSCREEN</code> and <code className="text-cyan-300 font-mono">SM_CXVIRTUALSCREEN</code> so cursor coordinates traverse dual and triple monitors seamlessly.
          </p>
        </div>

        <div className="p-4 rounded-lg bg-slate-900/40 border border-slate-800">
          <div className="flex items-center gap-2 text-xs font-semibold text-cyan-400 font-hud mb-2">
            <Zap className="w-4 h-4" />
            AIR-TAP LOOKBACK ANCHOR
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            When you flex your index finger in the air, the historical buffer locks the click to where your finger rested 150ms earlier, ensuring you never miss small buttons or icons.
          </p>
        </div>
      </div>
    </div>
  );
};
