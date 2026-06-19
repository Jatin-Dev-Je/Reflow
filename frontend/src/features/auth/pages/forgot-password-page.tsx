import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, Loader2, MailCheck } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { ReflowApiError } from "@/api/interceptors/error";
import { toApiError } from "@/api/interceptors/error";
import { AuthShell } from "@/components/layout/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import * as routes from "@/lib/constants/routes";

/**
 * Screen #3 — Forgot Password.
 *
 * Submits the email to /api/v1/auth/forgot-password. Always shows the same
 * success view regardless of whether the email exists — email enumeration
 * defence. The backend endpoint may not be wired yet; we surface backend
 * errors only for non-404 failures.
 */

const schema = z.object({
  email: z.string().email("Enter a valid email"),
});
type Values = z.infer<typeof schema>;

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function forgotRequest(values: Values): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });
  // 404 means the endpoint isn't deployed yet — still show success.
  if (response.status === 404) return;
  if (!response.ok) {
    throw await toApiError(response);
  }
}

export function ForgotPasswordPage(): JSX.Element {
  const {
    register,
    handleSubmit,
    formState: { errors },
    getValues,
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: "" },
  });

  const forgot = useMutation<void, Error, Values>({
    mutationFn: forgotRequest,
  });

  const onSubmit = (values: Values): void => {
    forgot.mutate(values);
  };

  if (forgot.isSuccess) {
    return (
      <AuthShell
        title="Check your email"
        subtitle={`If an account exists for ${getValues("email")}, we sent reset instructions.`}
        footer={
          <Link
            to={routes.LOGIN}
            className="inline-flex items-center gap-1 text-primary hover:underline underline-offset-4"
          >
            <ArrowLeft className="size-3.5" />
            Back to sign in
          </Link>
        }
      >
        <div className="rounded-md border border-success/30 bg-success-surface px-5 py-6 flex items-start gap-3">
          <MailCheck className="size-5 text-success shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-medium text-body text-foreground">Reset link sent</p>
            <p className="text-body-sm text-foreground-secondary leading-relaxed">
              The link expires in 30 minutes. If you don&rsquo;t see the email,
              check your spam folder.
            </p>
          </div>
        </div>
      </AuthShell>
    );
  }

  const apiError =
    forgot.error instanceof ReflowApiError
      ? forgot.error.message
      : forgot.error
        ? "Something went wrong. Try again."
        : null;

  return (
    <AuthShell
      title="Reset your password"
      subtitle="Enter your email and we&rsquo;ll send you a reset link."
      footer={
        <Link
          to={routes.LOGIN}
          className="inline-flex items-center gap-1 text-primary hover:underline underline-offset-4"
        >
          <ArrowLeft className="size-3.5" />
          Back to sign in
        </Link>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
        {apiError ? (
          <div
            role="alert"
            className="rounded-md border border-danger/30 bg-danger-surface px-4 py-3"
          >
            <p className="text-body-sm text-danger">{apiError}</p>
          </div>
        ) : null}

        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            aria-invalid={!!errors.email}
            {...register("email")}
          />
          {errors.email ? (
            <p className="text-caption text-danger">{errors.email.message}</p>
          ) : null}
        </div>

        <Button
          type="submit"
          variant="primary"
          size="lg"
          className="w-full"
          disabled={forgot.isPending}
        >
          {forgot.isPending ? (
            <>
              <Loader2 className="animate-spin" />
              Sending…
            </>
          ) : (
            "Send reset link"
          )}
        </Button>
      </form>
    </AuthShell>
  );
}
