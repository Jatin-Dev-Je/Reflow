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
import { useLogin } from "@/features/auth/api/use-login";
import * as routes from "@/lib/constants/routes";
import { cn } from "@/lib/utils/cn";

/**
 * Screen #1 — Login.
 *
 * Validates with Zod, submits to /api/v1/auth/login, stores tokens, navigates
 * to the executive dashboard on success. Surfaces typed backend errors
 * (ReflowApiError) inline above the form.
 */

const loginSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginPage(): JSX.Element {
  const navigate = useNavigate();
  const login = useLogin();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = (values: LoginFormValues): void => {
    login.mutate(values, {
      onSuccess: () => {
        navigate(routes.DASHBOARD_EXECUTIVE);
      },
    });
  };

  const apiErrorMessage =
    login.error instanceof ReflowApiError
      ? login.error.message
      : login.error
        ? "Something went wrong. Try again."
        : null;

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your Reflow account."
      footer={
        <span>
          Don&rsquo;t have an account?{" "}
          <Link
            to={routes.REGISTER}
            className="text-primary hover:underline underline-offset-4"
          >
            Create one
          </Link>
        </span>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
        {apiErrorMessage ? (
          <div
            role="alert"
            className="rounded-md border border-danger/30 bg-danger-surface px-4 py-3"
          >
            <p className="text-body-sm text-danger">{apiErrorMessage}</p>
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

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link
              to={routes.FORGOT_PASSWORD}
              className="text-caption text-foreground-secondary hover:text-primary hover:underline underline-offset-4"
            >
              Forgot?
            </Link>
          </div>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            placeholder="••••••••"
            aria-invalid={!!errors.password}
            {...register("password")}
          />
          {errors.password ? (
            <p className="text-caption text-danger">{errors.password.message}</p>
          ) : null}
        </div>

        <Button
          type="submit"
          variant="primary"
          size="lg"
          className={cn("w-full", login.isPending && "opacity-90")}
          disabled={login.isPending}
        >
          {login.isPending ? (
            <>
              <Loader2 className="animate-spin" />
              Signing in…
            </>
          ) : (
            "Sign in"
          )}
        </Button>
      </form>
    </AuthShell>
  );
}
