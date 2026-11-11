import React, { useState } from 'react';
import { X, ShieldCheck, ShieldAlert, CheckCircle, AlertTriangle, FileText } from 'lucide-react';

export default function VerificationModal({
  event,
  isOpen,
  onClose,
  onConfirmVerification
}) {
  if (!isOpen || !event) return null;

  const [verifyStatus, setVerifyStatus] = useState(
    event.is_violation ? "CONFIRMED" : "APPROVED"
  );
  const [officerName, setOfficerName] = useState("Officer J. Miller (ID #408)");
  const [notes, setNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const handleSubmit = async () => {
    setIsSaving(true);
    try {
      await onConfirmVerification({
        eventId: event.id,
        status: verifyStatus,
        verifiedBy: officerName,
        notes: notes
      });
      onClose();
    } catch (err) {
      alert(`Verification failed: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 font-mono select-none">
      <div className="w-full max-w-lg bg-[#0b0f17] border border-[#222e40] rounded-sm shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1f2a3a] bg-[#0e141f]">
          <div className="flex items-center space-x-2">
            <ShieldCheck size={16} className="text-[#00e5ff]" />
            <span className="font-bold text-sm text-[#e2e8f0]">
              EVIDENCE VERIFICATION & AUDIT REVIEW
            </span>
          </div>
          <button 
            onClick={onClose}
            className="text-[#64748b] hover:text-[#e2e8f0] transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-4 space-y-4 text-xs">
          {/* Snapshot & Telemetry Banner */}
          <div className="flex space-x-4 bg-[#080b0f] p-3 border border-[#1b2533] rounded">
            {/* Cropped Snapshot */}
            <div className="w-28 h-28 bg-[#16202c] border border-[#233145] rounded overflow-hidden flex-shrink-0 flex items-center justify-center">
              {event.thumbnail_url ? (
                <img 
                  src={event.thumbnail_url} 
                  alt="Violation Evidence" 
                  className="w-full h-full object-cover"
                />
              ) : (
                <span className="text-[#475569] text-[10px]">No Snapshot</span>
              )}
            </div>

            {/* Event Metadata */}
            <div className="flex flex-col justify-between flex-1 leading-relaxed">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-white font-bold text-sm">
                    {event.vehicle_type} #{event.vehicle_id}
                  </span>
                  <span className="text-[#64748b]">{event.camera_id || "CAM 01"}</span>
                </div>
                <div className="mt-1">
                  <span className="text-[#64748b]">Evaluation Status: </span>
                  <span className={`font-bold ${event.is_violation ? 'text-[#ff334b]' : 'text-[#00e676]'}`}>
                    {event.status}
                  </span>
                </div>
                <div className="text-[#94a3b8]">
                  Confidence: <span className="text-[#00e5ff] font-semibold">{Math.round((event.confidence || 0.92) * 100)}%</span>
                </div>
                <div className="text-[#94a3b8]">
                  Timestamp: <span className="text-[#e2e8f0] font-mono">{event.timestamp || "01:11"}</span>
                </div>
              </div>

              <div className="text-[10px] text-[#475569]">
                Evidence Token: #{Math.floor(100000 + Math.random() * 900000)}
              </div>
            </div>
          </div>

          {/* Verification Decision Form */}
          <div className="space-y-3">
            <div>
              <label className="text-[10px] text-[#64748b] uppercase block mb-1">
                Surveillance Decision Action
              </label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setVerifyStatus("CONFIRMED")}
                  className={`py-2 px-1 text-center font-bold rounded-sm border transition-colors ${
                    verifyStatus === "CONFIRMED"
                      ? 'bg-red-950/50 border-[#ff334b] text-[#ff334b]'
                      : 'bg-[#0f1521] border-[#1e2736] text-[#64748b] hover:text-[#94a3b8]'
                  }`}
                >
                  CONFIRM VIOLATION
                </button>
                <button
                  type="button"
                  onClick={() => setVerifyStatus("REJECTED")}
                  className={`py-2 px-1 text-center font-bold rounded-sm border transition-colors ${
                    verifyStatus === "REJECTED"
                      ? 'bg-amber-950/50 border-amber-500 text-amber-400'
                      : 'bg-[#0f1521] border-[#1e2736] text-[#64748b] hover:text-[#94a3b8]'
                  }`}
                >
                  FALSE POSITIVE
                </button>
                <button
                  type="button"
                  onClick={() => setVerifyStatus("APPROVED")}
                  className={`py-2 px-1 text-center font-bold rounded-sm border transition-colors ${
                    verifyStatus === "APPROVED"
                      ? 'bg-emerald-950/50 border-[#00e676] text-[#00e676]'
                      : 'bg-[#0f1521] border-[#1e2736] text-[#64748b] hover:text-[#94a3b8]'
                  }`}
                >
                  MARK COMPLIANT
                </button>
              </div>
            </div>

            <div>
              <label className="text-[10px] text-[#64748b] uppercase block mb-1">Reviewing Officer</label>
              <input
                type="text"
                value={officerName}
                onChange={(e) => setOfficerName(e.target.value)}
                className="w-full bg-[#080b0f] border border-[#232e3f] p-2 text-white rounded-sm focus:border-[#00e5ff] outline-none"
              />
            </div>

            <div>
              <label className="text-[10px] text-[#64748b] uppercase block mb-1">Verification Audit Notes</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. Visual confirmation of driver strap confirmed on windshield inspection..."
                rows={2}
                className="w-full bg-[#080b0f] border border-[#232e3f] p-2 text-white rounded-sm focus:border-[#00e5ff] outline-none resize-none"
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex space-x-2 pt-2 border-t border-[#1f2a3a]">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 bg-[#121926] hover:bg-[#1a2333] text-[#94a3b8] font-bold uppercase rounded-sm transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={isSaving}
              onClick={handleSubmit}
              className="flex-1 py-2 bg-[#00e5ff] hover:bg-[#00c5dc] text-black font-bold uppercase tracking-wider rounded-sm transition-colors"
            >
              {isSaving ? "Saving..." : "Commit Verification"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
