"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/lib/approvals/service";

import {
  fetchCancellationApprovalDetail,
  fetchCancellationApprovalsList,
  fetchCancellationEligibility,
  fetchCancellations,
} from "./service";
import type {
  CancellationApprovalDetail,
  CancellationApprovalListResponse,
  CancellationEligibility,
  CancellationRequestSummary,
} from "./types";

export type EligibilityState =
  | { status: "loading" }
  | { status: "ok"; data: CancellationEligibility }
  | { status: "error"; message: string };

export function useCancellationEligibility(
  applicationId: string
): { state: EligibilityState; refetch: () => void } {
  const [state, setState] = useState<EligibilityState>({ status: "loading" });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => {
      if (active) setState({ status: "loading" });
    });

    (async () => {
      try {
        const data = await fetchCancellationEligibility(applicationId);
        if (active) setState({ status: "ok", data });
      } catch (error) {
        if (!active) return;
        setState({ status: "error", message: errorMessage(error) });
      }
    })();

    return () => {
      active = false;
    };
  }, [applicationId, nonce]);

  const refetch = useCallback(() => setNonce((n) => n + 1), []);

  return { state, refetch };
}

export type CancellationListState =
  | { status: "loading" }
  | { status: "ok"; data: CancellationRequestSummary[] }
  | { status: "error"; message: string };

export function useCancellations(
  applicationId: string,
  refreshSignal?: unknown
): { state: CancellationListState; refetch: () => void } {
  const [state, setState] = useState<CancellationListState>({ status: "loading" });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => {
      if (active) setState({ status: "loading" });
    });

    (async () => {
      try {
        const data = await fetchCancellations(applicationId);
        if (active) setState({ status: "ok", data });
      } catch (error) {
        if (!active) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({ status: "ok", data: [] });
          return;
        }
        setState({ status: "error", message: errorMessage(error) });
      }
    })();

    return () => {
      active = false;
    };
  }, [applicationId, nonce, refreshSignal]);

  const refetch = useCallback(() => setNonce((n) => n + 1), []);

  return { state, refetch };
}

export type CancellationApprovalsListState =
  | { status: "loading" }
  | { status: "ok"; data: CancellationApprovalListResponse }
  | { status: "error"; message: string };

export function useCancellationApprovalsList(params: {
  tab: "pending" | "decided";
  page: number;
  pageSize: number;
}): { state: CancellationApprovalsListState; refetch: () => void } {
  const [state, setState] = useState<CancellationApprovalsListState>({
    status: "loading",
  });
  const [nonce, setNonce] = useState(0);
  const { tab, page, pageSize } = params;

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => {
      if (active) setState({ status: "loading" });
    });

    (async () => {
      try {
        const data = await fetchCancellationApprovalsList(tab, page, pageSize);
        if (active) setState({ status: "ok", data });
      } catch (error) {
        if (!active) return;
        setState({ status: "error", message: errorMessage(error) });
      }
    })();

    return () => {
      active = false;
    };
  }, [tab, page, pageSize, nonce]);

  const refetch = useCallback(() => setNonce((n) => n + 1), []);

  return { state, refetch };
}

export type CancellationApprovalDetailState =
  | { status: "loading" }
  | { status: "ok"; data: CancellationApprovalDetail }
  | { status: "not_found" }
  | { status: "error"; message: string };

export function useCancellationApprovalDetail(
  requestId: string
): {
  state: CancellationApprovalDetailState;
  setState: (next: CancellationApprovalDetailState) => void;
  refetch: () => void;
} {
  const [state, setState] = useState<CancellationApprovalDetailState>({
    status: "loading",
  });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let active = true;
    void Promise.resolve().then(() => {
      if (active) setState({ status: "loading" });
    });

    (async () => {
      try {
        const data = await fetchCancellationApprovalDetail(requestId);
        if (active) setState({ status: "ok", data });
      } catch (error) {
        if (!active) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({ status: "not_found" });
          return;
        }
        setState({ status: "error", message: errorMessage(error) });
      }
    })();

    return () => {
      active = false;
    };
  }, [requestId, nonce]);

  const refetch = useCallback(() => setNonce((n) => n + 1), []);

  return { state, setState, refetch };
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) {
    return "You do not have permission to view this.";
  }
  return "Something went wrong. Please try again.";
}