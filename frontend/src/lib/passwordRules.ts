// The server checks more (common passwords, the email in the password): these are quick hints.
export const MIN_PASSWORD_LENGTH = 12;
export const MAX_PASSWORD_LENGTH = 128;

export function newPasswordProblems(password: string, confirm: string): string[] {
  const problems: string[] = [];
  if (password.length < MIN_PASSWORD_LENGTH) {
    problems.push(`Use at least ${MIN_PASSWORD_LENGTH} characters.`);
  }
  if (password.length > MAX_PASSWORD_LENGTH) {
    problems.push(`Use at most ${MAX_PASSWORD_LENGTH} characters.`);
  }
  if (password !== confirm) problems.push("The two passwords differ.");
  return problems;
}
