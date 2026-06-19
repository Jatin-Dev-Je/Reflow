import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { ReflowApiError } from "@/api/interceptors/error";
import { AuthShell } from "@/components/layout/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useRegister } from "@/features/auth/api/use-register";
import * as routes from "@/lib/constants/routes";

/**
 * Screen #2 — Register.
 *
 * Validates email + 8+ char password + optional display name. Backend
 * returns a TokenPair on success (auto-login) or 409 on duplicate email.
 */

const registerSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z
    .string()
    .min(8, "At least 8 characters")
    .max(256, "Too long"),
  display_name: z
    .string()
    .max(128, "Too long")
    .optional()
    .transform((v) => (v === "" ? undefined : v)),
});

type RegisterFormValues = z.infer<typeof registerSchema>;

export function RegisterPage(): JSX.Element {
  const navigate = useNavigate();
  const reg = useRegister();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: "", password: "", display_name: "" },
  });

  const onSubmit = (values: RegisterFormValues): void => {
    reg.mutate(values, {
      onSuccess: () => {
        navigate(routes.ONBOARDING_WELCOME);
      },
    });
  };

  const apiError =
    reg.error instanceof ReflowApiError
      ? reg.error.message
      : reg.error
        ? "Something went wrong. Try again."
        : null;

  return (
    <AuthShell
      title="Create your account"
      subtitle="Spin up a Reflow workspace in under a minute."
      footer={
        <span>
          Already have an account?{" "}
          <Link
            to={routes.LOGIN}
            className="text-primary hover:underline underline-offset-4"
          >
            Sign in
          </Link>
        </span>
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
          <Label htmlFor="display_name">Your name (optional)</Label>
          <Input
            id="display_name"
            type="text"
            autoComplete="name"
            placeholder="Jane Doe"
            {...register("display_name")}
          />
          {errors.display_name ? (
            <p className="text-caption text-danger">{errors.display_name.message}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <Label htmlFor="email">Work email</Label>
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

        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            placeholder="At least 8 characters"
            aria-invalid={!!errors.password}
            {...register("password")}
          />
          {errors.password ? (
            <p className="text-caption text-danger">{errors.password.message}</p>
          ) : (
            <p className="text-caption text-foreground-tertiary">
              Use 8+ characters. We hash with argon2id.
            </p>
          )}
        </div>

        <Button
          type="submit"
          variant="primary"
          size="lg"
          className="w-full"
          disabled={reg.isPending}
        >
          {reg.isPending ? (
            <>
              <Loader2 className="animate-spin" />
              Creating account…
            </>
          ) : (
            "Create account"
          )}
        </Button>

        <p className="text-caption text-foreground-tertiary text-center leading-relaxed">
          By creating an account you agree to our{" "}
          <Link to="/terms" className="hover:text-primary hover:underline underline-offset-2">
            Terms
          </Link>{" "}
          and{" "}
          <Link to="/privacy" className="hover:text-primary hover:underline underline-offset-2">
            Privacy Policy
          </Link>
          .
        </p>
      </form>
    </AuthShell>
  );
}
