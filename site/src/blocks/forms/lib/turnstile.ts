// Turnstile helper for the forms block. The implementation now lives in the
// shared @lib layer so every block enforces the check identically (fail-closed);
// this module re-exports it to keep block-local import paths valid.
export { verifyTurnstile, enforceTurnstile, turnstileEnabled } from '@lib/turnstile';
export type { TurnstileResult } from '@lib/turnstile';
