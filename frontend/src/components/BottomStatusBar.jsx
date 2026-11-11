import React from 'react';

export default function BottomStatusBar({
  viewMode = "DETECTION",
  fps = 30.1,
  processedFrames = 2165,
  totalFrames = 3636,
  activeCamera = "CAM 01 (MAIN HIGHWAY AR2)"
}) {
  return (
    <div className="w-full h-7 bg-[#0a0d13] border-t border-[#1b2330] flex items-center justify-between px-4 text-[11px] font-mono text-[#94a3b8] select-none flex-shrink-0">
      <div className="flex items-center space-x-4">
        <div>
          View: <span className="text-[#00e5ff] font-semibold">{viewMode}</span>
        </div>
        <span className="text-[#334155]">|</span>
        <div>
          FPS: <span className="text-emerald-400 font-semibold">{Number(fps || 0).toFixed(1)}</span>
        </div>
        <span className="text-[#334155]">|</span>
        <div>
          Frames: <span className="text-[#e2e8f0] font-semibold">{processedFrames} / {totalFrames}</span>
        </div>
      </div>

      <div className="flex items-center space-x-3">
        <div>
          Active: <span className="text-amber-400 font-semibold">{activeCamera}</span>
        </div>
        <span className="text-[#334155]">|</span>
        <div className="flex items-center space-x-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-emerald-400 font-semibold">SURVEILLANCE ENGAGED</span>
        </div>
      </div>
    </div>
  );
}
