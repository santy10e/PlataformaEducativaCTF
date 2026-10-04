import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CircleAlert,
  Crosshair,
  KeyRound,
} from "lucide-react";
import { ApiError } from "../api/client";
import { useAuth } from "./AuthProvider";
import { Button, Input } from "../components/ui";

const loginSchema = z.object({
  username: z.string().trim().min(1, "Escribe tu usuario.").max(80),
  password: z.string().min(1, "Escribe tu contraseña.").max(256),
});
type LoginValues = z.infer<typeof loginSchema>;

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [formError, setFormError] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { username: "", password: "" },
  });

  async function submit(values: LoginValues) {
    setFormError("");
    try {
      await login(values.username, values.password);
      navigate(
        (location.state as { from?: string } | null)?.from ?? "/workspace",
        { replace: true },
      );
    } catch (error) {
      if (error instanceof ApiError && error.status === 429)
        setFormError(
          "Has intentado entrar varias veces. Espera un momento antes de volver a probar.",
        );
      else if (error instanceof ApiError && error.status === 401)
        setFormError("El usuario o la contraseña no coinciden.");
      else
        setFormError(
          "No pudimos conectar con el campus. Inténtalo de nuevo en un momento.",
        );
    }
  }

  return (
    <main className="login-page">
      <header className="login-top">
        <Link to="/" className="login-brand">
          <span>
            <Crosshair size={18} />
          </span>
          CYBERLAB<small>CUADERNOS DE CAMPO</small>
        </Link>
        <Link to="/" className="login-back">
          <ArrowLeft size={14} /> Volver al cuaderno
        </Link>
      </header>
      <section className="login-layout">
        <div className="login-manifesto">
          <p className="page-eyebrow">ENTORNO DE APRENDIZAJE</p>
          <h1>
            Volvamos
            <br />a <em>investigar.</em>
          </h1>
          <p>
            Entra al campus y continúa tu recorrido por el laboratorio de
            ciberseguridad.
          </p>
          <div className="login-mark">
            <KeyRound size={25} />
            <span>
              ACCESO
              <br />
              PERSONAL
            </span>
          </div>
        </div>
        <div className="login-card">
          <div className="login-card-number">
            IDENTIFICACIÓN &nbsp; / &nbsp; CAMPUS 01
          </div>
          <h2>Iniciar sesión</h2>
          <p className="login-hint">
            Usa las credenciales que te entregó tu profesor.
          </p>
          <form onSubmit={handleSubmit(submit)} noValidate>
            <label className="login-field">
              <span>Usuario</span>
              <Input
                autoComplete="username"
                autoFocus
                placeholder="Tu usuario"
                aria-invalid={!!errors.username}
                aria-describedby={
                  errors.username ? "username-error" : undefined
                }
                {...register("username")}
              />
              {errors.username && (
                <small id="username-error" className="field-error">
                  {errors.username.message}
                </small>
              )}
            </label>
            <label className="login-field">
              <span>Contraseña</span>
              <Input
                type="password"
                autoComplete="current-password"
                placeholder="Tu contraseña"
                aria-invalid={!!errors.password}
                aria-describedby={
                  errors.password ? "password-error" : undefined
                }
                {...register("password")}
              />
              {errors.password && (
                <small id="password-error" className="field-error">
                  {errors.password.message}
                </small>
              )}
            </label>
            {formError && (
              <p className="login-error" role="alert">
                <CircleAlert size={15} />
                {formError}
              </p>
            )}
            <Button
              type="submit"
              className="login-submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Verificando…" : "Entrar al campus"}{" "}
              {!isSubmitting && <ArrowRight size={15} />}
            </Button>
          </form>
          <p className="login-footnote">
            Tus sesiones están protegidas y solo tú puedes acceder a tu espacio.
          </p>
        </div>
      </section>
      <footer className="login-footer">
        <span>CYBERLAB &nbsp;·&nbsp; APRENDER HACIENDO</span>
        <span>LABORATORIO UNIVERSITARIO</span>
      </footer>
    </main>
  );
}

export function ForbiddenPage() {
  return (
    <section className="route-message">
      <span>403 &nbsp; / &nbsp; ACCESO RESTRINGIDO</span>
      <h1>
        Este espacio no está
        <br />
        <em>en tu recorrido.</em>
      </h1>
      <p>Tu cuenta no tiene permiso para ver esta sección.</p>
      <Link to="/workspace">
        Volver a mi espacio <ArrowRight size={15} />
      </Link>
    </section>
  );
}
export function NotFoundPage() {
  return (
    <section className="route-message">
      <span>404 &nbsp; / &nbsp; PÁGINA NO ENCONTRADA</span>
      <h1>
        Parece que esta
        <br />
        <em>pista no existe.</em>
      </h1>
      <p>La dirección pudo cambiar o todavía no está disponible.</p>
      <Link to="/workspace">
        <BookOpen size={15} /> Volver al campus
      </Link>
    </section>
  );
}
