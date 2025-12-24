import React from "react";

export default function LocationToggle({
  checked,
  onChange,
  disabled = false,
  id = "useLocation",
  label = "Tarayıcı konumumu kullan",
  hint = "(kapalıysa şehir girişi zorunlu)",
}) {
  return (
    <div className="locWrap">
      <label className={`locRow ${disabled ? "isDisabled" : ""}`} htmlFor={id}>
        <span className="locText">
          <span className="locLabel">
            <span className="locIcon" aria-hidden="true">
              📍
            </span>
            {label}
          </span>
          <span className="locHint">{hint}</span>
        </span>

        <span className={`locSwitch ${checked ? "isOn" : ""}`}>
          <input
            id={id}
            className="locInput"
            type="checkbox"
            checked={checked}
            disabled={disabled}
            onChange={(e) => onChange(e.target.checked)}
            aria-label={label}
          />
          <span className="locTrack" aria-hidden="true"></span>
          <span className="locKnob" aria-hidden="true"></span>
        </span>
      </label>
    </div>
  );
}

