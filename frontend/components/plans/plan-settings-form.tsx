"use client";

import { Loader2, Save } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchPlanSettings, updatePlanSettings } from "@/lib/plans/service";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { FormError } from "@/components/ui/form-error";

function windowOpensOn(leadDays: number): string {
  return new Date(Date.now() - (leadDays - 1) * 86400000)
    .toISOString()
    .slice(0, 10);
}

export function PlanSettingsForm() {
  const [value, setValue] = useState("");
  const [savedValue, setSavedValue] = useState<number | null>(null);
  const [effectiveToday, setEffectiveToday] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchPlanSettings()
      .then((result) => {
        if (cancelled) return;
        if (result.ok) {
          setValue(String(result.data.confirmation_lead_days));
          setSavedValue(result.data.confirmation_lead_days);
          setEffectiveToday(windowOpensOn(result.data.confirmation_lead_days));
          setError("");
        } else {
          setError(result.message);
        }
      })
      .catch(() => {
        if (!cancelled) setError("Failed to load plan settings.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const leading = Number(value);
  const valid = Number.isFinite(leading) && leading >= 1 && leading <= 60;
  const dirty = valid && leading !== savedValue;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!valid || !dirty) return;
    setSaving(true);
    setError("");
    setSaved(false);
    const result = await updatePlanSettings(leading);
    setSaving(false);
    if (result.ok) {
      setSavedValue(result.data.confirmation_lead_days);
      setValue(String(result.data.confirmation_lead_days));
      setEffectiveToday(windowOpensOn(result.data.confirmation_lead_days));
      setSaved(true);
    } else {
      setError(result.message);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-text-primary">Plan settings</h2>
        <p className="text-text-secondary">
          Controls how far before a reserved block the confirmation window opens.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle">
        {loading ? (
          <div className="flex justify-center py-6">
            <Loader2 className="size-5 animate-spin text-text-muted" />
          </div>
        ) : (
          <Field
            label="Confirmation lead days"
            htmlFor="confirmation_lead_days"
            hint="Blocks that count against annual entitlement must be confirmed at least this many days before they start, or they lapse."
          >
            <Input
              id="confirmation_lead_days"
              name="confirmation_lead_days"
              type="number"
              min={1}
              max={60}
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                setSaved(false);
              }}
              className="max-w-[10rem]"
            />
          </Field>
        )}
        {!loading && savedValue != null && (
          <p className="mt-3 text-xs text-text-muted">
            With this setting, the confirmation window for a block opens on the
            start date minus lead days. Blocks starting around{" "}
            <span className="font-medium text-text-secondary">{effectiveToday}</span>{" "}
            are in their window now.
          </p>
        )}
      </div>

      {error && <FormError>{error}</FormError>}
      {saved && (
        <p className="text-sm text-brand-secondary">Settings saved.</p>
      )}

      <div className="flex items-center gap-3">
        <Button
          type="submit"
          variant="primary"
          loading={saving}
          disabled={!dirty}
        >
          <Save className="size-4" />
          Save settings
        </Button>
      </div>
    </form>
  );
}