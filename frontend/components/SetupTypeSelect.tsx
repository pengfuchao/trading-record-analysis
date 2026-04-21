"use client";

import { useState } from "react";

const CUSTOM = "__custom__";

export function SetupTypeSelect({
  label,
  value,
  onChange,
  setupNames,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  setupNames: string[];
}) {
  const isKnown = value === "" || setupNames.includes(value);
  const [customText, setCustomText] = useState(isKnown ? "" : value);

  const selectValue = isKnown ? value : CUSTOM;

  function handleSelect(v: string) {
    if (v === CUSTOM) {
      onChange(customText);
    } else {
      onChange(v);
    }
  }

  function handleCustomText(v: string) {
    setCustomText(v);
    onChange(v);
  }

  return (
    <div className="space-y-1">
      <label className="block text-xs text-gray-500 uppercase tracking-wider mb-0.5">
        {label}
      </label>
      <select
        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
        value={selectValue}
        onChange={(e) => handleSelect(e.target.value)}
      >
        <option value="">— unset —</option>
        {setupNames.map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
        <option value={CUSTOM}>Custom…</option>
      </select>
      {selectValue === CUSTOM && (
        <input
          className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
          value={customText}
          onChange={(e) => handleCustomText(e.target.value)}
          placeholder="Enter custom setup type"
        />
      )}
    </div>
  );
}
