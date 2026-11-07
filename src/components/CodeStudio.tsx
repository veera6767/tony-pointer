import React, { useState } from 'react';
import { POINTER_V_FILES, CodeFile } from '../data/codeFiles';
import { Download, Copy, Check, FileCode, Terminal, Sparkles, FolderArchive } from 'lucide-react';
import JSZip from 'jszip';

export const CodeStudio: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<CodeFile>(POINTER_V_FILES[0]);
  const [copied, setCopied] = useState(false);
  const [isZipping, setIsZipping] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(selectedFile.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadZip = async () => {
    try {
      setIsZipping(true);
      const zip = new JSZip();

      // Add all project files into pointer_v folder in zip
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
    } catch (err) {
      console.error("Failed to generate zip:", err);
    } finally {
      setIsZipping(false);
    }
  };

  return (
    <div className="flex flex-col bg-slate-950 border border-slate-800 rounded-lg overflow-hidden shadow-2xl">
      {/* Top Header with One-Click Zip Download */}
      <div className="flex flex-wrap items-center justify-between gap-4 px-4 py-3 bg-slate-900/90 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-1.5 rounded bg-cyan-950/70 border border-cyan-500/40 text-cyan-400">
            <FileCode className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-100 font-hud tracking-wide">
              POINTER V DESKTOP SOURCE REPOSITORY
            </h2>
            <p className="text-xs text-slate-400">
              Clean modular Python 3.12 architecture · Win32 SendInput · MediaPipe Tasks API
            </p>
          </div>
        </div>

        <button
          onClick={handleDownloadZip}
          disabled={isZipping}
          className="flex items-center gap-2 px-4 py-2 text-xs font-bold text-slate-950 bg-cyan-400 hover:bg-cyan-300 rounded-md shadow-[0_0_15px_rgba(0,229,255,0.4)] transition-all cursor-pointer disabled:opacity-50"
        >
          <FolderArchive className="w-4 h-4" />
          <span>{isZipping ? 'PACKING ZIP...' : 'DOWNLOAD COMPLETE PROJECT (.ZIP)'}</span>
        </button>
      </div>

      {/* Main Split: Left File Explorer, Right Code Viewer */}
      <div className="flex flex-col md:flex-row h-[620px] divide-y md:divide-y-0 md:divide-x divide-slate-800">
        {/* Left File List */}
        <div className="w-full md:w-64 bg-slate-950/70 overflow-y-auto p-2 flex flex-col gap-1">
          <div className="px-2 py-1 text-[11px] font-mono text-slate-500 tracking-wider">
            PROJECT MODULES
          </div>
          {POINTER_V_FILES.map((file) => {
            const isSelected = selectedFile.name === file.name;
            return (
              <button
                key={file.name}
                onClick={() => setSelectedFile(file)}
                className={`flex items-start gap-2.5 px-3 py-2 rounded text-left transition-colors cursor-pointer ${
                  isSelected
                    ? 'bg-cyan-950/60 text-cyan-300 border border-cyan-500/40'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                }`}
              >
                <span className="font-mono text-xs font-semibold shrink-0 mt-0.5">
                  {file.name.endsWith('.py') ? '🐍' : file.name.endsWith('.bat') ? '⚡' : '📄'}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-mono font-medium truncate">{file.name}</div>
                  <div className="text-[10px] text-slate-500 truncate">{file.description}</div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Right Code Display */}
        <div className="flex-1 flex flex-col bg-[#050811] overflow-hidden">
          {/* File Toolbar */}
          <div className="flex items-center justify-between px-4 py-2 bg-slate-950 border-b border-slate-800/80">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-cyan-400 font-semibold">{selectedFile.path}</span>
              <span className="text-slate-600">·</span>
              <span className="text-xs text-slate-400 truncate max-w-md">{selectedFile.description}</span>
            </div>

            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-1 text-xs font-mono rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 transition-colors cursor-pointer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied!' : 'Copy File'}</span>
            </button>
          </div>

          {/* Syntax Code Block */}
          <div className="flex-1 overflow-auto p-4 text-xs font-mono text-slate-200 leading-relaxed bg-[#050811] select-text">
            <pre className="tab-4">
              <code>{selectedFile.content}</code>
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};
