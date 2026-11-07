import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Camera, CameraOff, Video, RefreshCw, AlertTriangle, Eye, EyeOff } from 'lucide-react';

interface ActiveRegion {
  xMin: number;
  yMin: number;
  xMax: number;
  yMax: number;
}

interface WebcamSimulatorProps {
  activeRegion: ActiveRegion;
  onActiveRegionChange: (ar: ActiveRegion) => void;
  isModeActive: boolean;
  brushLocked: boolean;
  dwellProgress: number;
  currentGesture: string;
  fingerPos: { x: number; y: number };
  onFingerMove: (pos: { x: number; y: number }) => void;
  onAirTap: () => void;
}

export const WebcamSimulator: React.FC<WebcamSimulatorProps> = ({
  activeRegion,
  onActiveRegionChange,
  isModeActive,
  brushLocked,
  dwellProgress,
  currentGesture,
  fingerPos,
  onFingerMove,
  onAirTap,
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [streamActive, setStreamActive] = useState(false);
  const [camError, setCamError] = useState<string | null>(null);
  const [isLowLight, setIsLowLight] = useState(false);
  const [showSkeleton, setShowSkeleton] = useState(true);

  // Request live webcam
  const startCamera = async () => {
    try {
      setCamError(null);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: false,
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
        setStreamActive(true);
      }
    } catch (err: any) {
      console.warn("Webcam access note:", err);
      setCamError(err.name === 'NotAllowedError' ? 'Camera permission was denied' : 'No physical webcam detected or in use by another app');
      setStreamActive(false);
    }
  };

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((track) => track.stop());
      videoRef.current.srcObject = null;
    }
    setStreamActive(false);
  };

  useEffect(() => {
    startCamera();
    return () => stopCamera();
  }, []);

  // Main canvas HUD render loop
  useEffect(() => {
    let animId: number;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const render = () => {
      const w = canvas.width;
      const h = canvas.height;

      ctx.clearRect(0, 0, w, h);

      // 1. Draw Camera Feed or Sci-Fi Hologram Placeholder
      if (streamActive && videoRef.current && videoRef.current.readyState >= 2) {
        ctx.save();
        // Mirror horizontally
        ctx.translate(w, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(videoRef.current, 0, 0, w, h);
        ctx.restore();

        // Check luminance
        try {
          const sample = ctx.getImageData(w / 2 - 20, h / 2 - 20, 40, 40);
          let sum = 0;
          for (let i = 0; i < sample.data.length; i += 4) {
            sum += (sample.data[i] + sample.data[i + 1] + sample.data[i + 2]) / 3;
          }
          const avg = sum / (sample.data.length / 4);
          setIsLowLight(avg < 45);
        } catch {
          // ignore CORS/canvas taint issues if any
        }
      } else {
        // Sci-Fi Chamber Holographic Grid Background
        ctx.fillStyle = '#080d1a';
        ctx.fillRect(0, 0, w, h);

        ctx.strokeStyle = 'rgba(6, 182, 212, 0.08)';
        ctx.lineWidth = 1;
        for (let x = 0; x < w; x += 30) {
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, h);
          ctx.stroke();
        }
        for (let y = 0; y < h; y += 30) {
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(w, y);
          ctx.stroke();
        }
      }

      // Subtle dark vignette overlay
      const gradient = ctx.createRadialGradient(w / 2, h / 2, h * 0.35, w / 2, h / 2, h * 0.7);
      gradient.addColorStop(0, 'rgba(0,0,0,0)');
      gradient.addColorStop(1, 'rgba(5, 8, 17, 0.65)');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, w, h);

      // 2. Draw Active Region Bounding Box (~70% of frame)
      const ax1 = activeRegion.xMin * w;
      const ay1 = activeRegion.yMin * h;
      const ax2 = activeRegion.xMax * w;
      const ay2 = activeRegion.yMax * h;
      const aw = ax2 - ax1;
      const ah = ay2 - ay1;

      // Dashed boundary
      ctx.strokeStyle = 'rgba(245, 158, 11, 0.45)';
      ctx.lineWidth = 1;
      ctx.setLineDash([6, 6]);
      ctx.strokeRect(ax1, ay1, aw, ah);
      ctx.setLineDash([]);

      // Corner Brackets (Iron-Man HUD styling)
      const cLen = Math.min(22, aw / 8);
      ctx.strokeStyle = '#00e5ff';
      ctx.lineWidth = 2.5;

      // Top-Left
      ctx.beginPath();
      ctx.moveTo(ax1, ay1 + cLen);
      ctx.lineTo(ax1, ay1);
      ctx.lineTo(ax1 + cLen, ay1);
      ctx.stroke();

      // Top-Right
      ctx.beginPath();
      ctx.moveTo(ax2 - cLen, ay1);
      ctx.lineTo(ax2, ay1);
      ctx.lineTo(ax2, ay1 + cLen);
      ctx.stroke();

      // Bottom-Right
      ctx.beginPath();
      ctx.moveTo(ax2, ay2 - cLen);
      ctx.lineTo(ax2, ay2);
      ctx.lineTo(ax2 - cLen, ay2);
      ctx.stroke();

      // Bottom-Left
      ctx.beginPath();
      ctx.moveTo(ax1 + cLen, ay2);
      ctx.lineTo(ax1, ay2);
      ctx.lineTo(ax1, ay2 - cLen);
      ctx.stroke();

      // Active Region Label
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.fillStyle = '#00e5ff';
      ctx.fillText('ACTIVE REGION [70% SCREEN MAP]', ax1 + 6, ay1 + 16);

      // 3. Render Hand Skeleton & Reticle
      if (showSkeleton) {
        const fx = fingerPos.x * w;
        const fy = fingerPos.y * h;

        // Approximate Hand Skeleton Nodes centered around the index tip
        const palmX = fx - 25;
        const palmY = fy + 70;
        const wristX = palmX - 10;
        const wristY = palmY + 60;

        // Joints
        const joints = [
          { x: wristX, y: wristY }, // 0: Wrist
          { x: palmX - 25, y: palmY + 10 }, // 1: Thumb base
          { x: palmX - 35, y: palmY - 15 }, // 2: Thumb mid
          { x: palmX - 30, y: palmY - 40 }, // 4: Thumb tip
          { x: fx - 8, y: fy + 50 }, // 5: Index MCP
          { x: fx - 4, y: fy + 26 }, // 6: Index PIP
          { x: fx - 2, y: fy + 12 }, // 7: Index DIP
          { x: fx, y: fy },          // 8: Index TIP (Pointer Reticle)
          { x: fx + 16, y: fy + 52 }, // 9: Middle MCP
          { x: fx + 18, y: fy + 38 }, // 10: Middle PIP
          { x: fx + 20, y: fy + 48 }, // 12: Middle Tip (curled)
          { x: fx + 36, y: fy + 56 }, // 13: Ring MCP
          { x: fx + 38, y: fy + 68 }, // 16: Ring Tip (curled)
          { x: fx + 52, y: fy + 62 }, // 17: Pinky MCP
          { x: fx + 54, y: fy + 80 }, // 20: Pinky Tip (curled)
        ];

        // Draw bone links
        ctx.strokeStyle = brushLocked ? 'rgba(255, 87, 34, 0.7)' : 'rgba(0, 229, 255, 0.6)';
        ctx.lineWidth = 2;

        const connections = [
          [0, 1], [1, 2], [2, 3],
          [0, 4], [4, 5], [5, 6], [6, 7],
          [4, 8], [8, 9], [9, 10],
          [8, 11], [11, 12],
          [11, 13], [13, 14],
          [0, 13]
        ];

        connections.forEach(([i, j]) => {
          if (joints[i] && joints[j]) {
            ctx.beginPath();
            ctx.moveTo(joints[i].x, joints[i].y);
            ctx.lineTo(joints[j].x, joints[j].y);
            ctx.stroke();
          }
        });

        // Draw joint points
        joints.forEach((pt, idx) => {
          if (idx !== 7) {
            ctx.fillStyle = idx === 3 ? '#ffb300' : '#e2e8f0';
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, idx === 3 ? 4 : 3, 0, Math.PI * 2);
            ctx.fill();
          }
        });

        // Landmark 8: Index Fingertip - Primary Stark Reticle!
        const reticleColor = brushLocked ? '#ff5722' : '#00e5ff';
        ctx.strokeStyle = reticleColor;
        ctx.fillStyle = brushLocked ? 'rgba(255, 87, 34, 0.8)' : 'rgba(0, 229, 255, 0.2)';
        ctx.lineWidth = 2;

        // Center dot & ring
        ctx.beginPath();
        ctx.arc(fx, fy, 14, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fill();

        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(fx, fy, 2.5, 0, Math.PI * 2);
        ctx.fill();

        // Dwell Arc Sweep
        if (dwellProgress > 0 && !brushLocked) {
          ctx.strokeStyle = '#ffb300';
          ctx.lineWidth = 3.5;
          ctx.beginPath();
          const startAngle = -Math.PI / 2;
          const endAngle = startAngle + (dwellProgress * Math.PI * 2);
          ctx.arc(fx, fy, 22, startAngle, endAngle);
          ctx.stroke();
        }
      }

      // 4. In-Chamber Telemetry Header
      ctx.font = '11px "JetBrains Mono", monospace';
      ctx.fillStyle = brushLocked ? '#ff5722' : '#00e5ff';
      ctx.fillText(
        `GESTURE: ${currentGesture} ${brushLocked ? '· [BRUSH LOCKED]' : ''}`,
        14,
        22
      );

      ctx.fillStyle = '#94a3b8';
      ctx.fillText(
        `INDEX TIP: [${(fingerPos.x * 100).toFixed(1)}%, ${(fingerPos.y * 100).toFixed(1)}%]`,
        14,
        38
      );

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [streamActive, activeRegion, brushLocked, dwellProgress, currentGesture, fingerPos, showSkeleton]);

  // Handle canvas mouse interaction to test gestures without physical webcam
  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
    onFingerMove({ x, y });
  };

  return (
    <div className="flex flex-col bg-slate-950/90 border border-slate-800 rounded-lg p-3 overflow-hidden shadow-xl">
      {/* Hidden live video element for webcam frame ingestion */}
      <video ref={videoRef} className="hidden" playsInline muted autoPlay />

      {/* Top Bar with Camera Controls */}
      <div className="flex items-center justify-between gap-4 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-300 font-hud tracking-wide">
            WEBCAM HUD
          </span>
          <span className="text-[11px] font-mono text-slate-400">
            {streamActive ? 'FEED: 60 FPS' : 'SIMULATION MODE'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {isLowLight && (
            <span className="flex items-center gap-1 text-[11px] font-mono text-amber-400">
              <AlertTriangle className="w-3.5 h-3.5" />
              Low Light
            </span>
          )}

          <button
            onClick={() => setShowSkeleton(!showSkeleton)}
            className="p-1 rounded text-slate-400 hover:text-cyan-400 transition-colors cursor-pointer"
            title={showSkeleton ? 'Hide Landmarks' : 'Show Landmarks'}
          >
            {showSkeleton ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
          </button>

          {streamActive ? (
            <button
              onClick={stopCamera}
              className="flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono text-slate-400 hover:text-rose-400 border border-slate-800 rounded transition-colors cursor-pointer"
            >
              <CameraOff className="w-3 h-3" />
              Pause
            </button>
          ) : (
            <button
              onClick={startCamera}
              className="flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono text-cyan-400 hover:bg-cyan-950/40 border border-cyan-800/80 rounded transition-colors cursor-pointer"
            >
              <Camera className="w-3 h-3" />
              Start Webcam
            </button>
          )}
        </div>
      </div>

      {/* Main Interactive HUD Canvas */}
      <div className="relative aspect-[4/3] w-full rounded border border-slate-800 bg-slate-950 overflow-hidden cursor-crosshair">
        <canvas
          ref={canvasRef}
          width={640}
          height={480}
          onMouseMove={handleCanvasMouseMove}
          onClick={onAirTap}
          className="w-full h-full object-cover"
        />

        {camError && !streamActive && (
          <div className="absolute inset-x-2 bottom-2 bg-slate-900/90 border border-amber-500/30 rounded p-2 text-center text-xs text-amber-200">
            {camError} · Move mouse inside this chamber to test hand gestures interactively!
          </div>
        )}
      </div>

      {/* Gesture Simulator Test Bar */}
      <div className="mt-2.5 pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs">
        <span className="text-slate-400 font-mono text-[11px]">
          Tap anywhere in feed to trigger <span className="text-cyan-400">Air Tap</span>
        </span>
        <button
          onClick={onAirTap}
          className="px-2.5 py-1 text-xs font-semibold text-cyan-300 bg-cyan-950/60 hover:bg-cyan-900 border border-cyan-500/40 rounded transition-colors cursor-pointer"
        >
          Simulate Air Double-Tap
        </button>
      </div>
    </div>
  );
};
