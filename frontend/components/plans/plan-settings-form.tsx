"use client";

import { useEffect, useState } from "react";

import { fetchPlanSettings, savePlanSettings } from "@/lib/plans/service";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/states";
import { Field, Input } from "@/components/ui/input";
import { FormError } from "@/components/ui/form-error";
import { useToast } from "@/components/ui/toast";

/**
 * The one HR-editable plan setting: how many days before a reserved block
 * starts the owner must confirm it.
 *
 * The input is validated against the same 1–90 range the backend enforces, so
 * the error appears before the round trip. `fieldError` is the client's
 * complaint about the input and `saveError` is the server's, and they are kept
 * apart so a rejected save is not written next to the field as if the number
 * itself were wrong.
 */
const MIN_DAYS = 1;
const MAX_DAYS = 90;

function validate(value: string): number | null {
  const parsed = Number(value.trim());
  if (!Number.isInteger(parsed) || parsed < MIN_DAYS || parsed > MAX_DAYS) {
    return null;
  }
  return parsed;
}

export function PlanSettingsForm() {
  const [days, setDays] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const { showToast } = useToast();

  useEffect(() => {
    let cancelled = false;
    fetchPlanSettings()
      .then((result) => {
        if (cancelled) return;
        if (result.ok) {
          setDays(String(result.data.confirmation_lead_days));
          setLoadError("");
        } else {
          setLoadError(result.message);
        }
      })
      .catch(() => {
        if (!cancelled) setLoadError("Plan settings could not be loaded.");
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    const parsed = validate(days);
    if (parsed === null) {
      setFieldError(
        `Enter a whole number of days between ${MIN_DAYS} and ${MAX_DAYS}.`
      );
      return;
    }
    setFieldError(null);
    setSaveError("");
    setSaving(true);
    const result = await savePlanSettings({ confirmation_lead_days: parsed });
    if (result.ok) {
      setDays(String(result.data.confirmation_lead_days));
      showToast("Plan settings saved");
    } else {
      setSaveError(result.message);
    }
    setSaving(false);
  }

  if (loadError) {
    return (
      <ErrorState
        message={loadError}
        onRetry={() => {
          setLoadError("");
          setReloadKey((value) => value + 1);
        }}
      />
    );
  }

  return (
    <Card>
      <CardHeader title="Confirmation window" />
      <form onSubmit={onSubmit} className="space-y-4">
        <Field
          label="Days before leave starts to confirm"
          htmlFor="confirmation-lead-days"
          hint={`Between ${MIN_DAYS} and ${MAX_DAYS}. Applies to blocks reserved by an approved plan: the owner confirms the leave inside this window.`}
          error={fieldError}
        >
          <Input
            id="confirmation-lead-days"
            name="confirmation_lead_days"
            type="number"
            inputMode="numeric"
            min={MIN_DAYS}
            max={MAX_DAYS}
            value={days}
            onChange={(event) => {
              setDays(event.target.value);
              if (fieldError) setFieldError(null);
              if (saveError) setSaveError("");
            }}
          />
        </Field>
        {saveError && <FormError>{saveError}</FormError>}
        <div className="flex items-center justify-end">
          <Button type="submit" variant="primary" loading={saving} disabled={saving}>
            Save settings
          </Button>
        </div>
      </form>
    </Card>
  );
}
