import { PasswordChangeForm } from "@/components/account/password-change-form";
import { FadeIn } from "@/components/motion/FadeIn";

/**
 * The signed-in user's own account page.
 *
 * Deliberately just the password form, and deliberately a page rather than a
 * dialog in the header: this is the first account surface in the app, so it is
 * worth having somewhere that can hold the rest of it later (name, notification
 * preferences) without a second migration of the navigation when that arrives.
 */
export default function AccountPage() {
  return (
    <FadeIn>
      <div className="mx-auto w-full max-w-2xl space-y-6">
        <header>
          <h1 className="text-2xl font-semibold text-ink-strong">My account</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Your sign-in details. Ask HR to change anything else about your record.
          </p>
        </header>
        <PasswordChangeForm />
      </div>
    </FadeIn>
  );
}
