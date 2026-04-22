"use client";

import { useState } from "react";

export function SetupMultiSelect({
  label,
  value,
  onChange,
  setupNames,
}: {
  label: string;
  value: string[];
  onChange: (v: string[]) => void;
  setupNames: string[];
}) {
  const [customInput, setCustomInput] = useState("");

  function toggle(name: string) {
    if (value.includes(name)) {
      onChange(value.filter((v) => v !== name));
    } else {
      onChange([...value, name]);
    }
  }

  function addCustom() {
    const trimmed = customInput.trim();
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
    }
    setCustomInput("");
  }

  function remove(name: string) {
    onChange(value.filter((v) => v !== name));
  }

  // Values not present in the current library (custom or from old free-text data)
  const customValues = value.filter((v) => !setupNames.includes(v));

  return (
    <div className="space-y-2">
      <label className="block text-xs text-gray-500 uppercase tracking-wider">
        {label}
      </label>

      {/* Library setups as toggle pills */}
      {setupNames.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {setupNames.map((name) => {
            const selected = value.includes(name);
            return (
              <button
                key={name}
                type="button"
                onClick={() => toggle(name)}
                className={`text-xs px-2 py-0.5 rounded border transition-colors ${
                  selected
                    ? "bg-blue-700 border-blue-500 text-blue-100"
                    : "bg-gray-800 border-gray-600 text-gray-400 hover:border-gray-400 hover:text-gray-200"
                }`}
              >
                {selected ? `✓ ${name}` : name}
              </button>
            );
          })}
        </div>
      )}

      {/* Custom values (either added via input or loaded from existing plan data) */}
      {customValues.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {customValues.map((name) => (
            <span
              key={name}
              className="inline-flex items-center gap-1 text-xs bg-gray-700 border border-gray-600 text-gray-300 px-2 py-0.5 rounded"
            >
              {name}
              <button
                type="button"
                onClick={() => remove(name)}
                className="text-gray-500 hover:text-gray-200 leading-none"
                aria-label={`Remove ${name}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Custom entry input */}
      <div className="flex gap-1">
        <input
          type="text"
          value={customInput}
          onChange={(e) => setCustomInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addCustom();
            }
          }}
          placeholder={setupNames.length > 0 ? "Custom…" : "Enter setup name…"}
          className="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-100 placeholder-gray-600 focus:outline-none focus:border-blue-500"
        />
        <button
          type="button"
          onClick={addCustom}
          disabled={!customInput.trim()}
          className="text-xs px-2 py-1 bg-gray-700 border border-gray-600 rounded text-gray-300 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Add
        </button>
      </div>

      {value.length === 0 && (
        <p className="text-xs text-gray-600">None selected</p>
      )}
    </div>
  );
}
