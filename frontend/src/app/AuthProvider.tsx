import { createContext, useContext, useEffect, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "../api/schema";
import { api, unwrap } from "../api/client";

export type AuthUser = components["schemas"]["CurrentUserOutput"];
type AuthState = {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  can: (permission: string) => boolean;
};
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const session = useQuery({
    queryKey: ["session"],
    queryFn: async () => {
      const result = await api.GET("/api/v1/auth/me");
      if (result.response.status === 401) return null;
      return unwrap(result);
    },
    retry: false,
    staleTime: 30_000,
  });

  useEffect(() => {
    const expire = () => {
      queryClient.setQueryData(["session"], null);
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
    };
    window.addEventListener("cyberlab:session-expired", expire);
    return () => window.removeEventListener("cyberlab:session-expired", expire);
  }, [queryClient]);

  const loginMutation = useMutation({
    mutationFn: async ({
      username,
      password,
    }: {
      username: string;
      password: string;
    }) =>
      unwrap(
        await api.POST("/api/v1/auth/login", { body: { username, password } }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["session"] });
    },
  });
  const logoutMutation = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/v1/auth/logout")),
    onSettled: () => {
      queryClient.clear();
    },
  });

  const value: AuthState = {
    user: session.data ?? null,
    loading: session.isLoading,
    login: async (username, password) => {
      await loginMutation.mutateAsync({ username, password });
    },
    logout: async () => {
      await logoutMutation.mutateAsync();
    },
    can: (permission) =>
      session.data?.permissions?.includes("*") === true ||
      session.data?.permissions?.includes(permission) === true,
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
