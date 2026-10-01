import React from 'react';
import { AlertTriangle, X } from 'lucide-react';

export default function Modal({ isOpen, onClose, onConfirm, title, children, confirmText = 'Confirm', confirmVariant = 'danger', isProcessing = false }) {
  if (!isOpen) return null;

  const confirmColors = {
    danger: 'bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-900/40',
    warning: 'bg-amber-600 hover:bg-amber-700 text-white shadow-lg shadow-amber-900/40',
    primary: 'bg-cyan-600 hover:bg-cyan-700 text-white shadow-lg shadow-cyan-900/40',
  }[confirmVariant] || 'bg-red-600 hover:bg-red-700 text-white';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-md bg-[#0f172a] border border-slate-700 rounded-xl shadow-2xl p-6 overflow-hidden">
        {/* Glow accent */}
        <div className={`absolute top-0 left-0 right-0 h-1 ${confirmVariant === 'danger' ? 'bg-red-500' : 'bg-cyan-500'}`} />

        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-lg ${confirmVariant === 'danger' ? 'bg-red-950/60 text-red-400 border border-red-800/40' : 'bg-cyan-950/60 text-cyan-400 border border-cyan-800/40'}`}>
              <AlertTriangle className="w-5 h-5" />
            </div>
            <h3 className="text-lg font-semibold text-slate-100">{title}</h3>
          </div>
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="text-slate-400 hover:text-slate-200 transition-colors p-1 rounded-md hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="text-sm text-slate-300 mb-6 leading-relaxed">
          {children}
        </div>

        <div className="flex items-center justify-end space-x-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isProcessing}
            className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-700 rounded-lg border border-slate-700 transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isProcessing}
            className={`px-5 py-2 text-sm font-medium rounded-lg transition flex items-center space-x-2 ${confirmColors} disabled:opacity-50`}
          >
            {isProcessing ? (
              <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                </svg>
                <span>Processing...</span>
              </>
            ) : (
              <span>{confirmText}</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
