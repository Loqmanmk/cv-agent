import type { CoverLetter, Cv, MatchReport } from "@/lib/types";

export function makeReport(overrides: Partial<MatchReport> = {}): MatchReport {
  return {
    matchedSkills: ["Python"],
    missingSkills: [
      { name: "Django", required: true, group: "Back-end" },
      { name: "Kubernetes", required: true, group: null },
      { name: "Terraform", required: false, group: null },
    ],
    changes: ["Profile rewritten with the words of the offer."],
    ...overrides,
  };
}

export function makeCv(overrides: Partial<Cv> = {}): Cv {
  return {
    header: {
      name: "Jane Doe",
      headline: "Software Engineer",
      target_line: "Looking for an internship",
      phone: "+00 000 000 000",
      email: "jane@example.com",
      linkedin: "",
      github: "",
      location: "Morocco",
    },
    profile: "Original profile.",
    experiences: [
      {
        title: "Mobile Developer",
        company: "Acme",
        city: "Casablanca",
        start: "Aug. 2026",
        end: "Sept. 2026",
        bullets: ["Built an Android app", "Integrated a REST API"],
      },
    ],
    projects: [{ title: "PathFinder", subtitle: "", bullets: ["Machine learning model"] }],
    education: [
      {
        degree: "Engineering",
        school: "School",
        city: "Oujda",
        start: "2024",
        end: "2027",
        note: "",
      },
    ],
    skills: [
      { category: "Back-end", items: ["Python", "FastAPI"] },
      { category: "Front-end", items: ["React"] },
    ],
    certifications: [{ name: "Cert A", issuer: "", status: "In progress" }],
    languages: [{ name: "French", level: "Fluent" }],
    interests: ["Chess"],
    ...overrides,
  };
}

export function makeLetter(): CoverLetter {
  return {
    sender: {
      name: "Jane Doe",
      address: "Oujda, Maroc",
      email: "jane@example.com",
      phone: "+00 000 000 000",
    },
    recipient: { contact: "", company: "Acme", address: "" },
    place_date: "Fait à Oujda, le 6 novembre 2026",
    subject: "Objet : Candidature pour le poste de Stagiaire",
    greeting: "Madame, Monsieur,",
    paragraphs: [
      "Opening paragraph.",
      "Experience paragraph.",
      "Motivation paragraph.",
      "Fixed closing.",
    ],
    signature: "Jane Doe",
  };
}

export function makeResultBody(overrides: Record<string, unknown> = {}) {
  return {
    job_title: "Stagiaire DataLab",
    company: "Coface",
    language: "fr",
    photo_used: true,
    cv_pdf_base64: btoa("%PDF-cv"),
    letter_pdf_base64: btoa("%PDF-letter"),
    original_cv: makeCv(),
    cv: makeCv({ profile: "Tailored profile." }),
    letter: makeLetter(),
    photo_base64: "iVBORw0KGgo=",
    report: {
      matched_skills: ["Python"],
      missing_skills: [
        { name: "Django", required: true, group: "Back-end" },
        { name: "Kubernetes", required: true, group: null },
        { name: "Terraform", required: false },
      ],
      changes: ["Profile rewritten with the words of the offer."],
    },
    ...overrides,
  };
}
