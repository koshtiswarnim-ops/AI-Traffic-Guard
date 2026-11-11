import React from 'react';
import { Focus, Eye } from 'lucide-react';

export default function LiveZoomPanel({ zoomData, vehicles = [] }) {
  const hasTarget = zoomData?.has_target && zoomData?.crop_b64;
  const activeList = vehicles || [];
  const inFrameCount = Math.max(hasTarget ? 1 : 0, activeList.length);
  const violationsNowCount = Math.max(
    zoomData?.is_violation ? 1 : 0,
    activeList.filter(v => v.is_violation).length
  );

  return (
    <div className="bg-[#0c1017] border border-[#1b2330] rounded-sm p-3 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#1b2330] pb-1.5 mb-2.5">
        <span className="text-amber-400 font-bold text-xs tracking-wide flex items-center space-x-1.5">
          <Focus size={13} className="text-amber-400" />
          <span>LIVE ZOOM</span>
        </span>
        <span className="text-[11px] text-[#94a3b8]">
          in frame: <span className="text-[#00e5ff] font-semibold">{inFrameCount}</span> | violations now: <span className="text-[#ff334b] font-semibold">{violationsNowCount}</span>
        </span>
      </div>

      {/* Target Preview Box */}
      <div className="relative w-full h-32 bg-[#080b0f] border border-[#1a2332] rounded-sm overflow-hidden flex items-center justify-center">
        {hasTarget ? (
          <div className="relative w-full h-full">
            <img 
              src={zoomData.crop_b64} 
              alt="Live Target Zoom" 
              className="w-full h-full object-cover"
            />
            
            {/* Crosshair Overlay */}
            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute top-2 left-2 w-3 h-3 border-t-2 border-l-2 border-[#00e5ff]" />
              <div className="absolute top-2 right-2 w-3 h-3 border-t-2 border-r-2 border-[#00e5ff]" />
              <div className="absolute bottom-2 left-2 w-3 h-3 border-l-2 border-b-2 border-[#00e5ff]" />
              <div className="absolute bottom-2 right-2 w-3 h-3 border-r-2 border-b-2 border-[#00e5ff]" />
            </div>

            {/* Target Telemetry Metadata Badge */}
            <div className="absolute bottom-1.5 left-2 right-2 flex items-center justify-between bg-[#0a0e14]/90 px-2 py-1 text-[10px] border border-[#1e2736] rounded">
              <span className="text-white font-bold">{zoomData.type} #{zoomData.id}</span>
              <span className={`font-semibold ${zoomData.is_violation ? 'text-[#ff334b]' : zoomData.status === 'CHECKING' ? 'text-amber-400' : 'text-[#00e676]'}`}>
                {zoomData.status}
              </span>
              <span className="text-[#00e5ff]">{Math.round((zoomData.conf || 0) * 100)}%</span>
              <span className="text-[#94a3b8]">{zoomData.timestamp || "00:00"}</span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center space-y-1.5 text-[#475569]">
            <Eye size={20} className="stroke-[1.5] text-[#334155]" />
            <span className="text-xs font-semibold tracking-widest text-[#475569]">
              WAITING FOR VEHICLE
            </span>
          </div>
        )}
      </div>

      {/* Sub-zoom audio/telemetry level meter */}
      <div className="mt-2 flex items-center space-x-1.5">
        <div className={`w-1.5 h-1.5 rounded-full ${hasTarget ? 'bg-[#00e5ff]' : 'bg-[#334155]'}`} />
        <div className="flex-1 h-0.5 bg-[#1b2330] relative overflow-hidden">
          <div 
            className={`h-full ${hasTarget ? 'w-3/4 bg-[#00e5ff]' : 'w-1/4 bg-[#334155]'} transition-all duration-300`} 
          />
        </div>
      </div>
    </div>
  );
}
