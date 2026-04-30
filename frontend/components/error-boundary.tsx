"use client";

import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * React Error Boundary
 * 
 * 捕获子组件树的渲染错误，展示友好的错误界面而非白屏。
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error("[ErrorBoundary] Caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="h-screen flex items-center justify-center bg-background text-white">
          <div className="flex flex-col items-center gap-6 max-w-md text-center">
            <div className="h-16 w-16 rounded-3xl bg-destructive/10 flex items-center justify-center">
              <AlertTriangle className="h-8 w-8 text-destructive" />
            </div>
            <div className="space-y-2">
              <h2 className="text-xl font-bold">渲染异常</h2>
              <p className="text-sm text-white/40 leading-relaxed">
                页面组件遇到了意外错误。你可以尝试刷新页面恢复。
              </p>
              {this.state.error && (
                <pre className="mt-4 p-3 bg-white/5 rounded-xl text-xs text-white/30 overflow-auto max-h-32 text-left">
                  {this.state.error.message}
                </pre>
              )}
            </div>
            <Button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="rounded-2xl px-8"
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              刷新页面
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
