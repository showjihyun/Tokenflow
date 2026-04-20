import { X } from "lucide-react";
import { useTweaks, type Tweaks } from "../lib/tweaksStore";
import "./TweaksPanel.css";

type Option<T> = [value: T, label: string];

interface GroupProps<K extends keyof Tweaks> {
  label: string;
  tweakKey: K;
  options: Option<Tweaks[K]>[];
}

function Group<K extends keyof Tweaks>({ label, tweakKey, options }: GroupProps<K>) {
  const value = useTweaks((s) => s.tweaks[tweakKey]);
  const setTweak = useTweaks((s) => s.setTweak);
  return (
    <div className="tweak-group">
      <div className="tweak-label">{label}</div>
      <div className="tweak-opts">
        {options.map(([opt, lbl]) => (
          <button
            key={String(opt)}
            className={value === opt ? "active" : ""}
            onClick={() => setTweak(tweakKey, opt)}
          >
            {lbl}
          </button>
        ))}
      </div>
    </div>
  );
}

export function TweaksPanel() {
  const open = useTweaks((s) => s.panelOpen);
  const close = useTweaks((s) => s.closePanel);

  return (
    <div className={`tweaks ${open ? "open" : ""}`}>
      <div className="tweaks-head">
        <span className="tweaks-title">Tweaks</span>
        <button className="icon-btn" onClick={close} aria-label="Close tweaks">
          <X size={14} strokeWidth={1.8} />
        </button>
      </div>
      <div className="tweaks-body">
        <Group
          label="Theme"
          tweakKey="theme"
          options={[["dark", "Dark"], ["light", "Light"]]}
        />
        <Group
          label="Density"
          tweakKey="density"
          options={[["compact", "Compact"], ["normal", "Normal"], ["roomy", "Roomy"]]}
        />
        <Group
          label="Chart style"
          tweakKey="chart_style"
          options={[["bold", "Bold"], ["minimal", "Minimal"], ["outlined", "Outlined"]]}
        />
        <Group
          label="Sidebar position"
          tweakKey="sidebar_pos"
          options={[["left", "Left"], ["right", "Right"]]}
        />
        <Group
          label="Alert aggressiveness"
          tweakKey="alert_level"
          options={[["quiet", "Quiet"], ["balanced", "Balanced"], ["loud", "Loud"]]}
        />
        <Group
          label="UI language"
          tweakKey="lang"
          options={[["ko", "한국어"], ["en", "English"]]}
        />
        <Group
          label="Better prompt"
          tweakKey="better_prompt_mode"
          options={[["static", "Static"], ["llm", "LLM"]]}
        />
        <div className="tweaks-foot">Preferences persist to localStorage + server</div>
      </div>
    </div>
  );
}
