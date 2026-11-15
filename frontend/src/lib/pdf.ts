export function base64ToPdfBlob(base64: string): Blob {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type: "application/pdf" });
}

export type DocumentKind = "cv" | "letter";

const LETTER_PREFIXES: Record<string, string> = { fr: "Lettre_de_motivation", de: "Anschreiben" };
const DEFAULT_LETTER_PREFIX = "Cover_Letter";

function capitalize(word: string): string {
  return word === word.toUpperCase()
    ? word.charAt(0) + word.slice(1).toLowerCase()
    : word.charAt(0).toUpperCase() + word.slice(1);
}

/** "Loqman MAKOURI" -> "Loqman_Makouri". Only ASCII letters and digits are kept. */
export function namePart(fullName: string): string {
  const ascii = fullName
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^\x00-\x7F]/g, "");
  return (ascii.match(/[A-Za-z0-9]+/g) ?? []).map(capitalize).join("_");
}

/** CV_Loqman_Makouri.pdf, Lettre_de_motivation_Loqman_Makouri.pdf, Cover_Letter_....pdf */
export function documentFileName(kind: DocumentKind, fullName: string, language: string): string {
  const prefix = kind === "cv" ? "CV" : (LETTER_PREFIXES[language] ?? DEFAULT_LETTER_PREFIX);
  const name = namePart(fullName);
  return name ? `${prefix}_${name}.pdf` : `${prefix}.pdf`;
}

export function imageDataUri(base64: string): string {
  const mime = base64.startsWith("/9j/") ? "image/jpeg" : "image/png";
  return `data:${mime};base64,${base64}`;
}
