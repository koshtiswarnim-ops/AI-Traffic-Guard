import React, { useRef, useEffect, useState, useCallback } from 'react';
import {
  Play, Pause, RefreshCw, Camera, Maximize2,
  Crosshair, AlertTriangle, Layers, WifiOff
} from 'lucide-react';

export default function CctvPlayer({
  telemetry,
  cameraConfig,
  isPaused,
  streamKey,
  wsConnected,
  onTogglePause,
  onReconnect,
  onOpenSourceModal,
  onUpdateZone,
  operatingMode
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);

  const [isCalibrating, setIsCalibrating] = useState(false);
  const [showHudOverlay, setShowHudOverlay] = useState(true);
  const [streamError, setStreamError] = useState(false);
  const [polygonPts, setPolygonPts] = useState([
    [40, 480],
    [1310, 480],
    [1260, 335],
    [80, 335]
  ]);
  const [activeHandle, setActiveHandle] = useState(null);

  const REF_W = 1350;
  const REF_H = 756;

  // Reset error flag whenever streamKey updates
  useEffect(() => {
    setStreamError(false);
  }, [streamKey]);

  // Auto-sync polygon from telemetry when not actively dragging
  useEffect(() => {
    if (telemetry?.zone_polygon && !isCalibrating && activeHandle === null) {
      setPolygonPts(telemetry.zone_polygon);
    }
  }, [telemetry?.zone_polygon, isCalibrating, activeHandle]);

  // Live clock OSD
  const [clockStr, setClockStr] = useState("");
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const month = String(now.getMonth() + 1).padStart(2, '0');
      const day = String(now.getDate()).padStart(2, '0');
      const year = now.getFullYear();
      const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
      const dayName = days[now.getDay()];
      const timePart = now.toTimeString().split(' ')[0];
      setClockStr(`${month}-${day}-${year} ${dayName} ${timePart}`);
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
  };

  // Determine whether current feed already has baked-in demo overlays
  const isPreAnnotated = Boolean(telemetry?.is_pre_annotated);
  const shouldDrawBoxes = showHudOverlay && (!isPreAnnotated || isCalibrating);

  // Canvas Overlay Drawing Loop
  const drawOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    const scaleX = width / REF_W;
    const scaleY = height / REF_H;

    // 1. Draw Check Zone Polygon (always visible in calibration mode or on raw feeds/HUD enabled)
    if ((shouldDrawBoxes || isCalibrating) && polygonPts && polygonPts.length >= 4) {
      ctx.beginPath();
      const p0 = polygonPts[0];
      ctx.moveTo(p0[0] * scaleX, p0[1] * scaleY);
      for (let i = 1; i < polygonPts.length; i++) {
        ctx.lineTo(polygonPts[i][0] * scaleX, polygonPts[i][1] * scaleY);
      }
      ctx.closePath();

      ctx.fillStyle = isCalibrating ? 'rgba(234, 179, 8, 0.22)' : 'rgba(234, 179, 8, 0.14)';
      ctx.fill();

      ctx.lineWidth = isCalibrating ? 3 : 2;
      ctx.strokeStyle = '#eab308';
      ctx.stroke();

      const labelX = (polygonPts[3][0] * scaleX) + 10;
      const labelY = (polygonPts[3][1] * scaleY) + 20;
      ctx.font = 'bold 12px "JetBrains Mono", monospace';
      ctx.fillStyle = '#eab308';
      ctx.fillText('CHECK ZONE', labelX, labelY);

      if (isCalibrating) {
        polygonPts.forEach((pt, idx) => {
          const hx = pt[0] * scaleX;
          const hy = pt[1] * scaleY;
          ctx.beginPath();
          ctx.arc(hx, hy, 7, 0, Math.PI * 2);
          ctx.fillStyle = idx === activeHandle ? '#ff334b' : '#38bdf8';
          ctx.fill();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 2;
          ctx.stroke();

          ctx.fillStyle = '#ffffff';
          ctx.font = 'bold 10px monospace';
          ctx.fillText(`P${idx + 1}`, hx + 10, hy - 5);
        });
      }
    }

    // 2. Draw YOLO Bounding Boxes & Tracking IDs
    if (shouldDrawBoxes) {
      const vehicles = telemetry?.vehicles || [];
      vehicles.forEach(v => {
        const bbox = v.bbox;
        if (!bbox || bbox.length < 4) return;

        const bx1 = bbox[0] * scaleX;
        const by1 = bbox[1] * scaleY;
        const bx2 = bbox[2] * scaleX;
        const by2 = bbox[3] * scaleY;
        const bw = bx2 - bx1;
        const bh = by2 - by1;

        let boxColor = '#94a3b8';
        if (v.state === 'CHECKING') {
          boxColor = '#eab308';
        } else if (v.state === 'PASSED') {
          boxColor = v.is_violation ? '#ff334b' : '#00e676';
        }

        ctx.lineWidth = 2;
        ctx.strokeStyle = boxColor;
        ctx.strokeRect(bx1, by1, bw, bh);

        const labelText = `${v.type} #${v.id}${v.status ? ` ${v.status}` : ''}`;
        ctx.font = 'bold 11px "JetBrains Mono", monospace';
        const textWidth = ctx.measureText(labelText).width;

        ctx.fillStyle = 'rgba(10, 14, 20, 0.88)';
        ctx.fillRect(bx1, Math.max(0, by1 - 19), textWidth + 12, 19);
        ctx.fillStyle = boxColor;
        ctx.fillText(labelText, bx1 + 6, Math.max(13, by1 - 5));

        if (v.head_bbox) {
          const hx1 = v.head_bbox[0] * scaleX;
          const hy1 = v.head_bbox[1] * scaleY;
          const hx2 = v.head_bbox[2] * scaleX;
          const hy2 = v.head_bbox[3] * scaleY;
          ctx.lineWidth = 1.5;
          ctx.strokeStyle = v.is_violation ? '#ff334b' : '#00e676';
          ctx.strokeRect(hx1, hy1, hx2 - hx1, hy2 - hy1);
        }
      });

      // 3. Draw Floating Toast Notification Banners (max 2 stacked)
      const toasts = telemetry?.toasts || [];
      const toastStartY = height - 86;

      toasts.slice(-2).forEach((toast, idx) => {
        const bannerY = toastStartY + (idx * 36);
        const bannerX = width * 0.22;
        ctx.font = 'bold 13px "JetBrains Mono", monospace';
        const bannerW = Math.max(360, ctx.measureText(toast.text).width + 28);
        const bannerH = 30;

        const borderColor = toast.is_violation ? '#ff334b' : '#00e676';
        const bgColor = toast.is_violation ? 'rgba(127, 29, 29, 0.82)' : 'rgba(6, 78, 59, 0.82)';

        ctx.fillStyle = bgColor;
        ctx.fillRect(bannerX, bannerY, bannerW, bannerH);

        ctx.lineWidth = 2;
        ctx.strokeStyle = borderColor;
        ctx.strokeRect(bannerX, bannerY, bannerW, bannerH);

        ctx.fillStyle = '#ffffff';
        ctx.fillText(toast.text, bannerX + 14, bannerY + 20);
      });
    }
  }, [polygonPts, isCalibrating, shouldDrawBoxes, activeHandle, telemetry]);

  useEffect(() => {
    let animId;
    const render = () => {
      drawOverlay();
      animId = requestAnimationFrame(render);
    };
    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [drawOverlay]);

  useEffect(() => {
    const handleResize = () => {
      if (canvasRef.current && containerRef.current) {
        canvasRef.current.width = containerRef.current.clientWidth;
        canvasRef.current.height = containerRef.current.clientHeight;
      }
    };
    handleResize();
    const ro = new ResizeObserver(handleResize);
    if (containerRef.current) ro.observe(containerRef.current);
    window.addEventListener('resize', handleResize);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  const handleMouseDown = (e) => {
    if (!isCalibrating || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const scaleX = canvasRef.current.width / REF_W;
    const scaleY = canvasRef.current.height / REF_H;

    polygonPts.forEach((pt, idx) => {
      const hx = pt[0] * scaleX;
      const hy = pt[1] * scaleY;
      if (Math.hypot(mx - hx, my - hy) < 16) {
        setActiveHandle(idx);
      }
    });
  };

  const handleMouseMove = (e) => {
    if (!isCalibrating || activeHandle === null || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const scaleX = canvasRef.current.width / REF_W;
    const scaleY = canvasRef.current.height / REF_H;

    const newX = Math.round(Math.max(0, Math.min(REF_W, mx / scaleX)));
    const newY = Math.round(Math.max(0, Math.min(REF_H, my / scaleY)));

    const updated = [...polygonPts];
    updated[activeHandle] = [newX, newY];
    setPolygonPts(updated);
  };

  const handleMouseUp = () => {
    if (activeHandle !== null) {
      setActiveHandle(null);
      if (onUpdateZone) {
        onUpdateZone(polygonPts);
      }
    }
  };

  const camStatus = telemetry?.status || "ONLINE";
  const isOffline = streamError || camStatus.includes("OFFLINE") || camStatus.includes("ERROR");

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full bg-[#080b0f] overflow-hidden flex items-center justify-center select-none"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      {/* Backend Synchronized Live MJPEG Stream (Supports MP4, Upload, Webcam & RTSP) */}
      <img
        key={streamKey}
        src={`/api/stream/video_feed?t=${streamKey}`}
        alt="Live CCTV Surveillance Feed"
        onLoad={() => setStreamError(false)}
        onError={() => setStreamError(true)}
        className="w-full h-full object-fill"
      />

      {/* Stream Error / Offline Fallback Overlay */}
      {isOffline && (
        <div className="absolute inset-0 bg-[#080b0f]/85 flex flex-col items-center justify-center space-y-3 z-10 font-mono">
          <WifiOff size={36} className="text-[#ff334b]" />
          <div className="text-sm font-bold text-[#ff334b] tracking-wider">
            {camStatus !== "ONLINE" ? camStatus : "VIDEO STREAM DISCONNECTED"}
          </div>
          <button
            onClick={onReconnect}
            className="px-4 py-1.5 bg-amber-500 hover:bg-amber-400 text-black text-xs font-bold uppercase tracking-wider rounded-sm transition-colors"
          >
            Reconnect Stream
          </button>
        </div>
      )}

      {/* CRT Scanline Overlay Effect */}
      <div className="absolute inset-0 scanlines pointer-events-none" />

      {/* Canvas Layer for HUD / Bounding Boxes / Polygon */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full pointer-events-auto"
      />

      {/* Top CCTV OSD Bar */}
      <div className="absolute top-2 left-3 right-3 flex items-center justify-between text-xs font-mono text-[#e2e8f0] pointer-events-none">
        <div className="flex items-center space-x-2.5 bg-[#080b0f]/90 px-2.5 py-1 border border-[#1f2937] rounded-sm shadow">
          <span className="font-bold text-amber-400">{cameraConfig?.id || "CAM 01"}</span>
          <span className="text-[#475569]">|</span>
          <span className="text-[#00e5ff] font-semibold">DETECTION</span>
          <span className="text-[#475569]">|</span>
          <span className="flex items-center space-x-1">
            <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-[#ff334b] animate-pulse' : 'bg-amber-400'}`} />
            <span className={wsConnected ? 'text-[#ff334b] font-bold' : 'text-amber-400 font-bold'}>
              {isPaused ? 'PAUSED' : wsConnected ? 'LIVE' : 'SYNC'}
            </span>
          </span>
          <span className="text-[#475569]">|</span>
          <span className="text-emerald-400 tabular-nums">FPS: {Number(telemetry?.fps ?? 0).toFixed(1)}</span>
          <span className="text-[#475569]">|</span>
          <span className="text-[#94a3b8] tabular-nums">{clockStr}</span>
        </div>

        {/* Operating Mode Indicator */}
        <div className="flex items-center space-x-2 bg-[#080b0f]/90 px-2.5 py-1 border border-[#1f2937] rounded-sm shadow">
          <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
          <span className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider">
            {operatingMode || "LIVE AI (YOLOv8 + BoT-SORT)"}
          </span>
        </div>
      </div>

      {/* Bottom Technical OSD (only drawn when not pre-annotated so text stays crisp) */}
      {!isPreAnnotated && (
        <>
          <div className="absolute bottom-3 left-4 text-[10px] font-mono text-[#ff4d4f] space-y-0.5 leading-tight pointer-events-none bg-[#080b0f]/60 px-2 py-1 rounded-sm">
            <div>User Name: admin</div>
            <div>IP Address: 10.0.0.28</div>
            <div>MAC Address: 00-E0-4C-68-02-85</div>
          </div>

          <div className="absolute bottom-3 right-4 text-[11px] font-mono text-[#cbd5e1] pointer-events-none bg-[#080b0f]/60 px-2 py-0.5 rounded-sm">
            (c) {cameraConfig?.location || "Ayesha Buni Sh Faisal AR2"}
          </div>
        </>
      )}

      {/* Surveillance Controls Bar */}
      <div className="absolute top-12 right-3 flex items-center space-x-1 bg-[#0b0f17]/90 backdrop-blur-sm border border-[#1e2736] p-1 rounded-sm shadow-xl z-20 opacity-75 hover:opacity-100 transition-opacity">
        <button
          onClick={onTogglePause}
          title={isPaused ? "Resume Video" : "Pause Video"}
          className="p-1.5 hover:bg-[#1a2332] text-[#94a3b8] hover:text-[#00e5ff] rounded transition-colors"
        >
          {isPaused ? <Play size={14} /> : <Pause size={14} />}
        </button>

        <button
          onClick={onReconnect}
          title="Reconnect Stream"
          className="p-1.5 hover:bg-[#1a2332] text-[#94a3b8] hover:text-amber-400 rounded transition-colors"
        >
          <RefreshCw size={14} />
        </button>

        <button
          onClick={onOpenSourceModal}
          title="Switch Camera / Upload MP4 / RTSP Source"
          className="p-1.5 hover:bg-[#1a2332] text-[#94a3b8] hover:text-emerald-400 rounded transition-colors"
        >
          <Camera size={14} />
        </button>

        <button
          onClick={() => setShowHudOverlay(!showHudOverlay)}
          title="Toggle Detection HUD Overlay"
          className={`p-1.5 rounded transition-colors ${
            showHudOverlay
              ? 'text-[#00e5ff] bg-[#142030]'
              : 'text-[#94a3b8] hover:bg-[#1a2332]'
          }`}
        >
          <Layers size={14} />
        </button>

        <button
          onClick={() => setIsCalibrating(!isCalibrating)}
          title={isCalibrating ? "Finish Zone Calibration" : "Calibrate Check Zone Polygon"}
          className={`p-1.5 rounded transition-colors ${
            isCalibrating
              ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
              : 'hover:bg-[#1a2332] text-[#94a3b8] hover:text-amber-400'
          }`}
        >
          <Crosshair size={14} />
        </button>

        <button
          onClick={toggleFullscreen}
          title="Fullscreen Display"
          className="p-1.5 hover:bg-[#1a2332] text-[#94a3b8] hover:text-[#e2e8f0] rounded transition-colors"
        >
          <Maximize2 size={14} />
        </button>
      </div>

      {/* Calibration Guide Hint */}
      {isCalibrating && (
        <div className="absolute top-14 left-1/2 -translate-x-1/2 bg-amber-950/90 border border-amber-500 text-amber-200 px-4 py-1.5 rounded-sm text-xs font-mono shadow-2xl flex items-center space-x-2 z-30">
          <AlertTriangle size={14} className="text-amber-400" />
          <span>DRAG ANCHOR HANDLES P1-P4 TO ADJUST CHECK ZONE POLYGON</span>
        </div>
      )}
    </div>
  );
}
