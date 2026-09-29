"use client";

import { FormEvent, useState } from "react";
import { ChevronDown, ChevronUp, Plus, Trash2 } from "lucide-react";

import type {
  LeaveDocumentTemplate,
  LeaveDocumentTemplateInput,
  TemplateField,
  TemplateSignatureArea,
} from "@/lib/leave-document-template";
import { updateLeaveDocumentTemplate } from "@/lib/leave-document-template-client";
import { DocumentTemplatePreview } from "./document-template-preview";
import { Field, Input, Select } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";
import { Textarea } from "@/components/ui/textarea";

export function LeaveDocumentTemplateEditor({
  template,
}: {
  template: LeaveDocumentTemplate;
}) {
  const [title, setTitle] = useState(template.title);
  const [header, setHeader] = useState(template.header);
  const [intro, setIntro] = useState(template.intro);
  const [fields, setFields] = useState<TemplateField[]>(template.fields);
  const [closing, setClosing] = useState(template.closing);
  const [signatureAreas, setSignatureAreas] = useState<
    TemplateSignatureArea[]
  >(template.signature_areas);
  const [footer, setFooter] = useState(template.footer);
  const [newFieldKey, setNewFieldKey] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  const usedKeys = fields.map((field) => field.key);
  const availableFields = template.available_fields.filter(
    (field) => !usedKeys.includes(field.key)
  );

  const previewDraft: LeaveDocumentTemplate = {
    title,
    header,
    intro,
    fields,
    closing,
    signature_areas: signatureAreas,
    footer,
    available_fields: template.available_fields,
    updated_at: template.updated_at,
  };

  function addField() {
    const catalog = template.available_fields.find(
      (field) => field.key === newFieldKey
    );
    if (!catalog) {
      return;
    }
    setFields([...fields, { key: catalog.key, label: catalog.label }]);
    setNewFieldKey("");
    setSaved(false);
  }

  function updateFieldLabel(index: number, label: string) {
    const next = [...fields];
    next[index] = { ...next[index], label };
    setFields(next);
    setSaved(false);
  }

  function updateFieldOrder(index: number, direction: -1 | 1) {
    const next = [...fields];
    const target = index + direction;
    if (target < 0 || target >= next.length) {
      return;
    }
    [next[index], next[target]] = [next[target], next[index]];
    setFields(next);
    setSaved(false);
  }

  function removeField(index: number) {
    if (fields.length <= 1) {
      return;
    }
    setFields(fields.filter((_, i) => i !== index));
    setSaved(false);
  }

  function updateSignatureLabel(index: number, label: string) {
    const next = [...signatureAreas];
    next[index] = { label };
    setSignatureAreas(next);
    setSaved(false);
  }

  function updateSignatureOrder(index: number, direction: -1 | 1) {
    const next = [...signatureAreas];
    const target = index + direction;
    if (target < 0 || target >= next.length) {
      return;
    }
    [next[index], next[target]] = [next[target], next[index]];
    setSignatureAreas(next);
    setSaved(false);
  }

  function removeSignature(index: number) {
    setSignatureAreas(signatureAreas.filter((_, i) => i !== index));
    setSaved(false);
  }

  function addSignatureArea() {
    setSignatureAreas([...signatureAreas, { label: "Signature" }]);
    setSaved(false);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSaved(false);
    setLoading(true);

    const input: LeaveDocumentTemplateInput = {
      title,
      header,
      intro,
      fields,
      closing,
      signature_areas: signatureAreas,
      footer,
    };

    try {
      const updated = await updateLeaveDocumentTemplate(input);
      setTitle(updated.title);
      setHeader(updated.header);
      setIntro(updated.intro);
      setFields(updated.fields);
      setClosing(updated.closing);
      setSignatureAreas(updated.signature_areas);
      setFooter(updated.footer);
      setSaved(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <div className="space-y-6">
        <Field
          label="Document title"
          htmlFor="template-title"
          hint="Shown at the top of the approved leave document."
        >
          <Input
            id="template-title"
            value={title}
            onChange={(event) => {
              setTitle(event.target.value);
              setSaved(false);
            }}
          />
        </Field>

        <Field label="Header" htmlFor="template-header">
          <Input
            id="template-header"
            value={header}
            onChange={(event) => {
              setHeader(event.target.value);
              setSaved(false);
            }}
          />
        </Field>

        <Field label="Opening wording" htmlFor="template-intro">
          <Textarea
            id="template-intro"
            rows={3}
            value={intro}
            onChange={(event) => {
              setIntro(event.target.value);
              setSaved(false);
            }}
          />
        </Field>

        <div className="rounded-xl border border-border-default bg-surface-card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">
              Data fields
            </h3>
            <div className="flex items-center gap-2">
              <Select
                aria-label="Add data field"
                value={newFieldKey}
                onChange={(event) => setNewFieldKey(event.target.value)}
                className="w-auto px-2 py-1.5"
              >
                <option value="">Add field</option>
                {availableFields.map((field) => (
                  <option key={field.key} value={field.key}>
                    {field.label}
                  </option>
                ))}
              </Select>
              <button
                type="button"
                onClick={addField}
                disabled={!newFieldKey}
                aria-label="Add selected field"
                className="rounded-md bg-button-primary px-3 py-1.5 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
          </div>

          <p className="mb-3 text-xs text-text-muted">
            The data field itself is fixed (its value always comes from the
            approved application record); you control the label and order.
          </p>

          {fields.length === 0 ? (
            <p className="py-2 text-sm text-text-muted">
              No fields chosen. Add at least one data field.
            </p>
          ) : (
            fields.map((field, index) => (
              <div
                key={field.key}
                className="mb-2 flex items-center gap-2 rounded-lg border border-border-default bg-surface-page p-2"
              >
                <span className="w-32 shrink-0 text-xs text-text-muted">
                  {field.key}
                </span>
                <Input
                  aria-label={`Edit label: ${field.key}`}
                  value={field.label}
                  onChange={(event) =>
                    updateFieldLabel(index, event.target.value)
                  }
                  className="w-auto min-w-0 flex-1 px-2 py-1.5"
                />
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    aria-label={`Move ${field.key} up`}
                    disabled={index === 0}
                    onClick={() => updateFieldOrder(index, -1)}
                    className="rounded p-1 text-text-secondary hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <ChevronUp className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Move ${field.key} down`}
                    disabled={index === fields.length - 1}
                    onClick={() => updateFieldOrder(index, 1)}
                    className="rounded p-1 text-text-secondary hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <ChevronDown className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Remove ${field.key}`}
                    disabled={fields.length <= 1}
                    onClick={() => removeField(index)}
                    className="rounded p-1 text-status-rejected hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        <Field label="Closing wording" htmlFor="template-closing">
          <Textarea
            id="template-closing"
            rows={2}
            value={closing}
            onChange={(event) => {
              setClosing(event.target.value);
              setSaved(false);
            }}
          />
        </Field>

        <div className="rounded-xl border border-border-default bg-surface-card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">
              Signature areas
            </h3>
            <button
              type="button"
              onClick={addSignatureArea}
              className="flex items-center gap-1 rounded-md bg-button-secondary px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
            >
              <Plus className="h-4 w-4" />
              Add signature
            </button>
          </div>

          {signatureAreas.length === 0 ? (
            <p className="py-1 text-xs text-text-muted">
              No signature areas configured.
            </p>
          ) : (
            signatureAreas.map((area, index) => (
              <div
                key={`${area.label}-${index}`}
                className="mb-2 flex items-center gap-2 rounded-lg border border-border-default bg-surface-page p-2"
              >
                <Input
                  aria-label={`Signature area ${index + 1} label`}
                  value={area.label}
                  onChange={(event) =>
                    updateSignatureLabel(index, event.target.value)
                  }
                  className="w-auto min-w-0 flex-1 px-2 py-1.5"
                />
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    aria-label={`Move signature ${index + 1} up`}
                    disabled={index === 0}
                    onClick={() => updateSignatureOrder(index, -1)}
                    className="rounded p-1 text-text-secondary hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <ChevronUp className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Move signature ${index + 1} down`}
                    disabled={index === signatureAreas.length - 1}
                    onClick={() => updateSignatureOrder(index, 1)}
                    className="rounded p-1 text-text-secondary hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <ChevronDown className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    aria-label={`Remove signature ${index + 1}`}
                    onClick={() => removeSignature(index)}
                    className="rounded p-1 text-status-rejected hover:bg-surface-hover"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        <Field label="Footer" htmlFor="template-footer">
          <Input
            id="template-footer"
            value={footer}
            onChange={(event) => {
              setFooter(event.target.value);
              setSaved(false);
            }}
          />
        </Field>

        {error && (
          <FormError>{error}</FormError>
        )}

        <div className="flex items-center gap-3">
          <Button type="submit" variant="primary" loading={loading}>
            {loading ? "Saving..." : "Save template"}
          </Button>
          {saved && (
            <span className="text-sm text-text-muted">
              Template saved — preview reflects the saved configuration.
            </span>
          )}
        </div>
      </div>

      <div className="lg:sticky lg:top-6 lg:self-start">
        <p className="mb-2 text-sm font-medium text-text-primary">
          Preview
        </p>
        <DocumentTemplatePreview template={previewDraft} />
      </div>
    </form>
  );
}