"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, fetchApprovalDetail, fetchApprovalsList } from "./service";
import type { ApprovalDetail, ApprovalListResponse } from "./types";

export type ApprovalsListState =
  | { status: "loading" }
  | { status: "ok"; data: ApprovalListResponse }
  | { status: "error"; message: string };

export function useApprovalsList(params: {
  tab: "pending" | "decided";
  q: string;
  page: number;
  pageSize: number;
}): {
  state: ApprovalsListState;
  refetch: () => void;
} {
  const [state, setState] = useState<ApprovalsListState>({ status: "loading" });
  const [nonce, setNonce] = useState(0);
  const { tab, q, page, pageSize } = params;

  useEffect(() => {
    let active = true;
    // Flip to the loading skeleton asynchronously so the fetch can replace it.
    void Promise.resolve().then(() => {
      if (active) setState({ status: "loading" });
    });

    (async () => {
      try {
        const data = await fetchApprovalsList({ tab, q, page, pageSize });
        if (active) setState({ status: "ok", data });
      } catch (error) {
        if (!active) return;
        const message =
          error instanceof ApiError && error.status === 403
            ? "You do not have permission to view the approvals queue."
            : "Failed to load approvals. Please try again.";
        setState({ status: "error", message });
      }
    })();

    return () => {
      active = false;
    };
  }, [tab, q, page, pageSize, nonce]);

  const refetch = useCallback(() => setNonce((n) => n + 1), []);

  return { state, refetch };
}

export type ApprovalDetailState =
  | { status: "loading" }
  | { status: "ok"; data: ApprovalDetail }
  | { status: "not_found" }
  | { status: "error"; message: string };

export function useApprovalDetail(id: string): {
  state: ApprovalDetailState;
  setState: (next: ApprovalDetailState) => void;
  refetch: () => void;
} {
  const [state, setState] = useState<ApprovalDetailState>({ status: "loading" });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => {
      if (active) setState({ status: "loading" });
    });

    (async () => {
      try {
        const data = await fetchApprovalDetail(id);
        if (active) setState({ status: "ok", data });
      } catch (error) {
        if (!active) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({ status: "not_found" });
          return;
        }
        setState({
          status: "error",
          message: "Failed to load this application. Please try again.",
        });
      }
    })();

    return () => {
      active = false;
    };
  }, [id, nonce]);

  const refetch = useCallback(() => setNonce((n) => n + 1), []);

  return { state, setState, refetch };
}